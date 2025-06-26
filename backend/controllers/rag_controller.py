"""
RAG知识库控制器（简化版）
处理RAG相关的业务逻辑和数据库交互
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.api_core.exceptions import (
    BusinessError,
    CollectionNotFoundError,
    DocumentNotFoundError,
)
from backend.api_core.response import rag_response
from backend.models.rag import RAGCollection, RAGDocument
from backend.schemas.base import Fail, Success
from backend.schemas.rag import (
    CollectionCreate,
    CollectionUpdate,
    DocumentCreate,
    DocumentUpdate,
    QueryRequest,
)

# 移除自定义的ControllerResponse，使用统一的响应系统


class RAGCollectionController:
    """RAG Collection控制器"""

    async def get_all_collections(self) -> Success:
        """获取所有Collections"""
        collections = await RAGCollection.all().order_by("created_at")
        result = []

        for collection in collections:
            # 获取文档数量
            doc_count = await RAGDocument.filter(collection=collection).count()

            result.append(
                {
                    "id": collection.id,
                    "name": collection.name,
                    "display_name": collection.display_name,
                    "description": collection.description,
                    "business_type": collection.business_type,
                    "dimension": collection.dimension,
                    "chunk_size": collection.chunk_size,
                    "chunk_overlap": collection.chunk_overlap,
                    "top_k": collection.top_k,
                    "similarity_threshold": collection.similarity_threshold,
                    "is_active": collection.is_active,
                    "document_count": doc_count,
                    "last_updated": collection.last_updated.isoformat(),
                    "created_at": collection.created_at.isoformat(),
                    "updated_at": collection.updated_at.isoformat(),
                    "metadata": collection.metadata,
                }
            )

        return rag_response.collection_success(result)

    async def create_collection(self, collection_data: CollectionCreate) -> Success:
        """创建新的Collection"""
        # 检查名称是否已存在
        existing = await RAGCollection.get_or_none(name=collection_data.name)
        if existing:
            raise BusinessError(
                f"Collection名称 '{collection_data.name}' 已存在", code=409
            )

        # 创建Collection
        collection = await RAGCollection.create(**collection_data.model_dump())
        logger.success(f"创建Collection成功: {collection.name}")

        collection_data = {
            "id": collection.id,
            "name": collection.name,
            "display_name": collection.display_name,
            "description": collection.description,
            "business_type": collection.business_type,
        }

        return rag_response.collection_created(collection_data)

    async def update_collection(
        self, name: str, update_data: CollectionUpdate
    ) -> Success:
        """更新Collection"""
        collection = await RAGCollection.get_or_none(name=name)
        if not collection:
            raise CollectionNotFoundError(f"Collection '{name}' 不存在")

        # 更新字段
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(collection, field):
                setattr(collection, field, value)

        await collection.save()
        logger.success(f"更新Collection成功: {collection.name}")

        return rag_response.collection_updated()

    async def delete_collection(self, name: str) -> Success:
        """删除Collection"""
        collection = await RAGCollection.get_or_none(name=name)
        if not collection:
            raise CollectionNotFoundError(f"Collection '{name}' 不存在")

        # 删除相关文档
        doc_count = await RAGDocument.filter(collection=collection).count()
        await RAGDocument.filter(collection=collection).delete()

        # 删除Collection
        await collection.delete()
        logger.success(f"删除Collection成功: {name}，同时删除了 {doc_count} 个文档")

        return rag_response.collection_deleted(doc_count)


class RAGDocumentController:
    """RAG Document控制器"""

    async def get_all_documents(
        self, collection_name: Optional[str] = None, page: int = 1, page_size: int = 20
    ) -> Success:
        """获取所有文档列表"""
        # 构建查询
        query = RAGDocument.all()
        if collection_name:
            collection = await RAGCollection.get_or_none(name=collection_name)
            if collection:
                query = query.filter(collection=collection)

        # 分页
        total = await query.count()
        documents = (
            await query.offset((page - 1) * page_size)
            .limit(page_size)
            .prefetch_related("collection")
        )

        # 格式化结果
        result = []
        for doc in documents:
            result.append(
                {
                    "id": doc.id,
                    "title": doc.title,
                    "content": (
                        doc.content[:200] + "..."
                        if len(doc.content) > 200
                        else doc.content
                    ),
                    "file_path": doc.file_path,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size or 0,
                    "collection_name": doc.collection.name,
                    "node_count": doc.node_count,
                    "embedding_status": doc.embedding_status,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                    "metadata": doc.metadata,
                }
            )

        return rag_response.documents_success(result, total, page, page_size)

    async def create_document(self, document_data: DocumentCreate) -> Success:
        """创建文档"""
        # 检查Collection是否存在
        collection = await RAGCollection.get_or_none(name=document_data.collection_name)
        if not collection:
            raise CollectionNotFoundError(
                f"Collection {document_data.collection_name} 不存在"
            )

        # 创建文档记录
        doc_dict = document_data.model_dump()
        doc_dict.pop("collection_name")  # 移除collection_name，使用collection对象
        doc_dict["collection"] = collection
        doc_dict["file_size"] = len(document_data.content.encode("utf-8"))
        doc_dict["embedding_status"] = "pending"

        document = await RAGDocument.create(**doc_dict)

        logger.info(
            f"文档创建成功: {document.title} -> {document_data.collection_name}"
        )

        return rag_response.document_created(document.id)

    async def delete_document(self, document_id: int) -> Success:
        """删除文档"""
        # 获取文档
        document = await RAGDocument.get_or_none(id=document_id)
        if not document:
            raise DocumentNotFoundError("文档不存在")

        # 删除文件（如果存在）
        if document.file_path:
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()

        # 删除数据库记录
        await document.delete()

        logger.info(f"文档删除成功: {document.title}")

        return rag_response.document_deleted()


class RAGQueryController:
    """RAG查询控制器"""

    async def query(self, query_request: QueryRequest) -> Success:
        """执行RAG查询"""
        # 这里应该调用实际的RAG服务
        # 暂时返回模拟数据
        result = {
            "answer": f"这是对问题 '{query_request.question}' 的回答",
            "sources": [],
            "collection_name": query_request.collection_name,
            "query_time": 0.5,
            "retrieved_count": 3,
        }

        return rag_response.query_success(result)

    async def get_system_stats(self) -> Success:
        """获取系统统计信息"""
        # 获取Collections统计
        total_collections = await RAGCollection.all().count()
        total_documents = await RAGDocument.all().count()

        # 模拟其他统计数据
        stats = {
            "total_collections": total_collections,
            "total_documents": total_documents,
            "total_vectors": total_documents * 10,  # 假设每个文档平均10个向量
            "storage_used": f"{total_documents * 2.5:.1f} MB",
            "query_count_today": 156,
            "avg_response_time": 245,
            "system_health": "healthy",
        }

        return rag_response.stats_success(stats)


# 创建全局实例
rag_collection_controller = RAGCollectionController()
rag_document_controller = RAGDocumentController()
rag_query_controller = RAGQueryController()
