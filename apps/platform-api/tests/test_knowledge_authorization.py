"""Operation leases recheck original Run owner, current ACL, and revocation."""

import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select

from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.knowledge.authorization import request_id, signature
from platform_api.modules.projects.models import ProjectMemberRecord, ProjectRecord
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunRequestRecord,
    ThreadAccessRecord,
)
from platform_api.modules.service_accounts.models import (
    ServiceAccountProjectGrantRecord,
    ServiceAccountRecord,
    ServiceAccountTokenRecord,
)
from tests import test_knowledge_member_upload as fixtures

SUBMIT = "mcp_submit_project_knowledge_document"


class KnowledgeAuthorizationTest(unittest.TestCase):
    headers = fixtures.KnowledgeMembersTest.headers

    def setUp(self):
        fixtures.KnowledgeMembersTest.setUp(self)
        self.settings.knowledge_upload_enabled = True
        self.thread, self.run = str(uuid4()), str(uuid4())
        with self.factory.begin() as session:
            session.add(
                ThreadAccessRecord(
                    thread_id=self.thread,
                    project_id=self.project,
                    owner_user_id=self.users["executor"],
                    visibility="private",
                )
            )
            session.add(
                RunRequestRecord(
                    project_id=self.project,
                    thread_id=self.thread,
                    agent_key="showcase_demo",
                    requested_by=self.users["executor"],
                    idempotency_key="fixture",
                    request_digest="0" * 64,
                    context_snapshot={},
                    context_hash="fixture",
                    run_id=self.run,
                )
            )

    def values(self, operation="upload", **changes):
        now = int(time.time())
        value = {
            "issuer": "runtime-service"
            if operation == "upload"
            else "rag-anything-use",
            "audience": "platform-api",
            "operation": operation,
            "tenant_id": "__default",
            "project_id": self.project,
            "resource_id": "knowledge",
            "subject": self.users["executor"],
            "principal_type": "user",
            "credential_id": "",
            "graph_id": "showcase_demo",
            "thread_id": self.thread,
            "run_id": self.run,
            "tool_call_id": "fixture-call",
            "sha256": "a" * 64,
            "size_bytes": 9,
            "file_name": "项目规范.md",
            "mime_type": "text/markdown",
            "iat": now,
            "exp": now + 30,
            "nonce": uuid4().hex,
        }
        if operation != "upload":
            value.update(job_id="kj_" + "1" * 32, knowledge_base_id="kb_" + "3" * 32)
        if operation == "read":
            value["issuer"] = "runtime-service"
            for key in ("sha256", "size_bytes", "file_name", "mime_type"):
                value.pop(key)
        if operation == "activate":
            value.update(target_revision="kg_" + "4" * 32, base_revision=0)
        value.update(changes)
        value["request_id"] = request_id(value)
        return value

    def envelope(self, values):
        return {
            "version": 1,
            "key_id": self.settings.knowledge_key_id,
            "values": values,
            "signature": signature(
                values,
                self.settings.knowledge_secret,
                self.settings.knowledge_key_id,
                "knowledge-operation-request",
            ),
        }

    def authorize(self, values=None):
        return self.client.post(
            "/api/runtime/internal/knowledge/authorize",
            json=self.envelope(values or self.values()),
        )

    def test_grant_scope_signature_and_short_lease(self):
        response = self.authorize()
        self.assertEqual(response.status_code, 200, response.text)
        envelope = response.json()
        value = envelope["values"]
        self.assertEqual(value["knowledge_base_id"], "kb_" + "3" * 32)
        self.assertEqual(value["audience"], "rag-knowledge")
        self.assertEqual(value["exp"] - value["iat"], 30)
        self.assertEqual(
            envelope["signature"],
            signature(
                value,
                self.settings.knowledge_secret,
                envelope["key_id"],
                "knowledge-operation-grant",
            ),
        )
        self.assertNotIn(self.settings.knowledge_secret, response.text)
        with self.factory() as session:
            audit = session.scalar(
                select(AuditLogRecord).where(
                    AuditLogRecord.action == "runtime.knowledge.authorization.checked"
                )
            )
            self.assertEqual(audit.actor_user_id, self.users["executor"])
            self.assertEqual(audit.project_id, self.project)
            self.assertEqual(
                audit.metadata_json["knowledge_request_id"], value["request_id"]
            )
            self.assertNotIn("signature", audit.metadata_json)

    def test_bad_signatures_expiry_scope_and_operation_are_denied(self):
        envelope = self.envelope(self.values())
        envelope["values"]["file_name"] = "changed.md"
        self.assertEqual(
            self.client.post(
                "/api/runtime/internal/knowledge/authorize", json=envelope
            ).status_code,
            403,
        )
        for changes in (
            {"iat": int(time.time()) - 60, "exp": int(time.time()) - 30},
            {"exp": int(time.time()) + 60},
            {"resource_id": "wrong"},
            {"tenant_id": str(uuid4())},
            {"subject": self.users["outsider"]},
            {"knowledge_base_id": "kb_" + "5" * 32},
            {"issuer": "rag-anything-use"},
            {"principal_type": "service_account"},
        ):
            self.assertIn(
                self.authorize(self.values(**changes)).status_code, (403, 404)
            )
        response = self.client.post(
            "/api/runtime/internal/knowledge/authorize",
            json={"user_id": self.users["executor"]},
            headers=self.headers(),
        )
        self.assertEqual(response.status_code, 403)

    def test_start_activate_keep_run_owner_without_thread_liveness(self):
        with self.factory.begin() as session:
            session.delete(session.get(ThreadAccessRecord, self.thread))
        self.assertEqual(self.authorize().status_code, 403)
        for operation in ("start", "activate"):
            response = self.authorize(self.values(operation))
            self.assertEqual(response.status_code, 200, response.text)
        with self.factory.begin() as session:
            session.scalar(select(RunRequestRecord)).requested_by = self.users["admin"]
        self.assertEqual(self.authorize(self.values("start")).status_code, 403)

    def test_current_acl_deny_and_plan_run_sources_reject(self):
        from platform_api.modules.runtime_policies.infra.sqlalchemy.models import (
            RuntimeToolRestrictionRecord,
        )

        with self.factory.begin() as session:
            session.get(ThreadAccessRecord, self.thread).owner_user_id = self.users[
                "admin"
            ]
        self.assertEqual(self.authorize().status_code, 403)
        with self.factory.begin() as session:
            session.get(ThreadAccessRecord, self.thread).owner_user_id = self.users[
                "executor"
            ]
            session.scalar(select(RunRequestRecord)).context_snapshot = {
                "plan_mode": True
            }
        self.assertEqual(self.authorize().status_code, 403)
        with self.factory.begin() as session:
            session.scalar(select(RunRequestRecord)).context_snapshot = {}
            session.add(
                RuntimeToolRestrictionRecord(
                    project_id=UUID(self.project),
                    graph_id="showcase_demo",
                    subject_type="project",
                    subject_id=UUID(self.project),
                    tool_name=SUBMIT,
                    reason="fixture",
                    created_by=self.users["admin"],
                )
            )
        self.assertEqual(self.authorize().status_code, 403)
        self.assertEqual(self.authorize(self.values("activate")).status_code, 403)

    def test_revocation_between_queue_and_activation_is_enforced(self):
        self.assertEqual(self.authorize().status_code, 200)
        with self.factory.begin() as session:
            session.query(ProjectMemberRecord).filter_by(
                project_id=UUID(self.project), user_id=UUID(self.users["executor"])
            ).delete()
        self.assertEqual(self.authorize(self.values("start")).status_code, 403)
        self.assertEqual(self.authorize(self.values("activate")).status_code, 403)

    def test_service_account_credentials_are_reloaded(self):
        with self.factory.begin() as session:
            account = ServiceAccountRecord(name="knowledge-fixture")
            session.add(account)
            session.flush()
            credential = ServiceAccountTokenRecord(
                service_account_id=account.id,
                name="fixture",
                token_prefix="synthetic",
                token_secret_hash="synthetic",
            )
            session.add_all(
                [
                    credential,
                    ServiceAccountProjectGrantRecord(
                        service_account_id=account.id,
                        project_id=UUID(self.project),
                        role="executor",
                    ),
                ]
            )
            session.flush()
            account_id, credential_id = str(account.id), str(credential.id)
            session.scalar(select(RunRequestRecord)).requested_by = credential_id
        values = self.values(
            "start",
            subject="service-account:" + account_id,
            principal_type="service_account",
            credential_id=credential_id,
        )
        self.assertEqual(self.authorize(values).status_code, 200)
        with self.factory.begin() as session:
            session.get(
                ServiceAccountTokenRecord, UUID(credential_id)
            ).status = "revoked"
        self.assertEqual(self.authorize(values).status_code, 403)

    def test_internal_body_is_bounded_and_disabled_is_safe(self):
        self.assertEqual(
            self.client.post(
                "/api/runtime/internal/knowledge/authorize",
                content="x" * 16385,
                headers={"Content-Type": "application/json"},
            ).status_code,
            413,
        )
        self.settings.knowledge_upload_enabled = False
        self.assertEqual(self.authorize().status_code, 503)

    def test_read_requires_current_active_project_even_with_upload_disabled(self):
        self.settings.knowledge_upload_enabled = False
        response = self.authorize(self.values("read"))
        self.assertEqual(response.status_code, 200, response.text)
        with self.factory.begin() as session:
            session.get(ProjectRecord, UUID(self.project)).status = "disabled"
        self.assertEqual(self.authorize(self.values("read")).status_code, 404)

    def test_upload_shutdown_drains_accepted_jobs_with_current_authorization(self):
        self.settings.knowledge_upload_enabled = False
        self.assertEqual(self.authorize().status_code, 503)
        for operation in ("start", "activate"):
            response = self.authorize(self.values(operation))
            self.assertEqual(response.status_code, 200, response.text)
        with self.factory.begin() as session:
            session.query(ProjectMemberRecord).filter_by(
                project_id=UUID(self.project), user_id=UUID(self.users["executor"])
            ).delete()
        for operation in ("start", "activate"):
            self.assertEqual(self.authorize(self.values(operation)).status_code, 403)

    def test_read_rejects_unknown_fields_and_cross_project_binding(self):
        self.assertEqual(
            self.authorize(self.values("read", file_name="unexpected.md")).status_code,
            403,
        )
        self.assertEqual(
            self.authorize(self.values("read", project_id=str(uuid4()))).status_code,
            403,
        )

    def test_signed_request_accepts_only_bounded_clock_skew_without_expiry_leeway(self):
        from platform_api.core.errors import ForbiddenError
        from platform_api.modules.knowledge.authorization import parse_operation

        for issued, expires, accepted in (
            (1002, 1032, True),
            (1005, 1035, True),
            (1006, 1036, False),
            (990, 1000, False),
            (1002, 1033, False),
        ):
            values = self.values(iat=issued, exp=expires)
            with patch(
                "platform_api.modules.knowledge.authorization.time.time",
                return_value=1000,
            ):
                if accepted:
                    self.assertEqual(
                        parse_operation(self.settings, self.envelope(values)).iat,
                        issued,
                    )
                else:
                    with self.assertRaises(ForbiddenError):
                        parse_operation(self.settings, self.envelope(values))
