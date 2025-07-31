"""
Milvus向量数据库模块
基于LlamaIndex的Milvus向量存储实现，支持多collection架构
"""

from typing import Any, Dict, List, Optional, Union

from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.vector_stores import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from llama_index.vector_stores.milvus import MilvusVectorStore
from loguru import logger

from backend.conf.rag_config import CollectionConfig, RAGConfig


class MilvusVectorDB:
    """Milvus向量数据库管理器，支持多collection"""

    def __init__(self, config: RAGConfig, collection_config: CollectionConfig):
        """
        初始化Milvus向量数据库

        Args:
            config: RAG总配置
            collection_config: 单个collection配置
        """
        self.config = config.milvus
        self.collection_config = collection_config
        self.vector_store: MilvusVectorStore = None
        self._initialized = False

        logger.info(f"🗄️ Milvus向量数据库初始化 - Collection: {collection_config.name}")

    def initialize(self):
        """初始化向量存储"""
        if self._initialized:
            return

        logger.info(
            f"🚀 正在连接Milvus向量数据库 - Collection: {self.collection_config.name}"
        )

        try:
            # 创建Milvus向量存储，参考官方文档的最佳实践
            self.vector_store = MilvusVectorStore(
                uri=f"http://{self.config.host}:{self.config.port}",  # 使用完整URI
                collection_name=self.collection_config.name,
                dim=self.collection_config.dimension,
                overwrite=False,  # 不覆盖现有集合
                # 根据官方文档配置参数
                enable_sparse=False,  # 禁用稀疏向量
                enable_dense=True,  # 启用密集向量
                similarity_metric="IP",  # 内积相似度
                consistency_level="Session",  # 会话级一致性
                hybrid_ranker="RRFRanker",
                hybrid_ranker_params={},
                # 批处理大小优化
                batch_size=1000,
            )

            self._initialized = True
            logger.success(
                f"✅ Milvus向量数据库连接成功 - Collection: {self.collection_config.name}"
            )
            logger.info(f"🔗 连接URI: http://{self.config.host}:{self.config.port}")

        except Exception as e:
            logger.error(
                f"❌ Milvus向量数据库连接失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def create_collection(self, overwrite: bool = False):
        """
        创建集合

        Args:
            overwrite: 是否覆盖现有集合
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"📦 创建集合: {self.collection_config.name}")

        try:
            if overwrite:
                # 重新创建向量存储以覆盖集合，使用与初始化相同的参数
                self.vector_store = MilvusVectorStore(
                    uri=f"http://{self.config.host}:{self.config.port}",
                    collection_name=self.collection_config.name,
                    dim=self.collection_config.dimension,
                    overwrite=True,
                    enable_sparse=False,
                    enable_dense=True,
                    similarity_metric="IP",
                    consistency_level="Session",
                    hybrid_ranker="RRFRanker",
                    hybrid_ranker_params={},
                    batch_size=1000,
                )

            logger.success(f"✅ 集合创建完成: {self.collection_config.name}")

        except Exception as e:
            logger.error(f"❌ 集合创建失败 - {self.collection_config.name}: {e}")
            raise

    def collection_exists(self) -> bool:
        """
        检查集合是否存在

        Returns:
            bool: 集合是否存在
        """
        try:
            # 直接使用Milvus客户端检查，不要初始化vector_store
            # 因为初始化可能会自动创建Collection
            from pymilvus import connections, utility

            # 建立临时连接
            conn_alias = f"temp_{self.collection_config.name}"
            connections.connect(
                alias=conn_alias, host=self.config.host, port=self.config.port
            )

            # 检查集合是否存在
            exists = utility.has_collection(
                self.collection_config.name, using=conn_alias
            )

            # 断开临时连接
            connections.disconnect(conn_alias)

            return exists

        except Exception as e:
            logger.error(f"❌ 检查集合存在性失败 - {self.collection_config.name}: {e}")
            return False

    def add_nodes(self, nodes: List[BaseNode]) -> List[str]:
        """
        添加节点到向量数据库

        Args:
            nodes: 节点列表

        Returns:
            List[str]: 节点ID列表
        """
        if not self._initialized:
            self.initialize()

        if not nodes:
            logger.warning("⚠️ 节点列表为空，跳过添加")
            return []

        logger.info(
            f"📝 添加 {len(nodes)} 个节点到向量数据库 - Collection: {self.collection_config.name}"
        )

        try:
            # 使用向量存储添加节点
            node_ids = self.vector_store.add(nodes)

            logger.success(
                f"✅ 节点添加完成: {len(node_ids)} 个 - Collection: {self.collection_config.name}"
            )
            return node_ids

        except Exception as e:
            logger.error(
                f"❌ 节点添加失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def query(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> VectorStoreQueryResult:
        """
        查询相似向量

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            filters: 过滤条件，支持Milvus表达式格式

        Returns:
            VectorStoreQueryResult: 查询结果
        """
        if not self._initialized:
            self.initialize()

        top_k = top_k or self.collection_config.top_k

        filter_info = ""
        if filters:
            filter_info = f", 过滤条件: {filters}"

        logger.info(
            f"🔍 向量查询 - Collection: {self.collection_config.name}, top_k: {top_k}{filter_info}"
        )

        try:
            # 创建查询对象，参考官方文档的最佳实践
            query_obj = VectorStoreQuery(
                query_embedding=query_embedding,
                similarity_top_k=top_k,
                filters=filters,  # 直接传递过滤器，让LlamaIndex处理
            )

            # 执行查询
            result = self.vector_store.query(query_obj)

            logger.success(
                f"✅ 查询完成: 返回 {len(result.nodes)} 个结果 - Collection: {self.collection_config.name}"
            )
            return result

        except Exception as e:
            logger.error(
                f"❌ 向量查询失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def delete_nodes(
        self,
        node_ids: Optional[List[str]] = None,
        filters: Optional[MetadataFilters] = None,
        **delete_kwargs: Any,
    ) -> None:
        """
        删除节点
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            node_ids: 要删除的节点ID列表
            filters: 元数据过滤器
            **delete_kwargs: 其他删除参数

        Raises:
            ValueError: 当node_ids和filters都未提供时
        """
        if not self._initialized:
            self.initialize()

        if node_ids is None and filters is None:
            raise ValueError("必须提供node_ids或filters中的至少一个参数")

        logger.info(
            f"🗑️ 删除节点 - Collection: {self.collection_config.name}, "
            f"node_ids: {len(node_ids) if node_ids else 0}, "
            f"filters: {filters is not None}"
        )

        try:
            # 使用LlamaIndex的delete_nodes方法
            self.vector_store.delete_nodes(
                node_ids=node_ids, filters=filters, **delete_kwargs
            )

            logger.success(
                f"✅ 节点删除完成 - Collection: {self.collection_config.name}"
            )

        except Exception as e:
            logger.error(
                f"❌ 节点删除失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def delete_by_doc_id(
        self, ref_doc_id: Union[str, List[str]], **delete_kwargs: Any
    ) -> None:
        """
        根据文档ID删除节点
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            ref_doc_id: 文档ID或文档ID列表
            **delete_kwargs: 其他删除参数
        """
        if not self._initialized:
            self.initialize()

        doc_ids = ref_doc_id if isinstance(ref_doc_id, list) else [ref_doc_id]

        logger.info(
            f"🗑️ 根据文档ID删除节点 - Collection: {self.collection_config.name}, "
            f"doc_ids: {len(doc_ids)}"
        )

        try:
            # 使用LlamaIndex的delete方法
            for doc_id in doc_ids:
                self.vector_store.delete(ref_doc_id=doc_id, **delete_kwargs)

            logger.success(
                f"✅ 文档删除完成 - Collection: {self.collection_config.name}, "
                f"删除了 {len(doc_ids)} 个文档"
            )

        except Exception as e:
            logger.error(
                f"❌ 文档删除失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def get_nodes(
        self,
        node_ids: Optional[List[str]] = None,
        filters: Optional[MetadataFilters] = None,
    ) -> List[BaseNode]:
        """
        获取节点
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            node_ids: 节点ID列表
            filters: 元数据过滤器

        Returns:
            List[BaseNode]: 节点列表

        Raises:
            ValueError: 当node_ids和filters都未提供时
        """
        if not self._initialized:
            self.initialize()

        if node_ids is None and filters is None:
            raise ValueError("必须提供node_ids或filters中的至少一个参数")

        logger.info(
            f"📖 获取节点 - Collection: {self.collection_config.name}, "
            f"node_ids: {len(node_ids) if node_ids else 0}, "
            f"filters: {filters is not None}"
        )

        try:
            # 使用LlamaIndex的get_nodes方法
            nodes = self.vector_store.get_nodes(node_ids=node_ids, filters=filters)

            logger.success(
                f"✅ 节点获取完成 - Collection: {self.collection_config.name}, "
                f"获取了 {len(nodes)} 个节点"
            )
            return nodes

        except Exception as e:
            logger.error(
                f"❌ 节点获取失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def clear_collection(self) -> None:
        """
        清空集合中的所有数据
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/
        """
        if not self._initialized:
            self.initialize()

        logger.warning(f"🗑️ 清空集合数据: {self.collection_config.name}")

        try:
            # 使用LlamaIndex的clear方法
            self.vector_store.clear()

            logger.success(f"✅ 集合数据清空完成: {self.collection_config.name}")

        except Exception as e:
            logger.error(f"❌ 集合数据清空失败 - {self.collection_config.name}: {e}")
            raise

    async def async_add_nodes(self, nodes: List[BaseNode]) -> List[str]:
        """
        异步添加节点到向量数据库
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            nodes: 节点列表

        Returns:
            List[str]: 节点ID列表
        """
        if not self._initialized:
            self.initialize()

        if not nodes:
            logger.warning("⚠️ 节点列表为空，跳过添加")
            return []

        logger.info(
            f"📝 异步添加 {len(nodes)} 个节点到向量数据库 - Collection: {self.collection_config.name}"
        )

        try:
            # 使用向量存储的异步添加方法
            node_ids = await self.vector_store.async_add(nodes)

            logger.success(
                f"✅ 异步节点添加完成: {len(node_ids)} 个 - Collection: {self.collection_config.name}"
            )
            return node_ids

        except Exception as e:
            logger.error(
                f"❌ 异步节点添加失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    async def async_delete_nodes(
        self,
        node_ids: Optional[List[str]] = None,
        filters: Optional[MetadataFilters] = None,
        **delete_kwargs: Any,
    ) -> None:
        """
        异步删除节点
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            node_ids: 要删除的节点ID列表
            filters: 元数据过滤器
            **delete_kwargs: 其他删除参数
        """
        if not self._initialized:
            self.initialize()

        if node_ids is None and filters is None:
            raise ValueError("必须提供node_ids或filters中的至少一个参数")

        logger.info(
            f"🗑️ 异步删除节点 - Collection: {self.collection_config.name}, "
            f"node_ids: {len(node_ids) if node_ids else 0}, "
            f"filters: {filters is not None}"
        )

        try:
            # 使用LlamaIndex的异步删除方法
            await self.vector_store.adelete_nodes(
                node_ids=node_ids, filters=filters, **delete_kwargs
            )

            logger.success(
                f"✅ 异步节点删除完成 - Collection: {self.collection_config.name}"
            )

        except Exception as e:
            logger.error(
                f"❌ 异步节点删除失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def upsert_nodes(self, nodes: List[BaseNode]) -> List[str]:
        """
        更新或插入节点（Upsert操作）
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            nodes: 节点列表

        Returns:
            List[str]: 节点ID列表
        """
        if not self._initialized:
            self.initialize()

        if not nodes:
            logger.warning("⚠️ 节点列表为空，跳过更新")
            return []

        logger.info(
            f"🔄 更新或插入 {len(nodes)} 个节点到向量数据库 - Collection: {self.collection_config.name}"
        )

        try:
            # 创建支持upsert的向量存储
            upsert_vector_store = MilvusVectorStore(
                uri=f"http://{self.config.host}:{self.config.port}",
                collection_name=self.collection_config.name,
                dim=self.collection_config.dimension,
                upsert_mode=True,  # 启用upsert模式
                enable_sparse=False,
                enable_dense=True,
                similarity_metric="IP",
                consistency_level="Session",
                hybrid_ranker="RRFRanker",
                hybrid_ranker_params={},
                batch_size=1000,
            )

            # 使用upsert模式添加节点
            node_ids = upsert_vector_store.add(nodes)

            logger.success(
                f"✅ 节点更新完成: {len(node_ids)} 个 - Collection: {self.collection_config.name}"
            )
            return node_ids

        except Exception as e:
            logger.error(
                f"❌ 节点更新失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def query_with_metadata_filter(
        self,
        query_embedding: List[float],
        metadata_filters: Dict[str, Any],
        top_k: Optional[int] = None,
        operator: str = "and",
    ) -> VectorStoreQueryResult:
        """
        使用元数据过滤条件查询相似向量
        参考官方文档: https://docs.llamaindex.ai/en/stable/examples/vector_stores/MilvusOperatorFunctionDemo/

        Args:
            query_embedding: 查询向量
            metadata_filters: 元数据过滤条件，如 {"category": "technology", "source": "doc1"}
            top_k: 返回结果数量
            operator: 多个条件之间的逻辑操作符 ("and" 或 "or")

        Returns:
            VectorStoreQueryResult: 查询结果
        """
        from llama_index.core.vector_stores import (
            FilterCondition,
            FilterOperator,
            MetadataFilter,
            MetadataFilters,
        )

        if not metadata_filters:
            return self.query(query_embedding, top_k)

        # 构建LlamaIndex MetadataFilters，参考官方文档实现
        filters_list = []
        for key, value in metadata_filters.items():
            if isinstance(value, list):
                # 对于列表值，创建IN操作符过滤器
                filters_list.append(
                    MetadataFilter(key=key, value=value, operator=FilterOperator.IN)
                )
            else:
                # 对于单个值，使用精确匹配
                filters_list.append(
                    MetadataFilter(key=key, value=value, operator=FilterOperator.EQ)
                )

        # 创建MetadataFilters对象，根据operator决定逻辑关系
        condition = (
            FilterCondition.OR if operator.lower() == "or" else FilterCondition.AND
        )
        metadata_filter_obj = MetadataFilters(filters=filters_list, condition=condition)

        logger.info(f"🔍 构建元数据过滤器: {metadata_filters}, 逻辑操作: {operator}")

        # 创建查询对象
        query_obj = VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=top_k or self.collection_config.top_k,
            filters=metadata_filter_obj,
        )

        # 执行查询
        result = self.vector_store.query(query_obj)

        logger.success(
            f"✅ 元数据过滤查询完成: 返回 {len(result.nodes)} 个结果 - Collection: {self.collection_config.name}"
        )
        return result

    def query_with_string_expr(
        self,
        query_embedding: List[float],
        string_expr: str,
        top_k: Optional[int] = None,
    ) -> VectorStoreQueryResult:
        """
        使用Milvus原生字符串表达式查询相似向量
        参考官方文档: https://docs.llamaindex.ai/en/stable/examples/vector_stores/MilvusOperatorFunctionDemo/

        Args:
            query_embedding: 查询向量
            string_expr: Milvus原生过滤表达式，如 "genre like '%Fiction'" 或 "year > 2000"
            top_k: 返回结果数量

        Returns:
            VectorStoreQueryResult: 查询结果

        Examples:
            # 基本比较
            result = query_with_string_expr(embedding, "year > 2000")

            # 字符串匹配
            result = query_with_string_expr(embedding, "genre like '%Fiction'")

            # 复合条件
            result = query_with_string_expr(embedding, "year > 1979 and year <= 2010")
        """
        if not self._initialized:
            self.initialize()

        top_k = top_k or self.collection_config.top_k

        logger.info(
            f"🔍 Milvus原生表达式查询 - Collection: {self.collection_config.name}, "
            f"top_k: {top_k}, 表达式: {string_expr}"
        )

        try:
            # 使用vector_store_kwargs传递string_expr
            from llama_index.core import VectorStoreIndex
            from llama_index.core.retrievers import VectorIndexRetriever

            # 创建临时索引用于查询
            index = VectorStoreIndex.from_vector_store(self.vector_store)
            retriever = index.as_retriever(
                similarity_top_k=top_k, vector_store_kwargs={"string_expr": string_expr}
            )

            # 执行查询 - 需要一个查询文本，这里使用空查询
            # 注意：这种方法需要embedding，我们直接使用vector_store的query方法
            query_obj = VectorStoreQuery(
                query_embedding=query_embedding,
                similarity_top_k=top_k,
            )

            # 直接调用vector_store的query方法并传递string_expr
            result = self.vector_store.query(query_obj, string_expr=string_expr)

            logger.success(
                f"✅ Milvus原生表达式查询完成: 返回 {len(result.nodes)} 个结果 - Collection: {self.collection_config.name}"
            )
            return result

        except Exception as e:
            logger.error(
                f"❌ Milvus原生表达式查询失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[MetadataFilters] = None,
        hybrid_ranker: str = "RRFRanker",
        hybrid_ranker_params: Optional[Dict[str, Any]] = None,
    ) -> VectorStoreQueryResult:
        """
        混合搜索（密集向量 + 稀疏向量）
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            query_embedding: 查询向量
            query_text: 查询文本（用于稀疏向量）
            top_k: 返回结果数量
            filters: 元数据过滤器
            hybrid_ranker: 混合排序器类型 ("RRFRanker" 或 "WeightedRanker")
            hybrid_ranker_params: 混合排序器参数

        Returns:
            VectorStoreQueryResult: 查询结果
        """
        if not self._initialized:
            self.initialize()

        top_k = top_k or self.collection_config.top_k
        hybrid_ranker_params = hybrid_ranker_params or {}

        logger.info(
            f"🔍 混合搜索 - Collection: {self.collection_config.name}, "
            f"top_k: {top_k}, ranker: {hybrid_ranker}"
        )

        try:
            # 创建支持混合搜索的向量存储
            hybrid_vector_store = MilvusVectorStore(
                uri=f"http://{self.config.host}:{self.config.port}",
                collection_name=self.collection_config.name,
                dim=self.collection_config.dimension,
                enable_sparse=True,  # 启用稀疏向量
                enable_dense=True,  # 启用密集向量
                similarity_metric="IP",
                consistency_level="Session",
                hybrid_ranker=hybrid_ranker,
                hybrid_ranker_params=hybrid_ranker_params,
                batch_size=1000,
            )

            # 创建混合查询对象
            # 注意：混合搜索需要稀疏向量支持，可能需要额外配置
            query_obj = VectorStoreQuery(
                query_embedding=query_embedding,
                query_str=query_text,  # 用于稀疏向量
                similarity_top_k=top_k,
                filters=filters,
                # mode="HYBRID"  # 混合模式 - 暂时注释，等待稀疏向量支持
            )

            # 执行混合查询
            result = hybrid_vector_store.query(query_obj)

            logger.success(
                f"✅ 混合搜索完成: 返回 {len(result.nodes)} 个结果 - Collection: {self.collection_config.name}"
            )
            return result

        except Exception as e:
            logger.error(
                f"❌ 混合搜索失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def mmr_search(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        filters: Optional[MetadataFilters] = None,
        mmr_threshold: float = 0.5,
    ) -> VectorStoreQueryResult:
        """
        最大边际相关性搜索（MMR）
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            filters: 元数据过滤器
            mmr_threshold: MMR阈值

        Returns:
            VectorStoreQueryResult: 查询结果
        """
        if not self._initialized:
            self.initialize()

        top_k = top_k or self.collection_config.top_k

        logger.info(
            f"🔍 MMR搜索 - Collection: {self.collection_config.name}, "
            f"top_k: {top_k}, threshold: {mmr_threshold}"
        )

        try:
            # 创建MMR查询对象
            # 注意：MMR功能可能需要特定版本的LlamaIndex
            query_obj = VectorStoreQuery(
                query_embedding=query_embedding,
                similarity_top_k=top_k,
                filters=filters,
                # mode="MMR",  # MMR模式 - 暂时注释，等待LlamaIndex支持
                mmr_threshold=mmr_threshold,
            )

            # 执行MMR查询
            result = self.vector_store.query(query_obj)

            logger.success(
                f"✅ MMR搜索完成: 返回 {len(result.nodes)} 个结果 - Collection: {self.collection_config.name}"
            )
            return result

        except Exception as e:
            logger.error(
                f"❌ MMR搜索失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def batch_add_nodes(
        self,
        nodes: List[BaseNode],
        batch_size: Optional[int] = None,
        force_flush: bool = False,
    ) -> List[str]:
        """
        批量添加节点，支持大规模数据插入
        参考官方文档: https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/milvus/

        Args:
            nodes: 节点列表
            batch_size: 批处理大小
            force_flush: 是否强制刷新

        Returns:
            List[str]: 节点ID列表
        """
        if not self._initialized:
            self.initialize()

        if not nodes:
            logger.warning("⚠️ 节点列表为空，跳过添加")
            return []

        batch_size = batch_size or 1000
        total_nodes = len(nodes)
        all_node_ids = []

        logger.info(
            f"📝 批量添加 {total_nodes} 个节点到向量数据库 - Collection: {self.collection_config.name}, "
            f"批大小: {batch_size}"
        )

        try:
            # 分批处理
            for i in range(0, total_nodes, batch_size):
                batch = nodes[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_nodes + batch_size - 1) // batch_size

                logger.info(
                    f"📦 处理批次 {batch_num}/{total_batches}: {len(batch)} 个节点"
                )

                # 添加当前批次
                batch_ids = self.vector_store.add(batch, force_flush=force_flush)
                all_node_ids.extend(batch_ids)

                logger.info(f"✅ 批次 {batch_num} 完成: {len(batch_ids)} 个节点")

            logger.success(
                f"✅ 批量添加完成: 总共 {len(all_node_ids)} 个节点 - Collection: {self.collection_config.name}"
            )
            return all_node_ids

        except Exception as e:
            logger.error(
                f"❌ 批量添加失败 - Collection: {self.collection_config.name}: {e}"
            )
            raise

    def delete_collection(self):
        """删除集合"""
        if not self._initialized:
            self.initialize()

        logger.warning(f"🗑️ 删除集合: {self.collection_config.name}")

        try:
            # 使用clear方法删除集合数据，这是官方推荐的方式
            if self.vector_store:
                self.vector_store.clear()
                logger.success(f"✅ 集合删除完成: {self.collection_config.name}")
            else:
                # 如果vector_store未初始化，直接使用pymilvus删除
                from pymilvus import connections, utility

                conn_alias = f"delete_{self.collection_config.name}"
                connections.connect(
                    alias=conn_alias, host=self.config.host, port=self.config.port
                )

                if utility.has_collection(
                    self.collection_config.name, using=conn_alias
                ):
                    utility.drop_collection(
                        self.collection_config.name, using=conn_alias
                    )
                    logger.success(f"✅ 集合删除完成: {self.collection_config.name}")
                else:
                    logger.warning(f"⚠️ 集合不存在: {self.collection_config.name}")

                connections.disconnect(conn_alias)

            logger.success(f"✅ 集合删除完成: {self.collection_config.name}")

        except Exception as e:
            logger.error(f"❌ 集合删除失败 - {self.collection_config.name}: {e}")
            raise

    def verify_connection(self) -> bool:
        """
        验证与远程Milvus的连接状态

        Returns:
            bool: 连接是否正常
        """
        if not self._initialized:
            return False

        try:
            # 尝试获取collection信息来验证连接
            if hasattr(self.vector_store, "_milvus_client"):
                # 检查是否真的连接到远程Milvus
                client = self.vector_store._milvus_client
                if hasattr(client, "server_address"):
                    server_address = client.server_address
                    is_remote = not (
                        server_address.startswith("file://")
                        or server_address.endswith(".db")
                    )
                    logger.info(f"🔗 Milvus连接地址: {server_address}")
                    logger.info(
                        f"📡 远程连接状态: {'是' if is_remote else '否（本地文件）'}"
                    )
                    return is_remote
            return True
        except Exception as e:
            logger.error(f"❌ 连接验证失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self._initialized:
            self.initialize()

        try:
            # 验证连接状态
            is_remote_connected = self.verify_connection()

            # 基本统计信息
            stats = {
                "collection_name": self.collection_config.name,
                "description": self.collection_config.description,
                "business_type": self.collection_config.business_type,
                "dimension": self.collection_config.dimension,
                "host": self.config.host,
                "port": self.config.port,
                "uri": f"http://{self.config.host}:{self.config.port}",
                "initialized": self._initialized,
                "remote_connected": is_remote_connected,
                "chunk_size": self.collection_config.chunk_size,
                "chunk_overlap": self.collection_config.chunk_overlap,
                "top_k": self.collection_config.top_k,
                "similarity_threshold": self.collection_config.similarity_threshold,
            }

            return stats

        except Exception as e:
            logger.error(
                f"❌ 获取统计信息失败 - Collection: {self.collection_config.name}: {e}"
            )
            return {"error": str(e)}

    def close(self):
        """关闭连接"""
        if self.vector_store:
            # LlamaIndex的MilvusVectorStore通常不需要显式关闭
            pass

        self._initialized = False
        logger.info(
            f"🔄 Milvus向量数据库连接关闭 - Collection: {self.collection_config.name}"
        )


def create_vector_db(
    config: RAGConfig, collection_config: CollectionConfig
) -> MilvusVectorDB:
    """
    创建并初始化向量数据库

    Args:
        config: RAG配置
        collection_config: Collection配置

    Returns:
        MilvusVectorDB: 初始化后的向量数据库
    """
    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()
    return vector_db


async def vilidate_vector_store():
    """测试向量数据库功能"""
    import asyncio

    from backend.conf.rag_config import get_rag_config
    from backend.rag_core.embedding_generator import EmbeddingGenerator

    config = get_rag_config()
    collection_config = config.get_collection_config("general")
    # 创建collection
    vector_db = MilvusVectorDB(config, collection_config)
    vector_db.initialize()
    vector_db.create_collection()

    if not collection_config:
        print("❌ 未找到general collection配置")
        return

    vector_db = None
    embedding_generator = None

    try:
        # 初始化组件
        vector_db = create_vector_db(config, collection_config)
        embedding_generator = EmbeddingGenerator(config)
        await embedding_generator.initialize()

        print(f"🔧 使用嵌入模型: {config.ollama.embedding_model}")
        print(f"📏 向量维度: {collection_config.dimension}")

        # 创建测试节点
        test_texts = [
            "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
            "机器学习是人工智能的子集，它使计算机能够在没有明确编程的情况下学习和改进。",
            "深度学习是机器学习的一个分支，使用神经网络来模拟人脑的学习过程。",
        ]

        test_nodes = []
        for i, text in enumerate(test_texts):
            node = TextNode(
                text=text,
                metadata={"source": "test", "topic": f"AI_{i}", "doc_id": f"test_{i}"},
            )
            test_nodes.append(node)

        # 生成嵌入向量
        print("🔄 正在生成嵌入向量...")
        embeddings = await embedding_generator.embed_texts(test_texts)

        # 为节点设置嵌入向量
        for node, embedding in zip(test_nodes, embeddings):
            node.embedding = embedding

        print(f"✅ 嵌入向量生成完成，维度: {len(embeddings[0])}")

        # 创建集合
        print("📦 创建集合...")
        vector_db.create_collection(overwrite=True)  # 使用overwrite确保测试环境干净

        # 添加节点
        print("📝 添加节点到向量数据库...")
        node_ids = vector_db.add_nodes(test_nodes)
        print(f"✅ 添加节点成功: {len(node_ids)} 个节点")

        # 测试查询
        print("🔍 测试查询功能...")
        query_text = "什么是人工智能？"
        query_embedding = await embedding_generator.embed_query(query_text)

        result = vector_db.query(query_embedding, top_k=2)
        print(f"📊 查询结果: 找到 {len(result.nodes)} 个相关文档")

        for i, node_with_score in enumerate(result.nodes):
            # 检查是否有 score 属性
            if hasattr(node_with_score, "score"):
                score = node_with_score.score
                node = node_with_score.node
            else:
                # 如果没有 score 属性，可能直接是 node
                score = getattr(node_with_score, "similarity", 0.0)
                node = node_with_score

            print(f"  {i+1}. 相似度: {score:.4f}")
            print(f"     内容: {node.text[:100]}...")

        # 获取统计信息
        stats = vector_db.get_stats()
        print(f"📈 统计信息: {stats}")

        print("🎉 测试完成！")

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        print(f"❌ 测试失败: {e}")
        raise

    finally:
        # 清理资源
        if embedding_generator:
            await embedding_generator.close()
        if vector_db:
            vector_db.close()


if __name__ == "__main__":
    # 运行异步测试
    import asyncio

    asyncio.run(vilidate_vector_store())
