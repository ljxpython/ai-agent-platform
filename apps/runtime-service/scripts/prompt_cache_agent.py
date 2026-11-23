"""Two-turn live DearFlow experiment; synthetic identity, files and memory only."""

from __future__ import annotations

import asyncio
import copy
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from langchain_core.messages import HumanMessage, ToolMessage
from prompt_cache_cases import (
    MODEL_ID,
    MODEL_NAME,
    capture,
    digest,
    fixed_history,
    legacy_layout,
    move_context,
    read_pair,
    source_fingerprints,
    source_table,
    text_slots,
)
from prompt_cache_experiment import collect, load_connection, report, write_json


async def run_agent(
    output, connection, *, client=None, factor="date", product_layout=False
):
    output.mkdir(parents=True, exist_ok=False)
    nonce = uuid4().hex
    task = {
        "first": "请先用 read_file 读取 /workspace/work/data.csv，计算 units 总和。结合本轮有效记忆回答总和及 Python 测试首选；不写文件、不调用其他工具。",
        "second": "话题切换到前端。请先读取 /workspace/work/data2.csv，计算 units 总和，结合本轮有效记忆回答总和及前端首选；不写文件、不调用其他工具。",
        "files": {
            "data.csv": "name,units\na,10\nb,20\nc,30\n",
            "data2.csv": "name,units\nx,12\ny,18\nz,30\n",
        },
        "memories": ["Python 测试首选 pytest。", "前端首选 Vue 3，使用 TypeScript。"],
        "criteria": "Both totals=60; pytest then Vue; both files actually read; no approval, other tool or side effect.",
    }
    if factor in {"date", "combined"}:
        task["first"] = (
            "请先用 read_file 读取 /workspace/work/data.csv，计算 units 总和，并输出本轮 current_date 的 UTC 日期。不写文件、不调用其他工具。"
        )
        task["second"] = (
            "请先读取 /workspace/work/data2.csv，计算 units 总和，并输出本轮 current_date 的 UTC 日期。不写文件、不调用其他工具。"
        )
        task["memories"] = ["项目统计单位为件。", "项目统计单位为件。"]
        task["criteria"] = (
            "Both totals=60; UTC dates 2026-11-23 then simulated 2026-11-24; both files actually read; no other tool/approval."
        )
        if factor == "combined":
            task["first"] += "同时回答本轮记忆中的 Python 测试首选。"
            task["second"] += "同时回答本轮记忆中的前端首选。"
            task["memories"] = [
                "Python 测试首选 pytest。",
                "前端首选 Vue 3，使用 TypeScript。",
            ]
            task["criteria"] += (
                " Also pytest then Vue; current memory is not persisted."
            )
    elif factor == "summary":
        task["first"] = (
            "已读取的最新合成文件中 ITEM-0000 的 units 是多少？只输出整数，不调用工具。"
        )
        task["files"] = {}
        task["memories"] = ["", ""]
        task["criteria"] = (
            "Real summary then final answer 10; seven predeclared historical read_file results, 3000 rows each; no new tool."
        )
        task["historical_files"] = {"count": 7, "rows": 3000}
    elif factor != "memory":
        raise ValueError("Expected date, memory, combined or summary factor")
    case = {
        "date": "AGENT-C03",
        "memory": "AGENT-C02",
        "summary": "C05-summary",
        "combined": "AGENT-combined",
    }[factor]
    manifest = {
        "version": 1,
        "material": "synthetic",
        "layer": "live_agent_in_process",
        "model_id": connection.get("model_id", MODEL_ID),
        "model": connection.get("model", MODEL_NAME),
        "route": connection.get("route", "xiaok"),
        "layout": "reconstructed_legacy_vs_actual_product"
        if product_layout
        else "legacy_replay_candidate",
        "task": task,
        "nonce": nonce,
        "records": [],
        "limits": "Synthetic trusted identity and memory source; no Platform HTTP authentication or production ACL evidence. Memory extraction and custom/MCP data sources mocked. Provider replies and read_file are real.",
    }
    registration = {
        "started_at": datetime.now(UTC).isoformat(),
        "pre_registered_task_sha256": digest(task),
        "pricing": connection["pricing"],
        "pricing_reference": connection.get("pricing_reference"),
        "connection_fingerprint": connection["connection_fingerprint"],
        "environment_id": connection["environment_id"],
        "max_requests": 16,
        "retries": 0,
        "attempted": 0,
        "stop_reason": None,
        "manifest_sha256": digest(manifest),
        "source_sha256": source_fingerprints(),
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "registration.json", registration)
    tasks = []
    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(120), follow_redirects=False
    )
    stopped = False
    try:
        for group in ("A",) if factor == "summary" else ("A", "B"):
            lane = digest({"nonce": nonce, "group": group})[:24]
            group_calls = []

            async def respond(
                request, *, group=group, lane=lane, group_calls=group_calls
            ):
                nonlocal stopped
                if stopped or len(group_calls) >= 8:
                    raise RuntimeError("Agent experiment dispatch stopped")
                baseline = json.loads(request.content)
                payload = copy.deepcopy(baseline)
                if product_layout and group == "B":
                    baseline = legacy_layout(baseline)
                if group == "B" and not product_layout:
                    for tag in (
                        ("memory", "date") if factor == "combined" else (factor,)
                    ):
                        payload = move_context(payload, tag)
                if connection.get("route") == "deepseek_official":
                    payload["model"] = connection["model"]
                    payload["thinking"] = {"type": "disabled"}
                container, key = text_slots(payload["messages"][0])[0]
                container[key] = (
                    f"<cache_experiment_lane>{lane}</cache_experiment_lane>\n"
                    + container[key]
                )
                index = len(group_calls)
                row = {
                    "id": f"{case}-{group}-r0-t{index}",
                    "case": case,
                    "group": group,
                    "repeat": 0,
                    "turn": index,
                    "expected": "60",
                    "execution_eligible": True,
                    "payload": payload,
                    "payload_sha256": digest(payload),
                    "baseline": baseline,
                    "baseline_sha256": digest(baseline),
                }
                manifest["records"].append(row)
                registration["attempted"] += 1
                registration["inflight_request"] = row["id"]
                registration["manifest_sha256"] = digest(manifest)
                write_json(output / "manifest.json", manifest)
                write_json(output / "registration.json", registration)
                result = await collect(client, connection, row)
                result["quality_pass"] = None
                result["quality_method"] = (
                    "evaluated per complete Agent turn, not per tool-call response"
                )
                write_json(output / (row["id"] + ".json"), result)
                group_calls.append(result)
                registration.pop("inflight_request", None)
                if (
                    result["status"] != "completed"
                    or result["usage"]["quality"]
                    not in {"reported", "derived_from_reported"}
                    or result["cache_normalization_matches"] is False
                    or result["usage"]["tokens"]["cache_read_tokens"] is None
                ):
                    stopped = True
                    raise RuntimeError("Provider evidence failed; no retry")
                # Buffer only between provider and local SDK. Provider TTFT is measured
                # by collect; this is not a frontend/UI streaming latency experiment.
                body = "\n\n".join(
                    "data: " + json.dumps(e["data"]) for e in result["events"]
                )
                return httpx.Response(
                    200,
                    text=body + "\n\ndata: [DONE]\n\n",
                    headers={"Content-Type": "text/event-stream"},
                )

            fixture = {
                "case": case,
                "turn": 0,
                "thread": f"live-{nonce[:12]}-{group}",
                "date": "2026-11-23",
                "model": connection.get("model", MODEL_NAME),
                "protocol": "deepseek"
                if connection.get("route") == "deepseek_official"
                else "openai-compatible",
                "memory": task["memories"][0],
                "messages": [HumanMessage(content=task["first"])],
                "files": task["files"],
                "continuations": [
                    {
                        "memory": task["memories"][1],
                        "question": task["second"],
                        **(
                            {"date": "2026-11-24"}
                            if factor in {"date", "combined"}
                            else {}
                        ),
                    }
                ],
            }
            if factor == "summary":
                history = fixed_history()
                for index in range(7):
                    history += read_pair(
                        f"/workspace/work/long-{index}.csv",
                        source_table(3000),
                        f"source-{index}",
                    )
                fixture["messages"] = [*history, HumanMessage(content=task["first"])]
                fixture["continuations"] = []
            initial_calls = {
                call["id"]
                for message in fixture["messages"]
                for call in getattr(message, "tool_calls", [])
            }
            try:
                result = await capture(
                    fixture,
                    output / "workspaces",
                    responder=respond,
                    layout="product" if product_layout and group == "B" else "legacy",
                )
                turns = result["turns"]
                answers = [turn["messages"][-1].text for turn in turns]
                calls = {
                    call["id"]: call
                    for message in turns[-1]["messages"]
                    for call in getattr(message, "tool_calls", [])
                    if call["id"] not in initial_calls
                }
                paths = {
                    call["args"].get("file_path")
                    for call in calls.values()
                    if call["name"] == "read_file"
                }
                read_results = [
                    message
                    for message in turns[-1]["messages"]
                    if isinstance(message, ToolMessage)
                    and message.tool_call_id in calls
                    and calls[message.tool_call_id]["name"] == "read_file"
                ]
                read_ok = len(read_results) == len(calls) and all(
                    message.status != "error" and "name,units" in message.text
                    for message in read_results
                )
                fact_ok = False
                if len(answers) == 2:
                    fact_ok = (
                        (
                            set(re.findall(r"\d{4}-\d{2}-\d{2}", answers[0]))
                            == {"2026-11-23"}
                            and set(re.findall(r"\d{4}-\d{2}-\d{2}", answers[1]))
                            == {"2026-11-24"}
                        )
                        if factor in {"date", "combined"}
                        else (
                            "pytest" in answers[0].lower()
                            and "vue" in answers[1].lower()
                        )
                    )
                    if factor == "combined":
                        fact_ok = (
                            fact_ok
                            and "pytest" in answers[0].lower()
                            and "vue" in answers[1].lower()
                        )
                ok = (
                    len(answers) == 2
                    and all(re.search(r"(?<![\d.-])60(?![\d.])", a) for a in answers)
                    and fact_ok
                    and read_ok
                    and paths
                    == {"/workspace/work/data.csv", "/workspace/work/data2.csv"}
                    and all(call["name"] == "read_file" for call in calls.values())
                    and not any(turn.get("__interrupt__") for turn in turns)
                )
                if factor == "summary":
                    ok = (
                        len(answers) == 1
                        and answers[0].strip() == "10"
                        and not calls
                        and len(group_calls) >= 2
                    )
                tasks.append(
                    {
                        "group": group,
                        "answers": answers,
                        "quality_pass": ok,
                        "model_calls": len(group_calls),
                        "tool_calls": len(calls),
                        "read_paths": sorted(paths),
                        "read_results_succeeded": read_ok
                        if factor != "summary"
                        else None,
                    }
                )
                if not ok:
                    stopped = True
                    registration["stop_reason"] = "agent_quality_failed"
                    break
            except Exception as exc:
                registration["stop_reason"] = (
                    "agent_execution_failed:" + type(exc).__name__
                )
                tasks.append(
                    {
                        "group": group,
                        "quality_pass": False,
                        "model_calls": len(group_calls),
                    }
                )
                break
    finally:
        if own_client:
            await client.aclose()
        registration["finished_at"] = datetime.now(UTC).isoformat()
        write_json(output / "registration.json", registration)
        write_json(output / "tasks.json", tasks)
    summary = report(output)
    return {
        "tasks": tasks,
        "usage": summary,
        "stop_reason": registration["stop_reason"],
    }


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(
            "Usage: prompt_cache_agent.py NEW_OUTPUT_DIRECTORY [date|memory|combined|summary]"
        )
    result = asyncio.run(
        run_agent(
            Path(sys.argv[1]),
            load_connection(),
            factor=sys.argv[2] if len(sys.argv) == 3 else "date",
        )
    )
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["stop_reason"] is None else 2)
