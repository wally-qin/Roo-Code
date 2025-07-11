"""
代码索引协调器

负责协调和编排整个代码索引过程，包括文件扫描、解析、嵌入和存储。
基于原TypeScript项目的相应功能重新实现。
"""

import asyncio
import os
from typing import Optional, Dict, Any, List
import logging

from .interfaces import (
    IndexingState, IVectorStore, IDirectoryScanner, 
    IFileWatcher, FileProcessingResult, BatchProcessingSummary
)
from .managers.config_manager import CodeIndexConfigManager
from .managers.state_manager import CodeIndexStateManager
from .managers.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class CodeIndexOrchestrator:
    """代码索引协调器"""
    
    def __init__(self, config_manager: CodeIndexConfigManager,
                 state_manager: CodeIndexStateManager,
                 workspace_path: str,
                 cache_manager: CacheManager,
                 vector_store: IVectorStore,
                 scanner: Optional[IDirectoryScanner] = None,
                 file_watcher: Optional[IFileWatcher] = None):
        """
        初始化协调器
        
        Args:
            config_manager: 配置管理器
            state_manager: 状态管理器
            workspace_path: 工作空间路径
            cache_manager: 缓存管理器
            vector_store: 向量存储
            scanner: 目录扫描器
            file_watcher: 文件监听器
        """
        self.config_manager = config_manager
        self.state_manager = state_manager
        self.workspace_path = workspace_path
        self.cache_manager = cache_manager
        self.vector_store = vector_store
        self.scanner = scanner
        self.file_watcher = file_watcher
        
        self._indexing_task: Optional[asyncio.Task] = None
        self._stop_requested = False
        
    @property
    def state(self) -> IndexingState:
        """获取当前索引状态"""
        return self.state_manager.current_state
        
    async def start_indexing(self) -> None:
        """开始索引过程"""
        if self.state == IndexingState.INDEXING:
            logger.info("索引已在进行中")
            return
            
        try:
            self.state_manager.set_system_state(IndexingState.INDEXING, "开始索引")
            
            # 1. 初始化向量存储
            await self._initialize_vector_store()
            
            # 2. 执行初始扫描
            await self._perform_initial_scan()
            
            # 3. 启动文件监听（如果可用）
            if self.file_watcher:
                await self._start_file_watcher()
                
            self.state_manager.set_system_state(IndexingState.INDEXED, "索引完成")
            
        except Exception as e:
            logger.error(f"索引过程失败: {e}")
            self.state_manager.set_system_state(IndexingState.ERROR, str(e))
            raise
            
    async def stop_watcher(self) -> None:
        """停止文件监听器"""
        if self.file_watcher:
            try:
                self.file_watcher.stop_watching()
                logger.info("文件监听器已停止")
            except Exception as e:
                logger.error(f"停止文件监听器失败: {e}")
                
        if self._indexing_task and not self._indexing_task.done():
            self._stop_requested = True
            try:
                await asyncio.wait_for(self._indexing_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._indexing_task.cancel()
                
    async def clear_index_data(self) -> None:
        """清空索引数据"""
        try:
            # 停止监听器
            await self.stop_watcher()
            
            # 清空向量存储
            await self.vector_store.clear_collection()
            
            # 重置状态
            self.state_manager.set_system_state(IndexingState.STANDBY, "索引数据已清空")
            
            logger.info("索引数据已清空")
            
        except Exception as e:
            logger.error(f"清空索引数据失败: {e}")
            self.state_manager.set_system_state(IndexingState.ERROR, str(e))
            raise
            
    async def _initialize_vector_store(self) -> None:
        """初始化向量存储"""
        try:
            created = await self.vector_store.initialize()
            if created:
                logger.info("创建了新的向量存储集合")
            else:
                logger.info("使用现有的向量存储集合")
        except Exception as e:
            logger.error(f"初始化向量存储失败: {e}")
            raise
            
    async def _perform_initial_scan(self) -> None:
        """执行初始目录扫描"""
        if not self.scanner:
            logger.warning("目录扫描器不可用，跳过初始扫描")
            return
            
        try:
            logger.info("开始目录扫描")
            
            # 设置进度回调
            def on_blocks_indexed(count: int):
                self.state_manager.update_progress(
                    f"已索引 {count} 个代码块"
                )
                
            def on_file_parsed(count: int):
                self.state_manager.update_progress(
                    f"已解析 {count} 个文件"
                )
                
            def on_error(error: Exception):
                logger.error(f"扫描过程中出现错误: {error}")
                
            # 执行扫描
            scan_result = await self.scanner.scan_directory(
                directory=self.workspace_path,
                on_error=on_error,
                on_blocks_indexed=on_blocks_indexed,
                on_file_parsed=on_file_parsed
            )
            
            logger.info(f"目录扫描完成: {scan_result}")
            
        except Exception as e:
            logger.error(f"目录扫描失败: {e}")
            raise
            
    async def _start_file_watcher(self) -> None:
        """启动文件监听器"""
        try:
            # 初始化文件监听器
            await self.file_watcher.initialize()
            
            # 设置事件处理器
            self._setup_file_watcher_events()
            
            # 启动监听
            self.file_watcher.start_watching()
            
            logger.info("文件监听器已启动")
            
        except Exception as e:
            logger.error(f"启动文件监听器失败: {e}")
            raise
            
    def _setup_file_watcher_events(self) -> None:
        """设置文件监听器事件处理"""
        if not self.file_watcher:
            return
            
        # 批处理开始事件
        async def on_batch_start():
            self.state_manager.update_progress("开始批处理文件变更")
            
        # 批处理进度事件
        async def on_batch_progress():
            self.state_manager.update_progress("处理文件变更中...")
            
        # 批处理完成事件
        async def on_batch_complete():
            self.state_manager.update_progress("文件变更处理完成")
            
        # 设置事件监听（这里需要根据实际的文件监听器实现来调整）
        # 由于接口中定义的是属性而不是方法，这里需要创建监听任务
        asyncio.create_task(self._monitor_file_watcher_events())
        
    async def _monitor_file_watcher_events(self) -> None:
        """监控文件监听器事件"""
        if not self.file_watcher:
            return
            
        try:
            while not self._stop_requested:
                # 监听批处理开始事件
                await self.file_watcher.on_batch_start.wait()
                self.state_manager.update_progress("开始批处理文件变更")
                
                # 监听批处理进度事件
                progress_task = asyncio.create_task(
                    self._monitor_batch_progress()
                )
                
                # 监听批处理完成事件
                await self.file_watcher.on_batch_complete.wait()
                progress_task.cancel()
                self.state_manager.update_progress("文件变更处理完成")
                
        except asyncio.CancelledError:
            logger.info("文件监听器事件监控已停止")
        except Exception as e:
            logger.error(f"文件监听器事件监控错误: {e}")
            
    async def _monitor_batch_progress(self) -> None:
        """监控批处理进度"""
        try:
            while True:
                await self.file_watcher.on_batch_progress.wait()
                self.state_manager.update_progress("处理文件变更中...")
                await asyncio.sleep(0.1)  # 防止过于频繁的更新
        except asyncio.CancelledError:
            pass
            
    async def process_file_changes(self, file_paths: List[str]) -> BatchProcessingSummary:
        """
        处理文件变更
        
        Args:
            file_paths: 变更的文件路径列表
            
        Returns:
            批处理摘要
        """
        processed_files = []
        batch_error = None
        
        try:
            if not self.file_watcher:
                raise Exception("文件监听器不可用")
                
            # 处理每个文件
            for file_path in file_paths:
                try:
                    result = await self.file_watcher.process_file(file_path)
                    processed_files.append(result)
                except Exception as e:
                    error_result = FileProcessingResult(
                        path=file_path,
                        status="error",
                        error=e,
                        reason=str(e)
                    )
                    processed_files.append(error_result)
                    
        except Exception as e:
            batch_error = e
            logger.error(f"批处理失败: {e}")
            
        return BatchProcessingSummary(
            processed_files=processed_files,
            batch_error=batch_error
        )
        
    async def get_indexing_statistics(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            # 检查集合是否存在
            collection_exists = await self.vector_store.collection_exists()
            
            if not collection_exists:
                return {
                    "collection_exists": False,
                    "total_vectors": 0,
                    "workspace_path": self.workspace_path,
                    "state": self.state.value
                }
                
            # 这里可以添加更多统计信息的获取逻辑
            # 例如向量数量、文件数量等（需要向量存储支持）
            
            return {
                "collection_exists": True,
                "workspace_path": self.workspace_path,
                "state": self.state.value,
                "vector_store_type": type(self.vector_store).__name__
            }
            
        except Exception as e:
            logger.error(f"获取索引统计信息失败: {e}")
            return {
                "error": str(e),
                "workspace_path": self.workspace_path,
                "state": self.state.value
            }