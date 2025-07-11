"""
代码索引系统接口定义

定义所有核心组件的接口，确保系统的模块化和可扩展性。
基于原TypeScript项目的接口设计。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, AsyncIterator, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio


# 数据模型
@dataclass
class CodeBlock:
    """代码块数据结构"""
    file_path: str
    identifier: Optional[str]
    type: str
    start_line: int
    end_line: int
    content: str
    file_hash: str
    segment_hash: str


@dataclass 
class EmbeddingResponse:
    """嵌入响应数据结构"""
    embeddings: List[List[float]]
    usage: Optional[Dict[str, int]] = None


@dataclass
class VectorStoreSearchResult:
    """向量存储搜索结果"""
    id: Union[str, int]
    score: float
    payload: Optional[Dict[str, Any]] = None


@dataclass
class PointStruct:
    """向量点数据结构"""
    id: str
    vector: List[float]
    payload: Dict[str, Any]


@dataclass
class FileProcessingResult:
    """文件处理结果"""
    path: str
    status: str  # "success" | "skipped" | "error" | "processed_for_batching" | "local_error"
    error: Optional[Exception] = None
    reason: Optional[str] = None
    new_hash: Optional[str] = None
    points_to_upsert: Optional[List[PointStruct]] = None


@dataclass
class BatchProcessingSummary:
    """批处理摘要"""
    processed_files: List[FileProcessingResult]
    batch_error: Optional[Exception] = None


class IndexingState(Enum):
    """索引状态枚举"""
    STANDBY = "Standby"
    INDEXING = "Indexing" 
    INDEXED = "Indexed"
    ERROR = "Error"


class EmbedderProvider(Enum):
    """嵌入器提供商枚举"""
    OPENAI = "openai"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai-compatible"
    GEMINI = "gemini"


# 核心接口定义

class IEmbedder(ABC):
    """嵌入器接口"""
    
    @abstractmethod
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """创建文本嵌入"""
        pass
    
    @abstractmethod
    async def validate_configuration(self) -> Dict[str, Any]:
        """验证配置"""
        pass
    
    @property
    @abstractmethod
    def embedder_info(self) -> Dict[str, str]:
        """获取嵌入器信息"""
        pass


class IVectorStore(ABC):
    """向量存储接口"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化向量存储，返回是否创建了新集合"""
        pass
    
    @abstractmethod
    async def upsert_points(self, points: List[PointStruct]) -> None:
        """插入或更新向量点"""
        pass
    
    @abstractmethod
    async def search(self, query_vector: List[float], directory_prefix: Optional[str] = None,
                    min_score: Optional[float] = None, max_results: Optional[int] = None) -> List[VectorStoreSearchResult]:
        """搜索相似向量"""
        pass
    
    @abstractmethod
    async def delete_points_by_file_path(self, file_path: str) -> None:
        """根据文件路径删除向量点"""
        pass
    
    @abstractmethod
    async def delete_points_by_multiple_file_paths(self, file_paths: List[str]) -> None:
        """根据多个文件路径删除向量点"""
        pass
    
    @abstractmethod
    async def clear_collection(self) -> None:
        """清空集合"""
        pass
    
    @abstractmethod
    async def delete_collection(self) -> None:
        """删除集合"""
        pass
    
    @abstractmethod
    async def collection_exists(self) -> bool:
        """检查集合是否存在"""
        pass


class ICodeParser(ABC):
    """代码解析器接口"""
    
    @abstractmethod
    async def parse_file(self, file_path: str, content: Optional[str] = None, 
                        file_hash: Optional[str] = None) -> List[CodeBlock]:
        """解析文件为代码块"""
        pass


class IDirectoryScanner(ABC):
    """目录扫描器接口"""
    
    @abstractmethod
    async def scan_directory(self, directory: str, 
                           on_error: Optional[Callable[[Exception], None]] = None,
                           on_blocks_indexed: Optional[Callable[[int], None]] = None,
                           on_file_parsed: Optional[Callable[[int], None]] = None) -> Dict[str, Any]:
        """扫描目录"""
        pass


class IFileWatcher(ABC):
    """文件监听器接口"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化文件监听器"""
        pass
    
    @abstractmethod
    async def process_file(self, file_path: str) -> FileProcessingResult:
        """处理文件"""
        pass
    
    @abstractmethod
    def start_watching(self) -> None:
        """开始监听文件变化"""
        pass
    
    @abstractmethod
    def stop_watching(self) -> None:
        """停止监听文件变化"""
        pass
    
    @property
    @abstractmethod
    def on_batch_start(self) -> asyncio.Event:
        """批处理开始事件"""
        pass
    
    @property
    @abstractmethod
    def on_batch_progress(self) -> asyncio.Event:
        """批处理进度事件"""
        pass
    
    @property
    @abstractmethod
    def on_batch_complete(self) -> asyncio.Event:
        """批处理完成事件"""
        pass


# 配置相关接口
@dataclass
class CodeIndexConfig:
    """代码索引配置"""
    is_configured: bool
    embedder_provider: EmbedderProvider
    model_id: Optional[str] = None
    model_dimension: Optional[int] = None
    openai_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    openai_compatible_base_url: Optional[str] = None
    openai_compatible_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    milvus_host: Optional[str] = None
    milvus_port: Optional[str] = None
    milvus_user: Optional[str] = None
    milvus_password: Optional[str] = None
    chroma_host: Optional[str] = None
    chroma_port: Optional[int] = None
    chroma_persist_directory: Optional[str] = None
    search_min_score: Optional[float] = None
    search_max_results: Optional[int] = None


@dataclass
class ConfigSnapshot:
    """配置快照，用于检测配置变化"""
    enabled: bool
    configured: bool
    embedder_provider: EmbedderProvider
    model_id: Optional[str]
    model_dimension: Optional[int]
    openai_key: str
    ollama_base_url: str
    openai_compatible_base_url: str
    openai_compatible_api_key: str
    gemini_api_key: str
    qdrant_url: str
    qdrant_api_key: str
    milvus_host: str
    milvus_port: str
    milvus_user: str
    milvus_password: str
    chroma_host: str
    chroma_port: str
    chroma_persist_directory: str