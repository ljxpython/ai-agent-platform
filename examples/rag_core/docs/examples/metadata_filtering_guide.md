# Milvus 元数据过滤使用指南

本指南展示如何在RAG系统中使用Milvus的元数据过滤功能，参考LlamaIndex官方文档实现。

## 基本概念

元数据过滤允许你在向量相似性搜索的基础上，根据文档的元数据属性进一步筛选结果。这样可以实现更精确的检索。

## 1. 基本元数据过滤

### 使用LlamaIndex标准过滤器

```python
import asyncio
from backend.rag_core.rag_system import RAGSystem
from backend.rag_core.embedding_generator import EmbeddingGenerator
from backend.conf.rag_config import get_rag_config

async def basic_metadata_filtering():
    """基本元数据过滤示例"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        # 初始化嵌入生成器
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        # 生成查询向量
        query_text = "人工智能的应用"
        query_embedding = await embedding_gen.embed_query(query_text)

        # 使用元数据过滤
        metadata_filters = {
            "category": "technology",
            "year": 2023
        }

        # 执行过滤查询
        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        result = vector_db.query_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filters=metadata_filters,
            top_k=5
        )

        print(f"找到 {len(result.nodes)} 个匹配结果")
        for i, node_with_score in enumerate(result.nodes):
            print(f"{i+1}. 相似度: {node_with_score.score:.4f}")
            print(f"   内容: {node_with_score.node.text[:100]}...")
            print(f"   元数据: {node_with_score.node.metadata}")

asyncio.run(basic_metadata_filtering())
```

### 使用多个过滤条件 (AND逻辑)

```python
async def multiple_filters_and():
    """多个过滤条件 - AND逻辑"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("机器学习算法")

        # 多个AND条件：技术类别且2022年后发布
        metadata_filters = {
            "category": "technology",
            "year": [2022, 2023, 2024]  # 列表值会被转换为IN操作
        }

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        result = vector_db.query_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filters=metadata_filters,
            operator="and",  # AND逻辑
            top_k=10
        )

        print(f"AND过滤结果: {len(result.nodes)} 个文档")

asyncio.run(multiple_filters_and())
```

### 使用多个过滤条件 (OR逻辑)

```python
async def multiple_filters_or():
    """多个过滤条件 - OR逻辑"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("深度学习")

        # 多个OR条件：技术类别或教育类别
        metadata_filters = {
            "category": ["technology", "education"],
            "language": "zh"
        }

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        result = vector_db.query_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filters=metadata_filters,
            operator="or",  # OR逻辑
            top_k=10
        )

        print(f"OR过滤结果: {len(result.nodes)} 个文档")

asyncio.run(multiple_filters_or())
```

## 2. 使用Milvus原生表达式过滤

### 基本字符串表达式

```python
async def string_expression_filtering():
    """使用Milvus原生字符串表达式过滤"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("自然语言处理")

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        # 使用Milvus原生表达式
        result = vector_db.query_with_string_expr(
            query_embedding=query_embedding,
            string_expr="year > 2020 and category like '%tech%'",
            top_k=5
        )

        print(f"字符串表达式过滤结果: {len(result.nodes)} 个文档")

asyncio.run(string_expression_filtering())
```

### 复杂表达式示例

```python
async def complex_expression_examples():
    """复杂Milvus表达式示例"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("人工智能")

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        # 示例1: 数值范围过滤
        result1 = vector_db.query_with_string_expr(
            query_embedding=query_embedding,
            string_expr="year >= 2020 and year <= 2024",
            top_k=5
        )
        print(f"年份范围过滤: {len(result1.nodes)} 个结果")

        # 示例2: 字符串模式匹配
        result2 = vector_db.query_with_string_expr(
            query_embedding=query_embedding,
            string_expr="title like '%AI%' or title like '%人工智能%'",
            top_k=5
        )
        print(f"标题模式匹配: {len(result2.nodes)} 个结果")

        # 示例3: 复合条件
        result3 = vector_db.query_with_string_expr(
            query_embedding=query_embedding,
            string_expr="(category == 'technology' and year > 2022) or (category == 'research' and priority > 5)",
            top_k=5
        )
        print(f"复合条件过滤: {len(result3.nodes)} 个结果")

asyncio.run(complex_expression_examples())
```

## 3. 实际应用场景

### 场景1: 按文档类型和时间过滤

