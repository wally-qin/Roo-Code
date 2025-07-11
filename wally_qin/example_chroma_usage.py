#!/usr/bin/env python3
"""
Chroma向量存储使用示例

演示如何使用ChromaVectorStore进行代码索引和搜索。
本示例展示了Chroma与Qdrant、Milvus并存的用法。
"""

import asyncio
import os
import tempfile
from typing import List
import numpy as np

from code_index.vector_store import ChromaVectorStore, QdrantVectorStore, MilvusVectorStore
from code_index.interfaces import PointStruct


async def create_sample_points() -> List[PointStruct]:
    """创建示例向量点"""
    points = []
    
    # 模拟一些代码块的向量表示
    sample_vectors = [
        np.random.rand(1536).tolist(),  # Python函数
        np.random.rand(1536).tolist(),  # JavaScript函数
        np.random.rand(1536).tolist(),  # TypeScript接口
    ]
    
    sample_payloads = [
        {
            "filePath": "/workspace/src/utils/helpers.py",
            "codeChunk": "def calculate_similarity(vec1, vec2):\n    return np.dot(vec1, vec2)",
            "startLine": 10,
            "endLine": 12,
            "segmentHash": "abc123",
            "type": "function"
        },
        {
            "filePath": "/workspace/src/components/Search.js",
            "codeChunk": "function searchCode(query) {\n  return vectorStore.search(query);\n}",
            "startLine": 25,
            "endLine": 27,
            "segmentHash": "def456",
            "type": "function"
        },
        {
            "filePath": "/workspace/src/types/interfaces.ts",
            "codeChunk": "interface VectorSearchResult {\n  id: string;\n  score: number;\n}",
            "startLine": 5,
            "endLine": 9,
            "segmentHash": "ghi789",
            "type": "interface"
        }
    ]
    
    for i, (vector, payload) in enumerate(zip(sample_vectors, sample_payloads)):
        points.append(PointStruct(
            id=f"point_{i}",
            vector=vector,
            payload=payload
        ))
    
    return points


async def demonstrate_chroma_basic_operations():
    """演示Chroma基本操作"""
    print("=== Chroma基本操作演示 ===\n")
    
    # 创建临时目录用于Chroma持久化
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_persist_dir = os.path.join(temp_dir, "chroma_db")
        
        # 初始化Chroma向量存储
        chroma_store = ChromaVectorStore(
            workspace_path="/workspace",
            persist_directory=chroma_persist_dir,
            vector_size=1536
        )
        
        try:
            # 1. 初始化
            print("1. 初始化Chroma向量存储...")
            created = await chroma_store.initialize()
            print(f"   集合创建: {'是' if created else '否'}")
            
            # 2. 插入向量点
            print("2. 插入示例向量点...")
            points = await create_sample_points()
            await chroma_store.upsert_points(points)
            print(f"   成功插入 {len(points)} 个向量点")
            
            # 3. 搜索相似向量
            print("3. 搜索相似向量...")
            query_vector = np.random.rand(1536).tolist()
            results = await chroma_store.search(
                query_vector=query_vector,
                max_results=3,
                min_score=0.0
            )
            
            print(f"   找到 {len(results)} 个结果:")
            for i, result in enumerate(results):
                payload = result.payload
                print(f"   [{i+1}] ID: {result.id}, Score: {result.score:.4f}")
                print(f"       文件: {payload.get('filePath', 'N/A')}")
                print(f"       类型: {payload.get('type', 'N/A')}")
                print(f"       行数: {payload.get('startLine', 'N/A')}-{payload.get('endLine', 'N/A')}")
                print()
            
            # 4. 根据目录前缀搜索
            print("4. 根据目录前缀搜索...")
            filtered_results = await chroma_store.search(
                query_vector=query_vector,
                directory_prefix="/workspace/src/components",
                max_results=5
            )
            print(f"   在 /workspace/src/components 目录下找到 {len(filtered_results)} 个结果")
            
            # 5. 删除特定文件的向量点
            print("5. 删除特定文件的向量点...")
            await chroma_store.delete_points_by_file_path("/workspace/src/utils/helpers.py")
            print("   已删除 helpers.py 的向量点")
            
            # 6. 验证删除结果
            print("6. 验证删除结果...")
            all_results = await chroma_store.search(
                query_vector=query_vector,
                max_results=10,
                min_score=0.0
            )
            print(f"   剩余向量点数量: {len(all_results)}")
            
            print("Chroma基本操作演示完成！")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # 清理
            try:
                await chroma_store.delete_collection()
                print("已清理Chroma集合")
            except:
                pass


