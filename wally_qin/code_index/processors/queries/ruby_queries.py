"""
Ruby Tree-sitter查询模式
支持Ruby语言结构
"""

RUBY_QUERY = """
; Method definitions
(method
  name: (identifier) @name.definition.method) @definition.method

; Class definitions
(class
  name: (constant) @name.definition.class) @definition.class

; Module definitions
(module
  name: (constant) @name.definition.module) @definition.module

; Singleton method definitions
(singleton_method
  object: (self)
  name: (identifier) @name.definition.singleton_method) @definition.singleton_method

; Alias definitions
(alias
  name: (identifier) @name.definition.alias) @definition.alias

; Assignment expressions (for constants and variables)
(assignment
  left: (identifier) @name.definition.variable) @definition.variable

(assignment
  left: (constant) @name.definition.constant) @definition.constant

; Block definitions
(block) @definition.block

; Lambda definitions
(lambda) @definition.lambda

; Proc definitions
(call
  method: (identifier) @method_name
  (#eq? @method_name "proc")) @definition.proc
"""