import unittest

from platform_api.adapters.langgraph.sdk_client import (
    _PUBLIC_CODES,
    create_runtime_upstream_error,
)
from platform_api.core.errors import UpstreamServiceError


class RuntimeUpstreamErrorsTest(unittest.TestCase):
    def make(self, status, detail, **kwargs):
        return create_runtime_upstream_error(
            status_code=status,
            detail=detail,
            fallback_code="thread_create_failed",
            **kwargs,
        )

    def test_source_and_public_status_are_distinct(self):
        cases = [
            (401, 502, "runtime_delegation_rejected"),
            (403, 403, "forbidden"),
            (422, 422, "validation_failed"),
            (429, 429, "langgraph_upstream_rate_limited"),
            (500, 502, "langgraph_upstream_request_failed"),
        ]
        for source, public, code in cases:
            with self.subTest(source=source):
                error = self.make(source, {"detail": "secret-key"})
                self.assertIsInstance(error, UpstreamServiceError)
                self.assertEqual(
                    (error.upstream_status_code, error.status_code, error.code),
                    (source, public, code),
                )
                self.assertNotIn("secret-key", str(error.to_payload(request_id="req")))

    def test_catalog_codes_and_wrong_status(self):
        self.assertIn("memory_setting_required", _PUBLIC_CODES[400])
        self.assertNotIn("memory_setting_required", _PUBLIC_CODES[409])
        for source, codes in _PUBLIC_CODES.items():
            for code in codes:
                with self.subTest(source=source, code=code):
                    error = self.make(
                        source, {"error": {"code": code, "message": "secret"}}
                    )
                    self.assertEqual(error.code, code)
                    self.assertNotEqual(error.message, "secret")
                    self.assertEqual(
                        error.status_code, 502 if source >= 500 else source
                    )
                    wrong = self.make(
                        418, {"error": {"code": code, "message": "secret"}}
                    )
                    self.assertEqual(wrong.code, "thread_create_failed")

    def test_selected_layer_does_not_mix_fields_or_leak_raw_data(self):
        error = self.make(
            409,
            {
                "error": {"message": "secret", "code": "unknown"},
                "detail": {"code": "workspace_directory_changed"},
                "Authorization": "secret",
            },
            upstream_path="/private",
        )
        self.assertEqual(error.code, "thread_create_failed")
        self.assertEqual(error.message, "Runtime request failed")
        self.assertEqual(
            error.extra, {"upstream": "langgraph", "upstream_status_code": 409}
        )

    def test_cursor_recovery_only_uses_exact_value(self):
        for recovery, expected in (
            ("thread_snapshot", {"recovery": "thread_snapshot"}),
            ("secret", None),
        ):
            error = self.make(
                410,
                {
                    "error": {
                        "code": "cursor_expired",
                        "extra": {
                            "upstream_detail": {"recovery": recovery, "token": "secret"}
                        },
                    }
                },
            )
            self.assertEqual(error.extra.get("upstream_detail"), expected)
            self.assertNotIn("secret", str(error.to_payload(request_id=None)))


if __name__ == "__main__":
    unittest.main()
