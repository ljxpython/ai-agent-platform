"""Thread-scoped document storage using descriptor-based workspace IO."""

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import fitz
from langchain_core.tools import ToolException

from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.file_refs import (
    MAX_FILE_BYTES, MIME_EXT, FileRef, validate_file_path, validate_file_ref,
)


class DocumentError(ToolException):
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def open_pdf(data: bytes) -> fitz.Document:
    if not data.startswith(b"%PDF-"):
        raise DocumentError("invalid_pdf_magic", 415)
    try:
        document = fitz.open(stream=data, filetype="pdf")
        if document.needs_pass:
            document.close()
            raise DocumentError("encrypted_pdf", 422)
        if document.is_repaired or document.page_count == 0:
            document.close()
            raise DocumentError("damaged_pdf", 422)
        return document
    except (fitz.FileDataError, RuntimeError, ValueError):
        raise DocumentError("damaged_pdf", 422) from None


def validate_document(data: bytes, mime: str) -> None:
    if not data:
        raise DocumentError("empty_file", 415)
    if len(data) > MAX_FILE_BYTES:
        raise DocumentError("file_too_large", 413)
    if mime not in MIME_EXT:
        raise DocumentError("unsupported_file_type", 415)
    if mime == "application/vnd.ms-excel":
        if not data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
            raise DocumentError("invalid_xls_magic", 415)
        # Full workbook parsing belongs to the resource-limited execution process.
        return
    if mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        from runtime_service.workspace.archives import read_zip
        try:
            names = {name for name, _ in read_zip(data)}
            if not {"[Content_Types].xml", "xl/workbook.xml"} <= names:
                raise ValueError("invalid_xlsx")
            if any(name.lower().endswith("vbaproject.bin") for name in names):
                raise ValueError("macro_workbook_denied")
        except ValueError as exc:
            raise DocumentError(str(exc), 422) from exc
        return
    if mime == "application/zip":
        from runtime_service.workspace.archives import read_zip
        try:
            read_zip(data)
        except ValueError as exc:
            raise DocumentError(str(exc), 422) from exc
        return
    if mime == "application/pdf":
        with open_pdf(data):
            pass
        return
    try:
        text = data.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError
        if mime == "application/json":
            json.loads(text)
    except (UnicodeError, ValueError, RecursionError):
        raise DocumentError("invalid_document", 422) from None


class DocumentWorkspace:
    def __init__(self, root: Path | None):
        self.io = ImageWorkspace(root)

    def read(self, path: str) -> tuple[bytes, FileRef]:
        try:
            digest, ext = validate_file_path(path)
        except ValueError:
            raise DocumentError("invalid_file_ref") from None
        try:
            data = self.io.read(path)
        except ToolException:
            raise DocumentError("file_not_found", 404) from None
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        if hashlib.sha256(data).hexdigest() != digest:
            raise DocumentError("file_hash_mismatch", 409)
        mime = next(mime for mime, extension in MIME_EXT.items() if extension == ext)
        return data, FileRef(version=1, path=path, file_name=path.rsplit("/", 1)[-1],
                            mime_type=mime, size_bytes=len(data), sha256=digest)

    def put(self, data: bytes, digest: str, mime: str, name: str | None = None) -> FileRef:
        ext = MIME_EXT.get(mime)
        if ext is None:
            raise DocumentError("unsupported_file_type", 415)
        validate_document(data, mime)
        filename = f"{digest}.{ext}"
        try:
            ref = validate_file_ref(dict(version=1, path=f"/workspace/uploads/{filename}",
                file_name=name or filename, mime_type=mime, size_bytes=len(data), sha256=digest))
        except ValueError:
            raise DocumentError("invalid_file_ref") from None
        if hashlib.sha256(data).hexdigest() != digest:
            raise DocumentError("file_hash_mismatch")
        try:
            directory = self.io._directory(("uploads",), create=True)
        except ToolException:
            raise DocumentError("file_workspace_unavailable", 409) from None
        temporary = f".document-{uuid4().hex}"
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
                existing, _ = self.read(ref["path"])
                if existing != data:
                    raise DocumentError("file_content_conflict", 409)
        except OSError:
            raise DocumentError("file_workspace_unavailable", 409) from None
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            os.close(directory)
        return ref
