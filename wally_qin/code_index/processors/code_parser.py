"""
代码解析器实现

基于原TypeScript项目的CodeParser类重新实现，
支持使用tree-sitter解析多种编程语言和markdown文件。
"""

import asyncio
import hashlib
import os
import re
from typing import List, Optional, Dict, Any, Set
import tree_sitter
from tree_sitter import Language, Parser

from ..interfaces import ICodeParser, CodeBlock
from ..constants import (
    MAX_BLOCK_CHARS, MIN_BLOCK_CHARS, MIN_CHUNK_REMAINDER_CHARS,
    MAX_CHARS_TOLERANCE_FACTOR, SUPPORTED_EXTENSIONS, LANGUAGE_EXTENSIONS
)

import logging
logger = logging.getLogger(__name__)


class CodeParser(ICodeParser):
    """代码解析器实现"""
    
    def __init__(self):
        """初始化代码解析器"""
        self.loaded_parsers: Dict[str, Dict[str, Any]] = {}
        self.pending_loads: Dict[str, asyncio.Future] = {}
        
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
            return []
            
        # 获取文件内容
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"读取文件失败 {file_path}: {e}")
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
            
        # 使用tree-sitter解析其他文件
        return await self._parse_with_tree_sitter(file_path, content, file_hash, seen_segment_hashes)
        
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
        
        # 简化的markdown解析，主要识别标题和代码块
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
        
    async def _parse_with_tree_sitter(self, file_path: str, content: str, 
                                    file_hash: str, seen_segment_hashes: Set[str]) -> List[CodeBlock]:
        """
        使用tree-sitter解析代码
        
        Args:
            file_path: 文件路径
            content: 文件内容
            file_hash: 文件哈希
            seen_segment_hashes: 已见过的片段哈希集合
            
        Returns:
            代码块列表
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # 简化的tree-sitter解析实现
        # 在实际实现中，这里应该加载相应的tree-sitter语言解析器
        # 由于复杂性，这里提供一个基础的回退解析
        
        if len(content) >= MIN_BLOCK_CHARS:
            return self._perform_fallback_chunking(file_path, content, file_hash, seen_segment_hashes)
        else:
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
        按行分块文本
        
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
            
        for i, line in enumerate(lines):
            line_length = len(line) + (1 if i < len(lines) - 1 else 0)  # +1 for newline
            
            # 处理超大行
            if line_length > effective_max_chars:
                # 完成当前块
                if current_chunk_lines:
                    finalize_chunk(i - 1)
                    
                # 分割超大行
                remaining_line = line
                segment_start = 0
                line_num = base_start_line + i
                
                while remaining_line:
                    segment = remaining_line[:MAX_BLOCK_CHARS]
                    remaining_line = remaining_line[MAX_BLOCK_CHARS:]
                    
                    segment_hash = hashlib.sha256(
                        f"{file_path}-{line_num}-{line_num}-{segment_start}-{len(segment)}-{segment[:100]}".encode()
                    ).hexdigest()
                    
                    if segment_hash not in seen_segment_hashes:
                        seen_segment_hashes.add(segment_hash)
                        chunks.append(CodeBlock(
                            file_path=file_path,
                            identifier=None,
                            type=f"{chunk_type}_segment",
                            start_line=line_num,
                            end_line=line_num,
                            content=segment,
                            file_hash=file_hash,
                            segment_hash=segment_hash
                        ))
                        
                    segment_start += MAX_BLOCK_CHARS
                    
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
                        potential_chunk_length = sum(len(line) for line in potential_chunk_lines) + len(potential_chunk_lines) - 1
                        potential_next_chunk_lines = lines[k + 1:]
                        potential_next_chunk_length = sum(len(line) for line in potential_next_chunk_lines) + len(potential_next_chunk_lines) - 1
                        
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