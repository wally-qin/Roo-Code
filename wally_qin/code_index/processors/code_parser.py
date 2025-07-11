"""
代码解析器实现

基于原TypeScript项目的CodeParser类重新实现，
支持使用tree-sitter解析多种编程语言，提供真正的代码结构识别。
"""

import asyncio
import hashlib
import os
import re
from typing import List, Optional, Dict, Any, Set, Tuple
import logging

from ..interfaces import ICodeParser, CodeBlock
from ..constants import (
    MAX_BLOCK_CHARS, MIN_BLOCK_CHARS, MIN_CHUNK_REMAINDER_CHARS,
    MAX_CHARS_TOLERANCE_FACTOR, SUPPORTED_EXTENSIONS, LANGUAGE_EXTENSIONS
)

logger = logging.getLogger(__name__)

# Tree-sitter imports with fallback
try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript  
    import tree_sitter_typescript as tstypescript
    import tree_sitter_java as tsjava
    import tree_sitter_go as tsgo
    import tree_sitter_rust as tsrust
    import tree_sitter_c as tsc
    import tree_sitter_cpp as tscpp
    import tree_sitter_c_sharp as tscsharp
    import tree_sitter_ruby as tsruby
    import tree_sitter_php as tsphp
    import tree_sitter_html as tshtml
    import tree_sitter_css as tscss
    import tree_sitter_json as tsjson
    TREE_SITTER_AVAILABLE = True
except ImportError:
    logger.warning("Tree-sitter languages not available, falling back to text chunking")
    TREE_SITTER_AVAILABLE = False

if TREE_SITTER_AVAILABLE:
    from tree_sitter import Language, Parser, Node


# Language-specific query patterns
LANGUAGE_QUERIES = {
    "python": """
    (function_definition
      name: (identifier) @name.definition.function) @definition.function
    
    (class_definition
      name: (identifier) @name.definition.class) @definition.class
    
    (import_statement) @definition.import
    (import_from_statement) @definition.import
    """,
    
    "javascript": """
    (function_declaration
      name: (identifier) @name.definition.function) @definition.function
    
    (class_declaration
      name: (identifier) @name.definition.class) @definition.class
    
    (method_definition
      name: (property_identifier) @name.definition.method) @definition.method
    
    (variable_declarator
      name: (identifier) @name.definition.variable) @definition.variable
    
    (import_statement) @definition.import
    """,
    
    "typescript": """
    (function_declaration
      name: (identifier) @name.definition.function) @definition.function
    
    (class_declaration
      name: (type_identifier) @name.definition.class) @definition.class
    
    (interface_declaration
      name: (type_identifier) @name.definition.interface) @definition.interface
    
    (type_alias_declaration
      name: (type_identifier) @name.definition.type) @definition.type
    
    (method_definition
      name: (property_identifier) @name.definition.method) @definition.method
    
    (import_statement) @definition.import
    """,
    
    "java": """
    (method_declaration
      name: (identifier) @name.definition.method) @definition.method
    
    (class_declaration
      name: (identifier) @name.definition.class) @definition.class
    
    (interface_declaration
      name: (identifier) @name.definition.interface) @definition.interface
    
    (import_declaration) @definition.import
    """,
    
    "go": """
    (function_declaration
      name: (identifier) @name.definition.function) @definition.function
    
    (type_declaration
      (type_spec name: (type_identifier) @name.definition.type)) @definition.type
    
    (import_declaration) @definition.import
    """,
    
    "rust": """
    (function_item
      name: (identifier) @name.definition.function) @definition.function
    
    (struct_item
      name: (type_identifier) @name.definition.struct) @definition.struct
    
    (enum_item
      name: (type_identifier) @name.definition.enum) @definition.enum
    
    (trait_item
      name: (type_identifier) @name.definition.trait) @definition.trait
    
    (use_declaration) @definition.import
    """,
    
    "c": """
    (function_definition
      declarator: (function_declarator
        declarator: (identifier) @name.definition.function)) @definition.function
    
    (struct_specifier
      name: (type_identifier) @name.definition.struct) @definition.struct
    
    (preproc_include) @definition.include
    """,
    
    "cpp": """
    (function_definition
      declarator: (function_declarator
        declarator: (identifier) @name.definition.function)) @definition.function
    
    (class_specifier
      name: (type_identifier) @name.definition.class) @definition.class
    
    (struct_specifier
      name: (type_identifier) @name.definition.struct) @definition.struct
    
    (preproc_include) @definition.include
    """,
    
    "ruby": """
    (method
      name: (identifier) @name.definition.method) @definition.method
    
    (class
      name: (constant) @name.definition.class) @definition.class
    
    (module
      name: (constant) @name.definition.module) @definition.module
    """,
    
    "html": """
    (element
      start_tag: (start_tag
        name: (tag_name) @name.definition.element)) @definition.element
    """,
    
    "css": """
    (rule_set
      selectors: (selectors) @name.definition.selector) @definition.rule
    """
}


