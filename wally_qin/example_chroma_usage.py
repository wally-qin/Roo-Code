#!/usr/bin/env python3
"""
Chroma向量存储使用示例

演示如何使用ChromaVectorStore和CodeIndexManager进行代码索引和搜索。
参照CodeIndexManager的实际实现，确保所有方法调用和参数都是正确的。

此示例将真正遍历wally_qin目录下的所有代码文件，解析代码块，并存储到Chroma向量数据库中。
"""

import asyncio
import os
import tempfile
from typing import List, Optional, Dict
import numpy as np
from pathlib import Path

from code_index.managers.code_index_manager import CodeIndexManager
from code_index.interfaces import IndexingState, PointStruct
from code_index.processors.code_parser import CodeParser
from code_index.vector_store.chroma_client import ChromaVectorStore
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
            "filePath": "/workspace/wally_qin/code_index/managers/code_index_manager.py",
            "codeChunk": "def initialize(self, config: Optional[Dict] = None) -> Dict[str, bool]:",
            "startLine": 10,
            "endLine": 12,
            "segmentHash": "abc123",
            "type": "function"
        },
        {
            "filePath": "/workspace/wally_qin/example_usage.py",
            "codeChunk": "async def example_basic_usage():\n    \"\"\"基础代码索引系统使用示例\"\"\"",
            "startLine": 25,
            "endLine": 27,
            "segmentHash": "def456",
            "type": "function"
        },
        {
            "filePath": "/workspace/wally_qin/code_index/interfaces/__init__.py",
            "codeChunk": "class IndexingState(Enum):\n    \"\"\"索引状态枚举\"\"\"\n    STANDBY = \"Standby\"",
            "startLine": 5,
            "endLine": 9,
            "segmentHash": "ghi789",
            "type": "class"
        }
    ]
    
    for i, (vector, payload) in enumerate(zip(sample_vectors, sample_payloads)):
        points.append(PointStruct(
            id=f"point_{i}",
            vector=vector,
            payload=payload
        ))
    
    return points


async def example_chroma_basic_operations():
    """演示Chroma基本操作"""
    print("=== Chroma基本操作演示 ===\n")
    
    # 创建临时目录用于Chroma持久化
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_persist_dir = os.path.join(temp_dir, "chroma_db")
        
        # 初始化Chroma向量存储
        chroma_store = ChromaVectorStore(
            workspace_path=os.getcwd(),
            persist_directory=chroma_persist_dir,
            vector_size=1536
        )
        
        try:
            # 1. 初始化
            print("1. 🔌 初始化Chroma向量存储...")
            created = await chroma_store.initialize()
            print(f"   集合创建: {'✅ 是' if created else '🔄 否（使用现有）'}")
            
            # 2. 插入向量点
            print("2. 📥 插入示例向量点...")
            points = await create_sample_points()
            await chroma_store.upsert_points(points)
            print(f"   ✅ 成功插入 {len(points)} 个向量点")
            
            # 3. 搜索相似向量
            print("3. 🔍 搜索相似向量...")
            query_vector = np.random.rand(1536).tolist()
            results = await chroma_store.search(
                query_vector=query_vector,
                max_results=3,
                min_score=0.0
            )
            
            print(f"   📊 找到 {len(results)} 个结果:")
            for i, result in enumerate(results):
                payload = result.payload
                print(f"   [{i+1}] ID: {result.id}, Score: {result.score:.4f}")
                print(f"       📄 文件: {payload.get('filePath', 'N/A')}")
                print(f"       🏷️ 类型: {payload.get('type', 'N/A')}")
                print(f"       📍 行数: {payload.get('startLine', 'N/A')}-{payload.get('endLine', 'N/A')}")
                print()
            
            # 4. 根据目录前缀搜索
            print("4. 📂 根据目录前缀搜索...")
            filtered_results = await chroma_store.search(
                query_vector=query_vector,
                directory_prefix="/workspace/wally_qin/code_index",
                max_results=5
            )
            print(f"   🎯 在 code_index 目录下找到 {len(filtered_results)} 个结果")
            
            # 5. 删除特定文件的向量点
            print("5. 🗑️ 删除特定文件的向量点...")
            await chroma_store.delete_points_by_file_path("/workspace/wally_qin/example_usage.py")
            print("   ✅ 已删除 example_usage.py 的向量点")
            
            # 6. 验证删除结果
            print("6. ✅ 验证删除结果...")
            all_results = await chroma_store.search(
                query_vector=query_vector,
                max_results=10,
                min_score=0.0
            )
            print(f"   📊 剩余向量点数量: {len(all_results)}")
            
            print("✅ Chroma基本操作演示完成！")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            # 清理
            try:
                await chroma_store.delete_collection()
                print("🧹 已清理Chroma集合")
            except:
                pass


