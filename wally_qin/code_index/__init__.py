"""
代码索引系统

这是一个完整的代码索引系统，用于分析、嵌入和搜索代码库。
基于原TypeScript项目重新用Python实现，保持完整性和正确性。

主要组件:
- 代码解析器: 使用tree-sitter解析多种编程语言
- 嵌入器: 支持多种AI模型进行代码嵌入
- 向量存储: 使用Qdrant存储和搜索向量
- 文件监控: 实时监控文件变化并更新索引
- 配置管理: 灵活的配置系统支持多种嵌入模型
"""

__version__ = "1.0.0"
__author__ = "Wally Qin"

from .managers.code_index_manager import CodeIndexManager
from .managers.config_manager import CodeIndexConfigManager
from .managers.state_manager import CodeIndexStateManager
from .managers.cache_manager import CacheManager
from .orchestrator import CodeIndexOrchestrator
from .search_service import CodeIndexSearchService

__all__ = [
    "CodeIndexManager",
    "CodeIndexConfigManager", 
    "CodeIndexStateManager",
    "CacheManager",
    "CodeIndexOrchestrator",
    "CodeIndexSearchService",
]