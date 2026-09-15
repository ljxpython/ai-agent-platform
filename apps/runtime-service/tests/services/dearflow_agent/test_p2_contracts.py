"""Shared boundary vectors run against both services, without production cross imports."""
import json
from pathlib import Path
import subprocess

import pytest

from runtime_service.runtime import runtime_context_hash
from runtime_service.services.dearflow_agent.schemas import ClarificationRequest, validate_answer


FIELDS = [
    {"name": "short", "label": "Short", "type": "text"},
    {"name": "long", "label": "Long", "type": "textarea"},
    {"name": "count", "label": "Count", "type": "number"},
    {"name": "choice", "label": "Choice", "type": "select", "options": [{"value": "a", "label": "A"}]},
    {"name": "choices", "label": "Choices", "type": "multi_select", "options": [{"value": "a", "label": "A"}]},
    {"name": "flag", "label": "Flag", "type": "checkbox"},
    {"name": "day", "label": "Day", "type": "date"},
]
VALUES = {"short": "ok", "long": "long\ntext", "count": 2.5, "choice": "a", "choices": ["a"], "flag": False, "day": "2026-09-14"}


def test_both_services_use_same_context_hash_and_answer_vectors():
    request = ClarificationRequest(question="Research scope?", fields=FIELDS)
    vectors = [(VALUES, True)] + [({**VALUES, key: value}, False) for key, value in (
        ("count", True), ("count", "2"), ("count", float("inf")), ("count", 10**400),
        ("choices", ["a", "a"]), ("choices", ["b"]), ("choices", []),
        ("flag", "false"), ("day", "2026-02-30"), ("day", "20260914"), ("short", ""))]
    answers = []
    for values, valid in vectors:
        answer = {"schema_version": 1, "status": "answered", "values": values}
        if valid:
            assert validate_answer(request, answer) == answer
        else:
            with pytest.raises(ValueError):
                validate_answer(request, answer)
        answers.append((answer, valid))
    context = {"execution_mode": "pro", "tools": ["read_file", "search_web"], "temperature": 1}
    expected = runtime_context_hash(context)
    repo = Path(__file__).resolve().parents[5]
    script = '''
import json,sys
from platform_api.modules.runtime_gateway.application.service import _runtime_context_snapshot
from platform_api.modules.runtime_gateway.application.clarification import _validate
p=json.load(sys.stdin)
assert _runtime_context_snapshot({"params":{"context":p["context"]}})[0] == p["hash"]
for answer, valid in p["answers"]:
    try:
        _validate(p["request"], answer)
    except (ValueError, TypeError):
        assert not valid
    else:
        assert valid
print("Platform and Runtime boundary vectors agree")
'''
    result = subprocess.run([str(repo / "apps/platform-api/.venv/bin/python"), "-c", script],
                            cwd=repo / "apps/platform-api", text=True, capture_output=True,
                            input=json.dumps({"request": request.model_dump(), "answers": answers,
                                              "context": context, "hash": expected}), timeout=90)
    assert result.returncode == 0, result.stderr
