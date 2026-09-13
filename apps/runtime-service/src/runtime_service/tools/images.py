"""Bounded image IO and provider calls, independent of any demo agent."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from langchain_core.tools import ToolException, tool
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from PIL import Image
from pydantic import SecretStr

from runtime_service.workspace.image_refs import (
    ASSET_MAX_BYTES,
    UPLOAD_MAX_BYTES,
    ImageRef,
    ImageRefValidationError,
    validate_image_path,
)

MAX_BYTES = ASSET_MAX_BYTES


class ImageWorkspaceError(ToolException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def image_type(data: bytes) -> tuple[str, str]:
    """Verify raster content before sending or persisting it."""
    if not data or len(data) > MAX_BYTES:
        raise ToolException("Image must be between 1 byte and 20 MiB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError("Too many pixels")
            formats = {
                "PNG": ("png", "image/png"),
                "JPEG": ("jpg", "image/jpeg"),
                "WEBP": ("webp", "image/webp"),
            }
            kind = formats[image.format or ""]
            image.verify()
            return kind
    except (OSError, ValueError, KeyError, Image.DecompressionBombError):
        raise ToolException(
            "Use a valid PNG, JPEG or WebP with at most 25 million pixels."
        ) from None


class ImageWorkspace:
    """A trusted thread root; all filesystem access rejects symlink traversal."""

    def __init__(self, root: Path | None):
        self.root = root

    def _directory(self, parts: tuple[str, ...], *, create: bool = False) -> int:
        if self.root is None:
            raise ToolException("Workspace is unavailable for schema-only graphs.")
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in (*self.root.absolute().parts[1:], *parts):
                if part in ("", ".", ".."):
                    raise ValueError("Invalid path")
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
            return descriptor
        except (OSError, ValueError):
            os.close(descriptor)
            raise ToolException("Workspace path is unavailable or unsafe.") from None

    def read(self, path: str) -> bytes:
        parts = PurePosixPath(path).parts
        if (
            not path.startswith("/workspace/")
            or ".." in parts
            or "\\" in path
            or len(parts) < 3
        ):
            raise ToolException("Use an image path inside /workspace/.")
        directory = self._directory(parts[2:-1])
        try:
            descriptor = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError("Not a file")
                return source.read(MAX_BYTES + 1)
        except (OSError, ValueError):
            raise ToolException("Image file is unavailable or unsafe.") from None
        finally:
            os.close(directory)

    def save(self, data: bytes, folder: str) -> str:
        extension, _ = image_type(data)
        if folder not in {"generated", "charts"}:
            raise ToolException("Invalid image destination.")
        directory = self._directory((folder,), create=True)
        name = f"{uuid4().hex}.{extension}"
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "wb") as target:
                target.write(data)
        finally:
            os.close(directory)
        return f"/workspace/{folder}/{name}"

    def save_asset(self, data: bytes, folder: str) -> ImageRef:
        path = self.save(data, folder)
        _, mime = image_type(data)
        return ImageRef(
            version=1,
            path=path,
            mime_type=mime,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def put_upload(self, data: bytes, sha256: str) -> ImageRef:
        if not isinstance(sha256, str) or not re.match(r"^[0-9a-f]{64}$", sha256):
            raise ImageWorkspaceError("image_digest_mismatch", "Invalid sha256 hex digest", status_code=400)
        if len(data) > UPLOAD_MAX_BYTES:
            raise ImageWorkspaceError("image_too_large", f"Upload exceeds {UPLOAD_MAX_BYTES} bytes limit", status_code=413)
        if not data:
            raise ImageWorkspaceError("image_type_unsupported", "Empty upload payload", status_code=415)

        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != sha256.lower():
            raise ImageWorkspaceError("image_digest_mismatch", "Payload digest does not match URL sha256", status_code=400)

        try:
            ext, mime = image_type(data)
        except ToolException as exc:
            raise ImageWorkspaceError("image_type_unsupported", str(exc), status_code=415) from exc

        name = f"{sha256}.{ext}"
        directory = self._directory(("uploads",), create=True)
        tmp_name = f".tmp_{uuid4().hex}"
        try:
            # 1. 检查目标文件是否已存在 (幂等检查)
            try:
                target_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
                with os.fdopen(target_fd, "rb") as existing:
                    existing_bytes = existing.read(UPLOAD_MAX_BYTES + 1)
                    if hashlib.sha256(existing_bytes).hexdigest() == sha256:
                        return ImageRef(
                            version=1,
                            path=f"/workspace/uploads/{name}",
                            mime_type=mime,
                            size_bytes=len(existing_bytes),
                            sha256=sha256,
                        )
                    else:
                        raise ImageWorkspaceError("image_content_conflict", "Existing file corrupted or conflict", status_code=409)
            except FileNotFoundError:
                pass

            # 2. 写入临时文件
            tmp_fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(tmp_fd, "wb") as tmp_file:
                tmp_file.write(data)
                tmp_file.flush()

            # 3. 原子重命名到目标位置
            os.replace(tmp_name, name, src_dir_fd=directory, dst_dir_fd=directory)

            return ImageRef(
                version=1,
                path=f"/workspace/uploads/{name}",
                mime_type=mime,
                size_bytes=len(data),
                sha256=sha256,
            )
        except OSError as exc:
            raise ImageWorkspaceError("image_workspace_unavailable", f"I/O error during upload: {exc}", status_code=500) from exc
        finally:
            try:
                os.unlink(tmp_name, dir_fd=directory)
            except OSError:
                pass
            os.close(directory)

    def read_asset(self, path: str) -> tuple[bytes, ImageRef]:
        try:
            folder, filename = validate_image_path(path)
        except ImageRefValidationError as exc:
            raise ImageWorkspaceError("image_path_invalid", str(exc), status_code=400) from exc

        try:
            directory = self._directory((folder,))
        except ToolException:
            raise ImageWorkspaceError("image_not_found", "Image file not found", status_code=404)
        try:
            try:
                fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            except FileNotFoundError:
                raise ImageWorkspaceError("image_not_found", "Image file not found", status_code=404)
            except OSError as exc:
                raise ImageWorkspaceError("image_workspace_unavailable", "Cannot open image file", status_code=500) from exc

            with os.fdopen(fd, "rb") as f:
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode):
                    raise ImageWorkspaceError("image_path_invalid", "Target is not a regular file", status_code=400)
                if st.st_size > ASSET_MAX_BYTES:
                    raise ImageWorkspaceError("image_too_large", f"Image size exceeds {ASSET_MAX_BYTES} bytes", status_code=413)
                data = f.read(ASSET_MAX_BYTES + 1)
                if len(data) > ASSET_MAX_BYTES:
                    raise ImageWorkspaceError("image_too_large", f"Image size exceeds {ASSET_MAX_BYTES} bytes", status_code=413)

            try:
                ext, mime = image_type(data)
            except ToolException as exc:
                raise ImageWorkspaceError("image_type_unsupported", str(exc), status_code=415) from exc

            actual_sha = hashlib.sha256(data).hexdigest()
            if folder == "uploads":
                stem = filename.rsplit(".", 1)[0]
                if stem != actual_sha:
                    raise ImageWorkspaceError("image_content_conflict", "File content does not match uploads digest", status_code=409)

            ref = ImageRef(
                version=1,
                path=path,
                mime_type=mime,
                size_bytes=len(data),
                sha256=actual_sha,
            )
            return data, ref
        finally:
            os.close(directory)

    def describe(self, path: str) -> ImageRef:
        _, ref = self.read_asset(path)
        return ref


async def download_image(url: str, *, allowed_hosts: set[str]) -> bytes:
    """Only accept operator-approved asset hosts; no redirects or ambient credentials."""
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in allowed_hosts
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Unapproved asset URL")
        async with (
            httpx.AsyncClient(timeout=45, trust_env=False) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes(65536):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("Oversized image")
        image_type(bytes(data))
        return bytes(data)
    except (httpx.HTTPError, ValueError, ToolException):
        raise ToolException(
            "Image download failed; check the configured asset host and image size."
        ) from None


def setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ToolException(f"Runtime image setting {name} is missing.")
    return value


def build_image_tools(workspace: ImageWorkspace):
    async def _extract_and_save_image(
        result: Any, operation: str
    ) -> tuple[str, dict[str, Any]]:
        if not getattr(result, "data", None):
            raise ToolException("Provider returned no image.")
        item = result.data[0]
        if getattr(item, "b64_json", None):
            if len(item.b64_json) > MAX_BYTES * 4 // 3 + 4:
                raise ToolException("Generated image is too large.")
            data = base64.b64decode(item.b64_json, validate=True)
        elif getattr(item, "url", None):
            hosts = {
                host.strip()
                for host in setting("RUNTIME_IMAGE_ASSET_HOSTS").split(",")
            }
            data = await download_image(item.url, allowed_hosts=hosts)
        else:
            raise ToolException("Provider returned no image.")
        ref = await asyncio.to_thread(workspace.save_asset, data, "generated")
        return ref["path"], {"runtime_images": [ref]}

    def _handle_image_provider_error(exc: Exception, operation: str) -> ToolException:
        if isinstance(exc, ToolException):
            return exc
        error_msg = str(exc)
        body = getattr(exc, "body", None)
        code = None
        message = None
        if isinstance(body, dict):
            code = body.get("code")
            message = body.get("message")
        if code == "content_policy_violation" or "content_policy_violation" in error_msg:
            hint = f": {message}" if message else ""
            return ToolException(
                f"{operation} failed: triggered content safety policy (content_policy_violation){hint}. "
                "Please modify the prompt to avoid sensitive, school uniform, violence, or restricted words and try again."
            )
        status_code = getattr(exc, "status_code", None)
        return ToolException(
            f"{operation} failed ({type(exc).__name__}, status={status_code}); no successful artifact was returned."
        )

    @tool(response_format="content_and_artifact")
    async def generate_image(prompt: str) -> tuple[str, dict[str, Any]]:
        """Generate an image from a prompt after human approval; return its /workspace path."""
        if not prompt.strip() or len(prompt) > 8000:
            raise ToolException("Prompt must contain 1 to 8000 characters.")
        try:
            async with AsyncOpenAI(
                api_key=setting("IMAGE_25_KEY"),
                base_url=setting("IMAGE_25_URL"),
                timeout=180,
                max_retries=0,
            ) as client:
                result = await client.images.generate(
                    model=setting("IMAGE_25_MODEL"),
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
            return await _extract_and_save_image(result, "Image generation")
        except Exception as exc:
            raise _handle_image_provider_error(exc, "Image generation") from None

    @tool(response_format="content_and_artifact")
    async def edit_image(
        image_path: str, prompt: str
    ) -> tuple[str, dict[str, Any]]:
        """Edit or transform an existing image in /workspace based on prompt after human approval; return its /workspace path."""
        if not prompt.strip() or len(prompt) > 8000:
            raise ToolException("Prompt must contain 1 to 8000 characters.")
        try:
            data = await asyncio.to_thread(workspace.read, image_path)
            _, mime = image_type(data)
            ext = "png" if mime == "image/png" else ("jpg" if mime == "image/jpeg" else "webp")
            file_tuple = (f"image.{ext}", data, mime)
            async with AsyncOpenAI(
                api_key=setting("IMAGE_25_KEY"),
                base_url=setting("IMAGE_25_URL"),
                timeout=180,
                max_retries=0,
            ) as client:
                result = await client.images.edit(
                    model=setting("IMAGE_25_MODEL"),
                    image=file_tuple,
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
            return await _extract_and_save_image(result, "Image editing")
        except Exception as exc:
            raise _handle_image_provider_error(exc, "Image editing") from None

    @tool
    async def analyze_image(
        image_path: str, question: str = "Describe this image."
    ) -> str:
        """Understand a PNG/JPEG/WebP file inside /workspace using the vision model. Read-only."""
        if not question.strip() or len(question) > 8000:
            raise ToolException("Question must contain 1 to 8000 characters.")
        try:
            data = await asyncio.to_thread(workspace.read, image_path)
            _, mime = image_type(data)
            model = ChatOpenAI(
                model=setting("DOUBAO_MODEL"),
                api_key=SecretStr(setting("DOUBAO_API_KEY")),
                base_url=setting("DOUBAO_API_BASE"),
                max_completion_tokens=min(
                    int(os.getenv("DOUBAO_MAX_TOKENS", "2048")), 4096
                ),
                timeout=60,
                max_retries=0,
            )
            result = await model.ainvoke(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{base64.b64encode(data).decode()}"
                                },
                            },
                        ],
                    }
                ],
                config={"callbacks": []},
            )
            return result.text
        except ToolException:
            raise
        except Exception:  # noqa: BLE001 - do not return provider payloads to the agent
            raise ToolException(
                "Image analysis failed; check the Runtime vision configuration."
            ) from None

    for image_tool in (generate_image, edit_image, analyze_image):
        image_tool.handle_tool_error = True
    return [generate_image, edit_image, analyze_image]
