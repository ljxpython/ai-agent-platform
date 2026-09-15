"""Immutable TXT artifacts, published from the mutable thread work directory."""
import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4
from langchain_core.tools import ToolException

from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.documents import validate_document, DocumentError


class ArtifactWorkspace:
    def __init__(self, root: Path | None):
        self.io = ImageWorkspace(root)

    def read(self, path: str) -> tuple[bytes, dict]:
        match = re.fullmatch(r"/workspace/outputs/([0-9a-f]{64})\.txt", path)
        if match is None:
            raise DocumentError("invalid_artifact_ref")
        try:
            data = self.io.read(path)
        except ToolException as exc:
            raise DocumentError("artifact_not_found", 404) from exc
        validate_document(data, "text/plain")
        digest = hashlib.sha256(data).hexdigest()
        if digest != match[1]:
            raise DocumentError("artifact_hash_mismatch", 409)
        return data, dict(version=1, artifact_id=digest, path=path,
                          file_name=digest + ".txt", mime_type="text/plain",
                          size_bytes=len(data), sha256=digest, kind="text")

    def publish(self, path: str) -> dict:
        if not path.startswith("/workspace/work/") or ".." in path.split("/"):
            raise DocumentError("artifact_source_denied")
        data = self.io.read(path)
        validate_document(data, "text/plain")
        digest = hashlib.sha256(data).hexdigest()
        filename = digest + ".txt"
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
