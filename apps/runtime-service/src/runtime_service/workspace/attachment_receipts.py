"""HTTP upload facts outside the Agent's mounted workspace, including original names."""

import hashlib
import json
import os
import stat
from pathlib import Path

from langchain_core.tools import ToolException

from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.file_refs import validate_file_name, validate_file_ref
from runtime_service.workspace.image_refs import validate_uploaded_image_ref


class AttachmentReceipts:
    def __init__(self, workspace: Path):
        scope = hashlib.sha256(str(workspace.absolute()).encode()).hexdigest()
        self.io = ImageWorkspace(workspace.parent / ".attachment-receipts" / scope)

    @staticmethod
    def _encoded(ref):
        return json.dumps(
            validate_file_ref(ref),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()

    def record(self, ref):
        raw = self._encoded(ref)
        name = hashlib.sha256(raw).hexdigest() + ".json"
        if not self._write("refs", name, raw):
            self.require(ref)

    def _write(self, folder, name, raw):
        directory = self.io._directory((folder,), create=True, create_root=True)
        try:
            try:
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=directory,
                )
            except FileExistsError:
                return False
            with os.fdopen(descriptor, "wb") as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            os.fsync(directory)
            return True
        finally:
            os.close(directory)

    def require(self, ref):
        raw = self._encoded(ref)
        name = hashlib.sha256(raw).hexdigest() + ".json"
        # Legacy attachments have no receipt; use their content-addressed name, never a model-supplied alias.
        saved = self._read("refs", name)
        if saved is None:
            return False
        if saved != raw:
            raise ToolException("knowledge_invalid_file_ref")
        return True

    def _read(self, folder, name):
        try:
            directory = self.io._directory((folder,))
        except (RuntimeWorkspaceError, ToolException) as exc:
            if isinstance(exc.__cause__ or exc.__context__, FileNotFoundError):
                return None
            raise
        try:
            try:
                descriptor = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
                )
            except FileNotFoundError:
                return None
            with os.fdopen(descriptor, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ToolException("knowledge_invalid_file_ref")
                saved = source.read(4097)
        except OSError as exc:
            raise ToolException("knowledge_invalid_file_ref") from exc
        finally:
            os.close(directory)
        return saved

    @staticmethod
    def _image_key(ref):
        encoded = json.dumps(validate_uploaded_image_ref(ref), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest() + ".json"

    def record_image(self, ref, file_name=None):
        safe = validate_uploaded_image_ref(ref)
        name = validate_file_name(
            file_name if file_name is not None else safe["path"].rsplit("/", 1)[-1]
        )
        raw = json.dumps({**safe, "file_name": name}, ensure_ascii=True).encode()
        # The first successful upload owns the name for these exact bytes in this Thread.
        self._write("images", self._image_key(safe), raw)
        return self.require_image(safe)

    def require_image(self, ref):
        safe = validate_uploaded_image_ref(ref)
        raw = self._read("images", self._image_key(safe))
        if raw is None:
            raise ToolException("knowledge_invalid_file_ref")
        try:
            saved = json.loads(raw)
            if not isinstance(saved, dict) or set(saved) != {*safe, "file_name"}:
                raise ValueError()
            if {k: saved[k] for k in safe} != safe:
                raise ValueError()
            validate_file_name(saved["file_name"])
            return saved
        except (ValueError, TypeError, KeyError) as exc:
            raise ToolException("knowledge_invalid_file_ref") from exc

    def copy_to(self, target: Path):
        self._copy_folder(target, "refs")
        self._copy_folder(target, "images")

    def _copy_folder(self, target: Path, folder):
        try:
            directory = self.io._directory((folder,))
        except (RuntimeWorkspaceError, ToolException) as exc:
            if isinstance(exc.__cause__ or exc.__context__, FileNotFoundError):
                return
            raise
        try:
            for name in os.listdir(directory):
                if len(name) == 69 and name.endswith(".json"):
                    ref = json.loads(self._read(folder, name))
                    if folder == "images":
                        image = {k: v for k, v in ref.items() if k != "file_name"}
                        trusted = self.require_image(image)
                        AttachmentReceipts(target).record_image(
                            image, trusted["file_name"]
                        )
                    else:
                        if not self.require(ref):
                            raise ToolException("knowledge_invalid_file_ref")
                        AttachmentReceipts(target).record(ref)
        finally:
            os.close(directory)
