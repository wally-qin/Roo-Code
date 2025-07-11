"""
Chroma向量存储客户端实现

基于IVectorStore接口实现的Chroma向量数据库客户端，
提供与Qdrant和Milvus相同的功能接口，支持无缝切换。
"""

import asyncio
import hashlib
import os
import uuid
from typing import List, Optional, Dict, Any, Union
import logging
import json

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from ..interfaces import IVectorStore, PointStruct, VectorStoreSearchResult
from ..constants import DEFAULT_SEARCH_MIN_SCORE, DEFAULT_MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)


class ChromaVectorStore(IVectorStore):
    """Chroma向量存储实现"""
    
    def __init__(self, workspace_path: str, persist_directory: Optional[str] = None, 
                 host: Optional[str] = None, port: Optional[int] = None, 
                 vector_size: int = 1536):
        """
        初始化Chroma向量存储
        
        Args:
            workspace_path: 工作空间路径
            persist_directory: 可选的持久化目录路径，如果未提供将使用内存模式
            host: 可选的Chroma服务器地址，用于客户端-服务器模式
            port: 可选的Chroma服务器端口
            vector_size: 向量维度
        """
        self.workspace_path = workspace_path
        self.vector_size = vector_size
        self.persist_directory = persist_directory
        self.host = host
        self.port = port
        
        # 基于工作空间路径生成集合名称
        hash_obj = hashlib.sha256(workspace_path.encode())
        # Chroma集合名称规则：只能包含字母、数字、点、下划线和连字符
        self.collection_name = f"ws-{hash_obj.hexdigest()[:16]}"
        
        self.client: Optional[chromadb.Client] = None
        self.collection: Optional[chromadb.Collection] = None
        
    async def _create_client(self) -> chromadb.Client:
        """创建Chroma客户端"""
        try:
            if self.host and self.port:
                # 客户端-服务器模式
                client = await asyncio.to_thread(
                    chromadb.HttpClient,
                    host=self.host,
                    port=self.port
                )
                logger.info(f"已连接到Chroma服务器: {self.host}:{self.port}")
            elif self.persist_directory:
                # 持久化模式
                settings = Settings(
                    persist_directory=self.persist_directory,
                    allow_reset=True
                )
                client = await asyncio.to_thread(
                    chromadb.PersistentClient,
                    path=self.persist_directory,
                    settings=settings
                )
                logger.info(f"已创建Chroma持久化客户端: {self.persist_directory}")
            else:
                # 内存模式
                client = await asyncio.to_thread(chromadb.Client)
                logger.info("已创建Chroma内存客户端")
                
            return client
            
        except Exception as e:
            logger.error(f"创建Chroma客户端失败: {e}")
            raise Exception(f"Chroma客户端创建失败: {e}")
            
    async def initialize(self) -> bool:
        """
        初始化向量存储
        
        Returns:
            bool: 是否创建了新集合
        """
        try:
            self.client = await self._create_client()
            created = False
            
            # 检查集合是否存在
            try:
                self.collection = await asyncio.to_thread(
                    self.client.get_collection,
                    name=self.collection_name
                )
                
                # 检查集合是否为空，如果为空则认为是新创建的
                count = await asyncio.to_thread(self.collection.count)
                if count == 0:
                    created = True
                    
                logger.info(f"集合已存在: {self.collection_name}, 包含 {count} 个向量")
                
            except Exception:
                # 集合不存在，创建新集合
                self.collection = await asyncio.to_thread(
                    self.client.create_collection,
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
                )
                created = True
                logger.info(f"创建新集合: {self.collection_name}")
                
            return created
            
        except Exception as e:
            logger.error(f"初始化Chroma集合失败: {e}")
            raise Exception(f"Chroma初始化失败: {e}")
            
    def _prepare_metadata(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """准备元数据，确保符合Chroma的要求"""
        metadata = {}
        
        # Chroma要求元数据的值必须是字符串、整数、浮点数或布尔值
        for key, value in payload.items():
            if key == "pathSegments" and isinstance(value, dict):
                # 将路径分段转换为JSON字符串
                metadata["path_segments"] = json.dumps(value)
            elif isinstance(value, (str, int, float, bool)):
                metadata[key] = value
            else:
                # 其他类型转换为字符串
                metadata[key] = str(value)
                
        # 添加路径分段用于过滤
        if "filePath" in payload:
            file_path = payload["filePath"]
            segments = file_path.split(os.sep)
            segments = [seg for seg in segments if seg]
            
            # 为前5个路径段创建单独的元数据字段
            for i, segment in enumerate(segments[:5]):
                metadata[f"path_segment_{i}"] = segment
                
        return metadata
        
    async def upsert_points(self, points: List[PointStruct]) -> None:
        """
        插入或更新向量点
        
        Args:
            points: 要插入的向量点列表
        """
        if not points:
            return
            
        try:
            # 准备数据
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            
            for point in points:
                # 确保ID是字符串格式
                point_id = str(point.id) if not isinstance(point.id, str) else point.id
                ids.append(point_id)
                embeddings.append(point.vector)
                
                # 准备元数据
                metadata = self._prepare_metadata(point.payload)
                metadatas.append(metadata)
                
                # 文档内容（代码块）
                documents.append(point.payload.get("codeChunk", ""))
                
            # 执行upsert操作
            await asyncio.to_thread(
                self.collection.upsert,
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            
        except Exception as e:
            logger.error(f"插入向量点失败: {e}")
            raise
            
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
            # 构建where过滤条件
            where_filter = None
            if directory_prefix:
                segments = directory_prefix.split(os.sep)
                segments = [seg for seg in segments if seg]
                
                # 构建路径过滤条件
                where_conditions = {}
                for i, segment in enumerate(segments):
                    if i < 5:  # 最多支持5层路径
                        where_conditions[f"path_segment_{i}"] = {"$eq": segment}
                
                if where_conditions:
                    if len(where_conditions) == 1:
                        where_filter = where_conditions
                    else:
                        where_filter = {"$and": [
                            {key: value} for key, value in where_conditions.items()
                        ]}
                        
            # 执行搜索
            n_results = max_results or DEFAULT_MAX_SEARCH_RESULTS
            
            search_results = await asyncio.to_thread(
                self.collection.query,
                query_embeddings=[query_vector],
                n_results=n_results,
                where=where_filter,
                include=["metadatas", "documents", "distances"]
            )
            
            # 处理结果
            results = []
            min_score_threshold = min_score or DEFAULT_SEARCH_MIN_SCORE
            
            if search_results["ids"] and search_results["ids"][0]:
                ids = search_results["ids"][0]
                distances = search_results["distances"][0] if search_results["distances"] else []
                metadatas = search_results["metadatas"][0] if search_results["metadatas"] else []
                documents = search_results["documents"][0] if search_results["documents"] else []
                
                for i, point_id in enumerate(ids):
                    # Chroma使用距离（越小越相似），转换为相似度分数
                    # 对于余弦距离，相似度 = 1 - 距离
                    distance = distances[i] if i < len(distances) else 1.0
                    score = 1.0 - distance if distance <= 1.0 else 0.0
                    
                    if score >= min_score_threshold:
                        # 重构payload
                        metadata = metadatas[i] if i < len(metadatas) else {}
                        payload = {}
                        
                        # 恢复原始字段名
                        for key, value in metadata.items():
                            if key.startswith("path_segment_"):
                                continue  # 跳过路径分段字段
                            elif key == "path_segments":
                                # 恢复路径分段
                                try:
                                    payload["pathSegments"] = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            else:
                                payload[key] = value
                                
                        # 确保包含必要字段
                        if i < len(documents):
                            payload["codeChunk"] = documents[i]
                            
                        results.append(VectorStoreSearchResult(
                            id=point_id,
                            score=score,
                            payload=payload
                        ))
                        
            return results
            
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
                
            # 构建where过滤条件
            if len(normalized_paths) == 1:
                where_filter = {"filePath": {"$eq": normalized_paths[0]}}
            else:
                where_filter = {"filePath": {"$in": normalized_paths}}
                
            # 先查询要删除的IDs
            query_result = await asyncio.to_thread(
                self.collection.get,
                where=where_filter,
                include=["metadatas"]
            )
            
            if query_result["ids"]:
                # 删除找到的向量点
                await asyncio.to_thread(
                    self.collection.delete,
                    ids=query_result["ids"]
                )
                
        except Exception as e:
            logger.error(f"根据文件路径删除向量点失败: {e}")
            raise
            
    async def clear_collection(self) -> None:
        """清空集合"""
        try:
            # 删除并重新创建集合
            await asyncio.to_thread(self.client.delete_collection, self.collection_name)
            self.collection = await asyncio.to_thread(
                self.client.create_collection,
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            raise
            
    async def delete_collection(self) -> None:
        """删除集合"""
        try:
            if await self.collection_exists():
                await asyncio.to_thread(self.client.delete_collection, self.collection_name)
                self.collection = None
        except Exception as e:
            logger.error(f"删除集合 {self.collection_name} 失败: {e}")
            raise
            
    async def collection_exists(self) -> bool:
        """检查集合是否存在"""
        try:
            collections = await asyncio.to_thread(self.client.list_collections)
            collection_names = [col.name for col in collections]
            return self.collection_name in collection_names
        except Exception:
            return False