class TreeSitterLanguageManager:
    """Tree-sitter语言管理器"""
    
    def __init__(self):
        self.loaded_languages: Dict[str, Any] = {}
        self.parsers: Dict[str, Any] = {}
        self.queries: Dict[str, Any] = {}
        
    def get_language_for_extension(self, extension: str) -> Optional[str]:
        """根据文件扩展名获取语言名称"""
        for lang_name, extensions in LANGUAGE_EXTENSIONS.items():
            if extension in extensions:
                return lang_name
        return None
        
    async def load_language_parser(self, language_name: str) -> bool:
        """加载特定语言的解析器"""
        if not TREE_SITTER_AVAILABLE:
            return False
            
        if language_name in self.loaded_languages:
            return True
            
        try:
            # 根据语言名加载对应的tree-sitter库
            if language_name == "python":
                lang = Language(tspython.language())
            elif language_name == "javascript":
                lang = Language(tsjavascript.language())
            elif language_name == "typescript":
                lang = Language(tstypescript.language())
            elif language_name == "java":
                lang = Language(tsjava.language())
            elif language_name == "go":
                lang = Language(tsgo.language())
            elif language_name == "rust":
                lang = Language(tsrust.language())
            elif language_name == "c":
                lang = Language(tsc.language())
            elif language_name == "cpp":
                lang = Language(tscpp.language())
            elif language_name == "c_sharp":
                lang = Language(tscsharp.language())
            elif language_name == "ruby":
                lang = Language(tsruby.language())
            elif language_name == "php":
                lang = Language(tsphp.language())
            elif language_name == "html":
                lang = Language(tshtml.language())
            elif language_name == "css":
                lang = Language(tscss.language())
            elif language_name == "json":
                lang = Language(tsjson.language())
            else:
                logger.warning(f"Unsupported language: {language_name}")
                return False
                
            # 创建解析器
            parser = Parser()
            parser.set_language(lang)
            
            # 创建查询
            query_str = LANGUAGE_QUERIES.get(language_name, "")
            if query_str:
                query = lang.query(query_str)
            else:
                query = None
                
            self.loaded_languages[language_name] = lang
            self.parsers[language_name] = parser
            self.queries[language_name] = query
            
            logger.info(f"Successfully loaded tree-sitter parser for {language_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load tree-sitter parser for {language_name}: {e}")
            return False
            
    def get_parser_and_query(self, language_name: str) -> Optional[Tuple[Any, Any]]:
        """获取解析器和查询对象"""
        if language_name not in self.parsers:
            return None
        return self.parsers[language_name], self.queries[language_name]


