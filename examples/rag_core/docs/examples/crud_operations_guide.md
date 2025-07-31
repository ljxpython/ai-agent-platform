# Milvus向量数据库CRUD操作指南

本指南详细介绍如何使用我们的RAG系统对Milvus向量数据库进行完整的CRUD（增删改查）操作，参考LlamaIndex官方文档实现。

## 目录

1. [Collection操作](#collection操作)
2. [节点创建（Create）](#节点创建create)
3. [节点查询（Read）](#节点查询read)
4. [节点更新（Update）](#节点更新update)
5. [节点删除（Delete）](#节点删除delete)
6. [异步操作](#异步操作)
7. [批量操作](#批量操作)
8. [高级查询](#高级查询)

## Collection操作

### 创建和管理Collection

```python
from backend.conf.rag_config import get_rag_config
from backend.rag_core.vector_store import MilvusVectorDB

def manage_collection():
    """Collection管理示例"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    # 检查Collection是否存在
    if vector_db.collection_exists():
        print("✅ Collection已存在")
    else:
        print("❌ Collection不存在")

    # 创建Collection（覆盖现有）
    vector_db.create_collection(overwrite=True)
    print("✅ Collection创建完成")

    # 获取统计信息
    stats = vector_db.get_stats()
    print(f"📊 Collection统计: {stats}")

    # 清空Collection数据
    vector_db.clear_collection()
    print("🗑️ Collection数据已清空")

    # 删除Collection
    vector_db.delete_collection()
    print("🗑️ Collection已删除")

manage_collection()
```

## 节点创建（Create）

### 基本节点添加

```python
import asyncio
from llama_index.core.schema import TextNode
from backend.rag_core.embedding_generator import EmbeddingGenerator

async def create_nodes():
    """创建和添加节点"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()
    vector_db.create_collection(overwrite=True)

    # 初始化嵌入生成器
    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 创建节点
    text = "人工智能是计算机科学的一个分支"
    embedding = await embedding_gen.embed_query(text)

    node = TextNode(
        text=text,
        metadata={
            "category": "technology",
            "year": 2024,
            "author": "AI研究团队",
            "language": "zh"
        },
        embedding=embedding
    )

    # 添加节点
    node_ids = vector_db.add_nodes([node])
    print(f"✅ 添加节点: {node_ids}")

    await embedding_gen.close()

asyncio.run(create_nodes())
```

### 批量节点添加

```python
async def batch_create_nodes():
    """批量创建节点"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 准备批量数据
    texts = [
        "机器学习是AI的子集",
        "深度学习使用神经网络",
        "自然语言处理理解人类语言"
    ]

    # 生成嵌入
    embeddings = await embedding_gen.embed_texts(texts)

    # 创建节点
    nodes = []
    for i, (text, embedding) in enumerate(zip(texts, embeddings)):
        node = TextNode(
            text=text,
            metadata={
                "category": "technology",
                "doc_id": f"doc_{i+1}",
                "batch": True
            },
            embedding=embedding
        )
        nodes.append(node)

    # 批量添加
    node_ids = vector_db.batch_add_nodes(nodes, batch_size=10)
    print(f"✅ 批量添加: {len(node_ids)} 个节点")

    await embedding_gen.close()

asyncio.run(batch_create_nodes())
```

### Upsert操作（更新或插入）

```python
async def upsert_nodes():
    """Upsert操作示例"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 创建或更新节点
    text = "更新后的AI定义：人工智能模拟人类智能"
    embedding = await embedding_gen.embed_query(text)

    node = TextNode(
        text=text,
        metadata={
            "category": "technology",
            "doc_id": "ai_definition",  # 相同ID会被更新
            "version": 2,
            "updated": True
        },
        embedding=embedding
    )

    # Upsert操作
    node_ids = vector_db.upsert_nodes([node])
    print(f"🔄 Upsert完成: {node_ids}")

    await embedding_gen.close()

asyncio.run(upsert_nodes())
```

## 节点查询（Read）

### 基本向量查询

```python
async def basic_query():
    """基本向量查询"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 生成查询向量
    query_text = "人工智能技术"
    query_embedding = await embedding_gen.embed_query(query_text)

    # 执行查询
    result = vector_db.query(query_embedding, top_k=5)

    print(f"📖 查询结果: {len(result.nodes)} 个节点")
    for i, node_with_score in enumerate(result.nodes):
        node = node_with_score.node if hasattr(node_with_score, 'node') else node_with_score
        score = getattr(node_with_score, 'score', 0.0)
        print(f"  {i+1}. 相似度: {score:.4f}")
        print(f"     内容: {node.text[:50]}...")
        print(f"     元数据: {node.metadata}")

    await embedding_gen.close()

asyncio.run(basic_query())
```

### 元数据过滤查询

```python
async def filtered_query():
    """元数据过滤查询"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    query_embedding = await embedding_gen.embed_query("机器学习")

    # 元数据过滤
    metadata_filters = {
        "category": "technology",
        "language": "zh",
        "year": [2023, 2024]  # 列表值使用IN操作
    }

    result = vector_db.query_with_metadata_filter(
        query_embedding=query_embedding,
        metadata_filters=metadata_filters,
        operator="and",
        top_k=5
    )

    print(f"📖 过滤查询结果: {len(result.nodes)} 个节点")

    await embedding_gen.close()

asyncio.run(filtered_query())
```

### 按ID获取节点

```python
def get_nodes_by_id():
    """按ID获取节点"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    # 按节点ID获取
    node_ids = ["node_id_1", "node_id_2"]
    nodes = vector_db.get_nodes(node_ids=node_ids)

    print(f"📖 按ID获取: {len(nodes)} 个节点")

    # 按元数据过滤获取
    from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

    filters = MetadataFilters(filters=[
        MetadataFilter(key="category", value="technology", operator=FilterOperator.EQ)
    ])

    filtered_nodes = vector_db.get_nodes(filters=filters)
    print(f"📖 按过滤器获取: {len(filtered_nodes)} 个节点")

get_nodes_by_id()
```

## 节点更新（Update）

### 使用Upsert更新节点

```python
async def update_nodes():
    """更新节点内容"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 更新现有节点
    updated_text = "更新后的内容：深度学习是机器学习的高级形式"
    updated_embedding = await embedding_gen.embed_query(updated_text)

    updated_node = TextNode(
        text=updated_text,
        metadata={
            "category": "technology",
            "doc_id": "existing_doc",  # 使用现有文档ID
            "version": 2,
            "last_updated": "2024-01-01"
        },
        embedding=updated_embedding
    )

    # 执行更新
    update_ids = vector_db.upsert_nodes([updated_node])
    print(f"🔄 节点更新完成: {update_ids}")

    await embedding_gen.close()

asyncio.run(update_nodes())
```

## 节点删除（Delete）

### 按节点ID删除

```python
def delete_by_node_id():
    """按节点ID删除"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    # 删除特定节点
    node_ids = ["node_id_1", "node_id_2"]
    vector_db.delete_nodes(node_ids=node_ids)

    print(f"🗑️ 删除节点: {len(node_ids)} 个")

delete_by_node_id()
```

### 按文档ID删除

```python
def delete_by_document_id():
    """按文档ID删除"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    # 删除整个文档
    doc_ids = ["doc_001", "doc_002"]
    for doc_id in doc_ids:
        vector_db.delete_by_doc_id(doc_id)

    print(f"🗑️ 删除文档: {len(doc_ids)} 个")

delete_by_document_id()
```

### 按元数据过滤删除

```python
def delete_by_metadata():
    """按元数据过滤删除"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

    # 删除特定类别的节点
    filters = MetadataFilters(filters=[
        MetadataFilter(key="category", value="test", operator=FilterOperator.EQ)
    ])

    vector_db.delete_nodes(filters=filters)
    print("🗑️ 按元数据删除完成")

delete_by_metadata()
```

## 异步操作

### 异步CRUD操作

```python
async def async_operations():
    """异步操作示例"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 创建异步节点
    text = "异步操作测试"
    embedding = await embedding_gen.embed_query(text)

    node = TextNode(
        text=text,
        metadata={"type": "async_test"},
        embedding=embedding
    )

    # 异步添加
    node_ids = await vector_db.async_add_nodes([node])
    print(f"📝 异步添加: {node_ids}")

    # 异步获取
    nodes = await vector_db.async_get_nodes(node_ids=node_ids)
    print(f"📖 异步获取: {len(nodes)} 个节点")

    # 异步删除
    await vector_db.async_delete_nodes(node_ids=node_ids)
    print("🗑️ 异步删除完成")

    await embedding_gen.close()

asyncio.run(async_operations())
```

## 批量操作

### 大规模数据处理

```python
async def large_scale_operations():
    """大规模数据处理"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    # 生成大量测试数据
    batch_size = 1000
    nodes = []

    for i in range(batch_size):
        text = f"批量测试文档 {i}: 这是第{i}个测试文档的内容。"
        embedding = await embedding_gen.embed_query(text)

        node = TextNode(
            text=text,
            metadata={
                "batch_id": i,
                "category": "batch_test"
            },
            embedding=embedding
        )
        nodes.append(node)

    # 批量添加（自动分批处理）
    node_ids = vector_db.batch_add_nodes(nodes, batch_size=100)
    print(f"📝 批量添加: {len(node_ids)} 个节点")

    # 批量删除
    from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator

    filters = MetadataFilters(filters=[
        MetadataFilter(key="category", value="batch_test", operator=FilterOperator.EQ)
    ])

    vector_db.delete_nodes(filters=filters)
    print("🗑️ 批量删除完成")

    await embedding_gen.close()

asyncio.run(large_scale_operations())
```

## 高级查询

### MMR搜索

```python
async def mmr_search():
    """最大边际相关性搜索"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    query_embedding = await embedding_gen.embed_query("人工智能")

    # MMR搜索（减少结果重复性）
    result = vector_db.mmr_search(
        query_embedding=query_embedding,
        top_k=5,
        mmr_threshold=0.5
    )

    print(f"🔍 MMR搜索结果: {len(result.nodes)} 个节点")

    await embedding_gen.close()

asyncio.run(mmr_search())
```

### 混合搜索

```python
async def hybrid_search():
    """混合搜索（密集+稀疏向量）"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_gen = EmbeddingGenerator(config)
    await embedding_gen.initialize()

    query_text = "深度学习"
    query_embedding = await embedding_gen.embed_query(query_text)

    # 混合搜索
    result = vector_db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query_text,
        top_k=5,
        hybrid_ranker="RRFRanker"
    )

    print(f"🔍 混合搜索结果: {len(result.nodes)} 个节点")

    await embedding_gen.close()

asyncio.run(hybrid_search())
```

## 最佳实践

### 1. 错误处理

```python
async def robust_operations():
    """健壮的操作示例"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    embedding_gen = EmbeddingGenerator(config)

    try:
        vector_db.initialize()
        await embedding_gen.initialize()

        # 执行操作
        # ... 你的代码 ...

    except Exception as e:
        print(f"❌ 操作失败: {e}")
        # 处理错误
    finally:
        # 清理资源
        await embedding_gen.close()
        vector_db.close()

asyncio.run(robust_operations())
```

### 2. 性能优化

- 使用批量操作处理大量数据
- 合理设置batch_size（建议100-1000）
- 使用异步操作提高并发性能
- 为常用查询字段创建索引
- 定期清理不需要的数据

### 3. 内存管理

- 及时关闭连接和释放资源
- 避免在内存中保存大量节点对象
- 使用流式处理处理大文件

## 参考资料

- [LlamaIndex Milvus官方文档](https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/)
- [Milvus官方文档](https://milvus.io/docs)
- [向量数据库最佳实践](../milvus_llamaindex_guide.md)
