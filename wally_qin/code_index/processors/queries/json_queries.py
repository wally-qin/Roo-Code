"""
JSON 语言的 tree-sitter 查询

用于解析 JSON 数据格式的结构化查询。
"""

JSON_QUERY = """
(pair
  key: (string) @definition.key
  value: (_) @assignment)

(object
  (pair
    key: (string) @definition.key
    value: (object))) @definition.object

(object
  (pair
    key: (string) @definition.key
    value: (array))) @definition.array_field

(array
  (object)) @definition.array_object

(array
  (string) @definition.array_string)

(array
  (number) @definition.array_number)
"""