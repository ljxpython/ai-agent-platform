import pytest

from runtime_service.runtime import RuntimeResolutionError, interrupts_for_access_policy


def test_workspace_write_skips_only_workspace_tools() -> None:
    approvals = {name: object() for name in ("write_file", "edit_file", "execute", "deploy_preview")}
    assert set(interrupts_for_access_policy("review", approvals)) == set(approvals)
    assert set(interrupts_for_access_policy("workspace_write", approvals)) == {"deploy_preview"}


def test_full_access_skips_all_tools() -> None:
    approvals = {name: object() for name in ("write_file", "edit_file", "execute", "deploy_preview", "sensitive_mcp")}
    assert interrupts_for_access_policy("full_access", approvals) == {}


def test_unknown_access_policy_is_rejected() -> None:
    with pytest.raises(RuntimeResolutionError):
        interrupts_for_access_policy("auto", {})
