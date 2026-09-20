"""Apply signed restrictions to direct HTTP operations as well as Agent calls."""
from fastapi import HTTPException

from runtime_service.runtime.capabilities import graph_tools
from runtime_service.runtime.resolver import parse_runtime_policy
from runtime_service.runtime.errors import RuntimeResolutionError


def require_tool_access(facts: dict, *names: str) -> None:
    scope = facts.get("runtime_scope", {})
    try:
        declared = set(graph_tools(scope["assistant_id"]))
        policy = parse_runtime_policy(facts["runtime_policy"])
        denied = set(policy.denied_tool_names)
        if denied - declared or set(names) - (declared - denied):
            raise ValueError("tool denied")
    except (KeyError, ValueError, RuntimeResolutionError) as exc:
        raise HTTPException(403, {"code": "runtime.tool.not_allowed"}) from exc
