from typing import Literal

ModelErrorCode = Literal[
    "provider_rate_limited",
    "provider_overloaded",
    "context_too_long",
    "model_unavailable",
    "provider_auth_failed",
    "provider_access_denied",
    "provider_timeout",
    "provider_unavailable",
    "model_call_failed",
]
WorkspaceErrorCode = Literal[
    "runtime.workspace.unavailable",
    "runtime.workspace.execution_unavailable",
    "runtime.workspace.backend_invalid",
    "runtime.workspace.image_invalid",
    "runtime.workspace.execution_outcome_unknown",
]
