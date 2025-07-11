"""
代码索引系统使用示例

展示如何正确初始化和使用代码索引系统。
参照CodeIndexManager的实际实现，确保所有方法调用和参数都是正确的。

此示例将真正遍历wally_qin目录下的所有代码文件，解析代码块，并存储到向量数据库中。
"""

import asyncio
import os
import glob
from typing import Dict, Any, List
from pathlib import Path

from code_index.managers.code_index_manager import CodeIndexManager
from code_index.interfaces import IndexingState
from code_index.processors.code_parser import CodeParser
from code_index.constants import SUPPORTED_EXTENSIONS


async def scan_code_files(directory: str) -> List[str]:
    """扫描目录下的所有代码文件"""
    code_files = []
    
    # 使用pathlib递归扫描所有文件
    for ext in SUPPORTED_EXTENSIONS:
        pattern = f"**/*{ext}"
        files = list(Path(directory).glob(pattern))
        for file_path in files:
            # 排除一些不需要索引的目录
            file_str = str(file_path)
            if not any(skip in file_str for skip in [
                '__pycache__', '.git', 'node_modules', '.venv', 
                'venv', '.pytest_cache', 'build', 'dist'
            ]):
                code_files.append(file_str)
    
    print(f"Found {len(code_files)} code files to index")
    for i, file_path in enumerate(code_files[:10], 1):  # 显示前10个文件
        print(f"  {i}. {os.path.relpath(file_path, directory)}")
    if len(code_files) > 10:
        print(f"  ... and {len(code_files) - 10} more files")
    
    return code_files


async def demonstrate_code_parsing(directory: str) -> None:
    """演示代码解析功能"""
    print("\n=== 代码解析演示 ===")
    
    parser = CodeParser()
    code_files = await scan_code_files(directory)
    
    # 选择几个文件进行解析演示
    demo_files = code_files[:3]  # 只演示前3个文件
    
    for file_path in demo_files:
        print(f"\n解析文件: {os.path.relpath(file_path, directory)}")
        try:
            code_blocks = await parser.parse_file(file_path)
            print(f"  发现 {len(code_blocks)} 个代码块:")
            
            for i, block in enumerate(code_blocks[:3], 1):  # 只显示前3个块
                print(f"    {i}. [{block.type}] {block.identifier or 'unnamed'}")
                print(f"       行 {block.start_line}-{block.end_line} ({len(block.content)} 字符)")
                # 显示代码预览
                preview = block.content[:100].replace('\n', '\\n')
                print(f"       预览: {preview}...")
                
        except Exception as e:
            print(f"  解析失败: {e}")


