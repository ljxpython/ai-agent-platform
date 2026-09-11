"""Schema requests must neither require execution credentials nor allow execution."""

import asyncio

import pytest

from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.services.demo.workflow_demo import agent as workflow
from runtime_service.services.reference_agent import agent as reference


@pytest.mark.parametrize("module,graph_id", [(workflow, "workflow_demo"), (reference, "reference_agent")])
@pytest.mark.parametrize("reading", ["schema", "state", "checkpoint"])
def test_deployment_schema_is_available_without_model_access(module, graph_id, reading, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Schema introspection attempted to build an execution model")

    monkeypatch.setattr(module, "build_model", forbidden)

    async def check():
        configurable = {"graph_id": graph_id} if reading == "schema" else {"thread_id": "read-only-test"}
        if reading == "checkpoint":
            configurable["checkpoint_id"] = "read-checkpoint"
        graph = await module.get_agent({"configurable": configurable})
        assert "messages" in graph.get_input_jsonschema()["properties"]
        assert "model_id" in graph.get_context_jsonschema()["properties"]
        with pytest.raises(RuntimeAuthError):
            await graph.ainvoke(
                {"messages": [{"role": "user", "content": "must not execute"}]},
                {"configurable": {"thread_id": "schema-only-test"}},
            )
    asyncio.run(check())
