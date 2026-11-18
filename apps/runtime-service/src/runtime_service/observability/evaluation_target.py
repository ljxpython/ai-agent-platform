"""Worker-owned deployment identity; consumers never inspect another checkout."""

import hashlib
import json
import os
from pathlib import Path

from runtime_service.build_info import STARTUP_MANIFEST, package_digest
from runtime_service.runtime.mcp_config import dynamic_knowledge_tools, mcp_connections


def capabilities(tenant_id, project_id):
    connections = {
        key: value
        for key, value in mcp_connections().items()
        if value["scope"] == {"tenant_id": tenant_id, "project_id": project_id}
    }
    resources = {
        "mcp": connections,
        "knowledge_gateway": os.getenv("RUNTIME_KNOWLEDGE_MCP_GATEWAY_URL", ""),
        "knowledge_sources_version": os.getenv(
            "RUNTIME_KNOWLEDGE_SOURCES_VERSION", "1"
        ),
        "workspace_backend": os.getenv("RUNTIME_BACKEND", "local"),
        "workspace_image": os.getenv(
            "RUNTIME_WORKSPACE_IMAGE", "runtime-agent-workspace:p5"
        ),
    }
    tools = set(dynamic_knowledge_tools())
    for connection in connections.values():
        tools.update(connection.get("allowed_tools", []))
    return {
        "schema": "evaluation-runtime/v1",
        "manifest": dict(STARTUP_MANIFEST),
        "available": os.getenv("RUNTIME_EVALUATION_EVIDENCE_ENABLED") == "1"
        and package_digest(Path(__file__).parents[1])
        == STARTUP_MANIFEST["package_sha256"],
        "resource_hash": hashlib.sha256(
            json.dumps(resources, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "tools": sorted(tools),
    }


def assert_target(config, facts):
    target = (config.get("metadata") or {}).get("evaluation_target")
    if target is None:
        return
    current = capabilities(facts.principal.tenant_id, facts.principal.project_id)
    context = config.get("context") or {}
    if (
        not isinstance(target, dict)
        or target.get("schema") != "evaluation-target/v1"
        or target.get("agent", {}).get("project_id") != facts.principal.project_id
        or target.get("agent", {}).get("graph_id") != facts.scope.assistant_id
        or current.get("available") is not True
        or target.get("deployment", {}).get("runtime") != current["manifest"]
        or target.get("deployment", {}).get("platform")
        != (config.get("metadata") or {}).get("platform_build")
        or target.get("resources", {}).get("runtime") != current
        or any(
            context.get(key) != target.get("context", {}).get(key)
            for key in (
                "model_id",
                "temperature",
                "max_tokens",
                "top_p",
                "execution_mode",
            )
        )
    ):
        from runtime_service.runtime import RuntimeAuthError

        raise RuntimeAuthError("runtime.evaluation.target_changed")
