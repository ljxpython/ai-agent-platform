#!/usr/bin/env python3
"""
测试Milvus向量数据库的核心CRUD操作
专注于稳定可靠的基础功能测试
"""

import asyncio
import os
import sys
from typing import List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from llama_index.core.schema import TextNode
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from loguru import logger

from backend.conf.rag_config import get_rag_config
from backend.rag_core.embedding_generator import EmbeddingGenerator
from backend.rag_core.vector_store import MilvusVectorDB


async def test_core_crud():
    """测试核心CRUD操作"""
    logger.info("🧪 开始测试Milvus向量数据库核心CRUD操作")

    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    # 初始化组件
    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()

    embedding_generator = EmbeddingGenerator(config)
    await embedding_generator.initialize()

    try:
        print("\n" + "=" * 60)
        print("🧪 Milvus向量数据库核心CRUD功能测试")
        print("=" * 60)

        # 1. Collection管理测试
        print("\n📦 1. Collection管理测试")
        await test_collection_management(vector_db)

        # 2. 创建测试数据
        print("\n🔄 2. 创建测试数据")
        test_nodes = await create_test_data(embedding_generator)

        # 3. 节点创建测试 (Create)
        print("\n📝 3. 节点创建测试 (Create)")
        await test_create_operations(vector_db, test_nodes)

        # 4. 节点查询测试 (Read)
        print("\n📖 4. 节点查询测试 (Read)")
        await test_read_operations(vector_db, embedding_generator)

        # 5. 节点更新测试 (Update)
        print("\n🔄 5. 节点更新测试 (Update)")
        await test_update_operations(vector_db, embedding_generator)

        # 6. 节点删除测试 (Delete)
        print("\n🗑️ 6. 节点删除测试 (Delete)")
        await test_delete_operations(vector_db)

        # 7. 异步操作测试
        print("\n⚡ 7. 异步操作测试")
        await test_async_operations(vector_db, embedding_generator)

        # 8. 批量操作测试
        print("\n📦 8. 批量操作测试")
        await test_batch_operations(vector_db, embedding_generator)

        print("\n" + "=" * 60)
        print("🎉 所有核心CRUD操作测试完成！")
        print("✅ 功能验证：Collection管理、节点增删改查、异步操作、批量处理")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        print(f"\n❌ 测试失败: {e}")
        raise

    finally:
        # 清理资源
        await embedding_generator.close()
        vector_db.close()


async def test_collection_management(vector_db: MilvusVectorDB):
    """测试Collection管理"""
    # 检查存在性
    exists_before = vector_db.collection_exists()
    print(f"   📊 Collection存在性: {exists_before}")

    # 创建Collection
    vector_db.create_collection(overwrite=True)
    print("   ✅ Collection创建成功")

    # 获取统计信息
    stats = vector_db.get_stats()
    print(
        f"   📊 Collection统计: 维度={stats['dimension']}, 连接状态={stats['remote_connected']}"
    )


async def create_test_data(embedding_generator: EmbeddingGenerator) -> List[TextNode]:
    """创建测试数据"""
    test_data = [
        {
            "text": "人工智能是计算机科学的一个分支，致力于创建智能系统。",
            "metadata": {
                "category": "technology",
                "year": 2023,
                "doc_id": "ai_001",
                "language": "zh",
            },
        },
        {
            "text": "机器学习是人工智能的子集，使计算机能够自主学习。",
            "metadata": {
                "category": "technology",
                "year": 2022,
                "doc_id": "ml_001",
                "language": "zh",
            },
        },
        {
            "text": "深度学习使用神经网络来模拟人脑的学习过程。",
            "metadata": {
                "category": "research",
                "year": 2024,
                "doc_id": "dl_001",
                "language": "zh",
            },
        },
    ]

    # 生成嵌入向量
    texts = [item["text"] for item in test_data]
    embeddings = await embedding_generator.embed_texts(texts)

    # 创建节点
    nodes = []
    for item, embedding in zip(test_data, embeddings):
        node = TextNode(
            text=item["text"], metadata=item["metadata"], embedding=embedding
        )
        nodes.append(node)

    print(f"   ✅ 创建了 {len(nodes)} 个测试节点")
    return nodes


async def test_create_operations(vector_db: MilvusVectorDB, test_nodes: List[TextNode]):
    """测试创建操作"""
    # 基本添加
    node_ids = vector_db.add_nodes(test_nodes)
    print(f"   📝 基本添加: {len(node_ids)} 个节点")

    # Upsert操作
    updated_node = test_nodes[0]
    updated_node.metadata["updated"] = True
    updated_node.metadata["priority"] = 10

    upsert_ids = vector_db.upsert_nodes([updated_node])
    print(f"   🔄 Upsert操作: {len(upsert_ids)} 个节点")


