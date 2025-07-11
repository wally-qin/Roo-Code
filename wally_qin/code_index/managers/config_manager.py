"""
配置管理器实现

简化的配置管理器，基于字典配置而非VSCode的配置系统。
支持多种向量数据库后端选择。
"""

from typing import Dict, Optional, Any
from ..interfaces import EmbedderProvider, CodeIndexConfig, ConfigSnapshot
from ..constants import DEFAULT_CONFIG, EMBEDDING_MODELS, VECTOR_STORE_OPTIONS


class CodeIndexConfigManager:
    """代码索引配置管理器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化配置管理器
        
        Args:
            config: 配置字典
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
    @property
    def is_feature_enabled(self) -> bool:
        """功能是否启用"""
        return self.config.get("enabled", True)
        
    @property
    def is_feature_configured(self) -> bool:
        """功能是否已配置"""
        provider = self.config.get("embedder_provider", "openai")
        vector_store = self.config.get("vector_store", "qdrant")
        
        # 检查嵌入器配置
        embedder_configured = False
        if provider == "openai":
            embedder_configured = bool(self.config.get("openai_api_key"))
        elif provider == "ollama":
            embedder_configured = bool(self.config.get("ollama_base_url"))
        
        # 检查向量存储配置
        vector_store_configured = False
        if vector_store == "qdrant":
            vector_store_configured = bool(self.config.get("qdrant_url"))
        elif vector_store == "milvus":
            vector_store_configured = bool(
                self.config.get("milvus_host") and 
                self.config.get("milvus_port")
            )
        
        return embedder_configured and vector_store_configured
        
    async def load_configuration(self) -> Dict[str, Any]:
        """加载配置"""
        return {
            "requires_restart": False,
            "config": self.get_config()
        }
        
    def get_config(self) -> CodeIndexConfig:
        """获取当前配置"""
        provider_str = self.config.get("embedder_provider", "openai")
        provider = EmbedderProvider(provider_str)
        
        return CodeIndexConfig(
            is_configured=self.is_feature_configured,
            embedder_provider=provider,
            model_id=self.config.get("model_id"),
            openai_api_key=self.config.get("openai_api_key"),
            ollama_base_url=self.config.get("ollama_base_url"),
            qdrant_url=self.config.get("qdrant_url"),
            qdrant_api_key=self.config.get("qdrant_api_key"),
            search_min_score=self.config.get("search_min_score"),
            search_max_results=self.config.get("search_max_results")
        )
        
    @property
    def vector_store_type(self) -> str:
        """获取向量存储类型"""
        return self.config.get("vector_store", "qdrant")
        
    @property 
    def milvus_config(self) -> Dict[str, Any]:
        """获取Milvus配置"""
        return {
            "host": self.config.get("milvus_host", "localhost"),
            "port": self.config.get("milvus_port", "19530"),
            "user": self.config.get("milvus_user"),
            "password": self.config.get("milvus_password"),
        }