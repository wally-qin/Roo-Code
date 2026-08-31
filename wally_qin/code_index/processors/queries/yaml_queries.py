"""
YAML 语言的 tree-sitter 查询

用于解析 YAML 配置文件的结构化查询。
"""

YAML_QUERY = """
(block_mapping_pair
  key: (flow_node (plain_scalar) @definition.key)
  value: (_))

(block_mapping_pair
  key: (flow_node (single_quote_scalar) @definition.key)
  value: (_))

(block_mapping_pair
  key: (flow_node (double_quote_scalar) @definition.key)
  value: (_))

(flow_mapping
  (flow_pair
    key: (flow_node) @definition.key
    value: (_)))

(block_sequence_item
  (flow_node) @definition.item)

(comment) @comment
"""