"""
RAG知识库相关API路由
"""

from fastapi import APIRouter
from loguru import logger

# 导入各个RAG子模块
from .chat import rag_chat_router
from .collections import rag_collections_router
from .dashboard import rag_dashboard_router
from .documents import rag_documents_router

# 创建RAG主路由
rag_router = APIRouter()

# 注册子路由
rag_router.include_router(rag_chat_router, tags=["RAG聊天查询"])
rag_router.include_router(rag_dashboard_router, prefix="/dashboard", tags=["RAG仪表板"])
rag_router.include_router(
    rag_documents_router, prefix="/documents", tags=["RAG文档管理"]
)
rag_router.include_router(
    rag_collections_router, prefix="/collections", tags=["RAG Collection管理"]
)


# 添加主路由级别的API
@rag_router.get("/processing/jobs", summary="获取处理任务列表")
async def get_processing_jobs():
    """获取文档处理任务列表"""
    try:
        logger.info("📋 获取处理任务列表")
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

        logger.success(f"✅ 处理任务列表获取成功: {len(jobs)} 个任务")
        return {"code": 200, "msg": "获取处理任务成功", "data": {"jobs": jobs}}

    except Exception as e:
        logger.error(f"❌ 获取处理任务失败: {e}")
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=f"获取处理任务失败: {str(e)}")


logger.info("🔗 RAG路由模块初始化完成")

__all__ = ["rag_router"]
