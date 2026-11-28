"""CLI entrypoint for standalone CI gates, worker polling, and patrols."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from eval_runner.domain.contracts import Case, Evidence, GateLimits
from eval_runner.engine.concurrent_runner import ConcurrentEvalRunner

app = typer.Typer(help="Independent concurrent evaluation runner and CI gate CLI.")


@app.command("gate")
def run_gate(
    cases_file: Path = typer.Option(..., exists=True, help="JSONL or JSON list of Case specs"),
    concurrency: int = typer.Option(3, min=1, max=5),
) -> None:
    """Validate and dry-check a local suite file for CI gating."""
    raw_lines = [
        line.strip()
        for line in cases_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases = [(Case.model_validate_json(line), 1) for line in raw_lines]
    runner = ConcurrentEvalRunner(concurrency=concurrency)
    res = runner.run_batch(
        cases=cases,
        execute_fn=lambda c, k: Evidence(
            case_key=c.case_key, attempt_idx=k, final_answer="ok"
        ),
        limits=GateLimits(),
    )
    typer.echo(json.dumps(res["gate"], ensure_ascii=False))
    raise typer.Exit(code=res["gate"]["exit_code"])


@app.command("worker")
def run_worker(
    concurrency: int = typer.Option(3, min=1, max=5),
    loop: bool = typer.Option(False, help="Continuously poll database for queued runs"),
    once: bool = typer.Option(False, help="Poll and execute at most one queued run"),
    poll_interval: float = typer.Option(2.0, min=0.5, max=30.0),
    env_file: Path | None = typer.Option(None, help="Optional .env file to load"),
) -> None:
    """Start background evaluation worker loop (reads PLATFORM_API_DATABASE_URL)."""
    import os
    from eval_runner.worker import poll_and_execute_once, run_worker_loop

    if env_file and env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val

    if loop:
        run_worker_loop(poll_interval=poll_interval)
        return
    if once:
        res = poll_and_execute_once(
            os.environ["PLATFORM_API_DATABASE_URL"],
            base_url=os.environ.get("PLATFORM_API_BASE_URL", "http://127.0.0.1:2142"),
            internal_secret=os.environ.get("PLATFORM_API_RUNTIME_DELEGATION_SECRET"),
        )
        typer.echo(json.dumps(res or {"status": "idle"}, ensure_ascii=False))
        return
    typer.echo(f"eval-runner worker initialized (default_concurrency={concurrency})")
