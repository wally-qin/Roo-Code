"""
代码索引搜索服务

提供代码搜索功能，包括文本嵌入生成、向量搜索和结果处理。
基于原TypeScript项目的搜索功能重新实现。
"""

import asyncio
from typing import List, Optional, Dict, Any
import logging

from .interfaces import (
    IEmbedder, IVectorStore, VectorStoreSearchResult, 
    IndexingState, EmbeddingResponse
)
from .managers.config_manager import CodeIndexConfigManager
from .managers.state_manager import CodeIndexStateManager

logger = logging.getLogger(__name__)


class CodeIndexSearchService:
    """代码索引搜索服务"""
    
    def __init__(self, config_manager: CodeIndexConfigManager,
                 state_manager: CodeIndexStateManager,
                 embedder: IEmbedder,
                 vector_store: IVectorStore):
        """
        初始化搜索服务
        
        Args:
            config_manager: 配置管理器
            state_manager: 状态管理器
            embedder: 嵌入器
            vector_store: 向量存储
        """
        self.config_manager = config_manager
        self.state_manager = state_manager
        self.embedder = embedder
        self.vector_store = vector_store
        
    async def search_index(self, query: str, directory_prefix: Optional[str] = None) -> List[VectorStoreSearchResult]:
        """
        搜索代码索引
        
        Args:
            query: 搜索查询字符串
            directory_prefix: 可选的目录前缀过滤
            
        Returns:
            搜索结果列表
        """
        if not query or not query.strip():
            return []
            
        # 检查系统状态
        if self.state_manager.current_state == IndexingState.ERROR:
            logger.warning("系统处于错误状态，无法执行搜索")
            return []
            
        try:
            # 1. 生成查询的嵌入向量
            query_vector = await self._generate_query_embedding(query)
            if not query_vector:
                return []
                
            # 2. 执行向量搜索
            results = await self._perform_vector_search(
                query_vector, 
                directory_prefix
            )
            
            # 3. 后处理搜索结果
            processed_results = self._process_search_results(results, query)
            
            logger.info(f"搜索查询 '{query}' 返回 {len(processed_results)} 个结果")
            return processed_results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
            
    async def _generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        生成查询的嵌入向量
        
        Args:
            query: 查询字符串
            
        Returns:
            嵌入向量或None
        """
        try:
            # 使用嵌入器生成向量
            embedding_response = await self.embedder.create_embeddings([query])
            
            if not embedding_response.embeddings or not embedding_response.embeddings[0]:
                logger.error("生成嵌入向量失败：返回空向量")
                return None
                
            return embedding_response.embeddings[0]
            
        except Exception as e:
            logger.error(f"生成查询嵌入向量失败: {e}")
            return None
            
    async def _perform_vector_search(self, query_vector: List[float], 
                                   directory_prefix: Optional[str] = None) -> List[VectorStoreSearchResult]:
        """
        执行向量搜索
        
        Args:
            query_vector: 查询向量
            directory_prefix: 可选的目录前缀过滤
            
        Returns:
            搜索结果列表
        """
        try:
            config = self.config_manager.get_config()
            
            # 获取搜索参数
            min_score = config.search_min_score
            max_results = config.search_max_results
            
            # 执行搜索
            results = await self.vector_store.search(
                query_vector=query_vector,
                directory_prefix=directory_prefix,
                min_score=min_score,
                max_results=max_results
            )
            
            return results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
            
    def _process_search_results(self, results: List[VectorStoreSearchResult], 
                              query: str) -> List[VectorStoreSearchResult]:
        """
        后处理搜索结果
        
        Args:
            results: 原始搜索结果
            query: 原始查询字符串
            
        Returns:
            处理后的搜索结果
        """
        try:
            # 过滤无效结果
            valid_results = []
            for result in results:
                if self._is_valid_result(result):
                    valid_results.append(result)
                    
            # 按相似度分数排序（降序）
            valid_results.sort(key=lambda x: x.score, reverse=True)
            
            # 增强结果信息
            enhanced_results = []
            for result in valid_results:
                enhanced_result = self._enhance_result(result, query)
                enhanced_results.append(enhanced_result)
                
            return enhanced_results
            
        except Exception as e:
            logger.error(f"处理搜索结果失败: {e}")
            return results  # 返回原始结果
            
    def _is_valid_result(self, result: VectorStoreSearchResult) -> bool:
        """
        检查搜索结果是否有效
        
        Args:
            result: 搜索结果
            
        Returns:
            是否有效
        """
        if not result.payload:
            return False
            
        # 检查必要字段
        required_fields = ["filePath", "codeChunk", "startLine", "endLine"]
        for field in required_fields:
            if field not in result.payload:
                return False
                
        # 检查文件路径是否有效
        file_path = result.payload.get("filePath", "")
        if not file_path or not isinstance(file_path, str):
            return False
            
        # 检查代码块是否有效
        code_chunk = result.payload.get("codeChunk", "")
        if not code_chunk or not isinstance(code_chunk, str):
            return False
            
        return True
        
    def _enhance_result(self, result: VectorStoreSearchResult, 
                       query: str) -> VectorStoreSearchResult:
        """
        增强搜索结果信息
        
        Args:
            result: 原始搜索结果
            query: 查询字符串
            
        Returns:
            增强后的搜索结果
        """
        try:
            enhanced_payload = dict(result.payload)
            
            # 添加查询匹配信息
            enhanced_payload["query"] = query
            enhanced_payload["matchScore"] = result.score
            
            # 计算代码块行数
            start_line = enhanced_payload.get("startLine", 0)
            end_line = enhanced_payload.get("endLine", 0)
            enhanced_payload["lineCount"] = max(0, end_line - start_line + 1)
            
            # 添加文件信息
            file_path = enhanced_payload.get("filePath", "")
            if file_path:
                enhanced_payload["fileName"] = file_path.split("/")[-1]
                enhanced_payload["fileExtension"] = self._get_file_extension(file_path)
                
            # 截断过长的代码块用于显示
            code_chunk = enhanced_payload.get("codeChunk", "")
            if len(code_chunk) > 500:
                enhanced_payload["codeChunkPreview"] = code_chunk[:500] + "..."
            else:
                enhanced_payload["codeChunkPreview"] = code_chunk
                
            return VectorStoreSearchResult(
                id=result.id,
                score=result.score,
                payload=enhanced_payload
            )
            
        except Exception as e:
            logger.error(f"增强搜索结果失败: {e}")
            return result
            
    def _get_file_extension(self, file_path: str) -> str:
        """
        获取文件扩展名
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件扩展名
        """
        try:
            if "." in file_path:
                return file_path.split(".")[-1].lower()
            return ""
        except:
            return ""
            
    async def get_search_statistics(self) -> Dict[str, Any]:
        """
        获取搜索统计信息
        
        Returns:
            统计信息字典
        """
        try:
            # 检查向量存储状态
            collection_exists = await self.vector_store.collection_exists()
            
            config = self.config_manager.get_config()
            embedder_info = self.embedder.embedder_info
            
            return {
                "collection_exists": collection_exists,
                "embedder_provider": config.embedder_provider.value,
                "embedder_model": config.model_id,
                "embedder_info": embedder_info,
                "search_config": {
                    "min_score": config.search_min_score,
                    "max_results": config.search_max_results
                },
                "vector_store_type": type(self.vector_store).__name__
            }
            
        except Exception as e:
            logger.error(f"获取搜索统计信息失败: {e}")
            return {"error": str(e)}
            
    async def validate_search_capability(self) -> Dict[str, Any]:
        """
        验证搜索能力
        
        Returns:
            验证结果
        """
        validation_result = {
            "embedder_valid": False,
            "vector_store_valid": False,
            "search_ready": False,
            "errors": []
        }
        
        try:
            # 验证嵌入器
            embedder_validation = await self.embedder.validate_configuration()
            validation_result["embedder_valid"] = embedder_validation.get("valid", False)
            if not validation_result["embedder_valid"]:
                validation_result["errors"].append(
                    f"嵌入器验证失败: {embedder_validation.get('error', '未知错误')}"
                )
                
            # 验证向量存储
            try:
                collection_exists = await self.vector_store.collection_exists()
                validation_result["vector_store_valid"] = True
                validation_result["collection_exists"] = collection_exists
            except Exception as e:
                validation_result["vector_store_valid"] = False
                validation_result["errors"].append(f"向量存储验证失败: {e}")
                
            # 综合判断搜索就绪状态
            validation_result["search_ready"] = (
                validation_result["embedder_valid"] and 
                validation_result["vector_store_valid"]
            )
            
        except Exception as e:
            validation_result["errors"].append(f"验证过程失败: {e}")
            
        return validation_result
        
    async def perform_test_search(self, test_query: str = "function") -> Dict[str, Any]:
        """
        执行测试搜索
        
        Args:
            test_query: 测试查询字符串
            
        Returns:
            测试结果
        """
        test_result = {
            "success": False,
            "query": test_query,
            "result_count": 0,
            "execution_time": 0,
            "error": None
        }
        
        try:
            import time
            start_time = time.time()
            
            # 执行搜索
            results = await self.search_index(test_query)
            
            execution_time = time.time() - start_time
            
            test_result.update({
                "success": True,
                "result_count": len(results),
                "execution_time": execution_time,
                "sample_results": [
                    {
                        "id": result.id,
                        "score": result.score,
                        "file_path": result.payload.get("filePath", ""),
                        "start_line": result.payload.get("startLine", 0)
                    }
                    for result in results[:3]  # 返回前3个结果作为样本
                ]
            })
            
        except Exception as e:
            test_result["error"] = str(e)
            logger.error(f"测试搜索失败: {e}")
            
        return test_result