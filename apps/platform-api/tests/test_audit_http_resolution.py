from __future__ import annotations

import unittest

from platform_api.modules.audit.http_resolution import AuditHttpRequest, resolve_http_audit
from platform_api.modules.audit.schemas import AuditPlane, AuditResult


class AuditHttpResolutionTest(unittest.TestCase):
    def test_tool_restriction_records_target_and_safe_rule_metadata(self):
        metadata = {"graph_id": "reference_agent", "subject_type": "user", "subject_id": "u", "tool_name": "read_reference", "reason": "test", "token": "secret"}
        for method, suffix, action in (("POST", "", "created"), ("DELETE", "/restriction", "deleted")):
            resolved = resolve_http_audit(
                request=AuditHttpRequest(method=method, path="/api/projects/p/runtime-policies/tool-restrictions" + suffix,
                    query_params={}, query_string=None, state_project_id="p", client_ip=None, user_agent=None,
                    response_content_length=None, metadata=metadata),
                response_payload={"id": "restriction"}, actor_user_id="admin", status_code=201,
                result=AuditResult.SUCCESS)
            self.assertEqual(resolved.action, "runtime.tool_restriction." + action)
            self.assertEqual(resolved.target_id, "restriction")
            self.assertEqual(resolved.metadata["tool_name"], "read_reference")
            self.assertEqual(resolved.metadata["subject_id"], "u")
            self.assertNotIn("token", resolved.metadata)

    def test_terminal_operations_have_audit_actions_without_output(self):
        for method, suffix, action in (
            ("POST", "", "created"), ("GET", "", "listed"),
            ("GET", "/session/output", "output.read"),
            ("POST", "/session/input", "input.sent"),
            ("POST", "/session/resize", "resized"),
            ("DELETE", "/session", "closed"),
        ):
            with self.subTest(action=action):
                resolved = resolve_http_audit(
                    request=AuditHttpRequest(method=method,
                        path="/api/langgraph/threads/thread-1/terminals" + suffix,
                        query_params={}, query_string=None, state_project_id="p",
                        client_ip=None, user_agent=None, response_content_length=None),
                    response_payload={"data_base64": "private-output"},
                    actor_user_id="u", status_code=200, result=AuditResult.SUCCESS,
                )
                self.assertEqual(resolved.action, "runtime.terminal." + action)
                self.assertEqual(resolved.target_id, "thread-1")
                self.assertNotIn("private-output", str(resolved.metadata))

    def test_run_cancel_audits_run_id_and_unknown_paths_do_not_become_ids(self):
        run_id = "11111111-1111-1111-1111-111111111111"
        for path, expected in (
            (f"/api/langgraph/threads/{run_id}/runs/{run_id}/cancel", run_id),
            ("/api/unknown/" + "x" * 200, None),
        ):
            resolved = resolve_http_audit(
                request=AuditHttpRequest(method="POST", path=path, query_params={},
                    query_string=None, state_project_id="p", client_ip=None,
                    user_agent=None, response_content_length=None),
                response_payload=None, actor_user_id="u", status_code=200, result=AuditResult.SUCCESS,
            )
            self.assertEqual(resolved.target_id, expected)
            if expected:
                self.assertEqual(resolved.action, "runtime.run.item.cancelled")

    def test_announcement_feed_resolution_uses_project_scope(self) -> None:
        resolved = resolve_http_audit(
            request=AuditHttpRequest(
                method="GET",
                path="/api/announcements/feed",
                query_params={"project_id": "project-1"},
                query_string="project_id=project-1",
                state_project_id=None,
                client_ip="127.0.0.1",
                user_agent="pytest",
                response_content_length="123",
            ),
            response_payload=None,
            actor_user_id="user-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )

        self.assertEqual(resolved.plane, AuditPlane.CONTROL_PLANE)
        self.assertEqual(resolved.action, "announcement.feed.read")
        self.assertEqual(resolved.target_type, "announcement_feed")
        self.assertEqual(resolved.target_id, "project-1")
        self.assertEqual(resolved.project_id, "project-1")
        self.assertEqual(resolved.metadata["route_kind"], "control_plane")

    def test_runtime_thread_create_resolution_uses_response_payload_target(self) -> None:
        resolved = resolve_http_audit(
            request=AuditHttpRequest(
                method="POST",
                path="/api/langgraph/threads",
                query_params={},
                query_string=None,
                state_project_id="project-2",
                client_ip="127.0.0.1",
                user_agent="pytest",
                response_content_length="64",
            ),
            response_payload={"thread_id": "thread-9"},
            actor_user_id="user-1",
            status_code=201,
            result=AuditResult.SUCCESS,
        )

        self.assertEqual(resolved.plane, AuditPlane.RUNTIME_GATEWAY)
        self.assertEqual(resolved.action, "runtime.thread.item.created")
        self.assertEqual(resolved.target_type, "thread")
        self.assertEqual(resolved.target_id, "thread-9")
        self.assertEqual(resolved.project_id, "project-2")
        self.assertEqual(resolved.metadata["response_size"], 64)

    def test_protocol_v2_routes_use_runtime_audit_actions(self) -> None:
        common = {
            "query_params": {},
            "query_string": None,
            "state_project_id": "project-2",
            "client_ip": None,
            "user_agent": None,
            "response_content_length": None,
        }
        command = resolve_http_audit(
            request=AuditHttpRequest(
                method="POST",
                path="/api/langgraph/threads/thread-9/commands",
                **common,
            ),
            response_payload=None,
            actor_user_id="user-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )
        events = resolve_http_audit(
            request=AuditHttpRequest(
                method="POST",
                path="/api/langgraph/threads/thread-9/stream/events",
                **common,
            ),
            response_payload=None,
            actor_user_id="user-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )

        self.assertEqual(command.action, "runtime.command.submitted")
        self.assertEqual(events.action, "runtime.event_stream.opened")
        self.assertEqual(command.target_id, "thread-9")
        self.assertEqual(events.project_id, "project-2")

    def test_project_lifecycle_and_service_account_grant_use_semantic_actions(self) -> None:
        archive = resolve_http_audit(
            request=AuditHttpRequest(
                method="POST",
                path="/api/projects/project-1/archive",
                query_params={},
                query_string=None,
                state_project_id="project-1",
                client_ip=None,
                user_agent=None,
                response_content_length=None,
            ),
            response_payload=None,
            actor_user_id="admin-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )
        grant = resolve_http_audit(
            request=AuditHttpRequest(
                method="PUT",
                path="/api/service-accounts/account-1/project-grants/project-1",
                query_params={},
                query_string=None,
                state_project_id=None,
                client_ip=None,
                user_agent=None,
                response_content_length=None,
            ),
            response_payload=None,
            actor_user_id="admin-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )

        self.assertEqual(archive.action, "project.project.archived")
        self.assertEqual(archive.target_id, "project-1")
        self.assertEqual(grant.action, "service_account.project_grant.upserted")
        self.assertEqual(grant.target_id, "project-1")

    def test_user_patch_accepts_only_controlled_semantic_action_override(self) -> None:
        resolved = resolve_http_audit(
            request=AuditHttpRequest(
                method="PATCH",
                path="/api/users/user-1",
                query_params={},
                query_string=None,
                state_project_id=None,
                client_ip=None,
                user_agent=None,
                response_content_length=None,
                action_override="user.status.updated",
            ),
            response_payload=None,
            actor_user_id="admin-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )
        rejected_override = resolve_http_audit(
            request=AuditHttpRequest(
                method="PATCH",
                path="/api/users/user-1",
                query_params={},
                query_string=None,
                state_project_id=None,
                client_ip=None,
                user_agent=None,
                response_content_length=None,
                action_override="attacker.custom.action",
            ),
            response_payload=None,
            actor_user_id="admin-1",
            status_code=200,
            result=AuditResult.SUCCESS,
        )

        self.assertEqual(resolved.action, "user.status.updated")
        self.assertEqual(rejected_override.action, "user.item.updated")


if __name__ == "__main__":
    unittest.main()
