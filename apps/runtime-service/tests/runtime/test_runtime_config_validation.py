from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "validate_runtime_config.py"
SPEC = importlib.util.spec_from_file_location("validate_runtime_config", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _base(**overrides: str) -> dict[str, str]:
    values = {
        "PLATFORM_RUNTIME_DELEGATION_SECRET": "s" * 32,
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": "c" * 32,
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
        "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "https://runtime-service.local",
        "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
        "GRAPHHARBOR_WORKSPACE_ROOT": "/tmp/runtime-workspaces",
        "RUNTIME_WORKSPACE_MAX_FILE_BYTES": "1",
        "RUNTIME_WORKSPACE_MAX_FILES": "1",
        "RUNTIME_WORKSPACE_MAX_TOTAL_BYTES": "1",
        "RUNTIME_WORKSPACE_TTL_SECONDS": "1",
        "GRAPHHARBOR_RUN_TIMEOUT_SECONDS": "300",
    }
    values.update(overrides)
    return values


def _write(tmp_path: Path, values: dict[str, str]) -> Path:
    path = tmp_path / "runtime.env"
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8"
    )
    return path


def test_runtime_config_accepts_empty_model_catalog(tmp_path: Path) -> None:
    assert module.validate(_write(tmp_path, _base())) == []


def test_runtime_config_ignores_retired_profile_and_e2e_variables(
    tmp_path: Path,
) -> None:
    values = _base(RUNTIME_MODEL_PROFILE="legacy", RUNTIME_E2E="invalid")
    assert module.validate(_write(tmp_path, values)) == []


@pytest.mark.parametrize(
    "reserve", ["-1", "300", "301", "NaN", "Infinity", "True", "120.5"]
)
def test_runtime_config_rejects_invalid_wrapup_window(tmp_path, monkeypatch, reserve):
    monkeypatch.setenv("AGENT_RUN_WRAPUP_RESERVE_SECONDS", reserve)
    errors = module.validate(_write(tmp_path, _base()))
    assert any("AGENT_RUN_WRAPUP_RESERVE_SECONDS" in error for error in errors)


def test_runtime_config_accepts_disabled_reminder_with_small_hard_limit(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AGENT_RUN_WRAPUP_RESERVE_SECONDS", "0")
    assert (
        module.validate(_write(tmp_path, _base(GRAPHHARBOR_RUN_TIMEOUT_SECONDS="1")))
        == []
    )


@pytest.mark.parametrize("maximum", ["0", "-1", "True", "1.5", str(2**53)])
def test_invalid_token_budget_deployment_config(tmp_path, monkeypatch, maximum):
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", maximum)
    assert any(
        "MAX_TOKENS" in item for item in module.validate(_write(tmp_path, _base()))
    )


@pytest.mark.parametrize("enabled", ["true", "on"])
def test_token_budget_requires_usage_and_storage(tmp_path, monkeypatch, enabled):
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", "100")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "false")
    errors = module.validate(_write(tmp_path, _base()))
    assert any("RUNTIME_USAGE_ENABLED" in item for item in errors)
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", enabled)
    monkeypatch.setenv("DATABASE_URI", "postgresql://test/test")
    assert module.validate(_write(tmp_path, _base())) == []


def test_remote_config_fails_closed_and_local_needs_no_node(tmp_path, monkeypatch):
    for key in list(module.os.environ):
        if key.startswith(
            ("RUNTIME_SANDBOX_", "RUNTIME_BACKEND", "RUNTIME_EXECUTION_HOST_ID")
        ):
            monkeypatch.delenv(key)
    assert (
        module.validate(
            _write(
                tmp_path,
                _base(RUNTIME_BACKEND="local", RUNTIME_SANDBOX_TARGET="remote"),
            )
        )
        == []
    )
    errors = module.validate(
        _write(
            tmp_path, _base(RUNTIME_BACKEND="docker", RUNTIME_SANDBOX_TARGET="remote")
        )
    )
    assert any("Sandbox Node configuration" in error for error in errors)
    assert any("DATABASE_URI" in error for error in errors)


def test_remote_config_validates_project_env_without_local_docker(
    tmp_path, monkeypatch
):
    from workspace.test_node_certificates import generator

    from runtime_service.workspace.target import NodeConnection

    root = tmp_path.resolve()
    secrets = root / "secrets"
    generator()(secrets, "127.0.0.1", "test-host", "127.0.0.1/32")
    values = _base(
        RUNTIME_BACKEND="docker",
        RUNTIME_SANDBOX_TARGET="remote",
        DATABASE_URI="postgresql://isolated/test",
        RUNTIME_SANDBOX_NODE_URL="https://127.0.0.1:19111",
        RUNTIME_SANDBOX_NODE_ID="test-node",
        RUNTIME_EXECUTION_HOST_ID="test-host",
        RUNTIME_SANDBOX_NODE_AUTH_FILE=str(secrets / "caller-token"),
        RUNTIME_SANDBOX_NODE_CA_FILE=str(secrets / "ca.pem"),
        RUNTIME_SANDBOX_NODE_CLIENT_CERT_FILE=str(secrets / "client.pem"),
        RUNTIME_SANDBOX_NODE_CLIENT_KEY_FILE=str(secrets / "client-key.pem"),
    )
    for key in values:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(module, "_settings", lambda path: values)
    path = _write(root, values)
    assert module.validate(path) == []
    connection = NodeConnection.load(values)
    assert connection.token not in repr(connection)
    token = secrets / "caller-token"
    token.chmod(0o644)
    assert any("Sandbox Node configuration" in error for error in module.validate(path))
    token.chmod(0o600)
    values["RUNTIME_SANDBOX_NODE_URL"] = "http://127.0.0.1:19111"
    assert any("Sandbox Node configuration" in error for error in module.validate(path))
    values["RUNTIME_SANDBOX_NODE_URL"] = "https://127.0.0.1:99999"
    assert any("Sandbox Node configuration" in error for error in module.validate(path))
