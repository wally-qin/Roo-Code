"""
TOML 语言的 tree-sitter 查询

用于解析 TOML 配置文件的结构化查询。
"""

TOML_QUERY = """
(table
  (bare_key) @definition.table)

(dotted_key
  (bare_key) @definition.key)

(pair
  key: (bare_key) @definition.key
  value: (_) @assignment)

(pair
  key: (dotted_key) @definition.key  
  value: (_) @assignment)

(array_table
  (bare_key) @definition.array_table)

(comment) @comment
"""