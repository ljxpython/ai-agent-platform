"""
大语言模型服务模块
基于LlamaIndex和DeepSeek的LLM服务实现
"""

from typing import Any, Dict, List

from llama_index.core.base.llms.base import BaseLLM
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.llms.deepseek import DeepSeek
from loguru import logger

from backend.conf.rag_config import RAGConfig


class LLMService:
    """大语言模型服务"""

    def __init__(self, config: RAGConfig):
        """
        初始化LLM服务

        Args:
            config: RAG配置
        """
        self.config = config.deepseek
        self.llm: BaseLLM = None
        self._initialized = False

        logger.info(f"🤖 LLM服务初始化 - 模型: {self.config.model}")

    def initialize(self):
        """初始化LLM模型"""
        if self._initialized:
            return

        logger.info("🚀 正在初始化DeepSeek LLM模型...")

        try:
            # 使用LlamaIndex官方DeepSeek实现
            self.llm = DeepSeek(
                model=self.config.model,
                api_key=self.config.api_key,
                temperature=0.1,
                max_tokens=2048,
            )

            # 测试模型是否可用
            test_response = self.llm.complete("请说'测试成功'")
            logger.debug(f"模型测试响应: {test_response.text[:50]}...")

            self._initialized = True
            logger.success("✅ DeepSeek LLM模型初始化成功")

        except Exception as e:
            logger.error(f"❌ DeepSeek LLM模型初始化失败: {e}")
            raise

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        生成文本响应

        Args:
            prompt: 输入提示
            **kwargs: 其他参数

        Returns:
            str: 生成的响应
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"💭 生成响应 - 提示长度: {len(prompt)}")

        try:
            # 生成响应
            response = self.llm.complete(prompt)

            logger.success("✅ 响应生成完成")
            return response.text

        except Exception as e:
            logger.error(f"❌ 响应生成失败: {e}")
            raise

    def chat(self, messages: List[ChatMessage], **kwargs) -> str:
        """
        聊天对话

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            str: 聊天响应
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"💬 聊天对话 - 消息数量: {len(messages)}")

        try:
            # 生成聊天响应
            response = self.llm.chat(messages)

            logger.success("✅ 聊天响应生成完成")
            return response.message.content

        except Exception as e:
            logger.error(f"❌ 聊天响应生成失败: {e}")
            raise

    def generate_rag_response(self, query: str, context: str, **kwargs) -> str:
        """
        基于检索上下文生成RAG响应

        Args:
            query: 用户查询
            context: 检索到的上下文
            **kwargs: 其他参数

        Returns:
            str: RAG响应
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"🔍 生成RAG响应 - 查询: {query[:50]}...")

        try:
            # 构建RAG提示
            rag_prompt = self._build_rag_prompt(query, context)

            # 生成响应
            response = self.generate_response(rag_prompt, **kwargs)

            logger.success("✅ RAG响应生成完成")
            return response

        except Exception as e:
            logger.error(f"❌ RAG响应生成失败: {e}")
            raise

    def _build_rag_prompt(self, query: str, context: str) -> str:
        """
        构建RAG提示模板

        Args:
            query: 用户查询
            context: 检索上下文

        Returns:
            str: 构建的提示
        """
        prompt_template = """你是一个专业的AI助手。请基于以下提供的上下文信息来回答用户的问题。

上下文信息：
{context}

用户问题：{query}

请根据上下文信息准确回答问题。如果上下文中没有相关信息，请明确说明。回答要简洁明了，重点突出。

回答："""

        return prompt_template.format(context=context, query=query)

    def _build_business_rag_prompt(
        self, query: str, context: str, business_type: str
    ) -> str:
        """
        构建业务专用RAG提示模板

        Args:
            query: 用户查询
            context: 检索上下文
            business_type: 业务类型

        Returns:
            str: 构建的提示
        """
        business_prompts = {
            "testcase": """你是一个专业的测试用例专家。请基于以下测试相关的上下文信息来回答用户的问题。

测试知识库信息：
{context}

用户问题：{query}

请根据测试知识库信息准确回答问题，重点关注测试用例设计、测试策略、测试方法等方面。如果知识库中没有相关信息，请明确说明。

专业回答：""",
            "ui_testing": """你是一个专业的UI测试专家。请基于以下UI测试相关的上下文信息来回答用户的问题。

UI测试知识库信息：
{context}

用户问题：{query}

请根据UI测试知识库信息准确回答问题，重点关注UI自动化测试、页面元素定位、测试脚本编写等方面。如果知识库中没有相关信息，请明确说明。

专业回答：""",
            "ai_chat": """你是一个专业的AI对话助手。请基于以下AI相关的上下文信息来回答用户的问题。

AI知识库信息：
{context}

用户问题：{query}

请根据AI知识库信息准确回答问题，重点关注人工智能、机器学习、深度学习等方面。如果知识库中没有相关信息，请明确说明。

专业回答：""",
        }

        template = business_prompts.get(
            business_type, self._build_rag_prompt(query, context)
        )
        if isinstance(template, str) and "{context}" in template:
            return template.format(context=context, query=query)
        else:
            return template

    def generate_business_rag_response(
        self, query: str, context: str, business_type: str, **kwargs
    ) -> str:
        """
        基于业务类型生成专业RAG响应

        Args:
            query: 用户查询
            context: 检索到的上下文
            business_type: 业务类型
            **kwargs: 其他参数

        Returns:
            str: RAG响应
        """
        if not self._initialized:
            self.initialize()

        logger.info(
            f"🔍 生成业务RAG响应 - 业务类型: {business_type}, 查询: {query[:50]}..."
        )

        try:
            # 构建业务专用RAG提示
            rag_prompt = self._build_business_rag_prompt(query, context, business_type)

            # 生成响应
            response = self.generate_response(rag_prompt, **kwargs)

            logger.success(f"✅ 业务RAG响应生成完成 - 业务类型: {business_type}")
            return response

        except Exception as e:
            logger.error(f"❌ 业务RAG响应生成失败 - 业务类型: {business_type}: {e}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            Dict[str, Any]: 模型信息
        """
        return {
            "model": self.config.model,
            "base_url": self.config.base_url,
            "initialized": self._initialized,
        }

    def close(self):
        """清理资源"""
        if self.llm:
            # LlamaIndex的LLM通常不需要显式关闭
            pass

        self._initialized = False
        logger.info("🔄 LLM服务资源清理完成")


def create_llm_service(config: RAGConfig) -> LLMService:
    """
    创建并初始化LLM服务

    Args:
        config: RAG配置

    Returns:
        LLMService: 初始化后的LLM服务
    """
    service = LLMService(config)
    service.initialize()
    return service


if __name__ == "__main__":
    print("************************* LLM服务测试 *************************")
    # 测试代码
    from backend.conf.rag_config import get_rag_config

    config = get_rag_config()
    llm_service = create_llm_service(config)

    # 测试基本响应生成
    test_prompt = "请简单介绍一下人工智能"
    response = llm_service.generate_response(test_prompt)
    print(f"基本响应: {response}")

    # 测试聊天功能
    messages = [ChatMessage(role=MessageRole.USER, content="你好，请介绍一下机器学习")]
    chat_response = llm_service.chat(messages)
    print(f"聊天响应: {chat_response}")

    # 测试RAG响应
    test_context = """
    人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。
    机器学习是人工智能的一个子集，它使计算机能够从数据中学习而无需明确编程。
    """
    test_query = "什么是机器学习？"
    rag_response = llm_service.generate_rag_response(test_query, test_context)
    print(f"RAG响应: {rag_response}")

    # 测试业务RAG响应
    business_rag_response = llm_service.generate_business_rag_response(
        test_query, test_context, "ai_chat"
    )
    print(f"业务RAG响应: {business_rag_response}")

    # 获取模型信息
    model_info = llm_service.get_model_info()
    print(f"模型信息: {model_info}")

    llm_service.close()
