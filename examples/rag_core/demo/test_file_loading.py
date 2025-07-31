#!/usr/bin/env python3
"""
测试文件加载功能
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from loguru import logger

from backend.rag_core.rag_system import RAGSystem


async def test_file_loading():
    """测试文件加载功能"""
    print("\n📁 文件加载功能测试")
    print("=" * 50)

    async with RAGSystem() as rag:
        try:
            # 1. 设置Collection
            print("🔧 设置Collection...")
            await rag.setup_collection("general", overwrite=True)
            print("✅ Collection设置完成")

            # 2. 创建示例文档内容
            sample_content = """
# 人工智能技术概述

人工智能(AI)是计算机科学的一个重要分支，致力于创建能够模拟人类智能的系统。

## 主要技术领域

### 机器学习
机器学习是AI的核心技术，包括：
- 监督学习
- 无监督学习
- 强化学习

### 深度学习
深度学习使用神经网络：
- 卷积神经网络(CNN)
- 循环神经网络(RNN)
- Transformer架构

### 自然语言处理
NLP技术包括：
- 文本分析
- 语言生成
- 机器翻译

## 应用场景

AI技术广泛应用于：
1. 智能助手
2. 自动驾驶
3. 医疗诊断
4. 金融分析
5. 推荐系统
"""

            print("📝 准备添加示例文档...")
            print(f"   文档长度: {len(sample_content)} 字符")

            # 3. 添加文档
            result = await rag.add_text(
                text=sample_content,
                collection_name="general",
                metadata={
                    "title": "人工智能技术概述",
                    "type": "markdown",
                    "category": "technology",
                    "source": "技术文档",
                    "year": 2024,
                    "language": "zh",
                },
            )

            print(f"✅ 文档添加成功: {result} 个节点")

            # 4. 验证文档添加
            print("🔍 验证文档添加...")
            query_result = await rag.query(
                question="什么是人工智能？", collection_name="general"
            )

            print(f"✅ 查询验证成功")
            print(f"   回答长度: {len(query_result.answer)} 字符")
            print(f"   上下文数量: {len(query_result.retrieved_nodes)} 个")

            # 5. 显示部分回答
            print("\n📄 AI回答预览:")
            print("-" * 30)
            answer_preview = (
                query_result.answer[:200] + "..."
                if len(query_result.answer) > 200
                else query_result.answer
            )
            print(answer_preview)

            # 6. 显示上下文信息
            print(f"\n📚 使用的上下文文档:")
            for i, node_with_score in enumerate(query_result.retrieved_nodes, 1):
                node = node_with_score.node
                score = node_with_score.score
                metadata = node.metadata
                content_preview = (
                    node.text[:100] + "..." if len(node.text) > 100 else node.text
                )
                print(f"   {i}. 标题: {metadata.get('title', 'Unknown')}")
                print(f"      类别: {metadata.get('category', 'Unknown')}")
                print(f"      相似度: {score:.4f}")
                print(f"      内容: {content_preview}")
                print()

            print("🎉 文件加载功能测试完成！")

        except Exception as e:
            logger.error(f"测试失败: {e}")
            print(f"❌ 测试失败: {e}")
            raise


async def test_batch_loading():
    """测试批量文档加载"""
    print("\n📦 批量文档加载测试")
    print("=" * 50)

    async with RAGSystem() as rag:
        try:
            # 设置Collection
            await rag.setup_collection("general", overwrite=True)
            print("✅ Collection设置完成")

            # 准备多个文档
            documents = [
                {
                    "content": "机器学习是人工智能的一个子集，它使计算机能够在没有明确编程的情况下学习和改进。主要包括监督学习、无监督学习和强化学习。",
                    "metadata": {
                        "title": "机器学习基础",
                        "category": "technology",
                        "type": "educational",
                        "difficulty": "beginner",
                    },
                },
                {
                    "content": "深度学习是机器学习的一个分支，使用神经网络来模拟人脑的学习过程。它在图像识别、语音识别和自然语言处理等领域取得了突破性进展。",
                    "metadata": {
                        "title": "深度学习原理",
                        "category": "technology",
                        "type": "advanced",
                        "difficulty": "intermediate",
                    },
                },
                {
                    "content": "自然语言处理(NLP)是人工智能的一个重要分支，专注于让计算机理解、解释和生成人类语言。现代NLP广泛使用Transformer架构。",
                    "metadata": {
                        "title": "自然语言处理",
                        "category": "technology",
                        "type": "specialized",
                        "difficulty": "advanced",
                    },
                },
            ]

            # 批量添加文档
            total_nodes = 0
            for i, doc in enumerate(documents, 1):
                print(f"📝 添加文档 {i}: {doc['metadata']['title']}")
                result = await rag.add_text(
                    text=doc["content"],
                    collection_name="general",
                    metadata=doc["metadata"],
                )
                total_nodes += result
                print(f"   ✅ 添加了 {result} 个节点")

            print(f"\n✅ 批量添加完成: 总共 {total_nodes} 个节点")

            # 测试不同类型的查询
            test_queries = [
                "什么是机器学习？",
                "深度学习有什么特点？",
                "NLP技术的应用有哪些？",
            ]

            print("\n🔍 测试查询:")
            for i, query in enumerate(test_queries, 1):
                print(f"\n查询 {i}: {query}")
                result = await rag.query(question=query, collection_name="general")
                print(f"   回答: {result.answer[:100]}...")
                print(f"   上下文: {len(result.retrieved_nodes)} 个文档")

            print("\n🎉 批量文档加载测试完成！")

        except Exception as e:
            logger.error(f"批量测试失败: {e}")
            print(f"❌ 批量测试失败: {e}")
            raise


async def main():
    """主测试函数"""
    try:
        # 测试单个文档加载
        await test_file_loading()

        # 测试批量文档加载
        await test_batch_loading()

        print("\n" + "=" * 50)
        print("🎉 所有文件加载测试完成！")
        print("✅ 功能验证: 文档添加、查询验证、批量处理")
        print("=" * 50)

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        print(f"\n❌ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
