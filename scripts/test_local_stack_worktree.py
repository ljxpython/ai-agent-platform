"""Regression checks for concurrent allocation and Worktree resource boundaries."""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from local_stack_worktree import (
    check_install_directories,
    configs,
    database_resources,
    destroy_environment,
    export_environment,
    free_port,
    initialize,
    read_registry,
    record,
    reserve,
    write_env,
    write_json,
)


class WorktreeRegistryTest(unittest.TestCase):
    def test_playwright_worktree_configuration_fails_closed(self):
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "worktree"
            common = base / "common"
            private = root / "git-private"
            private.mkdir(parents=True)
            (common / "local-stacks").mkdir(parents=True)
            web = root / "apps/platform-web"
            (web / "e2e").mkdir(parents=True)
            shutil.copy2(repository / "apps/platform-web/package.json", web)
            # Only load configuration; no stack installation or service uses this fixture link.
            (web / "node_modules").symlink_to(
                repository / "apps/platform-web/node_modules"
            )
            shutil.copy2(repository / "apps/platform-web/playwright.config.ts", web)
            (web / "e2e/probe.spec.ts").write_text(
                'import {test} from "@playwright/test"; test("probe", () => {});'
            )
            binary = base / "bin"
            binary.mkdir()
            git = binary / "git"
            git.write_text(
                "#!/usr/bin/env python3\nimport sys\n"
                f"print({str(common)!r} if '--git-common-dir' in sys.argv else {str(private)!r})\n"
            )
            git.chmod(0o700)
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("PLAYWRIGHT_", "PLATFORM_TEST_", "RUN_"))
            }
            env["PATH"] = str(binary) + os.pathsep + env["PATH"]

            def check(message: str | None = None, overrides: dict | None = None):
                result = subprocess.run(
                    [
                        "node",
                        str(
                            repository
                            / "apps/platform-web/node_modules/@playwright/test/cli.js"
                        ),
                        "test",
                        "--list",
                    ],
                    cwd=web,
                    env={**env, **(overrides or {})},
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if message is None:
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(message, result.stdout + result.stderr)

            check("Initialize this Worktree")
            entry = reserve(root, common)
            (root / ".local-stack").mkdir()
            write_json(root / ".local-stack/environment.json", entry)
            check()
            check(
                "E2E URL must match", {"PLAYWRIGHT_BASE_URL": "http://127.0.0.1:3000"}
            )
            check(
                "Test API URL must match",
                {"PLATFORM_TEST_URL": "http://127.0.0.1:2142"},
            )
            for flag in (
                "RUN_ERROR_CONTRACT_E2E",
                "RUN_SSE_CONTRACT_E2E",
                "RUN_LOCAL_GOVERNANCE_E2E",
            ):
                check("shared legacy fixture", {flag: "1"})
            write_json(
                root / ".local-stack/environment.json", {**entry, "id": "wt_wrong"}
            )
            check("Invalid Worktree E2E environment")

    def test_parallel_allocation_is_unique_and_persistent(self):
        script = Path(__file__).with_name("local_stack_worktree.py")
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary) / "common"
            roots = [Path(temporary) / f"worktree-{index}" for index in range(6)]
            code = "from pathlib import Path; from local_stack_worktree import reserve; import sys; reserve(Path(sys.argv[1]), Path(sys.argv[2]))"
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", code, str(root), str(common)],
                    cwd=script.parent,
                )
                for root in roots
            ]
            for process in processes:
                self.assertEqual(process.wait(timeout=20), 0)
            registry = read_registry(common)
            entries = list(registry["environments"].values())
            ports = [port for entry in entries for port in entry["ports"].values()]
            self.assertEqual(len(entries), 6)
            self.assertEqual(len(set(ports)), 24)
            self.assertTrue(all(23000 <= port < 30000 for port in ports))
            self.assertEqual(
                reserve(roots[0], common), registry["environments"][str(roots[0])]
            )
            self.assertNotIn("password", json.dumps(registry).lower())

    def test_port_check_detects_wildcard_listener(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.assertFalse(free_port(listener.getsockname()[1]))

    def test_identity_missing_or_mismatched_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "worktree"
            common = Path(temporary) / "common"
            with self.assertRaisesRegex(ValueError, "not initialized"):
                export_environment(root, common, True)
            entry = reserve(root, common)
            (root / ".local-stack").mkdir(parents=True)
            write_json(
                root / ".local-stack/environment.json", {**entry, "id": "wt_wrong"}
            )
            with self.assertRaisesRegex(ValueError, "registry"):
                record(root, common)

    def test_shared_installation_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "worktree"
            external = Path(temporary) / "shared"
            external.mkdir()
            for app, directory in (
                ("runtime-service", ".venv"),
                ("platform-api", ".venv"),
                ("platform-web", "node_modules"),
            ):
                target = root / "apps" / app / directory
                target.parent.mkdir(parents=True)
                target.symlink_to(external, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "independent"):
                    check_install_directories(root)
                target.unlink()
                target.parent.rmdir()
                target.parent.symlink_to(external, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "independent"):
                    check_install_directories(root)
                target.parent.unlink()

    def test_shared_data_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "worktree"
            external = Path(temporary) / "shared"
            external.mkdir()
            (root / ".local-stack").mkdir(parents=True)
            for name in (
                "runtime.env",
                "platform.env",
                "environment.json",
                "redis.conf",
                "pids",
                "logs",
                "redis",
                "workspaces",
                "workspaces/graphharbor",
            ):
                target = root / ".local-stack" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(external, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "independent"):
                    check_install_directories(root)
                target.unlink()

    def test_detached_process_does_not_inherit_admin_connection_or_operation_lock(self):
        script = Path(__file__).with_name("local-stack.sh")
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "child.log"
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    r"""
source "$1" help >/dev/null
spawn_detached "$2" "python3 -c 'import os; print(any(k in os.environ for k in (\"LOCAL_STACK_PG_ADMIN_DSN\", \"LOCAL_STACK_LOCKED_ROOT\")))'" "$3"
""",
                    "test",
                    str(script),
                    temporary,
                    str(log),
                ],
                env={
                    **os.environ,
                    "LOCAL_STACK_PG_ADMIN_DSN": "test-only",
                    "LOCAL_STACK_LOCKED_ROOT": "test-only",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for _ in range(50):
                if log.exists() and log.read_text():
                    break
                time.sleep(0.1)
            self.assertEqual(log.read_text().strip(), "False")

    def test_generated_configs_override_main_addresses_and_roundtrip_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            primary = Path(temporary) / "primary"
            root = Path(temporary) / "worktree with spaces"
            common = Path(temporary) / "common"
            baseline_runtime = primary / "apps/runtime-service/.env"
            baseline_platform = primary / "apps/platform-api/.env"
            baseline_web = primary / "apps/platform-web/.env"
            baseline_runtime.parent.mkdir(parents=True)
            baseline_platform.parent.mkdir(parents=True)
            baseline_web.parent.mkdir(parents=True)
            secret = "spaces 'quotes' $dollars $(must_not_run)"
            write_env(
                baseline_runtime,
                {
                    "DATABASE_URI": "postgresql://runtime:private@127.0.0.1:5432/runtime",
                    "PROVIDER_KEY": secret,
                },
            )
            write_env(
                baseline_platform,
                {
                    "PLATFORM_API_DATABASE_URL": "postgresql+psycopg://platform:private@127.0.0.1:5432/platform",
                    "PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME": "main-admin",
                    "PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD": "main-private-password",
                    "PLATFORM_API_LANGGRAPH_UPSTREAM_TIMEOUT_SECONDS": "60",
                    "PLATFORM_API_JWT_ACCESS_VERIFICATION_KEYS": '{"main-old-key":"main-old-secret"}',
                },
            )
            write_env(
                baseline_web,
                {"VITE_TEST_LABEL": "baseline", "VITE_DEV_PORT": "3000"},
            )
            write_env(
                baseline_web.with_name(".env.local"),
                {
                    "VITE_TEST_LABEL": "local",
                    "VITE_DEV_PROXY_TARGET": "http://127.0.0.1:2142",
                },
            )
            with patch("local_stack_worktree.database_resources") as database:
                initialize(root, common, primary)
                database.assert_called_once()
            entry = record(root, common)
            runtime, platform = configs(root, entry)
            self.assertEqual(runtime["PROVIDER_KEY"], secret)
            self.assertEqual(platform["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"], "admin")
            self.assertEqual(
                platform["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"], "admin123"
            )
            self.assertEqual(
                platform["PLATFORM_API_LANGGRAPH_UPSTREAM_TIMEOUT_SECONDS"], "60"
            )
            self.assertEqual(
                platform["PLATFORM_API_JWT_ACCESS_VERIFICATION_KEYS"], "{}"
            )
            self.assertNotEqual(runtime["DATABASE_URI"].split("/")[-1], "runtime")
            self.assertEqual(
                platform["PLATFORM_API_LANGGRAPH_UPSTREAM_URL"],
                runtime["RUNTIME_SELF_URL"],
            )
            for key, suffix in (
                ("PLATFORM_RUNTIME_MODEL_CONFIG_URL", "model-config"),
                ("PLATFORM_THREAD_AUTHORIZATION_URL", "thread-authorization"),
            ):
                self.assertEqual(
                    runtime[key],
                    f"http://127.0.0.1:{entry['ports']['PLATFORM_API_PORT']}/api/runtime/internal/{suffix}",
                )
            exported = export_environment(root, common, True)
            self.assertEqual(exported["LOCAL_STACK_WORKER_JOBS"], "1")
            self.assertEqual(exported["VITE_TEST_LABEL"], "local")
            self.assertEqual(
                exported["VITE_DEV_PORT"], str(entry["ports"]["PLATFORM_WEB_PORT"])
            )
            self.assertEqual(
                exported["VITE_DEV_PROXY_TARGET"],
                f"http://127.0.0.1:{entry['ports']['PLATFORM_API_PORT']}",
            )
            self.assertEqual(exported["STATE_DIR"], str(root / ".local-stack"))
            before = (root / ".local-stack/runtime.env").read_bytes()
            with patch("local_stack_worktree.database_resources"):
                initialize(root, common, primary)
            self.assertEqual(before, (root / ".local-stack/runtime.env").read_bytes())
            self.assertEqual(
                (root / ".local-stack/platform.env").stat().st_mode & 0o777, 0o600
            )
            self.assertEqual(
                (root / ".local-stack/web.env").stat().st_mode & 0o777, 0o600
            )
            for variable, value in (
                ("DATABASE_URI", "postgresql://runtime:private@127.0.0.1:5432/runtime"),
                ("REDIS_URI", "redis://127.0.0.1:6379/7"),
                (
                    "PLATFORM_RUNTIME_MODEL_CONFIG_URL",
                    "http://127.0.0.1:2142/api/runtime/internal/model-config",
                ),
            ):
                with self.subTest(variable=variable):
                    write_env(root / ".local-stack/runtime.env", {variable: value})
                    with self.assertRaises(ValueError):
                        configs(root, entry)
                    self.assertEqual(
                        export_environment(root, common, True, resources_only=True)[
                            "LOCAL_STACK_ID"
                        ],
                        entry["id"],
                    )
                    write_env(
                        root / ".local-stack/runtime.env", {variable: runtime[variable]}
                    )
            redis_config = root / ".local-stack/redis.conf"
            redis_config.write_text(
                redis_config.read_text().replace("bind 127.0.0.1", "bind 0.0.0.0")
            )
            with self.assertRaisesRegex(ValueError, "Redis configuration"):
                configs(root, entry)

    def test_process_directory_symlink_outside_repository_is_rejected(self):
        from local_stack_processes import process_directory

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "worktree"
            external = Path(temporary) / "external"
            external.mkdir()
            (root / "apps").mkdir(parents=True)
            (root / "apps/platform-api").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "outside"):
                process_directory(root, "platform-api")

    @unittest.skipUnless(
        os.environ.get("LOCAL_STACK_INTEGRATION") == "1",
        "Requires explicitly enabled local PostgreSQL/redis-server integration",
    )
    def test_three_real_database_and_redis_environments(self):
        import psycopg
        from redis import Redis
        from redis.exceptions import ConnectionError as RedisConnectionError

        repository = Path(__file__).resolve().parents[1]
        processes = []
        entries = []
        clients = []
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary) / "common"
            roots = [Path(temporary) / f"worktree-{index}" for index in range(3)]
            try:
                for root in roots:
                    initialize(root, common, repository)
                    entry = record(root, common)
                    entries.append((root, entry))
                    runtime, platform = configs(root, entry)
                    for key, uri in (
                        ("runtime", runtime["DATABASE_URI"]),
                        (
                            "platform",
                            platform["PLATFORM_API_DATABASE_URL"].replace(
                                "postgresql+psycopg:", "postgresql:"
                            ),
                        ),
                    ):
                        with psycopg.connect(uri) as connection:
                            identity = connection.execute(
                                "SELECT current_database(), current_user"
                            ).fetchone()
                            self.assertEqual(
                                identity,
                                (entry["databases"][key], entry["databases"][key]),
                            )
                            connection.execute(
                                "CREATE TABLE isolation_probe (value text)"
                            )
                            connection.execute(
                                "INSERT INTO isolation_probe VALUES (%s)",
                                (entry["id"],),
                            )
                    stream = (root / ".local-stack/redis-test.log").open("w")
                    process = subprocess.Popen(
                        ["redis-server", str(root / ".local-stack/redis.conf")],
                        cwd=root / ".local-stack",
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                    )
                    stream.close()
                    processes.append(process)
                    client = Redis.from_url(
                        runtime["REDIS_URI"], decode_responses=True, socket_timeout=2
                    )
                    clients.append(client)
                    for _ in range(50):
                        try:
                            if client.ping():
                                break
                        except RedisConnectionError:
                            time.sleep(0.1)
                    client.set("same-key", entry["id"])
                    client.lpush("same-queue", entry["id"])
                self.assertEqual(
                    len(
                        {
                            entry["ports"]["LOCAL_STACK_REDIS_PORT"]
                            for _, entry in entries
                        }
                    ),
                    3,
                )
                with self.assertRaisesRegex(ValueError, "requires destroy"):
                    destroy_environment(roots[0], common, None)
                with self.assertRaisesRegex(ValueError, "Stop all"):
                    destroy_environment(roots[0], common, entries[0][1]["id"])
                processes[0].terminate()
                processes[0].wait(timeout=10)
                for index, client in enumerate(clients[1:], start=1):
                    self.assertEqual(client.get("same-key"), entries[index][1]["id"])
                    self.assertEqual(client.rpop("same-queue"), entries[index][1]["id"])
                with (
                    psycopg.connect(
                        configs(roots[1], entries[1][1])[0]["DATABASE_URI"]
                    ) as connection,
                    self.assertRaises(psycopg.errors.InsufficientPrivilege),
                ):
                    connection.execute("SELECT 1 FROM pg_authid")
                initialize(roots[0], common, repository)
                self.assertEqual(record(roots[0], common), entries[0][1])
                uri = configs(roots[0], entries[0][1])[0]["DATABASE_URI"]
                with psycopg.connect(uri) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT value FROM isolation_probe"
                        ).fetchone()[0],
                        entries[0][1]["id"],
                    )
                    with self.assertRaisesRegex(ValueError, "database connections"):
                        database_resources(roots[0], entries[0][1], destroy=True)
                first_id = entries[0][1]["id"]
                destroy_environment(roots[0], common, first_id)
                self.assertNotIn(str(roots[0]), read_registry(common)["environments"])
                self.assertFalse((roots[0] / ".local-stack").exists())
                entries.pop(0)
            finally:
                for client in clients:
                    client.close()
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=10)
                for root, entry in entries:
                    database_resources(root, entry, destroy=True)

    def test_doctor_never_terminates_port_owner(self):
        script = Path(__file__).with_name("local-stack.sh")
        result = subprocess.run(
            [
                "bash",
                "-c",
                """
source "$1" help >/dev/null
port_in_use() { return 0; }
managed_alive() { return 1; }
python3() { printf 'owned 12345'; }
stop_process() { printf 'UNEXPECTED STOP'; }
check_port platform-api 23456
""",
                "test",
                str(script),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("UNEXPECTED", result.stdout)
        self.assertIn("explicitly", result.stderr)

    def test_startup_failure_cleans_only_new_processes(self):
        script = Path(__file__).with_name("local-stack.sh")
        result = subprocess.run(
            [
                "bash",
                "-c",
                """
source "$1" help >/dev/null
STARTED_KEYS=(redis runtime-api)
stop_process() { printf 'clean %s\\n' "$1"; }
trap cleanup_startup_failure EXIT
exit 17
""",
                "test",
                str(script),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 17)
        self.assertEqual(
            result.stdout.splitlines(), ["clean runtime-api", "clean redis"]
        )


if __name__ == "__main__":
    unittest.main()
