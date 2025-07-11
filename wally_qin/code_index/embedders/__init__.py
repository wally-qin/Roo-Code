"""嵌入器模块

包含多种AI模型的嵌入器实现，支持OpenAI、Ollama、OpenAI Compatible和Gemini。
"""

from .openai_embedder import OpenAIEmbedder
from .ollama_embedder import OllamaEmbedder

__all__ = ["OpenAIEmbedder", "OllamaEmbedder"]