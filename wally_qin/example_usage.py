"""
代码索引系统使用示例

展示如何初始化和使用代码索引系统。
"""

import asyncio
import os
from typing import Dict, Any

from code_index import CodeIndexManager
from code_index.interfaces import IndexingState


async def example_usage():
    """代码索引系统使用示例"""
    
    # 配置示例 - 使用OpenAI
    config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": "your-openai-api-key-here",
        "qdrant_url": "http://localhost:6333",
        "search_min_score": 0.7,
        "search_max_results": 10
    }
    
    # 获取代码索引管理器实例
    workspace_path = os.getcwd()  # 或指定特定的工作空间路径
    manager = CodeIndexManager.get_instance(workspace_path)
    
    if not manager:
        print("无法创建代码索引管理器")
        return
        
    try:
        # 初始化管理器
        print("正在初始化代码索引系统...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_configured:
            print("配置不完整，请检查API密钥和Qdrant URL")
            return
            
        print(f"初始化完成，需要重启: {init_result['requires_restart']}")
        
        # 监听进度更新
        async def monitor_progress():
            while True:
                await manager.on_progress_update.wait()
                status = manager.get_current_status()
                print(f"状态: {status['state']}, 消息: {status['message']}")
                print(f"进度: {status['progress']}")
                
        # 启动进度监控
        progress_task = asyncio.create_task(monitor_progress())
        
        # 启动索引
        print("正在启动索引...")
        await manager.start_indexing()
        
        # 等待索引完成
        while manager.state == IndexingState.INDEXING:
            await asyncio.sleep(1)
            
        if manager.state == IndexingState.INDEXED:
            print("索引完成！")
            
            # 执行搜索示例
            print("\n执行搜索示例...")
            search_queries = [
                "function definition",
                "class implementation", 
                "error handling",
                "async function"
            ]
            
            for query in search_queries:
                print(f"\n搜索: '{query}'")
                results = await manager.search_index(query)
                
                if results:
                    print(f"找到 {len(results)} 个结果:")
                    for i, result in enumerate(results[:3]):  # 只显示前3个结果
                        payload = result.payload
                        print(f"  {i+1}. 文件: {payload['filePath']}")
                        print(f"     行: {payload['startLine']}-{payload['endLine']}")
                        print(f"     相似度: {result.score:.3f}")
                        print(f"     内容片段: {payload['codeChunk'][:100]}...")
                else:
                    print("未找到相关结果")
                    
        elif manager.state == IndexingState.ERROR:
            print("索引过程出现错误")
            status = manager.get_current_status()
            print(f"错误信息: {status['message']}")
            
        # 取消进度监控
        progress_task.cancel()
        
    except Exception as e:
        print(f"发生错误: {e}")
        
    finally:
        # 清理资源
        manager.dispose()


async def ollama_example():
    """使用Ollama的示例"""
    
    config = {
        "enabled": True,
        "embedder_provider": "ollama",
        "ollama_base_url": "http://localhost:11434",
        "model_id": "nomic-embed-text",
        "qdrant_url": "http://localhost:6333",
    }
    
    workspace_path = os.getcwd()
    manager = CodeIndexManager.get_instance(workspace_path)
    
    if manager:
        await manager.initialize(config)
        # ... 其他操作类似于OpenAI示例
        

if __name__ == "__main__":
    print("代码索引系统示例")
    print("=" * 50)
    
    # 运行示例
    asyncio.run(example_usage())
    
    print("\n" + "=" * 50)
    print("示例完成")