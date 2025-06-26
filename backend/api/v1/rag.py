"""
RAG知识库API路由
提供RAG知识库的REST API接口
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel

from backend.api_core.exceptions import (
    BusinessError,
    CollectionNotFoundError,
    DocumentNotFoundError,
    RAGError,
)
from backend.controllers.rag_controller import (
    rag_collection_controller,
    rag_document_controller,
    rag_query_controller,
)
from backend.schemas.base import Fail, Success
from backend.schemas.rag import (
    BatchUploadResponse,
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    FileUploadResponse,
    QueryRequest,
    QueryResponse,
    SystemStats,
)
from backend.services.rag.rag_service import RAGService, get_rag_service


# 请求模型
class AddTextRequest(BaseModel):
    """添加文本请求"""

    text: str
    collection_name: str = "general"
    metadata: Optional[Dict[str, Any]] = None


class QueryRequest(BaseModel):
    """查询请求"""

    question: str
    collection_name: str = "general"


class MultiQueryRequest(BaseModel):
    """多Collection查询请求"""

    question: str
    collection_names: List[str]


class BusinessQueryRequest(BaseModel):
    """业务类型查询请求"""

    question: str
    business_type: str


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str
    collection_name: str = "general"


class CollectionCreateRequest(BaseModel):
    """创建Collection请求"""

    name: str
    description: str = ""
    business_type: str = "general"


class CollectionUpdateRequest(BaseModel):
    """更新Collection请求"""

    description: Optional[str] = None
    business_type: Optional[str] = None


class CollectionSetupRequest(BaseModel):
    """Collection设置请求"""

    collection_name: str
    overwrite: bool = False


class CollectionCreateRequest(BaseModel):
    """Collection创建请求"""

    name: str
    description: str
    business_type: str = "general"


class CollectionUpdateRequest(BaseModel):
    """Collection更新请求"""

    description: Optional[str] = None
    business_type: Optional[str] = None


# 创建路由器
rag_router = APIRouter()

from backend.api.v1.rag_collections import rag_collections_router

# 包含仪表板路由
from backend.api.v1.rag_dashboard import rag_dashboard_router
from backend.api.v1.rag_documents import rag_documents_router

rag_router.include_router(rag_dashboard_router, prefix="/dashboard", tags=["RAG仪表板"])
rag_router.include_router(
    rag_documents_router, prefix="/documents", tags=["RAG文档管理"]
)
rag_router.include_router(
    rag_collections_router, prefix="/collections-manage", tags=["RAG Collection管理"]
)


@rag_router.get("/processing/jobs", summary="获取处理任务列表")
async def get_processing_jobs():
    """获取文档处理任务列表"""
    try:
        from backend.models.rag_file import RAGFileRecord

        # 获取最近的处理任务（模拟处理队列）
        recent_records = await RAGFileRecord.all().order_by("-created_at").limit(10)

        jobs = []
        for record in recent_records:
            # 模拟处理状态
            status = "completed" if record.status == "completed" else "processing"
            progress = 100 if status == "completed" else 85

            jobs.append(
                {
                    "id": record.id,
                    "filename": record.filename,
                    "collection": record.collection_name,
                    "status": status,
                    "progress": progress,
                    "created_at": (
                        record.created_at.isoformat() if record.created_at else None
                    ),
                    "file_size": record.file_size,
                    "user_id": record.user_id,
                }
            )

        return {"code": 200, "msg": "获取处理任务成功", "data": {"jobs": jobs}}

    except Exception as e:
        logger.error(f"获取处理任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取处理任务失败: {str(e)}")


@rag_router.get("/collections/{collection_name}", summary="获取指定Collection信息")
async def get_collection_info(
    collection_name: str, rag_service: RAGService = Depends(get_rag_service)
):
    """获取指定Collection信息"""
    try:
        result = await rag_service.get_collection_info(collection_name)
        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Collection不存在: {collection_name}"
            )

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Collection信息失败: {str(e)}")


@rag_router.post("/collections/setup", summary="设置Collection")
async def setup_collection(
    request: CollectionSetupRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """设置Collection"""
    try:
        result = await rag_service.setup_collection(
            request.collection_name, request.overwrite
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Collection设置失败: {str(e)}")


@rag_router.post("/collections/setup-all", summary="设置所有Collections")
async def setup_all_collections(
    overwrite: bool = False, rag_service: RAGService = Depends(get_rag_service)
):
    """设置所有Collections"""
    try:
        result = await rag_service.setup_all_collections(overwrite)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"所有Collections设置失败: {str(e)}"
        )


@rag_router.post("/documents/add-text", summary="添加文本到知识库")
async def add_text(
    request: AddTextRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """添加文本到知识库"""
    try:
        result = await rag_service.add_text(
            request.text, request.collection_name, request.metadata
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文本添加失败: {str(e)}")


@rag_router.post("/documents/add-file", summary="添加文件到知识库")
async def add_file(
    file: UploadFile = File(...),
    collection_name: str = Form("general"),
    rag_service: RAGService = Depends(get_rag_service),
):
    """添加文件到知识库"""
    try:
        # 保存上传的文件
        upload_dir = Path("backend/data/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 添加文件到知识库
        result = await rag_service.add_file(file_path, collection_name)

        # 清理临时文件
        file_path.unlink()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件添加失败: {str(e)}")


@rag_router.post("/query", summary="RAG查询")
async def query(request: QueryRequest):
    """执行RAG查询"""
    return await rag_query_controller.query(request)


@rag_router.post("/query/multiple", summary="多Collection查询")
async def query_multiple(
    request: MultiQueryRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """在多个Collections中查询"""
    try:
        result = await rag_service.query_multiple_collections(
            request.question, request.collection_names
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"多Collection查询失败: {str(e)}")


@rag_router.post("/query/business", summary="业务类型查询")
async def query_business(
    request: BusinessQueryRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """根据业务类型查询"""
    try:
        result = await rag_service.query_business_type(
            request.question, request.business_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"业务类型查询失败: {str(e)}")


@rag_router.post("/chat", summary="RAG聊天")
async def chat(
    request: ChatRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """RAG聊天接口"""
    try:
        result = await rag_service.chat(request.message, request.collection_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG聊天失败: {str(e)}")


@rag_router.get("/collections", summary="获取所有Collections")
async def get_collections():
    """获取所有Collections信息"""
    return await rag_collection_controller.get_all_collections()


@rag_router.get("/stats", summary="获取系统统计信息")
async def get_stats():
    """获取系统统计信息"""
    return await rag_query_controller.get_system_stats()


@rag_router.delete("/collections/{collection_name}/clear", summary="清空Collection数据")
async def clear_collection(
    collection_name: str, rag_service: RAGService = Depends(get_rag_service)
):
    """清空Collection数据"""
    try:
        result = await rag_service.clear_collection(collection_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空Collection数据失败: {str(e)}")


@rag_router.post("/collections/create", summary="创建新Collection")
async def create_collection(request: CollectionCreateRequest):
    """创建新Collection"""
    collection_data = CollectionCreate(
        name=request.name,
        display_name=request.name.replace("_", " ").title(),
        description=request.description,
        business_type=request.business_type,
    )

    return await rag_collection_controller.create_collection(collection_data)


@rag_router.put("/collections/{collection_name}", summary="更新Collection")
async def update_collection(collection_name: str, request: CollectionUpdateRequest):
    """更新Collection"""
    update_data = CollectionUpdate(
        description=request.description, business_type=request.business_type
    )

    return await rag_collection_controller.update_collection(
        collection_name, update_data
    )


@rag_router.delete("/collections/{collection_name}", summary="删除Collection")
async def delete_collection(collection_name: str):
    """删除Collection"""
    return await rag_collection_controller.delete_collection(collection_name)


@rag_router.get(
    "/collections/{collection_name}/documents", summary="获取Collection中的文档"
)
async def get_collection_documents(
    collection_name: str,
    page: int = 1,
    page_size: int = 20,
    rag_service: RAGService = Depends(get_rag_service),
):
    """获取Collection中的文档列表"""
    try:
        # 这里需要实现文档列表功能
        # 暂时返回空列表
        return {
            "success": True,
            "documents": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@rag_router.delete(
    "/collections/{collection_name}/documents/{document_id}", summary="删除文档"
)
async def delete_document(
    collection_name: str,
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service),
):
    """删除指定文档"""
    try:
        # 这里需要实现文档删除功能
        return {"success": True, "message": f"文档 {document_id} 删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@rag_router.get("/documents", summary="获取所有文档")
async def get_all_documents(
    collection_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取所有文档列表"""
    return await rag_document_controller.get_all_documents(
        collection_name, page, page_size
    )


