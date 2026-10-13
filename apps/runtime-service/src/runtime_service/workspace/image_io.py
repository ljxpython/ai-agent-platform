"""Descriptor-based image and workspace IO, without provider clients."""

from __future__ import annotations

import hashlib
import io
import os
import re
import stat
from pathlib import Path, PurePosixPath
from uuid import uuid4

from langchain_core.tools import ToolException
from PIL import Image

from runtime_service.errors import RuntimeWorkspaceError
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

    def _directory(
        self,
        parts: tuple[str, ...],
        *,
        create: bool = False,
        create_root: bool = False,
    ) -> int:
        if self.root is None:
            raise ToolException("Workspace is unavailable for schema-only graphs.")
        root_parts = self.root.absolute().parts[1:]
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for _index, part in enumerate((*root_parts, *parts)):
                if part in ("", ".", ".."):
                    raise ValueError("Invalid path")
                if create and (create_root or _index >= len(root_parts)):
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
        except (OSError, ValueError) as exc:
            os.close(descriptor)
            if (
                _index < len(root_parts)
                or isinstance(exc, OSError)
                and exc.errno not in (2, 20, 40)
            ):
                raise RuntimeWorkspaceError("runtime.workspace.unavailable") from exc
            raise ToolException("Workspace path is unavailable or unsafe.") from None

    def read(self, path: str) -> bytes:
        from runtime_service.workspace.target import RemoteWorkspace

        if isinstance(self.root, RemoteWorkspace):
            return self.root.call("image.read", path=path)
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
        from runtime_service.workspace.target import RemoteWorkspace

        if isinstance(self.root, RemoteWorkspace):
            return self.root.call("image.save_asset", data=data, folder=folder)
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
        from runtime_service.workspace.target import RemoteWorkspace

        if isinstance(self.root, RemoteWorkspace):
            return self.root.call("image.put_upload", data=data, sha256=sha256)
        if not isinstance(sha256, str) or not re.match(r"^[0-9a-f]{64}$", sha256):
            raise ImageWorkspaceError(
                "image_digest_mismatch", "Invalid sha256 hex digest", status_code=400
            )
        if len(data) > UPLOAD_MAX_BYTES:
            raise ImageWorkspaceError(
                "image_too_large",
                f"Upload exceeds {UPLOAD_MAX_BYTES} bytes limit",
                status_code=413,
            )
        if not data:
            raise ImageWorkspaceError(
                "image_type_unsupported", "Empty upload payload", status_code=415
            )

        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != sha256.lower():
            raise ImageWorkspaceError(
                "image_digest_mismatch",
                "Payload digest does not match URL sha256",
                status_code=400,
            )

        try:
            ext, mime = image_type(data)
        except ToolException as exc:
            raise ImageWorkspaceError(
                "image_type_unsupported", str(exc), status_code=415
            ) from exc

        name = f"{sha256}.{ext}"
        directory = self._directory(("uploads",), create=True, create_root=True)
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
                        raise ImageWorkspaceError(
                            "image_content_conflict",
                            "Existing file corrupted or conflict",
                            status_code=409,
                        )
            except FileNotFoundError:
                pass

            # 2. 写入临时文件
            tmp_fd = os.open(
                tmp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
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
            raise ImageWorkspaceError(
                "image_workspace_unavailable",
                f"I/O error during upload: {exc}",
                status_code=500,
            ) from exc
        finally:
            try:
                os.unlink(tmp_name, dir_fd=directory)
            except OSError:
                pass
            os.close(directory)

    def read_asset(self, path: str) -> tuple[bytes, ImageRef]:
        from runtime_service.workspace.target import RemoteWorkspace

        if isinstance(self.root, RemoteWorkspace):
            return tuple(self.root.call("image.read_asset", path=path))
        try:
            folder, filename = validate_image_path(path)
        except ImageRefValidationError as exc:
            raise ImageWorkspaceError(
                "image_path_invalid", str(exc), status_code=400
            ) from exc

        try:
            directory = self._directory((folder,))
        except ToolException as exc:
            raise ImageWorkspaceError(
                "image_not_found", "Image file not found", status_code=404
            ) from exc
        try:
            try:
                fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            except FileNotFoundError as exc:
                raise ImageWorkspaceError(
                    "image_not_found", "Image file not found", status_code=404
                ) from exc
            except OSError as exc:
                raise ImageWorkspaceError(
                    "image_workspace_unavailable",
                    "Cannot open image file",
                    status_code=500,
                ) from exc

            with os.fdopen(fd, "rb") as f:
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode):
                    raise ImageWorkspaceError(
                        "image_path_invalid",
                        "Target is not a regular file",
                        status_code=400,
                    )
                if st.st_size > ASSET_MAX_BYTES:
                    raise ImageWorkspaceError(
                        "image_too_large",
                        f"Image size exceeds {ASSET_MAX_BYTES} bytes",
                        status_code=413,
                    )
                data = f.read(ASSET_MAX_BYTES + 1)
                if len(data) > ASSET_MAX_BYTES:
                    raise ImageWorkspaceError(
                        "image_too_large",
                        f"Image size exceeds {ASSET_MAX_BYTES} bytes",
                        status_code=413,
                    )

            try:
                ext, mime = image_type(data)
            except ToolException as exc:
                raise ImageWorkspaceError(
                    "image_type_unsupported", str(exc), status_code=415
                ) from exc

            actual_sha = hashlib.sha256(data).hexdigest()
            if folder in {"uploads", "outputs"}:
                stem = filename.rsplit(".", 1)[0]
                if stem != actual_sha:
                    raise ImageWorkspaceError(
                        "image_content_conflict",
                        f"File content does not match {folder} digest",
                        status_code=409,
                    )

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
