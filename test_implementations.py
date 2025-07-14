#!/usr/bin/env python3
"""
测试新实现的代码索引组件

这个脚本测试我们新实现的组件是否能正常工作。
"""

import asyncio
import os
import sys
import tempfile
import logging

# 添加项目路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wally_qin'))

from code_index.processors import CodeParser, DirectoryScanner, FileWatcher
from code_index.embedders import OpenAIEmbedder, OllamaEmbedder, GeminiEmbedder, OpenAICompatibleEmbedder
from code_index.managers.cache_manager import CacheManager
from code_index.managers.config_manager import CodeIndexConfigManager
from code_index.service_factory import CodeIndexServiceFactory

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_code_parser():
    """测试代码解析器"""
    logger.info("=== 测试代码解析器 ===")
    
    parser = CodeParser()
    
    # 创建测试Python文件
    test_code = '''
def hello_world():
    """Say hello to the world."""
    print("Hello, World!")

class TestClass:
    def __init__(self):
        self.name = "test"
        
    def get_name(self):
        return self.name
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_code)
        temp_file = f.name
    
    try:
        # 解析文件
        blocks = await parser.parse_file(temp_file)
        logger.info(f"解析得到 {len(blocks)} 个代码块")
        
        for i, block in enumerate(blocks):
            logger.info(f"块 {i+1}: {block.type} ({block.start_line}-{block.end_line})")
            if block.identifier:
                logger.info(f"  标识符: {block.identifier}")
                
        return len(blocks) > 0
        
    finally:
        os.unlink(temp_file)


async def test_embedders():
    """测试嵌入器"""
    logger.info("=== 测试嵌入器 ===")
    
    test_texts = ["def hello(): pass", "class MyClass: pass"]
    
    # 测试 OpenAI 嵌入器（需要API密钥）
    if os.getenv('OPENAI_API_KEY'):
        try:
            logger.info("测试 OpenAI 嵌入器...")
            embedder = OpenAIEmbedder(api_key=os.getenv('OPENAI_API_KEY'))
            validation = await embedder.validate_configuration()
            logger.info(f"OpenAI 嵌入器验证: {validation}")
            
            if validation['valid']:
                response = await embedder.create_embeddings(test_texts)
                logger.info(f"OpenAI 嵌入成功: {len(response.embeddings)} 个向量")
        except Exception as e:
            logger.error(f"OpenAI 嵌入器测试失败: {e}")
    else:
        logger.info("跳过 OpenAI 测试 (未设置 OPENAI_API_KEY)")
    
    # 测试 Ollama 嵌入器（需要本地Ollama服务）
    try:
        logger.info("测试 Ollama 嵌入器...")
        embedder = OllamaEmbedder(base_url="http://localhost:11434")
        validation = await embedder.validate_configuration()
        logger.info(f"Ollama 嵌入器验证: {validation}")
        
        if validation['valid']:
            response = await embedder.create_embeddings(test_texts)
            logger.info(f"Ollama 嵌入成功: {len(response.embeddings)} 个向量")
    except Exception as e:
        logger.error(f"Ollama 嵌入器测试失败: {e}")
    
    # 测试 Gemini 嵌入器（需要API密钥）
    if os.getenv('GEMINI_API_KEY'):
        try:
            logger.info("测试 Gemini 嵌入器...")
            embedder = GeminiEmbedder(api_key=os.getenv('GEMINI_API_KEY'))
            validation = await embedder.validate_configuration()
            logger.info(f"Gemini 嵌入器验证: {validation}")
            
            if validation['valid']:
                response = await embedder.create_embeddings(test_texts)
                logger.info(f"Gemini 嵌入成功: {len(response.embeddings)} 个向量")
        except Exception as e:
            logger.error(f"Gemini 嵌入器测试失败: {e}")
    else:
        logger.info("跳过 Gemini 测试 (未设置 GEMINI_API_KEY)")
    
    return True


async def test_service_factory():
    """测试服务工厂"""
    logger.info("=== 测试服务工厂 ===")
    
    # 创建测试配置
    test_config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": os.getenv('OPENAI_API_KEY', 'test-key'),
        "qdrant_url": "http://localhost:6333"
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            config_manager = CodeIndexConfigManager(test_config)
            cache_manager = CacheManager(temp_dir)
            await cache_manager.initialize()
            
            factory = CodeIndexServiceFactory(config_manager, temp_dir, cache_manager)
            
            # 测试创建服务（不执行实际API调用）
            config = config_manager.get_config()
            
            # 测试嵌入器创建
            try:
                embedder = factory._create_embedder(config)
                logger.info(f"成功创建嵌入器: {embedder.embedder_info}")
            except Exception as e:
                logger.error(f"创建嵌入器失败: {e}")
            
            # 测试代码解析器创建
            parser = factory._create_code_parser()
            logger.info(f"成功创建代码解析器: {type(parser).__name__}")
            
            return True
            
        except Exception as e:
            logger.error(f"服务工厂测试失败: {e}")
            return False


async def test_directory_scanner():
    """测试目录扫描器"""
    logger.info("=== 测试目录扫描器 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试文件
        test_files = {
            'test1.py': 'def func1(): pass',
            'test2.js': 'function func2() {}',
            'test3.md': '# Title\n\nContent here.',
            'ignore.pyc': 'binary content',  # 应该被忽略
        }
        
        for filename, content in test_files.items():
            with open(os.path.join(temp_dir, filename), 'w') as f:
                f.write(content)
        
        try:
            # 创建必要的组件
            cache_manager = CacheManager(temp_dir)
            await cache_manager.initialize()
            
            parser = CodeParser()
            
            # 创建模拟嵌入器和向量存储（不执行实际操作）
            class MockEmbedder:
                async def create_embeddings(self, texts):
                    from code_index.interfaces import EmbeddingResponse
                    return EmbeddingResponse(
                        embeddings=[[0.1] * 10 for _ in texts],
                        usage={'prompt_tokens': len(texts), 'total_tokens': len(texts)}
                    )
            
            class MockVectorStore:
                async def upsert_points(self, points):
                    pass
            
            scanner = DirectoryScanner(
                embedder=MockEmbedder(),
                vector_store=MockVectorStore(),
                code_parser=parser,
                cache_manager=cache_manager
            )
            
            # 扫描目录
            result = await scanner.scan_directory(temp_dir)
            logger.info(f"扫描结果: 处理了 {result['stats']['processed']} 个文件")
            logger.info(f"跳过了 {result['stats']['skipped']} 个文件")
            logger.info(f"总共 {result['totalBlockCount']} 个代码块")
            
            return result['stats']['processed'] > 0
            
        except Exception as e:
            logger.error(f"目录扫描器测试失败: {e}")
            return False


async def main():
    """运行所有测试"""
    logger.info("开始测试新实现的代码索引组件...")
    
    tests = [
        ("代码解析器", test_code_parser),
        ("嵌入器", test_embedders),
        ("服务工厂", test_service_factory),
        ("目录扫描器", test_directory_scanner),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n开始测试: {test_name}")
            result = await test_func()
            results[test_name] = result
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{test_name}: {status}")
        except Exception as e:
            logger.error(f"{test_name} 测试异常: {e}")
            results[test_name] = False
    
    # 总结
    logger.info("\n=== 测试总结 ===")
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试都通过了！")
        return True
    else:
        logger.info("⚠️  有一些测试失败")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)