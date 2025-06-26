"""
文档处理服务 - 迁移自examples/document_service.py
基于marker组件实现的文件到markdown转换器
支持多种文件格式，提供高质量的markdown输出
"""

import base64
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile
from loguru import logger

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.conf.file_extractor_config import MarkerConfig
from backend.services.document.file_processor import FileProcessor


def serialize_for_json(obj):
    """
    自定义JSON序列化函数，处理不能直接序列化的对象
    """
    if hasattr(obj, "__dict__"):
        # 对于有__dict__属性的对象，尝试序列化其属性
        try:
            return obj.__dict__
        except:
            return str(obj)
    elif hasattr(obj, "tobytes"):
        # 对于图像对象，转换为base64字符串
        try:
            return {
                "type": "image_bytes",
                "data": base64.b64encode(obj.tobytes()).decode("utf-8"),
                "format": getattr(obj, "format", "unknown"),
            }
        except:
            return str(obj)
    elif hasattr(obj, "save"):
        # 对于PIL Image对象
        try:
            import io

            buffer = io.BytesIO()
            obj.save(buffer, format="PNG")
            return {
                "type": "pil_image",
                "data": base64.b64encode(buffer.getvalue()).decode("utf-8"),
                "size": getattr(obj, "size", None),
                "mode": getattr(obj, "mode", None),
            }
        except:
            return str(obj)
    elif isinstance(obj, bytes):
        # 对于字节数据，转换为base64
        return {"type": "bytes", "data": base64.b64encode(obj).decode("utf-8")}
    else:
        # 其他情况，转换为字符串
        return str(obj)


def safe_json_dump(data, file_handle, **kwargs):
    """
    安全的JSON序列化，处理不能序列化的对象
    """

    def default_serializer(obj):
        return serialize_for_json(obj)

    return json.dump(data, file_handle, default=default_serializer, **kwargs)


