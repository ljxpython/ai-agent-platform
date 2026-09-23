"""Validated immutable artifacts published from a thread workspace."""
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from langchain_core.tools import ToolException

from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.documents import DocumentError, validate_document
from runtime_service.workspace.file_refs import MAX_FILE_BYTES, MIME_EXT
from runtime_service.workspace.media import MEDIA_MIMES, validate_media

ARTIFACT_MIMES = {
    "txt": "text/plain", "md": "text/markdown", "bib": "text/x-bibtex",
    "csv": "text/csv", "json": "application/json", "yaml": "application/yaml",
    "yml": "text/yaml", "toml": "application/toml", "xml": "application/xml",
    "html": "text/html", "css": "text/css", "js": "text/javascript",
    "ts": "text/typescript", "py": "text/x-python", "sh": "text/x-shellscript",
    "sql": "application/sql", "java": "text/x-java-source", "c": "text/x-c",
    "cpp": "text/x-c++src", "rs": "text/x-rust", "zip": "application/zip",
    "jsx": "text/jsx", "tsx": "text/tsx", "vue": "text/plain", "svg": "image/svg+xml",
    "pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    **MEDIA_MIMES,
}


def validate_artifact(data, extension):
    if len(data) > MAX_FILE_BYTES:
        raise DocumentError("file_too_large", 413)
    if extension in MEDIA_MIMES:
        validate_media(data, extension)
        return
    mime = ARTIFACT_MIMES[extension]
    validate_document(data, mime if mime in MIME_EXT else "text/plain")


def preview_kind(mime: str) -> str:
    if mime in {"image/png", "image/jpeg", "image/webp"}:
        return "image"
    if mime == "text/html":
        return "html-sandbox"
    if mime == "text/markdown":
        return "markdown"
    if mime.startswith("text/") or mime in {"application/json", "application/yaml", "application/toml", "application/xml", "application/sql", "image/svg+xml"}:
        return "text"
    return "download"



class ArtifactWorkspace:
    def __init__(self, root: Path | None):
        self.io = ImageWorkspace(root)

    def read(self, path: str) -> tuple[bytes, dict]:
        if (
            not isinstance(path, str)
            or not path.startswith("/workspace/outputs/")
            or ".." in path.split("/")
            or "\\" in path
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)
        ):
            raise DocumentError("invalid_artifact_ref")
        filename = path[len("/workspace/outputs/") :]
        if "/" in filename or not filename or filename.startswith("."):
            raise DocumentError("invalid_artifact_ref")
        extension = Path(filename).suffix.lstrip(".").lower()
        if extension not in ARTIFACT_MIMES:
            raise DocumentError("invalid_artifact_ref")
        stem = filename[: -(len(extension) + 1)]
        if not stem:
            raise DocumentError("invalid_artifact_ref")
        expected_hash = stem if re.fullmatch(r"[0-9a-f]{64}", stem) else None
        try:
            data = self.io.read(path)
        except ToolException as exc:
            raise DocumentError("artifact_not_found", 404) from exc
        # Shell can mutate the backing directory: verify both digest and format on read.
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        digest = hashlib.sha256(data).hexdigest()
        if expected_hash is not None and digest != expected_hash:
            raise DocumentError("artifact_hash_mismatch", 409)
        validate_artifact(data, extension)
        return data, {
            "version": 1,
            "artifact_id": digest,
            "path": path,
            "file_name": filename,
            "mime_type": ARTIFACT_MIMES[extension],
            "size_bytes": len(data),
            "sha256": digest,
            "preview_kind": preview_kind(ARTIFACT_MIMES[extension]),
            "kind": "media" if extension in MEDIA_MIMES else "archive" if extension == "zip" else "text",
        }

    def publish(self, path: str) -> dict:
        if not path.startswith(("/workspace/work/", "/workspace/generated/", "/workspace/charts/")) or ".." in path.split("/") or "\\" in path or any(ord(ch) < 32 for ch in path):
            raise DocumentError("artifact_source_denied")
        extension = Path(path).suffix.lstrip(".").lower()
        if extension not in ARTIFACT_MIMES:
            raise DocumentError("unsupported_artifact_type", 415)
        try:
            data = self.io.read(path)
        except ToolException as exc:
            raise DocumentError("artifact_source_unavailable", 404) from exc
        validate_artifact(data, extension)
        digest = hashlib.sha256(data).hexdigest()
        filename = digest + "." + extension
        directory = self.io._directory(("outputs",), create=True)
        temporary = ".publish-" + uuid4().hex
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as target:
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory,
                        follow_symlinks=False)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary, dir_fd=directory)
            os.close(directory)
        _, ref = self.read("/workspace/outputs/" + filename)
        return ref

    def _resolve_entry_sha256(self, item) -> str:
        stem = Path(item.name).stem
        if re.fullmatch(r"[0-9a-f]{64}", stem):
            return stem
        try:
            return hashlib.sha256(self.io.read(item.path)).hexdigest()
        except Exception:
            return hashlib.sha256(item.name.encode("utf-8")).hexdigest()

    def list_artifacts(self, *, cursor: str | None = None, limit: int = 100) -> dict:
        from runtime_service.workspace.browser import WorkspaceBrowser
        page = WorkspaceBrowser(self.io.root).list_directory("/workspace/outputs", cursor=cursor, limit=limit, artifacts_only=True)
        items = []
        for item in page.items:
            digest = self._resolve_entry_sha256(item)
            ext = item.name.rsplit(".", 1)[-1].lower() if "." in item.name else ""
            items.append({
                "version": 1,
                "artifact_id": digest,
                "path": item.path,
                "file_name": item.name,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "sha256": digest,
                "preview_kind": item.preview_kind,
                "kind": "media" if ext in MEDIA_MIMES else "archive" if ext == "zip" else "text",
            })
        return {"items": items, "next_cursor": page.next_cursor}
