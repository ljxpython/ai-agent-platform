"""Copy local development configuration data into an empty, owned Worktree database."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from local_stack_worktree import (
    check_install_directories,
    configs,
    endpoint,
    read_env,
    record,
)
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Json, Jsonb

PLATFORM_TABLES = (
    "tenants",
    "users",
    "projects",
    "project_members",
    "service_accounts",
    "service_account_project_grants",
    "agents",
    "runtime_catalog_models",
    "runtime_catalog_graphs",
    "runtime_catalog_tools",
    "project_graph_policies",
    "project_model_policies",
    "runtime_tool_restrictions",
    "announcements",
    "platform_config_entries",
)
RUNTIME_TABLES = ("assistants", "assistant_versions", "dear_skills")
SCHEMA_TABLES = {
    "alembic_version",
    "runtime_app_alembic_version",
    "checkpoint_migrations",
    "store_migrations",
    "runtime_schema",
    "_local_stack_seed",
}


def columns(connection, table: str) -> list[tuple[str, str]]:
    return connection.execute(
        "SELECT attname, format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = to_regclass(%s) AND attnum > 0 AND NOT attisdropped ORDER BY attname",
        (f"public.{table}",),
    ).fetchall()


def prepare_platform(target, source_config: dict, target_config: dict) -> None:
    from platform_api.core.security.passwords import hash_password
    from platform_api.modules.runtime_catalog.application.credentials import (
        decrypt_api_key,
        encrypt_api_key,
    )

    for model_id, ciphertext in target.execute(
        "SELECT id, api_key_ciphertext FROM public.runtime_catalog_models"
    ).fetchall():
        if not ciphertext:
            continue
        plaintext = decrypt_api_key(
            ciphertext,
            master_key=source_config.get("PLATFORM_API_MODEL_CONFIG_MASTER_KEY"),
        )
        encrypted = encrypt_api_key(
            plaintext, master_key=target_config["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"]
        )
        target.execute(
            "UPDATE public.runtime_catalog_models SET api_key_ciphertext = %s WHERE id = %s",
            (encrypted, model_id),
        )
    for table in ("runtime_catalog_graphs", "runtime_catalog_tools"):
        target.execute(
            sql.SQL("UPDATE {} SET runtime_id = %s WHERE runtime_id = %s").format(
                sql.Identifier("public", table)
            ),
            (
                target_config["PLATFORM_API_LANGGRAPH_UPSTREAM_URL"].rstrip("/"),
                source_config.get(
                    "PLATFORM_API_LANGGRAPH_UPSTREAM_URL", "http://127.0.0.1:8123"
                ).rstrip("/"),
            ),
        )
    username = target_config["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"]
    password = hash_password(target_config["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"])
    user = target.execute(
        "SELECT id FROM public.users WHERE username = %s", (username,)
    ).fetchone()
    if not user:
        # Preserve all copied IDs; only add the local administrator when the source lacks it.
        target.execute(
            "INSERT INTO public.users (id, external_subject, username, password_hash, status, "
            "is_super_admin, platform_roles_json, must_change_password, failed_login_attempts) "
            "VALUES (%s, %s, %s, %s, 'active', true, %s, false, 0)",
            (
                uuid4(),
                f"local-stack:{uuid4()}",
                username,
                password,
                Json(["platform_super_admin"]),
            ),
        )
    else:
        target.execute(
            "UPDATE public.users SET password_hash = %s, status = 'active', "
            "is_super_admin = true, platform_roles_json = %s, must_change_password = false, "
            "failed_login_attempts = 0, locked_until = NULL WHERE id = %s",
            (password, Json(["platform_super_admin"]), user[0]),
        )


def seed_state(target, entry: dict, kind: str) -> tuple[str, dict, list[str]]:
    identity = target.execute(
        "SELECT current_database(), current_user, shobj_description(oid, 'pg_database') "
        "FROM pg_database WHERE datname = current_database()"
    ).fetchone()
    name = entry["databases"][kind]
    if identity != (name, name, "local-stack:" + entry["id"]):
        raise ValueError("Refusing to seed a database not owned by this Worktree")
    if target.execute("SELECT to_regclass('public._local_stack_seed')").fetchone()[0]:
        existing = target.execute(
            "SELECT environment_id, report FROM public._local_stack_seed"
        ).fetchall()
        if existing:
            if len(existing) != 1 or existing[0][0] != entry["id"]:
                raise ValueError("Database seed marker belongs to another environment")
            return "already-seeded", existing[0][1], []
    tables = [
        row[0]
        for row in target.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        if row[0] not in SCHEMA_TABLES
    ]
    for table in tables:
        if target.execute(
            sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier("public", table))
        ).fetchone():
            return "existing-data-retained", {}, tables
    return "empty", {}, tables


def copy_database(
    source_uri: str,
    target_uri: str,
    entry: dict,
    kind: str,
    source_config: dict,
    target_config: dict,
) -> dict:
    for uri in (source_uri, target_uri):
        endpoint(uri)
        parameters = conninfo_to_dict(uri)
        if (
            parameters.get("host") not in {"localhost", "127.0.0.1", "::1"}
            or parameters.get("hostaddr", "127.0.0.1") not in {"127.0.0.1", "::1"}
            or parameters.get("service")
        ):
            raise ValueError(
                "Baseline copy requires a local server without connection overrides"
            )
    with psycopg.connect(target_uri, connect_timeout=30) as target:
        target.execute("SET LOCAL lock_timeout = '5s'")
        target.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", ("local-stack:seed",)
        )
        state, report, business_tables = seed_state(target, entry, kind)
        if state == "already-seeded":
            return {"status": state, "tables": report}
        if state != "empty":
            raise ValueError(
                "Target database is not empty; baseline copy never overwrites existing data"
            )
        target.execute(
            "CREATE TABLE IF NOT EXISTS public._local_stack_seed "
            "(environment_id text PRIMARY KEY, report jsonb NOT NULL)"
        )
        if business_tables:
            target.execute(
                sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                    sql.SQL(", ").join(
                        sql.Identifier("public", name) for name in business_tables
                    )
                )
            )
        for table in business_tables:
            if target.execute(
                sql.SQL("SELECT 1 FROM {} LIMIT 1").format(
                    sql.Identifier("public", table)
                )
            ).fetchone():
                raise ValueError(
                    "Target database is not empty; baseline copy never overwrites existing data"
                )
        tables = PLATFORM_TABLES if kind == "platform" else RUNTIME_TABLES
        with psycopg.connect(source_uri, connect_timeout=30) as source:
            source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            if (
                source.info.dbname == target.info.dbname
                and source.info.port == target.info.port
            ):
                raise ValueError("Source and target databases must be different")
            report = {}
            for table in tables:
                signature = columns(source, table)
                if not signature or signature != columns(target, table):
                    raise ValueError(
                        f"Baseline schema differs for {table}; explicit mapping is required"
                    )
                identifier = sql.Identifier("public", table)
                names = sql.SQL(", ").join(
                    sql.Identifier(name) for name, _ in signature
                )
                # Binary COPY preserves SQL NULL, JSON, UUIDs and timestamps without a dump file.
                with (
                    source.cursor().copy(
                        sql.SQL("COPY {} ({}) TO STDOUT (FORMAT BINARY)").format(
                            identifier, names
                        )
                    ) as outgoing,
                    target.cursor().copy(
                        sql.SQL("COPY {} ({}) FROM STDIN (FORMAT BINARY)").format(
                            identifier, names
                        )
                    ) as incoming,
                ):
                    for chunk in outgoing:
                        incoming.write(chunk)
                count = sql.SQL("SELECT count(*) FROM {}").format(identifier)
                report[table] = source.execute(count).fetchone()[0]
                if report[table] != target.execute(count).fetchone()[0]:
                    raise ValueError(f"Baseline row count differs for {table}")
            if kind == "platform":
                prepare_platform(target, source_config, target_config)
            target.execute(
                "INSERT INTO public._local_stack_seed VALUES (%s, %s)",
                (entry["id"], Jsonb(report)),
            )
        return {"status": "seeded", "tables": report}


def seed_environment(
    root: Path, common: Path, primary: Path, *, if_empty: bool = False
) -> dict:
    check_install_directories(root)
    entry = record(root, common)
    runtime, platform = configs(root, entry)
    sys.path.insert(0, str(root / "apps/platform-api/src"))
    databases = (
        ("platform", "platform-api", "PLATFORM_API_DATABASE_URL", platform),
        ("runtime", "runtime-service", "DATABASE_URI", runtime),
    )
    states = {}
    for kind, _, key, values in databases:
        with psycopg.connect(
            values[key].replace("postgresql+psycopg:", "postgresql:"), connect_timeout=30
        ) as target:
            states[kind] = seed_state(target, entry, kind)
    if any(state[0] == "existing-data-retained" for state in states.values()):
        if not if_empty:
            raise ValueError(
                "Target database is not empty; baseline copy never overwrites existing data"
            )
        print(
            "[seed] existing environment data retained; automatic baseline copy skipped"
        )
        return {
            kind: {"status": "existing-data-retained", "tables": {}} for kind in states
        }
    report = {}
    for kind, app, key, values in databases:
        if states[kind][0] == "already-seeded":
            report[kind] = {"status": "already-seeded", "tables": states[kind][1]}
            continue
        baseline = read_env(primary / "apps" / app / ".env")
        report[kind] = copy_database(
            baseline[key].replace("postgresql+psycopg:", "postgresql:"),
            values[key].replace("postgresql+psycopg:", "postgresql:"),
            entry,
            kind,
            baseline,
            values,
        )
        print(
            f"[seed] {kind}: {report[kind]['status']} ({sum(report[kind]['tables'].values())} baseline rows)"
        )
    return report
