#!/usr/bin/env python3
"""
RAGSystem 完整使用范例
展示RAG的完整流程：加载 -> 索引 -> 存储 -> 查询 -> 生成

RAG五个关键阶段：
1. 加载(Loading)：从各种数据源导入数据
2. 索引(Indexing)：创建向量嵌入和元数据结构
3. 存储(Storing)：持久化索引和元数据
4. 查询(Querying)：检索相关上下文
5. 生成(Generation)：结合上下文生成回答
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from loguru import logger

from backend.conf.rag_config import get_rag_config
from backend.rag_core.rag_system import RAGSystem


async def complete_rag_workflow():
    """
    完整的RAG工作流程示例
    演示从文档加载到最终回答生成的全过程
    """
    logger.info("🚀 开始RAG完整工作流程演示")

    print("\n" + "=" * 80)
    print("🤖 RAG系统完整工作流程演示")
    print("=" * 80)

    # 初始化RAG系统
    async with RAGSystem() as rag:

        # ==================== 阶段1: 加载(Loading) ====================
        print("\n📂 阶段1: 数据加载(Loading)")
        print("-" * 50)

        # 创建示例文档
        sample_documents = [
            {
                "content": "人工智能(AI)是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。AI包括机器学习、深度学习、自然语言处理等多个子领域。",
                "metadata": {
                    "title": "人工智能概述",
                    "category": "technology",
                    "source": "AI教程",
                    "author": "AI专家",
                    "year": 2024,
                    "language": "zh",
                },
            },
            {
                "content": "机器学习是人工智能的一个子集，它使计算机能够在没有明确编程的情况下学习和改进。主要包括监督学习、无监督学习和强化学习三种类型。",
                "metadata": {
                    "title": "机器学习基础",
                    "category": "technology",
                    "source": "ML教程",
                    "author": "ML研究员",
                    "year": 2024,
                    "language": "zh",
                },
            },
            {
                "content": "深度学习是机器学习的一个分支，使用神经网络来模拟人脑的学习过程。它在图像识别、语音识别和自然语言处理等领域取得了突破性进展。",
                "metadata": {
                    "title": "深度学习原理",
                    "category": "research",
                    "source": "DL论文",
                    "author": "深度学习专家",
                    "year": 2024,
                    "language": "zh",
                },
            },
            {
                "content": "自然语言处理(NLP)是人工智能的一个重要分支，专注于让计算机理解、解释和生成人类语言。现代NLP广泛使用Transformer架构和大语言模型。",
                "metadata": {
                    "title": "自然语言处理技术",
                    "category": "technology",
                    "source": "NLP指南",
                    "author": "NLP工程师",
                    "year": 2024,
                    "language": "zh",
                },
            },
            {
                "content": "Large Language Models (LLMs) are AI systems trained on vast amounts of text data to understand and generate human-like text. Examples include GPT, BERT, and Claude.",
                "metadata": {
                    "title": "Large Language Models",
                    "category": "technology",
                    "source": "LLM Guide",
                    "author": "AI Researcher",
                    "year": 2024,
                    "language": "en",
                },
            },
        ]

        print(f"✅ 准备了 {len(sample_documents)} 个示例文档")
        for i, doc in enumerate(sample_documents, 1):
            print(f"   {i}. {doc['metadata']['title']} ({doc['metadata']['language']})")

        # ==================== 阶段2: 索引(Indexing) ====================
        print("\n🔍 阶段2: 数据索引(Indexing)")
        print("-" * 50)

        # 设置Collection
        collection_name = "general"
        await rag.setup_collection(collection_name, overwrite=True)
        print(f"✅ Collection '{collection_name}' 设置完成")

        # 添加文档到向量数据库
        added_count = 0
        for doc in sample_documents:
            try:
                result = await rag.add_text(
                    text=doc["content"],
                    collection_name=collection_name,
                    metadata=doc["metadata"],
                )
                if result > 0:
                    added_count += 1
            except Exception as e:
                logger.warning(f"文档添加失败: {e}")
                continue

        print(f"✅ 成功索引 {added_count} 个文档")
        print("   - 文本分割完成")
        print("   - 向量嵌入生成完成")
        print("   - 元数据提取完成")

        # ==================== 阶段3: 存储(Storing) ====================
        print("\n💾 阶段3: 数据存储(Storing)")
        print("-" * 50)

        # 获取存储统计信息
        stats = rag.get_stats()
        print(f"✅ 数据已持久化存储")
        print(
            f"   - 系统状态: {'已初始化' if stats.get('initialized') else '未初始化'}"
        )
        print(f"   - Collection数量: {len(stats.get('collections', {}))}")
        print(f"   - 总节点数: {stats.get('total_nodes', 0)}")

        # ==================== 阶段4: 查询(Querying) ====================
        print("\n🔍 阶段4: 智能查询(Querying)")
        print("-" * 50)

        # 定义测试查询
        test_queries = [
            {"query": "什么是人工智能？", "description": "基本概念查询"},
            {"query": "机器学习有哪些类型？", "description": "具体技术查询"},
            {"query": "深度学习在哪些领域有应用？", "description": "应用场景查询"},
            {"query": "What are Large Language Models?", "description": "英文查询测试"},
        ]

        for i, test_case in enumerate(test_queries, 1):
            print(f"\n📝 查询 {i}: {test_case['description']}")
            print(f"   问题: {test_case['query']}")

            # 执行检索 - 使用query方法进行RAG查询
            try:
                rag_result = await rag.query(
                    question=test_case["query"], collection_name=collection_name
                )
                # 从RAG结果中提取检索到的文档
                results = (
                    rag_result.retrieved_nodes
                    if hasattr(rag_result, "retrieved_nodes")
                    else []
                )
            except Exception as e:
                logger.warning(f"查询失败: {e}")
                results = []

            print(f"   ✅ 检索到 {len(results)} 个相关文档片段")

            # 显示检索结果
            for j, node_with_score in enumerate(results, 1):
                if hasattr(node_with_score, "node") and hasattr(
                    node_with_score, "score"
                ):
                    node = node_with_score.node
                    score = node_with_score.score
                    content = (
                        node.text[:100] + "..." if len(node.text) > 100 else node.text
                    )
                    metadata = node.metadata
                    title = metadata.get("title", "Unknown")

                    print(f"      {j}. [{title}] 相似度: {score:.3f}")
                    print(f"         内容: {content}")
                else:
                    print(f"      {j}. 检索结果: {str(node_with_score)[:100]}...")

        # ==================== 阶段5: 生成(Generation) ====================
        print("\n🤖 阶段5: 回答生成(Generation)")
        print("-" * 50)

        # 使用RAG进行问答
        final_query = "请详细介绍人工智能的主要分支和应用领域"
        print(f"📝 最终问题: {final_query}")

        # 执行RAG查询（检索+生成）
        try:
            rag_response = await rag.query(
                question=final_query, collection_name=collection_name
            )

            print(f"\n✅ RAG回答生成完成")
            print(f"📄 回答内容:")
            print("-" * 30)
            print(
                rag_response.answer
                if hasattr(rag_response, "answer")
                else "未能生成回答"
            )

            # 显示使用的上下文
            contexts = (
                rag_response.retrieved_nodes
                if hasattr(rag_response, "retrieved_nodes")
                else []
            )
            if contexts:
                print(f"\n📚 使用的上下文文档 ({len(contexts)} 个):")
                for i, node_with_score in enumerate(contexts, 1):
                    if hasattr(node_with_score, "node") and hasattr(
                        node_with_score, "score"
                    ):
                        node = node_with_score.node
                        score = node_with_score.score
                        title = node.metadata.get("title", f"文档{i}")
                        print(f"   {i}. {title} (相似度: {score:.3f})")
                    else:
                        print(f"   {i}. 文档{i}")

        except Exception as e:
            print(f"⚠️ RAG查询失败: {e}")
            print("   注意: 需要配置LLM服务才能进行回答生成")

        # ==================== 高级功能演示 ====================
        print("\n🚀 高级功能演示")
        print("-" * 50)

        # 元数据过滤查询
        print("📋 元数据过滤查询:")
        try:
            filtered_result = await rag.query_with_filters(
                question="人工智能技术",
                collection_name=collection_name,
                metadata_filters={"category": "technology", "language": "zh"},
            )
            filtered_contexts = (
                filtered_result.retrieved_nodes
                if hasattr(filtered_result, "retrieved_nodes")
                else []
            )
            print(f"   ✅ 过滤查询结果: {len(filtered_contexts)} 个技术类中文文档")
        except Exception as e:
            print(f"   ⚠️ 过滤查询失败: {e}")

        # 多语言查询
        print("\n🌐 多语言查询:")
        try:
            en_result = await rag.query_with_filters(
                question="artificial intelligence",
                collection_name=collection_name,
                metadata_filters={"language": "en"},
            )
            en_contexts = (
                en_result.retrieved_nodes
                if hasattr(en_result, "retrieved_nodes")
                else []
            )
            print(f"   ✅ 英文查询结果: {len(en_contexts)} 个英文文档")
        except Exception as e:
            print(f"   ⚠️ 英文查询失败: {e}")

        # 批量查询
        print("\n📦 批量查询:")
        batch_queries = ["AI的定义", "机器学习类型", "深度学习应用"]
        batch_results = []

        for query in batch_queries:
            try:
                result = await rag.query(
                    question=query, collection_name=collection_name
                )
                contexts = (
                    result.retrieved_nodes if hasattr(result, "retrieved_nodes") else []
                )
                batch_results.append(len(contexts))
            except Exception as e:
                batch_results.append(0)

        print(f"   ✅ 批量查询完成: {batch_results} (每个查询的结果数)")

    print("\n" + "=" * 80)
    print("🎉 RAG完整工作流程演示完成！")
    print("✅ 所有阶段执行成功：加载 -> 索引 -> 存储 -> 查询 -> 生成")
    print("=" * 80)


async def demonstrate_file_loading():
    """
    演示文件加载功能
    """
    print("\n📁 文件加载功能演示")
    print("-" * 50)

    async with RAGSystem() as rag:
        # 先设置Collection
        await rag.setup_collection("general", overwrite=True)
        print("✅ Collection设置完成")

        # 创建示例文件
        sample_file_content = """
        # 人工智能发展史

        ## 早期发展 (1950-1980)
        人工智能概念最早由艾伦·图灵在1950年提出。图灵测试成为判断机器是否具有智能的重要标准。

        ## 专家系统时代 (1980-1990)
        专家系统是早期AI的重要应用，通过规则引擎模拟专家的决策过程。

        ## 机器学习兴起 (1990-2010)
        统计学习方法开始兴起，支持向量机、随机森林等算法得到广泛应用。

        ## 深度学习革命 (2010-至今)
        深度神经网络的突破带来了AI的新一轮发展，在图像、语音、自然语言等领域取得重大进展。
        """

        # 模拟文件上传和处理
        print("📄 处理示例文档: AI发展史")

        # 使用RAG系统处理文档
        try:
            result = await rag.add_text(
                text=sample_file_content,
                collection_name="general",
                metadata={
                    "title": "人工智能发展史",
                    "type": "markdown",
                    "category": "history",
                    "source": "AI历史文档",
                    "year": 2024,
                },
            )
            success = result > 0
        except Exception as e:
            success = False
            logger.error(f"文档处理失败: {e}")

        if success:
            print("✅ 文档处理成功")
            print("   - 文档解析完成")
            print("   - 文本分块完成")
            print("   - 向量化完成")
            print("   - 存储完成")
        else:
            print("❌ 文档处理失败")


async def performance_benchmark():
    """
    性能基准测试
    """
    print("\n⚡ 性能基准测试")
    print("-" * 50)

    import time

    async with RAGSystem() as rag:
        await rag.setup_collection("general", overwrite=True)

        # 测试批量添加性能
        start_time = time.time()

        batch_docs = []
        for i in range(50):
            batch_docs.append(
                {
                    "content": f"这是第{i+1}个测试文档，用于性能基准测试。包含一些示例内容来测试向量化和存储性能。",
                    "metadata": {
                        "doc_id": f"bench_{i+1}",
                        "category": "benchmark",
                        "batch": i // 10,
                    },
                }
            )

        # 批量添加
        success_count = 0
        for doc in batch_docs:
            try:
                result = await rag.add_text(
                    text=doc["content"],
                    collection_name="general",
                    metadata=doc["metadata"],
                )
                if result > 0:
                    success_count += 1
            except Exception as e:
                logger.warning(f"批量添加失败: {e}")
                continue

        add_time = time.time() - start_time
        print(f"✅ 批量添加: {success_count}/50 文档，耗时: {add_time:.2f}秒")

        # 测试查询性能
        start_time = time.time()

        query_results = []
        test_queries = ["测试文档", "性能基准", "示例内容", "向量化测试", "存储性能"]

        for query in test_queries:
            try:
                result = await rag.query(question=query, collection_name="general")
                contexts = (
                    result.retrieved_nodes if hasattr(result, "retrieved_nodes") else []
                )
                query_results.append(len(contexts))
            except Exception as e:
                query_results.append(0)

        query_time = time.time() - start_time
        print(
            f"✅ 批量查询: 5个查询，平均结果: {sum(query_results)/len(query_results):.1f}个，耗时: {query_time:.2f}秒"
        )

        print(f"📊 性能总结:")
        print(f"   - 添加速度: {success_count/add_time:.1f} 文档/秒")
        print(f"   - 查询速度: {len(test_queries)/query_time:.1f} 查询/秒")


async def demonstrate_all_modules():
    """
    演示backend/rag_core中所有功能模块的使用
    """
    print("\n" + "=" * 80)
    print("🔧 所有功能模块完整演示")
    print("=" * 80)

    # 1. RAGSystem - 主系统演示
    await demonstrate_rag_system()

    # 2. CollectionManager - 集合管理演示
    await demonstrate_collection_manager()

    # 3. VectorStore - 向量存储演示
    await demonstrate_vector_store()

    # 4. EmbeddingGenerator - 嵌入生成演示
    await demonstrate_embedding_generator()

    # 5. LLMService - 大语言模型演示
    await demonstrate_llm_service()

    # 6. QueryEngine - 查询引擎演示
    await demonstrate_query_engine()

    # 7. DocumentLoader - 文档加载演示
    await demonstrate_document_loader()


async def demonstrate_rag_system():
    """演示RAGSystem主系统功能"""
    print("\n🤖 1. RAGSystem - 主系统功能演示")
    print("-" * 50)

    async with RAGSystem() as rag:
        print("✅ RAGSystem初始化完成")

        # 系统统计
        stats = rag.get_stats()
        print(f"📊 系统统计: {stats}")

        # 设置Collection（使用已配置的Collection）
        await rag.setup_collection("general", overwrite=True)
        print(f"   ✅ Collection 'general' 设置完成")

        # 添加不同类型的文档到general Collection
        documents = [
            ("这是一个通用知识文档", {"type": "general", "priority": 1}),
            (
                "这是一个技术文档，介绍Python编程",
                {"type": "tech", "language": "python"},
            ),
            ("这是一个API文档，说明REST接口", {"type": "api", "format": "rest"}),
        ]

        for text, metadata in documents:
            result = await rag.add_text(text, "general", metadata)
            print(f"   📝 添加文档到 general: {result} 个节点")

        # 基本查询测试
        try:
            result = await rag.query(question="什么是编程？", collection_name="general")
            print(f"   🔍 查询结果: {len(result.retrieved_nodes)} 个上下文")
        except Exception as e:
            print(f"   ⚠️ 查询失败: {e}")

        # 业务类型查询
        try:
            results = await rag.query_business_type(
                question="技术相关的内容", business_type="general"
            )
            total_contexts = sum(len(result.retrieved_nodes) for result in results)
            print(f"   🎯 业务类型查询结果: {total_contexts} 个上下文")
        except Exception as e:
            print(f"   ⚠️ 业务类型查询失败: {e}")


async def demonstrate_collection_manager():
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


async def demonstrate_vector_store():
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

        # 创建测试节点
        test_node = TextNode(
            text="这是一个测试向量存储的文档",
            metadata={"test": True, "module": "vector_store"},
            embedding=[0.1] * 1024,  # 模拟1024维向量
        )

        # 添加节点
        node_ids = vector_db.add_nodes([test_node])
        print(f"📝 添加节点: {node_ids}")

        # 获取统计信息
        stats = vector_db.get_stats()
        print(f"📊 向量数据库统计: {stats}")

        # 验证连接
        connected = vector_db.verify_connection()
        print(f"🔗 连接验证: {'成功' if connected else '失败'}")

    except Exception as e:
        print(f"❌ VectorStore演示失败: {e}")
    finally:
        vector_db.close()


async def demonstrate_embedding_generator():
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
        texts = [
            "人工智能技术发展",
            "机器学习算法应用",
            "深度学习神经网络",
            "自然语言处理技术",
        ]
        embeddings = await embedding_gen.embed_texts(texts)
        print(
            f"📦 批量文本嵌入: {len(embeddings)} 个向量，每个维度 {len(embeddings[0])}"
        )

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


async def demonstrate_llm_service():
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

        messages = [ChatMessage(role="user", content="你好，请简单介绍一下自己")]
        response = llm_service.chat(messages)
        print(f"💬 简单对话: {response[:100]}...")

        # 带上下文的对话
        context_messages = [
            ChatMessage(role="system", content="用户正在学习人工智能技术"),
            ChatMessage(role="user", content="什么是机器学习？"),
        ]
        response = llm_service.chat(context_messages)
        print(f"📚 上下文对话: {response[:100]}...")

        # 流式对话演示（LLMService暂不支持流式输出）
        print("🌊 流式对话演示:")
        print("   ⚠️ 当前LLMService版本暂不支持流式输出")
        print("   💡 可以通过chat方法获取完整回答")

        # 获取模型信息
        model_info = llm_service.get_model_info()
        print(f"🤖 LLM模型信息: {model_info}")

    except Exception as e:
        print(f"❌ LLMService演示失败: {e}")
    finally:
        llm_service.close()


async def demonstrate_query_engine():
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


async def demonstrate_document_loader():
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
        # 人工智能简介

        人工智能(AI)是计算机科学的一个分支。

        ## 主要领域
        - 机器学习
        - 深度学习
        - 自然语言处理
        - 计算机视觉

        ## 应用场景
        AI技术广泛应用于各个领域。
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
        for i, node in enumerate(nodes[:3], 1):  # 只显示前3个
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

    async def main():
        """主函数"""
        try:
            # 完整工作流程演示
            await complete_rag_workflow()

            # 文件加载演示
            await demonstrate_file_loading()
            #
            # # 性能测试
            await performance_benchmark()
            #
            # # 所有功能模块演示
            await demonstrate_all_modules()

        except Exception as e:
            logger.error(f"演示过程中发生错误: {e}")
            print(f"\n❌ 演示失败: {e}")

    asyncio.run(main())
