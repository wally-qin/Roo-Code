"""
OpenAI嵌入器实现

基于原TypeScript项目的OpenAiEmbedder类重新实现，
支持批处理、速率限制和重试机制。
"""

import asyncio
import logging
import math
from typing import List, Optional, Dict, Any
import openai
from openai import OpenAI

from ..interfaces import IEmbedder, EmbeddingResponse
from ..constants import (
    MAX_BATCH_TOKENS, MAX_ITEM_TOKENS, MAX_BATCH_RETRIES,
    INITIAL_RETRY_DELAY_MS, EMBEDDING_MODELS
)

logger = logging.getLogger(__name__)


class OpenAIEmbedder(IEmbedder):
    """OpenAI嵌入器实现"""
    
    def __init__(self, api_key: str, model_id: Optional[str] = None):
        """
        初始化OpenAI嵌入器
        
        Args:
            api_key: OpenAI API密钥
            model_id: 可选的模型ID，默认使用text-embedding-3-small
        """
        self.api_key = api_key
        self.default_model_id = model_id or "text-embedding-3-small"
        self.client = OpenAI(api_key=api_key)
        
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
        usage = {"prompt_tokens": 0, "total_tokens": 0}
        remaining_texts = list(processed_texts)
        
        while remaining_texts:
            current_batch: List[str] = []
            current_batch_tokens = 0
            processed_indices: List[int] = []
            
            # 构建当前批次
            for i, text in enumerate(remaining_texts):
                item_tokens = math.ceil(len(text) / 4)  # 估算token数
                
                if item_tokens > MAX_ITEM_TOKENS:
                    logger.warning(f"文本超过最大token限制: {item_tokens} > {MAX_ITEM_TOKENS}")
                    processed_indices.append(i)
                    continue
                    
                if current_batch_tokens + item_tokens <= MAX_BATCH_TOKENS:
                    current_batch.append(text)
                    current_batch_tokens += item_tokens
                    processed_indices.append(i)
                else:
                    break
                    
            # 移除已处理的文本
            for i in reversed(processed_indices):
                remaining_texts.pop(i)
                
            # 处理当前批次
            if current_batch:
                batch_result = await self._embed_batch_with_retries(current_batch, model_to_use)
                all_embeddings.extend(batch_result.embeddings)
                if batch_result.usage:
                    usage["prompt_tokens"] += batch_result.usage.get("prompt_tokens", 0)
                    usage["total_tokens"] += batch_result.usage.get("total_tokens", 0)
                    
        return EmbeddingResponse(embeddings=all_embeddings, usage=usage)
        
    def _get_model_query_prefix(self, model_id: str) -> Optional[str]:
        """获取模型特定的查询前缀"""
        # 根据模型返回适当的前缀，这里简化处理
        if "3-small" in model_id or "3-large" in model_id:
            return None  # 新模型不需要前缀
        return None
        
    def _apply_query_prefix(self, texts: List[str], query_prefix: Optional[str]) -> List[str]:
        """应用查询前缀到文本"""
        if not query_prefix:
            return texts
            
        processed_texts = []
        for i, text in enumerate(texts):
            if text.startswith(query_prefix):
                processed_texts.append(text)
            else:
                prefixed_text = f"{query_prefix}{text}"
                estimated_tokens = math.ceil(len(prefixed_text) / 4)
                
                if estimated_tokens > MAX_ITEM_TOKENS:
                    logger.warning(f"添加前缀后文本超过token限制，使用原文本: {estimated_tokens} > {MAX_ITEM_TOKENS}")
                    processed_texts.append(text)
                else:
                    processed_texts.append(prefixed_text)
                    
        return processed_texts
        
    async def _embed_batch_with_retries(self, batch_texts: List[str], model: str) -> EmbeddingResponse:
        """
        带重试的批量嵌入处理
        
        Args:
            batch_texts: 批量文本
            model: 模型ID
            
        Returns:
            嵌入响应
        """
        for attempt in range(MAX_BATCH_RETRIES):
            try:
                response = await asyncio.to_thread(
                    self.client.embeddings.create,
                    input=batch_texts,
                    model=model
                )
                
                return EmbeddingResponse(
                    embeddings=[item.embedding for item in response.data],
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                    }
                )
                
            except Exception as e:
                has_more_attempts = attempt < MAX_BATCH_RETRIES - 1
                
                # 检查是否是速率限制错误
                if self._is_rate_limit_error(e) and has_more_attempts:
                    delay_ms = INITIAL_RETRY_DELAY_MS * (2 ** attempt)
                    logger.warning(f"速率限制，等待 {delay_ms}ms 后重试 (尝试 {attempt + 1}/{MAX_BATCH_RETRIES})")
                    await asyncio.sleep(delay_ms / 1000)
                    continue
                    
                logger.error(f"OpenAI嵌入器错误 (尝试 {attempt + 1}/{MAX_BATCH_RETRIES}): {e}")
                
                if not has_more_attempts:
                    raise self._format_embedding_error(e)
                    
        raise Exception(f"经过 {MAX_BATCH_RETRIES} 次尝试后失败")
        
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """检查是否是速率限制错误"""
        if hasattr(error, 'status_code'):
            return error.status_code == 429
        return "rate" in str(error).lower() and "limit" in str(error).lower()
        
    def _format_embedding_error(self, error: Exception) -> Exception:
        """格式化嵌入错误"""
        if hasattr(error, 'status_code'):
            if error.status_code == 401:
                return Exception("OpenAI API密钥无效或未授权")
            elif error.status_code == 429:
                return Exception("OpenAI API速率限制，请稍后重试")
            elif error.status_code == 500:
                return Exception("OpenAI服务器内部错误")
                
        return Exception(f"OpenAI嵌入错误: {str(error)}")
        
    async def validate_configuration(self) -> Dict[str, Any]:
        """
        验证OpenAI嵌入器配置
        
        Returns:
            验证结果字典
        """
        try:
            # 使用最小文本测试嵌入请求
            response = await asyncio.to_thread(
                self.client.embeddings.create,
                input=["test"],
                model=self.default_model_id
            )
            
            # 检查响应是否有效
            if not response.data or len(response.data) == 0:
                return {
                    "valid": False,
                    "error": "OpenAI返回无效响应格式"
                }
                
            return {"valid": True}
            
        except Exception as e:
            error_msg = self._format_embedding_error(e)
            return {
                "valid": False,
                "error": str(error_msg)
            }
            
    @property
    def embedder_info(self) -> Dict[str, str]:
        """获取嵌入器信息"""
        return {"name": "openai"}
        
    def get_model_dimension(self) -> int:
        """获取当前模型的向量维度"""
        model_config = EMBEDDING_MODELS.get("openai", {}).get(self.default_model_id)
        if model_config:
            return model_config["dimension"]
        return 1536  # 默认维度