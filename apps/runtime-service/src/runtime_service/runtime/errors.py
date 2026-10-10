"""Stable Runtime errors without sensitive payloads."""


class RuntimeErrorBase(ValueError):
    """Base error carrying only a stable code and optional field name."""

    def __init__(self, code: str, field: str | None = None) -> None:
        self.code = code
        self.field = field
        self.model_error_code: str | None = None
        message = f"{code}: {field}" if field else code
        super().__init__(message)


class RuntimeResolutionError(RuntimeErrorBase):
    """Invalid Runtime contract or policy decision."""


class RuntimeAuthError(RuntimeErrorBase):
    """Invalid or unverifiable Runtime Delegation token."""


class RuntimeExecutionError(RuntimeErrorBase):
    """Confirmed execution failure; Worker must not requeue it as infrastructure failure."""


class TokenBudgetExceededError(RuntimeExecutionError):
    """A new operation was refused after the native Run token cap."""

    def __init__(self) -> None:
        super().__init__("runtime.token_budget.exhausted")


class TokenBudgetUnverifiableError(RuntimeExecutionError):
    """A new operation was refused because usage cannot be verified."""

    def __init__(self) -> None:
        super().__init__("runtime.token_budget.unverifiable")


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