class CodeParser(ICodeParser):
    """代码解析器实现"""
    
    def __init__(self):
        """初始化代码解析器"""
        self.language_manager = TreeSitterLanguageManager()
        
    async def parse_file(self, file_path: str, content: Optional[str] = None, 
                        file_hash: Optional[str] = None) -> List[CodeBlock]:
        """
        解析文件为代码块
        
        Args:
            file_path: 文件路径
            content: 可选的文件内容
            file_hash: 可选的文件哈希
            
        Returns:
            代码块列表
        """
        # 获取文件扩展名
        ext = os.path.splitext(file_path)[1].lower()
        
        # 检查是否支持该语言
        if not self._is_supported_language(ext):
            logger.debug(f"Unsupported file extension: {ext}")
            return []
            
        # 获取文件内容
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return []
                
        # 计算文件哈希
        if file_hash is None:
            file_hash = self._create_file_hash(content)
            
        # 解析文件内容
        return await self._parse_content(file_path, content, file_hash)
        
    def _is_supported_language(self, extension: str) -> bool:
        """检查是否支持该语言"""
        return extension in SUPPORTED_EXTENSIONS
        
    def _create_file_hash(self, content: str) -> str:
        """创建文件哈希"""
        return hashlib.sha256(content.encode()).hexdigest()
        
    async def _parse_content(self, file_path: str, content: str, file_hash: str) -> List[CodeBlock]:
        """
        解析文件内容为代码块
        
        Args:
            file_path: 文件路径
            content: 文件内容
            file_hash: 文件哈希
            
        Returns:
            代码块列表
        """
        ext = os.path.splitext(file_path)[1].lower()
        seen_segment_hashes: Set[str] = set()
        
        # 特殊处理markdown文件
        if ext in ['.md', '.markdown']:
            return self._parse_markdown_content(file_path, content, file_hash, seen_segment_hashes)
            
        # 获取语言名称
        language_name = self.language_manager.get_language_for_extension(ext)
        if not language_name:
            logger.warning(f"No language mapping for extension: {ext}")
            return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            
        # 尝试使用tree-sitter解析
        if TREE_SITTER_AVAILABLE:
            return await self._parse_with_tree_sitter(
                file_path, content, file_hash, seen_segment_hashes, language_name
            )
        else:
            # 回退到文本分块
            return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            
    async def _parse_with_tree_sitter(self, file_path: str, content: str, 
                                    file_hash: str, seen_segment_hashes: Set[str],
                                    language_name: str) -> List[CodeBlock]:
        """
        使用tree-sitter解析代码
        
        Args:
            file_path: 文件路径
            content: 文件内容
            file_hash: 文件哈希
            seen_segment_hashes: 已见过的片段哈希集合
            language_name: 语言名称
            
        Returns:
            代码块列表
        """
        # 加载语言解析器
        success = await self.language_manager.load_language_parser(language_name)
        if not success:
            logger.warning(f"Failed to load parser for {language_name}, falling back to chunking")
            return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            
        # 获取解析器和查询
        parser_and_query = self.language_manager.get_parser_and_query(language_name)
        if not parser_and_query:
            return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            
        parser, query = parser_and_query
        
        try:
            # 解析代码为AST
            tree = parser.parse(bytes(content, "utf8"))
            
            # 如果没有查询，进行回退分块
            if not query:
                if len(content) >= MIN_BLOCK_CHARS:
                    return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
                else:
                    return []
                    
            # 运行查询获取captures
            captures = query.captures(tree.root_node)
            
            # 如果没有captures，进行回退分块
            if not captures:
                if len(content) >= MIN_BLOCK_CHARS:
                    return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
                else:
                    return []
                    
            results: List[CodeBlock] = []
            
            # 处理captures
            nodes_to_process = [capture[1] for capture in captures]  # capture[1] is the node
            
            for node in nodes_to_process:
                # 检查节点是否满足最小字符要求
                node_text = node.text.decode('utf-8') if isinstance(node.text, bytes) else str(node.text)
                
                if len(node_text) >= MIN_BLOCK_CHARS:
                    # 如果超过最大字符限制，尝试分解
                    if len(node_text) > MAX_BLOCK_CHARS * MAX_CHARS_TOLERANCE_FACTOR:
                        if node.children:
                            # 如果有子节点，处理子节点
                            nodes_to_process.extend(node.children)
                        else:
                            # 如果是叶节点，进行分块
                            chunked_blocks = self._chunk_leaf_node_by_lines(
                                node, file_path, file_hash, seen_segment_hashes, content
                            )
                            results.extend(chunked_blocks)
                    else:
                        # 节点满足要求，创建代码块
                        block = self._create_code_block_from_node(
                            node, file_path, file_hash, seen_segment_hashes, content
                        )
                        if block:
                            results.append(block)
                            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing with tree-sitter for {file_path}: {e}")
            return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            
    def _create_code_block_from_node(self, node: Any, file_path: str, file_hash: str,
                                   seen_segment_hashes: Set[str], content: str) -> Optional[CodeBlock]:
        """从tree-sitter节点创建代码块"""
        try:
            # 获取节点文本
            node_text = node.text.decode('utf-8') if isinstance(node.text, bytes) else str(node.text)
            
            # 获取标识符（如果有）
            identifier = None
            try:
                # 尝试获取name字段
                for child in node.children:
                    if hasattr(child, 'type') and 'identifier' in child.type:
                        identifier = child.text.decode('utf-8') if isinstance(child.text, bytes) else str(child.text)
                        break
            except:
                pass
                
            # 获取节点类型
            node_type = getattr(node, 'type', 'unknown')
            
            # 获取行号
            start_line = node.start_point[0] + 1  # tree-sitter行号从0开始
            end_line = node.end_point[0] + 1
            
            # 创建哈希
            content_preview = node_text[:100]
            segment_hash = hashlib.sha256(
                f"{file_path}-{start_line}-{end_line}-{len(node_text)}-{content_preview}".encode()
            ).hexdigest()
            
            if segment_hash not in seen_segment_hashes:
                seen_segment_hashes.add(segment_hash)
                return CodeBlock(
                    file_path=file_path,
                    identifier=identifier,
                    type=node_type,
                    start_line=start_line,
                    end_line=end_line,
                    content=node_text,
                    file_hash=file_hash,
                    segment_hash=segment_hash
                )
                
        except Exception as e:
            logger.error(f"Error creating code block from node: {e}")
            
        return None
        
    def _chunk_leaf_node_by_lines(self, node: Any, file_path: str, file_hash: str,
                                seen_segment_hashes: Set[str], content: str) -> List[CodeBlock]:
        """按行分块叶节点"""
        try:
            node_text = node.text.decode('utf-8') if isinstance(node.text, bytes) else str(node.text)
            lines = node_text.split('\n')
            base_start_line = node.start_point[0] + 1
            node_type = getattr(node, 'type', 'unknown')
            
            return self._chunk_text_by_lines(
                lines, file_path, file_hash, node_type, 
                seen_segment_hashes, base_start_line
            )
        except Exception as e:
            logger.error(f"Error chunking leaf node: {e}")
            return []
            
    def _parse_markdown_content(self, file_path: str, content: str, 
                               file_hash: str, seen_segment_hashes: Set[str]) -> List[CodeBlock]:
        """
        解析markdown内容
        
        Args:
            file_path: 文件路径
            content: 文件内容
            file_hash: 文件哈希
            seen_segment_hashes: 已见过的片段哈希集合
            
        Returns:
            代码块列表
        """
        lines = content.split('\n')
        results: List[CodeBlock] = []
        
        # 解析markdown标题和内容
        current_section_lines = []
        current_section_start = 1
        current_header = None
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # 检测标题
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                # 处理之前的部分
                if current_section_lines:
                    blocks = self._process_markdown_section(
                        current_section_lines, file_path, file_hash, 
                        "markdown_section", seen_segment_hashes, 
                        current_section_start, current_header
                    )
                    results.extend(blocks)
                    
                # 开始新部分
                header_level = len(header_match.group(1))
                current_header = header_match.group(2)
                current_section_lines = [line]
                current_section_start = line_num
            else:
                current_section_lines.append(line)
                
        # 处理最后一个部分
        if current_section_lines:
            blocks = self._process_markdown_section(
                current_section_lines, file_path, file_hash,
                "markdown_section", seen_segment_hashes,
                current_section_start, current_header
            )
            results.extend(blocks)
            
        return results
        
    def _process_markdown_section(self, lines: List[str], file_path: str, file_hash: str,
                                 section_type: str, seen_segment_hashes: Set[str],
                                 start_line: int, identifier: Optional[str] = None) -> List[CodeBlock]:
        """处理markdown部分"""
        content = '\n'.join(lines)
        
        if len(content.strip()) < MIN_BLOCK_CHARS:
            return []
            
        # 检查是否需要分块
        needs_chunking = (
            len(content) > MAX_BLOCK_CHARS * MAX_CHARS_TOLERANCE_FACTOR or
            any(len(line) > MAX_BLOCK_CHARS * MAX_CHARS_TOLERANCE_FACTOR for line in lines)
        )
        
        if needs_chunking:
            return self._chunk_text_by_lines(
                lines, file_path, file_hash, section_type, 
                seen_segment_hashes, start_line
            )
            
        # 创建单个代码块
        end_line = start_line + len(lines) - 1
        content_preview = content[:100]
        segment_hash = hashlib.sha256(
            f"{file_path}-{start_line}-{end_line}-{len(content)}-{content_preview}".encode()
        ).hexdigest()
        
        if segment_hash not in seen_segment_hashes:
            seen_segment_hashes.add(segment_hash)
            return [CodeBlock(
                file_path=file_path,
                identifier=identifier,
                type=section_type,
                start_line=start_line,
                end_line=end_line,
                content=content,
                file_hash=file_hash,
                segment_hash=segment_hash
            )]
            
        return []
        
    def _perform_fallback_chunking(self, file_path: str, content: str, 
                                 file_hash: str, seen_segment_hashes: Set[str]) -> List[CodeBlock]:
        """执行回退分块"""
        lines = content.split('\n')
        return self._chunk_text_by_lines(
            lines, file_path, file_hash, "fallback_chunk", seen_segment_hashes
        )
        
    def _chunk_text_by_lines(self, lines: List[str], file_path: str, file_hash: str,
                           chunk_type: str, seen_segment_hashes: Set[str],
                           base_start_line: int = 1) -> List[CodeBlock]:
        """
        按行分块文本（与TypeScript版本完全一致的逻辑）
        
        Args:
            lines: 文本行列表
            file_path: 文件路径
            file_hash: 文件哈希
            chunk_type: 块类型
            seen_segment_hashes: 已见过的片段哈希集合
            base_start_line: 基础起始行号
            
        Returns:
            代码块列表
        """
        chunks: List[CodeBlock] = []
        current_chunk_lines: List[str] = []
        current_chunk_length = 0
        chunk_start_line_index = 0
        effective_max_chars = int(MAX_BLOCK_CHARS * MAX_CHARS_TOLERANCE_FACTOR)
        
        def finalize_chunk(end_line_index: int):
            nonlocal current_chunk_lines, current_chunk_length, chunk_start_line_index
            
            if current_chunk_length >= MIN_BLOCK_CHARS and current_chunk_lines:
                chunk_content = '\n'.join(current_chunk_lines)
                start_line = base_start_line + chunk_start_line_index
                end_line = base_start_line + end_line_index
                content_preview = chunk_content[:100]
                segment_hash = hashlib.sha256(
                    f"{file_path}-{start_line}-{end_line}-{len(chunk_content)}-{content_preview}".encode()
                ).hexdigest()
                
                if segment_hash not in seen_segment_hashes:
                    seen_segment_hashes.add(segment_hash)
                    chunks.append(CodeBlock(
                        file_path=file_path,
                        identifier=None,
                        type=chunk_type,
                        start_line=start_line,
                        end_line=end_line,
                        content=chunk_content,
                        file_hash=file_hash,
                        segment_hash=segment_hash
                    ))
                    
            current_chunk_lines = []
            current_chunk_length = 0
            chunk_start_line_index = end_line_index + 1
            
        def create_segment_block(segment: str, original_line_number: int, start_char_index: int):
            segment_preview = segment[:100]
            segment_hash = hashlib.sha256(
                f"{file_path}-{original_line_number}-{original_line_number}-{start_char_index}-{len(segment)}-{segment_preview}".encode()
            ).hexdigest()
            
            if segment_hash not in seen_segment_hashes:
                seen_segment_hashes.add(segment_hash)
                chunks.append(CodeBlock(
                    file_path=file_path,
                    identifier=None,
                    type=f"{chunk_type}_segment",
                    start_line=original_line_number,
                    end_line=original_line_number,
                    content=segment,
                    file_hash=file_hash,
                    segment_hash=segment_hash
                ))
            
        for i, line in enumerate(lines):
            line_length = len(line) + (1 if i < len(lines) - 1 else 0)  # +1 for newline
            original_line_number = base_start_line + i
            
            # 处理超大行
            if line_length > effective_max_chars:
                # 完成当前块
                if current_chunk_lines:
                    finalize_chunk(i - 1)
                    
                # 分割超大行
                remaining_line = line
                current_segment_start_char = 0
                
                while remaining_line:
                    segment = remaining_line[:MAX_BLOCK_CHARS]
                    remaining_line = remaining_line[MAX_BLOCK_CHARS:]
                    create_segment_block(segment, original_line_number, current_segment_start_char)
                    current_segment_start_char += MAX_BLOCK_CHARS
                    
                chunk_start_line_index = i + 1
                continue
                
            # 处理正常大小的行
            if (current_chunk_length > 0 and 
                current_chunk_length + line_length > effective_max_chars):
                
                # 重新平衡逻辑
                split_index = i - 1
                remainder_length = sum(len(lines[j]) + (1 if j < len(lines) - 1 else 0) 
                                     for j in range(i, len(lines)))
                
                if (current_chunk_length >= MIN_BLOCK_CHARS and
                    remainder_length < MIN_CHUNK_REMAINDER_CHARS and
                    len(current_chunk_lines) > 1):
                    
                    # 尝试重新分配以避免小余块
                    for k in range(i - 2, chunk_start_line_index - 1, -1):
                        potential_chunk_lines = lines[chunk_start_line_index:k + 1]
                        potential_chunk_length = len('\n'.join(potential_chunk_lines))
                        potential_next_chunk_lines = lines[k + 1:]
                        potential_next_chunk_length = len('\n'.join(potential_next_chunk_lines))
                        
                        if (potential_chunk_length >= MIN_BLOCK_CHARS and
                            potential_next_chunk_length >= MIN_CHUNK_REMAINDER_CHARS):
                            split_index = k
                            break
                            
                finalize_chunk(split_index)
                
                if i >= chunk_start_line_index:
                    current_chunk_lines.append(line)
                    current_chunk_length += line_length
                else:
                    continue
            else:
                current_chunk_lines.append(line)
                current_chunk_length += line_length
                
        # 处理最后剩余的块
        if current_chunk_lines:
            finalize_chunk(len(lines) - 1)
            
        return chunks