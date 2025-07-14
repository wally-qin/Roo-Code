"""
嵌入器模块

包含各种嵌入器实现，支持OpenAI、Ollama、Gemini和OpenAI兼容的API。
"""

from .openai_embedder import OpenAIEmbedder
from .ollama_embedder import OllamaEmbedder
from .gemini_embedder import GeminiEmbedder
from .openai_compatible_embedder import OpenAICompatibleEmbedder

__all__ = [
    'OpenAIEmbedder',
    'OllamaEmbedder', 
    'GeminiEmbedder',
    'OpenAICompatibleEmbedder'
]