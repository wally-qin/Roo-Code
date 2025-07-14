"""
目录扫描器实现

基于原TypeScript项目的DirectoryScanner类重新实现，
支持递归扫描目录、解析文件、批处理嵌入和缓存管理。
"""

import os
import hashlib
import asyncio
from typing import List, Optional, Dict, Any, Set, Callable
import logging
from pathlib import Path
import fnmatch

from ..interfaces import (
    IDirectoryScanner, ICodeParser, IEmbedder, IVectorStore, 
    CodeBlock, PointStruct, FileProcessingResult, BatchProcessingSummary
)
from ..managers.cache_manager import CacheManager
from ..constants import (
    MAX_FILE_SIZE_BYTES, MAX_LIST_FILES_LIMIT, BATCH_SEGMENT_THRESHOLD,
    MAX_BATCH_RETRIES, INITIAL_RETRY_DELAY_MS, PARSING_CONCURRENCY,
    BATCH_PROCESSING_CONCURRENCY, SUPPORTED_EXTENSIONS
)

logger = logging.getLogger(__name__)


class DirectoryScanner(IDirectoryScanner):
    """目录扫描器实现"""
    
    def __init__(self, embedder: IEmbedder, vector_store: IVectorStore,
                 code_parser: ICodeParser, cache_manager: CacheManager,
                 ignore_patterns: Optional[List[str]] = None):
        """
        初始化目录扫描器
        
        Args:
            embedder: 嵌入器
            vector_store: 向量存储
            code_parser: 代码解析器
            cache_manager: 缓存管理器
            ignore_patterns: 忽略模式列表
        """
        self.embedder = embedder
        self.vector_store = vector_store
        self.code_parser = code_parser
        self.cache_manager = cache_manager
        self.ignore_patterns = ignore_patterns or [
            '*.pyc', '__pycache__', '.git', '.svn', '.hg',
            'node_modules', '.env', '*.log', '*.tmp'
        ]
        
        # 并发控制
        self.parse_semaphore = asyncio.Semaphore(PARSING_CONCURRENCY)
        self.batch_semaphore = asyncio.Semaphore(BATCH_PROCESSING_CONCURRENCY)
        self.batch_lock = asyncio.Lock()
        
        # 批处理累积器
        self.current_batch_blocks: List[CodeBlock] = []
        self.current_batch_texts: List[str] = []
        self.current_batch_file_infos: List[Dict[str, Any]] = []
        self.active_batch_tasks: List[asyncio.Task] = []
        
    async def scan_directory(self, directory: str, 
                           on_error: Optional[Callable[[Exception], None]] = None,
                           on_blocks_indexed: Optional[Callable[[int], None]] = None,
                           on_file_parsed: Optional[Callable[[int], None]] = None) -> Dict[str, Any]:
        """
        递归扫描目录寻找代码块
        
        Args:
            directory: 要扫描的目录
            on_error: 错误处理回调
            on_blocks_indexed: 块索引完成回调
            on_file_parsed: 文件解析完成回调
            
        Returns:
            包含代码块和统计信息的字典
        """
        directory_path = os.path.abspath(directory)
        
        if not os.path.exists(directory_path):
            raise ValueError(f"目录不存在: {directory_path}")
            
        # 获取所有文件
        all_files = await self._list_files_recursively(directory_path)
        
        # 过滤支持的文件
        supported_files = self._filter_supported_files(all_files)
        
        logger.info(f"找到 {len(supported_files)} 个支持的文件进行处理")
        
        # 初始化跟踪变量
        processed_files: Set[str] = set()
        code_blocks: List[CodeBlock] = []
        processed_count = 0
        skipped_count = 0
        total_block_count = 0
        
        # 并行处理所有文件
        tasks = []
        for file_path in supported_files:
            task = asyncio.create_task(
                self._process_file_with_semaphore(
                    file_path, directory_path, processed_files, code_blocks,
                    on_file_parsed, on_error
                )
            )
            tasks.append(task)
            
        # 等待所有文件处理完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for result in results:
            if isinstance(result, Exception):
                if on_error:
                    on_error(result)
                logger.error(f"文件处理错误: {result}")
            elif isinstance(result, dict):
                if result['status'] == 'processed':
                    processed_count += 1
                    total_block_count += result.get('block_count', 0)
                elif result['status'] == 'skipped':
                    skipped_count += 1
                    
        # 处理剩余的批次
        if self.current_batch_blocks:
            await self._process_final_batch(directory_path, on_error, on_blocks_indexed)
            
        # 等待所有批处理任务完成
        if self.active_batch_tasks:
            await asyncio.gather(*self.active_batch_tasks, return_exceptions=True)
            
        return {
            'codeBlocks': code_blocks,
            'stats': {
                'processed': processed_count,
                'skipped': skipped_count
            },
            'totalBlockCount': total_block_count
        }
        
    async def _list_files_recursively(self, directory: str) -> List[str]:
        """递归列出目录中的所有文件"""
        files = []
        count = 0
        
        for root, dirs, filenames in os.walk(directory):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if not self._should_ignore_directory(d)]
            
            for filename in filenames:
                if count >= MAX_LIST_FILES_LIMIT:
                    logger.warning(f"达到文件数量限制 {MAX_LIST_FILES_LIMIT}")
                    break
                    
                file_path = os.path.join(root, filename)
                if not self._should_ignore_file(file_path):
                    files.append(file_path)
                    count += 1
                    
            if count >= MAX_LIST_FILES_LIMIT:
                break
                
        return files
        
    def _filter_supported_files(self, files: List[str]) -> List[str]:
        """过滤支持的文件类型"""
        supported_files = []
        
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                supported_files.append(file_path)
                
        return supported_files
        
    def _should_ignore_directory(self, dirname: str) -> bool:
        """检查是否应该忽略目录"""
        ignore_dirs = {
            '.git', '.svn', '.hg', '__pycache__', 'node_modules',
            '.vscode', '.idea', '.DS_Store', 'build', 'dist'
        }
        return dirname in ignore_dirs
        
    def _should_ignore_file(self, file_path: str) -> bool:
        """检查是否应该忽略文件"""
        filename = os.path.basename(file_path)
        
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
                
        return False
        
    async def _process_file_with_semaphore(self, file_path: str, workspace_path: str,
                                         processed_files: Set[str], code_blocks: List[CodeBlock],
                                         on_file_parsed: Optional[Callable[[int], None]],
                                         on_error: Optional[Callable[[Exception], None]]) -> Dict[str, Any]:
        """使用信号量控制并发处理文件"""
        async with self.parse_semaphore:
            return await self._process_file(
                file_path, workspace_path, processed_files, code_blocks,
                on_file_parsed, on_error
            )
            
    async def _process_file(self, file_path: str, workspace_path: str,
                          processed_files: Set[str], code_blocks: List[CodeBlock],
                          on_file_parsed: Optional[Callable[[int], None]],
                          on_error: Optional[Callable[[Exception], None]]) -> Dict[str, Any]:
        """处理单个文件"""
        try:
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.debug(f"跳过大文件: {file_path} ({file_size} bytes)")
                return {'status': 'skipped', 'reason': 'file_too_large'}
                
            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # 尝试其他编码
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"无法读取文件 {file_path}: {e}")
                    return {'status': 'skipped', 'reason': 'encoding_error'}
                    
            # 计算文件哈希
            current_file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            processed_files.add(file_path)
            
            # 检查缓存
            cached_file_hash = await self.cache_manager.get_hash(file_path)
            if cached_file_hash == current_file_hash:
                return {'status': 'skipped', 'reason': 'unchanged'}
                
            # 解析文件
            blocks = await self.code_parser.parse_file(file_path, content, current_file_hash)
            file_block_count = len(blocks)
            
            if on_file_parsed:
                on_file_parsed(file_block_count)
                
            code_blocks.extend(blocks)
            
            # 处理嵌入（如果配置了）
            if self.embedder and self.vector_store and blocks:
                await self._add_blocks_to_batch(blocks, file_path, current_file_hash, workspace_path)
            else:
                # 只更新缓存哈希
                await self.cache_manager.update_hash(file_path, current_file_hash)
                
            return {
                'status': 'processed',
                'block_count': file_block_count
            }
            
        except Exception as error:
            logger.error(f"处理文件错误 {file_path}: {error}")
            if on_error:
                on_error(error)
            return {'status': 'error', 'error': str(error)}
            
    async def _add_blocks_to_batch(self, blocks: List[CodeBlock], file_path: str,
                                 file_hash: str, workspace_path: str) -> None:
        """将代码块添加到批处理队列"""
        async with self.batch_lock:
            added_blocks_from_file = False
            
            for block in blocks:
                trimmed_content = block.content.strip()
                if trimmed_content:
                    self.current_batch_blocks.append(block)
                    self.current_batch_texts.append(trimmed_content)
                    added_blocks_from_file = True
                    
            if added_blocks_from_file:
                is_new = not await self.cache_manager.get_hash(file_path)
                self.current_batch_file_infos.append({
                    'filePath': file_path,
                    'fileHash': file_hash,
                    'isNew': is_new
                })
                
            # 检查是否达到批处理阈值
            if len(self.current_batch_blocks) >= BATCH_SEGMENT_THRESHOLD:
                await self._process_current_batch(workspace_path)
                
    async def _process_current_batch(self, workspace_path: str) -> None:
        """处理当前批次"""
        # 复制当前批次数据并清空累积器
        batch_blocks = self.current_batch_blocks.copy()
        batch_texts = self.current_batch_texts.copy()
        batch_file_infos = self.current_batch_file_infos.copy()
        
        self.current_batch_blocks.clear()
        self.current_batch_texts.clear()
        self.current_batch_file_infos.clear()
        
        # 创建批处理任务
        task = asyncio.create_task(
            self._process_batch_with_semaphore(
                batch_blocks, batch_texts, batch_file_infos, workspace_path
            )
        )
        self.active_batch_tasks.append(task)
        
    async def _process_final_batch(self, workspace_path: str,
                                 on_error: Optional[Callable[[Exception], None]],
                                 on_blocks_indexed: Optional[Callable[[int], None]]) -> None:
        """处理最后的批次"""
        if self.current_batch_blocks:
            await self._process_batch(
                self.current_batch_blocks, self.current_batch_texts,
                self.current_batch_file_infos, workspace_path,
                on_error, on_blocks_indexed
            )
            
    async def _process_batch_with_semaphore(self, batch_blocks: List[CodeBlock],
                                          batch_texts: List[str],
                                          batch_file_infos: List[Dict[str, Any]],
                                          workspace_path: str) -> None:
        """使用信号量控制批处理"""
        async with self.batch_semaphore:
            await self._process_batch(
                batch_blocks, batch_texts, batch_file_infos, workspace_path
            )
            
    async def _process_batch(self, batch_blocks: List[CodeBlock],
                           batch_texts: List[str],
                           batch_file_infos: List[Dict[str, Any]],
                           workspace_path: str,
                           on_error: Optional[Callable[[Exception], None]] = None,
                           on_blocks_indexed: Optional[Callable[[int], None]] = None) -> None:
        """处理代码块批次的嵌入和存储"""
        if not batch_blocks:
            return
            
        retry_count = 0
        last_error = None
        
        while retry_count < MAX_BATCH_RETRIES:
            try:
                # 生成嵌入
                embedding_response = await self.embedder.create_embeddings(batch_texts)
                embeddings = embedding_response.embeddings
                
                if len(embeddings) != len(batch_blocks):
                    raise ValueError(f"嵌入数量 ({len(embeddings)}) 与代码块数量 ({len(batch_blocks)}) 不匹配")
                    
                # 准备向量点
                points = []
                for i, (block, embedding) in enumerate(zip(batch_blocks, embeddings)):
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
                            'workspace_path': workspace_path
                        }
                    )
                    points.append(point)
                    
                # 存储到向量数据库
                await self.vector_store.upsert_points(points)
                
                # 更新缓存
                for file_info in batch_file_infos:
                    await self.cache_manager.update_hash(
                        file_info['filePath'], file_info['fileHash']
                    )
                    
                # 调用回调
                if on_blocks_indexed:
                    on_blocks_indexed(len(batch_blocks))
                    
                logger.debug(f"成功处理批次: {len(batch_blocks)} 个代码块")
                return
                
            except Exception as error:
                retry_count += 1
                last_error = error
                
                if retry_count < MAX_BATCH_RETRIES:
                    delay = INITIAL_RETRY_DELAY_MS * (2 ** (retry_count - 1)) / 1000
                    logger.warning(f"批处理失败 (尝试 {retry_count}/{MAX_BATCH_RETRIES}), {delay}s 后重试: {error}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"批处理最终失败: {error}")
                    if on_error:
                        on_error(error)
                        
    def _generate_point_id(self, block: CodeBlock) -> str:
        """为代码块生成唯一ID"""
        # 使用文件路径、起始行和段哈希生成唯一ID
        id_string = f"{block.file_path}:{block.start_line}:{block.segment_hash}"
        return hashlib.sha256(id_string.encode('utf-8')).hexdigest()[:16]
        
    async def get_scan_statistics(self) -> Dict[str, Any]:
        """获取扫描统计信息"""
        return {
            'active_batch_tasks': len(self.active_batch_tasks),
            'current_batch_size': len(self.current_batch_blocks),
            'batch_threshold': BATCH_SEGMENT_THRESHOLD,
            'parse_concurrency': PARSING_CONCURRENCY,
            'batch_concurrency': BATCH_PROCESSING_CONCURRENCY
        }