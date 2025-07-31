"""
查询引擎模块
基于LlamaIndex的查询引擎实现，整合向量检索和LLM生成
支持多collection架构
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.schema import BaseNode, NodeWithScore, QueryBundle
from loguru import logger

from backend.conf.rag_config import CollectionConfig, RAGConfig
from backend.rag_core.embedding_generator import EmbeddingGenerator
from backend.rag_core.llm_service import LLMService
from backend.rag_core.vector_store import MilvusVectorDB


@dataclass
class QueryResult:
    """查询结果数据结构"""

    query: str
    answer: str
    retrieved_nodes: List[NodeWithScore]
    response_time: float
    metadata: Dict[str, Any]
    collection_name: str
    business_type: str


class RAGQueryEngine:
    """RAG查询引擎，支持多collection"""

    def __init__(self, config: RAGConfig, collection_config: CollectionConfig):
        """
        初始化查询引擎

        Args:
            config: RAG总配置
            collection_config: Collection配置
        """
        self.config = config
        self.collection_config = collection_config
        self.vector_db: MilvusVectorDB = None
        self.embedding_generator: EmbeddingGenerator = None
        self.llm_service: LLMService = None
        self.index: VectorStoreIndex = None
        self.retriever: VectorIndexRetriever = None
        self._initialized = False

        logger.info(f"🔧 RAG查询引擎初始化 - Collection: {collection_config.name}")

    async def initialize(self):
        """初始化查询引擎"""
        if self._initialized:
            return

        logger.info(
            f"🚀 正在初始化RAG查询引擎 - Collection: {self.collection_config.name}"
        )

        try:
            # 初始化向量数据库
            self.vector_db = MilvusVectorDB(self.config, self.collection_config)
            self.vector_db.initialize()

            # 初始化嵌入生成器
            self.embedding_generator = EmbeddingGenerator(self.config)
            await self.embedding_generator.initialize()

            # # 初始化LLM服务,使用Autogen的assitant,暂时注释调该部分
            self.llm_service = LLMService(self.config)
            self.llm_service.initialize()
            #
            # 创建向量索引
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=self.vector_db.vector_store,
                embed_model=self.embedding_generator.embedding_model,
            )

            # 创建检索器
            self.retriever = VectorIndexRetriever(
                index=self.index, similarity_top_k=self.collection_config.top_k
            )

            self._initialized = True
            logger.success(
                f"✅ RAG查询引擎初始化完成 - Collection: {self.collection_config.name}"
            )

        except Exception as e:
            logger.error(
                f"❌ RAG查询引擎初始化失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    async def query(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        **kwargs,
    ) -> QueryResult:
        """
        执行RAG查询

        Args:
            query_text: 查询文本
            filters: 原始过滤条件（Milvus表达式格式）
            metadata_filters: 元数据过滤条件（简化格式）
            top_k: 检索数量
            **kwargs: 其他参数

        Returns:
            QueryResult: 查询结果
        """
        if not self._initialized:
            await self.initialize()

        filter_info = ""
        if filters or metadata_filters:
            filter_info = f", 过滤条件: {filters or metadata_filters}"

        logger.info(
            f"🔍 执行RAG查询 - Collection: {self.collection_config.name}, 查询: {query_text}{filter_info}"
        )
        start_time = time.time()

        try:
            # 手动实现RAG流程
            # 1. 检索相关文档（支持过滤）
            retrieved_nodes = await self.retrieve_only(
                query_text,
                top_k=top_k,
                filters=filters,
                metadata_filters=metadata_filters,
            )

            # 2. 生成回答
            if retrieved_nodes:
                answer = await self.generate_answer(query_text, retrieved_nodes)
            else:
                answer = "抱歉，没有找到相关信息来回答您的问题。"

            # 计算响应时间
            response_time = time.time() - start_time

            # 构建查询结果
            result = QueryResult(
                query=query_text,
                answer=answer,
                retrieved_nodes=retrieved_nodes,
                response_time=response_time,
                collection_name=self.collection_config.name,
                business_type=self.collection_config.business_type,
                metadata={
                    "num_retrieved": len(retrieved_nodes),
                    "top_k": top_k or self.collection_config.top_k,
                    "similarity_threshold": self.collection_config.similarity_threshold,
                    "chunk_size": self.collection_config.chunk_size,
                    "filters": filters,
                    "metadata_filters": metadata_filters,
                },
            )

            logger.success(
                f"✅ RAG查询完成 - Collection: {self.collection_config.name}, 耗时: {response_time:.3f}s"
            )
            return result

        except Exception as e:
            logger.error(
                f"❌ RAG查询失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    async def retrieve_only(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> List[NodeWithScore]:
        """
        仅执行检索，不生成回答

        Args:
            query_text: 查询文本
            top_k: 检索数量
            filters: 原始过滤条件（Milvus表达式格式）
            metadata_filters: 元数据过滤条件（简化格式）

        Returns:
            List[NodeWithScore]: 检索到的节点
        """
        if not self._initialized:
            await self.initialize()

        top_k = top_k or self.collection_config.top_k

        filter_info = ""
        if filters or metadata_filters:
            filter_info = f", 过滤条件: {filters or metadata_filters}"

        logger.info(
            f"🔍 执行检索 - Collection: {self.collection_config.name}, top_k={top_k}{filter_info}"
        )

        try:
            # 生成查询嵌入向量
            query_embedding = await self.embedding_generator.embed_query(query_text)

            # 执行向量检索
            if metadata_filters:
                # 使用元数据过滤
                result = self.vector_db.query_with_metadata_filter(
                    query_embedding, metadata_filters, top_k
                )
            else:
                # 使用原始过滤或无过滤
                result = self.vector_db.query(query_embedding, top_k, filters)

            # 转换为NodeWithScore格式
            retrieved_nodes = result.nodes

            # 过滤低相似度结果
            filtered_nodes = []
            for node in retrieved_nodes:
                # 检查是否有 score 属性
                if hasattr(node, "score"):
                    score = node.score
                else:
                    score = getattr(node, "similarity", 0.0)

                if score >= self.collection_config.similarity_threshold:
                    filtered_nodes.append(node)
                else:
                    logger.debug(f"过滤低相似度节点: {score:.3f}")

            logger.success(
                f"✅ 检索完成 - Collection: {self.collection_config.name}: {len(filtered_nodes)}/{len(retrieved_nodes)} 个节点"
            )
            return filtered_nodes

        except Exception as e:
            logger.error(
                f"❌ 检索失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    async def generate_answer(
        self, query_text: str, context_nodes: List[NodeWithScore]
    ) -> str:
        """
        基于检索到的节点生成回答

        Args:
            query_text: 查询文本
            context_nodes: 上下文节点

        Returns:
            str: 生成的回答
        """
        if not self._initialized:
            await self.initialize()

        logger.info(
            f"💭 基于 {len(context_nodes)} 个节点生成回答 - Collection: {self.collection_config.name}"
        )

        try:
            # 构建上下文
            context_parts = []
            for i, node in enumerate(context_nodes):
                context_parts.append(f"[文档{i+1}] {node.node.text}")

            context = "\n\n".join(context_parts)

            # 根据业务类型生成回答
            if self.collection_config.business_type != "general":
                answer = self.llm_service.generate_business_rag_response(
                    query_text, context, self.collection_config.business_type
                )
            else:
                answer = self.llm_service.generate_rag_response(query_text, context)

            logger.success(
                f"✅ 回答生成完成 - Collection: {self.collection_config.name}"
            )
            return answer

        except Exception as e:
            logger.error(
                f"❌ 回答生成失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        获取查询引擎统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            "initialized": self._initialized,
            "collection_name": self.collection_config.name,
            "business_type": self.collection_config.business_type,
            "config": {
                "top_k": self.collection_config.top_k,
                "similarity_threshold": self.collection_config.similarity_threshold,
                "chunk_size": self.collection_config.chunk_size,
                "chunk_overlap": self.collection_config.chunk_overlap,
            },
        }

        if self.vector_db:
            stats["vector_db"] = self.vector_db.get_stats()

        if self.llm_service:
            stats["llm"] = self.llm_service.get_model_info()

        if self.embedding_generator:
            stats["embedding"] = self.embedding_generator.get_model_info()

        return stats

    async def close(self):
        """清理资源"""
        if self.embedding_generator:
            await self.embedding_generator.close()

        if self.llm_service:
            self.llm_service.close()

        if self.vector_db:
            self.vector_db.close()

        self._initialized = False
        logger.info(
            f"🔄 RAG查询引擎资源清理完成 - Collection: {self.collection_config.name}"
        )


async def create_query_engine(
    config: RAGConfig, collection_config: CollectionConfig
) -> RAGQueryEngine:
    """
    创建并初始化查询引擎

    Args:
        config: RAG配置
        collection_config: Collection配置

    Returns:
        RAGQueryEngine: 初始化后的查询引擎
    """
    engine = RAGQueryEngine(config, collection_config)
    await engine.initialize()
    return engine


if __name__ == "__main__":
    # 测试代码
    import asyncio

    from backend.conf.rag_config import get_rag_config

    async def test_query_engine():
        config = get_rag_config()
        collection_config = config.get_collection_config("general")

        if collection_config:
            engine = await create_query_engine(config, collection_config)

            # 获取统计信息
            stats = engine.get_stats()
            print(f"查询引擎统计: {stats}")

            await engine.close()
        else:
            print("未找到general collection配置")

    asyncio.run(test_query_engine())
