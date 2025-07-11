"""
Milvus向量数据库使用示例

演示如何配置和使用Milvus作为代码索引的向量存储后端。
参照CodeIndexManager的实际实现，确保所有方法调用和参数都是正确的。
"""

import asyncio
import os
from typing import Dict, Any

from code_index.managers.code_index_manager import CodeIndexManager
from code_index.interfaces import IndexingState
from code_index.vector_store.milvus_client import MilvusVectorStore


async def example_milvus_basic_connection():
    """基础Milvus连接测试示例"""
    print("=== Milvus基础连接测试 ===")
    
    # Milvus连接配置
    milvus_config = {
        "host": "localhost",
        "port": "19530",
        # 如果需要认证，可以添加以下配置
        # "user": "your_username",
        # "password": "your_password",
    }
    
    workspace_path = os.getcwd()
    
    try:
        # 直接使用Milvus向量存储进行连接测试
        vector_store = MilvusVectorStore(
            workspace_path=workspace_path,
            host=milvus_config["host"],
            port=milvus_config["port"],
            vector_size=1536  # text-embedding-3-small的维度
        )
        
        # 初始化向量存储
        print("正在连接Milvus...")
        created = await vector_store.initialize()
        if created:
            print("✓ 创建了新的Milvus集合")
        else:
            print("✓ 连接到现有的Milvus集合")
            
        # 检查集合是否存在
        exists = await vector_store.collection_exists()
        print(f"✓ 集合存在状态: {exists}")
        
        print("✓ Milvus连接成功!")
        
        # 清理测试集合
        await vector_store.delete_collection()
        print("✓ 清理测试集合完成")
        
    except Exception as e:
        print(f"✗ Milvus连接失败: {e}")
        print("请确保Milvus服务正在运行在localhost:19530")


