"""Exercise local-stack configuration and process environment without starting services."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class LocalStackBackendTest(unittest.TestCase):
    def test_runtime_restart_preflight_runs_before_stop(self):
        script = Path(__file__).with_name("local-stack.sh").resolve()
        for key in ("runtime-api", "runtime-worker"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                result = subprocess.run([
                    "bash", "-c", '''
source "$1" help >/dev/null
load_runtime_env() { :; }
validate_runtime() { printf 'CONFIG_ERROR audience missing\\n'; return 17; }
stop_process() { printf 'UNEXPECTED STOP\\n'; }
start_managed_key() { printf 'UNEXPECTED START\\n'; }
restart_one "$2"
''', "test", str(script), key,
                ], env={**os.environ, "TMPDIR": directory}, capture_output=True, text=True, timeout=10, check=False)
                self.assertEqual(result.returncode, 17, result.stderr)
                self.assertIn("CONFIG_ERROR", result.stdout)
                self.assertNotIn("UNEXPECTED", result.stdout)

    def test_failed_platform_migration_blocks_start(self):
        script = Path(__file__).with_name("local-stack.sh").resolve()
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                "bash", "-c", """
source "$1" help >/dev/null
PLATFORM_API_DIR="$2"
RUNTIME_DIR="$2"
validate_stack() { :; }
validate_runtime() { :; }
check_postgres() { :; }
uv() { printf '%s\n' "$*"; return 17; }
start_managed_key() { printf 'UNEXPECTED START\n'; }
start
""", "test", str(script), directory,
            ], env={**os.environ, "TMPDIR": directory}, capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 17, result.stderr)
            self.assertIn("scripts/database.py upgrade", result.stdout)
            self.assertNotIn("UNEXPECTED START", result.stdout)
            self.assertNotIn("graphharbor migrate", result.stdout)

    def test_cleanup_preview_preserves_database_and_backups(self):
        script = Path(__file__).with_name("cleanup_env.sh").resolve()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            local_script = root / "scripts/cleanup_env.sh"
            local_script.write_text(script.read_text())
            data = root / "apps/platform-api/.data/backups"
            data.mkdir(parents=True)
            protected = [data / "recovery.db", data.parent / "platform-api.db"]
            for path in protected:
                path.write_bytes(b"must remain unchanged")
            result = subprocess.run(["bash", str(local_script), "--dry-run"], capture_output=True, text=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            for path in protected:
                self.assertEqual(path.read_bytes(), b"must remain unchanged")
            self.assertNotIn("DROP DATABASE", local_script.read_text())
            self.assertNotIn("CASCADE", local_script.read_text())

    def test_terminal_switch(self):
        script = Path(__file__).with_name("local-stack.sh").resolve()
        for override, configured, expected in (
            (None, None, "1"), (None, "0", "0"), ("0", "1", "0"),
            ("1", "0", "1"), ("invalid", None, None),
        ):
            with self.subTest(override=override, configured=configured), tempfile.TemporaryDirectory() as directory:
                env_file = Path(directory) / ".env"
                env_file.write_text(f"RUNTIME_TERMINAL_ENABLED={configured}\n" if configured else "")
                env = {**os.environ, "TMPDIR": directory}
                env.pop("RUNTIME_TERMINAL_ENABLED", None)
                if override is not None:
                    env["RUNTIME_TERMINAL_ENABLED"] = override
                result = subprocess.run([
                    "bash", "-c", '''
source "$1" help >/dev/null
RUNTIME_ENV_FILE="$2/.env"
PLATFORM_API_DIR="$2"
python3() { printf 'test-secret'; }
load_runtime_env
start_process() { bash -c 'printf "terminal=%s\\n" "$RUNTIME_TERMINAL_ENABLED"'; }
start_managed_key runtime-api
start_managed_key runtime-worker
''', "test", str(script), directory,
                ], env=env, capture_output=True, text=True, timeout=10, check=False)
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("must be 0 or 1", result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.count(f"terminal={expected}\n"), 2)

    def test_selection_and_runtime_environment(self):
        script = Path(__file__).with_name("local-stack.sh").resolve()
        for override, configured, expected in (
            (None, None, "local"), (None, "docker", "docker"),
            ("docker", "local", "docker"), ("local", "docker", "local"),
            ("invalid", None, None),
        ):
            with self.subTest(override=override, configured=configured), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                env_file = root / ".env"
                env_file.write_text(
                    f"RUNTIME_BACKEND={configured}\n" if configured else ""
                )
                env = {**os.environ, "TMPDIR": directory}
                env.pop("RUNTIME_BACKEND", None)
                if override is not None:
                    env["RUNTIME_BACKEND"] = override
                result = subprocess.run([
                    "bash", "-c", '''
source "$1" help >/dev/null
RUNTIME_ENV_FILE="$2/.env"
PLATFORM_API_DIR="$2"
python3() { printf 'test-secret'; }
load_runtime_env
start_process() { bash -c 'printf "mode=%s\\n" "$RUNTIME_BACKEND"'; }
start_managed_key runtime-api
start_managed_key runtime-worker
''', "test", str(script), directory,
                ], env=env, capture_output=True, text=True, timeout=10, check=False)
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("must be local or docker", result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.count(f"mode={expected}\n"), 2)


if __name__ == "__main__":
    unittest.main()
