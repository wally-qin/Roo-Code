"""
代码解析器实现 (增强版)

基于原TypeScript项目的CodeParser类重新实现，
支持多种编程语言的代码解析和分块处理。
完整迁移了TypeScript版本的tree-sitter查询。
"""

import os
import hashlib
import re
from typing import List, Optional, Set, Dict, Any, Tuple
import logging
import asyncio
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_rust
import tree_sitter_go
import tree_sitter_java
import tree_sitter_cpp
import tree_sitter_c
from tree_sitter import Language, Parser, Node, Query

from ..interfaces import ICodeParser, CodeBlock
from ..constants import (
    MAX_BLOCK_CHARS, MIN_BLOCK_CHARS, MIN_CHUNK_REMAINDER_CHARS,
    MAX_CHARS_TOLERANCE_FACTOR, SUPPORTED_EXTENSIONS
)
from .queries import get_query_for_language

logger = logging.getLogger(__name__)


class CodeParser(ICodeParser):
    """代码解析器实现"""
    
    def __init__(self):
        """初始化代码解析器"""
        self.loaded_parsers: Dict[str, Dict[str, Any]] = {}
        self._init_tree_sitter_parsers()
        
    def _init_tree_sitter_parsers(self) -> None:
        """初始化tree-sitter解析器 (增强版)"""
        try:
            # 创建语言解析器映射
            language_map = {
                'py': Language(tree_sitter_python.language()),
                'js': Language(tree_sitter_javascript.language()),
                'jsx': Language(tree_sitter_javascript.language()),
                'ts': Language(tree_sitter_typescript.language_typescript()),
                'tsx': Language(tree_sitter_typescript.language_tsx()),
                'rs': Language(tree_sitter_rust.language()),
                'go': Language(tree_sitter_go.language()),
                'java': Language(tree_sitter_java.language()),
                'cpp': Language(tree_sitter_cpp.language()),
                'c': Language(tree_sitter_c.language()),
                'h': Language(tree_sitter_c.language()),
                'hpp': Language(tree_sitter_cpp.language()),
                'cc': Language(tree_sitter_cpp.language()),
                'cxx': Language(tree_sitter_cpp.language()),
            }
            
            # 为每种语言创建解析器
            for ext, language in language_map.items():
                parser = Parser()
                parser.set_language(language)
                
                # 使用完整的TypeScript迁移查询
                query_pattern = get_query_for_language(ext)
                query = None
                
                if query_pattern:
                    try:
                        query = language.query(query_pattern)
                        logger.debug(f"Loaded tree-sitter query for {ext}: {len(query_pattern)} chars")
                    except Exception as query_error:
                        logger.warning(f"Failed to load query for {ext}: {query_error}")
                        # 使用简化查询作为后备
                        fallback_query = self._get_fallback_query(ext)
                        if fallback_query:
                            query = language.query(fallback_query)
                
                self.loaded_parsers[ext] = {
                    'parser': parser,
                    'language': language,
                    'query': query
                }
                
        except Exception as error:
            logger.error(f"Error initializing tree-sitter parsers: {error}")
            
    def _get_fallback_query(self, extension: str) -> Optional[str]:
        """获取简化的后备查询模式"""
        fallback_patterns = {
            'py': """
                (function_definition) @function
                (class_definition) @class
                (async_function_def) @function
            """,
            'js': """
                (function_declaration) @function
                (method_definition) @function
                (class_declaration) @class
                (arrow_function) @function
            """,
            'jsx': """
                (function_declaration) @function
                (method_definition) @function
                (class_declaration) @class
                (arrow_function) @function
            """,
            'ts': """
                (function_declaration) @function
                (method_definition) @function
                (class_declaration) @class
                (interface_declaration) @interface
                (type_alias_declaration) @type
            """,
            'tsx': """
                (function_declaration) @function
                (method_definition) @function
                (class_declaration) @class
                (interface_declaration) @interface
                (type_alias_declaration) @type
            """,
            'rs': """
                (function_item) @function
                (impl_item) @implementation
                (struct_item) @struct
                (enum_item) @enum
                (trait_item) @trait
            """,
            'go': """
                (function_declaration) @function
                (method_declaration) @function
                (type_declaration) @type
                (struct_type) @struct
                (interface_type) @interface
            """,
            'java': """
                (method_declaration) @function
                (class_declaration) @class
                (interface_declaration) @interface
                (constructor_declaration) @constructor
            """,
            'cpp': """
                (function_definition) @function
                (class_specifier) @class
                (struct_specifier) @struct
                (namespace_definition) @namespace
            """,
            'c': """
                (function_definition) @function
                (struct_specifier) @struct
                (typedef_declaration) @typedef
            """
        }
        
        return fallback_patterns.get(extension)
        
    async def parse_file(self, file_path: str, content: Optional[str] = None, 
                        file_hash: Optional[str] = None) -> List[CodeBlock]:
        """
        解析代码文件为代码块
        
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
            return []
            
        # 获取文件内容
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as error:
                logger.error(f"Error reading file {file_path}: {error}")
                return []
                
        # 计算文件哈希
        if file_hash is None:
            file_hash = self._create_file_hash(content)
            
        # 解析内容
        return await self._parse_content(file_path, content, file_hash)
        
    def _is_supported_language(self, extension: str) -> bool:
        """检查是否支持该语言"""
        return extension in SUPPORTED_EXTENSIONS
        
    def _create_file_hash(self, content: str) -> str:
        """创建文件哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
        
    async def _parse_content(self, file_path: str, content: str, file_hash: str) -> List[CodeBlock]:
        """解析文件内容为代码块"""
        ext = os.path.splitext(file_path)[1][1:].lower()  # 去掉点号
        seen_segment_hashes: Set[str] = set()
        
        # 处理Markdown文件
        if ext in ['md', 'markdown']:
            return self._parse_markdown_content(file_path, content, file_hash, seen_segment_hashes)
            
        # 检查是否有可用的解析器
        if ext not in self.loaded_parsers:
            logger.warning(f"No parser available for file extension: {ext}")
            return []
            
        parser_info = self.loaded_parsers[ext]
        parser = parser_info['parser']
        query = parser_info['query']
        
        # 解析代码
        tree = parser.parse(content.encode('utf-8'))
        
        if not tree or not query:
            # 回退到基本分块
            if len(content) >= MIN_BLOCK_CHARS:
                return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            return []
            
        # 执行查询
        captures = query.captures(tree.root_node)
        
        if not captures:
            # 回退到基本分块
            if len(content) >= MIN_BLOCK_CHARS:
                return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
            return []
            
        results: List[CodeBlock] = []
        
        # 组织查询结果：按节点分组captures
        node_captures = {}
        for node, capture_name in captures:
            if node not in node_captures:
                node_captures[node] = []
            node_captures[node].append((node, capture_name))
        
        # 处理捕获的节点
        queue = list(node_captures.keys())
        
        while queue:
            current_node = queue.pop(0)
            node_query_matches = node_captures.get(current_node, [])
            
            # 检查节点是否满足最小字符要求
            if len(current_node.text) >= MIN_BLOCK_CHARS:
                # 如果超过最大字符限制，尝试拆分
                if len(current_node.text) > MAX_BLOCK_CHARS * MAX_CHARS_TOLERANCE_FACTOR:
                    if current_node.children:
                        # 如果有子节点，处理子节点
                        for child in current_node.children:
                            if child and child not in node_captures:
                                queue.append(child)
                                node_captures[child] = []
                    else:
                        # 如果是叶节点，进行分块
                        chunked_blocks = self._chunk_leaf_node_by_lines(
                            current_node, file_path, file_hash, seen_segment_hashes
                        )
                        results.extend(chunked_blocks)
                else:
                    # 节点满足要求，创建代码块
                    identifier = self._extract_identifier(current_node, node_query_matches)
                    block_type = self._get_block_type_from_captures(node_query_matches, current_node.type)
                    start_line = current_node.start_point[0] + 1
                    end_line = current_node.end_point[0] + 1
                    block_content = current_node.text.decode('utf-8') if isinstance(current_node.text, bytes) else current_node.text
                    
                    content_preview = block_content[:100]
                    segment_hash = hashlib.sha256(
                        f"{file_path}-{start_line}-{end_line}-{len(block_content)}-{content_preview}".encode('utf-8')
                    ).hexdigest()
                    
                    if segment_hash not in seen_segment_hashes:
                        seen_segment_hashes.add(segment_hash)
                        results.append(CodeBlock(
                            file_path=file_path,
                            identifier=identifier,
                            type=block_type,
                            start_line=start_line,
                            end_line=end_line,
                            content=block_content,
                            file_hash=file_hash,
                            segment_hash=segment_hash
                        ))
                        
        return results
    
    def _get_block_type_from_captures(self, captures: List[Tuple], default_type: str) -> str:
        """从查询捕获中获取更准确的块类型"""
        try:
            for capture in captures:
                capture_name = capture[1]  # capture name
                
                # 查找definition.*类型的捕获
                if capture_name.startswith('definition.'):
                    return capture_name.replace('definition.', '')
                    
                # 查找简单的类型捕获
                if capture_name in ['function', 'class', 'method', 'interface', 'type', 'enum', 'struct']:
                    return capture_name
                    
            return default_type
        except Exception:
            return default_type
        
    def _extract_identifier(self, node: Node, query_matches: List = None) -> Optional[str]:
        """从节点中提取标识符 (增强版)"""
        try:
            # 首先尝试从查询匹配中提取name.definition.*
            if query_matches:
                for match in query_matches:
                    for capture in match:
                        capture_name = capture[1]  # capture name
                        capture_node = capture[0]  # capture node
                        
                        # 查找name.definition.*类型的捕获
                        if 'name.definition' in capture_name:
                            # 检查这个捕获是否属于当前节点
                            if self._node_contains_or_equals(node, capture_node):
                                return capture_node.text.decode('utf-8')
                        
                        # 查找简单的name捕获
                        if capture_name == 'name':
                            if self._node_contains_or_equals(node, capture_node):
                                return capture_node.text.decode('utf-8')
            
            # 后备方法：传统的节点遍历
            return self._extract_identifier_fallback(node)
            
        except Exception as e:
            logger.debug(f"Error extracting identifier: {e}")
            return self._extract_identifier_fallback(node)
    
    def _node_contains_or_equals(self, parent: Node, child: Node) -> bool:
        """检查父节点是否包含或等于子节点"""
        if parent == child:
            return True
        
        current = child.parent
        while current:
            if current == parent:
                return True
            current = current.parent
        return False
    
    def _extract_identifier_fallback(self, node: Node) -> Optional[str]:
        """后备的标识符提取方法"""
        try:
            # 尝试查找名称字段
            name_node = node.child_by_field_name("name")
            if name_node:
                return name_node.text.decode('utf-8') if isinstance(name_node.text, bytes) else name_node.text
                
            # 查找identifier类型的子节点
            for child in node.children:
                if child and child.type == "identifier":
                    return child.text.decode('utf-8') if isinstance(child.text, bytes) else child.text
                    
            return None
        except Exception:
            return None
            
    def _chunk_leaf_node_by_lines(self, node: Node, file_path: str, 
                                 file_hash: str, seen_segment_hashes: Set[str]) -> List[CodeBlock]:
        """按行分块叶节点"""
        content = node.text.decode('utf-8') if isinstance(node.text, bytes) else node.text
        lines = content.split('\n')
        base_start_line = node.start_point[0] + 1
        
        return self._chunk_text_by_lines(
            lines, file_path, file_hash, node.type, seen_segment_hashes, base_start_line
        )
        
    def _chunk_text_by_lines(self, lines: List[str], file_path: str, file_hash: str,
                           chunk_type: str, seen_segment_hashes: Set[str], 
                           base_start_line: int = 1) -> List[CodeBlock]:
        """按行分块文本"""
        results: List[CodeBlock] = []
        current_chunk_lines: List[str] = []
        current_chunk_start_line = base_start_line
        
        def finalize_chunk(end_line_index: int) -> None:
            if current_chunk_lines:
                chunk_content = '\n'.join(current_chunk_lines)
                if len(chunk_content) >= MIN_BLOCK_CHARS:
                    end_line = base_start_line + end_line_index
                    content_preview = chunk_content[:100]
                    segment_hash = hashlib.sha256(
                        f"{file_path}-{current_chunk_start_line}-{end_line}-{len(chunk_content)}-{content_preview}".encode('utf-8')
                    ).hexdigest()
                    
                    if segment_hash not in seen_segment_hashes:
                        seen_segment_hashes.add(segment_hash)
                        results.append(CodeBlock(
                            file_path=file_path,
                            identifier=None,
                            type=chunk_type,
                            start_line=current_chunk_start_line,
                            end_line=end_line,
                            content=chunk_content,
                            file_hash=file_hash,
                            segment_hash=segment_hash
                        ))
                        
        for i, line in enumerate(lines):
            current_chunk_lines.append(line)
            current_chunk_content = '\n'.join(current_chunk_lines)
            
            # 检查是否超过最大字符数
            if len(current_chunk_content) > MAX_BLOCK_CHARS:
                # 确保剩余内容足够大
                remaining_lines = lines[i+1:]
                remaining_content = '\n'.join(remaining_lines)
                
                if len(remaining_content) >= MIN_CHUNK_REMAINDER_CHARS:
                    # 完成当前块（不包括当前行）
                    current_chunk_lines.pop()  # 移除当前行
                    finalize_chunk(i - 1)
                    
                    # 开始新块
                    current_chunk_lines = [line]
                    current_chunk_start_line = base_start_line + i
                    
        # 完成最后一个块
        if current_chunk_lines:
            finalize_chunk(len(lines) - 1)
            
        return results
        
    def _perform_fallback_chunking(self, file_path: str, content: str, 
                                  file_hash: str, seen_segment_hashes: Set[str]) -> List[CodeBlock]:
        """执行回退分块"""
        lines = content.split('\n')
        return self._chunk_text_by_lines(
            lines, file_path, file_hash, "fallback_chunk", seen_segment_hashes
        )
        
    def _parse_markdown_content(self, file_path: str, content: str, 
                               file_hash: str, seen_segment_hashes: Set[str]) -> List[CodeBlock]:
        """解析Markdown内容"""
        lines = content.split('\n')
        results: List[CodeBlock] = []
        current_section_lines: List[str] = []
        current_section_start_line = 1
        current_section_type = "content"
        current_section_identifier = None
        
        for i, line in enumerate(lines, 1):
            # 检查是否是标题
            if line.strip().startswith('#'):
                # 完成当前部分
                if current_section_lines:
                    section_blocks = self._process_markdown_section(
                        current_section_lines, file_path, file_hash,
                        current_section_type, seen_segment_hashes,
                        current_section_start_line, current_section_identifier
                    )
                    results.extend(section_blocks)
                    
                # 开始新部分
                current_section_lines = [line]
                current_section_start_line = i
                current_section_type = "section"
                current_section_identifier = line.strip()
            else:
                current_section_lines.append(line)
                
        # 处理最后一个部分
        if current_section_lines:
            section_blocks = self._process_markdown_section(
                current_section_lines, file_path, file_hash,
                current_section_type, seen_segment_hashes,
                current_section_start_line, current_section_identifier
            )
            results.extend(section_blocks)
            
        return results
        
    def _process_markdown_section(self, lines: List[str], file_path: str, file_hash: str,
                                 section_type: str, seen_segment_hashes: Set[str],
                                 start_line: int, identifier: Optional[str] = None) -> List[CodeBlock]:
        """处理Markdown部分"""
        return self._chunk_text_by_lines(
            lines, file_path, file_hash, section_type, seen_segment_hashes, start_line
        )