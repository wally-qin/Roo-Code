# 代码索引系统 (Python版)

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 概述

这是一个完整的代码索引系统的Python实现，基于原TypeScript项目重新开发。该系统能够分析、嵌入和搜索代码库，支持多种编程语言和AI嵌入模型。

## 主要特性

- 🚀 **多语言支持**: 支持40+种编程语言，包括Python、JavaScript、TypeScript、Java、Go、Rust等
- 🧠 **多种AI模型**: 支持OpenAI、Ollama、OpenAI Compatible和Gemini嵌入模型
- 🔍 **智能搜索**: 基于语义相似度的代码搜索功能
- 📁 **增量索引**: 智能检测文件变化，只处理修改过的文件
- ⚡ **异步处理**: 高性能的异步批处理和并发处理
- 🏗️ **模块化设计**: 完全模块化的架构，易于扩展和维护
- 📊 **向量存储**: 支持Qdrant、Milvus和Chroma作为高性能向量数据库

## 架构组件

### 核心组件

- **代码解析器**: 使用tree-sitter解析多种编程语言
- **嵌入器**: 支持多种AI模型进行代码嵌入
- **向量存储**: 使用Qdrant存储和搜索向量
- **文件监控**: 实时监控文件变化并更新索引
- **配置管理**: 灵活的配置系统支持多种嵌入模型

### 支持的语言

```
.py, .js, .jsx, .ts, .tsx, .vue, .java, .go, .rs, .c, .h, .cpp, .hpp, 
.cs, .rb, .php, .swift, .sol, .kt, .kts, .ex, .exs, .el, .html, .htm, 
.md, .markdown, .json, .css, .ml, .mli, .lua, .scala, .toml, .zig, .elm
```

## 安装

### 1. 安装依赖

```bash
cd wally_qin
pip install -r requirements.txt
```

### 2. 启动向量数据库

#### 选项A: 使用Qdrant (默认)

使用Docker启动Qdrant向量数据库：

```bash
docker run -p 6333:6333 qdrant/qdrant
```

或使用docker-compose：

```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```

#### 选项B: 使用Milvus

使用Docker Compose启动Milvus：

```bash
# 下载Milvus配置文件
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

# 启动Milvus
docker-compose up -d
```

或者单独运行：

```bash
docker run -p 19530:19530 -p 9091:9091 \
  -v /path/to/milvus:/var/lib/milvus \
  milvusdb/milvus:latest
```

#### 选项C: 使用Chroma

Chroma支持多种运行模式：

1. **内存模式** (无需额外配置，数据不持久化)
2. **持久化模式** (本地文件系统存储)
3. **客户端-服务器模式** (需要启动Chroma服务器)

启动Chroma服务器 (可选):

```bash
# 安装Chroma服务器
pip install chromadb[server]

# 启动服务器
chroma run --host localhost --port 8000
```

或使用Docker：

```bash
docker run -p 8000:8000 chromadb/chroma:latest
```

### 3. 配置环境

创建`.env`文件：

```env
# OpenAI配置
OPENAI_API_KEY=your-openai-api-key

# Ollama配置 (可选)
OLLAMA_BASE_URL=http://localhost:11434

# 向量数据库配置 (选择一种)
# Qdrant配置
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # 可选

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=  # 可选
MILVUS_PASSWORD=  # 可选

# Chroma配置
CHROMA_HOST=localhost  # 可选，用于客户端-服务器模式
CHROMA_PORT=8000  # 可选，用于客户端-服务器模式
CHROMA_PERSIST_DIRECTORY=/path/to/chroma/data  # 可选，用于持久化模式
```

## 快速开始

### 基本使用

