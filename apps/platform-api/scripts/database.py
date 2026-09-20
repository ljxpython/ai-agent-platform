"""Explicit PostgreSQL preflight, schema migration and local ledger cleanup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from platform_api.config import load_settings

APP_DIR = Path(__file__).resolve().parents[1]


def migration_config(url: str) -> Config:
    config = Config(str(APP_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def configured_engine():
    settings = load_settings()
    if not settings.platform_db_enabled or settings.platform_db_auto_create:
        raise ValueError("Database must be enabled and auto-create disabled.")
    url = make_url(settings.database_url or "")
    if url.drivername != "postgresql+psycopg" or not url.database:
        raise ValueError("Configure a dedicated postgresql+psycopg database.")
    if url.database in {"postgres", "template0", "template1"}:
        raise ValueError("A maintenance database cannot host Platform API.")
    return create_engine(url, connect_args={"connect_timeout": 5}, hide_parameters=True)


def check_database(connection, config: Config, *, require_head: bool = True):
    identity = connection.execute(text("SELECT current_database(), current_user")).one()
    revisions = MigrationContext.configure(connection).get_current_heads()
    heads = tuple(ScriptDirectory.from_config(config).get_heads())
    tables = set(inspect(connection).get_table_names())
    if not revisions and tables - {"alembic_version"}:
        raise ValueError(
            "Unversioned nonempty schema: inspect it; do not stamp or auto-create."
        )
    if revisions and not set(revisions) <= {
        revision.revision
        for revision in ScriptDirectory.from_config(config).walk_revisions()
    }:
        raise ValueError("Unknown database revision.")
    if require_head and set(revisions) != set(heads):
        raise ValueError(
            "Database is not at Alembic head; run the explicit upgrade first."
        )
    return {"database": identity[0], "role": identity[1], "revisions": list(revisions)}


def clean_ledgers(connection, *, execute: bool):
    # No CASCADE: unexpected incoming foreign keys must fail without deleting other data.
    names = ("run_requests", "audit_logs")
    if execute:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(
            text("LOCK TABLE run_requests, audit_logs IN ACCESS EXCLUSIVE MODE")
        )
    counts = {
        name: connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one()
        for name in names
    }
    if execute:
        connection.execute(text("TRUNCATE TABLE run_requests, audit_logs RESTRICT"))
    return counts


def clean_projects(connection, keep_project: str, *, execute: bool):
    """Match project soft-delete semantics; retain history and global catalogs."""
    keep_id = str(UUID(keep_project))
    if execute:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(text("LOCK TABLE projects IN SHARE ROW EXCLUSIVE MODE"))
    keep = (
        connection.execute(
            text("SELECT id, name FROM projects WHERE id = :id AND status = 'active'"),
            {"id": keep_id},
        )
        .mappings()
        .one_or_none()
    )
    if keep is None:
        raise ValueError("The retained project must exist and be active.")
    targets = (
        connection.execute(
            text(
                "SELECT id, name FROM projects WHERE id <> :id AND status <> 'deleted'"
            ),
            {"id": keep_id},
        )
        .mappings()
        .all()
    )
    if execute:
        connection.execute(
            text(
                "UPDATE projects SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP, "
                "updated_at = CURRENT_TIMESTAMP WHERE id <> :id AND status <> 'deleted'"
            ),
            {"id": keep_id},
        )
    return {
        "keep": dict(keep),
        "soft_deleted_count": len(targets),
        "projects": [dict(row) for row in targets],
        "history": "Agents, memberships, policies, runtime data and audit history retained.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("check", "preflight", "upgrade", "clean-ledgers", "clean-projects"),
    )
    parser.add_argument(
        "--execute", action="store_true", help="Otherwise cleanup is read-only."
    )
    parser.add_argument("--confirm-database")
    parser.add_argument("--writers-stopped", action="store_true")
    parser.add_argument(
        "--keep-project", help="Exact UUID of the active project to retain."
    )
    args = parser.parse_args()
    engine = None
    try:
        settings = load_settings()
        engine = configured_engine()
        config = migration_config(settings.database_url or "")
        with engine.connect() as connection:
            info = check_database(
                connection,
                config,
                require_head=args.action not in {"preflight", "upgrade"},
            )
        print(json.dumps(info))
        if args.action == "upgrade":
            command.upgrade(config, "head")
            with engine.connect() as connection:
                check_database(connection, config)
        elif args.action in {"clean-ledgers", "clean-projects"}:
            if settings.app_env not in {"local", "dev"}:
                raise ValueError("This cleanup command is restricted to local/dev.")
            if args.execute and (
                (args.action == "clean-ledgers" and not args.writers_stopped)
                or args.confirm_database != info["database"]
            ):
                raise ValueError(
                    "Stop all writers and explicitly confirm the exact database."
                )
            with engine.begin() as connection:
                if args.action == "clean-projects":
                    if not args.keep_project:
                        raise ValueError("Specify --keep-project UUID.")
                    print(
                        json.dumps(
                            clean_projects(
                                connection, args.keep_project, execute=args.execute
                            ),
                            default=str,
                        )
                    )
                    return
                print(
                    json.dumps(
                        {
                            "execute": args.execute,
                            "tables": clean_ledgers(connection, execute=args.execute),
                        }
                    )
                )
    except Exception as exc:  # noqa: BLE001 - CLI boundary must redact driver/config secrets.
        # Driver exceptions can contain SQL parameters and credentials.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        raise SystemExit(f"Database operation failed: {message}") from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
