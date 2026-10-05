import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from platform_api.core.errors import ForbiddenError
from platform_api.modules.scheduled_tasks.schemas import (
    Schedule,
    TaskCreate,
    TaskUpdate,
)
from platform_api.modules.scheduled_tasks.service import (
    native_schedule,
    sign_task,
    verify_task,
)


class ScheduledTaskContractsTest(unittest.TestCase):
    def test_signature_binds_scope_and_rejects_tampering(self):
        values = {
            "v": 1,
            "tenant_id": "tenant",
            "owner_id": "owner",
            "credential_id": "credential",
        }
        task = sign_task(values, "secret")
        self.assertEqual(verify_task(task, "secret"), values)
        task["values"]["tenant_id"] = "other"
        with self.assertRaises(ForbiddenError):
            verify_task(task, "secret")
        for value in ({}, None, {"values": {}, "signature": 123}):
            with self.assertRaises(ForbiddenError):
                verify_task(value, "secret")

    def test_schedule_validation_and_once_utc_conversion(self):
        rule = Schedule(
            schedule_type="once",
            run_at="2026-11-01T01:30:00-04:00",
            timezone="America/New_York",
        )
        self.assertEqual(native_schedule(rule), "30 5 1 11 * 0 2026")
        self.assertEqual(
            rule.run_at.astimezone(UTC), datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
        )
        for values in (
            {"cron": "0 0 * * *", "timezone": "Bad/Zone"},
            {"cron": "* * * * * *"},
            {"schedule_type": "once", "run_at": "2026-11-01T01:30:00"},
            {"schedule_type": "once", "run_at": "2026-11-01T01:30:00.001+00:00"},
            {"cron": "0 0 * * *", "end_time": "2026-11-01"},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                Schedule(**values)
        for values in ({}, {"title": None}, {"enabled": True}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                TaskUpdate(**values)
        self.assertEqual(TaskUpdate(end_time=None).model_fields_set, {"end_time"})
        with self.assertRaises(ValidationError):
            TaskCreate(title=" ", prompt="hello", agent_key="probe", cron="0 0 * * *")