```python
import asyncio
from code_index import CodeIndexManager

async def main():
    # 配置
    config = {
        "enabled": True,
        "embedder_provider": "openai",
        "openai_api_key": "your-api-key",
        "qdrant_url": "http://localhost:6333",
        "search_min_score": 0.7
    }
    
    # 获取管理器实例
    manager = CodeIndexManager.get_instance("/path/to/your/project")
    
    # 初始化
    await manager.initialize(config)
    
    # 启动索引
    await manager.start_indexing()
    
    # 搜索代码
    results = await manager.search_index("function definition")
    
    for result in results:
        print(f"文件: {result.payload['filePath']}")
        print(f"行号: {result.payload['startLine']}-{result.payload['endLine']}")
        print(f"相似度: {result.score}")
        print(f"代码: {result.payload['codeChunk'][:100]}...")

asyncio.run(main())
```

### 使用Ollama

```python
config = {
    "enabled": True,
    "embedder_provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "model_id": "nomic-embed-text",
    "qdrant_url": "http://localhost:6333"
}
```

### 使用Milvus

```python
config = {
    "enabled": True,
    "embedder_provider": "openai",
    "openai_api_key": "your-api-key",
    "vector_store": "milvus",
    "milvus_host": "localhost",
    "milvus_port": "19530",
    "search_min_score": 0.7
}
```

### 使用Chroma

```python
# 持久化模式
config = {
    "enabled": True,
    "embedder_provider": "openai",
    "openai_api_key": "your-api-key",
    "vector_store": "chroma",
    "chroma_persist_directory": "/path/to/chroma/data",
    "search_min_score": 0.7
}

# 客户端-服务器模式
config = {
    "enabled": True,
    "embedder_provider": "openai",
    "openai_api_key": "your-api-key",
    "vector_store": "chroma",
    "chroma_host": "localhost",
    "chroma_port": 8000,
    "search_min_score": 0.7
}

# 内存模式 (默认)
config = {
    "enabled": True,
    "embedder_provider": "openai",
    "openai_api_key": "your-api-key",
    "vector_store": "chroma",
    "search_min_score": 0.7
}
```

## 详细使用说明

### 配置选项

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | true | 是否启用代码索引 |
| `embedder_provider` | str | "openai" | 嵌入器提供商 |
| `vector_store` | str | "qdrant" | 向量数据库类型 (qdrant/milvus/chroma) |
| `openai_api_key` | str | - | OpenAI API密钥 |
| `ollama_base_url` | str | "http://localhost:11434" | Ollama服务地址 |
| `model_id` | str | - | 模型ID |
| `qdrant_url` | str | "http://localhost:6333" | Qdrant服务地址 |
| `qdrant_api_key` | str | - | Qdrant API密钥 |
| `milvus_host` | str | "localhost" | Milvus服务器地址 |
| `milvus_port` | str | "19530" | Milvus服务器端口 |
| `milvus_user` | str | - | Milvus用户名 (可选) |
| `milvus_password` | str | - | Milvus密码 (可选) |
| `chroma_host` | str | - | Chroma服务器地址 (客户端-服务器模式) |
| `chroma_port` | int | 8000 | Chroma服务器端口 (客户端-服务器模式) |
| `chroma_persist_directory` | str | - | Chroma持久化目录 (持久化模式) |
| `search_min_score` | float | 0.7 | 搜索最小相似度 |
| `search_max_results` | int | 100 | 搜索最大结果数 |

### 支持的嵌入模型

#### OpenAI模型
- `text-embedding-3-small` (1536维)
- `text-embedding-3-large` (3072维) 
- `text-embedding-ada-002` (1536维)

#### Ollama模型
- `nomic-embed-text` (768维)
- `all-minilm` (384维)

#### Gemini模型
- `models/embedding-001` (768维)

### 监控进度

```python
async def monitor_indexing_progress(manager):
    while True:
        await manager.on_progress_update.wait()
        status = manager.get_current_status()
        print(f"状态: {status['state']}")
        print(f"进度: {status['progress']}")
        
        if status['state'] in ['Indexed', 'Error']:
            break

# 启动监控
asyncio.create_task(monitor_indexing_progress(manager))
```

### 高级搜索

