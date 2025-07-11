"""
Milvus向量数据库使用示例

演示如何配置和使用Milvus作为代码索引的向量存储后端。
参照CodeIndexManager的实际实现，确保所有方法调用和参数都是正确的。

此示例将真正遍历wally_qin目录下的所有代码文件，解析代码块，并存储到Milvus向量数据库中。
"""

import asyncio
import os
from typing import Dict, Any, List
from pathlib import Path

from code_index.managers.code_index_manager import CodeIndexManager
from code_index.interfaces import IndexingState
from code_index.processors.code_parser import CodeParser
from code_index.vector_store.milvus_client import MilvusVectorStore
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
    
    print(f"🔍 发现 {len(code_files)} 个代码文件待索引")
    for i, file_path in enumerate(code_files[:10], 1):  # 显示前10个文件
        print(f"  {i}. {os.path.relpath(file_path, directory)}")
    if len(code_files) > 10:
        print(f"  ... 还有 {len(code_files) - 10} 个文件")
    
    return code_files


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
        print("🔌 正在连接Milvus...")
        created = await vector_store.initialize()
        if created:
            print("✅ 创建了新的Milvus集合")
        else:
            print("✅ 连接到现有的Milvus集合")
            
        # 检查集合是否存在
        exists = await vector_store.collection_exists()
        print(f"📊 集合存在状态: {'存在' if exists else '不存在'}")
        
        print("✅ Milvus连接成功!")
        
        # 清理测试集合
        await vector_store.delete_collection()
        print("🧹 清理测试集合完成")
        
    except Exception as e:
        print(f"❌ Milvus连接失败: {e}")
        print("💡 请确保Milvus服务正在运行在localhost:19530")
        print("   可以使用Docker启动: docker run -p 19530:19530 milvusdb/milvus:latest")


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
        print("❌ 错误: 请设置OPENAI_API_KEY环境变量")
        print("💡 可以使用: export OPENAI_API_KEY='your-api-key'")
        return
    
    workspace_path = os.getcwd()
    
    try:
        # 创建代码索引管理器
        manager = CodeIndexManager.get_instance(workspace_path)
        if not manager:
            print("❌ 无法创建代码索引管理器")
            return
        
        # 扫描代码文件
        code_files = await scan_code_files(workspace_path)
        
        if not code_files:
            print("⚠️ 未找到需要索引的代码文件")
            return
        
        # 初始化
        print("🚀 正在初始化代码索引管理器...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("❌ 错误: 功能未启用")
            return
            
        if not manager.is_feature_configured:
            print("❌ 错误: 配置不完整")
            return
        
        print(f"✅ 管理器初始化成功: {init_result}")
        print(f"📊 向量存储: Milvus")
        print(f"🤖 嵌入器: OpenAI ({config['openai_model']})")
        print(f"📁 待索引文件: {len(code_files)} 个")
        
        # 监听进度更新
        async def monitor_progress():
            try:
                while True:
                    await manager.on_progress_update.wait()
                    status = manager.get_current_status()
                    
                    print(f"\n📊 进度更新:")
                    print(f"   状态: {status['state']}")
                    if status.get('message'):
                        print(f"   消息: {status['message']}")
                    
                    progress = status.get('progress', {})
                    if 'current' in progress and 'total' in progress:
                        current = progress['current']
                        total = progress['total']
                        percentage = (current / total * 100) if total > 0 else 0
                        print(f"   文件进度: {current}/{total} ({percentage:.1f}%)")
                        
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
        
        # 启动索引
        print(f"\n🚀 开始索引到Milvus向量数据库...")
        await manager.start_indexing()
        
        # 等待索引完成
        print("⏳ 等待索引完成...")
        max_wait_time = 300  # 最多等待5分钟
        wait_time = 0
        while manager.state == IndexingState.INDEXING and wait_time < max_wait_time:
            await asyncio.sleep(2)
            wait_time += 2
            
        progress_task.cancel()
        
        if manager.state == IndexingState.INDEXED:
            print("✅ 索引完成!")
            
            # 搜索示例
            print("\n🔍 执行Milvus搜索测试...")
            search_queries = [
                "CodeIndexManager class",
                "milvus vector store",
                "async function definition",
                "tree sitter parser",
                "embedding model",
                "vector search"
            ]
            
            for query in search_queries:
                print(f"\n搜索: '{query}'")
                try:
                    results = await manager.search_index(query, directory_prefix=workspace_path)
                    
                    if results:
                        print(f"  🎯 找到 {len(results)} 个结果:")
                        for i, result in enumerate(results[:3], 1):
                            payload = result.payload
                            file_path = payload.get('filePath', 'Unknown')
                            rel_path = os.path.relpath(file_path, workspace_path) if file_path != 'Unknown' else 'Unknown'
                            
                            print(f"    {i}. 📄 {rel_path}")
                            print(f"       📍 行: {payload.get('startLine', 'N/A')}-{payload.get('endLine', 'N/A')}")
                            print(f"       🎯 相似度: {result.score:.3f}")
                            print(f"       📝 类型: {payload.get('type', 'N/A')}")
                            
                            # 显示代码预览
                            content = payload.get('codeChunk', '')
                            if content:
                                preview = content[:100].replace('\n', '\\n')
                                print(f"       💡 预览: {preview}...")
                    else:
                        print("  ❌ 未找到相关结果")
                        
                except Exception as e:
                    print(f"  ⚠️ 搜索失败: {e}")
        
        elif manager.state == IndexingState.ERROR:
            print("❌ 索引过程出现错误")
            status = manager.get_current_status()
            print(f"错误信息: {status['message']}")
        else:
            print(f"⏸️ 索引未完成，当前状态: {manager.state}")
            
        # 获取当前状态
        final_status = manager.get_current_status()
        print(f"\n📋 最终状态: {final_status}")
        
    except Exception as e:
        print(f"💥 示例执行失败: {e}")
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
            print("❌ 无法创建代码索引管理器")
            return
        
        print("🚀 正在初始化Milvus + Ollama配置...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("❌ 错误: 功能未启用")
            return
            
        if not manager.is_feature_configured:
            print("❌ 错误: 配置不完整，请确保Ollama服务正在运行")
            return
        
        print(f"✅ Milvus + Ollama初始化成功: {init_result}")
        print(f"📊 向量存储: Milvus")
        print(f"🤖 嵌入器: Ollama (nomic-embed-text)")
        
        # 扫描代码文件
        code_files = await scan_code_files(workspace_path)
        print(f"📁 发现 {len(code_files)} 个代码文件")
        
        # 获取状态
        status = manager.get_current_status()
        print(f"📊 管理器状态: {status}")
        
        print("✅ Milvus + Ollama配置验证成功!")
        
    except Exception as e:
        print(f"💥 示例执行失败: {e}")
        print("💡 请确保以下服务正在运行:")
        print("   - Milvus: http://localhost:19530")
        print("   - Ollama: http://localhost:11434")
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
        print("⏭️ 跳过系统操作示例: 需要OPENAI_API_KEY")
        return
    
    workspace_path = os.getcwd()
    
    try:
        manager = CodeIndexManager.get_instance(workspace_path)
        if not manager:
            print("❌ 无法创建代码索引管理器")
            return
        
        # 初始化计时
        import time
        start_time = time.time()
        await manager.initialize(config)
        init_time = time.time() - start_time
        print(f"⏱️ 初始化耗时: {init_time:.2f}秒")
        
        # 系统状态检查
        print("\n📊 系统状态检查:")
        print(f"  功能启用: {'✅' if manager.is_feature_enabled else '❌'}")
        print(f"  功能配置: {'✅' if manager.is_feature_configured else '❌'}")
        print(f"  已初始化: {'✅' if manager.is_initialized else '❌'}")
        print(f"  当前状态: {manager.state}")
        
        # 清空索引数据测试
        if manager.is_feature_enabled and manager.is_initialized:
            print("\n🗑️ 测试清空索引数据...")
            await manager.clear_index_data()
            print("✅ 索引数据清空完成")
        
        # 停止监听器测试
        print("\n🛑 测试停止文件监听器...")
        await manager.stop_watcher()
        print("✅ 文件监听器已停止")
        
        # 设置变更处理测试
        print("\n⚙️ 测试设置变更处理...")
        await manager.handle_settings_change()
        print("✅ 设置变更处理完成")
        
        print("\n✅ Milvus系统操作示例完成")
        
    except Exception as e:
        print(f"💥 系统操作示例失败: {e}")
    finally:
        if 'manager' in locals():
            manager.dispose()


async def demonstrate_milvus_code_parsing():
    """演示Milvus下的代码解析"""
    print("\n=== Milvus代码解析演示 ===")
    
    workspace_path = os.getcwd()
    parser = CodeParser()
    
    # 扫描代码文件
    code_files = await scan_code_files(workspace_path)
    
    if not code_files:
        print("⚠️ 未找到代码文件")
        return
    
    # 演示解析几个文件
    demo_files = code_files[:2]  # 解析前2个文件
    
    print(f"\n🔍 解析代码文件演示:")
    total_blocks = 0
    
    for file_path in demo_files:
        rel_path = os.path.relpath(file_path, workspace_path)
        print(f"\n📄 解析文件: {rel_path}")
        
        try:
            blocks = await parser.parse_file(file_path)
            print(f"   📊 发现 {len(blocks)} 个代码块")
            total_blocks += len(blocks)
            
            # 显示前几个代码块的信息
            for i, block in enumerate(blocks[:2], 1):
                print(f"     {i}. [{block.type}] {block.identifier or '未命名'}")
                print(f"        📍 行: {block.start_line}-{block.end_line}")
                print(f"        📏 长度: {len(block.content)} 字符")
                
                # 显示代码预览
                preview = block.content[:80].replace('\n', '\\n')
                print(f"        💡 预览: {preview}...")
                
        except Exception as e:
            print(f"   ❌ 解析失败: {e}")
    
    print(f"\n📊 总计发现 {total_blocks} 个代码块")


def print_milvus_setup_instructions():
    """打印Milvus安装配置说明"""
    print("""
=== Milvus安装配置说明 ===

1. 使用Docker安装Milvus (推荐):
   ```bash
   # 下载并启动Milvus standalone
   docker run -d --name milvus \\
     -p 19530:19530 \\
     -p 9091:9091 \\
     -v milvus_data:/var/lib/milvus \\
     milvusdb/milvus:latest
   ```

2. 或使用Docker Compose:
   ```bash
   # 下载docker-compose.yml
   wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
   
   # 启动Milvus
   docker-compose up -d
   ```

3. 安装Python依赖:
   ```bash
   pip install pymilvus
   ```

4. 验证Milvus服务:
   - API端口: 19530
   - Web UI: http://localhost:9091 (如果安装了Attu)
   - 健康检查: curl http://localhost:9091/health

5. 环境变量设置:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

6. 可选配置:
   - 如果使用认证，设置milvus_user和milvus_password
   - 可以修改milvus_host和milvus_port连接远程Milvus

更多信息请参考: https://milvus.io/docs
""")


async def main():
    """主函数"""
    print("🚀 代码索引系统 - Milvus向量数据库示例")
    print("="*60)
    print(f"📁 工作空间路径: {os.getcwd()}")
    print("="*60)
    
    # 打印设置说明
    print_milvus_setup_instructions()
    
    # 演示代码解析
    await demonstrate_milvus_code_parsing()
    
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
    
    print("\n" + "="*60)
    print("✅ 所有Milvus示例执行完成")
    print("\n📋 使用说明:")
    print("1. 🔧 确保Milvus服务正在运行: docker run -p 19530:19530 milvusdb/milvus:latest")
    print("2. 🔑 设置API密钥: export OPENAI_API_KEY='your-key'")
    print("3. 🐍 安装依赖: pip install -r requirements.txt")
    print("4. 📊 根据需要调整配置参数")


if __name__ == "__main__":
    asyncio.run(main())