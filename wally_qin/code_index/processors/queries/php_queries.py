"""
PHP Tree-sitter查询模式
支持PHP语言结构
"""

PHP_QUERY = """
; Function definitions
(function_definition
  name: (name) @name.definition.function) @definition.function

; Class definitions
(class_declaration
  name: (name) @name.definition.class) @definition.class

; Interface definitions
(interface_declaration
  name: (name) @name.definition.interface) @definition.interface

; Trait definitions
(trait_declaration
  name: (name) @name.definition.trait) @definition.trait

; Method definitions
(method_declaration
  name: (name) @name.definition.method) @definition.method

; Property definitions
(property_declaration
  (property_element
    name: (variable_name) @name.definition.property)) @definition.property

; Constant definitions
(const_declaration
  (const_element
    name: (name) @name.definition.constant)) @definition.constant

; Namespace definitions
(namespace_definition
  name: (namespace_name) @name.definition.namespace) @definition.namespace

; Use declarations
(namespace_use_declaration) @definition.use

; Anonymous functions (closures)
(anonymous_function_creation_expression) @definition.closure
"""