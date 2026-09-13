from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def thread_scope_hash(tenant_id: str, project_id: str, thread_id: str) -> str:
    """Derive scope hash using the canonical json tuple representation."""
    scope = (tenant_id, project_id, thread_id)
    return hashlib.sha256(json.dumps(scope).encode("utf-8")).hexdigest()


def hashed_thread_root(
    base_dir: Path | str,
    tenant_id: str,
    project_id: str,
    thread_id: str,
) -> Path:
    """Pure path derivation for thread root; does not perform I/O or create directories."""
    resolved_base = Path(base_dir).resolve()
    scope_id = thread_scope_hash(tenant_id, project_id, thread_id)
    return resolved_base / scope_id


def get_showcase_workspace_root(
    tenant_id: str,
    project_id: str,
    thread_id: str,
) -> Path:
    """Return the /workspace directory under the thread root using the configured base."""
    base = os.getenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", ".runtime/showcase")
    thread_root = hashed_thread_root(base, tenant_id, project_id, thread_id)
    return thread_root / "workspace"
