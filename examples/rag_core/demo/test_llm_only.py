#!/usr/bin/env python3
"""
单独测试LLMService
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from loguru import logger


async def test_llm_service_only():
    """单独测试LLMService"""
    print("\n🤖 LLMService - 单独测试")
    print("-" * 50)

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.llm_service import ChatMessage, LLMService

    config = get_rag_config()
    llm_service = LLMService(config)

    try:
        # 初始化LLM（不是异步方法）
        llm_service.initialize()
        print("✅ LLM服务初始化成功")

        # 简单对话（使用正确的方法）
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

        print("✅ LLMService测试成功")

    except Exception as e:
        print(f"❌ LLMService测试失败: {e}")
        raise
    finally:
        llm_service.close()


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🤖 LLMService单独测试")
    print("=" * 60)

    try:
        await test_llm_service_only()

        print("\n" + "=" * 60)
        print("🎉 LLMService单独测试完成！")
        print("=" * 60)

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        print(f"\n❌ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
