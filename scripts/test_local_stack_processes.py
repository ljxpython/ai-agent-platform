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

    def test_port_owner_and_cleanup_real_process(self):
        from local_stack_processes import check_port_owner, default_port
        import socket

        # Find an open port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            test_port = s.getsockname()[1]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "apps/platform-api"
            external = root / "other/external-api"
            app.mkdir(parents=True)
            external.mkdir(parents=True)

            status, _ = check_port_owner(root, "platform-api", test_port)
            self.assertEqual(status, "free")

            # Launch a process binding test_port from app directory
            server_script = (
                "import socket, time\n"
                "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                f"s.bind(('127.0.0.1', {test_port}))\n"
                "s.listen(1)\n"
                "time.sleep(30)\n"
            )
            p_app = subprocess.Popen(
                [sys.executable, "-c", server_script],
                cwd=app,
            )
            try:
                time.sleep(0.3)
                status, detail = check_port_owner(root, "platform-api", test_port)
                self.assertEqual(status, "owned")
                self.assertEqual(detail, str(p_app.pid))

                # Now test stop kills it and frees the port
                stop(root, "platform-api", test_port)
                self.assertIsNotNone(p_app.poll())
                status, _ = check_port_owner(root, "platform-api", test_port)
                self.assertEqual(status, "free")
            finally:
                if p_app.poll() is None:
                    p_app.kill()
                    p_app.wait()

            # Now launch a process from external directory binding test_port
            p_ext = subprocess.Popen(
                [sys.executable, "-c", server_script],
                cwd=external,
            )
            try:
                time.sleep(0.3)
                status, detail = check_port_owner(root, "platform-api", test_port)
                self.assertEqual(status, "external")
                self.assertIn(str(p_ext.pid), detail)

                # Stop platform-api should NOT kill external process
                stop(root, "platform-api", test_port)
                self.assertIsNone(p_ext.poll())
            finally:
                if p_ext.poll() is None:
                    p_ext.kill()
                    p_ext.wait()


if __name__ == "__main__":
    unittest.main()
