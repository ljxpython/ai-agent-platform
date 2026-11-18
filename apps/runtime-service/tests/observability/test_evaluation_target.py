from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from runtime_service.observability import evaluation_target as module
from runtime_service.runtime import RuntimeAuthError


@pytest.fixture
def target(monkeypatch):
    current = {
        "schema": "evaluation-runtime/v1",
        "manifest": {"package_sha256": "runtime"},
        "available": True,
        "resource_hash": "resources",
        "tools": [],
    }
    monkeypatch.setattr(module, "capabilities", lambda *args: deepcopy(current))
    context = {
        "model_id": "model",
        "max_tokens": 4096,
        "temperature": 0,
        "top_p": 1,
        "execution_mode": "standard",
    }
    expected = {
        "schema": "evaluation-target/v1",
        "agent": {"project_id": "project", "graph_id": "dearflow_agent"},
        "deployment": {
            "runtime": current["manifest"],
            "platform": {"package_sha256": "platform"},
        },
        "resources": {"runtime": deepcopy(current)},
        "context": context,
    }
    config = {
        "context": deepcopy(context),
        "metadata": {
            "evaluation_target": expected,
            "platform_build": expected["deployment"]["platform"],
        },
    }
    facts = NS(
        principal=NS(tenant_id="tenant", project_id="project"),
        scope=NS(assistant_id="dearflow_agent"),
    )
    return config, facts


def test_worker_accepts_matching_target_and_leaves_business_runs_alone(target):
    config, facts = target
    module.assert_target(config, facts)
    module.assert_target({}, facts)


@pytest.mark.parametrize(
    "change", ["project", "runtime", "platform", "model", "resources", "schema"]
)
def test_worker_rejects_drift_before_execution(target, change):
    config, facts = target
    expected = config["metadata"]["evaluation_target"]
    if change == "project":
        expected["agent"]["project_id"] = "other"
    elif change == "runtime":
        expected["deployment"]["runtime"] = {"package_sha256": "old"}
    elif change == "platform":
        config["metadata"]["platform_build"] = {"package_sha256": "old"}
    elif change == "model":
        config["context"]["model_id"] = "other"
    elif change == "resources":
        expected["resources"]["runtime"]["resource_hash"] = "changed"
    else:
        expected["schema"] = "unknown"
    with pytest.raises(RuntimeAuthError, match="runtime.evaluation.target_changed"):
        module.assert_target(config, facts)


def test_capabilities_only_expose_project_tools_and_no_connection_secrets(monkeypatch):
    monkeypatch.setattr(
        module,
        "mcp_connections",
        lambda: {
            "owned": {
                "scope": {"tenant_id": "t", "project_id": "p"},
                "allowed_tools": ["mcp_owned"],
                "secret": "do-not-export",
            },
            "other": {
                "scope": {"tenant_id": "t", "project_id": "other"},
                "allowed_tools": ["mcp_other"],
            },
        },
    )
    monkeypatch.setattr(module, "dynamic_knowledge_tools", lambda: ())
    monkeypatch.setattr(
        module, "package_digest", lambda _: module.STARTUP_MANIFEST["package_sha256"]
    )
    monkeypatch.setenv("RUNTIME_EVALUATION_EVIDENCE_ENABLED", "1")
    result = module.capabilities("t", "p")
    assert result["available"] is True
    assert result["tools"] == ["mcp_owned"]
    assert "do-not-export" not in str(result)
