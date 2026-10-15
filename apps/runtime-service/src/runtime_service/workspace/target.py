"""Trusted deployment configuration; remote paths are never local Path objects."""

from __future__ import annotations

import hashlib
import os
import re
import ssl
import stat
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from runtime_service.errors import RuntimeWorkspaceError


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", value):
        raise RuntimeWorkspaceError("runtime.workspace.backend_invalid")
    return value


def sandbox_target() -> str:
    value = os.getenv("RUNTIME_SANDBOX_TARGET", "local")
    if value not in {"local", "remote"}:
        raise RuntimeWorkspaceError("runtime.workspace.backend_invalid")
    return value if os.getenv("RUNTIME_BACKEND", "docker") == "docker" else "local"


def secret_file(name: str, settings=None) -> Path:
    path = Path((os.environ if settings is None else settings)[name])
    if (
        not path.is_absolute()
        or any(p.is_symlink() for p in (path, *path.parents))
        or not path.is_file()
    ):
        raise ValueError("invalid secret file")
    mode = stat.S_IMODE(path.stat().st_mode)
    private = name.endswith(("AUTH_FILE", "KEY_FILE"))
    if mode & (0o077 if private else 0o022):
        raise ValueError("unsafe secret file permissions")
    return path


@lru_cache(maxsize=4)
def _tls_context(material):
    ca, certificate, key = (path for path, _ in material)
    tls = ssl.create_default_context(cafile=ca)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(certificate, key)
    return tls


@dataclass(frozen=True)
class NodeConnection:
    url: str
    node_id: str
    execution_host: str
    token: str = field(repr=False)
    tls: ssl.SSLContext = field(repr=False)

    @classmethod
    def load(cls, settings=None):
        settings = os.environ if settings is None else settings
        try:
            url = settings["RUNTIME_SANDBOX_NODE_URL"].rstrip("/")
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.port is not None
                and not 1 <= parsed.port <= 65535
            ):
                raise ValueError("invalid node URL")
            node = identifier(settings["RUNTIME_SANDBOX_NODE_ID"])
            host = identifier(settings["RUNTIME_EXECUTION_HOST_ID"])
            token = (
                secret_file("RUNTIME_SANDBOX_NODE_AUTH_FILE", settings)
                .read_text()
                .strip()
            )
            if not re.fullmatch(r"[a-zA-Z0-9_-]{32,256}", token):
                raise ValueError("invalid caller token")
            paths = (
                secret_file("RUNTIME_SANDBOX_NODE_" + name, settings)
                for name in ("CA_FILE", "CLIENT_CERT_FILE", "CLIENT_KEY_FILE")
            )
            # Content fingerprints retire connections even when rotation keeps the paths.
            material = tuple(
                (str(path), hashlib.sha256(path.read_bytes()).digest())
                for path in paths
            )
            tls = _tls_context(material)
            return cls(url, node, host, token, tls)
        except (KeyError, ValueError, OSError, ssl.SSLError) as exc:
            raise RuntimeWorkspaceError("runtime.workspace.backend_invalid") from exc


@dataclass(frozen=True)
class RemoteWorkspace:
    scope: tuple[str, str, str]
    graph: str
    execution_host: str
    node_id: str
    workspace_id: str

    def call(self, operation: str, **arguments):
        from runtime_service.workspace.node_client import call

        return call(self, operation, arguments)

    async def stream_file(self, path: str):
        from runtime_service.workspace.node_client import stream_file

        return await stream_file(self, path)

    async def stream_archive(self):
        from runtime_service.workspace.node_client import stream_archive

        return await stream_archive(self)


@dataclass(frozen=True)
class RemoteSkills:
    workspace: RemoteWorkspace
    digest: str

    @property
    def name(self):
        return "skills-" + self.digest
