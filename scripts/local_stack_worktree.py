"""Register and isolate native development stacks for linked Git worktrees."""

from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

PORT_KEYS = (
    "PLATFORM_WEB_PORT",
    "PLATFORM_API_PORT",
    "RUNTIME_PORT",
    "LOCAL_STACK_REDIS_PORT",
)
CALLBACKS = {
    "PLATFORM_THREAD_AUTHORIZATION_URL": "thread-authorization",
    "PLATFORM_RUNTIME_MODEL_CONFIG_URL": "model-config",
    "PLATFORM_RUNTIME_MESSAGE_AUTH_URL": "message-authorization",
    "PLATFORM_RUNTIME_MEMORY_AUTH_URL": "memory-authorization",
}


def git_paths(root: Path) -> tuple[Path, Path, bool]:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True
        ).strip()

    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    private = Path(git("rev-parse", "--absolute-git-dir"))
    primary = Path(git("worktree", "list", "--porcelain", "-z").split("\0")[0][9:])
    return common.resolve(), primary.resolve(), common.resolve() != private.resolve()


@contextmanager
def file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_registry(common: Path) -> dict:
    path = common / "local-stacks/registry.json"
    value = (
        json.loads(path.read_text())
        if path.exists()
        else {"version": 1, "environments": {}}
    )
    if value.get("version") != 1 or not isinstance(value.get("environments"), dict):
        raise ValueError("Invalid local stack registry; preserve it for inspection")
    return value


def free_port(port: int) -> bool:
    with socket.socket() as listener:
        try:
            listener.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def reserve(root: Path, common: Path) -> dict:
    directory = common / "local-stacks"
    with file_lock(directory / "registry.lock"):
        registry = read_registry(common)
        existing = registry["environments"].get(str(root))
        if existing:
            return existing
        used = {
            port
            for entry in registry["environments"].values()
            for port in entry["ports"].values()
        }
        ports = {}
        candidates = list(range(23000, 30000))
        secrets.SystemRandom().shuffle(candidates)
        for port in candidates:
            if port not in used and free_port(port):
                ports[PORT_KEYS[len(ports)]] = port
                if len(ports) == len(PORT_KEYS):
                    break
        if len(ports) != len(PORT_KEYS):
            raise ValueError("No free ports in the local stack pool (23000-29999)")
        environment_id = "wt_" + secrets.token_hex(6)
        entry = {
            "id": environment_id,
            "root": str(root),
            "ports": ports,
            "databases": {
                key: f"{environment_id}_{key}" for key in ("runtime", "platform")
            },
        }
        registry["environments"][str(root)] = entry
        write_json(directory / "registry.json", registry)
        return entry


def record(root: Path, common: Path) -> dict:
    path = root / ".local-stack/environment.json"
    if not path.is_file():
        raise ValueError(
            "Worktree is not initialized; run bash scripts/local-stack.sh init"
        )
    entry = json.loads(path.read_text())
    if entry != read_registry(common)["environments"].get(str(root)):
        raise ValueError("Worktree configuration does not match the shared registry")
    if entry.get("root") != str(root) or not re.fullmatch(
        r"wt_[0-9a-f]{12}", entry.get("id", "")
    ):
        raise ValueError("Invalid Worktree identity")
    if set(entry["ports"]) != set(PORT_KEYS) or len(
        set(entry["ports"].values())
    ) != len(PORT_KEYS):
        raise ValueError("Invalid Worktree port allocation")
    if any(
        type(port) is not int or not 23000 <= port < 30000
        for port in entry["ports"].values()
    ):
        raise ValueError("Worktree ports must be in the registered pool")
    if entry["databases"] != {
        key: f"{entry['id']}_{key}" for key in ("runtime", "platform")
    }:
        raise ValueError("Invalid Worktree database allocation")
    return entry


def read_env(path: Path) -> dict[str, str]:
    from dotenv import dotenv_values

    if not path.is_file():
        raise ValueError(f"Missing local configuration file: {path}")
    values = {
        key: value
        for key, value in dotenv_values(path, interpolate=False).items()
        if value is not None
    }
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in values):
        raise ValueError("Invalid environment variable name")
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    from dotenv import set_key

    path.touch(mode=0o600)
    os.chmod(path, 0o600)
    for key, value in values.items():
        set_key(path, key, value)


def endpoint(value: str) -> tuple[str, int]:
    parsed = urlparse(value)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Worktree PostgreSQL provisioning requires a local server")
    return parsed.hostname, parsed.port or 5432


