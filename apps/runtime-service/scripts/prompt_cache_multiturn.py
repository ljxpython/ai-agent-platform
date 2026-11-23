"""Official eight-turn Agent comparison; no business middleware or shared settings change."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from langchain_core.messages import HumanMessage, ToolMessage
from prompt_cache_cases import capture, digest, source_fingerprints
from prompt_cache_experiment import collect, recompute_bundle, report, write_json
from prompt_cache_official import BASE_URL, MODEL, PRICE, load_official_connection

CASE = "OFFICIAL-eight-turn"


def task_spec():
    prompts = [
        "读取 /workspace/work/nov.csv，计算 units 总和，total 为总和。",
        "不要调用工具。根据上一轮读到的十一月数据，b_units 为 B 的数量，subtotal 为 A 与 B 的数量之和。",
        "读取 /workspace/work/dec.csv，total 为十二月总和，change 为它减去十一月总和。",
        "话题切换到前端。不要调用工具。根据前面两份原始数据，change 为十二月总和减十一月总和，growth_pct 为增长百分数的数值。",
        "本轮前端偏好已更正，以当前有效记忆为准。不要调用工具。nov_b 与 dec_b 分别为前面十一月和十二月原始文件 B 的数量。",
        "进入本轮运行日期。读取 /workspace/work/dec-corrected.csv，total 为修订后总和，correction 为修订后减去十二月原始总和。",
        "不要调用工具。old_total 为十一月总和，new_total 为十二月修订总和，delta 为两者之差。偏好只看本轮 user_memory；本轮没有记忆块就写 null，不能从历史回答恢复已移除偏好。",
        "不要调用工具。汇总 november_total、december_original、december_corrected 和 delta（修订十二月减十一月）。偏好只看本轮 user_memory，没有则 null，历史偏好不能代替当前记忆。",
    ]
    facts = [
        {"total": 60},
        {"b_units": 20, "subtotal": 30},
        {"total": 75, "change": 15},
        {"change": 15, "growth_pct": 25},
        {"nov_b": 20, "dec_b": 25},
        {"total": 71, "correction": -4},
        {"old_total": 60, "new_total": 71, "delta": 11},
        {
            "november_total": 60,
            "december_original": 75,
            "december_corrected": 71,
            "delta": 11,
        },
    ]
    memories = (
        ["Python 测试首选 pytest。"] * 3
        + ["前端首选 Vue 3，使用 TypeScript。"]
        + ["前端首选已更正为 React，使用 TypeScript；此前 Vue 偏好已失效。"] * 2
        + [""] * 2
    )
    preferences = ["pytest"] * 3 + ["Vue 3"] + ["React"] * 2 + [None] * 2
    paths = {0: "nov.csv", 2: "dec.csv", 5: "dec-corrected.csv"}
    turns = []
    for index, prompt in enumerate(prompts):
        date = "2026-11-23" if index < 5 else "2026-11-24"
        turns.append(
            {
                "question": f"实验第{index + 1}轮：{prompt} 仅输出一个 JSON 对象，包含要求的数值字段，另加 date（本轮 current_date 的 UTC 日期）和 preference（本轮有效记忆中的首选名称，无记忆则 null）。不写文件，不调用 read_file 之外工具。",
                "memory": memories[index],
                "date": date,
                "expected": {
                    **facts[index],
                    "date": date,
                    "preference": preferences[index],
                },
                "read_path": "/workspace/work/" + paths[index]
                if index in paths
                else None,
            }
        )
    return {
        "turns": turns,
        "files": {
            "nov.csv": "item,units\nA,10\nB,20\nC,30\n",
            "dec.csv": "item,units\nA,15\nB,25\nC,35\n",
            "dec-corrected.csv": "item,units\nA,15\nB,21\nC,35\n",
        },
        "group_order": ["A", "B"],
        "max_requests_per_group": 20,
        "criteria": "Eight JSON answers per group; exact numeric/date facts and fresh preference; three actual CSV reads; no write, other tool or persisted temporary context. One AB block, zero retries, fail and stop, no replacement samples.",
    }


def fingerprints():
    root = Path(__file__).resolve().parents[3]
    return {
        **source_fingerprints(),
        str(Path(__file__).resolve().relative_to(root)): hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
    }


def prepare():
    return {
        "version": 1,
        "route": "deepseek_official",
        "model": MODEL,
        "created_at": datetime.now(UTC).isoformat(),
        "nonce": uuid4().hex,
        "task": task_spec(),
        "source_sha256": fingerprints(),
        "pricing": PRICE,
        "metric_rule": "Weighted cache/input for all calls and separately after dropping exactly the first model call in each group by sequence, never by cache value. All costs include first calls.",
    }


def check_answer(content, expected):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        answer = json.loads(text)
    except (ValueError, TypeError):
        return {"pass": False, "errors": ["invalid_json"]}
    errors = []
    if not isinstance(answer, dict):
        return {"pass": False, "errors": ["not_an_object"]}
    for key, value in expected.items():
        actual = answer.get(key)
        if key not in answer:
            errors.append(key)
        elif key == "preference" and value is not None:
            words = (
                ["pytest"]
                if value == "pytest"
                else ["vue" if "Vue" in value else "react"]
            )
            lower = str(actual).lower()
            obsolete = {"pytest", "vue", "react"} - set(words)
            if (
                not isinstance(actual, str)
                or not all(w in lower for w in words)
                or any(w in lower for w in obsolete)
            ):
                errors.append(key)
        elif actual != value or isinstance(actual, bool):
            errors.append(key)
    return {"pass": not errors, "errors": errors, "answer": answer}


def requested_tools(events):
    calls = {}
    for event in events:
        for choice in event["data"].get("choices", []):
            for fragment in choice.get("delta", {}).get("tool_calls", []):
                target = calls.setdefault(
                    fragment["index"], {"name": "", "arguments": ""}
                )
                for key in target:
                    target[key] += fragment.get("function", {}).get(key) or ""
    return list(calls.values())


def analyze(bundle):
    results = recompute_bundle(bundle)
    for result, experiment in zip(results, bundle["experiments"], strict=True):
        after_first = copy.deepcopy(experiment)
        excluded = {
            group: next(r["id"] for r in experiment["requests"] if r["group"] == group)
            for group in dict.fromkeys(r["group"] for r in experiment["requests"])
        }
        after_first["requests"] = [
            r for r in after_first["requests"] if r["id"] not in excluded.values()
        ]
        after_first["planned"] = [
            r for r in after_first["planned"] if r["id"] not in excluded.values()
        ]
        result["after_first"] = recompute_bundle({"experiments": [after_first]})[0][
            "groups"
        ]
        result["excluded_request_ids"] = excluded
        tasks = experiment.get("tasks", [])
        result["task_complete"] = bool(tasks) and all(t["quality_pass"] for t in tasks)
        result["comparison_complete"] = result["task_complete"] and {
            t["group"] for t in tasks
        } == {"A", "B"}
    return results


async def run(output, connection, plan, *, client=None):
    expected_task = task_spec()
    if plan.get("diagnostic_of"):
        expected_task["group_order"] = ["B"]
    if (
        connection.get("base_url") != BASE_URL
        or connection.get("route") != "deepseek_official"
        or connection.get("model") != MODEL
        or connection.get("pricing") != PRICE
        or plan.get("task") != expected_task
        or plan.get("source_sha256") != fingerprints()
        or plan.get("pricing") != PRICE
        or plan.get("route") != "deepseek_official"
        or plan.get("model") != MODEL
    ):
        raise ValueError("Official connection, task or frozen source mismatch")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "version": 1,
        "route": "deepseek_official",
        "model": MODEL,
        "task": plan["task"],
        "nonce": plan["nonce"],
        "records": [],
        "source_sha256": plan["source_sha256"],
        "layer": "live_eight_turn_agent_in_process",
        "diagnostic_of": plan.get("diagnostic_of"),
    }
    registration = {
        "started_at": datetime.now(UTC).isoformat(),
        "pre_registered_plan_sha256": digest(plan),
        "pre_registered_task_sha256": digest(plan["task"]),
        "source_sha256": fingerprints(),
        "pricing": connection["pricing"],
        "pricing_reference": connection.get("pricing_reference"),
        "connection_fingerprint": connection["connection_fingerprint"],
        "environment_id": connection["environment_id"],
        "concurrency": 1,
        "max_requests": 40,
        "retries": 0,
        "attempted": 0,
        "stop_reason": None,
        "diagnostic_of": plan.get("diagnostic_of"),
    }
    tasks = []

    def save():
        registration["manifest_sha256"] = digest(manifest)
        write_json(output / "manifest.json", manifest)
        write_json(output / "registration.json", registration)
        write_json(output / "tasks.json", tasks)

    def stop(reason):
        # Model middleware wraps transport exceptions; preserve the reason first.
        registration["stop_reason"] = reason
        save()
        raise RuntimeError("Experiment stopped; see registration")

    save()
    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(120), follow_redirects=False
    )
    try:
        for group in plan["task"]["group_order"]:
            task = {"group": group, "turns": [], "quality_pass": False}
            tasks.append(task)
            lane = digest({"nonce": plan["nonce"], "group": group})[:24]
            group_calls = []
            turn_calls = {}
            expected = plan["task"]["turns"]

            async def respond(
                request,
                *,
                expected=expected,
                task=task,
                group=group,
                group_calls=group_calls,
                turn_calls=turn_calls,
                lane=lane,
            ):
                if registration["stop_reason"]:
                    raise RuntimeError("Experiment already stopped")
                payload = json.loads(request.content)
                question = next(
                    m["content"]
                    for m in reversed(payload["messages"])
                    if m["role"] == "user"
                    and m.get("name") not in {"runtime_date", "user_memory"}
                )
                index = next(
                    i for i, item in enumerate(expected) if item["question"] == question
                )
                if len(group_calls) >= plan["task"]["max_requests_per_group"]:
                    stop("model_call_limit")
                if any(t["conversation_turn"] == index for t in task["turns"]):
                    stop("unexpected_post_answer_call")
                # Keep the real adapter's payload; only add symmetric experiment isolation.
                payload["messages"][0]["content"] = (
                    f"<cache_experiment_lane>{lane}</cache_experiment_lane>\n"
                    + payload["messages"][0]["content"]
                )
                payload["thinking"] = {"type": "disabled"}
                call_index = len(group_calls)
                row = {
                    "id": f"{CASE}-{group}-r0-t{call_index}",
                    "case": CASE,
                    "group": group,
                    "repeat": 0,
                    "turn": call_index,
                    "conversation_turn": index,
                    "expected": "task_level",
                    "execution_eligible": True,
                    "payload": payload,
                    "payload_sha256": digest(payload),
                }
                manifest["records"].append(row)
                registration["attempted"] += 1
                registration["inflight_request"] = row["id"]
                save()
                result = await collect(client, connection, row)
                result["conversation_turn"] = index
                result["quality_pass"] = None
                result["quality_method"] = (
                    "per user turn with required real tool results; not per tool-call response"
                )
                write_json(output / (row["id"] + ".json"), result)
                group_calls.append(result)
                turn_calls.setdefault(index, []).append(row["id"])
                registration.pop("inflight_request", None)
                save()
                if (
                    result["status"] != "completed"
                    or result["response_model"] != MODEL
                    or result["usage"]["quality"]
                    not in {"reported", "derived_from_reported"}
                    or result["cache_normalization_matches"] is False
                    or result["usage"]["tokens"]["cache_read_tokens"] is None
                ):
                    stop("provider_evidence_failed")
                if result["finish_reason"] == "tool_calls":
                    calls = requested_tools(result["events"])
                    if len(calls) != 1 or not expected[index]["read_path"]:
                        stop("unexpected_tool_call")
                    call = calls[0]
                    if (
                        call["name"] != "read_file"
                        or json.loads(call["arguments"]).get("file_path")
                        != expected[index]["read_path"]
                    ):
                        stop("unexpected_tool_or_path")
                elif result["finish_reason"] == "stop":
                    if expected[index]["read_path"] and (
                        payload["messages"][-1]["role"] != "tool"
                        or "item,units" not in payload["messages"][-1]["content"]
                    ):
                        stop("required_real_read_missing")
                    quality = check_answer(
                        result["content"], expected[index]["expected"]
                    )
                    task["turns"].append(
                        {
                            "conversation_turn": index,
                            "model_call_ids": turn_calls[index],
                            "quality": quality,
                            "content": result["content"],
                        }
                    )
                    save()
                    if not quality["pass"]:
                        stop("answer_quality_failed")
                else:
                    stop("unexpected_finish_reason")
                body = "\n\n".join(
                    "data: " + json.dumps(e["data"]) for e in result["events"]
                )
                return httpx.Response(
                    200,
                    text=body + "\n\ndata: [DONE]\n\n",
                    headers={"Content-Type": "text/event-stream"},
                )

            first, *continuations = expected
            fixture = {
                "case": CASE,
                "turn": 0,
                "thread": f"multi-{plan['nonce'][:12]}-{group}",
                "date": first["date"],
                "memory": first["memory"],
                "model": MODEL,
                "protocol": "deepseek",
                "files": plan["task"]["files"],
                "messages": [HumanMessage(content=first["question"])],
                "continuations": [],
            }
            date = first["date"]
            for item in continuations:
                fixture["continuations"].append(
                    {
                        "question": item["question"],
                        "memory": item["memory"],
                        **({"date": item["date"]} if item["date"] != date else {}),
                    }
                )
                date = item["date"]
            started = time.perf_counter()
            try:
                captured = await capture(
                    fixture,
                    output / "workspaces",
                    responder=respond,
                    layout="legacy" if group == "A" else "product",
                )
                messages = captured["turns"][-1]["messages"]
                calls = {
                    c["id"]: c for m in messages for c in getattr(m, "tool_calls", [])
                }
                read_results = [m for m in messages if isinstance(m, ToolMessage)]
                paths = sorted(c["args"].get("file_path", "") for c in calls.values())
                expected_paths = sorted(
                    t["read_path"] for t in expected if t["read_path"]
                )
                task["read_paths"] = paths
                task["tool_calls"] = len(calls)
                task["read_results_succeeded"] = len(read_results) == len(
                    calls
                ) == 3 and all(
                    m.status != "error" and "item,units" in m.text for m in read_results
                )
                task["temporary_context_persisted"] = any(
                    getattr(m, "name", None) in {"runtime_date", "user_memory"}
                    for m in messages
                )
                task["quality_pass"] = (
                    len(task["turns"]) == 8
                    and all(t["quality"]["pass"] for t in task["turns"])
                    and task["read_results_succeeded"]
                    and paths == expected_paths
                    and all(c["name"] == "read_file" for c in calls.values())
                    and not task["temporary_context_persisted"]
                    and not any(t.get("__interrupt__") for t in captured["turns"])
                )
                if not task["quality_pass"]:
                    registration["stop_reason"] = "task_tool_or_state_quality_failed"
            except Exception as exc:
                registration["stop_reason"] = (
                    registration["stop_reason"]
                    or "agent_execution_failed:" + type(exc).__name__
                )
            finally:
                task["agent_execution_ms"] = (time.perf_counter() - started) * 1000
                task["model_calls"] = len(group_calls)
                save()
            if registration["stop_reason"]:
                break
    finally:
        if own_client:
            await client.aclose()
        registration["finished_at"] = datetime.now(UTC).isoformat()
        save()
    return {
        "tasks": tasks,
        "usage": report(output),
        "stop_reason": registration["stop_reason"],
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("output", type=Path)
    p = sub.add_parser("run")
    p.add_argument("output", type=Path)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--key-env", default="DEEPSEEK_API_KEY")
    p.add_argument("--env-file", type=Path)
    p = sub.add_parser("analyze")
    p.add_argument("bundle", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        with args.output.open("x") as handle:
            json.dump(prepare(), handle, ensure_ascii=False, sort_keys=True, indent=2)
        return {"network_calls": 0}
    if args.command == "analyze":
        return analyze(json.loads(args.bundle.read_text()))
    return await run(
        args.output,
        load_official_connection(key_env=args.key_env, env_file=args.env_file),
        json.loads(args.plan.read_text()),
    )


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main()), ensure_ascii=False))
