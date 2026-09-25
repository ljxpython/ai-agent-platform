import unittest

from platform_api.adapters.langgraph.sdk_client import create_runtime_upstream_error


class RuntimeUpstreamErrorsTest(unittest.TestCase):
    def test_expired_runtime_cursor_keeps_recovery_code(self):
        error = create_runtime_upstream_error(
            status_code=410,
            detail={
                "code": "cursor_expired",
                "detail": "cursor_expired",
                "recovery": "thread_snapshot",
            },
            fallback_code="langgraph_upstream_request_failed",
        )
        self.assertEqual(error.status_code, 410)
        self.assertEqual(error.code, "cursor_expired")
        self.assertEqual(error.extra["upstream_detail"]["recovery"], "thread_snapshot")

    def test_nested_message_preserves_status_code_and_redaction(self):
        error = create_runtime_upstream_error(
            status_code=409,
            detail={
                "detail": {
                    "code": "workspace_directory_changed",
                    "message": "Directory changed",
                    "_runtime_secret": "private",
                }
            },
            fallback_code="langgraph_upstream_request_failed",
        )
        self.assertEqual(error.status_code, 409)
        self.assertEqual(error.code, "workspace_directory_changed")
        self.assertEqual(error.message, "Directory changed")
        self.assertNotIn("_runtime_secret", error.extra["upstream_detail"]["detail"])

    def test_message_precedence_and_fallback(self):
        for detail, expected in (
            (" message ", "message"),
            ({"message": " top ", "detail": {"message": "nested"}}, "top"),
            ({"detail": " plain "}, "plain"),
            ({"detail": {"message": " nested "}}, "nested"),
            ({"detail": {"message": []}}, "upstream failed"),
            ({"detail": {"message": " "}}, "upstream failed"),
            ([], "upstream failed"),
            (None, "upstream failed"),
        ):
            with self.subTest(detail=detail):
                error = create_runtime_upstream_error(
                    status_code=400,
                    detail=detail,
                    fallback_code="upstream_failed",
                )
                self.assertEqual(error.message, expected)