def expected_values(root: Path, entry: dict) -> tuple[dict[str, str], dict[str, str]]:
    ports = entry["ports"]
    api = f"http://127.0.0.1:{ports['PLATFORM_API_PORT']}"
    runtime = {
        **{
            key: f"{api}/api/runtime/internal/{suffix}"
            for key, suffix in CALLBACKS.items()
        },
        "RUNTIME_SELF_URL": f"http://127.0.0.1:{ports['RUNTIME_PORT']}",
        "RUNTIME_SERVICE_PORT": str(ports["RUNTIME_PORT"]),
        "GRAPHHARBOR_WORKSPACE_ROOT": str(root / ".local-stack/workspaces/graphharbor"),
        "RUNTIME_SHOWCASE_WORKSPACE_ROOT": str(
            root / ".local-stack/workspaces/showcase"
        ),
        "RUNTIME_WORKSPACE_ROOT": str(root / ".local-stack/workspaces/runtime"),
        "RUNTIME_GRAPH_CONFIG_PATH": str(root / "apps/runtime-service/langgraph.json"),
        "RUNTIME_BACKEND": "local",
    }
    platform = {
        "PLATFORM_API_LANGGRAPH_UPSTREAM_URL": runtime["RUNTIME_SELF_URL"],
        "PLATFORM_API_PLATFORM_DB_ENABLED": "true",
        "PLATFORM_API_PLATFORM_DB_AUTO_CREATE": "false",
        "PLATFORM_API_APP_ENV": "local",
        "PLATFORM_API_AUTH_REQUIRED": "true",
        "PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED": "true",
        "PLATFORM_API_CORS_ALLOW_ORIGINS": json.dumps(
            [
                f"http://127.0.0.1:{ports['PLATFORM_WEB_PORT']}",
                f"http://localhost:{ports['PLATFORM_WEB_PORT']}",
            ]
        ),
    }
    return runtime, platform


def web_overrides(entry: dict) -> dict[str, str]:
    return {
        "VITE_PLATFORM_API_URL": "/",
        "VITE_PLATFORM_API_RUNTIME_ENABLED": "true",
        "VITE_DEV_PORT": str(entry["ports"]["PLATFORM_WEB_PORT"]),
        "VITE_DEV_PROXY_TARGET": f"http://127.0.0.1:{entry['ports']['PLATFORM_API_PORT']}",
    }


def configs(root: Path, entry: dict) -> tuple[dict[str, str], dict[str, str]]:
    runtime = read_env(root / ".local-stack/runtime.env")
    platform = read_env(root / ".local-stack/platform.env")
    expected_runtime, expected_platform = expected_values(root, entry)
    for values, expected in (
        (runtime, expected_runtime),
        (platform, expected_platform),
    ):
        if any(values.get(key) != value for key, value in expected.items()):
            raise ValueError(
                "Worktree resource addresses differ from the registered environment"
            )
    for key, value in (
        ("runtime", runtime.get("DATABASE_URI", "")),
        ("platform", platform.get("PLATFORM_API_DATABASE_URL", "")),
    ):
        parsed = urlparse(value)
        endpoint(value)
        if (
            parsed.path != "/" + entry["databases"][key]
            or parsed.username != entry["databases"][key]
            or not parsed.password
        ):
            raise ValueError(
                "Worktree database/role differs from the registered environment"
            )
    parsed = urlparse(runtime.get("REDIS_URI", ""))
    if (parsed.hostname, parsed.port, parsed.path) != (
        "127.0.0.1",
        entry["ports"]["LOCAL_STACK_REDIS_PORT"],
        "/0",
    ) or not parsed.password:
        raise ValueError("Worktree Redis differs from the registered environment")
    if len(runtime.get("PLATFORM_RUNTIME_DELEGATION_SECRET", "")) < 32 or runtime[
        "PLATFORM_RUNTIME_DELEGATION_SECRET"
    ] != platform.get("PLATFORM_API_RUNTIME_DELEGATION_SECRET"):
        raise ValueError("Worktree delegation secrets do not match")
    redis_settings = {}
    for line in (root / ".local-stack/redis.conf").read_text().splitlines():
        parts = shlex.split(line, comments=True)
        if parts:
            redis_settings[parts[0]] = parts[1:]
    required_redis = {
        "bind": ["127.0.0.1"],
        "protected-mode": ["yes"],
        "daemonize": ["no"],
        "port": [str(entry["ports"]["LOCAL_STACK_REDIS_PORT"])],
        "dir": [str(root / ".local-stack/redis")],
        "requirepass": [urlparse(runtime["REDIS_URI"]).password],
        "appendonly": ["yes"],
    }
    if any(redis_settings.get(key) != value for key, value in required_redis.items()):
        raise ValueError("Redis configuration differs from this Worktree's resources")
    return runtime, platform


