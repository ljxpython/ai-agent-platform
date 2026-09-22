"""Opt-in local Platform → Runtime → model approval smoke test."""
import os
import time
import unittest
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text

from platform_api.config import Settings


@unittest.skipUnless(os.getenv("RUN_LOCAL_GOVERNANCE_MODEL") == "1", "Explicit local real-model approval opt-in")
class GovernanceModelApprovalTest(unittest.TestCase):
    def test_owner_can_run_and_resume_approval_through_platform(self):
        settings = Settings()
        self.assertIn(settings.app_env, {"local", "dev"})
        engine = create_engine(settings.database_url)
        try:
            with engine.connect() as connection:
                project = connection.execute(text(
                    "SELECT p.id::text FROM projects p JOIN project_members m ON m.project_id=p.id "
                    "JOIN users u ON u.id=m.user_id WHERE p.status='active' AND u.username=:username "
                    "AND m.role='admin' ORDER BY p.created_at LIMIT 1"
                ), {"username": settings.bootstrap_admin_username}).scalar_one()
        finally:
            engine.dispose()
        with httpx.Client(base_url="http://127.0.0.1:2142", timeout=30, trust_env=False) as client:
            response = client.post("/api/identity/session", json={
                "username": settings.bootstrap_admin_username, "password": settings.bootstrap_admin_password,
            })
            response.raise_for_status()
            client.headers.update({"authorization": "Bearer " + response.json()["tokens"]["access_token"],
                                   "x-project-id": project})
            response = client.post("/api/langgraph/threads", json={"metadata": {
                "graph_id": "workflow_demo", "harness": "governance-model-approval",
            }})
            response.raise_for_status()
            path = "/api/langgraph/threads/" + response.json()["thread_id"]
            run_id = None
            try:
                def start(payload):
                    result = client.post(path + "/runs", json=payload,
                                         headers={"Idempotency-Key": str(uuid4())})
                    self.assertTrue(result.is_success, result.text)
                    return result.json()["run_id"]

                def wait(run):
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        result = client.get(path + "/runs/" + run)
                        result.raise_for_status()
                        status = result.json()["status"]
                        if status not in {"pending", "running"}:
                            return status
                        time.sleep(0.5)
                    self.fail("Synthetic approval run did not finish within 90 seconds")

                run_id = start({"assistant_id": "workflow_demo", "input": {
                    "message": "需要人工确认。这是权限治理验收，只回复 OK，不调用工具。",
                }})
                self.assertEqual(wait(run_id), "interrupted")
                state = client.get(path + "/state")
                state.raise_for_status()
                interrupts = [item for task in state.json().get("tasks", []) for item in task.get("interrupts", [])]
                self.assertEqual(len(interrupts), 1)
                run_id = start({"command": {"resume": {interrupts[0]["id"]: {
                    "decisions": [{"type": "approve"}],
                }}}})
                self.assertEqual(wait(run_id), "success")
                print("governance-model-approval: interrupted → approve → success", flush=True)
            finally:
                if run_id:
                    result = client.get(path + "/runs/" + run_id)
                    if result.is_success and result.json().get("status") in {"pending", "running"}:
                        client.post(path + "/runs/" + run_id + "/cancel").raise_for_status()
                client.delete(path).raise_for_status()
