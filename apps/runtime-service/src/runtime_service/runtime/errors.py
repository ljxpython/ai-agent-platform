"""Stable Runtime errors without sensitive payloads."""


class RuntimeErrorBase(ValueError):
    """Base error carrying only a stable code and optional field name."""

    def __init__(self, code: str, field: str | None = None) -> None:
        self.code = code
        self.field = field
        message = f"{code}: {field}" if field else code
        super().__init__(message)


class RuntimeResolutionError(RuntimeErrorBase):
    """Invalid Runtime contract or policy decision."""


class RuntimeAuthError(RuntimeErrorBase):
    """Invalid or unverifiable Runtime Delegation token."""


class RuntimeWorkspaceError(RuntimeError):
    """Must escape filesystem tools' ValueError-to-parameter-error handling."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


WORKSPACE_ERROR_CODES = frozenset(
    {
        "runtime.workspace.unavailable",
        "runtime.workspace.execution_unavailable",
        "runtime.workspace.backend_invalid",
        "runtime.workspace.image_invalid",
        "runtime.workspace.execution_outcome_unknown",
    }
)


def workspace_error_code(error: BaseException | None) -> str | None:
    if isinstance(error, RuntimeWorkspaceError) and error.code in WORKSPACE_ERROR_CODES:
        return error.code
    return None
