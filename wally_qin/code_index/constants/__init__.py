"""
代码索引系统常量定义

包含所有系统级别的常量配置，与原TypeScript项目保持一致。
"""

# 解析器相关常量
MAX_BLOCK_CHARS = 1000
MIN_BLOCK_CHARS = 50
MIN_CHUNK_REMAINDER_CHARS = 200  # 分块后最小字符数
MAX_CHARS_TOLERANCE_FACTOR = 1.15  # 最大字符数容忍因子 (15%)

# 搜索相关常量
DEFAULT_SEARCH_MIN_SCORE = 0.7
DEFAULT_MAX_SEARCH_RESULTS = 100

# 文件监听器常量
QDRANT_CODE_BLOCK_NAMESPACE = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1MB

# 目录扫描器常量
MAX_LIST_FILES_LIMIT = 3000
BATCH_SEGMENT_THRESHOLD = 60  # 批处理代码片段数量
MAX_BATCH_RETRIES = 3
INITIAL_RETRY_DELAY_MS = 500
PARSING_CONCURRENCY = 10
MAX_CONCURRENT_FILES = 10  # 最大并发文件处理数量
BATCH_SIZE = 60  # 批处理大小
MAX_CHUNK_SIZE = 1000  # 最大代码块大小
MIN_CHUNK_SIZE = 50  # 最小代码块大小
BATCH_PROCESSING_DELAY = 2.0  # 批处理延迟（秒）

# OpenAI 嵌入器常量
MAX_BATCH_TOKENS = 100000
MAX_ITEM_TOKENS = 8191
BATCH_PROCESSING_CONCURRENCY = 10

# Gemini 嵌入器常量
GEMINI_MAX_ITEM_TOKENS = 2048

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {
    ".tla", ".js", ".jsx", ".ts", ".vue", ".tsx", ".py",
    ".rs", ".go", ".c", ".h", ".cpp", ".hpp", ".cs", 
    ".rb", ".java", ".php", ".swift", ".sol", ".kt", 
    ".kts", ".ex", ".exs", ".el", ".html", ".htm", 
    ".md", ".markdown", ".json", ".css", ".rdl", 
    ".ml", ".mli", ".lua", ".scala", ".toml", ".zig", 
    ".elm", ".ejs", ".erb"
}

# 默认配置
DEFAULT_CONFIG = {
    "enabled": True,
    "embedder_provider": "openai",
    "model_id": "text-embedding-3-small",
    "vector_store": "qdrant",
    "qdrant_url": "http://localhost:6333",
    "search_min_score": DEFAULT_SEARCH_MIN_SCORE,
    "search_max_results": DEFAULT_MAX_SEARCH_RESULTS
}

# 嵌入模型配置
EMBEDDING_MODELS = {
    "openai": {
        "text-embedding-3-small": {"dimension": 1536, "max_tokens": 8191},
        "text-embedding-3-large": {"dimension": 3072, "max_tokens": 8191},
        "text-embedding-ada-002": {"dimension": 1536, "max_tokens": 8191}
    },
    "gemini": {
        "text-embedding-004": {"dimension": 768, "max_tokens": 2048}
    },
    "ollama": {
        "nomic-embed-text": {"dimension": 768, "max_tokens": 8192},
        "mxbai-embed-large": {"dimension": 1024, "max_tokens": 512}
    }
}

# 向量存储选项
VECTOR_STORE_OPTIONS = ["qdrant", "milvus", "chroma"]