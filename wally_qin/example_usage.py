"""
代码索引系统使用示例

展示如何正确初始化和使用代码索引系统。
参照CodeIndexManager的实际实现，确保所有方法调用和参数都是正确的。
"""

import asyncio
import os
from typing import Dict, Any

from code_index.managers.code_index_manager import CodeIndexManager
from code_index.interfaces import IndexingState


async def example_basic_usage():
    """基础代码索引系统使用示例"""
    print("=== 基础使用示例 ===")
    
    # 配置示例 - 使用OpenAI + Qdrant
    config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": "your-openai-api-key-here",
        "qdrant_url": "http://localhost:6333",
        "search_min_score": 0.7,
        "search_max_results": 10
    }
    
    # 获取代码索引管理器实例
    workspace_path = os.getcwd()  # 索引当前工作目录wally_qin下的所有文件
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
                try:
                    await manager.on_progress_update.wait()
                    status = manager.get_current_status()
                    print(f"状态: {status['state']}, 消息: {status['message']}")
                    print(f"进度: {status['progress']}")
                except asyncio.CancelledError:
                    break
                
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
                "async function",
                "import statement"
            ]
            
            for query in search_queries:
                print(f"\n搜索: '{query}'")
                results = await manager.search_index(query)
                
                if results:
                    print(f"找到 {len(results)} 个结果:")
                    for i, result in enumerate(results[:3]):  # 只显示前3个结果
                        payload = result.payload
                        print(f"  {i+1}. 文件: {payload.get('filePath', 'N/A')}")
                        print(f"     行: {payload.get('startLine', 'N/A')}-{payload.get('endLine', 'N/A')}")
                        print(f"     相似度: {result.score:.3f}")
                        print(f"     内容片段: {payload.get('codeChunk', '')[:100]}...")
                else:
                    print("未找到相关结果")
                    
            # 目录前缀搜索示例
            print("\n执行目录前缀搜索...")
            results = await manager.search_index("manager", directory_prefix="/wally_qin/code_index")
            print(f"在code_index目录下找到 {len(results)} 个相关结果")
                    
        elif manager.state == IndexingState.ERROR:
            print("索引过程出现错误")
            status = manager.get_current_status()
            print(f"错误信息: {status['message']}")
            
        # 取消进度监控
        progress_task.cancel()
        
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理资源
        manager.dispose()


async def example_ollama_usage():
    """使用Ollama本地嵌入器的示例"""
    print("\n=== Ollama使用示例 ===")
    
    config = {
        "enabled": True,
        "embedder_provider": "ollama",
        "ollama_base_url": "http://localhost:11434",
        "model_id": "nomic-embed-text",
        "qdrant_url": "http://localhost:6333",
        "search_min_score": 0.6,
        "search_max_results": 15
    }
    
    workspace_path = os.getcwd()
    manager = CodeIndexManager.get_instance(workspace_path)
    
    if not manager:
        print("无法创建代码索引管理器")
        return
        
    try:
        print("正在初始化Ollama嵌入器...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("功能未启用")
            return
            
        if not manager.is_feature_configured:
            print("配置不完整，请检查Ollama服务和Qdrant连接")
            return
            
        print(f"Ollama初始化完成: {init_result}")
        
        # 获取当前状态
        status = manager.get_current_status()
        print(f"当前状态: {status}")
        
        print("Ollama配置验证成功！")
        
    except Exception as e:
        print(f"Ollama示例执行失败: {e}")
        
    finally:
        manager.dispose()


async def example_system_management():
    """系统管理功能示例"""
    print("\n=== 系统管理功能示例 ===")
    
    config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": "your-openai-api-key-here",
        "qdrant_url": "http://localhost:6333"
    }
    
    workspace_path = os.getcwd()
    manager = CodeIndexManager.get_instance(workspace_path)
    
    if not manager:
        print("无法创建代码索引管理器")
        return
        
    try:
        # 初始化
        await manager.initialize(config)
        
        # 检查各种状态
        print(f"功能是否启用: {manager.is_feature_enabled}")
        print(f"功能是否已配置: {manager.is_feature_configured}")
        print(f"是否已初始化: {manager.is_initialized}")
        print(f"当前状态: {manager.state}")
        
        # 状态管理
        status = manager.get_current_status()
        print(f"详细状态: {status}")
        
        # 停止监听器
        print("停止文件监听器...")
        await manager.stop_watcher()
        
        # 清空索引数据
        if manager.is_feature_enabled and manager.is_initialized:
            print("清空索引数据...")
            await manager.clear_index_data()
            print("索引数据已清空")
        
        # 处理设置变更
        print("处理设置变更...")
        await manager.handle_settings_change()
        print("设置变更处理完成")
        
    except Exception as e:
        print(f"系统管理示例执行失败: {e}")
        
    finally:
        manager.dispose()


async def main():
    """主函数"""
    print("代码索引系统使用示例")
    print("=" * 50)
    print(f"工作空间路径: {os.getcwd()}")
    print("=" * 50)
    
    # 基础使用示例
    await example_basic_usage()
    
    # Ollama使用示例
    await example_ollama_usage()
    
    # 系统管理功能示例
    await example_system_management()
    
    # 释放所有实例
    CodeIndexManager.dispose_all()
    
    print("\n" + "=" * 50)
    print("示例完成")
    print("\n配置说明:")
    print("1. 设置正确的API密钥和服务URL")
    print("2. 确保Qdrant/Milvus/Chroma服务正在运行")
    print("3. 如果使用Ollama，确保已安装相应的嵌入模型")


if __name__ == "__main__":
    asyncio.run(main())