@rag_router.post("/documents/upload", summary="上传文件")
async def upload_documents(
    files: List[UploadFile] = File(...), collection_name: str = Form(...)
):
    """上传文件到指定Collection"""
    try:
        import uuid
        from pathlib import Path

        from backend.models.rag import RAGCollection, RAGDocument

        # 检查Collection是否存在
        collection = await RAGCollection.get_or_none(name=collection_name)
        if not collection:
            raise HTTPException(
                status_code=404, detail=f"Collection {collection_name} 不存在"
            )

        results = []
        upload_dir = Path("backend/data/uploads/rag")
        upload_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            try:
                # 生成唯一文件名
                file_id = str(uuid.uuid4())
                file_extension = Path(file.filename).suffix
                saved_filename = f"{file_id}{file_extension}"
                file_path = upload_dir / saved_filename

                # 保存文件
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)

                # 创建文档记录
                document = await RAGDocument.create(
                    collection=collection,
                    title=file.filename,
                    content="",  # 稍后处理
                    file_path=str(file_path),
                    file_type=file.content_type or "application/octet-stream",
                    file_size=len(content),
                    embedding_status="pending",
                )

                results.append(
                    {
                        "filename": file.filename,
                        "document_id": document.id,
                        "status": "uploaded",
                        "file_size": len(content),
                    }
                )

                logger.info(f"文件上传成功: {file.filename} -> {collection_name}")

            except Exception as e:
                logger.error(f"文件上传失败 {file.filename}: {e}")
                results.append(
                    {"filename": file.filename, "status": "failed", "error": str(e)}
                )

        return {
            "success": True,
            "message": f"处理了 {len(files)} 个文件",
            "results": results,
        }

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@rag_router.post("/documents/add-text", summary="添加文本文档")
async def add_text_document(
    collection_name: str = Form(...), title: str = Form(...), content: str = Form(...)
):
    """添加文本文档到指定Collection"""
    document_data = DocumentCreate(
        title=title,
        content=content,
        collection_name=collection_name,
        file_type="text/plain",
    )

    return await rag_document_controller.create_document(document_data)


@rag_router.delete("/documents/{document_id}", summary="删除文档")
async def delete_document(document_id: int):
    """删除指定文档"""
    return await rag_document_controller.delete_document(document_id)


@rag_router.delete("/clear-all", summary="清空所有数据")
async def clear_all_data(rag_service: RAGService = Depends(get_rag_service)):
    """清空所有数据"""
    try:
        result = await rag_service.clear_all_data()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空所有数据失败: {str(e)}")


# 健康检查
@rag_router.get("/health", summary="RAG服务健康检查")
async def health_check(rag_service: RAGService = Depends(get_rag_service)):
    """RAG服务健康检查"""
    try:
        collections = rag_service.list_collections()
        return {
            "success": True,
            "status": "healthy",
            "initialized": rag_service._initialized,
            "total_collections": len(collections),
            "collections": collections,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


__all__ = ["rag_router"]