async def demonstrate_chroma_code_parsing():
    """演示Chroma下的代码解析"""
    print("\n=== Chroma代码解析演示 ===")
    
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


async def example_chroma_with_manager():
    """使用CodeIndexManager的Chroma完整示例"""
    print("\n=== 使用CodeIndexManager的Chroma完整示例 ===\n")
    
    # 创建临时目录用于Chroma持久化
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_persist_dir = os.path.join(temp_dir, "chroma_db")
        
        # Chroma配置
        config = {
            "enabled": True,
            "vector_store": "chroma",
            "chroma_persist_directory": chroma_persist_dir,
            
            # 嵌入器配置
            "embedder_provider": "openai",
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "openai_model": "text-embedding-3-small",
            
            # 搜索配置
            "search_min_score": 0.7,
            "search_max_results": 20,
        }
        
        if not config["openai_api_key"]:
            print("❌ 错误: 请设置OPENAI_API_KEY环境变量")
            print("💡 可以使用: export OPENAI_API_KEY='your-api-key'")
            return
        
        workspace_path = os.getcwd()
        
        try:
            # 扫描代码文件
            code_files = await scan_code_files(workspace_path)
            
            if not code_files:
                print("⚠️ 未找到需要索引的代码文件")
                return
            
            # 创建代码索引管理器
            manager = CodeIndexManager.get_instance(workspace_path)
            if not manager:
                print("❌ 无法创建代码索引管理器")
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
            print(f"📊 向量存储: Chroma (持久化)")
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
            print(f"\n🚀 开始索引到Chroma向量数据库...")
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
                print("\n🔍 执行Chroma搜索测试...")
                search_queries = [
                    "CodeIndexManager class",
                    "chroma vector store",
                    "async function definition",
                    "tree sitter parser",
                    "embedding model",
                    "index initialization"
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


async def example_chroma_with_ollama():
    """Chroma + Ollama本地嵌入器示例"""
    print("\n=== Chroma + Ollama本地嵌入器示例 ===\n")
    
    # 创建临时目录用于Chroma持久化
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_persist_dir = os.path.join(temp_dir, "chroma_db")
        
        # Chroma + Ollama配置
        config = {
            "enabled": True,
            "vector_store": "chroma",
            "chroma_persist_directory": chroma_persist_dir,
            
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
            
            print("🚀 正在初始化Chroma + Ollama配置...")
            init_result = await manager.initialize(config)
            
            if not manager.is_feature_enabled:
                print("❌ 错误: 功能未启用")
                return
                
            if not manager.is_feature_configured:
                print("❌ 错误: 配置不完整，请确保Ollama服务正在运行")
                return
            
            print(f"✅ Chroma + Ollama初始化成功: {init_result}")
            print(f"📊 向量存储: Chroma")
            print(f"🤖 嵌入器: Ollama (nomic-embed-text)")
            
            # 扫描代码文件
            code_files = await scan_code_files(workspace_path)
            print(f"📁 发现 {len(code_files)} 个代码文件")
            
            # 获取状态
            status = manager.get_current_status()
            print(f"📊 管理器状态: {status}")
            
            print("✅ Chroma + Ollama配置验证成功!")
            
        except Exception as e:
            print(f"💥 示例执行失败: {e}")
            print("💡 请确保Ollama服务正在运行:")
            print("   - Ollama: http://localhost:11434")
        finally:
            if 'manager' in locals():
                manager.dispose()


async def example_chroma_memory_mode():
    """演示Chroma内存模式"""
    print("\n=== Chroma内存模式演示 ===\n")
    
    # 内存模式配置（不提供持久化目录）
    config = {
        "enabled": True,
        "vector_store": "chroma",
        # 不设置chroma_persist_directory，使用内存模式
        
        "embedder_provider": "openai",
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": "text-embedding-3-small",
    }
    
    if not config["openai_api_key"]:
        print("⏭️ 跳过内存模式示例: 需要OPENAI_API_KEY")
        return
    
    workspace_path = os.getcwd()
    
    try:
        manager = CodeIndexManager.get_instance(workspace_path)
        if not manager:
            print("❌ 无法创建代码索引管理器")
            return
        
        print("🚀 正在初始化Chroma内存模式...")
        init_result = await manager.initialize(config)
        
        if not manager.is_feature_enabled:
            print("❌ 错误: 功能未启用")
            return
            
        if not manager.is_feature_configured:
            print("❌ 错误: 配置不完整")
            return
        
        print(f"✅ Chroma内存模式初始化成功: {init_result}")
        print(f"📊 向量存储: Chroma (内存模式)")
        
        # 扫描代码文件
        code_files = await scan_code_files(workspace_path)
        print(f"📁 发现 {len(code_files)} 个代码文件")
        
        # 获取状态
        status = manager.get_current_status()
        print(f"📊 管理器状态: {status}")
        
        print("⚠️ 注意：内存模式数据不会持久化，程序结束后数据丢失")
        
    except Exception as e:
        print(f"💥 内存模式示例失败: {e}")
    finally:
        if 'manager' in locals():
            manager.dispose()


async def example_chroma_system_operations():
    """Chroma系统操作示例"""
    print("\n=== Chroma系统操作示例 ===\n")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        chroma_persist_dir = os.path.join(temp_dir, "chroma_db")
        
        config = {
            "enabled": True,
            "vector_store": "chroma",
            "chroma_persist_directory": chroma_persist_dir,
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
            
            print("\n✅ Chroma系统操作示例完成")
            
        except Exception as e:
            print(f"💥 系统操作示例失败: {e}")
        finally:
            if 'manager' in locals():
                manager.dispose()


def print_chroma_setup_instructions():
    """打印Chroma安装配置说明"""
    print("""
=== Chroma安装配置说明 ===

1. 安装Chroma:
   ```bash
   pip install chromadb
   ```

2. Chroma的两种模式:
   - 内存模式: 数据存储在内存中，程序结束后丢失
   - 持久化模式: 数据持久化到磁盘

3. 环境变量设置:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

4. 配置选项:
   - chroma_persist_directory: 持久化目录路径（可选）
   - chroma_host: Chroma服务器地址（如果使用远程服务）
   - chroma_port: Chroma服务器端口

5. 优势:
   - 💡 易于安装和使用
   - 🏠 支持本地部署
   - 🐍 良好的Python集成
   - 🔄 支持多种嵌入模型
   - ⚡ 无需额外服务器配置

更多信息请参考: https://docs.trychroma.com/
""")


async def main():
    """主函数"""
    print("🚀 代码索引系统 - Chroma向量存储演示程序")
    print("=" * 60)
    print(f"📁 工作空间路径: {os.getcwd()}")
    print("=" * 60)
    
    # 打印设置说明
    print_chroma_setup_instructions()
    
    # 演示代码解析
    await demonstrate_chroma_code_parsing()
    
    # 演示基本操作
    await example_chroma_basic_operations()
    
    # 演示完整的管理器集成
    await example_chroma_with_manager()
    
    # 演示Ollama集成
    await example_chroma_with_ollama()
    
    # 演示内存模式
    await example_chroma_memory_mode()
    
    # 演示系统操作
    await example_chroma_system_operations()
    
    # 释放所有实例
    CodeIndexManager.dispose_all()
    
    print("\n" + "=" * 60)
    print("✅ 所有演示完成！")
    print("\n📋 使用说明:")
    print("- 🏠 Chroma支持持久化模式和内存模式")
    print("- 🔄 可以与Qdrant和Milvus同时使用，互不干扰")
    print("- 🔀 提供与其他向量存储相同的接口，便于切换")
    print("- 🔍 支持目录前缀过滤和相似度阈值搜索")
    print("- ⚡ 易于部署，无需额外的服务器配置")
    print("- 🔑 设置API密钥: export OPENAI_API_KEY='your-key'")
    print("- 🐍 安装依赖: pip install -r requirements.txt")


if __name__ == "__main__":
    asyncio.run(main())