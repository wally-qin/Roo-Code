"""
Ollama嵌入器实现

基于原TypeScript项目的Ollama嵌入器重新实现，
支持本地Ollama服务的嵌入功能。
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
import aiohttp

from ..interfaces import IEmbedder, EmbeddingResponse

logger = logging.getLogger(__name__)


class OllamaEmbedder(IEmbedder):
    """Ollama嵌入器实现"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model_id: Optional[str] = None):
        """
        初始化Ollama嵌入器
        
        Args:
            base_url: Ollama服务器基础URL
            model_id: 可选的模型ID，默认使用nomic-embed-text
        """
        self.base_url = base_url.rstrip('/')
        self.default_model_id = model_id or "nomic-embed-text"
        
    async def create_embeddings(self, texts: List[str], model: Optional[str] = None) -> EmbeddingResponse:
        """
        创建文本嵌入
        
        Args:
            texts: 要嵌入的文本列表
            model: 可选的模型ID
            
        Returns:
            嵌入响应对象
        """
        model_to_use = model or self.default_model_id
        embeddings = []
        
        async with aiohttp.ClientSession() as session:
            for text in texts:
                try:
                    async with session.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": model_to_use,
                            "prompt": text
                        }
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            embeddings.append(result.get("embedding", []))
                        else:
                            logger.error(f"Ollama嵌入请求失败: {response.status}")
                            raise Exception(f"Ollama API错误: {response.status}")
                            
                except Exception as e:
                    logger.error(f"Ollama嵌入错误: {e}")
                    raise
                    
        return EmbeddingResponse(embeddings=embeddings)
        
    async def validate_configuration(self) -> Dict[str, Any]:
        """
        验证Ollama嵌入器配置
        
        Returns:
            验证结果字典
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.default_model_id,
                        "prompt": "test"
                    }
                ) as response:
                    if response.status == 200:
                        return {"valid": True}
                    else:
                        return {
                            "valid": False,
                            "error": f"Ollama连接失败: HTTP {response.status}"
                        }
                        
        except Exception as e:
            return {
                "valid": False,
                "error": f"Ollama连接错误: {str(e)}"
            }
            
    @property
    def embedder_info(self) -> Dict[str, str]:
        """获取嵌入器信息"""
        return {"name": "ollama"}