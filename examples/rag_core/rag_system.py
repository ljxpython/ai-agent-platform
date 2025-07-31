"""
RAG系统主入口
支持多collection架构，为不同业务提供专业知识库
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from backend.conf.rag_config import RAGConfig, get_rag_config
from backend.rag_core.collection_manager import CollectionManager
from backend.rag_core.data_loader import DocumentLoader
from backend.rag_core.query_engine import QueryResult, RAGQueryEngine


class RAGSystem:
    """RAG系统主类，支持多collection架构"""

    def __init__(self, config: Optional[RAGConfig] = None):
        """初始化RAG系统"""
        self.config = config or get_rag_config()
        self.collection_manager: CollectionManager = None
        self.query_engines: Dict[str, RAGQueryEngine] = {}
        self._initialized = False

        logger.info("🚀 RAG系统初始化")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.cleanup()

    async def initialize(self):
        """初始化RAG系统基础组件（不初始化所有Collection）"""
        if self._initialized:
            return

        logger.info("🔧 正在初始化RAG系统基础组件...")

        try:
            # 仅初始化Collection管理器，不自动初始化所有collections
            self.collection_manager = CollectionManager(self.config)
            # 注意：这里不调用 await self.collection_manager.initialize()
            # 因为那会初始化所有配置的collections

            self._initialized = True
            logger.success("✅ RAG系统基础组件初始化完成（按需初始化模式）")

        except Exception as e:
            logger.error(f"❌ RAG系统初始化失败: {e}")
            raise

    async def _ensure_collection_initialized(self, collection_name: str):
        """确保指定的Collection已初始化"""
        if collection_name not in self.query_engines:
            collection_config = self.config.get_collection_config(collection_name)
            if not collection_config:
                raise ValueError(f"Collection配置不存在: {collection_name}")

            logger.info(f"🔧 按需初始化Collection: {collection_name}")

            # 只初始化指定的Collection，不初始化所有Collection
            # 如果Collection管理器还没有这个Collection，就初始化它
            if collection_name not in self.collection_manager.vector_dbs:
                await self.collection_manager._initialize_collection(
                    collection_name, collection_config
                )

            # 初始化查询引擎
            query_engine = RAGQueryEngine(self.config, collection_config)
            await query_engine.initialize()
            self.query_engines[collection_name] = query_engine

            logger.success(f"✅ Collection初始化完成: {collection_name}")

    async def _check_collection_exists(self, collection_name: str) -> bool:
        """检查Collection在Milvus中是否存在（不初始化Collection）"""
        try:
            collection_config = self.config.get_collection_config(collection_name)
            if not collection_config:
                return False

            # 直接使用pymilvus检查，不通过LlamaIndex
            from pymilvus import connections, utility

            # 建立临时连接
            conn_alias = f"temp_check_{collection_name}"
            connections.connect(
                alias=conn_alias,
                host=self.config.milvus.host,
                port=self.config.milvus.port,
            )

            # 检查集合是否存在
            exists = utility.has_collection(collection_config.name, using=conn_alias)

            # 断开临时连接
            connections.disconnect(conn_alias)

            logger.info(
                f"🔍 Collection存在性检查 - {collection_name}: {'存在' if exists else '不存在'}"
            )
            return exists

        except Exception as e:
            logger.error(f"❌ 检查Collection存在性失败 {collection_name}: {e}")
            return False

    async def setup_collection(self, collection_name: str, overwrite: bool = False):
        """设置向量集合"""
        if not self._initialized:
            await self.initialize()

        # 确保Collection已初始化
        await self._ensure_collection_initialized(collection_name)

        logger.info(f"📦 设置向量集合: {collection_name}")

        # 直接调用向量数据库的create_collection方法
        vector_db = self.collection_manager.get_collection(collection_name)
        if vector_db:
            vector_db.create_collection(overwrite=overwrite)
            logger.success(f"✅ 向量集合设置完成: {collection_name}")
        else:
            logger.error(f"❌ Collection不存在: {collection_name}")

    async def setup_all_collections(self, overwrite: bool = False):
        """设置所有向量集合"""
        if not self._initialized:
            await self.initialize()

        logger.info("📦 设置所有向量集合...")
        for collection_name in self.config.milvus.collections.keys():
            await self.setup_collection(collection_name, overwrite=overwrite)
        logger.success("✅ 所有向量集合设置完成")

    async def add_text(
        self,
        text: str,
        collection_name: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """添加文本到指定知识库"""
        if not self._initialized:
            await self.initialize()

        # 检查Collection是否存在
        collection_exists = await self._check_collection_exists(collection_name)
        if not collection_exists:
            raise ValueError(
                f"Collection '{collection_name}' 不存在于Milvus中。"
                f"请先调用 setup_collection('{collection_name}') 创建Collection。"
            )

        # 确保Collection已初始化（包括查询引擎）
        await self._ensure_collection_initialized(collection_name)

        collection_config = self.config.get_collection_config(collection_name)
        if not collection_config:
            raise ValueError(f"Collection配置不存在: {collection_name}")

        logger.info(f"📝 添加文本到 {collection_name} - 长度: {len(text)}")

        try:
            # 1. 加载并分割文档
            loader = DocumentLoader(collection_config)
            nodes = loader.load_and_split_text(text, metadata)

            if not nodes:
                logger.warning("文本分割为空")
                return 0

            # 2. 生成嵌入向量
            query_engine = self.query_engines[collection_name]
            texts = [node.text for node in nodes]
            embeddings = await query_engine.embedding_generator.embed_texts(texts)

            # 3. 设置节点的嵌入向量
            for node, embedding in zip(nodes, embeddings):
                node.embedding = embedding

            # 4. 添加到向量数据库
            vector_db = self.collection_manager.get_collection(collection_name)
            node_ids = vector_db.add_nodes(nodes)

            logger.success(
                f"✅ 文本添加完成 - Collection: {collection_name}, 节点数: {len(node_ids)}"
            )
            return len(node_ids)

        except Exception as e:
            logger.error(f"❌ 文本添加失败 - Collection: {collection_name}: {e}")
            raise

    async def add_file(
        self, file_path: Union[str, Path], collection_name: str = "general"
    ) -> int:
        """从文件添加文档到指定知识库"""
        if not self._initialized:
            await self.initialize()

        # 检查Collection是否存在
        collection_exists = await self._check_collection_exists(collection_name)
        if not collection_exists:
            raise ValueError(
                f"Collection '{collection_name}' 不存在于Milvus中。"
                f"请先调用 setup_collection('{collection_name}') 创建Collection。"
            )

        # 确保Collection已初始化（包括查询引擎）
        await self._ensure_collection_initialized(collection_name)

        collection_config = self.config.get_collection_config(collection_name)
        if not collection_config:
            raise ValueError(f"Collection不存在: {collection_name}")

        logger.info(f"📄 添加文件到 {collection_name}: {file_path}")

        try:
            # 1. 加载并分割文档
            loader = DocumentLoader(collection_config)
            nodes = loader.load_and_split(file_path)

            if not nodes:
                logger.warning("文件为空，跳过处理")
                return 0

            # 2. 生成嵌入向量
            query_engine = self.query_engines[collection_name]
            texts = [node.text for node in nodes]
            embeddings = await query_engine.embedding_generator.embed_texts(texts)

            # 3. 设置节点的嵌入向量
            for node, embedding in zip(nodes, embeddings):
                node.embedding = embedding

            # 4. 添加到向量数据库
            vector_db = self.collection_manager.get_collection(collection_name)
            node_ids = vector_db.add_nodes(nodes)

            logger.success(
                f"✅ 文件添加完成 - Collection: {collection_name}, 节点数: {len(node_ids)}"
            )
            return len(node_ids)

        except Exception as e:
            logger.error(f"❌ 文件添加失败 - Collection: {collection_name}: {e}")
            raise

    async def query(
        self, question: str, collection_name: str = "general", **kwargs
    ) -> QueryResult:
        """执行RAG查询"""
        if not self._initialized:
            await self.initialize()

        # 检查Collection是否存在
        collection_exists = await self._check_collection_exists(collection_name)
        if not collection_exists:
            raise ValueError(
                f"Collection '{collection_name}' 不存在于Milvus中。"
                f"请先调用 setup_collection('{collection_name}') 创建Collection，"
                f"或添加一些文档到该Collection。"
            )

        # 确保Collection已初始化（连接到现有的Collection）
        await self._ensure_collection_initialized(collection_name)

        query_engine = self.query_engines[collection_name]
        return await query_engine.query(question, **kwargs)

    async def query_with_filters(
        self,
        question: str,
        collection_name: str = "general",
        metadata_filters: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        **kwargs,
    ) -> QueryResult:
        """
        执行带过滤条件的RAG查询

        Args:
            question: 查询问题
            collection_name: Collection名称
            metadata_filters: 元数据过滤条件，如 {"category": "technology", "source": "doc1"}
            filters: 原始Milvus过滤表达式
            top_k: 检索数量
            **kwargs: 其他参数

        Returns:
            QueryResult: 查询结果
        """
        if not self._initialized:
            await self.initialize()

        # 检查Collection是否存在
        collection_exists = await self._check_collection_exists(collection_name)
        if not collection_exists:
            raise ValueError(
                f"Collection '{collection_name}' 不存在于Milvus中。"
                f"请先调用 setup_collection('{collection_name}') 创建Collection，"
                f"或添加一些文档到该Collection。"
            )

        # 确保Collection已初始化（包括查询引擎）
        await self._ensure_collection_initialized(collection_name)

        query_engine = self.query_engines[collection_name]
        return await query_engine.query(
            question,
            filters=filters,
            metadata_filters=metadata_filters,
            top_k=top_k,
            **kwargs,
        )

    async def query_multiple_collections(
        self, question: str, collection_names: List[str], **kwargs
    ) -> List[QueryResult]:
        """在多个collection中查询"""
        if not self._initialized:
            await self.initialize()

        results = []
        for collection_name in collection_names:
            if collection_name in self.query_engines:
                try:
                    result = await self.query(question, collection_name, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ Collection {collection_name} 查询失败: {e}")

        return results

    async def query_business_type(
        self, question: str, business_type: str, **kwargs
    ) -> List[QueryResult]:
        """根据业务类型查询相关collections"""
        if not self._initialized:
            await self.initialize()

        # 获取业务相关的collection名称
        business_collections = []
        for (
            collection_name,
            collection_config,
        ) in self.config.milvus.collections.items():
            if collection_config.business_type == business_type:
                business_collections.append(collection_name)

        if not business_collections:
            logger.warning(f"未找到业务类型 {business_type} 的collections")
            return []

        return await self.query_multiple_collections(
            question, business_collections, **kwargs
        )

    async def chat(self, message: str, collection_name: str = "general") -> str:
        """简单的聊天接口"""
        result = await self.query(message, collection_name)
        return result.answer

    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        if not self._initialized:
            return {"initialized": False}

        stats = {
            "initialized": True,
            "collections": {},
            "total_collections": len(self.query_engines),
        }

        # 获取每个collection的统计信息
        for collection_name, query_engine in self.query_engines.items():
            stats["collections"][collection_name] = query_engine.get_stats()

        return stats

    def list_collections(self) -> List[str]:
        """列出所有collections"""
        return list(self.config.milvus.collections.keys())

    def get_collection_info(self, collection_name: str) -> Optional[Dict]:
        """获取collection信息"""
        if self.collection_manager:
            return self.collection_manager.get_collection_info(collection_name)
        return None

    async def clear_collection(self, collection_name: str):
        """清空指定collection的数据"""
        if not self._initialized:
            await self.initialize()

        logger.warning(f"🗑️ 清空collection数据: {collection_name}")
        await self.collection_manager.delete_collection(collection_name)
        await self.setup_collection(collection_name)
        logger.success(f"✅ Collection数据清空完成: {collection_name}")

    async def clear_all_data(self):
        """清空所有数据"""
        if not self._initialized:
            await self.initialize()

        logger.warning("🗑️ 清空所有数据...")
        for collection_name in self.config.milvus.collections.keys():
            await self.clear_collection(collection_name)
        logger.success("✅ 所有数据清空完成")

    async def cleanup(self):
        """清理资源"""
        for query_engine in self.query_engines.values():
            await query_engine.close()

        if self.collection_manager:
            await self.collection_manager.close()

        self.query_engines.clear()
        self._initialized = False
        logger.info("🔄 RAG系统资源清理完成")


# 便捷函数
async def create_rag_system(config: Optional[RAGConfig] = None) -> RAGSystem:
    """创建并初始化RAG系统"""
    rag = RAGSystem(config)
    await rag.initialize()
    return rag


if __name__ == "__main__":
    logger.info("*******************🔄 RAG系统测试 🔄*******************")

    # 简单测试
    async def rag_test():
        async with RAGSystem() as rag:
            # 创建一个新的Collection
            await rag.setup_collection(collection_name="my_docs", overwrite=True)

            # # 设置所有collections
            # # await rag.setup_all_collections(overwrite=True)
            # await rag.setup_collection(collection_name="general")
            # await rag.setup_collection(collection_name="testcase")
            #
            # # 添加测试文本到不同collections
            # await rag.add_text("人工智能是计算机科学的一个分支。", "general")
            # await rag.add_text("测试用例设计需要考虑边界条件。", "testcase")
            #
            # # 测试查询
            # result = await rag.query_with_filters("什么是人工智能？", "general",filters={"topic": "AI"})
            # print(f"通用知识库查询结果: {result.answer}")
            #
            #
            # general_answer = await rag.chat("什么是人工智能？", "general")
            # print(f"通用知识库回答: {general_answer}")
            #
            # testcase_answer = await rag.chat("如何设计测试用例？", "testcase")
            # print(f"测试用例知识库回答: {testcase_answer}")
            #
            # # 获取统计信息
            # stats = rag.get_stats()
            # print(f"系统统计: {stats}")

    asyncio.run(rag_test())
