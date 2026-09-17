"""Exercise local-stack configuration and process environment without starting services."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class LocalStackBackendTest(unittest.TestCase):
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
                    f"RUNTIME_SHOWCASE_BACKEND={configured}\n" if configured else ""
                )
                env = {**os.environ, "TMPDIR": directory}
                env.pop("RUNTIME_SHOWCASE_BACKEND", None)
                if override is not None:
                    env["RUNTIME_SHOWCASE_BACKEND"] = override
                result = subprocess.run([
                    "bash", "-c", '''
source "$1" help >/dev/null
RUNTIME_ENV_FILE="$2/.env"
PLATFORM_API_DIR="$2"
python3() { printf 'test-secret'; }
load_runtime_env
start_process() { bash -c 'printf "mode=%s\\n" "$RUNTIME_SHOWCASE_BACKEND"'; }
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
