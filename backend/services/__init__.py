"""
后端服务模块

该模块包含所有业务服务，按功能模块组织：
- ai_chat: AI对话相关服务
- testcase: 测试用例生成相关服务
- ui_testing: UI测试相关服务
- document: 文档处理相关服务
- auth: 认证权限相关服务
"""

# AI对话模块
from .ai_chat import AutoGenService, autogen_service

# 认证权限模块
from .auth import AuthService, PermissionService, permission_service

# 文档处理模块
from .document import (
    DocumentService,
    FileProcessor,
    ImageAnalyzer,
    default_analyzer,
    document_service,
)

# 测试用例生成模块
from .testcase import TestCaseService, testcase_service

# UI测试模块
from .ui_testing import MidsceneService

__all__ = [
    # AI对话
    "AutoGenService",
    "autogen_service",
    # 测试用例生成
    "TestCaseService",
    "testcase_service",
    # UI测试
    "MidsceneService",
    # 文档处理
    "DocumentService",
    "document_service",
    "FileProcessor",
    "ImageAnalyzer",
    "default_analyzer",
    # 认证权限
    "AuthService",
    "PermissionService",
    "permission_service",
]
