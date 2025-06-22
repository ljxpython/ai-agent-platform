"""
AI测试用例生成API路由 - 重新设计版本
实现两个核心接口：
1. /generate/sse - 启动需求分析和初步用例生成
2. /feedback - 处理用户反馈，支持优化和最终化
"""

import asyncio
import base64
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.models.chat import FileUpload, TestCaseRequest
from backend.services.document.document_service import document_service
from backend.services.testcase.testcase_service import (
    FeedbackMessage,
    RequirementMessage,
    testcase_service,
)

testcase_router = APIRouter()


# 消费者（SSE流生成）- 直接使用TestCaseService的流式接口
async def testcase_message_generator(conversation_id: str):
    """
    测试用例流式消息生成器 - 直接使用TestCaseService
    """
    try:
        # 直接使用TestCaseService的流式消息获取方法
        async for message in testcase_service.get_streaming_messages(conversation_id):
            yield message
    except Exception as e:
        logger.error(f"❌ [流式消息] 生成失败 | 对话ID: {conversation_id} | 错误: {e}")
        error_message = {
            "type": "error",
            "source": "system",
            "content": f"流式消息生成失败: {str(e)}",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
        }
        yield f"data: {json.dumps(error_message, ensure_ascii=False)}\n\n"


class FeedbackRequest(BaseModel):
    """用户反馈请求模型"""

    conversation_id: str
    feedback: str
    round_number: int
    previous_testcases: Optional[str] = ""


class GenerateRequest(BaseModel):
    """生成请求模型"""

    conversation_id: Optional[str] = None
    text_content: Optional[str] = None
    files: Optional[List[FileUpload]] = None
    round_number: int = 1


class StreamingGenerateRequest(BaseModel):
    """流式生成请求模型 - 简化版本，文件通过upload接口单独上传"""

    conversation_id: Optional[str] = None
    text_content: Optional[str] = None
    round_number: int = 1
    enable_streaming: bool = True


