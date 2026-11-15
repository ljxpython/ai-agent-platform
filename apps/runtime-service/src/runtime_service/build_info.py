"""Fingerprint deployed package files once, before graph code is imported."""

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path


def package_digest(root: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(root.rglob("*"))
    if root.is_symlink() or any(path.is_symlink() for path in paths):
        raise ValueError("Runtime package contains a symbolic link")
    files = sorted(
        path
        for path in paths
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    if not files or len(files) > 10000:
        raise ValueError("Invalid runtime package file count")
    size = 0
    for path in files:
        data = path.read_bytes()
        size += len(data)
        if size > 64 * 1024**2:
            raise ValueError("Runtime package exceeds fingerprint bound")
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


try:
    STARTUP_PACKAGE_DIGEST = package_digest(Path(__file__).parent)
except (OSError, ValueError):
    # Missing deployment evidence blocks evaluation, never business execution.
    STARTUP_PACKAGE_DIGEST = "unavailable"


def build_manifest():
    dependencies = sorted(
        (distribution.metadata.get("Name", ""), distribution.version)
        for distribution in importlib.metadata.distributions()
    )
    return {
        "package_sha256": STARTUP_PACKAGE_DIGEST,
        "dependencies_sha256": hashlib.sha256(
            json.dumps(dependencies).encode()
        ).hexdigest(),
        "python": platform.python_version(),
        "execution_mode": "local_process",
    }


STARTUP_MANIFEST = build_manifest()
