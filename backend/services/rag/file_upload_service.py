"""
RAG文件上传服务 - 简化版本
核心功能：MD5重复检测，避免重复上传到同一个collection
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from backend.models.rag_file import RAGFileRecord


class RAGFileUploadService:
    """RAG文件上传服务 - 专注于重复检测"""

    def __init__(self):
        self.logger = logger.bind(service="RAGFileUploadService")

    def calculate_file_md5(self, content: bytes) -> str:
        """计算文件内容的MD5哈希值"""
        try:
            return hashlib.md5(content).hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件MD5失败: {e}")
            raise

    async def check_file_exists(
        self, file_md5: str, collection_name: str
    ) -> Optional[RAGFileRecord]:
        """
        检查文件是否已经在指定collection中存在

        Args:
            file_md5: 文件MD5哈希值
            collection_name: 集合名称

        Returns:
            RAGFileRecord: 如果文件已存在，返回记录；否则返回None
        """
        try:
            existing_record = await RAGFileRecord.get_existing_record(
                file_md5, collection_name
            )
            if existing_record:
                self.logger.info(
                    f"文件已存在 | MD5: {file_md5[:8]}... | Collection: {collection_name} | 原文件: {existing_record.filename}"
                )
            return existing_record
        except Exception as e:
            self.logger.error(f"检查文件是否存在失败: {e}")
            return None

    async def record_uploaded_file(
        self,
        filename: str,
        file_md5: str,
        file_size: int,
        collection_name: str,
        user_id: Optional[str] = None,
    ) -> RAGFileRecord:
        """
        记录已上传的文件信息

        Args:
            filename: 文件名
            file_md5: 文件MD5哈希值
            file_size: 文件大小
            collection_name: 集合名称
            user_id: 用户ID（可选）

        Returns:
            RAGFileRecord: 创建的文件记录
        """
        try:
            record = await RAGFileRecord.create_record(
                filename=filename,
                file_md5=file_md5,
                file_size=file_size,
                collection_name=collection_name,
                user_id=user_id,
            )

            self.logger.success(
                f"记录文件上传 | 文件: {filename} | MD5: {file_md5[:8]}... | Collection: {collection_name}"
            )
            return record

        except Exception as e:
            self.logger.error(f"记录文件上传失败: {e}")
            raise

    async def process_file_upload(
        self,
        filename: str,
        content: bytes,
        collection_name: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理文件上传的完整流程

        Args:
            filename: 文件名
            content: 文件内容
            collection_name: 集合名称
            user_id: 用户ID（可选）

        Returns:
            Dict: 处理结果
        """
        try:
            # 1. 计算文件MD5
            file_md5 = self.calculate_file_md5(content)
            file_size = len(content)

            self.logger.info(
                f"处理文件上传 | 文件: {filename} | 大小: {file_size} bytes | MD5: {file_md5[:8]}... | Collection: {collection_name}"
            )

            # 2. 检查文件是否已存在
            existing_record = await self.check_file_exists(file_md5, collection_name)

            if existing_record:
                # 文件已存在，返回重复信息
                return {
                    "success": False,
                    "status": "duplicate",
                    "message": f"文件已存在于 {collection_name} 知识库中",
                    "existing_file": existing_record.filename,
                    "existing_record": existing_record.to_dict(),
                    "skip_upload": True,
                }

            # 3. 文件不存在，可以上传
            return {
                "success": True,
                "status": "new_file",
                "message": "文件可以上传",
                "file_md5": file_md5,
                "file_size": file_size,
                "skip_upload": False,
            }

        except Exception as e:
            self.logger.error(f"处理文件上传失败: {filename} | 错误: {e}")
            return {
                "success": False,
                "status": "error",
                "message": f"处理失败: {str(e)}",
                "skip_upload": True,
            }

    async def complete_file_upload(
        self,
        filename: str,
        file_md5: str,
        file_size: int,
        collection_name: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        完成文件上传，记录到数据库

        Args:
            filename: 文件名
            file_md5: 文件MD5哈希值
            file_size: 文件大小
            collection_name: 集合名称
            user_id: 用户ID（可选）

        Returns:
            Dict: 完成结果
        """
        try:
            # 记录文件上传信息
            record = await self.record_uploaded_file(
                filename=filename,
                file_md5=file_md5,
                file_size=file_size,
                collection_name=collection_name,
                user_id=user_id,
            )

            return {
                "success": True,
                "message": "文件上传记录已保存",
                "record": record.to_dict(),
            }

        except Exception as e:
            self.logger.error(f"完成文件上传失败: {filename} | 错误: {e}")
            return {"success": False, "message": f"保存上传记录失败: {str(e)}"}

    async def get_collection_files(self, collection_name: str) -> Dict[str, Any]:
        """
        获取指定collection中的所有文件

        Args:
            collection_name: 集合名称

        Returns:
            Dict: 文件列表和统计信息
        """
        try:
            records = await RAGFileRecord.filter(
                collection_name=collection_name
            ).order_by("-created_at")

            files = [record.to_dict() for record in records]
            total_size = sum(record.file_size for record in records)

            return {
                "success": True,
                "collection_name": collection_name,
                "file_count": len(files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "files": files,
            }

        except Exception as e:
            self.logger.error(
                f"获取collection文件列表失败: {collection_name} | 错误: {e}"
            )
            return {"success": False, "message": f"获取文件列表失败: {str(e)}"}

    async def delete_document_record(self, record_id: int, user_id: str) -> bool:
        """
        删除文档记录（仅允许用户删除自己的文档或管理员删除）

        Args:
            record_id: 记录ID
            user_id: 用户ID

        Returns:
            bool: 是否删除成功
        """
        try:
            # 查找记录
            record = await RAGFileRecord.filter(id=record_id).first()
            if not record:
                self.logger.warning(f"文档记录不存在: ID={record_id}")
                return False

            # 检查权限（用户只能删除自己的文档，或者是管理员）
            if record.user_id != user_id and user_id != "admin":
                self.logger.warning(
                    f"无权限删除文档: ID={record_id}, user_id={user_id}, owner={record.user_id}"
                )
                return False

            # 删除记录
            await record.delete()

            self.logger.info(
                f"删除文档记录成功: ID={record_id}, filename={record.filename}"
            )
            return True

        except Exception as e:
            self.logger.error(f"删除文档记录失败: ID={record_id} | 错误: {e}")
            return False

    async def get_document_statistics(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取文档统计信息

        Args:
            user_id: 用户ID（可选，如果提供则只统计该用户的文档）

        Returns:
            Dict: 统计信息
        """
        try:
            query = RAGFileRecord.all()
            if user_id:
                query = RAGFileRecord.filter(user_id=user_id)

            total_count = await query.count()
            completed_count = await query.filter(status="completed").count()

            # 按集合统计
            collections = await RAGFileRecord.all().values_list(
                "collection_name", flat=True
            )
            collection_stats = {}
            for collection in set(collections):
                count = await RAGFileRecord.filter(collection_name=collection).count()
                collection_stats[collection] = count

            # 计算总文件大小
            records = await query.all()
            total_size = sum(record.file_size for record in records)

            stats = {
                "total_documents": total_count,
                "completed_documents": completed_count,
                "collection_stats": collection_stats,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "success_rate": (
                    round(completed_count / total_count * 100, 2)
                    if total_count > 0
                    else 0
                ),
            }

            self.logger.info(f"文档统计: {stats}")
            return stats

        except Exception as e:
            self.logger.error(f"获取文档统计失败: {e}")
            return {}


# 全局实例
rag_file_upload_service = RAGFileUploadService()
