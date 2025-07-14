"""
OpenAI兼容嵌入器实现

基于原TypeScript项目的OpenAICompatibleEmbedder类重新实现，
支持任何兼容OpenAI API的端点，具有批处理和速率限制功能。
"""

import asyncio
import logging
import math
from typing import List, Optional, Dict, Any
import openai
from openai import OpenAI
import requests
import json

from ..interfaces import IEmbedder, EmbeddingResponse
from ..constants import (
    MAX_BATCH_TOKENS, MAX_ITEM_TOKENS, MAX_BATCH_RETRIES,
    INITIAL_RETRY_DELAY_MS, EMBEDDING_MODELS
)

logger = logging.getLogger(__name__)


class OpenAICompatibleEmbedder(IEmbedder):
    """OpenAI兼容嵌入器实现"""
    
    def __init__(self, base_url: str, api_key: str, 
                 model_id: Optional[str] = None, 
                 max_item_tokens: Optional[int] = None):
        """
        初始化OpenAI兼容嵌入器
        
        Args:
            base_url: API基础URL
            api_key: API密钥
            model_id: 可选的模型ID，默认使用text-embedding-3-small
            max_item_tokens: 可选的每项最大令牌数
        """
        if not base_url:
            raise ValueError("base_url不能为空")
        if not api_key:
            raise ValueError("api_key不能为空")
            
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.default_model_id = model_id or "text-embedding-3-small"
        self.max_item_tokens = max_item_tokens or MAX_ITEM_TOKENS
        
        # 创建OpenAI客户端
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        
        # 检查是否是完整端点URL
        self.is_full_url = self._is_full_endpoint_url(base_url)
        
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """
        创建文本嵌入，支持批处理和速率限制
        
        Args:
            texts: 要嵌入的文本列表
            model: 可选的模型ID
            
        Returns:
            嵌入响应对象
        """
        model_to_use = model or self.default_model_id
        
        # 应用模型特定的查询前缀（如果需要）
        query_prefix = self._get_model_query_prefix(model_to_use)
        processed_texts = self._apply_query_prefix(texts, query_prefix)
        
        all_embeddings: List[List[float]] = []
        total_prompt_tokens = 0
        total_tokens = 0
        
        # 按批次处理以避免超过最大令牌数
        batch_size = self._calculate_batch_size(processed_texts)
        
        for i in range(0, len(processed_texts), batch_size):
            batch_texts = processed_texts[i:i + batch_size]
            
            try:
                batch_result = await self._embed_batch_with_retries(batch_texts, model_to_use)
                all_embeddings.extend(batch_result['embeddings'])
                total_prompt_tokens += batch_result['usage']['prompt_tokens']
                total_tokens += batch_result['usage']['total_tokens']
                
            except Exception as error:
                logger.error(f"批次嵌入失败: {error}")
                raise self._format_embedding_error(error)
                
        return EmbeddingResponse(
            embeddings=all_embeddings,
            usage={
                'prompt_tokens': total_prompt_tokens,
                'total_tokens': total_tokens
            }
        )
        
    def _get_model_query_prefix(self, model_id: str) -> Optional[str]:
        """获取模型特定的查询前缀"""
        # 根据模型返回前缀，这里可以根据需要扩展
        prefixes = {
            "text-embedding-3-small": "search_query: ",
            "text-embedding-3-large": "search_query: ",
        }
        return prefixes.get(model_id)
        
    def _apply_query_prefix(self, texts: List[str], query_prefix: Optional[str]) -> List[str]:
        """应用查询前缀到文本"""
        if not query_prefix:
            return texts
            
        processed_texts = []
        for i, text in enumerate(texts):
            # 防止重复添加前缀
            if text.startswith(query_prefix):
                processed_texts.append(text)
                continue
                
            prefixed_text = f"{query_prefix}{text}"
            estimated_tokens = math.ceil(len(prefixed_text) / 4)
            
            if estimated_tokens > self.max_item_tokens:
                logger.warning(
                    f"文本 {i} 添加前缀后超过令牌限制 "
                    f"({estimated_tokens} > {self.max_item_tokens})，使用原始文本"
                )
                processed_texts.append(text)
            else:
                processed_texts.append(prefixed_text)
                
        return processed_texts
        
    def _calculate_batch_size(self, texts: List[str]) -> int:
        """计算批次大小以避免超过令牌限制"""
        if not texts:
            return 0
            
        # 估算每个文本的平均令牌数
        avg_text_length = sum(len(text) for text in texts) / len(texts)
        estimated_tokens_per_text = math.ceil(avg_text_length / 4)
        
        # 计算批次大小
        batch_size = min(
            len(texts),
            max(1, MAX_BATCH_TOKENS // max(1, estimated_tokens_per_text))
        )
        
        return batch_size
        
    def _is_full_endpoint_url(self, url: str) -> bool:
        """检查URL是否是完整的端点URL"""
        # 如果URL包含/embeddings路径，则认为是完整端点
        return '/embeddings' in url.lower()
        
    async def _make_direct_embedding_request(self, url: str, batch_texts: List[str], model: str) -> Dict[str, Any]:
        """对完整端点URL进行直接嵌入请求"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'input': batch_texts,
            'model': model
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        return response.json()
        
    async def _embed_batch_with_retries(self, batch_texts: List[str], model: str) -> Dict[str, Any]:
        """使用重试机制嵌入批次"""
        last_error = None
        
        for attempt in range(MAX_BATCH_RETRIES):
            try:
                if self.is_full_url:
                    # 使用直接HTTP请求
                    response_data = await self._make_direct_embedding_request(
                        self.base_url, batch_texts, model
                    )
                else:
                    # 使用OpenAI客户端
                    response = self.client.embeddings.create(
                        input=batch_texts,
                        model=model
                    )
                    response_data = response.model_dump()
                    
                # 提取嵌入向量
                embeddings = []
                for item in response_data['data']:
                    if isinstance(item['embedding'], list):
                        embeddings.append(item['embedding'])
                    else:
                        # 处理字符串形式的嵌入（如果有的话）
                        embeddings.append(json.loads(item['embedding']))
                        
                # 提取使用信息
                usage = response_data.get('usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                total_tokens = usage.get('total_tokens', prompt_tokens)
                
                return {
                    'embeddings': embeddings,
                    'usage': {
                        'prompt_tokens': prompt_tokens,
                        'total_tokens': total_tokens
                    }
                }
                
            except Exception as error:
                last_error = error
                
                if attempt < MAX_BATCH_RETRIES - 1:
                    # 检查是否是速率限制错误
                    if self._is_rate_limit_error(error):
                        delay = INITIAL_RETRY_DELAY_MS * (2 ** attempt) / 1000
                        logger.warning(f"速率限制，{delay}s后重试 (尝试 {attempt + 1}/{MAX_BATCH_RETRIES})")
                        await asyncio.sleep(delay)
                    else:
                        # 非速率限制错误，立即重试
                        logger.warning(f"嵌入请求失败，重试 (尝试 {attempt + 1}/{MAX_BATCH_RETRIES}): {error}")
                        await asyncio.sleep(0.5)
                else:
                    logger.error(f"嵌入批次最终失败: {error}")
                    
        raise last_error or Exception("嵌入批次处理失败")
        
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """检查是否是速率限制错误"""
        error_str = str(error).lower()
        return (
            'rate limit' in error_str or
            'too many requests' in error_str or
            '429' in error_str or
            'quota' in error_str
        )
        
    def _format_embedding_error(self, error: Exception) -> Exception:
        """格式化嵌入错误"""
        error_str = str(error)
        
        if 'rate limit' in error_str.lower():
            return Exception(f"速率限制错误: {error_str}")
        elif 'authentication' in error_str.lower():
            return Exception(f"认证错误: {error_str}")
        elif 'model' in error_str.lower() and 'not found' in error_str.lower():
            return Exception(f"模型不存在: {error_str}")
        else:
            return Exception(f"嵌入生成错误: {error_str}")
            
    async def validate_configuration(self) -> Dict[str, Any]:
        """验证配置"""
        try:
            # 使用简单测试文本验证配置
            test_text = "test"
            result = await self.create_embeddings([test_text])
            
            if result.embeddings and len(result.embeddings[0]) > 0:
                return {
                    'valid': True,
                    'dimension': len(result.embeddings[0]),
                    'model': self.default_model_id
                }
            else:
                return {
                    'valid': False,
                    'error': '嵌入响应为空'
                }
                
        except Exception as error:
            return {
                'valid': False,
                'error': str(error)
            }
            
    @property
    def embedder_info(self) -> Dict[str, str]:
        """返回嵌入器信息"""
        return {
            'name': 'openai-compatible',
            'base_url': self.base_url,
            'model': self.default_model_id
        }
        
    def get_model_dimension(self) -> int:
        """获取模型维度"""
        # 根据模型返回维度，这里可以根据需要扩展
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            "text-embedding-004": 768,  # Gemini
        }
        return dimensions.get(self.default_model_id, 1536)