"""Verify existing upstream metadata contracts without teaching Runtime business ACLs."""
import os
import unittest
from urllib.parse import urlparse
from uuid import uuid4

from platform_api.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream
from platform_api.config import Settings
from platform_api.core.security import create_runtime_delegation_token, empty_runtime_context_hash


@unittest.skipUnless(os.getenv("RUN_LOCAL_GOVERNANCE_CONTRACT") == "1", "explicit local Runtime contract gate")
class ThreadMetadataFilterContract(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_persistence_filter_and_count(self):
        settings = Settings()
        self.assertIn(urlparse(settings.langgraph_upstream_url).hostname, {"localhost", "127.0.0.1", "::1"})
        project_id = str(uuid4())
        marker = "governance-contract-" + uuid4().hex
        token = create_runtime_delegation_token(
            subject=marker, tenant_id="__default", project_id=project_id, role="project_admin",
            permissions=[], policy_version="contract", allowed_model_ids=["contract:model"], tool_overrides={},
            tool_policy_version="unscoped-read-v2",
            scope={"tenant_id": "__default", "project_id": project_id, "operation": "read"},
            context_hash=empty_runtime_context_hash(), settings=settings,
        )
        upstream = LangGraphRuntimeGatewayUpstream(
            base_url=settings.langgraph_upstream_url, timeout_seconds=10,
            forwarded_headers={"authorization": f"Bearer {token}"},
        )
        created = []
        try:
            for owner in ("a", "b"):
                thread = await upstream.create_thread({"metadata": {
                    "project_id": project_id, "harness": marker, "owner_subject": owner,
                    "access_subjects": [owner], "visibility": "private",
                }})
                created.append(thread["thread_id"])
            query = {"metadata": {"project_id": project_id, "harness": marker, "access_subjects": ["a"]}}
            rows = await upstream.search_threads({**query, "limit": 10})
            self.assertIsInstance(rows, list)
            self.assertEqual([row["thread_id"] for row in rows], [created[0]])
            self.assertEqual(await upstream.count_threads(query), {"count": 1})
            loaded = await upstream.get_thread(created[0])
            self.assertEqual(loaded["metadata"]["owner_subject"], "a")
            await upstream.update_thread(created[0], {"metadata": {"access_subjects": ["a", "b"]}})
            self.assertEqual(await upstream.count_threads({"metadata": {"harness": marker, "access_subjects": ["b"]}}), {"count": 2})
        finally:
            for thread_id in created:
                await upstream.delete_thread(thread_id)