@testcase_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(
        ..., description="对话ID，与测试用例生成的conversation_id保持一致"
    ),
):
    """
    文件上传接口 - 使用marker进行高质量文档处理，参考examples/topic1.py

    功能：
    1. 接收上传的文件
    2. 使用marker进行文档解析和内容提取
    3. 支持图片分析和描述
    4. 返回文件ID和解析统计信息
    5. 使用conversation_id作为session_id，确保与测试用例生成流程一致

    Args:
        file: 上传的文件
        conversation_id: 对话ID，与测试用例生成的conversation_id保持一致

    Returns:
        包含文件ID、统计信息和处理配置的响应
    """
    logger.info(f"📁 [文件上传-高质量解析] 收到文件上传请求")
    logger.info(f"   📄 文件名: {file.filename}")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   📊 文件大小: {file.size if hasattr(file, 'size') else '未知'}")
    logger.info(f"   🔧 内容类型: {file.content_type}")

    try:
        # 使用文档服务处理文件，使用conversation_id作为session_id
        logger.info(f"🚀 [文件上传-高质量解析] 开始使用marker处理文件: {file.filename}")
        result = await document_service.save_and_extract_file(file, conversation_id)

        logger.success(f"✅ [文件上传-高质量解析] 文件处理完成")
        logger.info(f"   📋 文件ID: {result['file_id']}")
        logger.info(f"   📊 统计信息:")
        logger.info(f"     - 总字符数: {result['statistics']['total_characters']}")
        logger.info(f"     - 总词数: {result['statistics']['total_words']}")
        logger.info(f"     - 表格数: {result['statistics']['tables_count']}")
        logger.info(f"     - 图片数: {result['statistics']['images_count']}")
        logger.info(f"     - 标题数: {result['statistics']['headers_count']}")
        logger.info(f"   🔧 处理配置:")
        logger.info(f"     - LLM启用: {result['processing_info']['llm_enabled']}")
        logger.info(f"     - 格式增强: {result['processing_info']['format_enhanced']}")

        return {"status": "success", "message": "文件上传成功", "data": result}

    except HTTPException as e:
        logger.error(f"❌ [文件上传-高质量解析] HTTP异常: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"❌ [文件上传-高质量解析] 文件上传失败")
        logger.error(f"   🐛 错误类型: {type(e).__name__}")
        logger.error(f"   📄 错误详情: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@testcase_router.post("/generate/streaming")
async def generate_testcase_streaming(request: StreamingGenerateRequest):
    """
    流式生成测试用例接口 - 队列模式，参考examples/topic1.py

    功能：启动需求分析和初步用例生成，返回流式输出
    流程：用户输入 → 需求分析智能体 → 测试用例生成智能体 → 队列消费者 → 流式SSE返回

    采用队列模式：
    1. 启动后台任务处理智能体流程
    2. 返回队列消费者的流式响应
    3. 智能体将消息放入队列，消费者从队列取出并流式返回

    Args:
        request: 流式生成请求对象

    Returns:
        StreamingResponse: SSE流式响应，实时返回智能体处理结果
    """
    # 生成或使用提供的对话ID
    conversation_id = request.conversation_id or str(uuid.uuid4())

    logger.info(f"🚀 [API-流式生成-队列模式] 收到流式测试用例生成请求")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   📝 文本内容长度: {len(request.text_content or '')}")
    logger.info(f"   🔢 轮次: {request.round_number}")
    logger.info(f"   🌊 流式模式: {request.enable_streaming}")
    logger.info(f"   🌐 请求方法: POST /api/testcase/generate/streaming (队列模式)")

    # 创建需求消息对象
    logger.info(
        f"📦 [API-流式生成-队列模式] 创建需求消息对象 | 对话ID: {conversation_id}"
    )
    requirement = RequirementMessage(
        text_content=request.text_content or "",
        files=[],  # 文件通过upload接口单独上传，这里为空
        file_paths=[],  # 文件通过upload接口单独上传，这里为空
        conversation_id=conversation_id,
        round_number=request.round_number,
    )
    logger.debug(f"   📋 需求消息: {requirement}")
    logger.success(
        f"✅ [API-流式生成-队列模式] 需求消息对象创建完成 | 对话ID: {conversation_id}"
    )

    # 启动后台任务处理智能体流程 - 参考examples/topic1.py
    logger.info(f"🚀 [API-流式生成-队列模式] 启动后台任务 | 对话ID: {conversation_id}")
    asyncio.create_task(testcase_service.start_streaming_generation(requirement))

    # 返回队列消费者的流式响应 - 参考examples/topic1.py
    logger.info(
        f"📡 [API-流式生成-队列模式] 返回队列消费者流式响应 | 对话ID: {conversation_id}"
    )
    return StreamingResponse(
        testcase_message_generator(conversation_id=conversation_id),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# 已删除 /generate/stream 接口 - 已被 /generate/sse 接口替代


# 已删除 /generate 接口 - 前端未使用，已被 /generate/sse 接口替代


@testcase_router.get("/feedback")
async def submit_feedback_simple(conversation_id: str, message: str):
    """
    简单用户反馈接口 - 参考examples/topic1.py模式

    功能：接收用户反馈并放入队列，立即返回确认
    - 类比examples/topic1.py中的简单feedback接口
    - 直接调用put_feedback_to_queue放入队列
    - 立即返回确认消息，不处理流式响应

    Args:
        conversation_id: 对话ID
        message: 用户反馈消息

    Returns:
        dict: 简单的确认消息
    """
    logger.info(f"💬 [API-简单反馈] 收到用户反馈")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   💭 反馈内容: {message}")
    logger.info(f"   🌐 请求方法: GET /api/testcase/feedback (简单模式)")

    # 使用新的服务接口处理反馈
    feedback = FeedbackMessage(
        feedback=message, conversation_id=conversation_id, round_number=1
    )
    asyncio.create_task(testcase_service.process_user_feedback(feedback))

    logger.success(f"✅ [API-简单反馈] 反馈已放入队列 | 对话ID: {conversation_id}")
    return {"message": "ok"}


# 已删除 /conversation/{id} GET 接口 - 前端未使用


# 已删除 /conversation/{id} DELETE 接口 - 前端未使用


# 已删除 /stats 接口 - 前端未使用


# 旧的GET接口已移除，现在使用POST流式接口


@testcase_router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    """
    获取对话历史接口

    功能：获取指定对话的完整历史记录和消息列表

    Args:
        conversation_id: 对话唯一标识符

    Returns:
        dict: 包含历史记录和消息列表的响应数据
    """
    logger.info(f"📚 [API-历史接口] 收到获取对话历史请求")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   🌐 请求方法: GET /api/testcase/history/{conversation_id}")

    try:
        # 获取对话历史
        logger.info(f"📖 [API-历史接口] 获取对话历史 | 对话ID: {conversation_id}")
        history = await testcase_service.get_conversation_history(conversation_id)
        logger.info(f"   📊 历史记录数量: {len(history)}")

        # 构造响应数据
        response_data = {
            "conversation_id": conversation_id,
            "history": history,
            "total_history": len(history),
        }
        logger.debug(f"   📦 响应数据: {response_data}")

        logger.success(
            f"✅ [API-历史接口] 对话历史获取成功 | 对话ID: {conversation_id}"
        )
        logger.info(f"   📊 历史记录: {len(history)} 条")

        return response_data

    except Exception as e:
        logger.error(f"❌ [API-历史接口] 获取对话历史失败 | 对话ID: {conversation_id}")
        logger.error(f"   🐛 错误类型: {type(e).__name__}")
        logger.error(f"   📄 错误详情: {str(e)}")
        logger.error(f"   📍 错误位置: 历史接口处理过程")

        raise HTTPException(status_code=500, detail=str(e))


@testcase_router.delete("/conversation/{conversation_id}")
async def clear_conversation_history(conversation_id: str):
    """
    清除对话历史接口

    功能：清除指定对话的所有历史记录和消息

    Args:
        conversation_id: 对话唯一标识符

    Returns:
        dict: 清除结果
    """
    logger.info(f"🗑️ [API-清除历史] 收到清除对话历史请求")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   🌐 请求方法: DELETE /api/testcase/conversation/{conversation_id}")

    try:
        # 清除对话资源
        await testcase_service.cleanup_conversation(conversation_id)

        logger.success(
            f"✅ [API-清除历史] 对话历史清除成功 | 对话ID: {conversation_id}"
        )

        return {
            "success": True,
            "message": "对话历史已清除",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ [API-清除历史] 清除对话历史失败 | 对话ID: {conversation_id}")
        logger.error(f"   🐛 错误类型: {type(e).__name__}")
        logger.error(f"   📄 错误详情: {str(e)}")
        logger.error(f"   📍 错误位置: 清除历史接口处理过程")

        raise HTTPException(status_code=500, detail=str(e))
