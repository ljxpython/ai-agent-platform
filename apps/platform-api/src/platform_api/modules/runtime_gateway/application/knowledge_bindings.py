"""Mint existing resource bindings from authorized project and Thread identity."""

from collections.abc import Mapping


def build_knowledge_binding(
    mapping: Mapping[str, str], tenant_id: str, project_id: str, thread_id: str
) -> dict:
    resource = mapping.get(f"{tenant_id}:{project_id}")
    if resource is None:
        return {}
    return {
        "mcp": {
            "provider": "mcp_http",
            "resource_id": resource,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "thread_id": thread_id,
        }
    }
