# 向量数据库对比指南

本文档帮助你选择适合的向量数据库用于代码索引系统。

## 支持的向量数据库

代码索引系统当前支持两种向量数据库：

- **Qdrant** - 高性能向量搜索引擎
- **Milvus** - 开源向量数据库

## 特性对比

| 特性 | Qdrant | Milvus |
|------|--------|--------|
| **部署方式** | Docker单容器 | Docker Compose多服务 |
| **内存占用** | 轻量级 (~200MB) | 中等 (~500MB+) |
| **启动速度** | 快速 (<10秒) | 中等 (~30秒) |
| **API复杂度** | 简单 | 稍复杂 |
| **数据类型** | 灵活payload | 结构化schema |
| **索引类型** | HNSW | IVF, HNSW, Annoy等 |
| **可扩展性** | 集群支持 | 分布式架构 |
| **生态系统** | Rust生态 | 更大的社区 |
| **企业特性** | 商业版 | 开源 + 云版本 |

## 性能比较

### 小规模项目 (<10万向量)

**Qdrant推荐** ✅
- 更快的启动和响应
- 更低的资源消耗
- 简单的配置和维护

### 中等规模项目 (10万-100万向量)

**两者皆可** ⚖️
- Qdrant: 简单稳定
- Milvus: 更多调优选项

### 大规模项目 (>100万向量)

**Milvus推荐** ✅
- 更好的分布式支持
- 更多的索引类型选择
- 更强的横向扩展能力

## 安装对比

### Qdrant安装

**优势**：
- 单一容器部署
- 即时可用
- 零配置启动

```bash
# 一键启动
docker run -p 6333:6333 qdrant/qdrant
```

### Milvus安装

**优势**：
- 更多配置选项
- 完整的数据库功能
- Web UI管理界面

```bash
# 需要多个服务
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
docker-compose up -d
```

## 配置对比

### Qdrant配置

```python
config = {
    "vector_store": "qdrant",
    "qdrant_url": "http://localhost:6333",
    "qdrant_api_key": "optional"  # 企业版
}
```

### Milvus配置

```python
config = {
    "vector_store": "milvus",
    "milvus_host": "localhost",
    "milvus_port": "19530",
    "milvus_user": "optional",     # 认证
    "milvus_password": "optional"  # 认证
}
```

## 使用场景建议

### 选择Qdrant当你需要：

- ✅ 快速原型开发
- ✅ 简单部署和维护
- ✅ 小到中等规模的项目
- ✅ 最小化资源消耗
- ✅ 灵活的数据结构
- ✅ Rust生态系统集成

### 选择Milvus当你需要：

- ✅ 大规模数据处理
- ✅ 多种索引算法选择
- ✅ 分布式部署
- ✅ 企业级功能
- ✅ 结构化数据管理
- ✅ Web UI管理界面

## 迁移指南

### 从Qdrant迁移到Milvus

1. **导出数据**（如需要）
2. **修改配置**
   ```python
   # 从这个
   config = {"vector_store": "qdrant", "qdrant_url": "..."}
   
   # 改为这个
   config = {"vector_store": "milvus", "milvus_host": "localhost", "milvus_port": "19530"}
   ```
3. **重新索引**
   ```python
   await manager.clear_index_data()
   await manager.start_indexing()
   ```

### 从Milvus迁移到Qdrant

类似的流程，只需反向修改配置。

## 开发建议

### 开发阶段

**推荐**: Qdrant
- 快速启动
- 简单调试
- 低资源占用

### 生产环境

**小型项目**: Qdrant
**大型项目**: Milvus

### 混合使用

可以在不同环境使用不同的向量数据库：

```python
import os

vector_store = "qdrant" if os.getenv("ENV") == "development" else "milvus"

config = {
    "vector_store": vector_store,
    # 其他配置...
}
```

## 社区和支持

### Qdrant
- GitHub: https://github.com/qdrant/qdrant
- 文档: https://qdrant.tech/documentation/
- 社区: Discord, GitHub Issues

### Milvus
- GitHub: https://github.com/milvus-io/milvus
- 文档: https://milvus.io/docs/
- 社区: Slack, GitHub Discussions

## 结论

两种向量数据库都是优秀的选择，关键是根据你的具体需求：

- **快速开始，简单项目** → Qdrant
- **大规模，企业级** → Milvus
- **不确定** → 从Qdrant开始，需要时迁移到Milvus

系统的抽象架构使得切换向量数据库变得容易，你可以随时根据项目发展调整选择。