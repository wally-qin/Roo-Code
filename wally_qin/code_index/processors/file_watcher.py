"""
文件监听器

监控工作空间中的文件变化，自动更新代码索引。
基于原TypeScript项目的FileWatcher重新实现。
"""

import asyncio
import os
import time
from typing import Optional, Dict, Any, List, Set
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..interfaces import IFileWatcher, ICodeParser, IEmbedder, IVectorStore, FileProcessingResult, PointStruct
from ..constants import SUPPORTED_EXTENSIONS, BATCH_PROCESSING_DELAY, MAX_CHUNK_SIZE, MIN_CHUNK_SIZE

logger = logging.getLogger(__name__)


class CodeFileEventHandler(FileSystemEventHandler):
    """代码文件事件处理器"""
    
    def __init__(self, file_watcher: 'FileWatcher'):
        self.file_watcher = file_watcher
        
    def on_any_event(self, event: FileSystemEvent):
        """处理任何文件系统事件"""
        if event.is_directory:
            return
            
        file_path = event.src_path
        
        # 检查是否是支持的文件类型
        if not self.file_watcher._has_supported_extension(file_path):
            return
            
        # 添加到待处理队列
        self.file_watcher._add_to_processing_queue(file_path, event.event_type)


class FileWatcher(IFileWatcher):
    """文件监听器实现"""
    
    def __init__(self, workspace_path: str, parser: ICodeParser, 
                 embedder: IEmbedder, vector_store: IVectorStore, cache_manager):
        """
        初始化文件监听器
        
        Args:
            workspace_path: 工作空间路径
            parser: 代码解析器
            embedder: 嵌入器
            vector_store: 向量存储
            cache_manager: 缓存管理器
        """
        self.workspace_path = workspace_path
        self.parser = parser
        self.embedder = embedder
        self.vector_store = vector_store
        self.cache_manager = cache_manager
        
        # 监听器组件
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[CodeFileEventHandler] = None
        
        # 事件系统
        self._batch_start_event = asyncio.Event()
        self._batch_progress_event = asyncio.Event()
        self._batch_complete_event = asyncio.Event()
        
        # 处理队列和状态
        self._processing_queue: Dict[str, str] = {}  # file_path -> event_type
        self._processing_task: Optional[asyncio.Task] = None
        self._is_processing = False
        self._last_activity_time = 0
        
    @property
    def on_batch_start(self) -> asyncio.Event:
        """批处理开始事件"""
        return self._batch_start_event
        
    @property
    def on_batch_progress(self) -> asyncio.Event:
        """批处理进度事件"""
        return self._batch_progress_event
        
    @property
    def on_batch_complete(self) -> asyncio.Event:
        """批处理完成事件"""
        return self._batch_complete_event
        
    async def initialize(self) -> None:
        """初始化文件监听器"""
        try:
            # 创建事件处理器
            self.event_handler = CodeFileEventHandler(self)
            
            # 创建观察者
            self.observer = Observer()
            self.observer.schedule(
                self.event_handler,
                self.workspace_path,
                recursive=True
            )
            
            # 启动批处理任务
            self._processing_task = asyncio.create_task(self._batch_processing_loop())
            
            logger.info("文件监听器初始化完成")
            
        except Exception as e:
            logger.error(f"文件监听器初始化失败: {e}")
            raise
            
    def start_watching(self) -> None:
        """开始监听文件变化"""
        if self.observer and not self.observer.is_alive():
            self.observer.start()
            logger.info("文件监听器已启动")
        else:
            logger.warning("文件监听器已在运行或未初始化")
            
    def stop_watching(self) -> None:
        """停止监听文件变化"""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("文件监听器已停止")
            
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            
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
                # 文件被删除，从索引中移除
                await self.vector_store.delete_points_by_file_path(file_path)
                await self.cache_manager.remove_from_cache(file_path)
                
                return FileProcessingResult(
                    path=file_path,
                    status="success",
                    reason="文件已删除，从索引中移除"
                )
                
            # 检查文件是否支持
            if not self._has_supported_extension(file_path):
                return FileProcessingResult(
                    path=file_path,
                    status="skipped",
                    reason="不支持的文件类型"
                )
                
            # 计算文件哈希
            file_hash = await self._calculate_file_hash(file_path)
            
            # 检查缓存
            if await self.cache_manager.is_file_cached(file_path, file_hash):
                return FileProcessingResult(
                    path=file_path,
                    status="skipped",
                    reason="文件未发生变化"
                )
                
            # 删除旧的索引数据
            await self.vector_store.delete_points_by_file_path(file_path)
            
            # 解析文件
            code_blocks = await self.parser.parse_file(file_path, file_hash=file_hash)
            
            if not code_blocks:
                # 更新缓存但不创建索引
                await self.cache_manager.cache_file(file_path, file_hash)
                return FileProcessingResult(
                    path=file_path,
                    status="success",
                    reason="文件无有效代码块"
                )
                
            # 过滤有效代码块
            valid_blocks = [
                block for block in code_blocks
                if MIN_CHUNK_SIZE <= len(block.content) <= MAX_CHUNK_SIZE
            ]
            
            if not valid_blocks:
                await self.cache_manager.cache_file(file_path, file_hash)
                return FileProcessingResult(
                    path=file_path,
                    status="success",
                    reason="无有效代码块"
                )
                
            # 生成嵌入向量点
            points = await self._create_embedding_points(valid_blocks)
            
            # 插入向量存储
            await self.vector_store.upsert_points(points)
            
            # 更新缓存
            await self.cache_manager.cache_file(file_path, file_hash)
            
            return FileProcessingResult(
                path=file_path,
                status="success",
                new_hash=file_hash,
                points_to_upsert=points
            )
            
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {e}")
            return FileProcessingResult(
                path=file_path,
                status="error",
                error=e,
                reason=str(e)
            )
            
    def _add_to_processing_queue(self, file_path: str, event_type: str):
        """添加文件到处理队列"""
        self._processing_queue[file_path] = event_type
        self._last_activity_time = time.time()
        
    async def _batch_processing_loop(self):
        """批处理循环"""
        while True:
            try:
                await asyncio.sleep(0.5)  # 检查间隔
                
                # 检查是否有待处理的文件
                if not self._processing_queue:
                    continue
                    
                # 检查是否达到批处理延迟
                current_time = time.time()
                if current_time - self._last_activity_time < BATCH_PROCESSING_DELAY:
                    continue
                    
                # 避免重复处理
                if self._is_processing:
                    continue
                    
                # 开始批处理
                await self._process_queued_files()
                
            except asyncio.CancelledError:
                logger.info("批处理循环已取消")
                break
            except Exception as e:
                logger.error(f"批处理循环错误: {e}")
                await asyncio.sleep(1)  # 错误时稍作等待
                
    async def _process_queued_files(self):
        """处理队列中的文件"""
        if not self._processing_queue:
            return
            
        self._is_processing = True
        
        try:
            # 触发批处理开始事件
            self._batch_start_event.set()
            self._batch_start_event.clear()
            
            # 获取待处理文件列表
            files_to_process = list(self._processing_queue.keys())
            self._processing_queue.clear()
            
            logger.info(f"开始批处理 {len(files_to_process)} 个文件")
            
            # 逐个处理文件
            for file_path in files_to_process:
                try:
                    result = await self.process_file(file_path)
                    logger.debug(f"处理文件结果: {file_path} -> {result.status}")
                    
                    # 触发进度事件
                    self._batch_progress_event.set()
                    self._batch_progress_event.clear()
                    
                except Exception as e:
                    logger.error(f"处理文件失败 {file_path}: {e}")
                    
            # 触发批处理完成事件
            self._batch_complete_event.set()
            self._batch_complete_event.clear()
            
            logger.info(f"批处理完成，处理了 {len(files_to_process)} 个文件")
            
        finally:
            self._is_processing = False
            
    def _has_supported_extension(self, file_path: str) -> bool:
        """检查文件是否有支持的扩展名"""
        _, ext = os.path.splitext(file_path.lower())
        return ext in SUPPORTED_EXTENSIONS
        
    async def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        try:
            import hashlib
            hash_obj = hashlib.md5()
            
            def read_file():
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_obj.update(chunk)
                return hash_obj.hexdigest()
                
            return await asyncio.to_thread(read_file)
            
        except Exception:
            return ""
            
    async def _create_embedding_points(self, code_blocks: List) -> List[PointStruct]:
        """为代码块创建嵌入向量点"""
        points = []
        
        # 提取文本内容
        texts = [block.content for block in code_blocks]
        
        # 批量生成嵌入
        embedding_response = await self.embedder.create_embeddings(texts)
        
        # 创建向量点
        for i, (block, embedding) in enumerate(zip(code_blocks, embedding_response.embeddings)):
            point_id = f"{block.file_hash}_{i}"
            
            payload = {
                "filePath": block.file_path,
                "codeChunk": block.content,
                "startLine": block.start_line,
                "endLine": block.end_line,
                "segmentHash": block.segment_hash,
                "type": block.type,
                "identifier": block.identifier
            }
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            ))
            
        return points
        
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queue_size": len(self._processing_queue),
            "is_processing": self._is_processing,
            "observer_alive": self.observer.is_alive() if self.observer else False,
            "queued_files": list(self._processing_queue.keys())
        }