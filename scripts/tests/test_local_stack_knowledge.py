import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import local_stack_processes as processes
import local_stack_worktree as stack


class KnowledgeRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name).resolve()
        self.root = base / "worktree"
        self.common = base / "common"
        self.source = base / "knowledge-source"
        self.state = self.root / ".local-stack/knowledge"
        self.state.mkdir(parents=True)
        for relative in ("src/mcp_server.py", ".venv/bin/python"):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        self.entry = {
            "id": "wt_123456abcdef",
            "root": str(self.root),
            "ports": dict(zip(stack.PORT_KEYS, range(23100, 23104))),
            "databases": {k: f"wt_123456abcdef_{k}" for k in ("platform", "runtime")},
        }
        stack.write_json(self.root / ".local-stack/environment.json", self.entry)
        self.registry = self.common / "local-stacks/registry.json"
        self.registry.parent.mkdir(parents=True)
        stack.write_json(
            self.registry, {"version": 1, "environments": {str(self.root): self.entry}}
        )
        stack.write_json(
            self.state / "mcp-process.json",
            {
                "environment": self.entry["id"],
                "root": str(self.source),
                "port": 63311,
                "env_file": str(self.state / "knowledge.env"),
            },
        )
        stack.write_json(
            self.state / "ollama-process.json",
            {"port": 65417, "models": str(self.state / "ollama-models")},
        )
        (self.state / "knowledge.env").write_text(
            f"MCP_HOST=127.0.0.1\nMCP_PORT=63311\nEMBEDDING_BASE_URL=http://127.0.0.1:65417\nKNOWLEDGE_ROOT_DIR={self.state / 'corpus'}\n"
        )

    def test_register_is_idempotent_and_preserves_environment(self):
        with (
            patch.object(processes, "snapshot", return_value={}),
            patch.object(processes, "port_pids", return_value=set()),
        ):
            stack.register_knowledge(self.root, self.common)
            stack.register_knowledge(self.root, self.common)
        actual = stack.record(self.root, self.common)
        self.assertEqual(actual["ports"], self.entry["ports"])
        self.assertEqual(
            actual["knowledge"]["ports"], {"mcp": 63311, "embedding": 65417}
        )

    def test_conflicting_registered_port_is_rejected(self):
        registry = json.loads(self.registry.read_text())
        registry["environments"]["another-root"] = {"ports": {"api": 63311}}
        stack.write_json(self.registry, registry)
        with (
            patch.object(processes, "snapshot", return_value={}),
            patch.object(processes, "port_pids", return_value=set()),
            self.assertRaisesRegex(ValueError, "conflict"),
        ):
            stack.register_knowledge(self.root, self.common)
        self.assertNotIn("knowledge", stack.record(self.root, self.common))

    def test_external_listener_is_rejected_without_signals(self):
        with (
            patch.object(
                processes, "snapshot", return_value={55: (1, ["foreign-server"])}
            ),
            patch.object(processes, "port_pids", return_value={55}),
            patch.object(processes, "cwd", return_value=Path("/foreign")),
            self.assertRaisesRegex(ValueError, "external"),
        ):
            stack.register_knowledge(self.root, self.common)
        self.assertNotIn("knowledge", stack.record(self.root, self.common))

    def test_ownership_does_not_select_other_embedding_listener(self):
        with (
            patch.object(processes, "snapshot", return_value={}),
            patch.object(processes, "port_pids", return_value=set()),
        ):
            stack.register_knowledge(self.root, self.common)
        with (
            patch.object(
                processes,
                "snapshot",
                return_value={
                    11: (1, ["ollama", "serve"]),
                    22: (1, ["ollama", "serve"]),
                    33: (1, ["foreign-server"]),
                },
            ),
            patch.object(processes, "port_pids", return_value={11}),
            patch.object(processes, "cwd", return_value=self.root),
        ):
            self.assertEqual(
                set(processes.owned(self.root, "knowledge-embedding", 65417)), {11}
            )

    def test_knowledge_callback_uses_only_own_registered_api(self):
        entry = {"ports": dict(zip(stack.PORT_KEYS, range(23100, 23104)))}
        runtime, _ = stack.expected_values(self.root, entry)
        expected = f"http://127.0.0.1:{entry['ports']['PLATFORM_API_PORT']}/api/runtime/internal/knowledge/authorize"
        self.assertEqual(runtime["PLATFORM_KNOWLEDGE_AUTHORIZATION_URL"], expected)


if __name__ == "__main__":
    unittest.main()
