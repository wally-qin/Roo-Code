"""
Java Tree-sitter查询模式
从TypeScript版本完整迁移
"""

JAVA_QUERY = """
; Class declarations
(class_declaration
  name: (identifier) @name.definition.class) @definition.class

; Interface declarations
(interface_declaration
  name: (identifier) @name.definition.interface) @definition.interface

; Method declarations
(method_declaration
  name: (identifier) @name.definition.method) @definition.method

; Constructor declarations
(constructor_declaration
  name: (identifier) @name.definition.constructor) @definition.constructor

; Field declarations
(field_declaration
  declarator: (variable_declarator
    name: (identifier) @name.definition.field)) @definition.field

; Enum declarations
(enum_declaration
  name: (identifier) @name.definition.enum) @definition.enum

; Annotation type declarations
(annotation_type_declaration
  name: (identifier) @name.definition.annotation) @definition.annotation

; Package declarations
(package_declaration
  (scoped_identifier) @name.definition.package) @definition.package

; Import declarations
(import_declaration) @definition.import
"""