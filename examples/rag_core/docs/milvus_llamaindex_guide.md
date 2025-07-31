# Milvus + LlamaIndex 使用指南

本文档详细介绍如何在项目中使用 Milvus 向量数据库和 LlamaIndex 框架构建 RAG 系统。

## 📋 目录

- [环境准备](#环境准备)
- [基础概念](#基础概念)
- [配置说明](#配置说明)
- [基本使用](#基本使用)
- [高级功能](#高级功能)
- [最佳实践](#最佳实践)
- [故障排除](#故障排除)

## 🛠️ 环境准备

### 1. 服务依赖

确保以下服务正常运行：

```bash
# Milvus 向量数据库
docker run -d --name milvus-standalone \
  -p 19530:19530 \
  -v milvus_data:/var/lib/milvus \
  milvusdb/milvus:latest

# Ollama 嵌入服务
docker run -d --name ollama \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  ollama/ollama:latest

# 拉取嵌入模型
docker exec ollama ollama pull bge-m3
```

### 2. Python 依赖

```bash
pip install llama-index-vector-stores-milvus
pip install llama-index-embeddings-ollama
pip install pymilvus
```

## 🧠 基础概念

### 1. 核心组件

- **MilvusVectorStore**: LlamaIndex 的 Milvus 向量存储适配器
- **OllamaEmbedding**: Ollama 嵌入模型接口
- **TextNode**: LlamaIndex 的文本节点，包含文本内容和嵌入向量
- **VectorStoreIndex**: 基于向量存储的索引

### 2. 数据流程

```
文本输入 → 分块处理 → 嵌入生成 → 向量存储 → 相似性检索 → 结果返回
```

## ⚙️ 配置说明

### 1. 系统配置 (backend/conf/settings.yaml)

```yaml
rag:
  # Milvus 向量数据库配置
  milvus:
    host: "101.126.90.71"
    port: 19530
    default_collection: "general_knowledge"
    dimension: 1024

  # Ollama 嵌入服务配置
  ollama:
    base_url: "http://101.126.90.71:11434"
    embedding_model: "bge-m3"

  # Collection 默认配置
  collection_defaults:
    dimension: 1024
    top_k: 5
    similarity_threshold: 0.7
    chunk_size: 1000
    chunk_overlap: 200

  # 预定义 Collections
  collections:
    general:
      name: "general_knowledge"
      description: "通用知识库"
      business_type: "general"
```

### 2. 嵌入模型配置

| 模型名称 | 维度 | 语言支持 | 特点 |
|---------|------|----------|------|
| bge-m3 | 1024 | 中英文 | 高质量多语言嵌入 |
| nomic-embed-text | 768 | 英文为主 | 轻量级高效 |
| text-embedding-ada-002 | 1536 | 多语言 | OpenAI 商业模型 |

## 🚀 基本使用

### 1. 初始化向量存储

```python
from llama_index.vector_stores.milvus import MilvusVectorStore
from backend.conf.rag_config import get_rag_config

# 获取配置
config = get_rag_config()
collection_config = config.get_collection_config("general")

# 创建向量存储
vector_store = MilvusVectorStore(
    uri=f"http://{config.milvus.host}:{config.milvus.port}",
    collection_name=collection_config.name,
    dim=collection_config.dimension,
    overwrite=False,  # 不覆盖现有集合
    enable_sparse=False,
    hybrid_ranker="RRFRanker",
)
```

### 2. 生成嵌入向量

```python
from backend.rag_core.embedding_generator import EmbeddingGenerator

# 初始化嵌入生成器
embedding_generator = EmbeddingGenerator(config)
await embedding_generator.initialize()

# 生成文本嵌入
texts = ["人工智能是计算机科学的一个分支", "机器学习是AI的子集"]
embeddings = await embedding_generator.embed_texts(texts)

# 生成查询嵌入
query = "什么是人工智能？"
query_embedding = await embedding_generator.embed_query(query)
```

### 3. 添加文档

```python
from llama_index.core.schema import TextNode

# 创建文本节点
nodes = []
for i, text in enumerate(texts):
    node = TextNode(
        text=text,
        metadata={"source": "demo", "doc_id": f"doc_{i}"},
        embedding=embeddings[i]  # 重要：必须设置嵌入向量
    )
    nodes.append(node)

# 添加到向量存储
node_ids = vector_store.add(nodes)
print(f"添加了 {len(node_ids)} 个文档")
```

### 4. 相似性检索

```python
from llama_index.core.vector_stores import VectorStoreQuery

# 创建查询
query_obj = VectorStoreQuery(
    query_embedding=query_embedding,
    similarity_top_k=5,
    mode="default"
)

# 执行检索
result = vector_store.query(query_obj)

# 处理结果
for node_with_score in result.nodes:
    print(f"相似度: {node_with_score.score:.4f}")
    print(f"内容: {node_with_score.node.text}")
    print(f"元数据: {node_with_score.node.metadata}")
```

## 🔧 高级功能

### 1. 混合检索

```python
# 启用稀疏向量支持
vector_store = MilvusVectorStore(
    uri=f"http://{config.milvus.host}:{config.milvus.port}",
    collection_name=collection_config.name,
    dim=collection_config.dimension,
    enable_sparse=True,  # 启用稀疏向量
    hybrid_ranker="RRFRanker",  # 使用 RRF 混合排序
    hybrid_ranker_params={"k": 60}
)
```

### 2. 自定义索引参数

```python
# 创建带有自定义索引的向量存储
vector_store = MilvusVectorStore(
    uri=f"http://{config.milvus.host}:{config.milvus.port}",
    collection_name=collection_config.name,
    dim=collection_config.dimension,
    index_config={
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 1024}
    },
    search_config={
        "metric_type": "COSINE",
        "params": {"nprobe": 10}
    }
)
```

### 3. 批量操作

```python
# 批量添加大量文档
batch_size = 100
for i in range(0, len(large_nodes), batch_size):
    batch = large_nodes[i:i + batch_size]
    batch_ids = vector_store.add(batch)
    print(f"批次 {i//batch_size + 1}: 添加了 {len(batch_ids)} 个文档")
```

## 💡 最佳实践

### 1. 嵌入向量管理

```python
# ✅ 正确：为节点设置嵌入向量
node = TextNode(text="示例文本", embedding=embedding_vector)

# ❌ 错误：嵌入向量为空
node = TextNode(text="示例文本")  # embedding=None 会导致错误
```

### 2. 错误处理

```python
try:
    # 添加节点
    node_ids = vector_store.add(nodes)
except Exception as e:
    if "DataNotMatchException" in str(e):
        logger.error("嵌入向量维度不匹配或为空")
    elif "CollectionNotExistException" in str(e):
        logger.error("集合不存在，需要先创建")
    else:
        logger.error(f"未知错误: {e}")
    raise
```

### 3. 资源管理

```python
# 使用上下文管理器
async def process_documents():
    embedding_generator = EmbeddingGenerator(config)
    try:
        await embedding_generator.initialize()
        # 处理文档...
    finally:
        await embedding_generator.close()
```

### 4. 性能优化

```python
# 批量生成嵌入向量
texts = [node.text for node in nodes]
embeddings = await embedding_generator.embed_texts(texts)

# 并行设置嵌入向量
for node, embedding in zip(nodes, embeddings):
    node.embedding = embedding
```

## 🔍 故障排除

### 1. 常见错误

#### DataNotMatchException: embedding field should be a float_vector

**原因**: 节点的 embedding 字段为 None 或维度不匹配

**解决方案**:
```python
# 确保为每个节点生成嵌入向量
embeddings = await embedding_generator.embed_texts([node.text for node in nodes])
for node, embedding in zip(nodes, embeddings):
    node.embedding = embedding
```

#### CollectionNotExistException

**原因**: 集合不存在

**解决方案**:
```python
# 创建集合
vector_store = MilvusVectorStore(
    uri=uri,
    collection_name=collection_name,
    dim=dimension,
    overwrite=True  # 强制创建新集合
)
```

#### 连接超时

**原因**: Milvus 服务不可用

**解决方案**:
```python
# 检查服务状态
import requests
try:
    response = requests.get(f"http://{host}:{port}/health")
    print(f"Milvus 状态: {response.status_code}")
except:
    print("Milvus 服务不可用")
```

### 2. 调试技巧

```python
# 启用详细日志
import logging
logging.getLogger("llama_index").setLevel(logging.DEBUG)

# 检查嵌入向量
print(f"嵌入向量维度: {len(embedding)}")
print(f"嵌入向量类型: {type(embedding)}")
print(f"嵌入向量示例: {embedding[:5]}")

# 检查集合信息
from pymilvus import Collection
collection = Collection(collection_name)
print(f"集合统计: {collection.num_entities}")
print(f"集合模式: {collection.schema}")
```

## 📚 参考资料

- [LlamaIndex Milvus 官方文档](https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/)
- [Milvus 官方文档](https://milvus.io/docs)
- [Ollama 模型库](https://ollama.ai/library)
- [BGE-M3 模型介绍](https://huggingface.co/BAAI/bge-m3)
