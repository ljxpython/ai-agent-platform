"""Bounded, in-memory ZIP reading. Archive entries are never executed or extracted."""
import io
import stat
import zipfile
import zlib
from pathlib import PurePosixPath


def read_zip(data: bytes) -> list[tuple[str, bytes]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 256 or sum(item.file_size for item in entries) > 20 * 1024 * 1024:
                raise ValueError("archive_size_limit")
            seen = set()
            result = []
            for item in entries:
                name = item.filename
                path = PurePosixPath(name)
                mode = item.external_attr >> 16
                if (not name or len(name) > 1000 or name.startswith("/") or "\\" in name or ":" in name
                    or any(ord(c) < 32 for c in name) or ".." in path.parts
                    or path.as_posix().rstrip("/").casefold() in seen
                    or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or item.flag_bits & 1):
                    raise ValueError("unsafe_archive_entry")
                seen.add(path.as_posix().rstrip("/").casefold())
                if item.is_dir():
                    continue
                if item.file_size > 2 * 1024 * 1024 or item.file_size > max(1, item.compress_size) * 100:
                    raise ValueError("archive_expansion_limit")
                result.append((name, archive.read(item)))
            if not result:
                raise ValueError("empty_archive")
            return result
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError) as exc:
        raise ValueError("invalid_archive") from exc
