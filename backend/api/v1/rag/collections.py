"""
RAG Collection管理API
提供Collection的CRUD操作
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from backend.models.rag import RAGCollection
from backend.services.rag.rag_service import RAGService, get_rag_service

rag_collections_router = APIRouter()


class CollectionCreateRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = ""
    business_type: str = "general"
    chunk_size: int = 512
    chunk_overlap: int = 50
    dimension: int = 768
    top_k: int = 5
    similarity_threshold: float = 0.7


class CollectionUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    business_type: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    dimension: Optional[int] = None
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None


@rag_collections_router.get("/", summary="获取Collection列表")
async def get_collections():
    """获取所有Collection列表"""
    try:
        logger.info("📋 获取Collection列表")

        collections = await RAGCollection.all().order_by("created_at")

        collection_list = []
        for collection in collections:
            # 统计文档数量
            from backend.models.rag_file import RAGFileRecord

            doc_count = await RAGFileRecord.filter(
                collection_name=collection.name
            ).count()

            collection_list.append(
                {
                    "id": collection.id,
                    "name": collection.name,
                    "display_name": collection.display_name,
                    "description": collection.description,
                    "business_type": collection.business_type,
                    "chunk_size": collection.chunk_size,
                    "chunk_overlap": collection.chunk_overlap,
                    "dimension": collection.dimension,
                    "top_k": collection.top_k,
                    "similarity_threshold": collection.similarity_threshold,
                    "is_active": collection.is_active,
                    "document_count": doc_count,
                    "created_at": (
                        collection.created_at.isoformat()
                        if collection.created_at
                        else None
                    ),
                    "updated_at": (
                        collection.updated_at.isoformat()
                        if collection.updated_at
                        else None
                    ),
                }
            )

        logger.success(
            f"✅ 获取Collection列表成功: {len(collection_list)} 个Collection"
        )

        return {
            "code": 200,
            "msg": "获取Collection列表成功",
            "data": {"collections": collection_list},
            "total": len(collection_list),
        }

    except Exception as e:
        logger.error(f"❌ 获取Collection列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Collection列表失败: {str(e)}")


@rag_collections_router.post("/", summary="创建Collection")
async def create_collection(request: CollectionCreateRequest):
    """创建新的Collection"""
    try:
        logger.info(f"📝 创建Collection: {request.name}")

        # 检查名称是否已存在
        existing = await RAGCollection.filter(name=request.name).first()
        if existing:
            logger.warning(f"⚠️ Collection名称已存在: {request.name}")
            raise HTTPException(
                status_code=400, detail=f"Collection名称 '{request.name}' 已存在"
            )

        # 创建Collection
        collection = await RAGCollection.create(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            business_type=request.business_type,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            dimension=request.dimension,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )

        logger.success(
            f"✅ Collection创建成功: {collection.name} (ID: {collection.id})"
        )

        return {
            "code": 200,
            "msg": "Collection创建成功",
            "data": {
                "collection": {
                    "id": collection.id,
                    "name": collection.name,
                    "display_name": collection.display_name,
                    "description": collection.description,
                    "business_type": collection.business_type,
                    "chunk_size": collection.chunk_size,
                    "chunk_overlap": collection.chunk_overlap,
                    "dimension": collection.dimension,
                    "top_k": collection.top_k,
                    "similarity_threshold": collection.similarity_threshold,
                    "created_at": (
                        collection.created_at.isoformat()
                        if collection.created_at
                        else None
                    ),
                }
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 创建Collection失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建Collection失败: {str(e)}")


@rag_collections_router.get("/{collection_id}", summary="获取Collection详情")
async def get_collection(collection_id: int):
    """获取指定Collection的详情"""
    try:
        logger.info(f"🔍 获取Collection详情: ID={collection_id}")

        collection = await RAGCollection.filter(id=collection_id).first()
        if not collection:
            logger.warning(f"⚠️ Collection不存在: ID={collection_id}")
            raise HTTPException(status_code=404, detail="Collection不存在")

        # 统计文档数量
        from backend.models.rag_file import RAGFileRecord

        doc_count = await RAGFileRecord.filter(collection_name=collection.name).count()

        collection_data = {
            "id": collection.id,
            "name": collection.name,
            "display_name": collection.display_name,
            "description": collection.description,
            "business_type": collection.business_type,
            "chunk_size": collection.chunk_size,
            "chunk_overlap": collection.chunk_overlap,
            "dimension": collection.dimension,
            "top_k": collection.top_k,
            "similarity_threshold": collection.similarity_threshold,
            "is_active": collection.is_active,
            "document_count": doc_count,
            "created_at": (
                collection.created_at.isoformat() if collection.created_at else None
            ),
            "updated_at": (
                collection.updated_at.isoformat() if collection.updated_at else None
            ),
        }

        logger.success(f"✅ 获取Collection详情成功: {collection.name}")

        return {
            "code": 200,
            "msg": "获取Collection详情成功",
            "data": {"collection": collection_data},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取Collection详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Collection详情失败: {str(e)}")


@rag_collections_router.put("/{collection_id}", summary="更新Collection")
async def update_collection(collection_id: int, request: CollectionUpdateRequest):
    """更新Collection信息"""
    try:
        logger.info(f"✏️ 更新Collection: ID={collection_id}")

        collection = await RAGCollection.filter(id=collection_id).first()
        if not collection:
            logger.warning(f"⚠️ Collection不存在: ID={collection_id}")
            raise HTTPException(status_code=404, detail="Collection不存在")

        # 更新字段
        update_data = {}
        if request.display_name is not None:
            update_data["display_name"] = request.display_name
        if request.description is not None:
            update_data["description"] = request.description
        if request.business_type is not None:
            update_data["business_type"] = request.business_type
        if request.chunk_size is not None:
            update_data["chunk_size"] = request.chunk_size
        if request.chunk_overlap is not None:
            update_data["chunk_overlap"] = request.chunk_overlap
        if request.dimension is not None:
            update_data["dimension"] = request.dimension
        if request.top_k is not None:
            update_data["top_k"] = request.top_k
        if request.similarity_threshold is not None:
            update_data["similarity_threshold"] = request.similarity_threshold

        if update_data:
            await RAGCollection.filter(id=collection_id).update(**update_data)
            # 重新获取更新后的数据
            collection = await RAGCollection.filter(id=collection_id).first()

        logger.success(f"✅ Collection更新成功: {collection.name}")

        return {
            "code": 200,
            "msg": "Collection更新成功",
            "data": {
                "collection": {
                    "id": collection.id,
                    "name": collection.name,
                    "display_name": collection.display_name,
                    "description": collection.description,
                    "business_type": collection.business_type,
                    "chunk_size": collection.chunk_size,
                    "chunk_overlap": collection.chunk_overlap,
                    "dimension": collection.dimension,
                    "top_k": collection.top_k,
                    "similarity_threshold": collection.similarity_threshold,
                    "updated_at": (
                        collection.updated_at.isoformat()
                        if collection.updated_at
                        else None
                    ),
                }
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新Collection失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新Collection失败: {str(e)}")


@rag_collections_router.delete("/{collection_id}", summary="删除Collection")
async def delete_collection(collection_id: int):
    """删除Collection"""
    try:
        logger.info(f"🗑️ 删除Collection: ID={collection_id}")

        collection = await RAGCollection.filter(id=collection_id).first()
        if not collection:
            logger.warning(f"⚠️ Collection不存在: ID={collection_id}")
            raise HTTPException(status_code=404, detail="Collection不存在")

        # 检查是否有关联文档
        from backend.models.rag_file import RAGFileRecord

        doc_count = await RAGFileRecord.filter(collection_name=collection.name).count()

        if doc_count > 0:
            logger.warning(
                f"⚠️ Collection包含文档，无法删除: {collection.name} ({doc_count} 个文档)"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Collection '{collection.name}' 包含 {doc_count} 个文档，请先删除所有文档后再删除Collection",
            )

        # 删除Collection
        collection_name = collection.name
        await collection.delete()

        logger.success(f"✅ Collection删除成功: {collection_name}")

        return {
            "code": 200,
            "msg": "Collection删除成功",
            "data": {"deleted_collection": collection_name},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除Collection失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除Collection失败: {str(e)}")


@rag_collections_router.get("/{collection_id}/stats", summary="获取Collection统计信息")
async def get_collection_stats(collection_id: int):
    """获取Collection的统计信息"""
    try:
        logger.info(f"📊 获取Collection统计: ID={collection_id}")

        collection = await RAGCollection.filter(id=collection_id).first()
        if not collection:
            logger.warning(f"⚠️ Collection不存在: ID={collection_id}")
            raise HTTPException(status_code=404, detail="Collection不存在")

        # 统计信息
        from backend.models.rag_file import RAGFileRecord

        total_docs = await RAGFileRecord.filter(collection_name=collection.name).count()
        completed_docs = await RAGFileRecord.filter(
            collection_name=collection.name, status="completed"
        ).count()

        # 计算总文件大小
        records = await RAGFileRecord.filter(collection_name=collection.name).all()
        total_size = sum(record.file_size for record in records)

        stats = {
            "collection_name": collection.name,
            "display_name": collection.display_name,
            "total_documents": total_docs,
            "completed_documents": completed_docs,
            "processing_documents": total_docs - completed_docs,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "success_rate": (
                round(completed_docs / total_docs * 100, 2) if total_docs > 0 else 0
            ),
            "business_type": collection.business_type,
            "chunk_size": collection.chunk_size,
            "chunk_overlap": collection.chunk_overlap,
            "dimension": collection.dimension,
            "top_k": collection.top_k,
            "similarity_threshold": collection.similarity_threshold,
        }

        logger.success(f"✅ Collection统计获取成功: {collection.name}")

        return {"code": 200, "msg": "获取Collection统计成功", "data": {"stats": stats}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取Collection统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Collection统计失败: {str(e)}")
