from __future__ import annotations

import unittest
from unittest.mock import patch

from platform_api.modules.runtime_catalog.application.model_connection import (
    ModelReferenceError,
    create_model_reference,
    parse_model_reference,
)


class ModelReferenceTests(unittest.TestCase):
    def test_model_reference_is_signed_and_scoped(self) -> None:
        reference = create_model_reference(
            project_id="project-1", model_id="deepseek:chat", secret="x" * 32
        )
        self.assertEqual(
            parse_model_reference(reference, secret="x" * 32)["project_id"], "project-1"
        )
        with self.assertRaises(ModelReferenceError):
            parse_model_reference(reference + "x", secret="x" * 32)

    def test_model_reference_expires(self) -> None:
        with patch("platform_api.modules.runtime_catalog.application.model_connection.time.time", return_value=100):
            reference = create_model_reference(
                project_id="project-1", model_id="deepseek:chat", secret="x" * 32
            )
        with patch("platform_api.modules.runtime_catalog.application.model_connection.time.time", return_value=1000):
            with self.assertRaises(ModelReferenceError):
                parse_model_reference(reference, secret="x" * 32)


class RuntimeModelRedemptionTest(unittest.IsolatedAsyncioTestCase):
    async def test_expired_reference_requires_fresh_runtime_signature(self):
        import hashlib
        import hmac
        import time
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from starlette.requests import Request
        from platform_api.core.errors import ForbiddenError
        from platform_api.modules.runtime_catalog.presentation.http import get_internal_runtime_model_config

        secret = "runtime-shared-secret-32-bytes-long"
        with patch("platform_api.modules.runtime_catalog.application.model_connection.time.time", return_value=100):
            reference = create_model_reference(project_id="p", model_id="m", secret=secret)
        with self.assertRaises(ModelReferenceError):
            parse_model_reference(reference, secret=secret)
        self.assertEqual(parse_model_reference(reference, secret=secret, allow_expired=True)["model_id"], "m")
        timestamp = str(int(time.time()))
        signature = hmac.new(secret.encode(), f"{timestamp}\np\n{reference}".encode(), hashlib.sha256).hexdigest()
        def request(signature, timestamp=timestamp, project="p"):
            return Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace(
                settings=SimpleNamespace(runtime_delegation_secret=secret))),
                "headers": [(k.encode(), v.encode()) for k, v in {
                    "x-runtime-model-ref": reference, "x-project-id": project,
                    "x-runtime-model-time": timestamp, "x-runtime-model-signature": signature}.items()]})
        service = SimpleNamespace(resolve_model_connection=AsyncMock(return_value={"model_id": "m"}))
        await get_internal_runtime_model_config(request(signature), service)
        service.resolve_model_connection.assert_called_once_with(
            reference=reference, project_id="p", trusted_runtime=True)
        for invalid in (request(signature+"x"), request(signature, timestamp="100"), request(signature, project="other")):
            with self.assertRaises(ForbiddenError):
                await get_internal_runtime_model_config(invalid, service)
