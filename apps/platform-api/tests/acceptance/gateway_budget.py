"""Private Worktree acceptance: real HTTP/Worker, synthetic OpenAI provider."""

import json
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from dotenv import dotenv_values
from psycopg.types.json import Jsonb

from platform_api.modules.runtime_catalog.application.credentials import encrypt_api_key

ROOT = next(
    p
    for p in Path(__file__).resolve().parents
    if (p / "scripts/local-stack.sh").is_file()
)
env = json.loads((ROOT / ".local-stack/environment.json").read_text())
assert (ROOT / ".git").is_file() and env["id"].startswith("wt_")
runtime = dotenv_values(ROOT / ".local-stack/runtime.env")
platform = dotenv_values(ROOT / ".local-stack/platform.env")
dsn = platform["PLATFORM_API_DATABASE_URL"].replace(
    "postgresql+psycopg://", "postgresql://"
)
assert (
    env["id"] + "_platform" in dsn and env["id"] + "_runtime" in runtime["DATABASE_URI"]
)
state = {"calls": 0, "tool": False, "tokens": [6, 5, 2, 6]}


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["content-length"])))
        index = state["calls"]
        state["calls"] += 1
        message = {"role": "assistant", "content": "2"}
        finish = "stop"
        if state["tool"]:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_" + uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": "read_reference",
                            "arguments": '{"topic":"budget"}',
                        },
                    }
                ],
            }
            finish = "tool_calls"
        usage = {
            "prompt_tokens": state["tokens"][min(index, 3)],
            "completion_tokens": 0,
            "total_tokens": state["tokens"][min(index, 3)],
            "prompt_tokens_details": {"cached_tokens": 0},
        }
        base = {
            "id": "chatcmpl_" + uuid4().hex,
            "created": int(time.time()),
            "model": payload["model"],
        }
        self.send_response(200)
        if payload.get("stream"):
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            for value in [
                {
                    **base,
                    "object": "chat.completion.chunk",
                    "choices": [
                        {"index": 0, "delta": message, "finish_reason": finish}
                    ],
                },
                {
                    **base,
                    "object": "chat.completion.chunk",
                    "choices": [],
                    "usage": usage,
                },
            ]:
                if value.get("choices") and "tool_calls" in value["choices"][0].get(
                    "delta", {}
                ):
                    value["choices"][0]["delta"]["tool_calls"][0]["index"] = 0
                self.wfile.write(("data: " + json.dumps(value) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        **base,
                        "object": "chat.completion",
                        "choices": [
                            {"index": 0, "message": message, "finish_reason": finish}
                        ],
                        "usage": usage,
                    }
                ).encode()
            )


server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
threading.Thread(target=server.serve_forever, daemon=True).start()
client = httpx.Client(
    base_url=f"http://127.0.0.1:{env['ports']['PLATFORM_API_PORT']}",
    timeout=90,
    trust_env=False,
)


def request(path, method="GET", body=None, status=200, key=None):
    result = client.request(
        method, path, json=body, headers={"Idempotency-Key": key} if key else {}
    )
    assert result.status_code == status, (
        method,
        path,
        result.status_code,
        result.json().get("error", {}).get("code"),
    )
    return result