class DocumentService:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

        # 创建文件存储目录
        self.files_db_dir = self.upload_dir / "files_db"
        self.files_db_dir.mkdir(exist_ok=True)

        # 内存中的文件存储（生产环境应使用数据库）
        self.uploaded_files: Dict[str, Dict[str, Any]] = {}
        self.session_files: Dict[str, List[str]] = {}  # session_id -> [file_ids]

        # 文件解析缓存 - 基于文件内容哈希
        self.file_cache: Dict[str, Dict[str, Any]] = {}  # file_hash -> parsed_content

        # 创建marker配置
        self.config = MarkerConfig(
            output_format="markdown",
            use_llm=self._should_use_llm(),
            format_lines=True,
            enable_image_description=True,  # 启用图片描述功能
            disable_image_extraction=self._should_use_llm(),  # 使用LLM时启用图片描述
            max_file_size=50 * 1024 * 1024,  # 50MB
            qwen_api_key=os.getenv("QWEN_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            # 使用支持视觉的模型
            openai_model="gpt-4o" if os.getenv("OPENAI_API_KEY") else "gpt-4o-mini",
            qwen_model="qwen-vl-max-latest",
        )

        # 创建文件处理器
        self.file_processor = FileProcessor(config=self.config, upload_dir=upload_dir)

        # 加载已存在的文件信息
        self._load_files_db()

    def _should_use_llm(self) -> bool:
        """检查是否应该使用LLM"""
        return bool(os.getenv("QWEN_API_KEY") or os.getenv("OPENAI_API_KEY"))

    def _calculate_file_hash(self, file_content: bytes) -> str:
        """计算文件内容的哈希值"""
        return hashlib.md5(file_content).hexdigest()

    def _get_cached_content(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """获取缓存的文件内容"""
        return self.file_cache.get(file_hash)

    def _cache_file_content(
        self,
        file_hash: str,
        filename: str,
        content: str,
        markdown_content: Dict[str, Any],
    ) -> None:
        """缓存文件内容"""
        cache_entry = {
            "filename": filename,
            "content": content,
            "markdown_content": markdown_content,
            "cached_time": datetime.now().isoformat(),
            "file_hash": file_hash,
        }
        self.file_cache[file_hash] = cache_entry

        # 限制缓存大小（保留最近的100个文件）
        if len(self.file_cache) > 100:
            # 删除最旧的缓存项
            oldest_hash = min(
                self.file_cache.keys(),
                key=lambda h: self.file_cache[h].get("cached_time", ""),
            )
            del self.file_cache[oldest_hash]

    def _load_files_db(self):
        """加载文件数据库"""
        db_file = self.files_db_dir / "files.json"
        if db_file.exists():
            try:
                with open(db_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.uploaded_files = data.get("uploaded_files", {})
                    self.session_files = data.get("session_files", {})
                    self.file_cache = data.get("file_cache", {})
            except Exception as e:
                logger.warning(f"加载文件数据库失败: {e}")

        # 加载文件缓存
        cache_file = self.files_db_dir / "file_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    self.file_cache = json.load(f)
            except Exception as e:
                logger.warning(f"加载文件缓存失败: {e}")

    def _save_files_db(self):
        """保存文件数据库"""
        logger.debug("💾 开始保存文件数据库...")

        db_file = self.files_db_dir / "files.json"
        try:
            logger.debug(f"📁 保存主数据库到: {db_file}")
            with open(db_file, "w", encoding="utf-8") as f:
                safe_json_dump(
                    {
                        "uploaded_files": self.uploaded_files,
                        "session_files": self.session_files,
                        "file_cache": self.file_cache,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.debug("✅ 主数据库保存成功")
        except Exception as e:
            logger.error(f"❌ 保存文件数据库失败: {e}")

        # 单独保存文件缓存（避免主数据库过大）
        cache_file = self.files_db_dir / "file_cache.json"
        try:
            logger.debug(f"📁 保存缓存数据库到: {cache_file}")
            with open(cache_file, "w", encoding="utf-8") as f:
                safe_json_dump(self.file_cache, f, ensure_ascii=False, indent=2)
            logger.debug("✅ 缓存数据库保存成功")
        except Exception as e:
            logger.error(f"❌ 保存文件缓存失败: {e}")

    async def save_and_extract_file(
        self, file: UploadFile, session_id: str = "default"
    ) -> Dict[str, Any]:
        """保存文件并使用marker提取内容，返回文件ID"""
        try:
            # 读取文件内容计算哈希
            file_content = await file.read()
            file_hash = self._calculate_file_hash(file_content)

            # 重置文件指针
            await file.seek(0)

            # 检查缓存
            cached_content = self._get_cached_content(file_hash)

            if cached_content:
                logger.info(f"✅ 文件已解析过，使用缓存: {file.filename}")

                # 使用缓存的内容
                plain_text = cached_content["content"]
                markdown_content_data = cached_content["markdown_content"]

                # 生成文件ID
                file_id = str(uuid.uuid4())

                # 仍需保存物理文件（用于后续可能的需求）
                file_extension = Path(file.filename).suffix.lower()
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                file_path = self.upload_dir / unique_filename

                with open(file_path, "wb") as f:
                    f.write(file_content)

                result = {
                    "filename": file.filename,
                    "saved_filename": unique_filename,
                    "file_path": str(file_path),
                    "file_size": len(file_content),
                    "file_type": file_extension,
                    "markdown_content": markdown_content_data,
                    "processing_config": {"cached": True},
                }
            else:
                logger.info(f"🔄 首次解析文件: {file.filename}")

                # 使用新的文件处理器处理上传文件
                result = await self.file_processor.process_upload_file(file)

                # 生成文件ID
                file_id = str(uuid.uuid4())

                # 提取markdown内容中的纯文本用于聊天
                markdown_content_data = result["markdown_content"]
                plain_text = markdown_content_data.get("plain_text", "")

                # 缓存解析结果
                self._cache_file_content(
                    file_hash, file.filename, plain_text, markdown_content_data
                )

            # 存储文件信息
            file_info = {
                "file_id": file_id,
                "filename": result["filename"],
                "saved_filename": result["saved_filename"],
                "file_path": result["file_path"],
                "content": plain_text,  # 用于聊天的纯文本内容
                "file_size": result["file_size"],
                "file_type": result["file_type"],
                "markdown_content": result["markdown_content"],
                "processing_config": result.get("processing_config", {}),
                "upload_time": datetime.now().isoformat(),
                "session_id": session_id,
            }

            # 保存到内存存储
            self.uploaded_files[file_id] = file_info

            # 关联到会话
            if session_id not in self.session_files:
                self.session_files[session_id] = []
            self.session_files[session_id].append(file_id)

            # 持久化存储
            self._save_files_db()

            # 返回文件ID和基本信息（不包含内容）
            return {
                "file_id": file_id,
                "filename": result["filename"],
                "file_size": result["file_size"],
                "file_type": result["file_type"],
                "upload_time": file_info["upload_time"],
                "statistics": {
                    "total_characters": markdown_content_data["statistics"][
                        "total_characters"
                    ],
                    "total_words": markdown_content_data["statistics"]["total_words"],
                    "tables_count": markdown_content_data["statistics"]["tables_count"],
                    "images_count": markdown_content_data["statistics"]["images_count"],
                    "headers_count": markdown_content_data["statistics"][
                        "headers_count"
                    ],
                },
                "processing_info": {
                    "llm_enabled": result.get("processing_config", {}).get(
                        "use_llm", False
                    ),
                    "format_enhanced": result.get("processing_config", {}).get(
                        "format_lines", False
                    ),
                },
            }

        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")

    def get_file_content(self, file_id: str) -> Optional[str]:
        """根据文件ID获取文件内容"""
        if file_id in self.uploaded_files:
            return self.uploaded_files[file_id]["content"]
        return None

    def get_file_info_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """根据文件ID获取文件信息"""
        return self.uploaded_files.get(file_id)

    def get_session_files(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话关联的所有文件"""
        file_ids = self.session_files.get(session_id, [])
        files = []
        for file_id in file_ids:
            if file_id in self.uploaded_files:
                file_info = self.uploaded_files[file_id].copy()
                # 不返回完整内容，只返回基本信息
                file_info.pop("content", None)
                file_info.pop("markdown_content", None)
                files.append(file_info)
        return files

    def get_session_content(self, session_id: str) -> str:
        """获取会话所有文件的合并内容"""
        file_ids = self.session_files.get(session_id, [])
        contents = []

        for file_id in file_ids:
            if file_id in self.uploaded_files:
                file_info = self.uploaded_files[file_id]
                content = file_info["content"]
                filename = file_info["filename"]
                contents.append(f"=== 文件: {filename} ===\n{content}\n")

        return "\n".join(contents)

    def get_supported_formats(self) -> Dict[str, Any]:
        """获取支持的文件格式"""
        return {
            "supported_formats": self.file_processor.get_supported_formats(),
            "max_file_size_mb": self.config.max_file_size / 1024 / 1024,
            "llm_enabled": self.config.use_llm,
        }

    async def parse_file_content(
        self, content: bytes, filename: str, file_type: str
    ) -> str:
        """
        解析文件内容，提取文本

        Args:
            content: 文件二进制内容
            filename: 文件名
            file_type: 文件类型（扩展名）

        Returns:
            str: 解析后的文本内容
        """
        try:
            # 创建临时文件
            import tempfile

            with tempfile.NamedTemporaryFile(
                suffix=file_type, delete=False
            ) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # 使用文件处理器解析内容
                result = await self.file_processor.process_file(
                    temp_file_path, filename
                )

                if result.get("success", False):
                    return result.get("content", "")
                else:
                    # 如果处理失败，尝试简单的文本解码
                    if file_type.lower() in [
                        ".txt",
                        ".md",
                        ".py",
                        ".js",
                        ".html",
                        ".css",
                        ".json",
                        ".xml",
                    ]:
                        try:
                            return content.decode("utf-8")
                        except UnicodeDecodeError:
                            try:
                                return content.decode("gbk")
                            except UnicodeDecodeError:
                                return content.decode("latin-1")
                    else:
                        return f"无法解析文件类型: {file_type}"

            finally:
                # 清理临时文件
                Path(temp_file_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"解析文件内容失败: {filename} | 错误: {e}")
            # 尝试简单的文本解码作为后备方案
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return f"文件解析失败: {str(e)}"


# 创建全局文档服务实例
document_service = DocumentService()