```python
# 带目录过滤的搜索
results = await manager.search_index(
    query="error handling",
    directory_prefix="src/utils"
)

# 自定义搜索参数 
results = await manager.search_index(
    query="async function",
    # 通过配置设置最小分数和最大结果数
)
```

### 清空索引

```python
# 清空所有索引数据
await manager.clear_index_data()

# 重新开始索引
await manager.start_indexing()
```

## API参考

### CodeIndexManager

主要的管理器类，提供代码索引系统的核心功能。

#### 方法

- `get_instance(workspace_path)`: 获取单例实例
- `initialize(config)`: 初始化系统
- `start_indexing()`: 开始索引
- `stop_watcher()`: 停止文件监听
- `search_index(query, directory_prefix)`: 搜索代码
- `clear_index_data()`: 清空索引数据
- `dispose()`: 释放资源

#### 属性

- `state`: 当前索引状态
- `is_feature_enabled`: 功能是否启用
- `is_feature_configured`: 是否已配置
- `on_progress_update`: 进度更新事件

### 索引状态

- `STANDBY`: 待机状态
- `INDEXING`: 正在索引
- `INDEXED`: 索引完成
- `ERROR`: 错误状态

## 性能优化

### 批处理配置

系统默认使用批处理来优化性能：

- 批处理大小: 60个代码段
- 并发解析: 10个文件
- 批处理并发: 10个批次
- 重试机制: 最多3次重试

### 文件大小限制

- 最大文件大小: 1MB
- 最大代码块: 1000字符
- 最小代码块: 50字符

### 内存优化

- 增量索引: 只处理变更的文件
- 哈希缓存: 避免重复处理
- 异步处理: 避免阻塞操作

## 故障排除

### 常见问题

1. **Qdrant连接失败**
   ```
   确保Qdrant服务正在运行: docker run -p 6333:6333 qdrant/qdrant
   ```

2. **Milvus连接失败**
   ```
   确保Milvus服务正在运行
   检查端口19530是否可访问
   验证用户名和密码（如果设置了认证）
   ```

3. **OpenAI API错误**
   ```
   检查API密钥是否正确设置
   确认账户有足够的使用额度
   ```

4. **Ollama连接失败**
   ```
   确保Ollama服务运行: ollama serve
   检查模型是否已下载: ollama pull nomic-embed-text
   ```

5. **Chroma连接失败**
   ```
   客户端-服务器模式: 确保Chroma服务器正在运行
   持久化模式: 检查目录权限和磁盘空间
   内存模式: 检查可用内存是否足够
   ```

6. **内存不足**
   ```
   减少批处理大小和并发数
   限制索引的文件类型和大小
   使用Chroma持久化模式而不是内存模式
   ```

### 日志配置

```python
import logging

# 启用详细日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('code_index')
logger.setLevel(logging.DEBUG)
```

## 扩展开发

### 添加新的嵌入器

```python
from code_index.interfaces import IEmbedder, EmbeddingResponse

class CustomEmbedder(IEmbedder):
    async def create_embeddings(self, texts, model=None):
        # 实现自定义嵌入逻辑
        pass
    
    async def validate_configuration(self):
        # 实现配置验证
        pass
    
    @property
    def embedder_info(self):
        return {"name": "custom"}
```

### 添加新的向量存储

```python
from code_index.interfaces import IVectorStore

class CustomVectorStore(IVectorStore):
    async def initialize(self):
        # 实现初始化逻辑
        pass
    
    async def upsert_points(self, points):
        # 实现点插入逻辑
        pass
    
    # 实现其他必需方法...
```

## 贡献指南

1. Fork项目
2. 创建功能分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送分支: `git push origin feature/new-feature`
5. 创建Pull Request

## 许可证

MIT License - 详见[LICENSE](LICENSE)文件

## 致谢

本项目基于原TypeScript代码索引系统重新实现，保持了原项目的完整性和正确性，同时提供了Python生态系统的原生支持。

---

**注意**: 这是一个完整的代码索引系统实现，包含了所有核心功能。请根据具体需求调整配置和使用方式。