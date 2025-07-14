"""
Tree-sitter查询模块

从TypeScript版本完整迁移所有语言的查询文件，
确保与原版本功能对等。
"""

from .python_queries import PYTHON_QUERY
from .javascript_queries import JAVASCRIPT_QUERY
from .typescript_queries import TYPESCRIPT_QUERY
from .rust_queries import RUST_QUERY
from .go_queries import GO_QUERY
from .java_queries import JAVA_QUERY
from .cpp_queries import CPP_QUERY
from .c_queries import C_QUERY
from .csharp_queries import CSHARP_QUERY
from .ruby_queries import RUBY_QUERY
from .php_queries import PHP_QUERY

# 语言查询映射
LANGUAGE_QUERIES = {
    'py': PYTHON_QUERY,
    'js': JAVASCRIPT_QUERY,
    'jsx': JAVASCRIPT_QUERY,
    'ts': TYPESCRIPT_QUERY,
    'tsx': TYPESCRIPT_QUERY,
    'rs': RUST_QUERY,
    'go': GO_QUERY,
    'java': JAVA_QUERY,
    'cpp': CPP_QUERY,
    'cc': CPP_QUERY,
    'cxx': CPP_QUERY,
    'c': C_QUERY,
    'h': C_QUERY,
    'hpp': CPP_QUERY,
    'cs': CSHARP_QUERY,
    'rb': RUBY_QUERY,
    'php': PHP_QUERY,
}

def get_query_for_language(extension: str) -> str:
    """获取指定语言的查询字符串"""
    return LANGUAGE_QUERIES.get(extension, "")