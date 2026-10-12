"""HTTP permission/ACL/deletion/fault checks on this Worktree's own smoke data."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from dotenv import dotenv_values


def run(chain, output):
    root = Path(__file__).resolve().parents[3]
    environment = json.loads((root / ".local-stack/environment.json").read_text())
    smoke = json.loads(chain.read_text())
    assert smoke["environment"] == environment["id"]
    settings = dotenv_values(root / ".local-stack/platform.env")
    runtime = dotenv_values(root / ".local-stack/runtime.env")
    assert environment["id"] in runtime["DATABASE_URI"]
    project = smoke["real_model"]["project_id"]
    thread = smoke["real_model"]["thread_id"]
    run_id = smoke["real_model"]["run_id"]
    window = {k: smoke["dashboard"]["window"][k] for k in ("from", "to")}
    report = {"environment": environment["id"], "project_id": project, "cases": {}}
    api = f"http://127.0.0.1:{environment['ports']['PLATFORM_API_PORT']}"
    path = f"/api/projects/{project}/usage"
    with httpx.Client(base_url=api, timeout=10, trust_env=False) as client:

        def request(method, uri, *, auth=None, expected=200, **kwargs):
            headers = {"x-project-id": project}
            if auth:
                if auth.startswith("ey"):
                    headers["authorization"] = "Bearer " + auth
                else:
                    headers["x-api-key"] = auth
            response = client.request(method, uri, headers=headers, **kwargs)
            assert response.status_code == expected, (
                method,
                uri,
                response.status_code,
                response.json().get("error", {}).get("code")
                if response.content
                else None,
            )
            if "/usage/" in uri:
                assert response.headers.get("cache-control") == "no-store"
            return response.json() if response.content else None

        def login(username, password):
            return request(
                "POST",
                "/api/identity/session",
                json={
                    "username": username,
                    "password": password,
                },
            )["tokens"]["access_token"]

        admin = login(
            settings.get("PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME", "admin"),
            settings["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
        )
        with psycopg.connect(runtime["DATABASE_URI"]) as conn:
            before = conn.execute(
                "SELECT count(*) FROM runtime_usage_calls WHERE project_id=%s",
                (project,),
            ).fetchone()[0]
        password = uuid4().hex + "Aa1!"
        users = {}
        for role in (
            "project_editor",
            "platform_viewer",
            "project_executor",
            "platform_operator",
        ):
            username = "usage_" + uuid4().hex[:12]
            user = request(
                "POST",
                "/api/users",
                auth=admin,
                json={
                    "username": username,
                    "password": password,
                    "platform_roles": [role] if role.startswith("platform_") else [],
                },
            )
            if role.startswith("project_"):
                request(
                    "PUT",
                    f"/api/projects/{project}/members/{user['id']}",
                    auth=admin,
                    json={"role": role},
                )
            users[role] = (user["id"], login(username, password))
        editor_id, editor = users["project_editor"]
        for role in ("platform_viewer", "project_executor"):
            request(
                "GET",
                path + "/dashboard",
                auth=users[role][1],
                params=window,
                expected=403,
            )
        total = request("GET", path + "/dashboard", auth=editor, params=window)
        assert (
            total["summary"]["tokens"]["total_tokens"]
            == smoke["dashboard"]["summary"]["tokens"]["total_tokens"]
        )
        assert not request("GET", path + "/runs", auth=editor, params=window)["items"]
        request("GET", "/api/usage/dashboard", auth=editor, params=window, expected=403)
        operator = users["platform_operator"][1]
        assert (
            request(
                "GET",
                "/api/usage/dashboard",
                auth=operator,
                params={**window, "project_ids": project},
            )["summary"]["tokens"]
            == total["summary"]["tokens"]
        )
        request("GET", path + "/runs", auth=operator, params=window, expected=403)
        request("GET", path + "/dashboard", params=window, expected=401)
        report["cases"]["aggregate_roles_do_not_grant_private_thread_content"] = (
            "passed"
        )
        request(
            "PUT",
            f"/api/langgraph/threads/{thread}/shares",
            auth=admin,
            json={"user_id": editor_id, "actions": ["read"]},
        )
        assert (
            request("GET", path + "/runs", auth=editor, params=window)["items"][0][
                "run_id"
            ]
            == run_id
        )
        request("DELETE", f"/api/projects/{project}/members/{editor_id}", auth=admin)
        request("GET", path + "/dashboard", auth=editor, params=window, expected=403)
        report["cases"]["share_then_current_member_revocation"] = "passed"
        account = request(
            "POST",
            "/api/service-accounts",
            auth=admin,
            json={"name": "usage-" + uuid4().hex[:8], "platform_roles": []},
        )
        credential = request(
            "POST",
            f"/api/service-accounts/{account['id']}/tokens",
            auth=admin,
            json={"name": "usage-verification", "expires_in_days": 1},
        )
        service_token = credential["plain_text_token"]
        request(
            "PUT",
            f"/api/service-accounts/{account['id']}/project-grants/{project}",
            auth=admin,
            json={"role": "project_editor"},
        )
        request("GET", path + "/dashboard", auth=service_token, params=window)
        assert not request("GET", path + "/runs", auth=service_token, params=window)[
            "items"
        ]
        request(
            "DELETE",
            f"/api/service-accounts/{account['id']}/tokens/{credential['token']['id']}",
            auth=admin,
        )
        request(
            "GET", path + "/dashboard", auth=service_token, params=window, expected=401
        )
        report["cases"]["service_credential_and_thread_acl"] = "passed"
        with psycopg.connect(runtime["DATABASE_URI"]) as lock:
            lock.execute(
                "LOCK TABLE runtime_usage_projection_state IN ACCESS EXCLUSIVE MODE"
            )
            unavailable = request("GET", path + "/dashboard", auth=admin, params=window)
            assert unavailable["availability"] == "unavailable"
            assert unavailable["unavailable_reason"] == "backend_unavailable"
            assert unavailable["summary"]["tokens"]["total_tokens"] is None
        assert (
            request("GET", path + "/dashboard", auth=admin, params=window)["summary"][
                "tokens"
            ]
            == total["summary"]["tokens"]
        )
        report["cases"]["database_lock_failure_and_recovery"] = "passed"
        request("DELETE", f"/api/langgraph/threads/{thread}", auth=admin)
        assert not request("GET", path + "/runs", auth=admin, params=window)["items"]
        assert (
            request("GET", path + "/dashboard", auth=admin, params=window)["summary"][
                "tokens"
            ]
            == total["summary"]["tokens"]
        )
        report["cases"]["deleted_thread_hidden_but_historical_consumption_retained"] = (
            "passed"
        )
        with psycopg.connect(runtime["DATABASE_URI"]) as conn:
            after = conn.execute(
                "SELECT count(*) FROM runtime_usage_calls WHERE project_id=%s",
                (project,),
            ).fetchone()[0]
        assert before == after
        report["cases"]["read_queries_generate_no_model_calls"] = "passed"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.chain, args.output)
