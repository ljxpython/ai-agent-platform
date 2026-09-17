"""Read-only, bounded access to a trusted thread workspace."""

import base64
import binascii
import codecs
import hashlib
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.tools import ToolException

from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.artifact_refs import (
    ARTIFACT_MIMES,
    ArtifactWorkspace,
    preview_kind,
)
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.file_refs import MAX_FILE_BYTES
from runtime_service.workspace.media import validate_media
from runtime_service.workspace.schemas import WorkspaceEntry, WorkspacePage

PREVIEW_BYTES = 256 * 1024
MAX_DIRECTORY_ENTRIES = 10000


def path_parts(path: str) -> tuple[str, ...]:
    if (
        not isinstance(path, str)
        or len(path) > 4096
        or "\\" in path
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
    ):
        raise DocumentError("invalid_workspace_path")
    if path == "/workspace":
        return ()
    if not path.startswith("/workspace/"):
        raise DocumentError("invalid_workspace_path")
    parts = tuple(path[len("/workspace/") :].split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise DocumentError("invalid_workspace_path")
    return parts


class WorkspaceBrowser:
    def __init__(self, root: Path):
        self.root = root
        self.io = ImageWorkspace(root)

    def list_directory(
        self,
        path: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
        artifacts_only: bool = False,
    ) -> WorkspacePage:
        parts = path_parts(path)
        if not 1 <= limit <= 200:
            raise DocumentError("invalid_workspace_limit")
        after = None
        if cursor:
            try:
                value = json.loads(
                    base64.b64decode(cursor, altchars=b"-_", validate=True)
                )
                if value["path"] != path or not isinstance(value["after"], str):
                    raise ValueError
                after = value
            except (ValueError, KeyError, TypeError, binascii.Error, RecursionError):
                raise DocumentError("invalid_workspace_cursor") from None
        if not self.root.exists():
            if parts == () or artifacts_only:
                return WorkspacePage(items=[])
            raise DocumentError("workspace_not_found", 404)
        try:
            directory = self.io._directory(parts)
        except ToolException:
            if artifacts_only and not (self.root / "outputs").exists():
                return WorkspacePage(items=[])
            raise DocumentError("workspace_directory_unavailable", 404) from None
        try:
            fingerprint = str(os.fstat(directory).st_mtime_ns)
            if after and after.get("revision") != fingerprint:
                raise DocumentError("workspace_directory_changed", 409)
            entries = []
            with os.scandir(directory) as iterator:
                for count, entry in enumerate(iterator, 1):
                    if count > MAX_DIRECTORY_ENTRIES:
                        raise DocumentError("workspace_directory_too_large", 413)
                    if any(
                        ord(c) < 32 or ord(c) == 127 or c == "\\" for c in entry.name
                    ):
                        continue
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    is_dir = stat.S_ISDIR(info.st_mode)
                    if not is_dir and not stat.S_ISREG(info.st_mode):
                        continue
                    extension = Path(entry.name).suffix[1:].lower()
                    artifact = (
                        parts == ("outputs",)
                        and bool(re.fullmatch(r"[0-9a-f]{64}\.[a-z0-9]+", entry.name))
                        and extension in ARTIFACT_MIMES
                        and not is_dir
                    )
                    if artifacts_only and not artifact:
                        continue
                    mime = (
                        None
                        if is_dir
                        else ARTIFACT_MIMES.get(extension, "application/octet-stream")
                    )
                    entries.append(
                        WorkspaceEntry(
                            path=path + "/" + entry.name,
                            name=entry.name,
                            type="directory" if is_dir else "file",
                            size_bytes=None if is_dir else info.st_size,
                            mtime=datetime.fromtimestamp(
                                info.st_mtime, UTC
                            ).isoformat(),
                            mime_type=mime,
                            preview_kind=None if is_dir else preview_kind(mime),
                            is_artifact=artifact,
                        )
                    )
            entries.sort(key=lambda item: item.name)
            if after:
                entries = [entry for entry in entries if entry.name > after["after"]]
            page = entries[:limit]
            next_cursor = None
            if len(entries) > limit:
                next_cursor = base64.urlsafe_b64encode(
                    json.dumps(
                        {"path": path, "after": page[-1].name, "revision": fingerprint}
                    ).encode()
                ).decode()
            return WorkspacePage(items=page, next_cursor=next_cursor)
        except OSError:
            raise DocumentError("workspace_directory_unavailable", 404) from None
        finally:
            os.close(directory)

    def read_file(self, path: str) -> tuple[bytes, dict]:
        parts = path_parts(path)
        if not parts:
            raise DocumentError("workspace_not_file", 415)
        if (
            len(parts) == 2
            and parts[0] == "outputs"
            and re.fullmatch(r"[0-9a-f]{64}\.[a-z0-9]+", parts[1])
        ):
            return ArtifactWorkspace(self.root).read(path)
        try:
            data = self.io.read(path)
        except ToolException:
            raise DocumentError("workspace_file_unavailable", 404) from None
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        mime = ARTIFACT_MIMES.get(
            Path(path).suffix[1:].lower(), "application/octet-stream"
        )
        return data, {
            "path": path,
            "file_name": parts[-1],
            "mime_type": mime,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "preview_kind": preview_kind(mime),
        }

    def preview(self, path: str) -> tuple[bytes, str]:
        data, ref = self.read_file(path)
        kind = ref["preview_kind"]
        if kind == "download":
            raise DocumentError("workspace_preview_unsupported", 415)
        if kind == "image":
            validate_media(data, Path(path).suffix[1:].lower())
            return data, ref["mime_type"]
        if kind == "html-sandbox":
            from runtime_service.workspace.html_preview import safe_html

            if len(data) > PREVIEW_BYTES:
                raise DocumentError("html_preview_too_large", 413)
            try:
                return safe_html(data.decode("utf-8-sig")).encode(), "text/html"
            except UnicodeError:
                raise DocumentError("invalid_document", 422) from None
        truncated = len(data) > PREVIEW_BYTES
        try:
            text = codecs.getincrementaldecoder("utf-8-sig")().decode(
                data[:PREVIEW_BYTES], final=not truncated
            )
            if "\x00" in text:
                raise ValueError
        except (UnicodeError, ValueError):
            raise DocumentError("invalid_document", 422) from None
        return json.dumps(
            {**ref, "text": text, "truncated": truncated}, ensure_ascii=False
        ).encode(), "application/json"
