"""Configuration gates only; never probe the runner or grant tool permissions."""

import os

from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.workspace.background import host_id


def query_enabled():
    return bool(os.getenv("DATABASE_URI"))


def start_enabled():
    if (
        not query_enabled()
        or os.getenv("RUNTIME_BACKEND", "docker") != "docker"
        or os.getenv("RUNTIME_BACKGROUND_TASKS_ENABLED") != "1"
    ):
        return False
    try:
        host_id()
    except RuntimeWorkspaceError:
        return False
    return True