```python
async def filter_by_document_type_and_time():
    """按文档类型和时间过滤"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("API文档")

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        # 查找最近的API文档
        metadata_filters = {
            "doc_type": "api_documentation",
            "status": "published"
        }

        result = vector_db.query_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filters=metadata_filters,
            top_k=10
        )

        print("最新API文档:")
        for node_with_score in result.nodes:
            metadata = node_with_score.node.metadata
            print(f"- {metadata.get('title', 'Unknown')}")
            print(f"  更新时间: {metadata.get('updated_at', 'Unknown')}")

asyncio.run(filter_by_document_type_and_time())
```

### 场景2: 按用户权限过滤

```python
async def filter_by_user_permission():
    """按用户权限过滤"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("内部流程")

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        # 模拟用户权限级别
        user_level = "manager"

        # 根据权限级别过滤
        if user_level == "admin":
            string_expr = "access_level in ['public', 'internal', 'confidential']"
        elif user_level == "manager":
            string_expr = "access_level in ['public', 'internal']"
        else:
            string_expr = "access_level == 'public'"

        result = vector_db.query_with_string_expr(
            query_embedding=query_embedding,
            string_expr=string_expr,
            top_k=5
        )

        print(f"用户 {user_level} 可访问的文档: {len(result.nodes)} 个")

asyncio.run(filter_by_user_permission())
```

### 场景3: 多语言文档过滤

```python
async def filter_by_language():
    """按语言过滤文档"""
    config = get_rag_config()

    async with RAGSystem() as rag:
        embedding_gen = EmbeddingGenerator(config)
        await embedding_gen.initialize()

        query_embedding = await embedding_gen.embed_query("用户指南")

        collection_name = "general"
        vector_db = rag.collection_manager.get_collection(collection_name)

        # 优先中文，其次英文
        preferred_languages = ["zh", "en"]

        metadata_filters = {
            "language": preferred_languages,
            "doc_type": "user_guide"
        }

        result = vector_db.query_with_metadata_filter(
            query_embedding=query_embedding,
            metadata_filters=metadata_filters,
            top_k=10
        )

        print("多语言用户指南:")
        for node_with_score in result.nodes:
            metadata = node_with_score.node.metadata
            lang = metadata.get('language', 'unknown')
            title = metadata.get('title', 'Unknown')
            print(f"- [{lang}] {title}")

asyncio.run(filter_by_language())
```

## 4. 最佳实践

### 1. 元数据设计原则
- 使用有意义的字段名
- 保持数据类型一致性
- 避免过深的嵌套结构
- 考虑查询频率设计索引

### 2. 过滤器性能优化
- 优先使用等值匹配而非模糊匹配
- 合理使用AND/OR逻辑
- 避免过于复杂的表达式
- 考虑为常用字段创建索引

### 3. 错误处理

```python
async def robust_filtering():
    """健壮的过滤查询"""
    config = get_rag_config()

    try:
        async with RAGSystem() as rag:
            embedding_gen = EmbeddingGenerator(config)
            await embedding_gen.initialize()

            query_embedding = await embedding_gen.embed_query("测试查询")

            collection_name = "general"
            vector_db = rag.collection_manager.get_collection(collection_name)

            # 安全的过滤查询
            metadata_filters = {
                "category": "test"
            }

            result = vector_db.query_with_metadata_filter(
                query_embedding=query_embedding,
                metadata_filters=metadata_filters,
                top_k=5
            )

            if result.nodes:
                print(f"查询成功: {len(result.nodes)} 个结果")
            else:
                print("未找到匹配的文档")

    except Exception as e:
        print(f"查询失败: {e}")
        # 可以回退到无过滤的查询
        print("尝试无过滤查询...")

asyncio.run(robust_filtering())
```

## 5. 支持的操作符

### LlamaIndex标准操作符
- `EQ`: 等于
- `NE`: 不等于
- `GT`: 大于
- `GTE`: 大于等于
- `LT`: 小于
- `LTE`: 小于等于
- `IN`: 包含在列表中
- `NIN`: 不包含在列表中

### Milvus原生表达式
- 比较操作: `==`, `!=`, `>`, `>=`, `<`, `<=`
- 逻辑操作: `and`, `or`, `not`
- 字符串操作: `like`, `in`
- 数组操作: `array_contains`, `array_length`

## 参考资料

- [LlamaIndex元数据过滤文档](https://docs.llamaindex.ai/en/stable/examples/vector_stores/MilvusOperatorFunctionDemo/)
- [Milvus布尔表达式文档](https://milvus.io/docs/boolean.md)
- [向量检索最佳实践](../milvus_llamaindex_guide.md)