def check_install_directories(root: Path) -> None:
    if (root / ".local-stack").is_symlink():
        raise ValueError("Use an independent .local-stack directory in this Worktree")
    for name in (
        "environment.json",
        "runtime.env",
        "platform.env",
        "web.env",
        "redis.conf",
        "pids",
        "logs",
        "redis",
        "workspaces",
        "workspaces/graphharbor",
        "workspaces/showcase",
        "workspaces/runtime",
    ):
        directory = root / ".local-stack" / name
        if not directory.resolve().is_relative_to((root / ".local-stack").resolve()):
            raise ValueError(
                "Use independent local state files and directories in this Worktree"
            )
    for app, name in (
        ("runtime-service", ".venv"),
        ("platform-api", ".venv"),
        ("platform-web", "node_modules"),
    ):
        directory = root / "apps" / app / name
        if directory.is_symlink() or not directory.resolve().is_relative_to(
            root.resolve()
        ):
            raise ValueError(
                f"Use an independent {name} in {app}; share package caches instead"
            )


def initialize(root: Path, common: Path, primary: Path) -> None:
    check_install_directories(root)
    baseline_runtime = read_env(primary / "apps/runtime-service/.env")
    baseline_platform = read_env(primary / "apps/platform-api/.env")
    runtime_endpoint = endpoint(baseline_runtime.get("DATABASE_URI", ""))
    if (
        runtime_endpoint[1]
        != endpoint(baseline_platform.get("PLATFORM_API_DATABASE_URL", ""))[1]
    ):
        raise ValueError(
            "Worktree initialization requires both databases on the same local PostgreSQL server"
        )
    entry = reserve(root, common)
    state = root / ".local-stack"
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not (state / "environment.json").exists():
        runtime_overrides, platform_overrides = expected_values(root, entry)
        runtime = {**baseline_runtime, **runtime_overrides}
        platform = {**baseline_platform, **platform_overrides}
        delegation = secrets.token_urlsafe(48)
        runtime["PLATFORM_RUNTIME_DELEGATION_SECRET"] = delegation
        runtime["GRAPHHARBOR_RUNTIME_CONTEXT_SECRET"] = secrets.token_urlsafe(48)
        platform["PLATFORM_API_RUNTIME_DELEGATION_SECRET"] = delegation
        for key in (
            "PLATFORM_API_JWT_ACCESS_SECRET",
            "PLATFORM_API_JWT_REFRESH_SECRET",
        ):
            platform[key] = secrets.token_urlsafe(48)
        for key in (
            "PLATFORM_API_JWT_ACCESS_VERIFICATION_KEYS",
            "PLATFORM_API_JWT_REFRESH_VERIFICATION_KEYS",
        ):
            platform[key] = "{}"
        platform["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"] = "admin"
        platform["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"] = "admin123"
        platform["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"] = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode()
        platform["PLATFORM_API_RUNTIME_MODEL_CONFIG_SECRET"] = delegation
        for key, values, variable, scheme in (
            ("runtime", runtime, "DATABASE_URI", "postgresql"),
            ("platform", platform, "PLATFORM_API_DATABASE_URL", "postgresql+psycopg"),
        ):
            name = entry["databases"][key]
            password = secrets.token_urlsafe(36)
            host, port = runtime_endpoint
            host = f"[{host}]" if ":" in host else host
            values[variable] = f"{scheme}://{name}:{password}@{host}:{port}/{name}"
        redis_password = secrets.token_urlsafe(36)
        runtime["REDIS_URI"] = (
            f"redis://:{redis_password}@127.0.0.1:{entry['ports']['LOCAL_STACK_REDIS_PORT']}/0"
        )
        for path in (
            state / "redis",
            *(
                Path(runtime[key])
                for key in runtime_overrides
                if key.endswith("WORKSPACE_ROOT")
            ),
        ):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        redis_config = (
            "bind 127.0.0.1\nprotected-mode yes\ndaemonize no\n"
            f"port {entry['ports']['LOCAL_STACK_REDIS_PORT']}\n"
            f"dir {json.dumps(str(state / 'redis'))}\nrequirepass {redis_password}\n"
            "save 60 1\nappendonly yes\nappendfsync everysec\nmaxmemory 512mb\nmaxmemory-policy noeviction\n"
        )
        (state / "redis.conf").write_text(redis_config)
        os.chmod(state / "redis.conf", 0o600)
        write_env(state / "runtime.env", runtime)
        write_env(state / "platform.env", platform)
        web = {}
        for name in (".env", ".env.local"):
            path = primary / "apps/platform-web" / name
            if path.is_file():
                web.update(read_env(path))
        write_env(state / "web.env", {**web, **web_overrides(entry)})
        write_json(state / "environment.json", entry)
    entry = record(root, common)
    database_resources(root, entry, destroy=False)
    print(
        f"[init] {entry['id']}: configuration and dedicated PostgreSQL databases ready"
    )
    print(
        f"[private-config] {state / 'platform.env'} (local administrator; baseline data is copied on first start)"
    )


