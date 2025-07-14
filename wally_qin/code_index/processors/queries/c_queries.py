"""
C Tree-sitter查询模式
支持C语言结构
"""

C_QUERY = """
; Function definitions
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function)) @definition.function

; Struct definitions
(struct_specifier
  name: (type_identifier) @name.definition.struct) @definition.struct

; Typedef declarations
(type_definition
  declarator: (type_identifier) @name.definition.typedef) @definition.typedef

; Function declarations (prototypes)
(declaration
  declarator: (function_declarator
    declarator: (identifier) @name.definition.function_declaration)) @definition.function_declaration

; Variable declarations
(declaration
  declarator: (identifier) @name.definition.variable) @definition.variable

; Enum definitions
(enum_specifier
  name: (type_identifier) @name.definition.enum) @definition.enum

; Union definitions
(union_specifier
  name: (type_identifier) @name.definition.union) @definition.union

; Preprocessor defines
(preproc_def
  name: (identifier) @name.definition.macro) @definition.macro
"""