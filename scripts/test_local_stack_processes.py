"""Real-process regression: stop untracked servers, preserve other repositories."""

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from local_stack_processes import owned, stop


class LocalStackProcessesTest(unittest.TestCase):
    def test_untracked_server_and_stubborn_child_but_not_other_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "apps/platform-web"
            other = root / "other/apps/platform-web"
            app.mkdir(parents=True)
            other.mkdir(parents=True)
            script = root / "vite"
            script.write_text(
                "import subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', "
                "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])\n"
                "print(child.pid, flush=True)\n"
                "time.sleep(60)\n"
            )
            processes = []
            try:
                for directory in (app, other):
                    processes.append(
                        subprocess.Popen(
                            [sys.executable, str(script)],
                            cwd=directory,
                            stdout=subprocess.PIPE,
                            text=True,
                        )
                    )
                children = [int(process.stdout.readline()) for process in processes]
                time.sleep(0.1)
                self.assertIn(processes[0].pid, owned(root, "platform-web"))
                self.assertNotIn(processes[1].pid, owned(root, "platform-web"))
                stop(root, "platform-web")
                self.assertIsNotNone(processes[0].poll())
                self.assertIsNone(processes[1].poll())
                self.assertEqual(owned(root, "platform-web"), {})
                remaining = (
                    subprocess.check_output(
                        ["ps", "-p", str(children[0]), "-o", "stat="], text=True
                    )
                    if subprocess.run(
                        ["kill", "-0", str(children[0])],
                        capture_output=True,
                        check=False,
                    ).returncode
                    == 0
                    else ""
                )
                self.assertTrue(
                    not remaining.strip() or remaining.strip().startswith("Z")
                )
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    process.stdout.close()
                for child in locals().get("children", []):
                    subprocess.run(
                        ["kill", "-9", str(child)], capture_output=True, check=False
                    )


if __name__ == "__main__":
    unittest.main()
