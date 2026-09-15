import pytest

from runtime_service.runtime import runtime_context_hash, parse_runtime_context, RuntimeResolutionError
from runtime_service.services.dearflow_agent.modes import resolve_mode, apply_reasoning


def test_context_mode_is_signed_and_legacy_is_stable():
    assert runtime_context_hash({}) == runtime_context_hash({"execution_mode": None})
    assert len({runtime_context_hash({"execution_mode": mode}) for mode in ("flash", "standard", "pro", "ultra")}) == 4
    assert runtime_context_hash({}) != runtime_context_hash({"execution_mode": "standard"})
    for value in ("unknown", [], True, 1):
        with pytest.raises(RuntimeResolutionError):
            parse_runtime_context({"execution_mode": value})
    with pytest.raises(RuntimeResolutionError):
        resolve_mode("unknown")


def test_reasoning_configuration_does_not_mutate_model():
    from langchain_deepseek import ChatDeepSeek
    original = ChatDeepSeek(model="DeepSeek-V4-Flash", api_key="test", base_url="http://localhost")
    flash, flash_info = apply_reasoning(original, resolve_mode("flash"))
    pro, _ = apply_reasoning(original, resolve_mode("pro"))
    assert original.extra_body is None
    assert flash.extra_body["thinking"]["type"] == "disabled"
    assert pro.extra_body["thinking"]["type"] == "enabled"
    assert flash_info["reasoning"]["thinking"]["type"] == "disabled"
    configured = original.model_copy(update={"extra_body": {"private_extension": "not-for-tracing"}})
    updated, info = apply_reasoning(configured, resolve_mode("pro"))
    assert updated.extra_body["private_extension"] == "not-for-tracing"
    assert "private_extension" not in info["reasoning"]
    assert resolve_mode("ultra").delegation and not resolve_mode("pro").delegation
