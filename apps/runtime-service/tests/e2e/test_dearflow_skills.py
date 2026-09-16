"""Opt-in formal skill acceptance through the real Platform gateway."""
import os

import pytest
from services.dearflow_agent.test_platform import (
    test_platform_creates_and_completes_dear_run as run_platform,
)


@pytest.mark.e2e
@pytest.mark.parametrize("skill_id", ["K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K09", "K10", "K11", "K12", "K13", "K12_EDIT", "K13_UPLOAD", "K17", "K18", "K19", "K20", "K21"])
def test_dearflow_skill(skill_id, monkeypatch):
    if os.environ.get("DEAR_SKILL_E2E") != "1":
        pytest.skip("DEAR_SKILL_E2E=1 enables real Platform, model and search usage")
    monkeypatch.setenv("DEAR_PLATFORM_TEST", "1")
    monkeypatch.setenv("DEAR_PLATFORM_SKILL_TEST", skill_id)
    monkeypatch.setenv("DEAR_PLATFORM_STREAM_VERSION", "v3")
    run_platform()
