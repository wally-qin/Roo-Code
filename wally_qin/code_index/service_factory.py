"""
服务工厂

根据配置创建不同的服务实例，支持多种嵌入器和向量存储。
"""

from typing import Dict, Any, Optional
import logging

from .interfaces import IEmbedder, IVectorStore, ICodeParser
from .managers.config_manager import CodeIndexConfigManager
from .managers.cache_manager import CacheManager
from .embedders import OpenAIEmbedder, OllamaEmbedder
from .vector_store import QdrantVectorStore, MilvusVectorStore
from .processors import CodeParser
from .constants import EMBEDDING_MODELS

logger = logging.getLogger(__name__)


class CodeIndexServiceFactory:
    """代码索引服务工厂"""
    
    def __init__(self, config_manager: CodeIndexConfigManager, 
                 workspace_path: str, cache_manager: CacheManager):
        """
        初始化服务工厂
        
        Args:
            config_manager: 配置管理器
            workspace_path: 工作空间路径
            cache_manager: 缓存管理器
        """
        self.config_manager = config_manager
        self.workspace_path = workspace_path
        self.cache_manager = cache_manager
        
    async def create_services(self) -> Dict[str, Any]:
        """
        创建所有服务实例
        
        Returns:
            包含所有服务实例的字典
        """
        config = self.config_manager.get_config()
        
        # 创建嵌入器
        embedder = self._create_embedder(config)
        
        # 创建向量存储
        vector_store = self._create_vector_store(config, embedder)
        
        # 创建代码解析器
        parser = self._create_code_parser()
        
        # 创建目录扫描器 (简化版本)
        scanner = None  # 这里可以根据需要实现完整的扫描器
        
        # 创建文件监听器 (简化版本)
        file_watcher = None  # 这里可以根据需要实现完整的文件监听器
        
        return {
            "embedder": embedder,
            "vector_store": vector_store,
            "parser": parser,
            "scanner": scanner,
            "file_watcher": file_watcher
        }
        
    def _create_embedder(self, config) -> IEmbedder:
        """创建嵌入器实例"""
        provider = config.embedder_provider.value
        
        if provider == "openai":
            if not config.openai_api_key:
                raise ValueError("OpenAI API密钥未配置")
            return OpenAIEmbedder(
                api_key=config.openai_api_key,
                model_id=config.model_id
            )
        elif provider == "ollama":
            if not config.ollama_base_url:
                raise ValueError("Ollama基础URL未配置")
            return OllamaEmbedder(
                base_url=config.ollama_base_url,
                model_id=config.model_id
            )
        else:
            raise ValueError(f"不支持的嵌入器类型: {provider}")
            
    def _create_vector_store(self, config, embedder: IEmbedder) -> IVectorStore:
        """创建向量存储实例"""
        vector_store_type = self.config_manager.vector_store_type
        
        # 获取向量维度
        vector_size = self._get_vector_size(config, embedder)
        
        if vector_store_type == "qdrant":
            if not config.qdrant_url:
                raise ValueError("Qdrant URL未配置")
            return QdrantVectorStore(
                workspace_path=self.workspace_path,
                url=config.qdrant_url,
                vector_size=vector_size,
                api_key=config.qdrant_api_key
            )
        elif vector_store_type == "milvus":
            milvus_config = self.config_manager.milvus_config
            return MilvusVectorStore(
                workspace_path=self.workspace_path,
                host=milvus_config["host"],
                port=milvus_config["port"],
                vector_size=vector_size,
                user=milvus_config["user"],
                password=milvus_config["password"]
            )
        else:
            raise ValueError(f"不支持的向量存储类型: {vector_store_type}")
            
    def _create_code_parser(self) -> ICodeParser:
        """创建代码解析器实例"""
        return CodeParser()
        
    def _get_vector_size(self, config, embedder: IEmbedder) -> int:
        """获取向量维度"""
        # 如果配置中指定了维度，使用配置的维度
        if config.model_dimension:
            return config.model_dimension
            
        # 否则从嵌入器信息获取
        if hasattr(embedder, 'get_model_dimension'):
            return embedder.get_model_dimension()
            
        # 从模型配置获取默认维度
        provider = config.embedder_provider.value
        model_id = config.model_id
        
        if provider in EMBEDDING_MODELS:
            models = EMBEDDING_MODELS[provider]
            if model_id and model_id in models:
                return models[model_id]["dimension"]
            else:
                # 使用该提供商的第一个模型的维度
                first_model = list(models.values())[0]
                return first_model["dimension"]
        
        # 默认维度
        return 1536
        
    async def validate_embedder(self, embedder: IEmbedder) -> Dict[str, Any]:
        """验证嵌入器配置"""
        try:
            return await embedder.validate_configuration()
        except Exception as e:
            logger.error(f"嵌入器验证失败: {e}")
            return {
                "valid": False,
                "error": str(e)
            }