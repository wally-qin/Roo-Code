"""
Milvus向量数据库使用示例

演示如何配置和使用Milvus作为代码索引的向量存储后端。
"""

import asyncio
import os
from typing import Dict, Any

from code_index.managers.config_manager import CodeIndexConfigManager
from code_index.managers.code_index_manager import CodeIndexManager
from code_index.vector_store.milvus_client import MilvusVectorStore


async def example_milvus_basic_usage():
    """基础Milvus使用示例"""
    print("=== Milvus基础使用示例 ===")
    
    # 配置Milvus连接
    config = {
        "vector_store": "milvus",
        "milvus_host": "localhost",
        "milvus_port": "19530",
        # 如果需要认证，可以添加以下配置
        # "milvus_user": "your_username",
        # "milvus_password": "your_password",
        
        # 嵌入器配置（使用OpenAI）
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": "text-embedding-3-small",
    }
    
    if not config["openai_api_key"]:
        print("错误: 请设置OPENAI_API_KEY环境变量")
        return
    
    workspace_path = os.getcwd()
    
    try:
        # 直接使用Milvus向量存储
        vector_store = MilvusVectorStore(
            workspace_path=workspace_path,
            host=config["milvus_host"],
            port=config["milvus_port"],
            vector_size=1536  # text-embedding-3-small的维度
        )
        
        # 初始化向量存储
        print("正在初始化Milvus集合...")
        created = await vector_store.initialize()
        if created:
            print("✓ 创建了新的Milvus集合")
        else:
            print("✓ 连接到现有的Milvus集合")
            
        # 检查集合是否存在
        exists = await vector_store.collection_exists()
        print(f"✓ 集合存在状态: {exists}")
        
        print("Milvus连接成功!")
        
    except Exception as e:
        print(f"Milvus连接失败: {e}")
        print("请确保Milvus服务正在运行")


async def example_milvus_with_manager():
    """使用管理器的Milvus完整示例"""
    print("\n=== 使用管理器的Milvus完整示例 ===")
    
    # Milvus配置
    config = {
        "vector_store": "milvus",
        "milvus_host": "localhost",
        "milvus_port": "19530",
        "milvus_user": None,  # 可选
        "milvus_password": None,  # 可选
        
        # 嵌入器配置
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": "text-embedding-3-small",
        
        # 其他配置
        "search_min_score": 0.7,
        "search_max_results": 20,
    }
    
    if not config["openai_api_key"]:
        print("错误: 请设置OPENAI_API_KEY环境变量")
        return
    
    workspace_path = os.getcwd()
    
    try:
        # 创建配置管理器
        config_manager = CodeIndexConfigManager(config)
        
        # 验证配置
        if not config_manager.is_feature_configured:
            print("错误: 配置不完整")
            return
        
        print(f"✓ 向量存储类型: {config_manager.vector_store_type}")
        print(f"✓ Milvus配置: {config_manager.milvus_config}")
        
        # 创建代码索引管理器
        manager = CodeIndexManager(workspace_path, config_manager)
        
        # 初始化
        print("正在初始化代码索引管理器...")
        await manager.initialize()
        print("✓ 管理器初始化成功")
        
        # 索引文件（如果有Python文件）
        python_files = [f for f in os.listdir(".") if f.endswith(".py")]
        if python_files:
            sample_file = python_files[0]
            print(f"正在索引文件: {sample_file}")
            await manager.index_file(sample_file)
            print("✓ 文件索引完成")
            
            # 搜索示例
            print("执行搜索测试...")
            results = await manager.search_by_query("函数定义", max_results=5)
            print(f"✓ 搜索到 {len(results)} 个结果")
            
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result.payload.get('filePath', 'Unknown')} "
                      f"(分数: {result.score:.3f})")
        
        # 获取统计信息
        stats = await manager.get_stats()
        print(f"✓ 索引统计: {stats}")
        
    except Exception as e:
        print(f"示例执行失败: {e}")
        import traceback
        traceback.print_exc()


