#!/usr/bin/env python3
"""
AutoGen 服务 - 修复版本
支持RAG增强的流式聊天，使用消息队列实现
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import ModelClientStreamingChunkEvent
from loguru import logger

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

# 使用 AI 核心模块的配置
from backend.ai_core.llm import get_default_client
from backend.ai_core.message_queue import (
    MessageQueueManager,
    get_streaming_sse_messages_from_queue,
    put_message_to_queue,
    put_streaming_message_to_queue,
)
from backend.services.rag.rag_service import get_rag_service


class AutoGenService:
    """AutoGen 服务类，支持RAG增强的流式聊天"""

    def __init__(
        self,
        max_agents: int = 100,
        cleanup_interval: int = 3600,
        agent_ttl: int = 7200,
    ):
        self.agents: Dict[str, Dict] = {}
        self.max_agents = max_agents
        self.cleanup_interval = cleanup_interval
        self.agent_ttl = agent_ttl
        self.last_cleanup = asyncio.get_event_loop().time()
        self.rag_service = None
        self.message_queue_manager = MessageQueueManager()
        logger.info(
            f"AutoGen 服务初始化 | 最大Agent数: {max_agents} | TTL: {agent_ttl}s | 支持RAG知识库"
        )

    def create_agent(
        self,
        conversation_id: str,
        system_message: str = "你是一个有用的AI助手",
    ) -> AssistantAgent:
        """创建或获取 Agent"""
        if conversation_id not in self.agents:
            logger.debug(f"创建新的 Agent | 对话ID: {conversation_id}")
            # 将 UUID 中的连字符替换为下划线，确保是有效的 Python 标识符
            safe_name = f"assistant_{conversation_id.replace('-', '_')}"

            agent = AssistantAgent(
                name=safe_name,
                model_client=get_default_client(),
                system_message=system_message,
                model_client_stream=True,
            )

            self.agents[conversation_id] = {
                "agent": agent,
                "created_at": asyncio.get_event_loop().time(),
                "last_used": asyncio.get_event_loop().time(),
            }
            logger.success(
                f"Agent 创建成功 | 对话ID: {conversation_id} | 名称: {safe_name}"
            )
        else:
            logger.debug(f"复用现有 Agent | 对话ID: {conversation_id}")
            # 更新最后使用时间
            self.agents[conversation_id]["last_used"] = asyncio.get_event_loop().time()
        return self.agents[conversation_id]["agent"]

    async def _ensure_rag_service(self):
        """确保RAG服务已初始化"""
        if self.rag_service is None:
            try:
                self.rag_service = await get_rag_service()
                logger.info("RAG服务初始化成功")
            except Exception as e:
                logger.error(f"RAG服务初始化失败: {e}")
                self.rag_service = None

    async def query_rag(self, question: str, collection_name: str) -> Optional[Dict]:
        """查询RAG知识库"""
        await self._ensure_rag_service()
        if self.rag_service is None:
            return None

        try:
            result = await self.rag_service.query(question, collection_name)
            if result.get("success"):
                logger.info(f"RAG查询成功: {collection_name}")
                return result
            else:
                logger.warning(f"RAG查询失败: {result.get('message')}")
                return None
        except Exception as e:
            logger.error(f"RAG查询异常: {e}")
            return None

    async def get_rag_collections(self) -> List[str]:
        """获取可用的RAG集合列表"""
        await self._ensure_rag_service()
        if self.rag_service is None:
            return []

        try:
            collections = self.rag_service.list_collections()
            return collections
        except Exception as e:
            logger.error(f"获取RAG集合失败: {e}")
            return []

    def _auto_cleanup(self):
        """自动清理过期的Agent"""
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_expired_agents()
            self.last_cleanup = current_time

    def _cleanup_expired_agents(self):
        """清理过期的Agent"""
        current_time = asyncio.get_event_loop().time()
        expired_ids = []

        for conversation_id, agent_info in self.agents.items():
            if current_time - agent_info["last_used"] > self.agent_ttl:
                expired_ids.append(conversation_id)

        for conversation_id in expired_ids:
            del self.agents[conversation_id]
            logger.debug(f"清理过期Agent | 对话ID: {conversation_id}")

        if expired_ids:
            logger.info(f"清理了 {len(expired_ids)} 个过期Agent")

    def _cleanup_oldest_agents(self, keep_count: int):
        """清理最旧的Agent，保留指定数量"""
        if len(self.agents) <= keep_count:
            return

        # 按最后使用时间排序
        sorted_agents = sorted(self.agents.items(), key=lambda x: x[1]["last_used"])

        # 删除最旧的Agent
        remove_count = len(self.agents) - keep_count
        for i in range(remove_count):
            conversation_id = sorted_agents[i][0]
            del self.agents[conversation_id]
            logger.debug(f"清理最旧Agent | 对话ID: {conversation_id}")

        logger.info(f"清理了 {remove_count} 个最旧Agent")

    async def start_rag_chat_stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        system_message: str = "你是一个有用的AI助手",
        collection_name: str = "ai_chat",
        use_rag: bool = True,
    ) -> None:
        """
        启动RAG增强流式聊天处理（用于API层）

        这个方法将消息放入队列，不直接返回流式内容
        """
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        logger.info(
            f"启动RAG增强流式聊天处理 | 对话ID: {conversation_id} | 消息: {message[:100]}... | 使用RAG: {use_rag} | Collection: {collection_name}"
        )

        # 执行自动清理
        self._auto_cleanup()

        try:
            await self._process_rag_and_agent_stream(
                message, conversation_id, system_message, collection_name, use_rag
            )
        except Exception as e:
            logger.error(
                f"RAG增强流式聊天处理失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            error_message = json.dumps(
                {
                    "type": "error",
                    "source": "系统",
                    "content": f"❌ 处理失败: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )
            await put_message_to_queue(conversation_id, error_message)
            await put_message_to_queue(conversation_id, "CLOSE")

    async def _process_rag_and_agent_stream(
        self,
        message: str,
        conversation_id: str,
        system_message: str,
        collection_name: str,
        use_rag: bool,
    ) -> None:
        """处理RAG和Agent流式输出（放入队列）"""
        try:
            enhanced_message = message
            rag_context = ""

            # 如果启用RAG，执行RAG流程
            if use_rag:
                # 确保RAG服务已初始化
                await self._ensure_rag_service()

                # 1. 发送RAG查询开始信息
                rag_start_message = json.dumps(
                    {
                        "type": "rag_start",
                        "source": "RAG知识库",
                        "content": f"🔍 正在查询 {collection_name} 知识库...",
                        "collection_name": collection_name,
                        "timestamp": datetime.now().isoformat(),
                    },
                    ensure_ascii=False,
                )

                await put_message_to_queue(conversation_id, rag_start_message)

                # 2. 执行RAG查询：用户需求 → 向量化 → 检索 → 召回
                logger.info(f"🔍 查询RAG知识库 | Collection: {collection_name}")
                rag_result = await self.query_rag(message, collection_name)

                if rag_result and rag_result.get("success"):
                    rag_context = rag_result.get("answer", "")
                    retrieved_nodes = rag_result.get("retrieved_nodes", [])

                    logger.info(
                        f"✅ RAG查询成功 | 检索到 {len(retrieved_nodes)} 个相关文档"
                    )

                    # 3. 发送检索结果信息
                    retrieval_message = json.dumps(
                        {
                            "type": "rag_retrieval",
                            "source": "RAG知识库",
                            "content": f"📄 检索到 {len(retrieved_nodes)} 个相关文档",
                            "retrieved_count": len(retrieved_nodes),
                            "collection_name": collection_name,
                            "timestamp": datetime.now().isoformat(),
                        },
                        ensure_ascii=False,
                    )
                    logger.info(f"📄 检索到 {retrieval_message}")
                    await put_message_to_queue(conversation_id, retrieval_message)

                    # 4. 流式输出召回的内容
                    if retrieved_nodes:
                        retrieved_start_message = json.dumps(
                            {
                                "type": "rag_retrieved_start",
                                "source": "RAG知识库",
                                "content": "📚 召回的相关内容：",
                                "collection_name": collection_name,
                                "timestamp": datetime.now().isoformat(),
                            },
                            ensure_ascii=False,
                        )
                        await put_message_to_queue(
                            conversation_id, retrieved_start_message
                        )

                        # 逐个流式输出召回的文档
                        for i, node_info in enumerate(retrieved_nodes):
                            node_content = f"\n\n【文档 {i+1}】(相似度: {node_info.get('score', 0):.3f})\n{node_info.get('text', '')}"
                            logger.info(f"{node_content}")

                            # 分块流式输出文档内容
                            chunk_size = 100
                            for j in range(0, len(node_content), chunk_size):
                                chunk = node_content[j : j + chunk_size]
                                chunk_message = json.dumps(
                                    {
                                        "type": "rag_retrieved_chunk",
                                        "source": "RAG知识库",
                                        "content": chunk,
                                        "collection_name": collection_name,
                                        "document_index": i + 1,
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                    ensure_ascii=False,
                                )
                                await put_message_to_queue(
                                    conversation_id, chunk_message
                                )

                        retrieved_end_message = json.dumps(
                            {
                                "type": "rag_retrieved_end",
                                "source": "RAG知识库",
                                "content": "\n\n---\n",
                                "collection_name": collection_name,
                                "timestamp": datetime.now().isoformat(),
                            },
                            ensure_ascii=False,
                        )
                        await put_message_to_queue(
                            conversation_id, retrieved_end_message
                        )

                    # 5. 构建增强的提示给AutoGen Assistant
                    if rag_context:
                        enhanced_message = f"""基于以下知识库信息回答用户问题：

