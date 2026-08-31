"""
CSS 语言的 tree-sitter 查询

用于解析 CSS 样式表的结构化查询。
"""

CSS_QUERY = """
(rule_set
  (selectors) @definition.selector
  (block
    (declaration
      (property_name) @definition.property
      (declaration_value) @assignment)))

(at_rule
  (at_keyword) @definition.at_rule
  (rule_set
    (selectors) @definition.selector))

(keyframes_statement
  (keyframes_name) @definition.keyframes)

(media_statement
  (media_feature_name) @definition.media_feature)

(import_statement
  (string_value) @reference.import)

(comment) @comment
"""