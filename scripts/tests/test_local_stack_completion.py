import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import local_stack_worktree as stack


class CompletionIsolationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.entry = {
            "id": "wt_retentiontest",
            "ports": dict(zip(stack.PORT_KEYS, range(23100, 23104))),
            "databases": {
                key: f"wt_retentiontest_{key}" for key in ("platform", "runtime")
            },
        }
        state = self.root / ".local-stack"
        state.mkdir()
        self.runtime, self.platform = stack.expected_values(self.root, self.entry)
        self.runtime.update(
            DATABASE_URI="postgresql://wt_retentiontest_runtime:password@127.0.0.1/wt_retentiontest_runtime",
            REDIS_URI=f"redis://:password@127.0.0.1:{self.entry['ports']['LOCAL_STACK_REDIS_PORT']}/0",
            PLATFORM_RUNTIME_DELEGATION_SECRET="d" * 32,
        )
        self.platform.update(
            PLATFORM_API_DATABASE_URL="postgresql://wt_retentiontest_platform:password@127.0.0.1/wt_retentiontest_platform",
            PLATFORM_API_RUNTIME_DELEGATION_SECRET="d" * 32,
        )
        (state / "redis.conf").write_text(
            f'bind 127.0.0.1\nprotected-mode yes\ndaemonize no\nport {self.entry["ports"]["LOCAL_STACK_REDIS_PORT"]}\ndir "{state / "redis"}"\nrequirepass password\nappendonly yes\n'
        )

    def save(self):
        stack.write_env(self.root / ".local-stack/runtime.env", self.runtime)
        stack.write_env(self.root / ".local-stack/platform.env", self.platform)

    def test_missing_pair_is_generated_once_for_own_environment(self):
        self.save()
        runtime, platform = stack.configs(self.root, self.entry)
        secret = runtime["GRAPHHARBOR_TERMINAL_WEBHOOK_SECRET"]
        self.assertGreaterEqual(len(secret), 32)
        self.assertEqual(platform["PLATFORM_API_RUNTIME_COMPLETION_SECRET"], secret)
        self.assertEqual(
            runtime["GRAPHHARBOR_TERMINAL_WEBHOOK_KEY_ID"], self.entry["id"]
        )
        self.assertEqual(
            runtime["GRAPHHARBOR_TERMINAL_WEBHOOK_URL"],
            "http://127.0.0.1:23101/api/runtime/internal/run-completion",
        )
        self.assertEqual(
            stack.configs(self.root, self.entry)[0][
                "GRAPHHARBOR_TERMINAL_WEBHOOK_SECRET"
            ],
            secret,
        )

    def test_foreign_callback_and_mismatched_keys_fail_closed(self):
        stack.configure_completion(self.runtime, self.platform, self.entry)
        for key in ("GRAPHHARBOR_TERMINAL_WEBHOOK_URL",):
            with self.subTest(key=key):
                original = self.runtime[key]
                self.runtime[key] = "http://127.0.0.1:8123/foreign"
                self.save()
                with self.assertRaises(ValueError):
                    stack.configs(self.root, self.entry)
                self.runtime[key] = original
        self.platform["PLATFORM_API_RUNTIME_COMPLETION_SECRET"] = "other" * 10
        self.save()
        with self.assertRaisesRegex(ValueError, "signing keys"):
            stack.configs(self.root, self.entry)


if __name__ == "__main__":
    unittest.main()
