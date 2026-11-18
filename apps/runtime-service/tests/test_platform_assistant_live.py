"""Opt-in real-model + real signed HTTP reads against isolated synthetic API data."""

import asyncio
import json
import os
import re
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from runtime_service.services.platform_assistant.agent import CurrentAuthorization
from runtime_service.services.platform_assistant.approval import create_platform_agent
from runtime_service.services.platform_assistant.prompts import SYSTEM_PROMPT
from runtime_service.services.platform_assistant.tools import make_tools

pytestmark = pytest.mark.skipif(
    os.getenv("ASSISTANT_LIVE_TEST") != "1", reason="Opt-in real model calls"
)


def test_live_model_and_signed_api(monkeypatch, tmp_path):
    repo = Path(__file__).resolve().parents[3]
    api = repo / "apps/platform-api"
    output = Path(os.environ.get("ASSISTANT_VALIDATION_OUTPUT", str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            str(api / ".venv/bin/python"),
            str(api / "tests/assistant_validation_server.py"),
            str(output),
        ],
        cwd=api,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    results = []
    history_counts = {}
    try:
        line = process.stdout.readline()
        if not line:
            raise AssertionError(
                "Validation API failed to start: " + process.stderr.read()[-1200:]
            )
        config = json.loads(line)
        base = f"http://127.0.0.1:{config['port']}"
        for _ in range(100):
            try:
                if (
                    httpx.get(base + "/validation/health", trust_env=False).status_code
                    == 200
                ):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        else:
            raise AssertionError("Validation API startup timeout")
        monkeypatch.setenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", base)
        monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", config["secret"])
        facts = SimpleNamespace(
            principal=SimpleNamespace(
                user_id=config["actor_id"], project_id=config["project_id"]
            )
        )
        model = ChatOpenAI(
            **config["model"], temperature=0, max_tokens=5000, timeout=60, max_retries=0
        )

        def new_agent():
            return create_platform_agent(
                model,
                tools=make_tools(facts),
                system_prompt=SYSTEM_PROMPT,
                middleware=[
                    CurrentAuthorization(facts),
                    ModelCallLimitMiddleware(run_limit=8, exit_behavior="end"),
                    ToolCallLimitMiddleware(run_limit=10, exit_behavior="end"),
                ],
                checkpointer=InMemorySaver(),
            )

        async def ask(name, question, *, agent=None):
            agent = agent or new_agent()
            invocation = {
                "configurable": {"thread_id": config["thread_id"]},
                "metadata": {"run_id": str(uuid4())},
                # Middleware uses graph steps too; model/tool budgets remain 8/10.
                "recursion_limit": 100,
            }
            try:
                state = await agent.ainvoke(
                    {"messages": [HumanMessage(content=question)]}, invocation
                )
            except Exception as error:
                snapshot = await agent.aget_state(invocation)
                partial = snapshot.values.get("messages", [])
                (output / "failure.json").write_text(
                    json.dumps(
                        {
                            "case": name,
                            "error": type(error).__name__,
                            "model_calls": sum(m.type == "ai" for m in partial),
                            "tools": [
                                m.name for m in partial if isinstance(m, ToolMessage)
                            ],
                        },
                        indent=2,
                    )
                )
                raise
            messages = state["messages"][history_counts.get(agent, 0) :]
            history_counts[agent] = len(state["messages"])
            final = messages[-1].text
            assert messages[-1].response_metadata.get("finish_reason") != "length", (
                "Model answer was truncated"
            )
            tools = [
                {
                    "name": m.name,
                    "data": json.loads(m.content)
                    if m.content.startswith("{")
                    else m.content,
                }
                for m in messages
                if isinstance(m, ToolMessage)
            ]
            result = {
                "case": name,
                "question": question,
                "answer": final,
                "tools": tools,
            }
            evidence_ids = {
                t["data"]["evidence_id"]
                for t in tools
                if isinstance(t["data"], dict) and "evidence_id" in t["data"]
            }
            citations = re.findall(r"\[证据[:：]([^\]]+)\]", final)
            if any(value not in evidence_ids for value in citations):
                (output / "citation-failure.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2)
                )
            assert all(value in evidence_ids for value in citations), (
                "Answer must copy exact evidence IDs from this turn"
            )
            assert "SYNTHETIC-DO-NOT-RETURN" not in json.dumps(result)
            results.append(result)
            (output / "results.json").write_text(
                json.dumps(
                    {"model": config["model"]["model"], "results": results},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            print(
                f"{name}: {len(tools)} tool results, {len(final)} answer characters",
                flush=True,
            )
            return result

        async def run():
            if os.getenv("ASSISTANT_VALIDATION_DIAGNOSTICS_ONLY") == "1":
                agent = new_agent()
                failure = await ask(
                    "pre_agent_failure",
                    f"帮我排查运行：thread_id={config['target_thread_id']}，run_id={config['cases']['pre_agent']}。发生时间未知，诊断包今天才生成。请查证后给出原因和下一步。",
                    agent=agent,
                )
                assert "ExecutionSkillsMiddleware.before_agent" in failure["answer"]
                assert "不是模型调用失败" not in failure["answer"]
                assert any(
                    t["name"] == "read_run_diagnostics" for t in failure["tools"]
                )
                continued = await ask(
                    "continue_failure", "你继续帮我排查。", agent=agent
                )
                assert any(
                    t["name"] in {"read_run_diagnostics", "read_run_logs"}
                    for t in continued["tools"]
                )
                assert "已超出默认日志窗口" not in continued["answer"]
                capacity = await ask(
                    "current_sources",
                    "你能读取当前服务的日志吗？你知道日志存放在哪里吗？你知道查哪些数据库吗？请实际查一下，并解释刚才的review是否说明我没审批、not_configured是否说明当时没采集。",
                    agent=agent,
                )
                assert any(t["name"] == "list_databases" for t in capacity["tools"])
                assert any(
                    t["name"] == "read_run_diagnostics" for t in capacity["tools"]
                )
                fallback = await ask(
                    "request_fallback",
                    f"请排查thread_id={config['target_thread_id']}、run_id={config['cases']['request_fallback']}的关联日志，说明实际关联方式和时间范围。",
                )
                assert any(
                    t["name"] == "read_run_logs"
                    and isinstance(t["data"], dict)
                    and t["data"]["data"]["correlation_type"] == "execution_request_id"
                    and t["data"]["data"]["total"] == 1
                    for t in fallback["tools"]
                )
                assert "graph-1" not in fallback["answer"]
                assert "供应商侧按 request_id" not in fallback["answer"]
                assert not any(
                    t["name"] in {"search_project_logs", "search_public_web"}
                    for r in results
                    for t in r["tools"]
                )
                return
            smalltalk = await ask("ordinary_chat", "你好，讲一个一句话的程序员笑话。")
            assert not smalltalk["tools"]
            docs = await ask(
                "guide_cross_document",
                "如何创建Agent，再聊天并把历史对话转为评测集？按当前页面给我步骤。",
            )
            ids = {
                s["document_id"]
                for t in docs["tools"]
                if t["name"] == "search_documents" and isinstance(t["data"], dict)
                for s in t["data"].get("data", {}).get("sources", [])
            }
            assert {"agents", "evaluation"} <= ids
            assert "[证据:" in docs["answer"]
            knowledge = await ask(
                "guide_known_gap", "知识库页面点确认提交入库就真的上传成功了吗？"
            )
            assert any(t["name"] == "search_documents" for t in knowledge["tools"])
            assert "没有" in knowledge["answer"] or "未" in knowledge["answer"]
            for name, run_id in config["cases"].items():
                question = f"请排查业务项目运行，thread_id={config['target_thread_id']}，run_id={run_id}。先核对诊断和日志（必要时），说明事实、可能原因、谁该做什么及缺失证据，不要执行修复。"
                if name == "interrupted":
                    question += "我刚主动停止了这次运行，请区分停止与失败。"
                result = await ask(name, question)
                assert any(t["name"] == "read_run_diagnostics" for t in result["tools"])
                assert not any(
                    t["name"] == "search_project_logs" for t in result["tools"]
                ), "Run-scoped investigation must not expand to project logs"
                assert "[证据:" in result["answer"]
                if name == "recovered":
                    assert "成功" in result["answer"]
                if name == "interrupted":
                    assert "停止" in result["answer"] or "中断" in result["answer"]
                if name == "running":
                    assert (
                        "运行中" in result["answer"] or "正在运行" in result["answer"]
                    )
                if name == "unavailable":
                    assert any(
                        word in result["answer"] for word in ("无法", "不能", "不足")
                    )
            missing = await ask(
                "missing_run",
                "我在配置页还没点发送就出现前端渲染报错，尚未创建运行，没有Thread或Run编号。你能替我修好吗？",
            )
            assert not any(
                t["name"] in {"read_run_diagnostics", "read_run_logs"}
                for t in missing["tools"]
            )
            follow = new_agent()
            await ask(
                "before_guide_update",
                "平台助手怎么开启新的独立会话？按钮叫什么？",
                agent=follow,
            )
            response = httpx.post(
                base + "/validation/update-guide",
                headers={"x-validation-key": config["secret"]},
                trust_env=False,
            )
            response.raise_for_status()
            updated = await ask(
                "after_guide_update",
                "资料刚更新了，现在新建会话按钮叫什么？请按当前指南确认。",
                agent=follow,
            )
            assert "新对话验证" in updated["answer"]
            assert any(
                "新对话验证" in str(t["data"])
                for t in updated["tools"]
                if t["name"] == "search_documents"
            )

        asyncio.run(run())
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