model_id = None
try:
    login = request(
        "/api/identity/session",
        "POST",
        {"username": "admin", "password": "admin123456"},
    ).json()
    client.headers["authorization"] = "Bearer " + login["tokens"]["access_token"]
    project = request(
        "/api/projects", "POST", {"name": "Budget controlled " + uuid4().hex[:8]}
    ).json()
    project_id = project["id"]
    client.headers["x-project-id"] = project_id
    request("/api/runtime/graphs/refresh", "POST")
    graph = next(
        g
        for g in request("/api/runtime/graphs").json()["graphs"]
        if g["graph_id"] == "reference_agent"
    )
    request(
        f"/api/projects/{project_id}/runtime-policies/graphs/{graph['id']}",
        "PUT",
        {"is_enabled": True},
    )
    model_id = str(uuid4())
    pricing = {
        "currency": "USD",
        "basis": "per_million_tokens",
        "source": "configured_catalog",
        "version": str(uuid4()),
        "updated_at": datetime.now(UTC).isoformat(),
        "input": "100000",
        "output": "0",
        "cache_read": "0",
        "cache_write": "0",
        "cache_write_5m": "0",
        "cache_write_1h": "0",
    }
    # Only this isolated DB fixture uses loopback; public SSRF validation stays enabled.
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO runtime_catalog_models(id,display_name,provider,base_url,protocol,model_name,api_key_ciphertext,pricing_json,enabled,scope_type,project_id) VALUES(%s,%s,'budget-controlled',%s,'openai','budget-controlled',%s,%s,true,'project',%s)",
            (
                model_id,
                "Budget controlled HTTP",
                f"http://127.0.0.1:{server.server_port}/v1",
                encrypt_api_key(
                    "synthetic-only",
                    master_key=platform["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"],
                ),
                Jsonb(pricing),
                project_id,
            ),
        )
    request(
        f"/api/projects/{project_id}/runtime-policies/models/{model_id}",
        "PUT",
        {"is_enabled": True, "is_default_for_project": True},
    )
    agent = request(
        f"/api/projects/{project_id}/agents?graph_id=reference_agent"
    ).json()["items"][0]
    request(
        f"/api/agents/{agent['id']}",
        "PATCH",
        {"context": {"model_id": model_id, "max_tokens": 128}},
    )
    thread = request(
        "/api/langgraph/threads",
        "POST",
        {"graph_id": "reference_agent", "metadata": {"agent_id": agent["id"]}},
    ).json()["thread_id"]
    policy_body = {
        "scope": "PROJECT",
        "project_id": project_id,
        "budget_amount": "1",
        "duration": {"unit": "DAYS", "value": 1},
        "action": "REJECT",
    }
    policy_id = request(
        "/api/policies/budgets", "POST", policy_body, status=201
    ).json()["policy"]["id"]
    body = {
        "assistant_id": "reference_agent",
        "context": {"model_id": model_id, "max_tokens": 128},
        "input": {"messages": [{"role": "user", "content": "1+1?"}]},
        "config": {"recursion_limit": 32},
    }

    def run():
        key = str(uuid4())
        run_id = request(
            f"/api/langgraph/threads/{thread}/runs", "POST", body, key=key
        ).json()["run_id"]
        for _ in range(60):
            value = request(f"/api/langgraph/threads/{thread}/runs/{run_id}").json()
            if value["status"] not in {"running", "pending"}:
                break
            time.sleep(0.5)
        assert value["status"] == "success", (value["status"], value.get("error"))
        cost = request(f"/api/langgraph/threads/{thread}/runs/{run_id}/usage").json()[
            "cost"
        ]["estimated_cost_usd"]
        return run_id, key, cost

    first = run()
    second = run()
    assert (first[2], second[2]) == ("0.600000000000", "0.500000000000"), (
        first[2],
        second[2],
    )
    before = state["calls"]
    denied = request(
        f"/api/langgraph/threads/{thread}/runs",
        "POST",
        body,
        key=str(uuid4()),
        status=429,
    )
    assert denied.json()["request_id"] and int(denied.headers["retry-after"]) > 0
    assert (
        request(
            f"/api/langgraph/threads/{thread}/runs", "POST", body, key=second[1]
        ).json()["run_id"]
        == second[0]
    )
    assert state["calls"] == before
    request(
        f"/api/policies/budgets/{policy_id}", "PUT", {**policy_body, "action": "ALERT"}
    )
    third = run()
    assert third[2] == "0.200000000000"
    for _ in range(30):
        with psycopg.connect(runtime["DATABASE_URI"]) as conn:
            events = conn.execute(
                "SELECT event_id,delivered_at FROM runtime_budget_outbox WHERE policy_id=%s",
                (policy_id,),
            ).fetchall()
        if events and events[0][1]:
            break
        time.sleep(0.5)
    assert len(events) == 1 and events[0][1]
    request(
        f"/api/policies/budgets/{policy_id}",
        "PUT",
        {**policy_body, "budget_amount": "1.5"},
    )
    state["tool"] = True
    stream = request(
        f"/api/langgraph/threads/{thread}/runs/stream",
        "POST",
        {**body, "stream_mode": ["messages", "updates"]},
        key=str(uuid4()),
    )
    assert stream.status_code == 200
    assert "runtime_gateway_budget_exhausted" in stream.text, stream.text[-500:]
    assert state["calls"] == 4, state["calls"]
    current = request("/api/policies/budgets?project_id=" + project_id).json()["items"][
        0
    ]
    assert (
        current["current_spend"] == "1.900000000000"
        and current["accounting_status"] == "complete"
    )
    # A new independent transport nonce replays the same persisted event safely.
    from platform_api.modules.runtime_policies.application.budget_transport import (
        encode,
    )

    with psycopg.connect(runtime["DATABASE_URI"]) as conn:
        payload = conn.execute(
            "SELECT payload FROM runtime_budget_outbox WHERE event_id=%s",
            (events[0][0],),
        ).fetchone()[0]
    path = "/api/runtime/internal/budgets/events"
    for _ in range(2):
        raw, headers = encode(
            platform["PLATFORM_API_RUNTIME_DELEGATION_SECRET"], path, payload
        )
        assert client.post(path, content=raw, headers=headers).status_code == 200
    with psycopg.connect(dsn) as conn:
        receipt = conn.execute(
            "SELECT count(*) FROM runtime_budget_event_receipts WHERE id=%s",
            (str(events[0][0]),),
        ).fetchone()[0]
    assert receipt == 1
    with psycopg.connect(runtime["DATABASE_URI"]) as conn:
        stopped = str(
            conn.execute(
                "SELECT run_id FROM runtime_usage_runs WHERE thread_id=%s AND gateway_budget_stop_code='runtime.gateway_budget.exhausted'",
                (thread,),
            ).fetchone()[0]
        )
    historical = request(f"/api/langgraph/threads/{thread}/runs/{stopped}/usage").json()
    assert historical["gateway_budget_stop_code"] == "runtime.gateway_budget.exhausted"
    request(
        f"/api/policies/budgets/{policy_id}",
        "PUT",
        {**policy_body, "budget_amount": "10"},
    )
    state["tool"] = False
    restored = run()
    assert restored[2] == "0.600000000000"
    request(f"/api/langgraph/threads/{thread}", "DELETE")
    after_delete = request("/api/policies/budgets?project_id=" + project_id).json()[
        "items"
    ][0]
    assert after_delete["current_spend"] == "2.500000000000"
    result = {
        "environment": env["id"],
        "project_id": project_id,
        "thread_id": thread,
        "policy_id": policy_id,
        "model_id": model_id,
        "run_ids": [first[0], second[0], third[0], stopped, restored[0]],
        "costs": [first[2], second[2], third[2], "0.600000000000", restored[2]],
        "current_spend": after_delete["current_spend"],
        "model_http_requests": state["calls"],
        "preflight_429": True,
        "idempotent_recovery": True,
        "alert_continues": True,
        "sse_budget_stop": True,
        "history_stop_code": True,
        "raise_limit_recovers": True,
        "thread_delete_preserves_budget": True,
        "event_id": str(events[0][0]),
        "receipt_count": receipt,
        "model_type": "controlled OpenAI-compatible HTTP",
    }
    (ROOT / ".local-stack/gateway-budget-controlled-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))
finally:
    if model_id:
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE runtime_catalog_models SET enabled=false WHERE id=%s",
                (model_id,),
            )
    server.shutdown()
    server.server_close()
    client.close()
