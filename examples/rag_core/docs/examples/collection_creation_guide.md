# Milvus Collection 创建指南

本指南展示如何使用我们的RAG系统创建和管理Milvus Collections，参考LlamaIndex官方文档的最佳实践。

## 基本概念

Collection是Milvus中存储向量数据的基本单位，类似于关系数据库中的表。每个Collection包含：
- 向量字段：存储嵌入向量
- 标量字段：存储元数据
- 主键字段：唯一标识每个向量

## 1. 基本Collection创建

### 使用RAGSystem创建Collection

```python
import asyncio
from backend.rag_core.rag_system import RAGSystem

async def create_basic_collection():
    """创建基本的Collection"""
    async with RAGSystem() as rag:
        # 创建一个新的Collection
        await rag.setup_collection(
            collection_name="my_documents",
            overwrite=True  # 如果存在则覆盖
        )
        print("✅ Collection创建成功")

# 运行示例
asyncio.run(create_basic_collection())
```

### 直接使用MilvusVectorDB创建

```python
from backend.conf.rag_config import get_rag_config
from backend.rag_core.vector_store import MilvusVectorDB

def create_collection_directly():
    """直接创建Collection"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    # 创建向量数据库实例
    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    # 创建Collection
    vector_db.create_collection(overwrite=True)
    print("✅ Collection创建成功")

create_collection_directly()
```

## 2. 配置Collection参数

### 在配置文件中定义Collection

编辑 `backend/conf/settings.yaml`:

```yaml
rag:
  milvus:
    host: "localhost"
    port: 19530
    collections:
      my_docs:
        name: "my_documents"
        description: "我的文档知识库"
        business_type: "documentation"
        dimension: 1024  # 向量维度
        top_k: 5
        similarity_threshold: 0.7
        chunk_size: 1000
        chunk_overlap: 200
```

### 使用自定义配置

```python
from backend.conf.rag_config import CollectionConfig, RAGConfig
from backend.rag_core.vector_store import MilvusVectorDB

def create_custom_collection():
    """使用自定义配置创建Collection"""
    # 创建自定义配置
    collection_config = CollectionConfig(
        name="custom_collection",
        description="自定义知识库",
        business_type="custom",
        dimension=1536,  # OpenAI embedding维度
        top_k=10,
        similarity_threshold=0.8,
        chunk_size=500,
        chunk_overlap=100
    )

    config = get_rag_config()
    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()
    vector_db.create_collection(overwrite=True)

    print("✅ 自定义Collection创建成功")

create_custom_collection()
```

## 3. Collection管理操作

### 检查Collection是否存在

```python
def check_collection_exists():
    """检查Collection是否存在"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)

    if vector_db.collection_exists():
        print("✅ Collection存在")
    else:
        print("❌ Collection不存在")

check_collection_exists()
```

### 获取Collection统计信息

```python
def get_collection_stats():
    """获取Collection统计信息"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    stats = vector_db.get_stats()
    print(f"Collection统计信息: {stats}")

get_collection_stats()
```

### 删除Collection

```python
def delete_collection():
    """删除Collection"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    # 删除Collection
    vector_db.delete_collection()
    print("✅ Collection删除成功")

delete_collection()
```

## 4. 最佳实践

### 1. Collection命名规范
- 使用有意义的名称，如 `product_docs`, `user_manuals`
- 避免特殊字符，使用下划线分隔
- 保持名称简洁但描述性强

### 2. 维度选择
- OpenAI text-embedding-ada-002: 1536维
- BGE-M3: 1024维
- 确保与嵌入模型维度匹配

### 3. 参数调优
- `top_k`: 根据业务需求调整，通常5-20
- `similarity_threshold`: 0.7-0.9之间，过高可能检索不到结果
- `chunk_size`: 500-2000字符，根据文档类型调整
- `chunk_overlap`: chunk_size的10-20%

### 4. 错误处理

```python
async def robust_collection_creation():
    """健壮的Collection创建"""
    try:
        async with RAGSystem() as rag:
            # 检查Collection是否存在
            if not await rag.collection_exists("my_docs"):
                await rag.setup_collection("my_docs")
                print("✅ Collection创建成功")
            else:
                print("ℹ️ Collection已存在")

    except Exception as e:
        print(f"❌ Collection创建失败: {e}")

asyncio.run(robust_collection_creation())
```

## 5. 故障排除

### 常见问题

1. **连接失败**
   - 检查Milvus服务是否运行
   - 验证host和port配置
   - 确认网络连接

2. **维度不匹配**
   - 确保配置的维度与嵌入模型匹配
   - 重新创建Collection时使用正确维度

3. **权限问题**
   - 检查Milvus用户权限
   - 验证token配置

### 调试技巧

```python
def debug_collection():
    """调试Collection问题"""
    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)

    # 检查连接
    print(f"连接URI: http://{config.milvus.host}:{config.milvus.port}")

    # 检查配置
    print(f"Collection名称: {collection_config.name}")
    print(f"向量维度: {collection_config.dimension}")

    # 验证连接
    vector_db.initialize()
    is_connected = vector_db.verify_connection()
    print(f"连接状态: {'成功' if is_connected else '失败'}")

debug_collection()
```

## 参考资料

- [LlamaIndex Milvus官方文档](https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/)
- [Milvus官方文档](https://milvus.io/docs)
- [向量数据库最佳实践](../milvus_llamaindex_guide.md)
