"""Real API/Runtime/Worker/PG smoke, using only this Worktree's registered stack."""

import argparse
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from dotenv import dotenv_values


def run(output):
    root = Path(__file__).resolve().parents[3]
    environment = json.loads((root / ".local-stack/environment.json").read_text())
    settings = dotenv_values(root / ".local-stack/platform.env")
    runtime = dotenv_values(root / ".local-stack/runtime.env")
    api = f"http://127.0.0.1:{environment['ports']['PLATFORM_API_PORT']}"
    runtime_url = f"http://127.0.0.1:{environment['ports']['RUNTIME_PORT']}"
    assert environment["id"] in runtime["DATABASE_URI"]
    report = {"environment": environment["id"], "cases": {}, "real_model": None}
    with httpx.Client(base_url=api, timeout=180, trust_env=False) as client:

        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if response.status_code >= 400:
                payload = response.json()
                raise AssertionError(
                    f"{method} {path}: {response.status_code} {payload.get('error', {}).get('code')}"
                )
            return response.json() if response.content else None

        session = request(
            "POST",
            "/api/identity/session",
            json={
                "username": settings.get(
                    "PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME", "admin"
                ),
                "password": settings["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
            },
        )
        client.headers["authorization"] = "Bearer " + session["tokens"]["access_token"]
        project = request(
            "POST",
            "/api/projects",
            json={"name": "Token dashboard verification " + uuid4().hex[:8]},
        )
        project_id = project["id"]
        client.headers["x-project-id"] = project_id
        request("POST", "/api/runtime/graphs/refresh")
        graphs = request("GET", "/api/runtime/graphs")["graphs"]
        graph = next(g for g in graphs if g["graph_id"] == "reference_agent")
        request(
            "PUT",
            f"/api/projects/{project_id}/runtime-policies/graphs/{graph['id']}",
            json={"is_enabled": True},
        )
        models = request("GET", "/api/runtime/platform-models")["models"]
        model = next(
            m
            for m in models
            if m["enabled"]
            and m["credential_configured"]
            and m.get("model", "").lower() == "deepseek-v4.1-flash"
        )
        request(
            "PUT",
            f"/api/projects/{project_id}/runtime-policies/models/{model['id']}",
            json={"is_enabled": True, "is_default_for_project": True},
        )
        agents = request(
            "GET",
            f"/api/projects/{project_id}/agents",
            params={"graph_id": "reference_agent"},
        )["items"]
        agent = next(a for a in agents if a["graph_id"] == "reference_agent")
        request(
            "PATCH",
            f"/api/agents/{agent['id']}",
            json={"context": {"model_id": model["id"], "max_tokens": 64}},
        )
        thread = request(
            "POST",
            "/api/langgraph/threads",
            json={"metadata": {"graph_id": "reference_agent"}},
        )
        now = datetime.now(UTC)
        params = {
            "from": (now - timedelta(minutes=1)).isoformat(),
            "to": (now + timedelta(hours=1)).isoformat(),
            "timezone": "UTC",
        }
        response = client.post(
            f"/api/langgraph/threads/{thread['thread_id']}/runs/stream",
            json={
                "assistant_id": "reference_agent",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Reply with only OK. Do not call tools.",
                        }
                    ]
                },
                "context": {"model_id": model["id"], "max_tokens": 64},
                "stream_mode": ["values", "custom"],
                "version": "v3",
            },
        )
        assert response.status_code == 200, response.status_code
        runs = request("GET", f"/api/langgraph/threads/{thread['thread_id']}/runs")
        run_id = runs[0].get("run_id", runs[0].get("id"))
        usage = request(
            "GET", f"/api/langgraph/threads/{thread['thread_id']}/runs/{run_id}/usage"
        )
        dashboard = request(
            "GET", f"/api/projects/{project_id}/usage/dashboard", params=params
        )
        page = request(
            "GET",
            f"/api/projects/{project_id}/usage/runs",
            params={k: v for k, v in params.items() if k in {"from", "to"}},
        )
        with psycopg.connect(runtime["DATABASE_URI"]) as conn:
            counts = conn.execute(
                "SELECT count(*),sum(total_tokens),sum(estimated_cost_usd),count(*) FILTER (WHERE quality IN ('reported','derived_from_reported')) FROM runtime_usage_calls WHERE tenant_id='__default' AND project_id=%s AND run_id=%s",
                (project_id, run_id),
            ).fetchone()
        assert counts[0] > 0 and counts[1] > 0 and counts[0] == counts[3]
        assert (
            usage["tokens"]["total_tokens"]
            == dashboard["summary"]["tokens"]["total_tokens"]
            == counts[1]
        )
        assert len(page["items"]) == 1 and page["items"][0]["run_id"] == run_id
        assert (
            sum(
                point["known_tokens"]["total_tokens"] or 0
                for point in dashboard["series"]
            )
            == counts[1]
        )
        assert (
            sum(
                group["known_tokens"]["total_tokens"] or 0
                for group in dashboard["breakdown"]["items"]
            )
            == counts[1]
        )
        assert dashboard["summary"]["cost"]["known_cost_usd"] == (
            format(counts[2], ".12f") if counts[2] is not None else None
        )
        assert not any(
            key in json.dumps(dashboard)
            for key in (
                "api_key",
                "pricing_snapshot",
                "base_url",
                "prompt",
                "completion",
            )
        )
        report["real_model"] = {
            "provider": "miaomiaoai",
            "model": model["model"],
            "project_id": project_id,
            "thread_id": thread["thread_id"],
            "run_id": run_id,
            "observed_call_count": counts[0],
            "total_tokens": int(counts[1]),
            "known_cost_usd": dashboard["summary"]["cost"]["known_cost_usd"],
        }
        report["cases"]["worker_ledger_single_run_dashboard_series_groups_acl"] = (
            "passed"
        )
        platform_dashboard = request(
            "GET", "/api/usage/dashboard", params={**params, "project_ids": project_id}
        )
        assert platform_dashboard["summary"]["tokens"] == dashboard["summary"]["tokens"]
        report["cases"]["platform_and_project_consistency"] = "passed"
        state = request("GET", f"/api/langgraph/threads/{thread['thread_id']}/state")
        fork = request(
            "POST",
            f"/api/langgraph/threads/{thread['thread_id']}/fork",
            json={"checkpoint_id": state["checkpoint"]["checkpoint_id"]},
        )
        assert fork["thread_id"] != thread["thread_id"]
        after_fork = request(
            "GET", f"/api/projects/{project_id}/usage/dashboard", params=params
        )
        assert after_fork["summary"] == dashboard["summary"]
        with psycopg.connect(runtime["DATABASE_URI"]) as conn:
            assert (
                conn.execute(
                    "SELECT count(*) FROM runtime_usage_calls WHERE project_id=%s",
                    (project_id,),
                ).fetchone()[0]
                == counts[0]
            )
            assert (
                conn.execute(
                    "SELECT count(*) FROM runtime_usage_calls WHERE project_id=%s AND thread_id=%s",
                    (project_id, fork["thread_id"]),
                ).fetchone()[0]
                == 0
            )
        report["cases"]["fork_retains_consumption_without_copying_calls"] = "passed"
        # Exercise the deployed custom-route authentication layer, not only FastAPI in-process.
        path = "/internal/usage/aggregate"
        payload = {
            "version": 1,
            "actor_id": session["user"]["id"],
            "tenant_id": "__default",
            "project_ids": [project_id],
            "request_id": "smoke-internal",
            **params,
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        stamp = str(int(time.time()))
        signature = hmac.new(
            settings["PLATFORM_API_RUNTIME_DELEGATION_SECRET"].encode(),
            f"usage-query/v1\n{stamp}\nPOST\n{path}\n".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "x-usage-query-timestamp": stamp,
            "x-usage-query-signature": "sha256=" + signature,
        }
        with httpx.Client(
            base_url=runtime_url, timeout=10, trust_env=False
        ) as internal:
            good = internal.post(path, content=body, headers=headers)
            assert good.status_code == 200, good.status_code
            assert internal.post(path, content=body).status_code == 401
            assert (
                internal.post(
                    path,
                    content=body,
                    headers={"authorization": client.headers["authorization"]},
                ).status_code
                == 401
            )
            assert (
                internal.post(
                    "/internal/usage/runs/query", content=body, headers=headers
                ).status_code
                == 401
            )
            assert internal.get("/threads", headers=headers).status_code in {
                401,
                403,
                405,
            }
        report["cases"]["deployed_hmac_auth_and_native_isolation"] = "passed"
        report["dashboard"] = dashboard
        report["run_page"] = page
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "environment": report["environment"],
                "cases": report["cases"],
                "real_model": report["real_model"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
