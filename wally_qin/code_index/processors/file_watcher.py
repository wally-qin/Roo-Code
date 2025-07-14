"""
文件监听器实现

基于原TypeScript项目的FileWatcher类重新实现，
支持文件系统事件监听、批处理文件变更和自动索引更新。
"""

import os
import hashlib
import asyncio
from typing import Dict, List, Optional, Set, Callable, Any
import logging
from pathlib import Path
import fnmatch
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

from ..interfaces import (
    IFileWatcher, ICodeParser, IEmbedder, IVectorStore,
    FileProcessingResult, BatchProcessingSummary, PointStruct, CodeBlock
)
from ..managers.cache_manager import CacheManager
from ..constants import (
    MAX_FILE_SIZE_BYTES, BATCH_SEGMENT_THRESHOLD, MAX_BATCH_RETRIES,
    INITIAL_RETRY_DELAY_MS, SUPPORTED_EXTENSIONS, BATCH_PROCESSING_DELAY
)

logger = logging.getLogger(__name__)


class FileWatcher(IFileWatcher):
    """文件监听器实现"""
    
    def __init__(self, workspace_path: str, cache_manager: CacheManager,
                 code_parser: Optional[ICodeParser] = None,
                 embedder: Optional[IEmbedder] = None,
                 vector_store: Optional[IVectorStore] = None,
                 ignore_patterns: Optional[List[str]] = None):
        """
        初始化文件监听器
        
        Args:
            workspace_path: 工作空间路径
            cache_manager: 缓存管理器
            code_parser: 代码解析器
            embedder: 嵌入器
            vector_store: 向量存储
            ignore_patterns: 忽略模式列表
        """
        self.workspace_path = os.path.abspath(workspace_path)
        self.cache_manager = cache_manager
        self.code_parser = code_parser
        self.embedder = embedder
        self.vector_store = vector_store
        self.ignore_patterns = ignore_patterns or [
            '*.pyc', '__pycache__', '.git', '.svn', '.hg',
            'node_modules', '.env', '*.log', '*.tmp'
        ]
        
        # 文件系统监听器
        self.observer: Optional[Observer] = None
        self.event_handler: Optional['FileChangeHandler'] = None
        
        # 批处理相关
        self.accumulated_events: Dict[str, Dict[str, Any]] = {}
        self.batch_timer: Optional[threading.Timer] = None
        self.batch_lock = asyncio.Lock()
        self.is_watching = False
        
        # 事件处理
        self._on_batch_start = asyncio.Event()
        self._on_batch_progress = asyncio.Event()
        self._on_batch_complete = asyncio.Event()
        
        # 批处理延迟（秒）
        self.BATCH_DEBOUNCE_DELAY = BATCH_PROCESSING_DELAY
        self.FILE_PROCESSING_CONCURRENCY_LIMIT = 10
        
    async def initialize(self) -> None:
        """初始化文件监听器"""
        if not os.path.exists(self.workspace_path):
            raise ValueError(f"工作空间路径不存在: {self.workspace_path}")
            
        # 创建事件处理器
        self.event_handler = FileChangeHandler(self)
        
        # 创建观察者
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            self.workspace_path,
            recursive=True
        )
        
        logger.info(f"文件监听器已初始化，监听路径: {self.workspace_path}")
        
    def start_watching(self) -> None:
        """开始监听文件变化"""
        if not self.observer:
            raise RuntimeError("文件监听器未初始化")
            
        if not self.is_watching:
            self.observer.start()
            self.is_watching = True
            logger.info("文件监听器已启动")
            
    def stop_watching(self) -> None:
        """停止监听文件变化"""
        if self.observer and self.is_watching:
            self.observer.stop()
            self.observer.join()
            self.is_watching = False
            
            # 取消批处理定时器
            if self.batch_timer:
                self.batch_timer.cancel()
                self.batch_timer = None
                
            logger.info("文件监听器已停止")
            
    @property
    def on_batch_start(self) -> asyncio.Event:
        """批处理开始事件"""
        return self._on_batch_start
        
    @property
    def on_batch_progress(self) -> asyncio.Event:
        """批处理进度事件"""
        return self._on_batch_progress
        
    @property
    def on_batch_complete(self) -> asyncio.Event:
        """批处理完成事件"""
        return self._on_batch_complete
        
    async def handle_file_event(self, event_type: str, file_path: str) -> None:
        """处理文件事件"""
        if not self._should_process_file(file_path):
            return
            
        # 记录事件
        async with self.batch_lock:
            self.accumulated_events[file_path] = {
                'type': event_type,
                'timestamp': time.time(),
                'path': file_path
            }
            
        # 调度批处理
        self._schedule_batch_processing()
        
    def _should_process_file(self, file_path: str) -> bool:
        """检查是否应该处理文件"""
        # 检查文件扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False
            
        # 检查忽略模式
        filename = os.path.basename(file_path)
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return False
                
        # 检查是否在忽略的目录中
        ignored_dirs = {'.git', '.svn', '.hg', '__pycache__', 'node_modules'}
        path_parts = Path(file_path).parts
        if any(part in ignored_dirs for part in path_parts):
            return False
            
        return True
        
    def _schedule_batch_processing(self) -> None:
        """调度批处理"""
        # 取消之前的定时器
        if self.batch_timer:
            self.batch_timer.cancel()
            
        # 创建新的定时器
        self.batch_timer = threading.Timer(
            self.BATCH_DEBOUNCE_DELAY,
            self._trigger_batch_processing
        )
        self.batch_timer.start()
        
    def _trigger_batch_processing(self) -> None:
        """触发批处理"""
        # 在新的事件循环中运行异步批处理
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._process_batch())
            loop.close()
        except Exception as error:
            logger.error(f"批处理执行错误: {error}")
            
    async def _process_batch(self) -> None:
        """处理批量文件变更"""
        async with self.batch_lock:
            if not self.accumulated_events:
                return
                
            # 复制事件并清空累积器
            events_to_process = self.accumulated_events.copy()
            self.accumulated_events.clear()
            
        logger.info(f"开始处理批次: {len(events_to_process)} 个文件")
        
        # 触发批处理开始事件
        self._on_batch_start.set()
        self._on_batch_start.clear()
        
        # 分类事件
        files_to_delete = []
        files_to_upsert = []
        
        for file_path, event_info in events_to_process.items():
            if event_info['type'] == 'delete':
                files_to_delete.append(file_path)
            else:  # create or modify
                files_to_upsert.append((file_path, event_info))
                
        batch_results: List[FileProcessingResult] = []
        processed_count = 0
        total_count = len(events_to_process)
        
        # 处理删除
        if files_to_delete and self.vector_store:
            try:
                await self.vector_store.delete_points_by_multiple_file_paths(files_to_delete)
                for file_path in files_to_delete:
                    await self.cache_manager.remove_hash(file_path)
                    batch_results.append(FileProcessingResult(
                        path=file_path,
                        status="success",
                        reason="File deleted from index"
                    ))
                    processed_count += 1
                    
                logger.info(f"删除了 {len(files_to_delete)} 个文件的索引")
            except Exception as error:
                logger.error(f"批量删除失败: {error}")
                for file_path in files_to_delete:
                    batch_results.append(FileProcessingResult(
                        path=file_path,
                        status="error",
                        error=error
                    ))
                    
        # 处理创建和修改
        if files_to_upsert:
            # 并发处理文件
            semaphore = asyncio.Semaphore(self.FILE_PROCESSING_CONCURRENCY_LIMIT)
            tasks = []
            
            for file_path, event_info in files_to_upsert:
                task = asyncio.create_task(
                    self._process_file_with_semaphore(semaphore, file_path)
                )
                tasks.append(task)
                
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            points_to_upsert = []
            successful_files = []
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"文件处理异常: {result}")
                    continue
                    
                batch_results.append(result)
                processed_count += 1
                
                if (result.status == "processed_for_batching" and 
                    result.points_to_upsert):
                    points_to_upsert.extend(result.points_to_upsert)
                    successful_files.append({
                        'path': result.path,
                        'new_hash': result.new_hash
                    })
                    
            # 批量上传向量
            if points_to_upsert and self.vector_store:
                try:
                    await self.vector_store.upsert_points(points_to_upsert)
                    
                    # 更新缓存
                    for file_info in successful_files:
                        await self.cache_manager.update_hash(
                            file_info['path'], file_info['new_hash']
                        )
                        
                    logger.info(f"成功上传 {len(points_to_upsert)} 个向量点")
                except Exception as error:
                    logger.error(f"批量上传失败: {error}")
                    
        # 报告进度
        self._on_batch_progress.set()
        self._on_batch_progress.clear()
        
        # 触发批处理完成事件
        summary = BatchProcessingSummary(
            processed_files=batch_results,
            batch_error=None
        )
        
        self._on_batch_complete.set()
        self._on_batch_complete.clear()
        
        logger.info(f"批处理完成: 处理了 {processed_count}/{total_count} 个文件")
        
    async def _process_file_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                         file_path: str) -> FileProcessingResult:
        """使用信号量控制并发处理文件"""
        async with semaphore:
            return await self.process_file(file_path)
            
    async def process_file(self, file_path: str) -> FileProcessingResult:
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件处理结果
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return FileProcessingResult(
                    path=file_path,
                    status="skipped",
                    reason="File does not exist"
                )
                
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_BYTES:
                return FileProcessingResult(
                    path=file_path,
                    status="skipped",
                    reason="File is too large"
                )
                
            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    return FileProcessingResult(
                        path=file_path,
                        status="error",
                        error=e
                    )
                    
            # 计算文件哈希
            new_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            
            # 检查文件是否已更改
            cached_hash = await self.cache_manager.get_hash(file_path)
            if cached_hash == new_hash:
                return FileProcessingResult(
                    path=file_path,
                    status="skipped",
                    reason="File has not changed"
                )
                
            # 解析文件（如果有解析器）
            if not self.code_parser:
                return FileProcessingResult(
                    path=file_path,
                    status="skipped",
                    reason="No code parser available"
                )
                
            blocks = await self.code_parser.parse_file(file_path, content, new_hash)
            
            # 准备向量点（如果有嵌入器）
            points_to_upsert = []
            if self.embedder and blocks:
                texts = [block.content for block in blocks]
                embedding_response = await self.embedder.create_embeddings(texts)
                embeddings = embedding_response.embeddings
                
                for i, (block, embedding) in enumerate(zip(blocks, embeddings)):
                    point_id = self._generate_point_id(block)
                    point = PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            'file_path': block.file_path,
                            'identifier': block.identifier,
                            'type': block.type,
                            'start_line': block.start_line,
                            'end_line': block.end_line,
                            'content': block.content,
                            'file_hash': block.file_hash,
                            'segment_hash': block.segment_hash,
                            'workspace_path': self.workspace_path
                        }
                    )
                    points_to_upsert.append(point)
                    
            return FileProcessingResult(
                path=file_path,
                status="processed_for_batching",
                new_hash=new_hash,
                points_to_upsert=points_to_upsert
            )
            
        except Exception as error:
            return FileProcessingResult(
                path=file_path,
                status="local_error",
                error=error
            )
            
    def _generate_point_id(self, block: CodeBlock) -> str:
        """为代码块生成唯一ID"""
        id_string = f"{block.file_path}:{block.start_line}:{block.segment_hash}"
        return hashlib.sha256(id_string.encode('utf-8')).hexdigest()[:16]
        
    async def get_watch_statistics(self) -> Dict[str, Any]:
        """获取监听统计信息"""
        return {
            'is_watching': self.is_watching,
            'workspace_path': self.workspace_path,
            'accumulated_events': len(self.accumulated_events),
            'batch_delay': self.BATCH_DEBOUNCE_DELAY,
            'concurrency_limit': self.FILE_PROCESSING_CONCURRENCY_LIMIT
        }


class FileChangeHandler(FileSystemEventHandler):
    """文件系统事件处理器"""
    
    def __init__(self, file_watcher: FileWatcher):
        """
        初始化事件处理器
        
        Args:
            file_watcher: 文件监听器实例
        """
        super().__init__()
        self.file_watcher = file_watcher
        
    def on_created(self, event):
        """文件创建事件"""
        if not event.is_directory:
            asyncio.create_task(
                self.file_watcher.handle_file_event('create', event.src_path)
            )
            
    def on_modified(self, event):
        """文件修改事件"""
        if not event.is_directory:
            asyncio.create_task(
                self.file_watcher.handle_file_event('change', event.src_path)
            )
            
    def on_deleted(self, event):
        """文件删除事件"""
        if not event.is_directory:
            asyncio.create_task(
                self.file_watcher.handle_file_event('delete', event.src_path)
            )