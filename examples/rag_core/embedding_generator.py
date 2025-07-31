"""
嵌入生成模块
基于LlamaIndex和Ollama的嵌入向量生成器
"""

import asyncio
from typing import List

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.embeddings.ollama import OllamaEmbedding
from loguru import logger

from backend.conf.rag_config import RAGConfig


class EmbeddingGenerator:
    """嵌入向量生成器"""

    def __init__(self, config: RAGConfig):
        """
        初始化嵌入生成器

        Args:
            config: RAG配置
        """
        self.config = config.ollama
        self.embedding_model: BaseEmbedding = None
        self._initialized = False

        logger.info(f"🔧 嵌入生成器初始化 - 模型: {self.config.embedding_model}")

    async def initialize(self):
        """初始化嵌入模型"""
        if self._initialized:
            return

        logger.info("🚀 正在初始化嵌入模型...")

        try:
            # 创建Ollama嵌入模型
            self.embedding_model = OllamaEmbedding(
                model_name=self.config.embedding_model,
                base_url=self.config.base_url,
                ollama_additional_kwargs={"mirostat": 0},
            )

            # 测试模型是否可用
            test_text = "测试文本"
            await self.embedding_model.aget_text_embedding(test_text)

            self._initialized = True
            logger.success("✅ 嵌入模型初始化成功")

        except Exception as e:
            logger.error(f"❌ 嵌入模型初始化失败: {e}")
            raise

    async def embed_text(self, text: str) -> List[float]:
        """
        生成单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入向量
        """
        if not self._initialized:
            await self.initialize()

        try:
            embedding = await self.embedding_model.aget_text_embedding(text)
            return embedding

        except Exception as e:
            logger.error(f"❌ 文本嵌入生成失败: {e}")
            raise

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文本嵌入向量

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not self._initialized:
            await self.initialize()

        if not texts:
            return []

        logger.info(f"📝 批量生成嵌入向量 - 文本数量: {len(texts)}")

        try:
            # 使用异步方式批量处理
            tasks = [self.embedding_model.aget_text_embedding(text) for text in texts]
            embeddings = await asyncio.gather(*tasks)

            logger.success(f"✅ 批量嵌入生成完成: {len(embeddings)} 个向量")
            return embeddings

        except Exception as e:
            logger.error(f"❌ 批量嵌入生成失败: {e}")
            raise

    async def embed_query(self, query: str) -> List[float]:
        """
        异步方式生成查询嵌入向量

        Args:
            query: 查询文本

        Returns:
            List[float]: 嵌入向量
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 使用异步方法
            embedding = await self.embedding_model.aget_query_embedding(query)
            return embedding

        except Exception as e:
            logger.error(f"❌ 查询嵌入生成失败: {e}")
            raise

    def embed_query_sync(self, query: str) -> List[float]:
        """
        同步方式生成查询嵌入向量

        Args:
            query: 查询文本

        Returns:
            List[float]: 嵌入向量
        """
        if not self._initialized:
            # 同步初始化
            asyncio.run(self.initialize())

        try:
            # 使用同步方法
            embedding = self.embedding_model.get_text_embedding(query)
            return embedding

        except Exception as e:
            logger.error(f"❌ 查询嵌入生成失败: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """
        获取嵌入向量维度

        Returns:
            int: 向量维度
        """
        # 根据模型动态获取维度
        if self.config.embedding_model == "bge-m3":
            return 1024
        elif self.config.embedding_model == "nomic-embed-text":
            return 768
        else:
            # 默认使用配置中的维度
            from backend.conf.rag_config import get_rag_config

            rag_config = get_rag_config()
            return rag_config.milvus.dimension

    def get_model_info(self) -> dict:
        """
        获取模型信息

        Returns:
            dict: 模型信息
        """
        return {
            "model_name": self.config.embedding_model,
            "base_url": self.config.base_url,
            "dimension": self.get_embedding_dimension(),
            "initialized": self._initialized,
        }

    async def close(self):
        """清理资源"""
        if self.embedding_model:
            # LlamaIndex的嵌入模型通常不需要显式关闭
            pass

        self._initialized = False
        logger.info("🔄 嵌入生成器资源清理完成")


async def create_embedding_generator(config: RAGConfig) -> EmbeddingGenerator:
    """
    创建并初始化嵌入生成器

    Args:
        config: RAG配置

    Returns:
        EmbeddingGenerator: 初始化后的嵌入生成器
    """
    generator = EmbeddingGenerator(config)
    await generator.initialize()
    return generator


if __name__ == "__main__":
    print(
        "*********************************EmbeddingGenerator模块测试**********************************"
    )

    # 测试代码
    async def test_embedding_generator():
        from backend.conf.rag_config import get_rag_config

        config = get_rag_config()
        generator = await create_embedding_generator(config)

        # 测试单个文本嵌入
        test_text = "这是一个测试文本"
        embedding = await generator.embed_text(test_text)
        print(f"单个文本嵌入维度: {len(embedding)}")

        # 测试批量文本嵌入
        test_texts = [
            "人工智能是计算机科学的一个分支",
            "机器学习是人工智能的子集",
            "深度学习使用神经网络",
        ]

        embeddings = await generator.embed_texts(test_texts)
        print(f"批量嵌入数量: {len(embeddings)}")
        print(f"每个嵌入维度: {len(embeddings[0])}")

        # 测试查询嵌入
        query_embedding = await generator.embed_query("什么是人工智能？")
        print(f"查询嵌入维度: {len(query_embedding)}")

        # 测试同步查询嵌入
        sync_query_embedding = generator.embed_query_sync("什么是机器学习？")
        print(f"同步查询嵌入维度: {len(sync_query_embedding)}")

        # 获取模型信息
        model_info = generator.get_model_info()
        print(f"模型信息: {model_info}")

        await generator.close()

    asyncio.run(test_embedding_generator())