知识库信息：
{rag_context}

用户问题：{message}

请结合知识库信息和你的知识来回答用户问题。如果知识库信息不足以回答问题，请说明并提供你的最佳建议。"""
                else:
                    logger.info("❌ RAG查询无结果，使用原始消息")
                    no_result_message = json.dumps(
                        {
                            "type": "rag_no_result",
                            "source": "RAG知识库",
                            "content": f"📚 在 {collection_name} 知识库中未找到相关信息，将基于通用知识回答",
                            "collection_name": collection_name,
                            "timestamp": datetime.now().isoformat(),
                        },
                        ensure_ascii=False,
                    )
                    await put_message_to_queue(conversation_id, no_result_message)

            # 6. 创建普通Agent（不使用RAG增强的Agent）
            agent = self.create_agent(
                conversation_id=conversation_id,
                system_message=system_message,
            )

            # 7. 发送Agent开始处理的信息
            agent_start_message = json.dumps(
                {
                    "type": "agent_start",
                    "source": "AI智能体",
                    "content": "🤖 AI智能体开始处理您的问题...",
                    "timestamp": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )
            await put_message_to_queue(conversation_id, agent_start_message)

            # 8. 调用Agent处理增强后的消息
            result = agent.run_stream(task=enhanced_message)
            chunk_count = 0

            async for item in result:
                if isinstance(item, ModelClientStreamingChunkEvent):
                    if item.content:
                        chunk_count += 1
                        logger.debug(
                            f"收到流式数据块 {chunk_count} | 对话ID: {conversation_id} | 内容: {item.content[:50]}..."
                        )

                        # 发送流式内容到队列
                        streaming_message = json.dumps(
                            {
                                "type": "streaming_chunk",
                                "source": "AI智能体",
                                "content": item.content,
                                "timestamp": datetime.now().isoformat(),
                            },
                            ensure_ascii=False,
                        )
                        await put_message_to_queue(conversation_id, streaming_message)

            # 9. 发送完成信号到队列
            complete_message = json.dumps(
                {
                    "type": "complete",
                    "source": "AI智能体",
                    "content": "✅ 回答完成",
                    "timestamp": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )
            await put_message_to_queue(conversation_id, complete_message)

            # 发送关闭信号
            await put_message_to_queue(conversation_id, "CLOSE")

            logger.success(
                f"RAG增强流式聊天完成 | 对话ID: {conversation_id} | 总块数: {chunk_count} | 使用RAG: {use_rag}"
            )

        except Exception as e:
            logger.error(
                f"RAG和Agent流式处理失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            # 发送错误信息到队列
            error_message = json.dumps(
                {
                    "type": "error",
                    "source": "系统",
                    "content": f"❌ 处理失败: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            )
            await put_message_to_queue(conversation_id, error_message)
            await put_message_to_queue(conversation_id, "CLOSE")

    async def get_agent_stats(self) -> dict:
        """获取 Agent 统计信息，包括RAG状态"""
        current_time = asyncio.get_event_loop().time()
        active_count = 0
        expired_count = 0

        for agent_info in self.agents.values():
            if current_time - agent_info["last_used"] <= self.agent_ttl:
                active_count += 1
            else:
                expired_count += 1

        # 获取RAG统计信息
        rag_stats = {}
        try:
            await self._ensure_rag_service()
            if self.rag_service:
                rag_system_stats = await self.rag_service.get_system_stats()
                rag_collections = await self.get_rag_collections()
                rag_stats = {
                    "rag_available": True,
                    "rag_collections": rag_collections,
                    "rag_system_stats": rag_system_stats,
                }
            else:
                rag_stats = {"rag_available": False}
        except Exception as e:
            logger.error(f"获取RAG统计信息失败: {e}")
            rag_stats = {"rag_available": False, "rag_error": str(e)}

        return {
            "total_agents": len(self.agents),
            "active_agents": active_count,
            "expired_count": expired_count,
            "max_agents": self.max_agents,
            "agent_ttl": self.agent_ttl,
            "cleanup_interval": self.cleanup_interval,
            **rag_stats,
        }

    async def add_content_to_rag(
        self, content: str, filename: str, collection_name: str = "ai_chat"
    ) -> dict:
        """
        添加文本内容到RAG知识库

        Args:
            content: 文本内容
            filename: 文件名（用于标识）
            collection_name: 集合名称

        Returns:
            dict: 处理结果
        """
        try:
            await self._ensure_rag_service()
            if not self.rag_service:
                return {"success": False, "error": "RAG服务不可用"}

            logger.info(
                f"添加内容到RAG | 文件: {filename} | 集合: {collection_name} | 内容长度: {len(content)}"
            )

            # 调用RAG服务添加内容
            result = await self.rag_service.add_text_to_collection(
                text=content,
                collection_name=collection_name,
                metadata={"filename": filename, "source": "upload"},
            )

            if result.get("success", False):
                logger.success(
                    f"内容添加成功 | 文件: {filename} | 向量数: {result.get('vector_count', 0)}"
                )
                return {
                    "success": True,
                    "vector_count": result.get("vector_count", 0),
                    "chunk_count": result.get("chunk_count", 0),
                    "collection_name": collection_name,
                    "filename": filename,
                }
            else:
                error_msg = result.get("error", "未知错误")
                logger.error(f"内容添加失败 | 文件: {filename} | 错误: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            logger.error(f"添加内容到RAG异常 | 文件: {filename} | 错误: {e}")
            return {"success": False, "error": str(e)}

    async def add_file_to_rag(
        self, file_path: str, collection_name: str = "ai_chat"
    ) -> dict:
        """
        添加文件到RAG知识库（兼容旧接口）

        Args:
            file_path: 文件路径
            collection_name: 集合名称

        Returns:
            dict: 处理结果
        """
        try:
            from backend.services.document.document_service import document_service

            # 读取文件内容
            with open(file_path, "rb") as f:
                content = f.read()

            filename = Path(file_path).name
            file_type = Path(file_path).suffix.lower()

            # 解析文件内容
            parsed_content = await document_service.parse_file_content(
                content, filename, file_type
            )

            if not parsed_content:
                return {"success": False, "error": "文件解析失败"}

            # 添加到RAG
            return await self.add_content_to_rag(
                content=parsed_content,
                filename=filename,
                collection_name=collection_name,
            )

        except Exception as e:
            logger.error(f"添加文件到RAG异常 | 文件: {file_path} | 错误: {e}")
            return {"success": False, "error": str(e)}


# 全局服务实例
def create_autogen_service():
    """创建 AutoGen 服务实例"""
    try:
        # 尝试导入配置
        from backend.conf.config import settings

        # 使用配置中的参数，如果没有则使用默认值
        max_agents = getattr(settings, "autogen", {}).get("max_agents", 100)
        cleanup_interval = getattr(settings, "autogen", {}).get(
            "cleanup_interval", 3600
        )
        agent_ttl = getattr(settings, "autogen", {}).get("agent_ttl", 7200)

        return AutoGenService(
            max_agents=max_agents,
            cleanup_interval=cleanup_interval,
            agent_ttl=agent_ttl,
        )
    except ImportError:
        logger.warning("无法导入配置，使用默认参数")
        return AutoGenService()


autogen_service = create_autogen_service()
