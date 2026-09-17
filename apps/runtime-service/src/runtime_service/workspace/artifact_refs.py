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
        extensions = "|".join(sorted(ARTIFACT_MIMES))
        match = re.fullmatch(rf"/workspace/outputs/([0-9a-f]{{64}})\.({extensions})", path)
        if match is None:
            raise DocumentError("invalid_artifact_ref")
        try:
            data = self.io.read(path)
        except ToolException as exc:
            raise DocumentError("artifact_not_found", 404) from exc
        # Shell can mutate the backing directory: verify both digest and format on read.
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        digest = hashlib.sha256(data).hexdigest()
        if digest != match[1]:
            raise DocumentError("artifact_hash_mismatch", 409)
        validate_artifact(data, match[2])
        return data, {"version": 1, "artifact_id": digest, "path": path,
                      "file_name": digest + "." + match[2], "mime_type": ARTIFACT_MIMES[match[2]],
                      "size_bytes": len(data), "sha256": digest,
                      "preview_kind": preview_kind(ARTIFACT_MIMES[match[2]]),
                      "kind": "media" if match[2] in MEDIA_MIMES else "archive" if match[2] == "zip" else "text"}

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

    def list_artifacts(self, *, cursor: str | None = None, limit: int = 100) -> dict:
        from runtime_service.workspace.browser import WorkspaceBrowser
        page = WorkspaceBrowser(self.io.root).list_directory("/workspace/outputs", cursor=cursor, limit=limit, artifacts_only=True)
        return {"items": [{"version": 1, "artifact_id": item.name.split(".")[0],
                           "path": item.path, "file_name": item.name, "mime_type": item.mime_type,
                           "size_bytes": item.size_bytes, "sha256": item.name.split(".")[0],
                           "preview_kind": item.preview_kind,
                           "kind": "media" if item.name.rsplit(".", 1)[-1] in MEDIA_MIMES else "archive" if item.name.endswith(".zip") else "text"}
                          for item in page.items], "next_cursor": page.next_cursor}
