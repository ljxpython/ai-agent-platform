"""Offline characterization of the real Dear assembly, not an acceptance suite.

Run from the repository root with apps/runtime-service/.venv/bin/python.
Fake model outputs; real graph/tools, temporary workspace, no provider calls.
Assertions pin observed gaps so a future fix requires updating this evidence.
"""

import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [
    str(ROOT / "apps/runtime-service/src"),
    str(ROOT / "apps/runtime-service/tests"),
]

from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402
from langgraph.types import Command  # noqa: E402
from pytest import MonkeyPatch  # noqa: E402
from services.dearflow_agent.test_agent import build, call, config  # noqa: E402

from runtime_service.runtime import runtime_context_hash  # noqa: E402
from runtime_service.services.dearflow_agent.workspace.backend import (  # noqa: E402
    DearWorkspaceBackend,
)


async def probe(name, responses, *, mode="standard", approve=False, limit=None):
    with TemporaryDirectory(prefix="dear-effect-probe-") as directory:
        with MonkeyPatch.context() as patch:
            patch.setenv("RUNTIME_DEAR_GOVERNANCE_ENABLED", "0")
            patch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", "{}")
            patch.setenv("TAVILY_API_KEY", "")
            if limit:
                patch.setenv("AGENT_MODEL_CALL_LIMIT_PER_RUN", str(limit))
            cfg = config()
            cfg["context"] = {"execution_mode": mode}
            cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
                runtime_context_hash(cfg["context"])
            )
            create = build.__wrapped__(patch, Path(directory))
            graph, cfg = await create(responses, cfg)
            result = await graph.ainvoke(
                {"messages": [("user", "Complete the task and report honestly.")]},
                cfg,
                context=cfg["context"],
            )
            pending = bool(result.get("__interrupt__"))
            if pending and approve:
                result = await graph.ainvoke(
                    Command(resume={"decisions": [{"type": "approve"}]}),
                    cfg,
                    context=cfg["context"],
                )
            root = DearWorkspaceBackend("tenant", "project", "dear-thread").root
            messages = result["messages"]
            tools = [m for m in messages if isinstance(m, ToolMessage)]
            return {
                "probe": name,
                "reached_approval": pending,
                "final_text": messages[-1].content,
                "model_messages": sum(isinstance(m, AIMessage) for m in messages),
                "tool_messages": len(tools),
                "tool_statuses": [m.status for m in tools],
                "todos": result.get("todos"),
                "created_file": (root / "work/probe.txt").exists(),
            }


async def main():
    results = []
    for reason in ("length", "content_filter"):
        message = call(
            "write_file",
            {"file_path": "/workspace/work/probe.txt", "content": "partial output"},
        )
        message.response_metadata = {"finish_reason": reason}
        row = await probe(reason, [message, AIMessage(content="done")], approve=True)
        assert row["reached_approval"] and row["created_file"], row
        results.append(row)
    row = await probe(
        "empty_after_tool",
        [call("ls", {"path": "/workspace/work/"}), AIMessage(content="")],
    )
    assert row["final_text"] == "", row
    results.append(row)
    row = await probe(
        "failed_read_then_claim_done",
        [
            call("read_file", {"file_path": "/workspace/work/missing.txt"}),
            AIMessage(content="The missing file was read and verified successfully."),
        ],
    )
    assert row["final_text"].endswith("successfully."), row
    results.append(row)
    row = await probe(
        "six_identical_calls",
        [call("ls", {"path": "/workspace/work/"}, f"repeat-{i}") for i in range(6)]
        + [AIMessage(content="done")],
    )
    assert row["tool_messages"] == 6, row
    results.append(row)
    row = await probe(
        "environment_model_limit_one",
        [
            call("ls", {"path": "/workspace/work/"}, "one"),
            call("ls", {"path": "/workspace/work/"}, "two"),
            AIMessage(content="done"),
        ],
        limit=1,
    )
    assert row["model_messages"] == 3, row
    results.append(row)
    row = await probe(
        "unfinished_todo_then_exit",
        [
            call(
                "write_todos",
                {
                    "todos": [
                        {"content": "Validate the result", "status": "in_progress"}
                    ]
                },
            ),
            AIMessage(content="All work is complete."),
        ],
        mode="pro",
    )
    assert row["todos"][0]["status"] == "in_progress", row
    assert row["final_text"] == "All work is complete.", row
    results.append(row)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
