from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal
from uuid import UUID

from lightrag.api.config import initialize_config, parse_args

SupportedTransport = Literal["stdio", "http", "sse", "streamable-http"]
SUPPORTED_TRANSPORTS: set[str] = {"stdio", "http", "sse", "streamable-http"}


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _read_env_default(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@contextmanager
def _temporary_argv(argv: list[str]) -> Iterator[None]:
    original = sys.argv[:]
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = original


@dataclass(frozen=True, slots=True)
class ProjectKnowledgeMCPConfig:
    storage_root: Path
    input_root: Path
    transport: SupportedTransport = "stdio"
    host: str = "127.0.0.1"
    port: int = 8621
    path: str | None = None
    message_path: str | None = None
    show_banner: bool = False
    log_level: str | None = None
    default_query_mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = (
        "mix"
    )
    default_top_k: int = 8
    default_list_limit: int = 20

    def workspace_key(self, project_id: str) -> str:
        return f"kb_{UUID(project_id).hex}"

    def workspace_input_dir(self, project_id: str) -> Path:
        return self.input_root / self.workspace_key(project_id)


def build_mcp_config() -> ProjectKnowledgeMCPConfig:
    transport = (_read_env_default("MCP_TRANSPORT") or "stdio").lower()
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"unsupported_mcp_transport:{transport}")

    storage_root = Path(
        os.getenv("LIGHTRAG_MCP_STORAGE_ROOT")
        or os.getenv("WORKING_DIR")
        or "./rag_storage"
    ).expanduser()
    input_root = Path(
        os.getenv("LIGHTRAG_MCP_INPUT_ROOT")
        or os.getenv("INPUT_DIR")
        or "./inputs"
    ).expanduser()

    path = _read_env_default("MCP_PATH") or "/sse"
    message_path = _read_env_default("MCP_MESSAGE_PATH") or "/messages/"
    log_level = _read_env_default("MCP_LOG_LEVEL")
    if log_level is not None:
        log_level = log_level.upper()

    default_query_mode = (_read_env_default("LIGHTRAG_MCP_DEFAULT_QUERY_MODE") or "mix").lower()
    default_top_k = _parse_int_env("LIGHTRAG_MCP_DEFAULT_TOP_K", 8)
    default_list_limit = _parse_int_env("LIGHTRAG_MCP_DEFAULT_LIST_LIMIT", 20)

    return ProjectKnowledgeMCPConfig(
        storage_root=storage_root.resolve(),
        input_root=input_root.resolve(),
        transport=transport,  # type: ignore[arg-type]
        host=_read_env_default("MCP_HOST") or "127.0.0.1",
        port=_parse_int_env("MCP_PORT", 8621),
        path=path,
        message_path=message_path,
        show_banner=_parse_bool_env("MCP_SHOW_BANNER", False),
        log_level=log_level,
        default_query_mode=default_query_mode,  # type: ignore[arg-type]
        default_top_k=max(1, default_top_k),
        default_list_limit=max(1, default_list_limit),
    )


def build_api_args_for_mcp(config: ProjectKnowledgeMCPConfig):
    """Build LightRAG API args from env defaults without consuming MCP CLI args."""

    with _temporary_argv([sys.argv[0]]):
        args = parse_args()

    args.working_dir = str(config.storage_root)
    args.input_dir = str(config.input_root)
    args.workspace = "__lightrag_mcp_template__"
    initialize_config(args, force=True)
    return args
