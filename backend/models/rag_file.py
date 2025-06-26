"""
RAG文件记录模型 - 简化版本
"""

from datetime import datetime
from typing import Optional

from tortoise import fields
from tortoise.models import Model


class RAGFileRecord(Model):
    """RAG文件上传记录表 - 核心功能：记录文件MD5和collection，避免重复上传"""

    id = fields.IntField(pk=True)

    # 核心字段：文件MD5和collection
    file_md5 = fields.CharField(max_length=32, description="文件MD5哈希值")
    collection_name = fields.CharField(max_length=100, description="所属知识库集合")

    # 基本信息
    filename = fields.CharField(max_length=255, description="原始文件名")
    file_size = fields.BigIntField(description="文件大小(字节)")

    # 时间戳
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    # 可选的额外信息
    user_id = fields.CharField(max_length=100, null=True, description="上传用户ID")
    status = fields.CharField(max_length=20, default="completed", description="状态")

    class Meta:
        table = "rag_file_records"
        # 联合唯一索引：同一个文件(MD5)在同一个collection中只能存在一次
        unique_together = [("file_md5", "collection_name")]
        indexes = [
            ("file_md5",),
            ("collection_name",),
            ("created_at",),
        ]

    def __str__(self):
        return f"RAGFileRecord(filename={self.filename}, md5={self.file_md5[:8]}..., collection={self.collection_name})"

    @property
    def size_mb(self) -> float:
        """文件大小(MB)"""
        return round(self.file_size / (1024 * 1024), 2)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "filename": self.filename,
            "file_size": self.file_size,
            "size_mb": self.size_mb,
            "file_md5": self.file_md5,
            "collection_name": self.collection_name,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    async def is_file_exists_in_collection(
        cls, file_md5: str, collection_name: str
    ) -> bool:
        """检查文件是否已经在指定collection中存在"""
        record = await cls.filter(
            file_md5=file_md5, collection_name=collection_name
        ).first()
        return record is not None

    @classmethod
    async def get_existing_record(
        cls, file_md5: str, collection_name: str
    ) -> Optional["RAGFileRecord"]:
        """获取已存在的文件记录"""
        return await cls.filter(
            file_md5=file_md5, collection_name=collection_name
        ).first()

    @classmethod
    async def create_record(
        cls,
        filename: str,
        file_md5: str,
        file_size: int,
        collection_name: str,
        user_id: Optional[str] = None,
    ) -> "RAGFileRecord":
        """创建新的文件记录"""
        return await cls.create(
            filename=filename,
            file_md5=file_md5,
            file_size=file_size,
            collection_name=collection_name,
            user_id=user_id,
            status="completed",
        )
