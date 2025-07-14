"""
C# Tree-sitter查询模式
支持C#语言结构
"""

CSHARP_QUERY = """
; Class declarations
(class_declaration
  name: (identifier) @name.definition.class) @definition.class

; Interface declarations
(interface_declaration
  name: (identifier) @name.definition.interface) @definition.interface

; Method declarations
(method_declaration
  name: (identifier) @name.definition.method) @definition.method

; Property declarations
(property_declaration
  name: (identifier) @name.definition.property) @definition.property

; Field declarations
(field_declaration
  (variable_declaration
    (variable_declarator
      (identifier) @name.definition.field))) @definition.field

; Constructor declarations
(constructor_declaration
  name: (identifier) @name.definition.constructor) @definition.constructor

; Enum declarations
(enum_declaration
  name: (identifier) @name.definition.enum) @definition.enum

; Struct declarations
(struct_declaration
  name: (identifier) @name.definition.struct) @definition.struct

; Namespace declarations
(namespace_declaration
  name: (qualified_name) @name.definition.namespace) @definition.namespace

; Using directives
(using_directive) @definition.using
"""