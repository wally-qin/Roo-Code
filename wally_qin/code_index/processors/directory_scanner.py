"""
目录扫描器

负责扫描工作空间目录，识别代码文件并进行解析和索引。
基于原TypeScript项目的DirectoryScanner重新实现。
"""

import asyncio
import os
import hashlib
from typing import Optional, Dict, Any, List, Callable, Set
import logging
from pathspec import PathSpec

from ..interfaces import IDirectoryScanner, ICodeParser, IEmbedder, IVectorStore, PointStruct
from ..constants import (
    SUPPORTED_EXTENSIONS, BATCH_SIZE, MAX_FILE_SIZE_BYTES,
    MAX_CONCURRENT_FILES, MAX_CHUNK_SIZE, MIN_CHUNK_SIZE
)

logger = logging.getLogger(__name__)


class DirectoryScanner(IDirectoryScanner):
    """目录扫描器实现"""
    
    def __init__(self, parser: ICodeParser, embedder: IEmbedder, 
                 vector_store: IVectorStore, cache_manager):
        """
        初始化目录扫描器
        
        Args:
            parser: 代码解析器
            embedder: 嵌入器
            vector_store: 向量存储
            cache_manager: 缓存管理器
        """
        self.parser = parser
        self.embedder = embedder
        self.vector_store = vector_store
        self.cache_manager = cache_manager
        
        # 统计信息
        self.stats = {
            "files_processed": 0,
            "blocks_indexed": 0,
            "files_skipped": 0,
            "errors": 0
        }
        
    async def scan_directory(self, directory: str, 
                           on_error: Optional[Callable[[Exception], None]] = None,
                           on_blocks_indexed: Optional[Callable[[int], None]] = None,
                           on_file_parsed: Optional[Callable[[int], None]] = None) -> Dict[str, Any]:
        """
        扫描目录
        
        Args:
            directory: 要扫描的目录路径
            on_error: 错误回调函数
            on_blocks_indexed: 代码块索引回调函数
            on_file_parsed: 文件解析回调函数
            
        Returns:
            扫描结果统计
        """
        try:
            logger.info(f"开始扫描目录: {directory}")
            
            # 重置统计信息
            self.stats = {
                "files_processed": 0,
                "blocks_indexed": 0,
                "files_skipped": 0,
                "errors": 0
            }
            
            # 1. 收集需要处理的文件
            files_to_process = await self._collect_files(directory)
            logger.info(f"找到 {len(files_to_process)} 个代码文件")
            
            # 2. 批量处理文件
            await self._process_files_in_batches(
                files_to_process,
                on_error,
                on_blocks_indexed,
                on_file_parsed
            )
            
            result = {
                "directory": directory,
                "files_found": len(files_to_process),
                "files_processed": self.stats["files_processed"],
                "blocks_indexed": self.stats["blocks_indexed"],
                "files_skipped": self.stats["files_skipped"],
                "errors": self.stats["errors"]
            }
            
            logger.info(f"目录扫描完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"目录扫描失败: {e}")
            if on_error:
                on_error(e)
            raise
            
    async def _collect_files(self, directory: str) -> List[str]:
        """收集需要处理的文件"""
        files = []
        
        # 加载.gitignore规则
        gitignore_spec = self._load_gitignore(directory)
        
        for root, dirs, filenames in os.walk(directory):
            # 过滤目录
            dirs[:] = [d for d in dirs if not self._should_ignore_directory(d, gitignore_spec)]
            
            for filename in filenames:
                file_path = os.path.join(root, filename)
                
                # 检查文件是否应该被处理
                if self._should_process_file(file_path, gitignore_spec):
                    files.append(file_path)
                    
        return files
        
    def _load_gitignore(self, directory: str) -> Optional[PathSpec]:
        """加载.gitignore规则"""
        try:
            gitignore_path = os.path.join(directory, '.gitignore')
            if os.path.exists(gitignore_path):
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    return PathSpec.from_lines('gitwildmatch', f)
        except Exception as e:
            logger.warning(f"加载.gitignore失败: {e}")
        return None
        
    def _should_ignore_directory(self, dirname: str, gitignore_spec: Optional[PathSpec]) -> bool:
        """检查目录是否应该忽略"""
        # 默认忽略的目录
        ignored_dirs = {
            '.git', '.svn', '.hg', '__pycache__', '.pytest_cache',
            'node_modules', '.vscode', '.idea', 'dist', 'build',
            '.next', '.nuxt', 'coverage', '.nyc_output'
        }
        
        if dirname in ignored_dirs:
            return True
            
        # 检查gitignore规则
        if gitignore_spec and gitignore_spec.match_file(dirname):
            return True
            
        return False
        
    def _should_process_file(self, file_path: str, gitignore_spec: Optional[PathSpec]) -> bool:
        """检查文件是否应该处理"""
        # 检查文件扩展名
        if not self._has_supported_extension(file_path):
            return False
            
        # 检查文件大小
        try:
            if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
                return False
        except OSError:
            return False
            
        # 检查gitignore规则
        if gitignore_spec:
            relative_path = os.path.relpath(file_path)
            if gitignore_spec.match_file(relative_path):
                return False
                
        return True
        
    def _has_supported_extension(self, file_path: str) -> bool:
        """检查文件是否有支持的扩展名"""
        _, ext = os.path.splitext(file_path.lower())
        return ext in SUPPORTED_EXTENSIONS
        
    async def _process_files_in_batches(self, files: List[str],
                                      on_error: Optional[Callable[[Exception], None]],
                                      on_blocks_indexed: Optional[Callable[[int], None]],
                                      on_file_parsed: Optional[Callable[[int], None]]):
        """批量处理文件"""
        
        for i in range(0, len(files), MAX_CONCURRENT_FILES):
            batch = files[i:i + MAX_CONCURRENT_FILES]
            
            # 并发处理批次中的文件
            tasks = [
                self._process_single_file(file_path, on_error)
                for file_path in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理批次结果
            batch_points = []
            for result in batch_results:
                if isinstance(result, Exception):
                    self.stats["errors"] += 1
                    if on_error:
                        on_error(result)
                elif result:
                    batch_points.extend(result)
                    self.stats["files_processed"] += 1
                    if on_file_parsed:
                        on_file_parsed(self.stats["files_processed"])
                else:
                    self.stats["files_skipped"] += 1
                    
            # 批量插入向量点
            if batch_points:
                await self._insert_points_batch(batch_points)
                self.stats["blocks_indexed"] += len(batch_points)
                if on_blocks_indexed:
                    on_blocks_indexed(self.stats["blocks_indexed"])
                    
    async def _process_single_file(self, file_path: str, 
                                 on_error: Optional[Callable[[Exception], None]]) -> Optional[List[PointStruct]]:
        """处理单个文件"""
        try:
            # 检查缓存
            file_hash = await self._calculate_file_hash(file_path)
            if await self.cache_manager.is_file_cached(file_path, file_hash):
                logger.debug(f"文件已缓存，跳过: {file_path}")
                return None
                
            # 解析文件
            code_blocks = await self.parser.parse_file(file_path, file_hash=file_hash)
            if not code_blocks:
                return None
                
            # 过滤和处理代码块
            valid_blocks = [
                block for block in code_blocks
                if MIN_CHUNK_SIZE <= len(block.content) <= MAX_CHUNK_SIZE
            ]
            
            if not valid_blocks:
                return None
                
            # 生成嵌入向量
            points = await self._create_embedding_points(valid_blocks)
            
            # 更新缓存
            await self.cache_manager.cache_file(file_path, file_hash)
            
            return points
            
        except Exception as e:
            logger.error(f"处理文件失败 {file_path}: {e}")
            if on_error:
                on_error(e)
            return None
            
    async def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        try:
            hash_obj = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
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
        
    async def _insert_points_batch(self, points: List[PointStruct]):
        """批量插入向量点"""
        if not points:
            return
            
        # 分批插入以避免内存问题
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i:i + BATCH_SIZE]
            await self.vector_store.upsert_points(batch)
            
    async def get_scan_statistics(self) -> Dict[str, Any]:
        """获取扫描统计信息"""
        return self.stats.copy()