async def example_full_indexing():
    """完整的索引示例 - 真正索引wally_qin目录"""
    print("=== 完整索引示例 ===")
    
    # 配置示例 - 使用OpenAI + Qdrant
    config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY", "your-openai-api-key-here"),
        "qdrant_url": "http://localhost:6333",
        "search_min_score": 0.7,
        "search_max_results": 10
    }
    
    # 获取当前工作目录（wally_qin）
    workspace_path = os.getcwd()
    print(f"工作空间路径: {workspace_path}")
    
    # 首先演示代码解析
    await demonstrate_code_parsing(workspace_path)
    
    # 创建代码索引管理器
    manager = CodeIndexManager.get_instance(workspace_path)
    
    if not manager:
        print("无法创建代码索引管理器")
        return
        
    try:
        print(f"\n正在初始化代码索引系统...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("功能未启用，请检查配置")
            return
            
        if not manager.is_feature_configured:
            print("配置不完整，请检查API密钥和Qdrant URL")
            print("提示: 设置环境变量 OPENAI_API_KEY")
            return
            
        print(f"初始化完成，需要重启: {init_result['requires_restart']}")
        
        # 获取要索引的文件列表
        code_files = await scan_code_files(workspace_path)
        total_files = len(code_files)
        
        if total_files == 0:
            print("未找到需要索引的代码文件")
            return
            
        # 监听进度更新
        async def monitor_progress():
            indexed_count = 0
            try:
                while True:
                    await manager.on_progress_update.wait()
                    status = manager.get_current_status()
                    
                    print(f"\n📊 状态更新:")
                    print(f"   状态: {status['state']}")
                    if status['message']:
                        print(f"   消息: {status['message']}")
                    
                    progress = status.get('progress', {})
                    if 'current' in progress and 'total' in progress:
                        current = progress['current']
                        total = progress['total']
                        percentage = (current / total * 100) if total > 0 else 0
                        print(f"   进度: {current}/{total} ({percentage:.1f}%)")
                        
                        if 'current_file' in progress:
                            rel_path = os.path.relpath(progress['current_file'], workspace_path)
                            print(f"   当前文件: {rel_path}")
                            
                    elif 'indexed' in progress and 'total' in progress:
                        indexed = progress['indexed']
                        total = progress['total']
                        percentage = (indexed / total * 100) if total > 0 else 0
                        print(f"   索引进度: {indexed}/{total} 代码块 ({percentage:.1f}%)")
                        
            except asyncio.CancelledError:
                pass
                
        # 启动进度监控
        progress_task = asyncio.create_task(monitor_progress())
        
        print(f"\n🚀 开始索引 {total_files} 个代码文件...")
        await manager.start_indexing()
        
        # 等待索引完成
        print("⏳ 等待索引完成...")
        max_wait_time = 300  # 最多等待5分钟
        wait_time = 0
        
        while manager.state == IndexingState.INDEXING and wait_time < max_wait_time:
            await asyncio.sleep(2)
            wait_time += 2
            
        progress_task.cancel()
        
        final_status = manager.get_current_status()
        print(f"\n📋 最终状态: {final_status}")
        
        if manager.state == IndexingState.INDEXED:
            print("✅ 索引完成！")
            
            # 执行搜索示例
            print("\n🔍 执行搜索示例...")
            search_queries = [
                "CodeIndexManager",
                "async function", 
                "class definition",
                "import statement",
                "vector store",
                "parse file",
                "tree sitter"
            ]
            
            for query in search_queries:
                print(f"\n搜索: '{query}'")
                try:
                    results = await manager.search_index(query)
                    
                    if results:
                        print(f"  找到 {len(results)} 个结果:")
                        for i, result in enumerate(results[:3], 1):  # 只显示前3个结果
                            payload = result.payload
                            file_path = payload.get('filePath', 'N/A')
                            rel_path = os.path.relpath(file_path, workspace_path) if file_path != 'N/A' else 'N/A'
                            
                            print(f"    {i}. 📄 {rel_path}")
                            print(f"       📍 行 {payload.get('startLine', 'N/A')}-{payload.get('endLine', 'N/A')}")
                            print(f"       🎯 相似度: {result.score:.3f}")
                            print(f"       📝 类型: {payload.get('type', 'N/A')}")
                            
                            # 显示代码片段预览
                            content = payload.get('codeChunk', '')
                            if content:
                                preview = content[:150].replace('\n', '\\n')
                                print(f"       💡 预览: {preview}...")
                    else:
                        print("  ❌ 未找到相关结果")
                        
                except Exception as e:
                    print(f"  ⚠️ 搜索失败: {e}")
                    
            # 目录前缀搜索示例
            print(f"\n🔍 执行目录前缀搜索...")
            try:
                results = await manager.search_index("manager", directory_prefix=workspace_path)
                print(f"在工作目录下找到 {len(results)} 个包含'manager'的结果")
                
                for i, result in enumerate(results[:2], 1):
                    payload = result.payload
                    file_path = payload.get('filePath', 'N/A')
                    rel_path = os.path.relpath(file_path, workspace_path) if file_path != 'N/A' else 'N/A'
                    print(f"  {i}. 📄 {rel_path} (相似度: {result.score:.3f})")
                    
            except Exception as e:
                print(f"⚠️ 目录搜索失败: {e}")
                    
        elif manager.state == IndexingState.ERROR:
            print("❌ 索引过程出现错误")
            status = manager.get_current_status()
            print(f"错误信息: {status['message']}")
        else:
            print(f"⏸️ 索引未完成，当前状态: {manager.state}")
            
    except Exception as e:
        print(f"💥 发生错误: {e}")
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
            print("确保Ollama服务运行在: http://localhost:11434")
            return
            
        print(f"✅ Ollama初始化完成: {init_result}")
        
        # 获取当前状态
        status = manager.get_current_status()
        print(f"📊 当前状态: {status}")
        
        print("✅ Ollama配置验证成功！")
        
    except Exception as e:
        print(f"❌ Ollama示例执行失败: {e}")
        
    finally:
        manager.dispose()


async def example_system_management():
    """系统管理功能示例"""
    print("\n=== 系统管理功能示例 ===")
    
    config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY", "your-openai-api-key-here"),
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
        print(f"📊 系统状态检查:")
        print(f"  功能是否启用: {manager.is_feature_enabled}")
        print(f"  功能是否已配置: {manager.is_feature_configured}")
        print(f"  是否已初始化: {manager.is_initialized}")
        print(f"  当前状态: {manager.state}")
        
        # 状态管理
        status = manager.get_current_status()
        print(f"  详细状态: {status}")
        
        # 停止监听器
        print("\n🛑 停止文件监听器...")
        await manager.stop_watcher()
        print("✅ 文件监听器已停止")
        
        # 清空索引数据（仅在有效配置时）
        if manager.is_feature_enabled and manager.is_initialized:
            print("\n🗑️ 清空索引数据...")
            await manager.clear_index_data()
            print("✅ 索引数据已清空")
        
        # 处理设置变更
        print("\n⚙️ 处理设置变更...")
        await manager.handle_settings_change()
        print("✅ 设置变更处理完成")
        
    except Exception as e:
        print(f"❌ 系统管理示例执行失败: {e}")
        
    finally:
        manager.dispose()


async def main():
    """主函数"""
    print("🚀 代码索引系统使用示例")
    print("=" * 60)
    print(f"📁 工作空间路径: {os.getcwd()}")
    print("=" * 60)
    
    # 完整索引示例（主要功能）
    await example_full_indexing()
    
    # Ollama使用示例
    await example_ollama_usage()
    
    # 系统管理功能示例
    await example_system_management()
    
    # 释放所有实例
    CodeIndexManager.dispose_all()
    
    print("\n" + "=" * 60)
    print("✅ 示例完成")
    print("\n📋 使用说明:")
    print("1. 设置正确的API密钥: export OPENAI_API_KEY='your-key'")
    print("2. 确保Qdrant服务运行: docker run -p 6333:6333 qdrant/qdrant")
    print("3. 如果使用Ollama: docker run -p 11434:11434 ollama/ollama")
    print("4. 安装tree-sitter依赖: pip install -r requirements.txt")


if __name__ == "__main__":
    asyncio.run(main())