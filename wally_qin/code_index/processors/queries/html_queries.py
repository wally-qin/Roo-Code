"""
HTML 语言的 tree-sitter 查询

用于解析 HTML 标记语言的结构化查询。
"""

HTML_QUERY = """
(element
  (start_tag
    (tag_name) @definition.tag))

(element
  (start_tag
    (tag_name) @definition.tag
    (attribute
      (attribute_name) @definition.attribute)))

(script_element
  (start_tag) @definition.script
  (raw_text) @assignment)

(style_element
  (start_tag) @definition.style
  (raw_text) @assignment)

(attribute
  (attribute_name) @definition.attribute
  (quoted_attribute_value) @assignment)

(comment) @comment
"""