"""
Qdrant向量存储客户端实现

基于原TypeScript项目的QdrantVectorStore类重新实现，
提供完整的向量存储功能包括初始化、搜索、插入和删除操作。
"""

import asyncio
import hashlib
import os
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urlparse
import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, CreateCollection, PointStruct as QdrantPoint

from ..interfaces import IVectorStore, PointStruct, VectorStoreSearchResult
from ..constants import DEFAULT_SEARCH_MIN_SCORE, DEFAULT_MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)


class QdrantVectorStore(IVectorStore):
    """Qdrant向量存储实现"""
    
    def __init__(self, workspace_path: str, url: str, vector_size: int, api_key: Optional[str] = None):
        """
        初始化Qdrant向量存储
        
        Args:
            workspace_path: 工作空间路径
            url: Qdrant服务器URL
            vector_size: 向量维度
            api_key: 可选的API密钥
        """
        self.workspace_path = workspace_path
        self.vector_size = vector_size
        self.distance_metric = Distance.COSINE
        self.qdrant_url = self._parse_qdrant_url(url)
        
        # 基于工作空间路径生成集合名称
        hash_obj = hashlib.sha256(workspace_path.encode())
        self.collection_name = f"ws-{hash_obj.hexdigest()[:16]}"
        
        # 初始化Qdrant客户端
        self.client = self._create_client(self.qdrant_url, api_key)
        
    def _parse_qdrant_url(self, url: Optional[str]) -> str:
        """解析和规范化Qdrant服务器URL"""
        if not url or not url.strip():
            return "http://localhost:6333"
            
        trimmed_url = url.strip()
        
        # 检查是否包含协议
        if not trimmed_url.startswith(("http://", "https://")) and "://" not in trimmed_url:
            return self._parse_hostname(trimmed_url)
            
        try:
            parsed = urlparse(trimmed_url)
            return trimmed_url
        except Exception:
            return self._parse_hostname(trimmed_url)
            
    def _parse_hostname(self, hostname: str) -> str:
        """处理仅有主机名的输入"""
        if ":" in hostname:
            return hostname if hostname.startswith("http") else f"http://{hostname}"
        else:
            return f"http://{hostname}"
            
    def _create_client(self, url: str, api_key: Optional[str]) -> QdrantClient:
        """创建Qdrant客户端"""
        try:
            parsed_url = urlparse(url)
            
            # 确定端口和协议
            if parsed_url.port:
                port = parsed_url.port
                use_https = parsed_url.scheme == "https"
            else:
                if parsed_url.scheme == "https":
                    port = 443
                    use_https = True
                else:
                    port = 80
                    use_https = False
                    
            # 构建客户端配置
            client_config = {
                "host": parsed_url.hostname,
                "port": port,
                "https": use_https,
            }
            
            if api_key:
                client_config["api_key"] = api_key
                
            if parsed_url.path and parsed_url.path != "/":
                client_config["prefix"] = parsed_url.path.rstrip("/")
                
            return QdrantClient(**client_config)
            
        except Exception as e:
            logger.warning(f"URL解析失败，使用fallback配置: {e}")
            # Fallback配置
            client_config = {"url": url}
            if api_key:
                client_config["api_key"] = api_key
            return QdrantClient(**client_config)
            
    async def _get_collection_info(self) -> Optional[models.CollectionInfo]:
        """获取集合信息"""
        try:
            return await asyncio.to_thread(self.client.get_collection, self.collection_name)
        except Exception as e:
            logger.warning(f"获取集合信息失败: {e}")
            return None
            
    async def initialize(self) -> bool:
        """
        初始化向量存储
        
        Returns:
            bool: 是否创建了新集合
        """
        created = False
        
        try:
            collection_info = await self._get_collection_info()
            
            if collection_info is None:
                # 集合不存在，创建新集合
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=self.distance_metric
                    )
                )
                created = True
                logger.info(f"创建新集合: {self.collection_name}")
                
            else:
                # 集合存在，检查向量维度
                existing_vector_size = collection_info.config.params.vectors.size
                if existing_vector_size == self.vector_size:
                    created = False
                    logger.info(f"集合已存在且配置正确: {self.collection_name}")
                else:
                    # 维度不匹配，重新创建集合
                    logger.warning(f"集合 {self.collection_name} 向量维度不匹配 "
                                 f"(现有: {existing_vector_size}, 期望: {self.vector_size})，重新创建")
                    
                    try:
                        await asyncio.to_thread(self.client.delete_collection, self.collection_name)
                        await asyncio.to_thread(
                            self.client.create_collection,
                            collection_name=self.collection_name,
                            vectors_config=VectorParams(
                                size=self.vector_size,
                                distance=self.distance_metric
                            )
                        )
                        created = True
                        logger.info(f"重新创建集合: {self.collection_name}")
                        
                    except Exception as recreate_error:
                        error_msg = f"重新创建集合失败: {recreate_error}"
                        logger.error(error_msg)
                        raise Exception(f"向量维度不匹配错误: {error_msg}")
                        
            # 创建负载索引
            await self._create_payload_indexes()
            return created
            
        except Exception as e:
            error_msg = f"初始化Qdrant集合 '{self.collection_name}' 失败: {e}"
            logger.error(error_msg)
            raise Exception(f"Qdrant连接失败: {self.qdrant_url}, 错误: {error_msg}")
            
    async def _create_payload_indexes(self) -> None:
        """创建负载索引以优化搜索性能"""
        for i in range(5):
            try:
                await asyncio.to_thread(
                    self.client.create_payload_index,
                    collection_name=self.collection_name,
                    field_name=f"pathSegments.{i}",
                    field_schema=models.PayloadSchemaType.KEYWORD
                )
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"创建负载索引 pathSegments.{i} 失败: {e}")
                    
    async def upsert_points(self, points: List[PointStruct]) -> None:
        """
        插入或更新向量点
        
        Args:
            points: 要插入的向量点列表
        """
        try:
            # 转换为Qdrant格式并添加路径分段
            processed_points = []
            for point in points:
                payload = dict(point.payload)
                
                # 添加路径分段用于过滤
                if "filePath" in payload:
                    segments = payload["filePath"].split(os.sep)
                    segments = [seg for seg in segments if seg]  # 过滤空字符串
                    path_segments = {str(i): segments[i] for i in range(min(len(segments), 5))}
                    payload["pathSegments"] = path_segments
                    
                processed_points.append(
                    QdrantPoint(
                        id=point.id,
                        vector=point.vector,
                        payload=payload
                    )
                )
                
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.collection_name,
                points=processed_points,
                wait=True
            )
            
        except Exception as e:
            logger.error(f"插入向量点失败: {e}")
            raise
            
    def _is_payload_valid(self, payload: Optional[Dict[str, Any]]) -> bool:
        """检查负载是否有效"""
        if not payload:
            return False
        required_keys = ["filePath", "codeChunk", "startLine", "endLine"]
        return all(key in payload for key in required_keys)
        
    async def search(self, query_vector: List[float], directory_prefix: Optional[str] = None,
                    min_score: Optional[float] = None, max_results: Optional[int] = None) -> List[VectorStoreSearchResult]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量
            directory_prefix: 可选的目录前缀过滤
            min_score: 可选的最小相似度阈值
            max_results: 可选的最大结果数量
            
        Returns:
            搜索结果列表
        """
        try:
            # 构建过滤条件
            filter_condition = None
            if directory_prefix:
                segments = directory_prefix.split(os.sep)
                segments = [seg for seg in segments if seg]
                
                must_conditions = []
                for i, segment in enumerate(segments):
                    must_conditions.append(
                        models.FieldCondition(
                            key=f"pathSegments.{i}",
                            match=models.MatchValue(value=segment)
                        )
                    )
                    
                if must_conditions:
                    filter_condition = models.Filter(must=must_conditions)
                    
            # 执行搜索
            search_result = await asyncio.to_thread(
                self.client.search,
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=filter_condition,
                score_threshold=min_score or DEFAULT_SEARCH_MIN_SCORE,
                limit=max_results or DEFAULT_MAX_SEARCH_RESULTS,
                with_payload=True
            )
            
            # 过滤并转换结果
            filtered_results = []
            for result in search_result:
                if self._is_payload_valid(result.payload):
                    filtered_results.append(
                        VectorStoreSearchResult(
                            id=result.id,
                            score=result.score,
                            payload=result.payload
                        )
                    )
                    
            return filtered_results
            
        except Exception as e:
            logger.error(f"搜索向量失败: {e}")
            raise
            
    async def delete_points_by_file_path(self, file_path: str) -> None:
        """根据文件路径删除向量点"""
        await self.delete_points_by_multiple_file_paths([file_path])
        
    async def delete_points_by_multiple_file_paths(self, file_paths: List[str]) -> None:
        """
        根据多个文件路径删除向量点
        
        Args:
            file_paths: 要删除的文件路径列表
        """
        if not file_paths:
            return
            
        try:
            # 规范化文件路径
            normalized_paths = []
            for file_path in file_paths:
                abs_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
                normalized_paths.append(os.path.normpath(abs_path))
                
            # 构建删除过滤条件
            should_conditions = []
            for path in normalized_paths:
                should_conditions.append(
                    models.FieldCondition(
                        key="filePath",
                        match=models.MatchValue(value=path)
                    )
                )
                
            if should_conditions:
                filter_condition = models.Filter(should=should_conditions)
                
                await asyncio.to_thread(
                    self.client.delete,
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(filter=filter_condition),
                    wait=True
                )
                
        except Exception as e:
            logger.error(f"根据文件路径删除向量点失败: {e}")
            raise
            
    async def clear_collection(self) -> None:
        """清空集合"""
        try:
            await asyncio.to_thread(
                self.client.delete,
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=[])
                ),
                wait=True
            )
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            raise
            
    async def delete_collection(self) -> None:
        """删除集合"""
        try:
            if await self.collection_exists():
                await asyncio.to_thread(self.client.delete_collection, self.collection_name)
        except Exception as e:
            logger.error(f"删除集合 {self.collection_name} 失败: {e}")
            raise
            
    async def collection_exists(self) -> bool:
        """检查集合是否存在"""
        collection_info = await self._get_collection_info()
        return collection_info is not None