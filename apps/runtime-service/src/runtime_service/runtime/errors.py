"""Compatibility exports for the lightweight Runtime error contract."""

from runtime_service.errors import (
    WORKSPACE_ERROR_CODES,
    BackgroundTaskNotStarted,
    RuntimeAuthError,
    RuntimeErrorBase,
    RuntimeExecutionError,
    RuntimePrivacyError,
    RuntimeResolutionError,
    RuntimeWorkspaceError,
    TokenBudgetExceededError,
    TokenBudgetUnverifiableError,
    workspace_error_code,
)

__all__ = [
    "WORKSPACE_ERROR_CODES",
    "BackgroundTaskNotStarted",
    "RuntimeAuthError",
    "RuntimeErrorBase",
    "RuntimeExecutionError",
    "RuntimePrivacyError",
    "RuntimeResolutionError",
    "RuntimeWorkspaceError",
    "TokenBudgetExceededError",
    "TokenBudgetUnverifiableError",
    "workspace_error_code",
]
