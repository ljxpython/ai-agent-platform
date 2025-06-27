"""
RAG Collection管理服务
"""

from typing import Dict, List, Optional

from loguru import logger
from tortoise.exceptions import DoesNotExist, IntegrityError

from backend.conf.rag_config import CollectionConfig, get_rag_config
from backend.models.rag import RAGCollection, RAGDocument
from backend.rag_core.collection_manager import create_collection_manager


class RAGCollectionService:
    """RAG Collection管理服务"""

    async def initialize_default_collections(self):
        """初始化默认的Collections"""
        logger.info("🚀 初始化默认RAG Collections...")

        default_collections = [
            {
                "name": "general",
                "display_name": "通用知识库",
                "description": "通用知识和常见问题解答",
                "business_type": "general",
                "dimension": 768,
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "top_k": 5,
                "similarity_threshold": 0.7,
            },
            {
                "name": "testcase",
                "display_name": "测试用例知识库",
                "description": "测试用例生成和测试方法相关知识",
                "business_type": "testcase",
                "dimension": 768,
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "top_k": 5,
                "similarity_threshold": 0.7,
            },
            {
                "name": "ui_testing",
                "display_name": "UI测试知识库",
                "description": "UI自动化测试和脚本生成相关知识",
                "business_type": "ui_testing",
                "dimension": 768,
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "top_k": 5,
                "similarity_threshold": 0.7,
            },
            {
                "name": "ai_chat",
                "display_name": "AI对话知识库",
                "description": "AI对话和智能助手相关知识",
                "business_type": "ai_chat",
                "dimension": 768,
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "top_k": 5,
                "similarity_threshold": 0.7,
            },
        ]

        created_count = 0
        for collection_data in default_collections:
            try:
                # 检查是否已存在
                existing = await RAGCollection.get_or_none(name=collection_data["name"])
                if existing:
                    logger.info(f"Collection已存在: {collection_data['name']}")
                    continue

                # 创建新的Collection
                collection = await RAGCollection.create(**collection_data)
                logger.success(
                    f"✅ 创建Collection: {collection.name} - {collection.display_name}"
                )
                created_count += 1

            except Exception as e:
                logger.error(f"❌ 创建Collection失败 {collection_data['name']}: {e}")

        logger.success(f"🎉 默认Collections初始化完成，新创建 {created_count} 个")
        return created_count

    async def get_all_collections(self) -> List[Dict]:
        """获取所有Collections"""
        try:
            collections = await RAGCollection.all().order_by("created_at")
            result = []

            for collection in collections:
                # 获取文档数量
                doc_count = await RAGDocument.filter(collection=collection).count()

                result.append(
                    {
                        "id": collection.id,
                        "name": collection.name,
                        "display_name": collection.display_name,
                        "description": collection.description,
                        "business_type": collection.business_type,
                        "dimension": collection.dimension,
                        "chunk_size": collection.chunk_size,
                        "chunk_overlap": collection.chunk_overlap,
                        "top_k": collection.top_k,
                        "similarity_threshold": collection.similarity_threshold,
                        "is_active": collection.is_active,
                        "document_count": doc_count,
                        "last_updated": collection.last_updated.isoformat(),
                        "created_at": collection.created_at.isoformat(),
                        "metadata": collection.metadata,
                    }
                )

            logger.info(f"📋 获取到 {len(result)} 个Collections")
            return result

        except Exception as e:
            logger.error(f"❌ 获取Collections失败: {e}")
            return []

    async def get_collection_names(self) -> List[str]:
        """获取所有激活的Collection名称"""
        try:
            collections = await RAGCollection.filter(is_active=True).all()
            names = [collection.name for collection in collections]
            logger.info(f"📋 获取到 {len(names)} 个激活的Collection名称: {names}")
            return names
        except Exception as e:
            logger.error(f"❌ 获取Collection名称失败: {e}")
            return []

    async def get_collection_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取Collection"""
        try:
            collection = await RAGCollection.get_or_none(name=name)
            if not collection:
                return None

            # 获取文档数量
            doc_count = await RAGDocument.filter(collection=collection).count()

            return {
                "id": collection.id,
                "name": collection.name,
                "display_name": collection.display_name,
                "description": collection.description,
                "business_type": collection.business_type,
                "dimension": collection.dimension,
                "chunk_size": collection.chunk_size,
                "chunk_overlap": collection.chunk_overlap,
                "top_k": collection.top_k,
                "similarity_threshold": collection.similarity_threshold,
                "is_active": collection.is_active,
                "document_count": doc_count,
                "last_updated": collection.last_updated.isoformat(),
                "created_at": collection.created_at.isoformat(),
                "metadata": collection.metadata,
            }

        except Exception as e:
            logger.error(f"❌ 获取Collection失败 {name}: {e}")
            return None

    async def create_collection(self, collection_data: Dict) -> Dict:
        """创建新的Collection，包括数据库记录和向量数据库collection"""
        try:
            # 检查名称是否已存在
            existing = await RAGCollection.get_or_none(name=collection_data["name"])
            if existing:
                return {
                    "success": False,
                    "message": f"Collection名称 '{collection_data['name']}' 已存在",
                }

            # 1. 先在数据库中创建记录
            collection = await RAGCollection.create(**collection_data)
            logger.success(f"✅ 数据库Collection记录创建成功: {collection.name}")

            # 2. 在向量数据库中创建实际的collection
            try:
                await self._create_vector_collection(collection)
                logger.success(f"✅ 向量数据库Collection创建成功: {collection.name}")
            except Exception as vector_error:
                # 如果向量数据库创建失败，删除数据库记录
                await collection.delete()
                logger.error(
                    f"❌ 向量数据库Collection创建失败，已回滚数据库记录: {vector_error}"
                )
                return {
                    "success": False,
                    "message": f"向量数据库创建失败: {str(vector_error)}",
                }

            return {
                "success": True,
                "message": "Collection创建成功",
                "collection": {
                    "id": collection.id,
                    "name": collection.name,
                    "display_name": collection.display_name,
                    "description": collection.description,
                    "business_type": collection.business_type,
                },
            }

        except IntegrityError as e:
            logger.error(f"❌ Collection名称重复: {e}")
            return {"success": False, "message": "Collection名称已存在"}
        except Exception as e:
            logger.error(f"❌ 创建Collection失败: {e}")
            return {"success": False, "message": f"创建失败: {str(e)}"}

    async def _create_vector_collection(self, collection: RAGCollection):
        """在向量数据库中创建collection"""
        logger.info(f"🚀 开始在向量数据库中创建Collection: {collection.name}")

        try:
            # 创建CollectionConfig
            collection_config = CollectionConfig(
                name=collection.name,
                description=collection.description,
                dimension=collection.dimension,
                business_type=collection.business_type,
                top_k=collection.top_k,
                similarity_threshold=collection.similarity_threshold,
                chunk_size=collection.chunk_size,
                chunk_overlap=collection.chunk_overlap,
            )

            # 获取RAG配置
            rag_config = get_rag_config()

            # 动态添加到配置中
            rag_config.milvus.collections[collection.name] = collection_config

            # 创建collection manager并初始化新的collection
            manager = await create_collection_manager(rag_config)
            await manager.create_collection(collection.name, overwrite=False)

            logger.success(f"✅ 向量数据库Collection创建完成: {collection.name}")

        except Exception as e:
            logger.error(f"❌ 向量数据库Collection创建失败: {collection.name}: {e}")
            raise

    async def _delete_vector_collection(self, collection: RAGCollection):
        """在向量数据库中删除collection"""
        logger.info(f"🗑️ 开始在向量数据库中删除Collection: {collection.name}")

        try:
            # 获取RAG配置
            rag_config = get_rag_config()

            # 创建collection manager并删除collection
            manager = await create_collection_manager(rag_config)
            await manager.delete_collection(collection.name)

            # 从配置中移除collection配置
            if collection.name in rag_config.milvus.collections:
                del rag_config.milvus.collections[collection.name]

            logger.success(f"✅ 向量数据库Collection删除完成: {collection.name}")

        except Exception as e:
            logger.error(f"❌ 向量数据库Collection删除失败: {collection.name}: {e}")
            raise

    async def _update_vector_collection_config(self, collection: RAGCollection):
        """更新向量数据库中的collection配置"""
        logger.info(f"🔄 开始更新向量数据库Collection配置: {collection.name}")

        try:
            # 创建新的CollectionConfig
            collection_config = CollectionConfig(
                name=collection.name,
                description=collection.description,
                dimension=collection.dimension,
                business_type=collection.business_type,
                top_k=collection.top_k,
                similarity_threshold=collection.similarity_threshold,
                chunk_size=collection.chunk_size,
                chunk_overlap=collection.chunk_overlap,
            )

            # 获取RAG配置并更新
            rag_config = get_rag_config()
            rag_config.milvus.collections[collection.name] = collection_config

            logger.success(f"✅ 向量数据库Collection配置更新完成: {collection.name}")

        except Exception as e:
            logger.error(f"❌ 向量数据库Collection配置更新失败: {collection.name}: {e}")
            raise

    async def update_collection(self, name: str, update_data: Dict) -> Dict:
        """更新Collection，包括数据库记录和向量数据库配置"""
        try:
            collection = await RAGCollection.get_or_none(name=name)
            if not collection:
                return {"success": False, "message": f"Collection '{name}' 不存在"}

            # 1. 更新数据库记录
            for field, value in update_data.items():
                if hasattr(collection, field) and field != "name":  # 不允许修改name
                    setattr(collection, field, value)

            await collection.save()
            logger.success(f"✅ 数据库Collection记录更新成功: {collection.name}")

            # 2. 更新向量数据库配置
            try:
                await self._update_vector_collection_config(collection)
                logger.success(
                    f"✅ 向量数据库Collection配置更新成功: {collection.name}"
                )
            except Exception as vector_error:
                logger.error(f"❌ 向量数据库配置更新失败: {vector_error}")
                # 向量数据库配置更新失败不回滚数据库更新，但记录警告
                logger.warning(
                    f"⚠️ 向量数据库配置更新失败，数据库记录已更新: {collection.name}"
                )

            return {"success": True, "message": "Collection更新成功"}

        except Exception as e:
            logger.error(f"❌ 更新Collection失败 {name}: {e}")
            return {"success": False, "message": f"更新失败: {str(e)}"}

    async def delete_collection(self, name: str) -> Dict:
        """删除Collection，包括数据库记录和向量数据库collection"""
        try:
            collection = await RAGCollection.get_or_none(name=name)
            if not collection:
                return {"success": False, "message": f"Collection '{name}' 不存在"}

            # 1. 先删除向量数据库中的collection
            try:
                await self._delete_vector_collection(collection)
                logger.success(f"✅ 向量数据库Collection删除成功: {collection.name}")
            except Exception as vector_error:
                logger.error(f"❌ 向量数据库Collection删除失败: {vector_error}")
                # 向量数据库删除失败不阻止数据库记录删除，但记录警告
                logger.warning(
                    f"⚠️ 向量数据库删除失败，继续删除数据库记录: {collection.name}"
                )

            # 2. 删除相关文档
            doc_count = await RAGDocument.filter(collection=collection).count()
            await RAGDocument.filter(collection=collection).delete()

            # 3. 删除数据库中的Collection记录
            await collection.delete()
            logger.success(
                f"✅ 删除Collection成功: {name}，同时删除了 {doc_count} 个文档"
            )

            return {
                "success": True,
                "message": f"Collection删除成功，同时删除了 {doc_count} 个相关文档",
            }

        except Exception as e:
            logger.error(f"❌ 删除Collection失败 {name}: {e}")
            return {"success": False, "message": f"删除失败: {str(e)}"}

    async def update_document_count(self, collection_name: str, count: int):
        """更新Collection的文档数量"""
        try:
            collection = await RAGCollection.get_or_none(name=collection_name)
            if collection:
                collection.document_count = count
                await collection.save()
                logger.info(f"📊 更新Collection文档数量: {collection_name} -> {count}")
        except Exception as e:
            logger.error(f"❌ 更新文档数量失败 {collection_name}: {e}")


# 创建全局实例
collection_service = RAGCollectionService()
