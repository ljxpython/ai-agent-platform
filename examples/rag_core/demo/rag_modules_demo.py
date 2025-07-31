#!/usr/bin/env python3
"""
RAG系统所有功能模块演示
展示backend/rag_core中每个模块的核心功能
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from loguru import logger


async def main():
    """主演示函数"""
    print("\n" + "=" * 80)
    print("🔧 RAG系统所有功能模块演示")
    print("=" * 80)

    try:
        # 1. RAGSystem - 主系统演示
        await demo_rag_system()

        # 2. CollectionManager - 集合管理演示
        await demo_collection_manager()

        # 3. VectorStore - 向量存储演示
        await demo_vector_store()

        # 4. EmbeddingGenerator - 嵌入生成演示
        await demo_embedding_generator()

        # 5. LLMService - 大语言模型演示
        await demo_llm_service()

        # 6. QueryEngine - 查询引擎演示
        await demo_query_engine()

        # 7. DocumentLoader - 文档加载演示
        await demo_document_loader()

        print("\n" + "=" * 80)
        print("🎉 所有模块演示完成！")
        print("=" * 80)

    except Exception as e:
        logger.error(f"演示过程中发生错误: {e}")
        print(f"\n❌ 演示失败: {e}")


async def demo_rag_system():
    """演示RAGSystem主系统功能"""
    print("\n🤖 1. RAGSystem - 主系统功能演示")
    print("-" * 50)

    from backend.rag_core.rag_system import RAGSystem

    async with RAGSystem() as rag:
        print("✅ RAGSystem初始化完成")

        # 系统统计
        stats = rag.get_stats()
        print(f"📊 系统统计: 初始化状态={stats.get('initialized', False)}")

        # 设置Collection
        await rag.setup_collection("general", overwrite=True)
        print("✅ Collection设置完成")

        # 添加文档
        result = await rag.add_text(
            text="这是RAGSystem演示文档",
            collection_name="general",
            metadata={"demo": "rag_system", "type": "test"},
        )
        print(f"📝 添加文档: {result} 个节点")

        # 查询文档
        try:
            query_result = await rag.query(
                question="RAGSystem演示", collection_name="general"
            )
            print(f"🔍 查询结果: {len(query_result.retrieved_nodes)} 个上下文")
        except Exception as e:
            print(f"⚠️ 查询失败: {e}")


async def demo_collection_manager():
    """演示CollectionManager集合管理功能"""
    print("\n🗂️ 2. CollectionManager - 集合管理功能演示")
    print("-" * 50)

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.collection_manager import CollectionManager

    config = get_rag_config()
    manager = CollectionManager(config)

    try:
        # 获取Collection
        collection = manager.get_collection("general")
        collection_name = collection.collection_name if collection else "None"
        print(f"✅ 获取Collection: {collection_name}")

        # 列出所有Collection
        collections = manager.list_collections()
        print(f"📋 所有Collection: {collections}")

        # 检查Collection状态
        for name in collections[:3]:  # 只检查前3个
            status = manager.is_collection_initialized(name)
            print(f"   📊 {name}: {'已初始化' if status else '未初始化'}")

    except Exception as e:
        print(f"❌ CollectionManager演示失败: {e}")
    finally:
        await manager.close()


async def demo_vector_store():
    """演示VectorStore向量存储功能"""
    print("\n🗄️ 3. VectorStore - 向量存储功能演示")
    print("-" * 50)

    from llama_index.core.schema import TextNode

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.vector_store import MilvusVectorDB

    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    vector_db = MilvusVectorDB(config, collection_config)

    try:
        # 初始化连接
        vector_db.initialize()
        print("✅ 向量数据库连接成功")

        # 检查Collection存在性
        exists = vector_db.collection_exists()
        print(f"📊 Collection存在: {exists}")

        # 获取统计信息
        stats = vector_db.get_stats()
        print(f"📊 向量数据库统计: 维度={stats.get('dimension', 'N/A')}")

        # 验证连接
        connected = vector_db.verify_connection()
        print(f"🔗 连接验证: {'成功' if connected else '失败'}")

    except Exception as e:
        print(f"❌ VectorStore演示失败: {e}")
    finally:
        vector_db.close()


async def demo_embedding_generator():
    """演示EmbeddingGenerator嵌入生成功能"""
    print("\n🔢 4. EmbeddingGenerator - 嵌入生成功能演示")
    print("-" * 50)

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.embedding_generator import EmbeddingGenerator

    config = get_rag_config()
    embedding_gen = EmbeddingGenerator(config)

    try:
        # 初始化嵌入模型
        await embedding_gen.initialize()
        print("✅ 嵌入模型初始化成功")

        # 单个文本嵌入
        text = "这是一个测试文本"
        embedding = await embedding_gen.embed_query(text)
        print(f"📝 单个文本嵌入: 维度 {len(embedding)}")

        # 批量文本嵌入
        texts = ["人工智能", "机器学习", "深度学习"]
        embeddings = await embedding_gen.embed_texts(texts)
        print(f"📦 批量文本嵌入: {len(embeddings)} 个向量")

        # 嵌入相似性计算（手动实现）
        import numpy as np

        vec1 = np.array(embeddings[0])
        vec2 = np.array(embeddings[1])
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        print(f"🔍 向量相似性: {similarity:.4f}")

        # 获取模型信息
        model_info = embedding_gen.get_model_info()
        print(f"🤖 模型信息: {model_info}")

    except Exception as e:
        print(f"❌ EmbeddingGenerator演示失败: {e}")
    finally:
        await embedding_gen.close()


async def demo_llm_service():
    """演示LLMService大语言模型功能"""
    print("\n🤖 5. LLMService - 大语言模型功能演示")
    print("-" * 50)

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.llm_service import LLMService

    config = get_rag_config()
    llm_service = LLMService(config)

    try:
        # 初始化LLM（不是异步方法）
        llm_service.initialize()
        print("✅ LLM服务初始化成功")

        # 简单对话（使用正确的方法）
        from backend.rag_core.llm_service import ChatMessage

        messages = [ChatMessage(role="user", content="请用一句话介绍人工智能")]
        response = llm_service.chat(messages)
        print(f"💬 简单对话: {response[:100]}...")

        # 带上下文的对话
        context_messages = [
            ChatMessage(role="system", content="用户正在学习RAG技术"),
            ChatMessage(role="user", content="什么是RAG？"),
        ]
        response = llm_service.chat(context_messages)
        print(f"📚 上下文对话: {response[:100]}...")

        # 获取模型信息
        model_info = llm_service.get_model_info()
        print(f"🤖 LLM模型信息: {model_info}")

    except Exception as e:
        print(f"❌ LLMService演示失败: {e}")
    finally:
        llm_service.close()


async def demo_query_engine():
    """演示RAGQueryEngine查询引擎功能"""
    print("\n🔍 6. RAGQueryEngine - 查询引擎功能演示")
    print("-" * 50)

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.query_engine import RAGQueryEngine

    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    query_engine = RAGQueryEngine(config, collection_config)

    try:
        # 初始化查询引擎
        await query_engine.initialize()
        print("✅ 查询引擎初始化成功")

        # 基本查询
        result = await query_engine.query("什么是人工智能？")
        print(f"🔍 基本查询结果: {len(result.retrieved_nodes)} 个上下文")

        # 带过滤的查询（RAGQueryEngine暂不支持过滤查询）
        print("🔍 过滤查询:")
        print("   ⚠️ 当前RAGQueryEngine版本暂不支持过滤查询")
        print("   💡 可以通过RAGSystem的query_with_filters方法实现")

        # 检索功能测试
        retrieve_result = await query_engine.retrieve_only("机器学习", top_k=3)
        print(f"🔍 检索测试: {len(retrieve_result)} 个结果")

        # 获取引擎统计
        stats = query_engine.get_stats()
        print(f"📊 查询引擎统计: {stats}")

    except Exception as e:
        print(f"❌ QueryEngine演示失败: {e}")
    finally:
        await query_engine.close()


async def demo_document_loader():
    """演示DocumentLoader文档加载功能"""
    print("\n📚 7. DocumentLoader - 文档加载功能演示")
    print("-" * 50)

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.data_loader import DocumentLoader

    config = get_rag_config()
    collection_config = config.get_collection_config("general")

    loader = DocumentLoader(collection_config)

    try:
        print("✅ 文档加载器初始化成功")

        # 从文本创建文档
        text_content = """
        # RAG技术简介

        RAG (Retrieval-Augmented Generation) 是一种结合检索和生成的AI技术。

        ## 主要组件
        - 向量数据库
        - 嵌入模型
        - 大语言模型

        ## 应用场景
        RAG技术广泛应用于问答系统、知识库等领域。
        """

        documents = loader.load_from_text(text_content)
        document = documents[0] if documents else None
        if document:
            print(f"📝 从文本创建文档: {len(document.text)} 字符")
        else:
            print("❌ 文档创建失败")
            return

        # 文档分割
        nodes = loader.split_documents(documents)
        print(f"✂️ 文档分割结果: {len(nodes)} 个节点")

        # 显示分割后的节点
        for i, node in enumerate(nodes[:2], 1):  # 只显示前2个
            print(f"   📄 节点 {i}: {len(node.text)} 字符")
            print(f"      内容预览: {node.text[:50]}...")

        # 元数据提取（DocumentLoader暂不支持自动元数据提取）
        print("🏷️ 元数据提取:")
        print("   ⚠️ 当前DocumentLoader版本暂不支持自动元数据提取")
        print("   💡 可以在添加文档时手动指定元数据")

        # 支持的文件类型（DocumentLoader暂不提供此方法）
        print("📋 支持的文件类型:")
        print("   ⚠️ 当前DocumentLoader版本暂不提供get_supported_file_types方法")
        print("   💡 支持常见格式: txt, md, pdf, docx等")

    except Exception as e:
        print(f"❌ DocumentLoader演示失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
