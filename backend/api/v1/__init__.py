"""
API v1 版本路由
"""

from fastapi import APIRouter

from backend.api_core.dependency import DependAdmin, DependPermission

from .auth import auth_router
from .chat import chat_router
from .midscene import midscene_router
from .rag import rag_router
from .system import system_router
from .testcase import testcase_router

# 创建v1版本的主路由
v1_router = APIRouter()

# 注册各个模块的路由
v1_router.include_router(auth_router, prefix="/auth", tags=["认证"])
v1_router.include_router(chat_router, prefix="/chat", tags=["AI对话"])
v1_router.include_router(testcase_router, prefix="/testcase", tags=["测试用例生成"])
v1_router.include_router(midscene_router, prefix="/midscene", tags=["Midscene智能体"])
v1_router.include_router(rag_router, prefix="/rag", tags=["RAG知识库"])
# 系统管理需要管理员权限
v1_router.include_router(
    system_router,
    prefix="/system",
    tags=["系统管理"],
    # dependencies=[DependAdmin]
)

__all__ = ["v1_router"]
