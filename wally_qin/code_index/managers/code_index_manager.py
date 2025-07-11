"""
代码索引管理器

基于原TypeScript项目的CodeIndexManager类重新实现，
作为整个代码索引系统的主要入口点，管理所有组件的生命周期。
"""

import asyncio
import os
from typing import Dict, Optional, List
import logging

from ..interfaces import VectorStoreSearchResult, IndexingState
from .config_manager import CodeIndexConfigManager
from .state_manager import CodeIndexStateManager
from .cache_manager import CacheManager
from ..service_factory import CodeIndexServiceFactory
from ..orchestrator import CodeIndexOrchestrator
from ..search_service import CodeIndexSearchService

logger = logging.getLogger(__name__)


class CodeIndexManager:
    """代码索引管理器 - 单例模式"""
    
    _instances: Dict[str, 'CodeIndexManager'] = {}
    
    def __init__(self, workspace_path: str):
        """
        私有构造函数，用于单例模式
        
        Args:
            workspace_path: 工作空间路径
        """
        self.workspace_path = workspace_path
        
        # 专业化类实例
        self._config_manager: Optional[CodeIndexConfigManager] = None
        self._state_manager = CodeIndexStateManager()
        self._service_factory: Optional[CodeIndexServiceFactory] = None
        self._orchestrator: Optional[CodeIndexOrchestrator] = None
        self._search_service: Optional[CodeIndexSearchService] = None
        self._cache_manager: Optional[CacheManager] = None
        
    @classmethod
    def get_instance(cls, workspace_path: Optional[str] = None) -> Optional['CodeIndexManager']:
        """
        获取代码索引管理器单例实例
        
        Args:
            workspace_path: 工作空间路径
            
        Returns:
            代码索引管理器实例或None
        """
        if workspace_path is None:
            workspace_path = os.getcwd()
            
        if not os.path.exists(workspace_path):
            logger.warning(f"工作空间路径不存在: {workspace_path}")
            return None
            
        # 规范化路径
        workspace_path = os.path.abspath(workspace_path)
        
        if workspace_path not in cls._instances:
            cls._instances[workspace_path] = cls(workspace_path)
            
        return cls._instances[workspace_path]
        
    @classmethod
    def dispose_all(cls) -> None:
        """释放所有实例"""
        for instance in cls._instances.values():
            instance.dispose()
        cls._instances.clear()
        
    def _assert_initialized(self) -> None:
        """断言管理器已初始化"""
        if (not self._config_manager or not self._orchestrator or 
            not self._search_service or not self._cache_manager):
            raise RuntimeError("CodeIndexManager未初始化，请先调用initialize()")
            
    @property
    def state(self) -> IndexingState:
        """获取当前索引状态"""
        if not self.is_feature_enabled:
            return IndexingState.STANDBY
        self._assert_initialized()
        return self._orchestrator.state
        
    @property
    def is_feature_enabled(self) -> bool:
        """检查功能是否启用"""
        return self._config_manager.is_feature_enabled if self._config_manager else False
        
    @property
    def is_feature_configured(self) -> bool:
        """检查功能是否已配置"""
        return self._config_manager.is_feature_configured if self._config_manager else False
        
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        try:
            self._assert_initialized()
            return True
        except RuntimeError:
            return False
            
    @property
    def on_progress_update(self) -> asyncio.Event:
        """进度更新事件"""
        return self._state_manager.on_progress_update
        
    async def initialize(self, config: Optional[Dict] = None) -> Dict[str, bool]:
        """
        初始化管理器
        
        Args:
            config: 可选的配置字典
            
        Returns:
            包含是否需要重启信息的字典
        """
        # 1. 配置管理器初始化
        if not self._config_manager:
            self._config_manager = CodeIndexConfigManager(config)
            
        # 加载配置
        config_result = await self._config_manager.load_configuration()
        requires_restart = config_result.get("requires_restart", False)
        
        # 2. 检查功能是否启用
        if not self.is_feature_enabled:
            if self._orchestrator:
                await self._orchestrator.stop_watcher()
            return {"requires_restart": requires_restart}
            
        # 3. 检查工作空间是否可用
        if not os.path.exists(self.workspace_path):
            self._state_manager.set_system_state(IndexingState.STANDBY, "工作空间不可用")
            return {"requires_restart": requires_restart}
            
        # 4. 缓存管理器初始化
        if not self._cache_manager:
            self._cache_manager = CacheManager(self.workspace_path)
            await self._cache_manager.initialize()
            
        # 5. 确定是否需要重新创建核心服务
        needs_service_recreation = not self._service_factory or requires_restart
        
        if needs_service_recreation:
            await self._recreate_services()
            
        # 6. 处理索引启动/重启
        should_start_or_restart_indexing = (
            requires_restart or
            (needs_service_recreation and 
             (not self._orchestrator or self._orchestrator.state != IndexingState.INDEXING))
        )
        
        if should_start_or_restart_indexing:
            # 异步启动索引，不等待完成
            asyncio.create_task(self._orchestrator.start_indexing())
            
        return {"requires_restart": requires_restart}
        
    async def start_indexing(self) -> None:
        """启动索引过程"""
        if not self.is_feature_enabled:
            return
        self._assert_initialized()
        await self._orchestrator.start_indexing()
        
    async def stop_watcher(self) -> None:
        """停止文件监听器"""
        if not self.is_feature_enabled:
            return
        if self._orchestrator:
            await self._orchestrator.stop_watcher()
            
    def dispose(self) -> None:
        """释放管理器实例"""
        if self._orchestrator:
            asyncio.create_task(self.stop_watcher())
        self._state_manager.dispose()
        
    async def clear_index_data(self) -> None:
        """清空所有索引数据"""
        if not self.is_feature_enabled:
            return
        self._assert_initialized()
        await self._orchestrator.clear_index_data()
        await self._cache_manager.clear_cache_file()
        
    def get_current_status(self) -> Dict:
        """获取当前状态"""
        return self._state_manager.get_current_status()
        
    async def search_index(self, query: str, directory_prefix: Optional[str] = None) -> List[VectorStoreSearchResult]:
        """
        搜索索引
        
        Args:
            query: 搜索查询
            directory_prefix: 可选的目录前缀过滤
            
        Returns:
            搜索结果列表
        """
        if not self.is_feature_enabled:
            return []
        self._assert_initialized()
        return await self._search_service.search_index(query, directory_prefix)
        
    async def _recreate_services(self) -> None:
        """重新创建服务"""
        # 停止监听器
        if self._orchestrator:
            await self.stop_watcher()
            
        # 清空现有服务
        self._orchestrator = None
        self._search_service = None
        
        # 重新初始化服务工厂
        self._service_factory = CodeIndexServiceFactory(
            self._config_manager,
            self.workspace_path,
            self._cache_manager
        )
        
        try:
            # 创建服务
            services = await self._service_factory.create_services()
            embedder = services["embedder"]
            vector_store = services["vector_store"]
            scanner = services["scanner"]
            file_watcher = services["file_watcher"]
            
            # 验证嵌入器配置
            validation_result = await self._service_factory.validate_embedder(embedder)
            if not validation_result["valid"]:
                error_message = validation_result.get("error", "嵌入器配置验证失败")
                self._state_manager.set_system_state(IndexingState.ERROR, error_message)
                raise Exception(error_message)
                
            # 重新初始化协调器
            self._orchestrator = CodeIndexOrchestrator(
                self._config_manager,
                self._state_manager,
                self.workspace_path,
                self._cache_manager,
                vector_store,
                scanner,
                file_watcher
            )
            
            # 重新初始化搜索服务
            self._search_service = CodeIndexSearchService(
                self._config_manager,
                self._state_manager,
                embedder,
                vector_store
            )
            
            # 清除错误状态
            self._state_manager.set_system_state(IndexingState.STANDBY, "")
            
        except Exception as e:
            logger.error(f"重新创建服务失败: {e}")
            raise
            
    async def handle_settings_change(self) -> None:
        """处理设置变更"""
        if self._config_manager:
            config_result = await self._config_manager.load_configuration()
            requires_restart = config_result.get("requires_restart", False)
            
            is_feature_enabled = self.is_feature_enabled
            is_feature_configured = self.is_feature_configured
            
            if requires_restart and is_feature_enabled and is_feature_configured:
                try:
                    await self._recreate_services()
                except Exception as e:
                    logger.error(f"重新创建服务失败: {e}")
                    raise