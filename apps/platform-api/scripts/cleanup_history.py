"""Explicit local history cleanup. Preview by default; back up every target first."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from database import check_database, configured_engine, migration_config
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from platform_api.config import load_settings

ROOT = Path(__file__).resolve().parents[3]
HISTORY = (
    "runtime_events",
    "run_leases",
    "retry_counters",
    "runtime_message_inbox",
    "dear_external_tasks",
    "dear_skill_bindings",
    "checkpoint_writes",
    "checkpoint_blobs",
    "checkpoints",
    "runs",
    "threads",
)
TOKEN_FILTER = "expires_at <= CURRENT_TIMESTAMP OR revoked_at IS NOT NULL"


def local_url(value):
    url = make_url(value).set(drivername="postgresql+psycopg")
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not url.database:
        raise ValueError("Only explicit local PostgreSQL targets are allowed.")
    return url


def validate_test_name(name, protected):
    if (
        not re.fullmatch(r"platform_migration_test_[a-z0-9_]+", name)
        or name in protected
    ):
        raise ValueError(
            "Specify an exact migration test database; active databases are protected."
        )


def history_counts(connection, *, runtime):
    if runtime:
        if connection.execute(
            text(
                "SELECT count(*) FROM runs WHERE status NOT IN "
                "('success', 'error', 'failed', 'timeout', 'cancelled', 'canceled', 'interrupted')"
            )
        ).scalar_one():
            raise ValueError("Unfinished runs exist; finish or cancel them first.")
        if connection.execute(
            text("SELECT count(*) FROM crons WHERE enabled")
        ).scalar_one():
            raise ValueError("Enabled cron jobs exist; disable them first.")
        if connection.execute(
            text(
                "SELECT count(*) FROM dear_external_tasks WHERE status IN ('intent', 'pending', 'running', 'queued', 'claimed')"
            )
        ).scalar_one():
            raise ValueError("Pending external tasks exist.")
        return {
            name: connection.execute(
                text(f'SELECT count(*) FROM "{name}"')
            ).scalar_one()
            for name in HISTORY
        }
    return {
        "expired_or_revoked_tokens": connection.execute(
            text(f"SELECT count(*) FROM refresh_tokens WHERE {TOKEN_FILTER}")
        ).scalar_one(),
        **{
            name: connection.execute(
                text(f'SELECT count(*) FROM "{name}"')
            ).scalar_one()
            for name in ("run_requests", "audit_logs")
        },
    }


def clean(connection, *, runtime):
    names = HISTORY if runtime else ("refresh_tokens", "run_requests", "audit_logs")
    tables = ", ".join(f'"{name}"' for name in names)
    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    connection.execute(text(f"LOCK TABLE {tables} IN ACCESS EXCLUSIVE MODE"))
    before = history_counts(connection, runtime=runtime)
    if runtime:
        connection.execute(text(f"TRUNCATE TABLE {tables} RESTRICT"))
    else:
        connection.execute(text(f"DELETE FROM refresh_tokens WHERE {TOKEN_FILTER}"))
        connection.execute(text("TRUNCATE TABLE run_requests, audit_logs RESTRICT"))
    return before


def backup_database(url, directory, pg_bin):
    env = {
        **os.environ,
        "PGHOST": url.host,
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
    }
    target = directory / f"{url.database}.dump"
    # Open exclusively so retrying cannot overwrite a recovery copy.
    with target.open("xb") as output:
        target.chmod(0o600)
        subprocess.run(
            [str(pg_bin / "pg_dump"), "-Fc", "-d", url.database],
            env=env,
            stdout=output,
            stderr=subprocess.PIPE,
            check=True,
        )
    subprocess.run(
        [str(pg_bin / "pg_restore"), "--list", str(target)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        action="store_true",
        help="Expired/revoked tokens and all request/audit history",
    )
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="All conversations, including interrupted runs and checkpoints",
    )
    parser.add_argument("--drop-test-database", action="append", default=[])
    parser.add_argument("--confirm-database", action="append", default=[])
    parser.add_argument("--writers-stopped", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--pg-bin",
        type=Path,
        default=Path(
            os.environ.get(
                "PG_BIN", str(Path(shutil.which("pg_dump") or "pg_dump").parent)
            )
        ),
    )
    args = parser.parse_args()
    engines = []
    try:
        settings = load_settings()
        if settings.app_env not in {"local", "dev"}:
            raise ValueError("History cleanup is restricted to local/dev.")
        platform_url = local_url(settings.database_url or "")
        runtime_url = local_url(
            dotenv_values(ROOT / "apps/runtime-service/.env")["DATABASE_URI"]
        )
        if (platform_url.host, platform_url.port, platform_url.database) == (
            runtime_url.host,
            runtime_url.port,
            runtime_url.database,
        ):
            raise ValueError("Platform and Runtime must use separate databases.")
        protected = {
            platform_url.database,
            runtime_url.database,
            "postgres",
            "template0",
            "template1",
        }
        targets = []
        if args.platform:
            engine = configured_engine()
            engines.append(engine)
            with engine.connect() as connection:
                check_database(
                    connection, migration_config(settings.database_url or "")
                )
            targets.append((platform_url, engine, "platform"))
        if args.runtime:
            engine = create_engine(runtime_url, hide_parameters=True)
            engines.append(engine)
            targets.append((runtime_url, engine, "runtime"))
        admin = None
        if args.drop_test_database:
            admin_url = local_url(os.environ.get("CLEANUP_ADMIN_DATABASE_URL", ""))
            if admin_url.database != "postgres":
                raise ValueError(
                    "CLEANUP_ADMIN_DATABASE_URL must select the local postgres maintenance database."
                )
            admin = create_engine(
                admin_url, isolation_level="AUTOCOMMIT", hide_parameters=True
            )
            engines.append(admin)
            with admin.connect() as connection:
                for name in dict.fromkeys(args.drop_test_database):
                    validate_test_name(name, protected)
                    exists = connection.execute(
                        text("SELECT 1 FROM pg_database WHERE datname=:name"),
                        {"name": name},
                    ).scalar()
                    if exists:
                        targets.append((admin_url.set(database=name), None, "drop"))
                    else:
                        print(json.dumps({"database": name, "already_absent": True}))
        if not (args.platform or args.runtime or args.drop_test_database):
            raise ValueError(
                "Select --platform, --runtime or explicit --drop-test-database names."
            )
        if args.execute and (
            not args.writers_stopped
            or not {url.database for url, _, _ in targets} <= set(args.confirm_database)
        ):
            raise ValueError(
                "Stop writers and confirm every target database by exact name."
            )
        report = {}
        for url, engine, kind in targets:
            with (admin if kind == "drop" else engine).connect() as connection:
                if (
                    args.execute
                    and connection.execute(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE datname=:name AND pid <> pg_backend_pid()"
                        ),
                        {"name": url.database},
                    ).scalar_one()
                ):
                    raise ValueError(
                        f"Other connections exist for {url.database}; stop writers first."
                    )
                report[url.database] = {
                    "action": kind,
                    "counts": history_counts(connection, runtime=kind == "runtime")
                    if kind != "drop"
                    else {},
                }
        print(json.dumps(report))
        if not args.execute or not targets:
            return
        directory = (
            ROOT
            / "apps/platform-api/.data/backups"
            / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ-history-cleanup")
        )
        directory.mkdir(mode=0o700)
        for url, _, _ in targets:
            backup_database(url, directory, args.pg_bin)
        (directory / "manifest.json").write_text(json.dumps(report, indent=2))
        # Cross-database operations cannot be atomic; record each successful step for recovery.
        for url, engine, kind in targets:
            if kind == "drop":
                with admin.connect() as connection:
                    name = connection.dialect.identifier_preparer.quote(url.database)
                    connection.execute(text(f"DROP DATABASE {name}"))  # No FORCE.
            else:
                with engine.begin() as connection:
                    clean(connection, runtime=kind == "runtime")
            report[url.database]["completed"] = True
            (directory / "manifest.json").write_text(json.dumps(report, indent=2))
        print(
            json.dumps({"backup": str(directory.relative_to(ROOT)), "results": report})
        )
    except Exception as exc:  # noqa: BLE001 - redact driver and subprocess secrets at CLI boundary.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        raise SystemExit(f"History cleanup failed: {message}") from None
    finally:
        for engine in engines:
            engine.dispose()


if __name__ == "__main__":
    main()