async def demonstrate_multi_vector_store_coexistence():
    """演示多个向量存储共存"""
    print("\n=== 多向量存储共存演示 ===\n")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_persist_dir = os.path.join(temp_dir, "chroma_db")
        
        # 初始化三个不同的向量存储
        stores = {
            "chroma": ChromaVectorStore(
                workspace_path="/workspace",
                persist_directory=chroma_persist_dir,
                vector_size=1536
            ),
            # 注意：以下两个在真实环境中需要对应的服务运行
            # "qdrant": QdrantVectorStore(
            #     workspace_path="/workspace",
            #     url="http://localhost:6333",
            #     vector_size=1536
            # ),
            # "milvus": MilvusVectorStore(
            #     workspace_path="/workspace",
            #     host="localhost",
            #     port="19530",
            #     vector_size=1536
            # )
        }
        
        # 创建示例数据
        points = await create_sample_points()
        
        # 在每个向量存储中执行相同操作
        for store_name, store in stores.items():
            try:
                print(f"处理 {store_name.upper()} 向量存储:")
                
                # 初始化
                created = await store.initialize()
                print(f"  - 初始化完成，集合创建: {'是' if created else '否'}")
                
                # 插入数据
                await store.upsert_points(points)
                print(f"  - 插入 {len(points)} 个向量点")
                
                # 搜索
                query_vector = np.random.rand(1536).tolist()
                results = await store.search(query_vector, max_results=3)
                print(f"  - 搜索结果: {len(results)} 个")
                
                # 检查集合是否存在
                exists = await store.collection_exists()
                print(f"  - 集合存在: {'是' if exists else '否'}")
                
                print(f"  - {store_name.upper()} 操作完成\n")
                
            except Exception as e:
                print(f"  - {store_name.upper()} 操作失败: {e}\n")
                continue
            
            finally:
                # 清理
                try:
                    await store.delete_collection()
                except:
                    pass
        
        print("多向量存储共存演示完成！")


async def demonstrate_chroma_memory_mode():
    """演示Chroma内存模式"""
    print("\n=== Chroma内存模式演示 ===\n")
    
    # 不提供持久化目录，使用内存模式
    chroma_store = ChromaVectorStore(
        workspace_path="/workspace",
        vector_size=1536
    )
    
    try:
        print("1. 初始化内存模式Chroma...")
        await chroma_store.initialize()
        print("   内存模式初始化完成")
        
        print("2. 插入数据到内存...")
        points = await create_sample_points()
        await chroma_store.upsert_points(points)
        print(f"   插入 {len(points)} 个向量点到内存")
        
        print("3. 从内存搜索...")
        query_vector = np.random.rand(1536).tolist()
        results = await chroma_store.search(query_vector, max_results=3)
        print(f"   从内存搜索到 {len(results)} 个结果")
        
        print("内存模式演示完成！")
        print("注意：内存模式数据不会持久化，程序结束后数据丢失")
        
    except Exception as e:
        print(f"Error: {e}")


async def main():
    """主函数"""
    print("Chroma向量存储演示程序")
    print("=" * 50)
    
    # 演示基本操作
    await demonstrate_chroma_basic_operations()
    
    # 演示多向量存储共存
    await demonstrate_multi_vector_store_coexistence()
    
    # 演示内存模式
    await demonstrate_chroma_memory_mode()
    
    print("\n" + "=" * 50)
    print("所有演示完成！")
    print("\n说明:")
    print("- Chroma支持持久化模式和内存模式")
    print("- 可以与Qdrant和Milvus同时使用，互不干扰")
    print("- 提供与其他向量存储相同的接口，便于切换")
    print("- 支持目录前缀过滤和相似度阈值搜索")


if __name__ == "__main__":
    asyncio.run(main())