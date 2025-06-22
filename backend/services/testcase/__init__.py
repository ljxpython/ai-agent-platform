"""
测试用例生成模块

该模块包含测试用例生成相关的服务：
- 测试用例生成服务
- 测试用例专用运行时
- 测试用例智能体实现
"""

from .agents import (
    RequirementAnalysisAgent,
    TestCaseFinalizationAgent,
    TestCaseGenerationAgent,
    TestCaseOptimizationAgent,
)
from .testcase_runtime import TestCaseRuntime, get_testcase_runtime
from .testcase_service import (
    FeedbackMessage,
    RequirementMessage,
    TestCaseService,
    testcase_service,
)

__all__ = [
    # 服务类
    "TestCaseService",
    "testcase_service",
    # 消息模型
    "RequirementMessage",
    "FeedbackMessage",
    # 运行时
    "TestCaseRuntime",
    "get_testcase_runtime",
    # 智能体
    "RequirementAnalysisAgent",
    "TestCaseGenerationAgent",
    "TestCaseOptimizationAgent",
    "TestCaseFinalizationAgent",
]
