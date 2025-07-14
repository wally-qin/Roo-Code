"""
Gemini嵌入器实现

基于原TypeScript项目的GeminiEmbedder类重新实现，
作为OpenAI兼容嵌入器的包装器，使用固定的Gemini API配置。
"""

from typing import List, Optional, Dict, Any

from ..interfaces import IEmbedder, EmbeddingResponse
from ..constants import GEMINI_MAX_ITEM_TOKENS
from .openai_compatible_embedder import OpenAICompatibleEmbedder


class GeminiEmbedder(IEmbedder):
    """
    Gemini嵌入器实现，包装OpenAI兼容嵌入器
    使用固定的Google Gemini嵌入API配置。
    
    固定值:
    - Base URL: https://generativelanguage.googleapis.com/v1beta/openai/
    - Model: text-embedding-004
    - Dimension: 768
    """
    
    # Gemini API 常量
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL = "text-embedding-004"
    GEMINI_DIMENSION = 768
    
    def __init__(self, api_key: str):
        """
        创建新的Gemini嵌入器
        
        Args:
            api_key: Gemini API密钥用于认证
        """
        if not api_key:
            raise ValueError("API密钥是必需的")
            
        # 创建带有Gemini固定配置的OpenAI兼容嵌入器
        self.openai_compatible_embedder = OpenAICompatibleEmbedder(
            base_url=self.GEMINI_BASE_URL,
            api_key=api_key,
            model_id=self.GEMINI_MODEL,
            max_item_tokens=GEMINI_MAX_ITEM_TOKENS
        )
        
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """
        使用Gemini嵌入API为给定文本创建嵌入
        
        Args:
            texts: 要嵌入的文本字符串数组
            model: 可选的模型标识符（被忽略 - 始终使用text-embedding-004）
            
        Returns:
            解析为嵌入响应的Promise
        """
        # 始终使用固定的Gemini模型，忽略任何传递的模型参数
        return await self.openai_compatible_embedder.create_embeddings(texts, self.GEMINI_MODEL)
        
    async def validate_configuration(self) -> Dict[str, Any]:
        """
        通过委托给底层OpenAI兼容嵌入器来验证Gemini嵌入器配置
        
        Returns:
            包含成功状态和可选错误消息的验证结果Promise
        """
        # 委托验证给OpenAI兼容嵌入器
        # 错误消息将特定于Gemini，因为我们使用的是Gemini的基础URL
        return await self.openai_compatible_embedder.validate_configuration()
        
    @property
    def embedder_info(self) -> Dict[str, str]:
        """返回此嵌入器的信息"""
        return {
            "name": "gemini",
            "base_url": self.GEMINI_BASE_URL,
            "model": self.GEMINI_MODEL
        }
        
    @classmethod
    def get_dimension(cls) -> int:
        """获取Gemini嵌入的固定维度"""
        return cls.GEMINI_DIMENSION
        
    def get_model_dimension(self) -> int:
        """获取当前模型的维度"""
        return self.GEMINI_DIMENSION