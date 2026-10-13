"""Safe local file primitives on the daemon host; only virtual paths cross HTTP."""

import base64
import errno
import hashlib
import json
import os
import stat
import time
from pathlib import Path
from uuid import uuid4

from deepagents.backends.protocol import GlobResult, GrepResult, LsResult, ReadResult
from deepagents.backends.utils import (
    compile_recursive_glob,
    create_file_data,
    perform_string_replacement,
    slice_read_response,
)
from langchain_core.tools import ToolException

from runtime_service.workspace.browser import WorkspaceBrowser, path_parts
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.file_refs import MAX_FILE_BYTES
from runtime_service.workspace.image_io import ImageWorkspace


class Storage:
    def __init__(self, config, ledger):
        self.config, self.ledger = config, ledger

    def key(self, request):
        return "/".join((request.execution_host, request.graph, request.workspace_id))

    def root(self, request):
        base = self.config.workspaces.resolve()
        root = base / self.key(request) / "workspace"
        current = base
        for part in root.relative_to(base).parts:
            current /= part
            if current.is_symlink():
                raise DocumentError("invalid_workspace_path")
        return root

    def check(self, request):
        with self.ledger.connect() as db:
            row = db.execute(
                "SELECT status FROM workspaces WHERE key=?", (self.key(request),)
            ).fetchone()
        if (
            row is None
            or row["status"] != "retained"
            or not self.root(request).is_dir()
        ):
            raise DocumentError("workspace_not_found", 404)
        return self.root(request)

    def prepare(self, request, examples):
        root = self.root(request)
        with self.ledger.connect() as db:
            row = db.execute(
                "SELECT status FROM workspaces WHERE key=?", (self.key(request),)
            ).fetchone()
            if row and row["status"] != "preparing":
                self.check(request)
                return {"prepared": True}
            if not row and root.exists():
                raise DocumentError("workspace_binding_missing", 409)
            if not row:
                db.execute(
                    "INSERT INTO workspaces(key,status,created) VALUES (?, 'preparing', ?)",
                    (self.key(request), time.time()),
                )
        io = ImageWorkspace(root)
        for name in ("work", "uploads", "outputs", "generated", "charts", "sources"):
            os.close(io._directory((name,), create=True, create_root=True))
        for name, data in examples.items():
            if Path(name).name != name:
                raise DocumentError("invalid_workspace_path")
            self.write_bytes(root, "/workspace/" + name, data, replace=False)
        with self.ledger.connect() as db:
            db.execute(
                "UPDATE workspaces SET status='retained' WHERE key=?",
                (self.key(request),),
            )
        return {"prepared": True}

    def write_bytes(self, root, path, data, *, replace=True):
        parts = path_parts(path)
        if not parts or len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        self.quota(root, path, len(data))
        directory = ImageWorkspace(root)._directory(parts[:-1], create=True)
        temporary = ".node-" + uuid4().hex
        try:
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise DocumentError("invalid_workspace_path")
            except FileNotFoundError:
                pass
            if replace:
                os.replace(
                    temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory
                )
            else:
                try:
                    os.link(
                        temporary,
                        parts[-1],
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    if ImageWorkspace(root).read(path) != data:
                        raise DocumentError("file_content_conflict", 409) from None
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            os.close(directory)
        return {"path": path}

    def quota(self, root, path, size):
        count, total = 0, 0
        current = root.joinpath(*path_parts(path))
        for parent, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(parent) / name).is_symlink()]
            for name in names:
                info = (Path(parent) / name).lstat()
                if stat.S_ISREG(info.st_mode):
                    count += 1
                    if Path(parent) / name != current:
                        total += info.st_size
            if count > 10000 or total + size > 1024**3:
                raise DocumentError("workspace_quota_exceeded", 413)

    def read_bytes(self, root, path):
        parts = path_parts(path)
        if not parts:
            raise DocumentError("workspace_not_file", 415)
        directory = ImageWorkspace(root)._directory(())
        try:
            for part in parts[:-1]:
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                os.close(directory)
                directory = child
            descriptor = os.open(
                parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(descriptor, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise DocumentError("workspace_not_file", 415)
                data = source.read(MAX_FILE_BYTES + 1)
        except OSError as exc:
            code = {
                errno.ENOENT: "file_not_found",
                errno.EACCES: "file_permission_denied",
                errno.EPERM: "file_permission_denied",
                errno.ELOOP: "invalid_workspace_path",
                errno.ENOTDIR: "invalid_workspace_path",
            }.get(exc.errno, "file_read_failed")
            raise DocumentError(
                code,
                404
                if code == "file_not_found"
                else 403
                if code == "file_permission_denied"
                else 400,
            ) from None
        finally:
            os.close(directory)
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        return data

    def file_data(self, root, path):
        data = self.read_bytes(root, path)
        if len(data) > MAX_FILE_BYTES:
            raise DocumentError("file_too_large", 413)
        try:
            return create_file_data(data.decode("utf-8"))
        except UnicodeError:
            value = create_file_data("")
            return {
                **value,
                "content": base64.b64encode(data).decode(),
                "encoding": "base64",
            }

    def read(self, root, arguments):
        try:
            if arguments.get("limit", 2000) <= 0:
                return ReadResult(
                    file_data=create_file_data(""), no_lines_requested=True
                )
            data = self.file_data(root, arguments["path"])
            if data.get("encoding") == "base64":
                return ReadResult(file_data=data)
            return slice_read_response(
                data,
                arguments.get("offset", 0),
                min(arguments.get("limit", 2000), 2000),
            )
        except DocumentError as exc:
            return ReadResult(error=exc.code)

    def ls(self, root, path):
        try:
            page = WorkspaceBrowser(root).list_directory(path, limit=200)
            return LsResult(
                entries=[
                    {
                        "path": item.path,
                        "is_dir": item.type == "directory",
                        "size": item.size_bytes,
                        "modified_at": item.mtime,
                    }
                    for item in page.items
                ],
                error="directory_truncated" if page.next_cursor else None,
            )
        except DocumentError as exc:
            return LsResult(error=exc.code)

    def search(self, root, arguments, *, grep):
        path = arguments.get("path") or "/workspace"
        parts = path_parts(path)
        directory = root.joinpath(*parts)
        try:
            os.close(ImageWorkspace(root)._directory(parts))
        except ToolException:
            return (
                GrepResult(error="directory_unavailable")
                if grep
                else GlobResult(error="directory_unavailable")
            )
        pattern = arguments.get("glob") if grep else arguments["pattern"]
        matcher = compile_recursive_glob(pattern or "*")
        found, count, total, deadline = [], 0, 0, time.monotonic() + 10
        cap = min(arguments.get("max_count") or 1000, 1000)

        def walk_error(exc):
            raise exc

        try:
            for parent, dirs, names in os.walk(
                directory, followlinks=False, onerror=walk_error
            ):
                dirs[:] = [
                    name for name in dirs if not (Path(parent) / name).is_symlink()
                ]
                for name in sorted(names):
                    count += 1
                    if (
                        count > 10000
                        or total > 32 * 1024**2
                        or time.monotonic() >= deadline
                    ):
                        return (
                            GrepResult(matches=found, truncated=True)
                            if grep
                            else GlobResult(matches=found, truncated=True)
                        )
                    file = Path(parent) / name
                    if (
                        file.is_symlink()
                        or not file.is_file()
                        or not matcher(file.relative_to(directory).as_posix())
                    ):
                        continue
                    virtual = "/workspace/" + file.relative_to(root).as_posix()
                    if grep:
                        data = self.read_bytes(root, virtual)
                        total += len(data)
                        if len(data) > MAX_FILE_BYTES:
                            return GrepResult(
                                error="file_too_large", matches=found, truncated=True
                            )
                        text = data.decode("utf-8", errors="replace")
                        for line, content in enumerate(text.splitlines(), 1):
                            if arguments["pattern"] in content:
                                found.append(
                                    {
                                        "path": virtual,
                                        "line": line,
                                        "text": content[:2000],
                                    }
                                )
                                if len(found) > cap:
                                    return GrepResult(
                                        matches=found[:cap], truncated=True
                                    )
                    else:
                        found.append(
                            {
                                "path": virtual,
                                "is_dir": False,
                                "size": file.stat().st_size,
                            }
                        )
                        if len(found) > cap:
                            return GlobResult(matches=found[:cap], truncated=True)
            return GrepResult(matches=found) if grep else GlobResult(matches=found)
        except (OSError, ToolException):
            return (
                GrepResult(error="search_incomplete", matches=found, truncated=True)
                if grep
                else GlobResult(
                    error="search_incomplete", matches=found, truncated=True
                )
            )

    def mutate(self, root, operation, arguments, *, protected=True):
        path = arguments["path"]
        if not path.startswith("/workspace/work/" if protected else "/workspace/"):
            return {"error": "workspace_write_denied"}
        try:
            if operation == "delete":
                parts = path_parts(path)
                directory = ImageWorkspace(root)._directory(parts[:-1])
                try:
                    if not stat.S_ISREG(
                        os.stat(
                            parts[-1], dir_fd=directory, follow_symlinks=False
                        ).st_mode
                    ):
                        raise DocumentError("invalid_workspace_path")
                    os.unlink(parts[-1], dir_fd=directory)
                finally:
                    os.close(directory)
                return {"path": path}
            content = arguments.get("content")
            occurrences = None
            if operation == "edit":
                previous = ImageWorkspace(root).read(path).decode("utf-8")
                replacement = perform_string_replacement(
                    previous,
                    arguments["old_string"],
                    arguments["new_string"],
                    arguments.get("replace_all", False),
                )
                if isinstance(replacement, str):
                    return {"error": replacement[:2000]}
                content, occurrences = replacement
            result = self.write_bytes(root, path, content.encode())
            return {
                **result,
                **({"occurrences": occurrences} if operation == "edit" else {}),
            }
        except (ToolException, UnicodeError, OSError) as exc:
            return {"error": getattr(exc, "code", "file_unavailable")}

    def snapshot_path(self, root, digest):
        import re

        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise DocumentError("skill_snapshot_invalid")
        path = root.parent / ("skills-" + digest)
        if path.is_symlink() or not path.is_dir():
            raise DocumentError("skill_snapshot_missing", 409)
        if snapshot_hash(path) != digest:
            raise DocumentError("skill_snapshot_mismatch", 409)
        return path

    def publish_skills(self, request, files, documents, run_id=None):
        root = self.check(request)
        record = (
            root.parent
            / (
                "execution-"
                + hashlib.sha256(str(run_id).encode()).hexdigest()
                + ".json"
            )
            if run_id
            else None
        )
        if record and record.exists():
            return self.restore_skills(request, json.loads(record.read_text()))
        content = dict(files)
        for document in documents:
            for name, data in document["files"].items():
                content[f"custom/{document['slug']}/{name}"] = data.encode()
        if (
            len(content) > 10000
            or sum(len(data) for data in content.values()) > 32 * 1024**2
        ):
            raise DocumentError("skill_snapshot_too_large", 413)
        digest = hashlib.sha256()
        for name, data in sorted(content.items()):
            if (
                name.startswith("/")
                or "\\" in name
                or any(p in {"", ".", ".."} for p in name.split("/"))
            ):
                raise DocumentError("skill_snapshot_invalid")
            digest.update(name.encode() + b"\0")
            digest.update(hashlib.sha256(data).digest())
        fingerprint = digest.hexdigest()
        destination = root.parent / ("skills-" + fingerprint)
        if destination.is_symlink():
            raise DocumentError("skill_snapshot_invalid")
        if not destination.exists():
            import tempfile

            with tempfile.TemporaryDirectory(
                prefix=".snapshot-", dir=root.parent
            ) as temporary:
                staging = Path(temporary) / "files"
                staging.mkdir()
                for name, data in content.items():
                    file = staging / name
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_bytes(data)
                staging.rename(destination)
        self.snapshot_path(root, fingerprint)
        result = {"directory": "skills-" + fingerprint, "digest": fingerprint}
        if record:
            staged = record.with_suffix(".tmp")
            staged.write_text(json.dumps(result))
            staged.replace(record)
        return result

    def restore_skills(self, request, ref):
        root = self.check(request)
        if ref.get("directory") != "skills-" + str(ref.get("digest")):
            raise DocumentError("skill_snapshot_invalid")
        self.snapshot_path(root, ref["digest"])
        return ref

    def research(self, root, arguments):
        from datetime import UTC, datetime

        artifacts, summaries = [], []
        for record in arguments["records"]:
            record = dict(record)
            content = record.pop("content")
            raw = content.encode()
            digest = hashlib.sha256(raw).hexdigest()
            path = "/workspace/sources/" + digest + ".txt"
            self.write_bytes(root, path, raw, replace=False)
            evidence = {
                **record,
                "content_hash": digest,
                "path": path,
                **{
                    key: arguments[key]
                    for key in ("tool_call_id", "thread_id", "run_id", "namespace")
                },
                "observed_at": datetime.now(UTC).isoformat(),
            }
            artifacts.append(evidence)
            summaries.append(
                {
                    **evidence,
                    "preview": content[:8000],
                    "truncated": len(content) > 8000,
                }
            )
        return json.dumps(summaries, ensure_ascii=False), {
            "version": 1,
            "sources": artifacts,
        }

    def fork_source(self, request, source_scope):
        from runtime_service.workspace.scoped import thread_scope_hash

        if (
            not isinstance(source_scope, (list, tuple))
            or len(source_scope) != 3
            or list(source_scope[:2]) != request.scope[:2]
            or any(
                not isinstance(value, str) or not value or len(value) > 256
                for value in source_scope
            )
        ):
            raise DocumentError("workspace_fork_scope_mismatch", 403)
        return request.model_copy(
            update={
                "scope": list(source_scope),
                "workspace_id": thread_scope_hash(*source_scope),
            }
        )

    def fork(self, request, source):
        source_root = self.check(source)
        if self.key(source) == self.key(request):
            return {"files_copied": 0}
        self.prepare(request, {})
        target_root = self.check(request)
        count, total = 0, 0
        for parent, dirs, names in os.walk(source_root, followlinks=False):
            dirs[:] = [
                name
                for name in dirs
                if not name.startswith(".") and not (Path(parent) / name).is_symlink()
            ]
            for name in names:
                if name.startswith("."):
                    continue
                if (Path(parent) / name).is_symlink():
                    raise DocumentError("invalid_workspace_path")
                relative = (Path(parent) / name).relative_to(source_root).as_posix()
                data = ImageWorkspace(source_root).read("/workspace/" + relative)
                count += 1
                total += len(data)
                if count > 10000 or total > 1024**3:
                    raise DocumentError("workspace_quota_exceeded", 413)
                self.write_bytes(
                    target_root, "/workspace/" + relative, data, replace=False
                )
        return {"files_copied": count}

    def archive(self, root):
        import io
        import zipfile

        output, count, total = io.BytesIO(), 0, 0
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for parent, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [
                    name
                    for name in dirs
                    if not name.startswith(".")
                    and not (Path(parent) / name).is_symlink()
                ]
                for name in sorted(names):
                    if name.startswith("."):
                        continue
                    relative = (Path(parent) / name).relative_to(root).as_posix()
                    data = ImageWorkspace(root).read("/workspace/" + relative)
                    count += 1
                    total += len(data)
                    if count > 1000 or total > 20 * 1024**2:
                        raise DocumentError("workspace_archive_too_large", 413)
                    archive.writestr(relative, data)
        return output.getvalue(), "workspace.zip"


def snapshot_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DocumentError("skill_snapshot_mismatch", 409)
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()
