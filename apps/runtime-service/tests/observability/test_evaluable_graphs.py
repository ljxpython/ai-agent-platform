"""Tests for multi-graph evaluation capability declarations and target hooks."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from runtime_service import webapp
from runtime_service.observability import evaluation_hooks, evaluation_target
from runtime_service.runtime import RuntimeAuthError


def test_graph_capability_exposes_evaluation_for_evaluable_graphs(monkeypatch):
    async def fake_auth(_auth):
        return {}

    monkeypatch.setattr(webapp, "authenticate", fake_auth)
    monkeypatch.setattr(
        evaluation_hooks,
        "capabilities",
        lambda tenant_id, project_id: {
            "schema": "evaluation-runtime/v1",
            "available": True,
            "tenant_id": tenant_id,
            "project_id": project_id,
        },
    )

    for graph_id in (
        "dearflow_agent",
        "showcase_demo",
        "reference_agent",
        "workflow_demo",
    ):

        async def auth_graph(_auth, gid=graph_id):
            return {
                "runtime_scope": {
                    "assistant_id": gid,
                    "operation": "read",
                    "tenant_id": "t1",
                    "project_id": "p1",
                }
            }

        monkeypatch.setattr(webapp, "authenticate", auth_graph)
        res = asyncio.run(webapp.graph_capability(graph_id, "Bearer tok"))
        assert "evaluation" in res
        features = res["evaluation"]["graph_features"]
        assert features["workspace_files"] is (
            graph_id in {"dearflow_agent", "showcase_demo"}
        )

    async def auth_assistant(_auth):
        return {
            "runtime_scope": {
                "assistant_id": "platform_assistant",
                "operation": "read",
                "tenant_id": "t1",
                "project_id": "p1",
            }
        }

    monkeypatch.setattr(webapp, "authenticate", auth_assistant)
    assistant_res = asyncio.run(
        webapp.graph_capability("platform_assistant", "Bearer tok")
    )
    assert "evaluation" not in assistant_res


def test_verify_evaluation_target_checks_non_dearflow_graphs(monkeypatch):
    current = {
        "schema": "evaluation-runtime/v1",
        "manifest": {"package_sha256": "runtime"},
        "available": True,
        "resource_hash": "resources",
        "tools": [],
    }
    monkeypatch.setattr(
        evaluation_target, "capabilities", lambda *args: deepcopy(current)
    )
    context = {"model_id": "model", "max_tokens": 4096, "temperature": 0, "top_p": 1}
    config = {
        "context": deepcopy(context),
        "metadata": {
            "platform_build": {"package_sha256": "platform"},
            "evaluation_target": {
                "schema": "evaluation-target/v1",
                "agent": {"project_id": "p1", "graph_id": "reference_agent"},
                "deployment": {
                    "runtime": current["manifest"],
                    "platform": {"package_sha256": "platform"},
                },
                "resources": {"runtime": deepcopy(current)},
                "context": context,
            },
        },
    }
    facts = NS(
        principal=NS(tenant_id="t1", project_id="p1"),
        scope=NS(assistant_id="reference_agent"),
    )
    asyncio.run(evaluation_hooks.verify_evaluation_target(config, facts))

    config["metadata"]["evaluation_target"]["agent"]["graph_id"] = "workflow_demo"
    with pytest.raises(RuntimeAuthError, match="runtime.evaluation.target_changed"):
        asyncio.run(evaluation_hooks.verify_evaluation_target(config, facts))
