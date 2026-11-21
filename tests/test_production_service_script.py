import json
import shutil
import subprocess
from configparser import ConfigParser
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("service", "app", "program", "args"),
    [
        (
            "runtime-api",
            "runtime-service",
            "graphharbor",
            [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "8123",
                "--config",
                "langgraph.json",
                "--n-jobs-per-worker",
                "0",
            ],
        ),
        (
            "runtime-worker",
            "runtime-service",
            "graphharbor",
            ["worker", "--config", "langgraph.json", "--n-jobs-per-worker", "1"],
        ),
        (
            "platform-api",
            "platform-api",
            "uvicorn",
            [
                "platform_api.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "2142",
                "--workers",
                "1",
                "--env-file",
                ".env",
            ],
        ),
    ],
)
def test_production_service_uses_owned_source_and_single_worker(
    tmp_path, service, app, program, args
):
    root = Path(__file__).resolve().parents[1]
    script = tmp_path / "scripts" / "run_production_service.sh"
    script.parent.mkdir()
    shutil.copyfile(root / "scripts" / script.name, script)
    executable = tmp_path / "apps" / app / ".venv" / "bin" / program
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "print(json.dumps({'cwd': os.getcwd(), 'args': sys.argv[1:]}))\n"
    )
    executable.chmod(0o700)
    result = subprocess.run(
        ["bash", str(script), service],
        cwd="/",
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "cwd": str(tmp_path / "apps" / app),
        "args": args,
    }


def test_unknown_production_service_does_not_start_a_process():
    script = (
        Path(__file__).resolve().parents[1] / "scripts" / "run_production_service.sh"
    )
    result = subprocess.run(
        ["bash", str(script), "unknown"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "Unknown service: unknown"


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        ("agent-runtime-api", ["256M", "384M", "256M"]),
        ("agent-runtime-worker", ["384M", "512M", "768M"]),
    ],
)
def test_4gb_service_budgets_match_approved_limits(service, expected):
    root = Path(__file__).resolve().parents[1]
    config = ConfigParser()
    config.read(root / "scripts" / "systemd" / "4gb" / f"{service}.conf")
    assert [
        config["Service"][key]
        for key in ("MemoryHigh", "MemoryMax", "MemorySwapMax")
    ] == expected


def test_redis_4gb_budget_only_sets_soft_memory_limit():
    root = Path(__file__).resolve().parents[1]
    config = ConfigParser()
    config.read(root / "scripts" / "systemd" / "4gb" / "redis.conf")
    assert dict(config["Service"]) == {"memoryhigh": "512M"}