async def example_milvus_with_local_ollama():
    """Milvus + Ollama本地嵌入器示例"""
    print("\n=== Milvus + Ollama本地嵌入器示例 ===")
    
    # Milvus + Ollama配置
    config = {
        "vector_store": "milvus",
        "milvus_host": "localhost",
        "milvus_port": "19530",
        
        # 使用Ollama本地嵌入器
        "embedder_provider": "ollama",
        "ollama_base_url": "http://localhost:11434",
        "model_id": "nomic-embed-text",
        
        "search_min_score": 0.6,
        "search_max_results": 15,
    }
    
    workspace_path = os.getcwd()
    
    try:
        # 创建配置管理器
        config_manager = CodeIndexConfigManager(config)
        
        if not config_manager.is_feature_configured:
            print("错误: 配置不完整，请确保Ollama服务正在运行")
            return
        
        print(f"✓ 向量存储: {config_manager.vector_store_type}")
        print(f"✓ 嵌入器: Ollama ({config['model_id']})")
        
        # 创建代码索引管理器
        manager = CodeIndexManager(workspace_path, config_manager)
        
        # 初始化
        print("正在初始化...")
        await manager.initialize()
        print("✓ 初始化成功")
        
        # 获取状态
        status = await manager.get_status()
        print(f"✓ 管理器状态: {status}")
        
        print("Milvus + Ollama配置验证成功!")
        
    except Exception as e:
        print(f"示例执行失败: {e}")
        print("请确保Milvus和Ollama服务都在运行")


async def example_milvus_performance_test():
    """Milvus性能测试示例"""
    print("\n=== Milvus性能测试示例 ===")
    
    config = {
        "vector_store": "milvus",
        "milvus_host": "localhost",
        "milvus_port": "19530",
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": "text-embedding-3-small",
    }
    
    if not config["openai_api_key"]:
        print("跳过性能测试: 需要OPENAI_API_KEY")
        return
    
    workspace_path = os.getcwd()
    
    try:
        import time
        
        config_manager = CodeIndexConfigManager(config)
        manager = CodeIndexManager(workspace_path, config_manager)
        
        start_time = time.time()
        await manager.initialize()
        init_time = time.time() - start_time
        print(f"✓ 初始化耗时: {init_time:.2f}秒")
        
        # 索引性能测试
        python_files = [f for f in os.listdir(".") if f.endswith(".py")][:5]
        if python_files:
            start_time = time.time()
            for file in python_files:
                await manager.index_file(file)
            index_time = time.time() - start_time
            print(f"✓ 索引{len(python_files)}个文件耗时: {index_time:.2f}秒")
            
            # 搜索性能测试
            search_queries = ["函数", "类", "导入", "异步", "配置"]
            start_time = time.time()
            for query in search_queries:
                await manager.search_by_query(query, max_results=10)
            search_time = time.time() - start_time
            print(f"✓ {len(search_queries)}次搜索耗时: {search_time:.2f}秒")
        
        print("✓ Milvus性能测试完成")
        
    except Exception as e:
        print(f"性能测试失败: {e}")


def print_milvus_setup_instructions():
    """打印Milvus安装配置说明"""
    print("""
=== Milvus安装配置说明 ===

1. 使用Docker Compose安装Milvus:
   ```bash
   # 下载docker-compose.yml
   wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
   
   # 启动Milvus
   docker-compose up -d
   ```

2. 安装Python依赖:
   ```bash
   pip install pymilvus
   ```

3. 验证Milvus服务:
   - 默认端口: 19530
   - Web UI: http://localhost:9091 (如果安装了Attu)

4. 环境变量设置:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

5. 可选配置:
   - 如果使用认证，设置milvus_user和milvus_password
   - 可以修改milvus_host和milvus_port连接远程Milvus

更多信息请参考: https://milvus.io/docs
""")


async def main():
    """主函数"""
    print("代码索引系统 - Milvus向量数据库示例")
    print("="*50)
    
    # 打印设置说明
    print_milvus_setup_instructions()
    
    # 基础示例
    await example_milvus_basic_usage()
    
    # 完整管理器示例
    await example_milvus_with_manager()
    
    # Ollama本地嵌入器示例
    await example_milvus_with_local_ollama()
    
    # 性能测试
    await example_milvus_performance_test()
    
    print("\n✓ 所有Milvus示例执行完成")


if __name__ == "__main__":
    asyncio.run(main())