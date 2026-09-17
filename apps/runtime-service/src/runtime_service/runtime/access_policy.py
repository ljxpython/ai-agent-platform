"""Trusted session access policies for Deep Agents tool interrupts."""

from collections.abc import Mapping

from runtime_service.runtime.errors import RuntimeResolutionError

REVIEW = "review"
WORKSPACE_WRITE = "workspace_write"
FULL_ACCESS = "full_access"
ACCESS_POLICIES = frozenset((REVIEW, WORKSPACE_WRITE, FULL_ACCESS))
WORKSPACE_WRITE_TOOLS = frozenset(("write_file", "edit_file", "execute"))


def interrupts_for_access_policy(
    policy: str | None, approvals: Mapping[str, object]
) -> dict[str, object]:
    effective = REVIEW if policy is None else policy
    if effective not in ACCESS_POLICIES:
        raise RuntimeResolutionError("runtime.context.invalid_value", "access_policy")
    if effective == FULL_ACCESS:
        return {}
    if effective == REVIEW:
        return dict(approvals)
    return {name: value for name, value in approvals.items() if name not in WORKSPACE_WRITE_TOOLS}
