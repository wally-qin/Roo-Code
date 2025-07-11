"""
配置管理器实现

简化的配置管理器，基于字典配置而非VSCode的配置系统。
"""

from typing import Dict, Optional, Any
from ..interfaces import EmbedderProvider, CodeIndexConfig, ConfigSnapshot
from ..constants import DEFAULT_CONFIG, EMBEDDING_MODELS


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
        
        if provider == "openai":
            return bool(self.config.get("openai_api_key") and self.config.get("qdrant_url"))
        elif provider == "ollama":
            return bool(self.config.get("ollama_base_url") and self.config.get("qdrant_url"))
        
        return False
        
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