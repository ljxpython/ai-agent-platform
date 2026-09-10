from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from platform_api.adapters.langgraph.parameter_schema import GraphParameterSchemaProvider
from platform_api.adapters.langgraph.graphs_sdk_adapter import LangGraphGraphsSdkAdapter
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ServiceUnavailableError


class GraphParameterSchemaProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_default_assistant_discovery_reads_all_pages(self):
        adapter = LangGraphGraphsSdkAdapter(base_url="http://runtime.test")
        adapter._client.request_json = AsyncMock(side_effect=[
            [{"graph_id": f"graph-{i}"} for i in range(1000)],
            [{"graph_id": "last-graph"}],
        ])
        result = await adapter.count()
        self.assertEqual(result, {"count": 1001})
        calls = adapter._client.request_json.await_args_list
        self.assertEqual([c.kwargs["payload"]["offset"] for c in calls], [0, 1000])
        self.assertTrue(all(c.kwargs["payload"]["metadata"] == {"created_by": "system"} for c in calls))

    async def test_gateway_graph_search_reads_registry(self):
        adapter = LangGraphGraphsSdkAdapter(base_url="http://runtime.test")
        adapter._client.request_json = AsyncMock(return_value=[{"graph_id": "beta"}, {"graph_id": "alpha"}])
        result = await adapter.search({"query": "a", "limit": 1, "offset": 1})
        self.assertEqual(result["items"], [{"graph_id": "beta", "description": ""}])
        self.assertEqual(result["total"], 2)
        self.assertEqual(await adapter.count({"query": "alpha"}), {"count": 1})
        self.assertTrue(all(call.args == ("POST", "/assistants/search") for call in adapter._client.request_json.await_args_list))

    async def test_remote_schema_exposes_only_public_parameters(self):
        actor = ActorContext(user_id="user")
        catalog = SimpleNamespace(get_graph_schema=AsyncMock(return_value={
            "graph_id": "remote_graph",
            "context_schema": {"properties": {
                "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                "tenant_id": {"type": "string"},
                "permissions": {"type": "array"},
                "runtime_model_ref": {"type": "string"},
                "tools": {"type": "array"},
                "system_prompt": {"type": "string"},
            }},
        }))
        result = await GraphParameterSchemaProvider(catalog).build_schema(
            "remote_graph", actor=actor, project_id="project",
        )
        catalog.get_graph_schema.assert_awaited_once_with(
            actor=actor, project_id="project", graph_id="remote_graph",
        )
        self.assertEqual(result["schema_version"], "remote-v1")
        self.assertNotIn("sources", result)
        context = next(s for s in result["sections"] if s["key"] == "context")
        self.assertEqual(context["properties"], {
            "temperature": {"type": "number", "minimum": 0, "maximum": 2},
        })
        self.assertNotIn("configurable", {s["key"] for s in result["sections"]})

    async def test_invalid_or_unavailable_schema_has_no_fallback(self):
        catalog = SimpleNamespace(get_graph_schema=AsyncMock())
        provider = GraphParameterSchemaProvider(catalog)
        for response in ({}, {"graph_id": "other"}, {"graph_id": "agent", "context_schema": []}):
            catalog.get_graph_schema.return_value = response
            with self.assertRaises(ServiceUnavailableError):
                await provider.build_schema("agent", actor=ActorContext(), project_id="project")
        catalog.get_graph_schema.side_effect = ServiceUnavailableError(message="offline")
        with self.assertRaises(ServiceUnavailableError):
            await provider.build_schema("agent", actor=ActorContext(), project_id="project")
