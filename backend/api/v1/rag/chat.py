"""
RAG聊天和查询相关API
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from backend.controllers.rag_controller import rag_query_controller
from backend.services.rag.rag_service import RAGService, get_rag_service

# 创建路由器
rag_chat_router = APIRouter()


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


class CollectionSetupRequest(BaseModel):
    """Collection设置请求"""

    collection_name: str
    overwrite: bool = False


@rag_chat_router.get("/collections/{collection_name}", summary="获取指定Collection信息")
async def get_collection_info(
    collection_name: str, rag_service: RAGService = Depends(get_rag_service)
):
    """获取指定Collection信息"""
    try:
        logger.info(f"🔍 获取Collection信息: {collection_name}")
        result = await rag_service.get_collection_info(collection_name)
        if result is None:
            logger.warning(f"⚠️ Collection不存在: {collection_name}")
            raise HTTPException(
                status_code=404, detail=f"Collection不存在: {collection_name}"
            )

        logger.success(f"✅ Collection信息获取成功: {collection_name}")
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取Collection信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Collection信息失败: {str(e)}")


@rag_chat_router.post("/collections/setup", summary="设置Collection")
async def setup_collection(
    request: CollectionSetupRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """设置Collection"""
    try:
        logger.info(
            f"⚙️ 设置Collection: {request.collection_name} (覆盖: {request.overwrite})"
        )
        result = await rag_service.setup_collection(
            request.collection_name, request.overwrite
        )
        logger.success(f"✅ Collection设置成功: {request.collection_name}")
        return result
    except Exception as e:
        logger.error(f"❌ Collection设置失败: {e}")
        raise HTTPException(status_code=500, detail=f"Collection设置失败: {str(e)}")


@rag_chat_router.post("/collections/setup-all", summary="设置所有Collections")
async def setup_all_collections(
    overwrite: bool = False, rag_service: RAGService = Depends(get_rag_service)
):
    """设置所有Collections"""
    try:
        logger.info(f"⚙️ 设置所有Collections (覆盖: {overwrite})")
        result = await rag_service.setup_all_collections(overwrite)
        logger.success("✅ 所有Collections设置成功")
        return result
    except Exception as e:
        logger.error(f"❌ 所有Collections设置失败: {e}")
        raise HTTPException(
            status_code=500, detail=f"所有Collections设置失败: {str(e)}"
        )


@rag_chat_router.post("/query", summary="RAG查询")
async def query(request: QueryRequest):
    """执行RAG查询"""
    logger.info(
        f"🔍 RAG查询: {request.question[:50]}... | Collection: {request.collection_name}"
    )
    try:
        result = await rag_query_controller.query(request)
        logger.success(f"✅ RAG查询成功: {request.collection_name}")
        return result
    except Exception as e:
        logger.error(f"❌ RAG查询失败: {e}")
        raise


@rag_chat_router.post("/query/multiple", summary="多Collection查询")
async def query_multiple(
    request: MultiQueryRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """在多个Collections中查询"""
    try:
        logger.info(
            f"🔍 多Collection查询: {request.question[:50]}... | Collections: {request.collection_names}"
        )
        result = await rag_service.query_multiple_collections(
            request.question, request.collection_names
        )
        logger.success(
            f"✅ 多Collection查询成功: {len(request.collection_names)} 个Collection"
        )
        return result
    except Exception as e:
        logger.error(f"❌ 多Collection查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"多Collection查询失败: {str(e)}")


@rag_chat_router.post("/query/business", summary="业务类型查询")
async def query_business(
    request: BusinessQueryRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """根据业务类型查询"""
    try:
        logger.info(
            f"🔍 业务类型查询: {request.question[:50]}... | 业务类型: {request.business_type}"
        )
        result = await rag_service.query_business_type(
            request.question, request.business_type
        )
        logger.success(f"✅ 业务类型查询成功: {request.business_type}")
        return result
    except Exception as e:
        logger.error(f"❌ 业务类型查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"业务类型查询失败: {str(e)}")


@rag_chat_router.post("/chat", summary="RAG聊天")
async def chat(
    request: ChatRequest, rag_service: RAGService = Depends(get_rag_service)
):
    """RAG聊天接口"""
    try:
        logger.info(
            f"💬 RAG聊天: {request.message[:50]}... | Collection: {request.collection_name}"
        )
        result = await rag_service.chat(request.message, request.collection_name)
        logger.success(f"✅ RAG聊天成功: {request.collection_name}")
        return result
    except Exception as e:
        logger.error(f"❌ RAG聊天失败: {e}")
        raise HTTPException(status_code=500, detail=f"RAG聊天失败: {str(e)}")


# 这个路由移动到了主RAG路由中


@rag_chat_router.delete(
    "/collections/{collection_name}/clear", summary="清空Collection数据"
)
async def clear_collection(
    collection_name: str, rag_service: RAGService = Depends(get_rag_service)
):
    """清空Collection数据"""
    try:
        logger.warning(f"🗑️ 清空Collection数据: {collection_name}")
        result = await rag_service.clear_collection(collection_name)
        logger.success(f"✅ Collection数据清空成功: {collection_name}")
        return result
    except Exception as e:
        logger.error(f"❌ 清空Collection数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空Collection数据失败: {str(e)}")


# 处理任务路由移动到了主RAG路由中


logger.info("🔗 RAG聊天路由模块初始化完成")