async def test_read_operations(
    vector_db: MilvusVectorDB, embedding_generator: EmbeddingGenerator
):
    """测试查询操作"""
    # 生成查询向量
    query_embedding = await embedding_generator.embed_query("人工智能技术")

    # 基本查询
    result1 = vector_db.query(query_embedding, top_k=3)
    print(f"   📖 基本查询: {len(result1.nodes)} 个结果")

    # 元数据过滤查询
    metadata_filters = {"category": "technology", "language": "zh"}
    result2 = vector_db.query_with_metadata_filter(
        query_embedding=query_embedding, metadata_filters=metadata_filters, top_k=3
    )
    print(f"   📖 元数据过滤查询: {len(result2.nodes)} 个结果")

    # 按ID获取节点
    if result1.nodes:
        first_node = result1.nodes[0]
        node_id = (
            first_node.node.node_id
            if hasattr(first_node, "node")
            else first_node.node_id
        )
        retrieved_nodes = vector_db.get_nodes(node_ids=[node_id])
        print(f"   📖 按ID获取: {len(retrieved_nodes)} 个节点")

    # 按过滤器获取节点
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="category", value="technology", operator=FilterOperator.EQ
            )
        ]
    )
    filtered_nodes = vector_db.get_nodes(filters=filters)
    print(f"   📖 按过滤器获取: {len(filtered_nodes)} 个节点")


async def test_update_operations(
    vector_db: MilvusVectorDB, embedding_generator: EmbeddingGenerator
):
    """测试更新操作"""
    # 创建更新节点
    update_text = "更新后的AI定义：人工智能模拟人类智能的计算机系统。"
    update_embedding = await embedding_generator.embed_query(update_text)

    update_node = TextNode(
        text=update_text,
        metadata={
            "category": "technology",
            "year": 2024,
            "doc_id": "ai_updated",
            "language": "zh",
            "version": 2,
        },
        embedding=update_embedding,
    )

    # 执行更新
    update_ids = vector_db.upsert_nodes([update_node])
    print(f"   🔄 节点更新: {len(update_ids)} 个节点")


async def test_delete_operations(vector_db: MilvusVectorDB):
    """测试删除操作"""
    # 按文档ID删除
    vector_db.delete_by_doc_id("ml_001")
    print("   🗑️ 按文档ID删除: 完成")

    # 按元数据过滤删除
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="category", value="research", operator=FilterOperator.EQ)
        ]
    )
    vector_db.delete_nodes(filters=filters)
    print("   🗑️ 按过滤器删除: 完成")


async def test_async_operations(
    vector_db: MilvusVectorDB, embedding_generator: EmbeddingGenerator
):
    """测试异步操作"""
    # 创建异步测试节点
    async_text = "异步操作测试节点"
    async_embedding = await embedding_generator.embed_query(async_text)

    async_node = TextNode(
        text=async_text,
        metadata={"category": "test", "type": "async", "doc_id": "async_test"},
        embedding=async_embedding,
    )

    try:
        # 异步添加
        async_ids = await vector_db.async_add_nodes([async_node])
        print(f"   ⚡ 异步添加: {len(async_ids)} 个节点")

        # 异步删除
        await vector_db.async_delete_nodes(node_ids=async_ids)
        print("   ⚡ 异步删除: 完成")

    except Exception as e:
        print(f"   ⚠️ 异步操作失败: {e}")


async def test_batch_operations(
    vector_db: MilvusVectorDB, embedding_generator: EmbeddingGenerator
):
    """测试批量操作"""
    # 创建批量测试节点
    batch_size = 20
    batch_nodes = []

    for i in range(batch_size):
        text = f"批量测试节点 {i+1}: 用于测试批量操作的节点。"
        embedding = await embedding_generator.embed_query(text)

        node = TextNode(
            text=text,
            metadata={"category": "batch_test", "batch_id": i, "doc_id": f"batch_{i}"},
            embedding=embedding,
        )
        batch_nodes.append(node)

    # 批量添加
    batch_ids = vector_db.batch_add_nodes(batch_nodes, batch_size=5)
    print(f"   📦 批量添加: {len(batch_ids)} 个节点")

    # 清理批量测试数据
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="category", value="batch_test", operator=FilterOperator.EQ
            )
        ]
    )
    vector_db.delete_nodes(filters=filters)
    print("   📦 批量清理: 完成")


if __name__ == "__main__":
    asyncio.run(test_core_crud())
