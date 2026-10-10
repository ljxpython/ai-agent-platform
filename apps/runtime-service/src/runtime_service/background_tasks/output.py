"""Private, atomic byte-bounded snapshots, kept outside model-writable Workspace."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.workspace.background import MAX_LOG_BYTES, host_id

MAX_TOTAL_BYTES = 2 * 1024 * MAX_LOG_BYTES


@contextmanager
def directory():
    root = (
        Path(
            os.getenv("RUNTIME_BACKGROUND_LOG_ROOT", ".runtime/background-logs")
        ).absolute()
        / host_id()
    )
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise RuntimeWorkspaceError("background_task_storage_unavailable")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock = None
    try:
        lock = os.open(
            ".writer.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield descriptor
    finally:
        if lock is not None:
            os.close(lock)
        os.close(descriptor)


def check_space():
    with directory() as descriptor:
        space = os.fstatvfs(descriptor)
        if (
            space.f_bavail * space.f_frsize < 2 * MAX_LOG_BYTES
            or storage_bytes(descriptor) + 2 * MAX_LOG_BYTES > MAX_TOTAL_BYTES
        ):
            raise RuntimeWorkspaceError("background_task_log_capacity_reached")


def storage_bytes(descriptor):
    total = 0
    for name in os.listdir(descriptor):
        info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            try:
                UUID(name)
            except ValueError as exc:
                raise RuntimeWorkspaceError(
                    "background_task_storage_unavailable"
                ) from exc
            child = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            try:
                total += storage_bytes(child)
            finally:
                os.close(child)
        elif not stat.S_ISREG(info.st_mode):
            raise RuntimeWorkspaceError("background_task_storage_unavailable")
        elif name.startswith(".snapshot-"):
            # All writers hold this lock; a remaining temporary file is from a crash.
            os.unlink(name, dir_fd=descriptor)
        else:
            total += info.st_size
    return total


@contextmanager
def task_directory(row):
    name = str(UUID(str(row["task_id"])))
    with directory() as root:
        try:
            os.mkdir(name, mode=0o700, dir_fd=root)
        except FileExistsError:
            pass
        descriptor = os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root
        )
        try:
            yield descriptor
        finally:
            os.close(descriptor)


def write_output(row, output):
    body = output[0].encode()
    if len(body) > MAX_LOG_BYTES:
        raise ValueError("background_output_limit")
    name = f"{row['fence']}.log"
    temporary = ".snapshot-" + uuid4().hex
    with task_directory(row) as descriptor:
        # Keep the committed fence while replacing; never remove a newer writer.
        for existing in os.listdir(descriptor):
            if existing.endswith(".log") and existing[:-4].isdecimal():
                fence = int(existing[:-4])
                if fence < row["fence"] and fence != row.get("log_fence"):
                    os.unlink(existing, dir_fd=descriptor)
        if storage_bytes(descriptor) + len(body) > min(
            MAX_TOTAL_BYTES, 2 * MAX_LOG_BYTES
        ):
            raise RuntimeWorkspaceError("background_task_log_capacity_reached")
        file = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
        try:
            with os.fdopen(file, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, name, src_dir_fd=descriptor, dst_dir_fd=descriptor)
        finally:
            try:
                os.unlink(temporary, dir_fd=descriptor)
            except FileNotFoundError:
                pass


def delete_unpublished(row):
    with task_directory(row) as descriptor:
        try:
            os.unlink(f"{row['fence']}.log", dir_fd=descriptor)
        except FileNotFoundError:
            pass


def delete_output(row, *, stale=False):
    with task_directory(row) as descriptor:
        for name in os.listdir(descriptor):
            if not name.endswith(".log"):
                continue
            fence = name[:-4]
            if not fence.isdecimal() or (
                stale
                and (int(fence) >= row["fence"] or int(fence) == row.get("log_fence"))
            ):
                continue
            try:
                os.unlink(name, dir_fd=descriptor)
            except FileNotFoundError:
                pass


def bounded_text(raw, limit):
    if len(raw) > limit:
        marker = b"\n[bytes omitted]\n"
        raw = raw[: limit // 2 - len(marker)] + marker + raw[-limit // 2 :]
    return raw.decode("utf-8", errors="ignore")


def read_output(row, limit=65536):
    if not row["output_available"]:
        return None
    try:
        with task_directory(row) as descriptor:
            file = os.open(
                f"{row['log_fence']}.log",
                os.O_RDONLY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            with os.fdopen(file, "rb") as stream:
                raw = stream.read(MAX_LOG_BYTES + 1)
        if len(raw) > MAX_LOG_BYTES:
            return None
        return bounded_text(raw, limit)
    except (OSError, RuntimeWorkspaceError):
        return None
