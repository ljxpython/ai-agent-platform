"""Mint existing resource bindings from authorized project and Thread identity."""

from collections.abc import Mapping


def build_knowledge_binding(
    mapping: Mapping[str, str],
    tenant_id: str,
    project_id: str,
    thread_id: str,
    knowledge_secret: str | None = None,
    gateway_url: str | None = None,
    project_name: str | None = None,
) -> dict:
    resource = mapping.get(f"{tenant_id}:{project_id}")
    if resource is None and not knowledge_secret:
        return {}
    is_dynamic = resource is None
    resource = resource or f"knowledge_{project_id}"
    from uuid import UUID

    kb_id = "kb_" + UUID(project_id).hex
    binding = {
        "provider": "mcp_http",
        "resource_id": resource,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "thread_id": thread_id,
    }
    if is_dynamic and knowledge_secret:
        from platform_api.modules.knowledge.authorization import mint_knowledge_jwt

        token = mint_knowledge_jwt(
            secret=knowledge_secret,
            tenant_id=tenant_id,
            project_id=project_id,
            knowledge_base_id=kb_id,
            project_name=project_name,
        )
        binding["auth_token"] = token
        if gateway_url:
            if not gateway_url.endswith("/mcp"):
                gateway_url = gateway_url.rstrip("/") + "/mcp"
            binding["gateway_url"] = gateway_url
    return {"mcp": binding}
