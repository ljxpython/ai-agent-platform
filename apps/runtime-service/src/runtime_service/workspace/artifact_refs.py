"""Immutable text artifacts, published from the mutable thread work directory."""
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

from langchain_core.tools import ToolException

from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.documents import DocumentError, validate_document
from runtime_service.workspace.media import MEDIA_MIMES, validate_media

ARTIFACT_MIMES = {"txt": "text/plain", "md": "text/markdown", "bib": "text/x-bibtex",
                  "csv": "text/csv", "json": "application/json", "html": "text/html",
                  "css": "text/css", "js": "text/javascript", "zip": "application/zip", **MEDIA_MIMES}


def validate_artifact(data, extension):
    if extension in MEDIA_MIMES:
        validate_media(data, extension)
        return
    mime = ARTIFACT_MIMES[extension]
    validate_document(data, "text/plain" if extension == "bib" else mime)



class ArtifactWorkspace:
    def __init__(self, root: Path | None):
        self.io = ImageWorkspace(root)

    def read(self, path: str) -> tuple[bytes, dict]:
        match = re.fullmatch(r"/workspace/outputs/([0-9a-f]{64})\.(txt|md|bib|csv|json|html|css|js|zip|pptx)", path)
        if match is None:
            raise DocumentError("invalid_artifact_ref")
        try:
            data = self.io.read(path)
        except ToolException as exc:
            raise DocumentError("artifact_not_found", 404) from exc
        # Published media is immutable and validated on publish; verify its hash on read.
        if match[2] not in MEDIA_MIMES:
            validate_artifact(data, match[2])
        digest = hashlib.sha256(data).hexdigest()
        if digest != match[1]:
            raise DocumentError("artifact_hash_mismatch", 409)
        return data, {"version": 1, "artifact_id": digest, "path": path,
                      "file_name": digest + "." + match[2], "mime_type": ARTIFACT_MIMES[match[2]],
                      "size_bytes": len(data), "sha256": digest,
                      "kind": "media" if match[2] in MEDIA_MIMES else "archive" if match[2] == "zip" else "text"}

    def publish(self, path: str) -> dict:
        if not path.startswith("/workspace/work/") or ".." in path.split("/"):
            raise DocumentError("artifact_source_denied")
        extension = Path(path).suffix.lstrip(".").lower()
        if extension not in ARTIFACT_MIMES:
            raise DocumentError("unsupported_artifact_type", 415)
        data = self.io.read(path)
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