async def example_milvus_with_manager():
    """使用CodeIndexManager的Milvus完整示例"""
    print("\n=== 使用CodeIndexManager的Milvus完整示例 ===")
    
    # Milvus配置
    config = {
        "enabled": True,
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
        print("可以使用: export OPENAI_API_KEY='your-api-key'")
        return
    
    workspace_path = os.getcwd()
    
    try:
        # 创建代码索引管理器
        manager = CodeIndexManager.get_instance(workspace_path)
        if not manager:
            print("无法创建代码索引管理器")
            return
        
        # 初始化
        print("正在初始化代码索引管理器...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("错误: 功能未启用")
            return
            
        if not manager.is_feature_configured:
            print("错误: 配置不完整")
            return
        
        print(f"✓ 管理器初始化成功: {init_result}")
        print(f"✓ 当前状态: {manager.state}")
        
        # 监听进度更新
        async def monitor_progress():
            try:
                while True:
                    await manager.on_progress_update.wait()
                    status = manager.get_current_status()
                    print(f"  进度更新 - 状态: {status['state']}, 消息: {status['message']}")
                    if status.get('progress'):
                        print(f"  进度详情: {status['progress']}")
            except asyncio.CancelledError:
                pass
        
        # 启动进度监控
        progress_task = asyncio.create_task(monitor_progress())
        
        # 启动索引
        print("正在启动索引...")
        await manager.start_indexing()
        
        # 等待索引完成
        max_wait_time = 60  # 最多等待60秒
        wait_time = 0
        while manager.state == IndexingState.INDEXING and wait_time < max_wait_time:
            await asyncio.sleep(1)
            wait_time += 1
            
        progress_task.cancel()
        
        if manager.state == IndexingState.INDEXED:
            print("✓ 索引完成!")
            
            # 搜索示例
            print("\n执行搜索测试...")
            search_queries = [
                "CodeIndexManager",
                "async function",
                "vector store",
                "embedding",
                "milvus"
            ]
            
            for query in search_queries:
                print(f"\n搜索: '{query}'")
                results = await manager.search_index(query, directory_prefix="/wally_qin")
                
                if results:
                    print(f"  找到 {len(results)} 个结果:")
                    for i, result in enumerate(results[:3], 1):
                        payload = result.payload
                        print(f"    {i}. {payload.get('filePath', 'Unknown')} "
                              f"(分数: {result.score:.3f})")
                        print(f"       行: {payload.get('startLine', 'N/A')}-{payload.get('endLine', 'N/A')}")
                else:
                    print("  未找到相关结果")
        
        elif manager.state == IndexingState.ERROR:
            print("✗ 索引过程出现错误")
            status = manager.get_current_status()
            print(f"错误信息: {status['message']}")
        else:
            print(f"索引未完成，当前状态: {manager.state}")
            
        # 获取当前状态
        final_status = manager.get_current_status()
        print(f"\n最终状态: {final_status}")
        
    except Exception as e:
        print(f"示例执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'manager' in locals():
            manager.dispose()


async def example_milvus_with_ollama():
    """Milvus + Ollama本地嵌入器示例"""
    print("\n=== Milvus + Ollama本地嵌入器示例 ===")
    
    # Milvus + Ollama配置
    config = {
        "enabled": True,
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
        manager = CodeIndexManager.get_instance(workspace_path)
        if not manager:
            print("无法创建代码索引管理器")
            return
        
        print("正在初始化Milvus + Ollama配置...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("错误: 功能未启用")
            return
            
        if not manager.is_feature_configured:
            print("错误: 配置不完整，请确保Ollama服务正在运行")
            return
        
        print(f"✓ Milvus + Ollama初始化成功: {init_result}")
        print(f"✓ 向量存储: Milvus")
        print(f"✓ 嵌入器: Ollama (nomic-embed-text)")
        
        # 获取状态
        status = manager.get_current_status()
        print(f"✓ 管理器状态: {status}")
        
        print("Milvus + Ollama配置验证成功!")
        
    except Exception as e:
        print(f"示例执行失败: {e}")
        print("请确保Milvus和Ollama服务都在运行")
        print("- Milvus: http://localhost:19530")
        print("- Ollama: http://localhost:11434")
    finally:
        if 'manager' in locals():
            manager.dispose()


async def example_milvus_system_operations():
    """Milvus系统操作示例"""
    print("\n=== Milvus系统操作示例 ===")
    
    config = {
        "enabled": True,
        "vector_store": "milvus",
        "milvus_host": "localhost",
        "milvus_port": "19530",
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": "text-embedding-3-small",
    }
    
    if not config["openai_api_key"]:
        print("跳过系统操作示例: 需要OPENAI_API_KEY")
        return
    
    workspace_path = os.getcwd()
    
    try:
        manager = CodeIndexManager.get_instance(workspace_path)
        if not manager:
            print("无法创建代码索引管理器")
            return
        
        # 初始化计时
        import time
        start_time = time.time()
        await manager.initialize(config)
        init_time = time.time() - start_time
        print(f"✓ 初始化耗时: {init_time:.2f}秒")
        
        # 系统状态检查
        print("\n系统状态检查:")
        print(f"  功能启用: {manager.is_feature_enabled}")
        print(f"  功能配置: {manager.is_feature_configured}")
        print(f"  已初始化: {manager.is_initialized}")
        print(f"  当前状态: {manager.state}")
        
        # 清空索引数据测试
        if manager.is_feature_enabled and manager.is_initialized:
            print("\n测试清空索引数据...")
            await manager.clear_index_data()
            print("✓ 索引数据清空完成")
        
        # 停止监听器测试
        print("\n测试停止文件监听器...")
        await manager.stop_watcher()
        print("✓ 文件监听器已停止")
        
        # 设置变更处理测试
        print("\n测试设置变更处理...")
        await manager.handle_settings_change()
        print("✓ 设置变更处理完成")
        
        print("\n✓ Milvus系统操作示例完成")
        
    except Exception as e:
        print(f"系统操作示例失败: {e}")
    finally:
        if 'manager' in locals():
            manager.dispose()


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
    print(f"工作空间路径: {os.getcwd()}")
    print("="*50)
    
    # 打印设置说明
    print_milvus_setup_instructions()
    
    # 基础连接测试
    await example_milvus_basic_connection()
    
    # 完整管理器示例
    await example_milvus_with_manager()
    
    # Ollama本地嵌入器示例
    await example_milvus_with_ollama()
    
    # 系统操作示例
    await example_milvus_system_operations()
    
    # 释放所有实例
    CodeIndexManager.dispose_all()
    
    print("\n✓ 所有Milvus示例执行完成")
    print("\n使用说明:")
    print("1. 确保Milvus服务正在运行")
    print("2. 设置正确的API密钥")
    print("3. 根据需要调整配置参数")


if __name__ == "__main__":
    asyncio.run(main())