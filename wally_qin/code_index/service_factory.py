"""
服务工厂

根据配置创建不同的服务实例，支持多种嵌入器和向量存储。
"""

from typing import Dict, Any, Optional
import logging

from .interfaces import IEmbedder, IVectorStore, ICodeParser
from .managers.config_manager import CodeIndexConfigManager
from .managers.cache_manager import CacheManager
from .embedders import OpenAIEmbedder, OllamaEmbedder, GeminiEmbedder, OpenAICompatibleEmbedder
from .vector_store import QdrantVectorStore, MilvusVectorStore, ChromaVectorStore
from .processors import CodeParser, DirectoryScanner, FileWatcher
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
        code_parser = self._create_code_parser()
        
        # 创建目录扫描器
        directory_scanner = self._create_directory_scanner(code_parser, embedder, vector_store)
        
        # 创建文件监听器
        file_watcher = self._create_file_watcher(code_parser, embedder, vector_store)
        
        return {
            'embedder': embedder,
            'vector_store': vector_store,
            'code_parser': code_parser,
            'directory_scanner': directory_scanner,
            'file_watcher': file_watcher
        }
        
    def _create_embedder(self, config) -> IEmbedder:
        """创建嵌入器实例"""
        provider = config.embedder_provider.value
        
        if provider == "openai":
            api_key = config.openai_api_key
            if not api_key:
                raise ValueError("OpenAI API密钥未配置")
            
            model_id = config.model_id or "text-embedding-3-small"
            return OpenAIEmbedder(api_key=api_key, model_id=model_id)
            
        elif provider == "ollama":
            base_url = config.ollama_base_url
            if not base_url:
                raise ValueError("Ollama基础URL未配置")
            
            model_id = config.model_id or "nomic-embed-text"
            return OllamaEmbedder(base_url=base_url, model_id=model_id)
            
        elif provider == "gemini":
            api_key = config.gemini_api_key
            if not api_key:
                raise ValueError("Gemini API密钥未配置")
            
            return GeminiEmbedder(api_key=api_key)
            
        elif provider == "openai-compatible":
            base_url = config.openai_compatible_base_url
            api_key = config.openai_compatible_api_key
            
            if not base_url or not api_key:
                raise ValueError("OpenAI兼容API配置不完整")
            
            model_id = config.model_id or "text-embedding-3-small"
            return OpenAICompatibleEmbedder(
                base_url=base_url,
                api_key=api_key,
                model_id=model_id
            )
            
        else:
            raise ValueError(f"不支持的嵌入器提供商: {provider}")
            
    def _create_vector_store(self, config, embedder: IEmbedder) -> IVectorStore:
        """创建向量存储实例"""
        vector_store_type = getattr(config, 'vector_store', 'qdrant')
        vector_size = self._get_vector_size(config, embedder)
        
        if vector_store_type == "qdrant":
            url = config.qdrant_url or "http://localhost:6333"
            api_key = config.qdrant_api_key
            
            return QdrantVectorStore(
                url=url,
                api_key=api_key,
                collection_name="code_blocks",
                vector_size=vector_size
            )
            
        elif vector_store_type == "milvus":
            host = getattr(config, 'milvus_host', 'localhost')
            port = getattr(config, 'milvus_port', 19530)
            user = getattr(config, 'milvus_user', None)
            password = getattr(config, 'milvus_password', None)
            
            return MilvusVectorStore(
                host=host,
                port=port,
                user=user,
                password=password,
                collection_name="code_blocks",
                vector_size=vector_size
            )
            
        elif vector_store_type == "chroma":
            host = getattr(config, 'chroma_host', 'localhost')
            port = getattr(config, 'chroma_port', 8000)
            persist_directory = getattr(config, 'chroma_persist_directory', None)
            
            return ChromaVectorStore(
                host=host,
                port=port,
                persist_directory=persist_directory,
                collection_name="code_blocks"
            )
            
        else:
            raise ValueError(f"不支持的向量存储类型: {vector_store_type}")
            
    def _create_code_parser(self) -> ICodeParser:
        """创建代码解析器"""
        return CodeParser()
        
    def _create_directory_scanner(self, parser: ICodeParser, embedder: IEmbedder, vector_store: IVectorStore) -> DirectoryScanner:
        """创建目录扫描器"""
        return DirectoryScanner(
            embedder=embedder,
            vector_store=vector_store,
            code_parser=parser,
            cache_manager=self.cache_manager
        )
        
    def _create_file_watcher(self, parser: ICodeParser, embedder: IEmbedder, vector_store: IVectorStore) -> FileWatcher:
        """创建文件监听器"""
        return FileWatcher(
            workspace_path=self.workspace_path,
            cache_manager=self.cache_manager,
            code_parser=parser,
            embedder=embedder,
            vector_store=vector_store
        )
        
    def _get_vector_size(self, config, embedder: IEmbedder) -> int:
        """获取向量维度"""
        # 如果配置中有明确的维度，优先使用
        if hasattr(config, 'model_dimension') and config.model_dimension:
            return config.model_dimension
            
        # 否则根据嵌入器类型推断
        provider = config.embedder_provider.value
        model_id = config.model_id
        
        if provider == "openai":
            if model_id == "text-embedding-3-small":
                return 1536
            elif model_id == "text-embedding-3-large":
                return 3072
            elif model_id == "text-embedding-ada-002":
                return 1536
            else:
                return 1536  # 默认
                
        elif provider == "gemini":
            return 768
            
        elif provider == "ollama":
            # Ollama模型维度可能不同，默认1536
            return 1536
            
        elif provider == "openai-compatible":
            # 根据模型ID推断
            if hasattr(embedder, 'get_model_dimension'):
                return embedder.get_model_dimension()
            return 1536
            
        return 1536  # 默认
        
    async def validate_embedder(self, embedder: IEmbedder) -> Dict[str, Any]:
        """验证嵌入器配置"""
        try:
            return await embedder.validate_configuration()
        except Exception as error:
            return {
                'valid': False,
                'error': str(error)
            }