def database_resources(root: Path, entry: dict, *, destroy: bool) -> None:
    import psycopg
    from psycopg import sql

    runtime, platform = configs(root, entry)
    marker = "local-stack:" + entry["id"]
    admin_dsn = os.environ.get("LOCAL_STACK_PG_ADMIN_DSN", "dbname=postgres")
    with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as connection:
        if connection.info.port != endpoint(runtime["DATABASE_URI"])[1] or (
            connection.info.host
            and not connection.info.host.startswith("/")
            and connection.info.host not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError(
                "PostgreSQL administrator connection must use the configured local server"
            )
        resources = []
        for key, uri in (
            ("runtime", runtime["DATABASE_URI"]),
            ("platform", platform["PLATFORM_API_DATABASE_URL"]),
        ):
            name = entry["databases"][key]
            role = connection.execute(
                "SELECT rolname, rolsuper, shobj_description(oid, 'pg_authid') FROM pg_roles WHERE rolname = %s",
                (name,),
            ).fetchone()
            database = connection.execute(
                "SELECT pg_get_userbyid(datdba), shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s",
                (name,),
            ).fetchone()
            if role and (role[1] or role[2] != marker):
                raise ValueError(
                    "Refusing to alter a PostgreSQL role not owned by this environment"
                )
            if database and database != (name, marker):
                raise ValueError(
                    "Refusing to alter a PostgreSQL database not owned by this environment"
                )
            if (
                destroy
                and database
                and connection.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname = %s)",
                    (name,),
                ).fetchone()[0]
            ):
                raise ValueError(
                    "Stop all database connections before destroying environment data"
                )
            resources.append((name, uri, role, database))
        for name, uri, role, database in resources:
            identifier = sql.Identifier(name)
            if destroy:
                if database:
                    connection.execute(sql.SQL("DROP DATABASE {}").format(identifier))
                if role:
                    connection.execute(sql.SQL("DROP ROLE {}").format(identifier))
                continue
            if not role:
                with connection.transaction():
                    connection.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
                        ).format(identifier, sql.Literal(urlparse(uri).password))
                    )
                    connection.execute(
                        sql.SQL("COMMENT ON ROLE {} IS {}").format(
                            identifier, sql.Literal(marker)
                        )
                    )
            if not database:
                connection.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        identifier, identifier
                    )
                )
                connection.execute(
                    sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                        identifier, sql.Literal(marker)
                    )
                )
                connection.execute(
                    sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(
                        identifier
                    )
                )


def export_environment(
    root: Path, common: Path, linked: bool, *, resources_only: bool = False
) -> dict[str, str]:
    check_install_directories(root)
    values = {
        "STATE_DIR": str(root / ".local-stack"),
        "LOCAL_STACK_WORKTREE": "1" if linked else "0",
    }
    if not linked:
        if resources_only:
            path = Path(
                os.environ.get(
                    "RUNTIME_ENV_FILE", str(root / "apps/runtime-service/.env")
                )
            )
            runtime = read_env(path) if path.is_file() else {}
            values["RUNTIME_PORT"] = (
                os.environ.get("RUNTIME_PORT")
                or os.environ.get("RUNTIME_SERVICE_PORT")
                or runtime.get("RUNTIME_SERVICE_PORT")
                or "8123"
            )
        return values
    entry = record(root, common)
    resources = {
        **values,
        **{key: str(port) for key, port in entry["ports"].items()},
        "LOCAL_STACK_ID": entry["id"],
        "RUNTIME_ENV_FILE": str(root / ".local-stack/runtime.env"),
        "PLATFORM_ENV_FILE": str(root / ".local-stack/platform.env"),
    }
    if resources_only:
        return resources
    runtime, platform = configs(root, entry)
    web_path = root / ".local-stack/web.env"
    web = read_env(web_path) if web_path.is_file() else {}
    if web and any(
        web.get(key) != value for key, value in web_overrides(entry).items()
    ):
        raise ValueError(
            "Worktree Web addresses differ from the registered environment"
        )
    return {
        **{key: value for key, value in web.items() if key.startswith("VITE_")},
        **runtime,
        **platform,
        **resources,
        "LOCAL_STACK_WORKER_JOBS": "1",
        "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{entry['ports']['PLATFORM_WEB_PORT']}",
        **web_overrides(entry),
    }


