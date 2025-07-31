"""
Collection管理器
支持多collection架构，为不同业务提供专业知识库管理
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from backend.conf.rag_config import CollectionConfig, RAGConfig, get_rag_config
from backend.rag_core.vector_store import MilvusVectorDB


class CollectionManager:
    """Collection管理器，支持多collection架构"""

    def __init__(self, config: Optional[RAGConfig] = None):
        """
        初始化Collection管理器

        Args:
            config: RAG配置
        """
        self.config = config or get_rag_config()
        self.vector_dbs: Dict[str, MilvusVectorDB] = {}
        self._initialized = False

        logger.info("🗂️ Collection管理器初始化")

    async def initialize(self):
        """初始化所有collections"""
        if self._initialized:
            return

        logger.info("🚀 正在初始化Collection管理器...")

        try:
            # 初始化所有配置的collections
            for (
                collection_name,
                collection_config,
            ) in self.config.milvus.collections.items():
                await self._initialize_collection(collection_name, collection_config)

            self._initialized = True
            logger.success(
                f"✅ Collection管理器初始化完成，共 {len(self.vector_dbs)} 个collections"
            )

        except Exception as e:
            logger.error(f"❌ Collection管理器初始化失败: {e}")
            raise

    async def _initialize_collection(
        self, collection_name: str, collection_config: CollectionConfig
    ):
        """初始化单个collection"""
        logger.info(f"📦 初始化collection: {collection_name}")

        try:
            # 创建向量数据库实例
            vector_db = MilvusVectorDB(self.config, collection_config)
            vector_db.initialize()

            # 存储到管理器中
            self.vector_dbs[collection_name] = vector_db

            logger.success(f"✅ Collection初始化完成: {collection_name}")

        except Exception as e:
            logger.error(f"❌ Collection初始化失败 {collection_name}: {e}")
            raise

    def get_collection(self, collection_name: str) -> Optional[MilvusVectorDB]:
        """
        获取指定的collection

        Args:
            collection_name: collection名称

        Returns:
            MilvusVectorDB: 向量数据库实例
        """
        # 在按需初始化模式下，不需要检查_initialized状态
        # 直接返回已初始化的collection
        return self.vector_dbs.get(collection_name)

    def get_business_collections(self, business_type: str) -> List[MilvusVectorDB]:
        """
        获取指定业务类型的所有collections

        Args:
            business_type: 业务类型

        Returns:
            List[MilvusVectorDB]: 向量数据库实例列表
        """
        if not self._initialized:
            logger.warning("Collection管理器未初始化")
            return []

        business_collections = []
        for (
            collection_name,
            collection_config,
        ) in self.config.milvus.collections.items():
            if collection_config.business_type == business_type:
                vector_db = self.vector_dbs.get(collection_name)
                if vector_db:
                    business_collections.append(vector_db)

        return business_collections

    async def create_collection(self, collection_name: str, overwrite: bool = False):
        """
        创建collection

        Args:
            collection_name: collection名称
            overwrite: 是否覆盖现有collection
        """
        # 不要触发全量初始化，只确保指定的Collection存在
        if collection_name not in self.vector_dbs:
            # 如果Collection不存在，说明还没有初始化，这是一个错误
            logger.error(
                f"❌ Collection未初始化: {collection_name}，请先调用_ensure_collection_initialized"
            )
            return

        vector_db = self.get_collection(collection_name)
        if vector_db:
            vector_db.create_collection(overwrite=overwrite)
            logger.success(f"✅ Collection创建完成: {collection_name}")
        else:
            logger.error(f"❌ Collection不存在: {collection_name}")

    async def delete_collection(self, collection_name: str):
        """
        删除collection

        Args:
            collection_name: collection名称
        """
        # 不要触发全量初始化，只操作已存在的Collection
        vector_db = self.get_collection(collection_name)
        if vector_db:
            vector_db.delete_collection()
            logger.success(f"✅ Collection删除完成: {collection_name}")
        else:
            logger.error(f"❌ Collection不存在: {collection_name}")

    def list_collections(self) -> List[str]:
        """
        列出所有已初始化的collections

        Returns:
            List[str]: collection名称列表
        """
        return list(self.vector_dbs.keys())

    def list_milvus_collections(self) -> List[str]:
        """
        直接查询Milvus中存在的所有collections

        Returns:
            List[str]: Milvus中实际存在的collection名称列表
        """
        try:
            from pymilvus import connections, utility

            # 建立临时连接
            conn_alias = "temp_list_collections"
            connections.connect(
                alias=conn_alias,
                host=self.config.milvus.host,
                port=self.config.milvus.port,
            )

            # 获取所有collection列表
            collections = utility.list_collections(using=conn_alias)

            # 断开临时连接
            connections.disconnect(conn_alias)

            logger.info(f"📋 Milvus中的Collections: {collections}")
            return collections

        except Exception as e:
            logger.error(f"❌ 获取Milvus Collections失败: {e}")
            return []

    def get_milvus_collection_info(self, collection_name: str) -> Optional[Dict]:
        """
        获取Milvus中collection的详细信息

        Args:
            collection_name: collection名称

        Returns:
            Dict: collection详细信息
        """
        try:
            from pymilvus import Collection, connections, utility

            # 建立临时连接
            conn_alias = f"temp_info_{collection_name}"
            connections.connect(
                alias=conn_alias,
                host=self.config.milvus.host,
                port=self.config.milvus.port,
            )

            # 检查collection是否存在
            if not utility.has_collection(collection_name, using=conn_alias):
                connections.disconnect(conn_alias)
                return None

            # 获取collection对象
            collection = Collection(collection_name, using=conn_alias)

            # 获取详细信息
            info = {
                "name": collection_name,
                "description": collection.description,
                "num_entities": collection.num_entities,
                "schema": {
                    "fields": [
                        {
                            "name": field.name,
                            "type": str(field.dtype),
                            "is_primary": field.is_primary,
                            "auto_id": field.auto_id,
                            "description": field.description,
                        }
                        for field in collection.schema.fields
                    ]
                },
                "indexes": [],
            }

            # 获取索引信息
            try:
                indexes = collection.indexes
                for index in indexes:
                    info["indexes"].append(
                        {
                            "field_name": index.field_name,
                            "index_name": index.index_name,
                            "params": index.params,
                        }
                    )
            except Exception as idx_e:
                logger.warning(f"获取索引信息失败: {idx_e}")

            # 断开临时连接
            connections.disconnect(conn_alias)

            logger.info(f"📊 Collection信息获取成功: {collection_name}")
            return info

        except Exception as e:
            logger.error(f"❌ 获取Collection信息失败 {collection_name}: {e}")
            return None

    def get_collection_info(self, collection_name: str) -> Optional[Dict]:
        """
        获取collection信息

        Args:
            collection_name: collection名称

        Returns:
            Dict: collection信息
        """
        if collection_name not in self.config.milvus.collections:
            return None

        collection_config = self.config.milvus.collections[collection_name]
        vector_db = self.get_collection(collection_name)

        info = {
            "name": collection_config.name,
            "description": collection_config.description,
            "business_type": collection_config.business_type,
            "dimension": collection_config.dimension,
            "chunk_size": collection_config.chunk_size,
            "chunk_overlap": collection_config.chunk_overlap,
            "top_k": collection_config.top_k,
            "similarity_threshold": collection_config.similarity_threshold,
            "initialized": vector_db is not None,
        }

        if vector_db:
            info.update(vector_db.get_stats())

        return info

    async def close(self):
        """关闭所有collections"""
        for vector_db in self.vector_dbs.values():
            vector_db.close()

        self.vector_dbs.clear()
        self._initialized = False
        logger.info("🔄 Collection管理器资源清理完成")


async def create_collection_manager(
    config: Optional[RAGConfig] = None,
) -> CollectionManager:
    """
    创建并初始化Collection管理器

    Args:
        config: RAG配置

    Returns:
        CollectionManager: 初始化后的Collection管理器
    """
    manager = CollectionManager(config)
    # await manager.initialize()
    return manager


if __name__ == "__main__":
    # 测试代码
    import asyncio

    async def test_collection_manager():
        manager = await create_collection_manager()
        # 实例化一个collection
        await manager._initialize_collection(
            "general", manager.config.milvus.collections["general"]
        )

        # 列出所有collections
        collections = manager.list_collections()
        print(f"可用collections: {collections}")

        # 获取collection信息
        for collection_name in collections:
            info = manager.get_collection_info(collection_name)
            print(f"Collection {collection_name}: {info}")

        # 获取业务相关collections
        testcase_collections = manager.get_business_collections("testcase")
        print(f"测试用例相关collections: {len(testcase_collections)}")

        await manager.close()

    asyncio.run(test_collection_manager())
