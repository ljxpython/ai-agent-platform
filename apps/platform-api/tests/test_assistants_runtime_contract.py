import unittest

from platform_api.core.errors import BadRequestError
from platform_api.modules.agents.application.contracts import (
    CreateAssistantCommand,
    UpdateAssistantCommand,
)
from platform_api.modules.agents.application.service import _normalize_agent_context
from pydantic import ValidationError


class AssistantsRuntimeContractTest(unittest.TestCase):
    def test_agent_rejects_removed_fields(self):
        for field in ("assistant_id", "config", "metadata"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    CreateAssistantCommand(graph_id="demo", name="Demo", **{field: {}})
                with self.assertRaises(ValidationError):
                    UpdateAssistantCommand(**{field: {}})

    def test_agent_context_only_allows_public_execution_defaults(self):
        self.assertEqual(_normalize_agent_context({"temperature": 0.2, "tools": []}, "p"),
                         {"temperature": 0.2, "tools": []})
        for context in ({"unknown": 1}, {"runtime_model_ref": "secret"}, {"temperature": 3}):
            with self.subTest(context=context), self.assertRaises(BadRequestError):
                _normalize_agent_context(context, "p")
