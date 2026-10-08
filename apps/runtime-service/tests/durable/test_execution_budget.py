"""Run the production-worker HTTP contract against isolated storage."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.durable]


def test_isolated_execution_budget_http_chain(tmp_path):
    if os.getenv("BUDGET_RUNTIME_INTEGRATION") != "1":
        pytest.skip(
            "BUDGET_RUNTIME_INTEGRATION=1 enables isolated PG/Redis verification"
        )
    root = Path(__file__).resolve().parents[4]
    evidence = tmp_path / "budget-evidence.json"
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            str(root / path)
            for path in (".", "apps/runtime-service/src", "apps/platform-api/src")
        ),
        "BUDGET_EVIDENCE_PATH": str(evidence),
    }
    result = subprocess.run(
        [sys.executable, str(root / "scripts/verify_execution_budget.py")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-12000:]
    assert json.loads(evidence.read_text())["complete"] is True
