"""
RAG知识库服务
为后端API提供RAG功能的服务层
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from backend.conf.rag_config import RAGConfig, get_rag_config
from backend.rag_core.rag_system import QueryResult, RAGSystem


class RAGService:
    """RAG知识库服务"""

    def __init__(self, config: Optional[RAGConfig] = None):
        """
        初始化RAG服务

        Args:
            config: RAG配置
        """
        self.config = config or get_rag_config()
        self.rag_system: RAGSystem = None
        self._initialized = False

        logger.info("🔧 RAG服务初始化")

    async def initialize(self):
        """初始化RAG服务"""
        if self._initialized:
            return

        logger.info("🚀 正在初始化RAG服务...")

        try:
            # 初始化RAG系统
            self.rag_system = RAGSystem(self.config)
            await self.rag_system.initialize()

            self._initialized = True
            logger.success("✅ RAG服务初始化完成")

        except Exception as e:
            logger.error(f"❌ RAG服务初始化失败: {e}")
            raise

    async def ensure_initialized(self):
        """确保服务已初始化"""
        if not self._initialized:
            await self.initialize()

    # Collection管理相关方法
    async def setup_collection(
        self, collection_name: str, overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        设置collection

        Args:
            collection_name: collection名称
            overwrite: 是否覆盖现有collection

        Returns:
            Dict[str, Any]: 操作结果
        """
        await self.ensure_initialized()

        try:
            await self.rag_system.setup_collection(collection_name, overwrite)

            return {
                "success": True,
                "message": f"Collection {collection_name} 设置成功",
                "collection_name": collection_name,
            }

        except Exception as e:
            logger.error(f"❌ Collection设置失败 {collection_name}: {e}")
            return {
                "success": False,
                "message": f"Collection {collection_name} 设置失败: {str(e)}",
                "collection_name": collection_name,
            }

    async def setup_all_collections(self, overwrite: bool = False) -> Dict[str, Any]:
        """
        设置所有collections

        Args:
            overwrite: 是否覆盖现有collections

        Returns:
            Dict[str, Any]: 操作结果
        """
        await self.ensure_initialized()

        try:
            await self.rag_system.setup_all_collections(overwrite)

            return {
                "success": True,
                "message": "所有Collections设置成功",
                "collections": self.list_collections(),
            }

        except Exception as e:
            logger.error(f"❌ 所有Collections设置失败: {e}")
            return {
                "success": False,
                "message": f"所有Collections设置失败: {str(e)}",
            }

    def list_collections(self) -> List[str]:
        """列出所有collections"""
        if not self._initialized:
            return []
        return self.rag_system.list_collections()

    async def get_collection_info(
        self, collection_name: str
    ) -> Optional[Dict[str, Any]]:
        """获取collection信息"""
        await self.ensure_initialized()
        return self.rag_system.get_collection_info(collection_name)

    async def get_all_collections_info(self) -> Dict[str, Any]:
        """获取所有collections信息"""
        await self.ensure_initialized()

        collections_info = {}
        for collection_name in self.list_collections():
            info = await self.get_collection_info(collection_name)
            if info:
                collections_info[collection_name] = info

        return {
            "total_collections": len(collections_info),
            "collections": collections_info,
        }

    # 文档添加相关方法
    async def add_text(
        self,
        text: str,
        collection_name: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        添加文本到知识库

        Args:
            text: 文本内容
            collection_name: collection名称
            metadata: 元数据

        Returns:
            Dict[str, Any]: 添加结果
        """
        await self.ensure_initialized()

        operation_id = f"add_text_{hash(text[:100])}_{collection_name}"
        try:
            logger.info(
                f"🚀 [操作开始] {operation_id} | 添加文本到Collection: {collection_name}"
            )
            logger.info(f"📝 [文本信息] 长度: {len(text)} 字符 | 元数据: {metadata}")

            # 开始添加文本
            logger.info(f"⚙️ [处理阶段] 开始向量化和存储文本...")
            node_count = await self.rag_system.add_text(text, collection_name, metadata)

            logger.success(f"🎉 [操作完成] {operation_id} - 文本添加成功")
            logger.info(
                f"📊 [结果详情] Collection: {collection_name} | 节点数: {node_count} | 文本长度: {len(text)}"
            )

            return {
                "success": True,
                "message": f"文本添加成功",
                "collection_name": collection_name,
                "node_count": node_count,
                "text_length": len(text),
            }

        except Exception as e:
            logger.error(
                f"💥 [操作失败] {operation_id} - Collection: {collection_name} | 错误: {str(e)}"
            )
            logger.error(
                f"🔍 [错误详情] 异常类型: {type(e).__name__} | 文本长度: {len(text)}"
            )
            return {
                "success": False,
                "message": f"文本添加失败: {str(e)}",
                "collection_name": collection_name,
            }

    async def add_text_to_collection(
        self,
        text: str,
        collection_name: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        添加文本到指定collection（add_text的别名方法）

        Args:
            text: 要添加的文本内容
            collection_name: 集合名称
            metadata: 元数据

        Returns:
            Dict: 添加结果，包含vector_count和chunk_count
        """
        result = await self.add_text(text, collection_name, metadata)

        # 为了兼容性，添加vector_count和chunk_count字段
        if result.get("success", False):
            node_count = result.get("node_count", 0)
            result["vector_count"] = node_count
            result["chunk_count"] = node_count

        return result

    async def add_file(
        self, file_path: Union[str, Path], collection_name: str = "general"
    ) -> Dict[str, Any]:
        """
        添加文件到知识库

        Args:
            file_path: 文件路径
            collection_name: collection名称

        Returns:
            Dict[str, Any]: 添加结果
        """
        await self.ensure_initialized()

        try:
            node_count = await self.rag_system.add_file(file_path, collection_name)

            return {
                "success": True,
                "message": f"文件添加成功",
                "collection_name": collection_name,
                "node_count": node_count,
                "file_path": str(file_path),
            }

        except Exception as e:
            logger.error(f"❌ 文件添加失败 - Collection: {collection_name}: {e}")
            return {
                "success": False,
                "message": f"文件添加失败: {str(e)}",
                "collection_name": collection_name,
                "file_path": str(file_path),
            }

    # 查询相关方法
    async def query(
        self, question: str, collection_name: str = "general", **kwargs
    ) -> Dict[str, Any]:
        """
        执行RAG查询

        Args:
            question: 查询问题
            collection_name: collection名称
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: 查询结果
        """
        await self.ensure_initialized()

        try:
            result: QueryResult = await self.rag_system.query(
                question, collection_name, **kwargs
            )

            return {
                "success": True,
                "query": result.query,
                "answer": result.answer,
                "collection_name": result.collection_name,
                "business_type": result.business_type,
                "response_time": result.response_time,
                "retrieved_count": len(result.retrieved_nodes),
                "metadata": result.metadata,
                "retrieved_nodes": [
                    {
                        "text": (
                            node.node.text[:200] + "..."
                            if len(node.node.text) > 200
                            else node.node.text
                        ),
                        "score": node.score,
                        "metadata": node.node.metadata,
                    }
                    for node in result.retrieved_nodes
                ],
            }

        except Exception as e:
            logger.error(f"❌ RAG查询失败 - Collection: {collection_name}: {e}")
            return {
                "success": False,
                "message": f"RAG查询失败: {str(e)}",
                "collection_name": collection_name,
                "query": question,
            }

    async def query_multiple_collections(
        self, question: str, collection_names: List[str], **kwargs
    ) -> Dict[str, Any]:
        """
        在多个collections中查询

        Args:
            question: 查询问题
            collection_names: collection名称列表
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: 查询结果
        """
        await self.ensure_initialized()

        try:
            results = await self.rag_system.query_multiple_collections(
                question, collection_names, **kwargs
            )

            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "collection_name": result.collection_name,
                        "business_type": result.business_type,
                        "answer": result.answer,
                        "response_time": result.response_time,
                        "retrieved_count": len(result.retrieved_nodes),
                    }
                )

            return {
                "success": True,
                "query": question,
                "total_collections": len(formatted_results),
                "results": formatted_results,
            }

        except Exception as e:
            logger.error(f"❌ 多Collection查询失败: {e}")
            return {
                "success": False,
                "message": f"多Collection查询失败: {str(e)}",
                "query": question,
                "collection_names": collection_names,
            }

    async def query_business_type(
        self, question: str, business_type: str, **kwargs
    ) -> Dict[str, Any]:
        """
        根据业务类型查询

        Args:
            question: 查询问题
            business_type: 业务类型
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: 查询结果
        """
        await self.ensure_initialized()

        try:
            results = await self.rag_system.query_business_type(
                question, business_type, **kwargs
            )

            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "collection_name": result.collection_name,
                        "answer": result.answer,
                        "response_time": result.response_time,
                        "retrieved_count": len(result.retrieved_nodes),
                    }
                )

            return {
                "success": True,
                "query": question,
                "business_type": business_type,
                "total_results": len(formatted_results),
                "results": formatted_results,
            }

        except Exception as e:
            logger.error(f"❌ 业务类型查询失败 - {business_type}: {e}")
            return {
                "success": False,
                "message": f"业务类型查询失败: {str(e)}",
                "query": question,
                "business_type": business_type,
            }

    async def chat(
        self, message: str, collection_name: str = "general"
    ) -> Dict[str, Any]:
        """
        简单聊天接口

        Args:
            message: 聊天消息
            collection_name: collection名称

        Returns:
            Dict[str, Any]: 聊天结果
        """
        await self.ensure_initialized()

        try:
            answer = await self.rag_system.chat(message, collection_name)

            return {
                "success": True,
                "message": message,
                "answer": answer,
                "collection_name": collection_name,
            }

        except Exception as e:
            logger.error(f"❌ 聊天失败 - Collection: {collection_name}: {e}")
            return {
                "success": False,
                "message": f"聊天失败: {str(e)}",
                "collection_name": collection_name,
                "user_message": message,
            }

    # 系统管理相关方法
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        await self.ensure_initialized()
        return self.rag_system.get_stats()

    async def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """清空collection数据"""
        await self.ensure_initialized()

        try:
            await self.rag_system.clear_collection(collection_name)

            return {
                "success": True,
                "message": f"Collection {collection_name} 数据清空成功",
                "collection_name": collection_name,
            }

        except Exception as e:
            logger.error(f"❌ Collection数据清空失败 {collection_name}: {e}")
            return {
                "success": False,
                "message": f"Collection {collection_name} 数据清空失败: {str(e)}",
                "collection_name": collection_name,
            }

    async def clear_all_data(self) -> Dict[str, Any]:
        """清空所有数据"""
        await self.ensure_initialized()

        try:
            await self.rag_system.clear_all_data()

            return {
                "success": True,
                "message": "所有数据清空成功",
                "collections": self.list_collections(),
            }

        except Exception as e:
            logger.error(f"❌ 所有数据清空失败: {e}")
            return {
                "success": False,
                "message": f"所有数据清空失败: {str(e)}",
            }

    async def close(self):
        """关闭服务"""
        if self.rag_system:
            await self.rag_system.cleanup()

        self._initialized = False
        logger.info("🔄 RAG服务关闭完成")


# 全局RAG服务实例
_rag_service: Optional[RAGService] = None


async def get_rag_service() -> RAGService:
    """获取RAG服务实例（单例模式）"""
    global _rag_service

    if _rag_service is None:
        _rag_service = RAGService()
        await _rag_service.initialize()

    return _rag_service


if __name__ == "__main__":
    # 测试代码
    import asyncio

    async def test_rag_service():
        service = RAGService()
        await service.initialize()

        # 设置collections
        setup_result = await service.setup_all_collections(overwrite=True)
        print(f"设置结果: {setup_result}")

        # 添加测试文本
        add_result = await service.add_text(
            "人工智能是计算机科学的一个分支，致力于创建智能机器。",
            "general",
            {"source": "test", "topic": "AI"},
        )
        print(f"添加结果: {add_result}")

        # 测试查询
        query_result = await service.query("什么是人工智能？", "general")
        print(f"查询结果: {query_result}")

        # 获取统计信息
        stats = await service.get_system_stats()
        print(f"系统统计: {stats}")

        await service.close()

    asyncio.run(test_rag_service())
