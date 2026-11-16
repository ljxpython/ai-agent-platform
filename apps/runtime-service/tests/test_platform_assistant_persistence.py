"""Two-process approval recovery in this Worktree's PostgreSQL, without a sandbox."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def run_step(mode, thread_id, decision="approve", interrupt_id=""):
    import psycopg
    from dotenv import dotenv_values
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import ToolException, tool
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.types import Command

    from runtime_service.services.platform_assistant.approval import (
        create_platform_agent,
    )

    root = Path(__file__).resolve().parents[3]
    state = json.loads((root / ".local-stack/environment.json").read_text())
    assert Path(state["root"]) == root
    dsn = dotenv_values(root / ".local-stack/runtime.env")["DATABASE_URI"]
    assert (
        psycopg.conninfo.conninfo_to_dict(dsn)["dbname"]
        == state["databases"]["runtime"]
    )
    schema = "assistant_approval_test"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS assistant_approval_test")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS assistant_approval_test.write_attempts (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, thread_id text, value text)"
        )

    class Model(BaseChatModel):
        @property
        def _llm_type(self):
            return "deterministic-approval-test"

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, **kwargs):
            message = (
                AIMessage(content="completed")
                if any(isinstance(m, ToolMessage) for m in messages)
                else AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "test_write",
                            "args": {"value": "original-value"},
                            "id": "write1",
                            "type": "tool_call",
                        }
                    ],
                )
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

    @tool
    def test_write(value: str) -> str:
        """Isolated verification mutation, never exposed by a production graph."""
        if decision == "revoked":
            raise ToolException("business_permission_revoked")
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO assistant_approval_test.write_attempts(thread_id,value) VALUES (%s,%s)",
                (thread_id, value),
            )
        return "saved"

    test_write.handle_tool_error = True
    with PostgresSaver.from_conn_string(
        psycopg.conninfo.make_conninfo(dsn, options="-c search_path=" + schema)
    ) as saver:
        saver.setup()
        agent = create_platform_agent(
            Model(), tools=[], business_write_tools=[test_write], checkpointer=saver
        )
        config = {"configurable": {"thread_id": thread_id}}
        if mode == "start":
            result = agent.invoke(
                {"messages": [{"role": "user", "content": "test"}]}, config
            )
            interrupt = result["__interrupt__"][0]
            output = {"interrupt_id": interrupt.id, "value": interrupt.value}
        else:
            if mode == "resume":
                kind = "approve" if decision == "revoked" else decision
                agent.invoke(
                    Command(
                        resume={
                            interrupt_id: {
                                "decisions": [
                                    {
                                        "type": kind,
                                        **(
                                            {"message": "用户选择不执行"}
                                            if kind == "reject"
                                            else {}
                                        ),
                                    }
                                ]
                            }
                        }
                    ),
                    config,
                )
            output = {"pending": bool(agent.get_state(config).interrupts)}
        with psycopg.connect(dsn) as conn:
            output["writes"] = conn.execute(
                "SELECT count(*) FROM assistant_approval_test.write_attempts WHERE thread_id=%s",
                (thread_id,),
            ).fetchone()[0]
    return output


@pytest.mark.parametrize(
    "decision,expected", [("approve", 1), ("reject", 0), ("revoked", 0)]
)
def test_approval_survives_process_restart(decision, expected):
    if os.getenv("ASSISTANT_LOCAL_POSTGRES_TEST") != "1":
        pytest.skip("Explicit local Worktree PostgreSQL fixture required")
    thread_id = str(uuid4())

    def child(mode, interrupt_id=""):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                mode,
                thread_id,
                decision,
                interrupt_id,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])

    started = child("start")
    assert started["writes"] == 0
    assert started["value"]["review_configs"][0]["allowed_decisions"] == [
        "approve",
        "reject",
    ]
    assert child("inspect") == {"pending": True, "writes": 0}
    resumed = child("resume", started["interrupt_id"])
    assert resumed == {"pending": False, "writes": expected}
    assert child("resume", started["interrupt_id"])["writes"] == expected


if __name__ == "__main__":
    print(json.dumps(run_step(*sys.argv[1:]), ensure_ascii=False))
