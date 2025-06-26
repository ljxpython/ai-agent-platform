"""
RAG文档管理API
提供文档的CRUD操作、批量管理和统计功能
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from loguru import logger

from backend.models.rag_file import RAGFileRecord
from backend.schemas.rag import DocumentCreate, DocumentResponse, DocumentUpdate
from backend.services.rag.file_upload_service import rag_file_upload_service
from backend.services.rag.rag_service import RAGService, get_rag_service

rag_documents_router = APIRouter()


@rag_documents_router.get("/", summary="获取文档列表")
@rag_documents_router.get("", summary="获取文档列表")
async def get_documents(
    collection_name: Optional[str] = Query(None, description="Collection名称"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取文档列表，支持分页和搜索"""
    try:
        logger.info(
            f"获取文档列表 | Collection: {collection_name} | 页码: {page} | 每页: {page_size}"
        )

        # 构建查询条件
        query = RAGFileRecord.all()

        if collection_name:
            query = query.filter(collection_name=collection_name)

        if search:
            query = query.filter(filename__icontains=search)

        # 计算总数
        total = await query.count()

        # 分页查询
        offset = (page - 1) * page_size
        records = await query.order_by("-created_at").limit(page_size).offset(offset)

        # 转换为响应格式
        documents = []
        for record in records:
            documents.append(
                {
                    "id": record.id,
                    "title": record.filename,
                    "content": f"文件大小: {record.size_mb}MB",
                    "collection_name": record.collection_name,
                    "file_type": record.file_md5[:8] + "...",  # 显示MD5前8位作为标识
                    "created_at": (
                        record.created_at.isoformat() if record.created_at else None
                    ),
                    "updated_at": (
                        record.created_at.isoformat() if record.created_at else None
                    ),
                    "metadata": {
                        "file_size": record.file_size,
                        "size_mb": record.size_mb,
                        "md5_hash": record.file_md5,
                        "status": record.status,
                        "user_id": record.user_id,
                    },
                }
            )

        return {
            "code": 200,
            "msg": "获取文档列表成功",
            "data": {"documents": documents},
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@rag_documents_router.get(
    "/collections/{collection_name}/documents", summary="获取指定Collection的文档"
)
async def get_collection_documents(
    collection_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取指定Collection的文档列表"""
    try:
        result = await rag_file_upload_service.get_collection_files(collection_name)

        if not result.get("success", False):
            raise HTTPException(
                status_code=500, detail=result.get("message", "获取文档失败")
            )

        files = result.get("files", [])

        # 简单分页处理
        total = len(files)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_files = files[start:end]

        # 转换为文档格式
        documents = []
        for file_info in paginated_files:
            documents.append(
                {
                    "id": file_info["id"],
                    "title": file_info["filename"],
                    "content": f"文件大小: {file_info['size_mb']}MB",
                    "collection_name": collection_name,
                    "file_type": file_info["file_md5"][:8] + "...",
                    "created_at": file_info["created_at"],
                    "updated_at": file_info["created_at"],
                    "metadata": file_info,
                }
            )

        return {
            "success": True,
            "data": {
                "documents": documents,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "pages": (total + page_size - 1) // page_size,
                },
                "collection_info": {
                    "name": collection_name,
                    "file_count": result.get("file_count", 0),
                    "total_size_mb": result.get("total_size_mb", 0),
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Collection文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Collection文档失败: {str(e)}")


from pydantic import BaseModel


class AddTextRequest(BaseModel):
    title: str
    content: str
    collection_name: str = "ai_chat"
    user_id: str = "admin"


@rag_documents_router.post("/add-text", summary="添加文本文档")
async def add_text_document(
    request: AddTextRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """添加文本文档到知识库"""
    try:
        logger.info(
            f"添加文本文档 | 标题: {request.title} | Collection: {request.collection_name}"
        )

        # 添加到RAG知识库
        result = await rag_service.add_text_to_collection(
            text=request.content,
            collection_name=request.collection_name,
            metadata={
                "title": request.title,
                "source": "manual_input",
                "user_id": request.user_id,
            },
        )

        if result.get("success", False):
            # 计算内容MD5并记录到数据库
            import hashlib

            content_bytes = request.content.encode("utf-8")
            md5_hash = hashlib.md5(content_bytes).hexdigest()

            # 检查是否已存在
            existing_record = await rag_file_upload_service.check_file_exists(
                md5_hash, request.collection_name
            )

            if not existing_record:
                # 创建文档记录
                await rag_file_upload_service.record_uploaded_file(
                    filename=f"{request.title}.txt",
                    file_md5=md5_hash,
                    file_size=len(content_bytes),
                    collection_name=request.collection_name,
                    user_id=request.user_id,
                )

            return {
                "code": 200,
                "msg": "文本文档添加成功",
                "data": {
                    "title": request.title,
                    "collection_name": request.collection_name,
                    "vector_count": result.get("vector_count", 0),
                    "chunk_count": result.get("chunk_count", 0),
                },
            }
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "添加文档失败")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加文本文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加文本文档失败: {str(e)}")


@rag_documents_router.delete("/{document_id}", summary="删除文档")
async def delete_document(
    document_id: int, user_id: str = Query("admin", description="用户ID")
):
    """删除文档"""
    try:
        logger.info(f"删除文档 | ID: {document_id} | 用户: {user_id}")

        # 删除数据库记录
        success = await rag_file_upload_service.delete_document_record(
            document_id, user_id
        )

        if success:
            return {"success": True, "message": "文档删除成功"}
        else:
            raise HTTPException(status_code=404, detail="文档不存在或无权限删除")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@rag_documents_router.get("/stats", summary="获取文档统计信息")
async def get_document_stats():
    """获取文档统计信息"""
    try:
        stats = await rag_file_upload_service.get_document_statistics()

        return {"success": True, "data": stats}

    except Exception as e:
        logger.error(f"获取文档统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档统计失败: {str(e)}")


@rag_documents_router.post("/batch-upload", summary="批量上传文档")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    collection_name: str = Form("ai_chat"),
    user_id: str = Form("admin"),
):
    """批量上传文档"""
    try:
        logger.info(
            f"批量上传文档 | 文件数: {len(files)} | Collection: {collection_name}"
        )

        # 使用现有的文件上传服务
        from backend.services.ai_chat.autogen_service import autogen_service
        from backend.services.document.document_service import document_service
        from backend.services.rag.file_upload_service import rag_file_upload_service

        results = []

        for file in files:
            try:
                # 读取文件内容
                content = await file.read()

                # 检查重复
                upload_check = await rag_file_upload_service.process_file_upload(
                    filename=file.filename,
                    content=content,
                    collection_name=collection_name,
                    user_id=user_id,
                )

                if upload_check.get("skip_upload", False):
                    results.append(
                        {
                            "filename": file.filename,
                            "status": upload_check.get("status", "error"),
                            "message": upload_check.get("message", "处理失败"),
                            "success": False,
                        }
                    )
                    continue

                # 解析文件内容
                file_type = (
                    file.filename.split(".")[-1].lower()
                    if "." in file.filename
                    else "txt"
                )
                parsed_content = await document_service.parse_file_content(
                    content, file.filename, f".{file_type}"
                )

                if not parsed_content:
                    results.append(
                        {
                            "filename": file.filename,
                            "status": "error",
                            "message": "文件解析失败",
                            "success": False,
                        }
                    )
                    continue

                # 添加到RAG
                rag_result = await autogen_service.add_content_to_rag(
                    content=parsed_content,
                    filename=file.filename,
                    collection_name=collection_name,
                )

                if rag_result.get("success", False):
                    # 记录到数据库
                    await rag_file_upload_service.complete_file_upload(
                        filename=file.filename,
                        file_md5=upload_check.get("file_md5"),
                        file_size=upload_check.get("file_size"),
                        collection_name=collection_name,
                        user_id=user_id,
                    )

                    results.append(
                        {
                            "filename": file.filename,
                            "status": "success",
                            "message": "上传成功",
                            "success": True,
                            "vector_count": rag_result.get("vector_count", 0),
                        }
                    )
                else:
                    results.append(
                        {
                            "filename": file.filename,
                            "status": "error",
                            "message": rag_result.get("error", "RAG处理失败"),
                            "success": False,
                        }
                    )

            except Exception as file_error:
                results.append(
                    {
                        "filename": file.filename,
                        "status": "error",
                        "message": str(file_error),
                        "success": False,
                    }
                )

        # 统计结果
        success_count = sum(1 for r in results if r.get("success", False))

        return {
            "success": True,
            "message": f"批量上传完成，成功 {success_count}/{len(files)} 个文件",
            "data": {
                "total": len(files),
                "success": success_count,
                "failed": len(files) - success_count,
                "results": results,
            },
        }

    except Exception as e:
        logger.error(f"批量上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量上传失败: {str(e)}")
