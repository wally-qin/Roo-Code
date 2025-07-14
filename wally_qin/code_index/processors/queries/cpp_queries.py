"""
C++ Tree-sitter查询模式
支持C++语言结构
"""

CPP_QUERY = """
; Function definitions
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function)) @definition.function

; Class definitions
(class_specifier
  name: (type_identifier) @name.definition.class) @definition.class

; Struct definitions
(struct_specifier
  name: (type_identifier) @name.definition.struct) @definition.struct

; Namespace definitions
(namespace_definition
  name: (identifier) @name.definition.namespace) @definition.namespace

; Method definitions
(function_definition
  declarator: (function_declarator
    declarator: (qualified_identifier
      scope: (namespace_identifier)
      name: (identifier) @name.definition.method))) @definition.method

; Template declarations
(template_declaration) @definition.template

; Using declarations
(using_declaration) @definition.using

; Typedef declarations
(type_definition
  declarator: (type_identifier) @name.definition.typedef) @definition.typedef
"""