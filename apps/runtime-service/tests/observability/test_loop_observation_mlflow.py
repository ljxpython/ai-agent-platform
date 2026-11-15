import asyncio
import json
from uuid import uuid4

import mlflow
import pytest
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.loop_detection import LoopDetectionMiddleware
from runtime_service.observability.mlflow_tracer import MLflowFailSoftCallback


@pytest.mark.parametrize("asynchronous", [False, True])
def test_observation_survives_mlflow_export_without_langfuse(
    tmp_path, monkeypatch, asynchronous
):
    from runtime_service.observability import langfuse as diagnostics

    monkeypatch.setenv("TRACING_PROVIDER", "mlflow")
    monkeypatch.setenv("AGENT_LOOP_OBSERVATION_ENABLED", "1")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    monkeypatch.setattr(diagnostics, "_client", None)
    previous_uri = mlflow.get_tracking_uri()
    mlflow.set_tracking_uri("sqlite:///" + str(tmp_path / "traces.db"))
    experiment_id = mlflow.create_experiment(
        "synthetic-observation", artifact_location=(tmp_path / "artifacts").as_uri()
    )
    experiment = mlflow.set_experiment(experiment_id=experiment_id)

    @tool
    def read_file(file_path: str) -> str:
        """Read synthetic content without touching a filesystem."""
        return "same synthetic content"

    responses = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": f"call-{i}",
                    "name": "read_file",
                    "args": {"file_path": "/synthetic"},
                }
            ],
        )
        for i in range(4)
    ] + [AIMessage(content="complete")]
    run_id = str(uuid4())
    graph = create_agent(
        BindableFakeMessagesChatModel(responses=responses),
        tools=[read_file],
        middleware=[LoopDetectionMiddleware(["read_file"], observe_only=True)],
    )
    callback = MLflowFailSoftCallback(
        graph_id="synthetic", bound_metadata={"run_id": run_id}
    )
    config = {
        "callbacks": [callback],
        "metadata": {"run_id": run_id},
        "recursion_limit": 100,
    }
    try:
        payload = {"messages": [("user", "bounded synthetic observation")]}
        result = (
            asyncio.run(graph.ainvoke(payload, config))
            if asynchronous
            else graph.invoke(payload, config)
        )
        assert result["messages"][-1].content == "complete"
        mlflow.flush_trace_async_logging()
        traces = mlflow.search_traces(
            locations=[experiment.experiment_id], return_type="list"
        )
        assert len(traces) == 1
        events = [
            event
            for span in traces[0].data.spans
            for event in span.events
            if event.name.startswith("runtime.loop.observation")
        ]
        assert sorted(event.name for event in events) == [
            "runtime.loop.observation",
            "runtime.loop.observation.completed",
            "runtime.loop.observation.started",
        ]
        summary = next(
            event.attributes for event in events if event.name.endswith(".completed")
        )
        assert summary["eligible_batches"] == 4
        assert summary["signals"] == 1
        assert summary["run_id"] == run_id
        owners = {event.attributes["observation_id"] for event in events}
        assert len(owners) == 1
        assert len(next(iter(owners))) == 64
        assert "/synthetic" not in json.dumps([event.attributes for event in events])
    finally:
        mlflow.set_tracking_uri(previous_uri)
