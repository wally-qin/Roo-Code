"""
Milvus向量存储客户端实现

基于IVectorStore接口实现的Milvus向量数据库客户端，
提供与Qdrant相同的功能接口，支持无缝切换。
"""

import asyncio
import hashlib
import os
from typing import List, Optional, Dict, Any, Union
import logging
import json

from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, exceptions
)
import numpy as np

from ..interfaces import IVectorStore, PointStruct, VectorStoreSearchResult
from ..constants import DEFAULT_SEARCH_MIN_SCORE, DEFAULT_MAX_SEARCH_RESULTS

logger = logging.getLogger(__name__)


class MilvusVectorStore(IVectorStore):
    """Milvus向量存储实现"""
    
    def __init__(self, workspace_path: str, host: str = "localhost", port: str = "19530", 
                 vector_size: int = 1536, user: Optional[str] = None, password: Optional[str] = None):
        """
        初始化Milvus向量存储
        
        Args:
            workspace_path: 工作空间路径
            host: Milvus服务器地址
            port: Milvus服务器端口
            vector_size: 向量维度
            user: 可选的用户名
            password: 可选的密码
        """
        self.workspace_path = workspace_path
        self.host = host
        self.port = port
        self.vector_size = vector_size
        self.user = user
        self.password = password
        
        # 基于工作空间路径生成集合名称
        hash_obj = hashlib.sha256(workspace_path.encode())
        # Milvus集合名称规则：只能包含字母、数字和下划线，且以字母或下划线开头
        self.collection_name = f"ws_{hash_obj.hexdigest()[:16]}"
        
        self.collection: Optional[Collection] = None
        self._connection_alias = f"conn_{hash_obj.hexdigest()[:8]}"
        
    async def _connect(self) -> None:
        """连接到Milvus服务器"""
        try:
            # 检查是否已连接
            if connections.has_connection(self._connection_alias):
                return
                
            # 建立连接
            await asyncio.to_thread(
                connections.connect,
                alias=self._connection_alias,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password
            )
            logger.info(f"已连接到Milvus: {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"连接Milvus失败: {e}")
            raise Exception(f"Milvus连接失败: {self.host}:{self.port}, 错误: {e}")
            
    def _create_collection_schema(self) -> CollectionSchema:
        """创建集合模式"""
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True, auto_id=False),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.vector_size),
            FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="code_chunk", dtype=DataType.VARCHAR, max_length=10000),
            FieldSchema(name="start_line", dtype=DataType.INT64),
            FieldSchema(name="end_line", dtype=DataType.INT64),
            FieldSchema(name="segment_hash", dtype=DataType.VARCHAR, max_length=64),
            # 路径分段字段，用于过滤
            FieldSchema(name="path_segments", dtype=DataType.VARCHAR, max_length=2000),
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description="代码索引向量集合"
        )
        return schema
        
    async def initialize(self) -> bool:
        """
        初始化向量存储
        
        Returns:
            bool: 是否创建了新集合
        """
        await self._connect()
        created = False
        
        try:
            # 检查集合是否存在
            has_collection = await asyncio.to_thread(
                utility.has_collection,
                self.collection_name,
                using=self._connection_alias
            )
            
            if has_collection:
                # 集合存在，加载现有集合
                self.collection = Collection(
                    name=self.collection_name,
                    using=self._connection_alias
                )
                
                # 检查向量维度
                schema = self.collection.schema
                vector_field = None
                for field in schema.fields:
                    if field.name == "vector":
                        vector_field = field
                        break
                        
                if vector_field and hasattr(vector_field, 'params'):
                    existing_dim = vector_field.params.get('dim', 0)
                    if existing_dim != self.vector_size:
                        logger.warning(f"集合 {self.collection_name} 向量维度不匹配 "
                                     f"(现有: {existing_dim}, 期望: {self.vector_size})，重新创建")
                        await self._drop_collection()
                        await self._create_collection()
                        created = True
                    else:
                        logger.info(f"集合已存在且配置正确: {self.collection_name}")
                else:
                    # 无法确定维度，重新创建
                    await self._drop_collection()
                    await self._create_collection()
                    created = True
            else:
                # 集合不存在，创建新集合
                await self._create_collection()
                created = True
                
            # 加载集合到内存
            await asyncio.to_thread(self.collection.load)
            
            # 创建索引（如果不存在）
            await self._create_indexes()
            
            return created
            
        except Exception as e:
            logger.error(f"初始化Milvus集合失败: {e}")
            raise Exception(f"Milvus初始化失败: {e}")
            
    async def _create_collection(self) -> None:
        """创建新集合"""
        schema = self._create_collection_schema()
        
        self.collection = await asyncio.to_thread(
            Collection,
            name=self.collection_name,
            schema=schema,
            using=self._connection_alias
        )
        logger.info(f"创建新集合: {self.collection_name}")
        
    async def _drop_collection(self) -> None:
        """删除集合"""
        if self.collection:
            await asyncio.to_thread(self.collection.drop)
            
    async def _create_indexes(self) -> None:
        """创建索引"""
        try:
            # 为向量字段创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            
            # 检查是否已有索引
            indexes = await asyncio.to_thread(self.collection.indexes)
            vector_index_exists = any(idx.field_name == "vector" for idx in indexes)
            
            if not vector_index_exists:
                await asyncio.to_thread(
                    self.collection.create_index,
                    field_name="vector",
                    index_params=index_params
                )
                logger.info("已创建向量索引")
                
        except Exception as e:
            logger.warning(f"创建索引失败: {e}")
            
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
            vectors = []
            file_paths = []
            code_chunks = []
            start_lines = []
            end_lines = []
            segment_hashes = []
            path_segments_list = []
            
            for point in points:
                ids.append(point.id)
                vectors.append(point.vector)
                
                payload = point.payload
                file_paths.append(payload.get("filePath", ""))
                code_chunks.append(payload.get("codeChunk", ""))
                start_lines.append(payload.get("startLine", 0))
                end_lines.append(payload.get("endLine", 0))
                segment_hashes.append(payload.get("segmentHash", ""))
                
                # 处理路径分段
                file_path = payload.get("filePath", "")
                segments = file_path.split(os.sep)
                segments = [seg for seg in segments if seg]
                path_segments = json.dumps({str(i): segments[i] for i in range(min(len(segments), 5))})
                path_segments_list.append(path_segments)
                
            data = [
                ids,
                vectors,
                file_paths,
                code_chunks,
                start_lines,
                end_lines,
                segment_hashes,
                path_segments_list
            ]
            
            # 执行插入
            await asyncio.to_thread(self.collection.insert, data)
            
            # 刷新以确保数据可见
            await asyncio.to_thread(self.collection.flush)
            
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
            # 构建搜索参数
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            limit = max_results or DEFAULT_MAX_SEARCH_RESULTS
            
            # 构建过滤表达式
            expr = None
            if directory_prefix:
                segments = directory_prefix.split(os.sep)
                segments = [seg for seg in segments if seg]
                
                # 构建路径过滤表达式
                conditions = []
                for i, segment in enumerate(segments):
                    conditions.append(f'json_extract(path_segments, "$.{i}") == "{segment}"')
                
                if conditions:
                    expr = " and ".join(conditions)
                    
            # 执行搜索
            search_results = await asyncio.to_thread(
                self.collection.search,
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["file_path", "code_chunk", "start_line", "end_line", "segment_hash"]
            )
            
            # 处理结果
            results = []
            min_score_threshold = min_score or DEFAULT_SEARCH_MIN_SCORE
            
            for hits in search_results:
                for hit in hits:
                    # Milvus的cosine距离需要转换为相似度分数
                    # 距离越小，相似度越高，分数 = 1 - 距离
                    score = 1.0 - hit.distance if hit.distance <= 1.0 else 0.0
                    
                    if score >= min_score_threshold:
                        payload = {
                            "filePath": hit.entity.get("file_path"),
                            "codeChunk": hit.entity.get("code_chunk"),
                            "startLine": hit.entity.get("start_line"),
                            "endLine": hit.entity.get("end_line"),
                            "segmentHash": hit.entity.get("segment_hash")
                        }
                        
                        results.append(VectorStoreSearchResult(
                            id=hit.id,
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
                
            # 构建删除表达式
            path_conditions = [f'file_path == "{path}"' for path in normalized_paths]
            expr = " or ".join(path_conditions)
            
            if expr:
                await asyncio.to_thread(self.collection.delete, expr)
                await asyncio.to_thread(self.collection.flush)
                
        except Exception as e:
            logger.error(f"根据文件路径删除向量点失败: {e}")
            raise
            
    async def clear_collection(self) -> None:
        """清空集合"""
        try:
            # Milvus删除所有数据的方式是删除并重新创建集合
            await self._drop_collection()
            await self._create_collection()
            await asyncio.to_thread(self.collection.load)
            await self._create_indexes()
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            raise
            
    async def delete_collection(self) -> None:
        """删除集合"""
        try:
            if await self.collection_exists():
                await self._drop_collection()
                self.collection = None
        except Exception as e:
            logger.error(f"删除集合 {self.collection_name} 失败: {e}")
            raise
            
    async def collection_exists(self) -> bool:
        """检查集合是否存在"""
        try:
            return await asyncio.to_thread(
                utility.has_collection,
                self.collection_name,
                using=self._connection_alias
            )
        except Exception:
            return False
            
    def __del__(self):
        """析构函数，清理连接"""
        try:
            if hasattr(self, '_connection_alias') and connections.has_connection(self._connection_alias):
                connections.disconnect(self._connection_alias)
        except Exception:
            pass