def destroy_environment(root: Path, common: Path, confirmation: str | None) -> None:
    from local_stack_processes import owned

    check_install_directories(root)
    entry = record(root, common)
    if confirmation != entry["id"]:
        raise ValueError(
            f"Destructive cleanup requires destroy --confirm {entry['id']}; databases and Workspace will be deleted"
        )
    for key in (
        "runtime-api",
        "runtime-worker",
        "platform-api",
        "platform-web",
        "redis",
    ):
        if owned(root, key):
            raise ValueError(
                "Stop all environment processes before destroying its data"
            )
    database_resources(root, entry, destroy=True)
    with file_lock(common / "local-stacks/registry.lock"):
        registry = read_registry(common)
        if registry["environments"].get(str(root)) != entry:
            raise ValueError(
                "Registry changed during cleanup; preserve the environment for inspection"
            )
        shutil.rmtree(root / ".local-stack")
        del registry["environments"][str(root)]
        write_json(common / "local-stacks/registry.json", registry)
    print(f"[destroy] {entry['id']}: dedicated data deleted and allocation released")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("run", "init", "seed", "exports", "destroy", "list")
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        common, primary, linked = git_paths(root)
        if args.action == "run":
            if not args.arguments:
                raise ValueError("Missing local stack command")
            env = dict(os.environ)
            for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"):
                env.pop(key, None)
            bootstrap = next(
                (
                    path
                    for path in (
                        root / "apps/runtime-service/.venv/bin/python",
                        primary / "apps/runtime-service/.venv/bin/python",
                    )
                    if path.is_file()
                ),
                Path(sys.executable),
            )
            env["LOCAL_STACK_PYTHON"] = str(bootstrap)
            env["PATH"] = str(bootstrap.parent) + os.pathsep + env.get("PATH", "")
            env["LOCAL_STACK_LOCKED_ROOT"] = str(root)
            with file_lock(
                common / f"local-stacks/operations/{secrets_hash(root)}.lock"
            ):
                result = subprocess.run(
                    ["bash", str(root / "scripts/local-stack.sh"), *args.arguments],
                    env=env,
                    check=False,
                )
            raise SystemExit(result.returncode)
        if args.action == "exports":
            for key, value in export_environment(
                root,
                common,
                linked,
                resources_only=args.arguments == ["--resources-only"],
            ).items():
                print(f"export {key}={shlex.quote(value)}")
        elif args.action == "list":
            print(json.dumps(read_registry(common), indent=2))
        elif not linked:
            raise ValueError(
                "init/seed/destroy are for linked Worktrees; primary workspace keeps its existing app configuration"
            )
        elif args.action == "init":
            initialize(root, common, primary)
        elif args.action == "seed":
            from local_stack_seed import seed_environment

            if args.arguments not in ([], ["--if-empty"]):
                raise ValueError(
                    "seed accepts only --if-empty for automatic initialization"
                )
            seed_environment(
                root, common, primary, if_empty=args.arguments == ["--if-empty"]
            )
        else:
            confirmation = (
                args.arguments[1]
                if len(args.arguments) == 2 and args.arguments[0] == "--confirm"
                else None
            )
            destroy_environment(root, common, confirmation)
    except ValueError as exc:
        raise SystemExit(f"ERROR {exc}") from None
    except Exception as exc:  # noqa: BLE001 - CLI boundary must redact config/driver secrets.
        # Database/config exceptions may contain credentials; only expose their type.
        raise SystemExit(
            f"ERROR Worktree operation failed ({type(exc).__name__}); check local configuration and PostgreSQL administrator access"
        ) from None


def secrets_hash(root: Path) -> str:
    import hashlib

    return hashlib.sha256(str(root).encode()).hexdigest()[:16]


if __name__ == "__main__":
    main()
