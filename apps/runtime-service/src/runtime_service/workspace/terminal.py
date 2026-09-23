"""Process-owned interactive PTYs with bounded replay and explicit ownership."""

from __future__ import annotations

import base64
import errno
import fcntl
import hashlib
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
from pathlib import Path
from uuid import uuid4

from langchain_core.tools import ToolException

from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.execution import docker_workspace_args, runtime_backend
from runtime_service.workspace.scoped import resolve_thread_workspace

BUFFER_BYTES = 1024 * 1024
READ_BYTES = 64 * 1024
IDLE_SECONDS = 900
LIFETIME_SECONDS = 3600
RETAIN_SECONDS = 300


def terminal_enabled() -> bool:
    return os.name == "posix" and os.getenv("RUNTIME_TERMINAL_ENABLED", "1") == "1"


class TerminalSession:
    def __init__(self, identifier, owner, request_id, rows, cols):
        self.id, self.owner, self.request_id = identifier, owner, request_id
        self.created = self.last_input = time.monotonic()
        self.finished = None
        self.reason = None
        self.buffer = bytearray()
        self.offset = 0
        self.sequence = 0
        self.last_write = None
        self.lock = threading.RLock()
        self.process = None
        self.fd = None
        self.container = None
        self.rows, self.cols = rows, cols
        tenant, project, thread, graph, _ = owner
        self.root = resolve_thread_workspace(tenant, project, thread, graph)
        try:
            self.backend = runtime_backend()
        except ValueError:
            raise DocumentError("terminal_backend_invalid", 409)
        io = ImageWorkspace(self.root)
        try:
            os.close(
                io._directory(
                    ("work",) if graph == "dearflow_agent" else (), create=True
                )
            )
        except (ToolException, OSError) as exc:
            raise DocumentError("terminal_workspace_unavailable", 409) from exc
        env = {
            "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
            "HOME": str(self.root),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "TERM": "xterm-256color",
            "LANG": "C.UTF-8",
            "ENV": "/dev/null",
        }
        command = ["/bin/sh", "-i"]
        if self.backend == "docker":
            docker = shutil.which("docker")
            if not docker:
                raise DocumentError("terminal_docker_unavailable", 503)
            self.container = "runtime-terminal-" + uuid4().hex
            image = (
                os.getenv("RUNTIME_SHOWCASE_IMAGE", "python:3.13-slim")
                if graph == "showcase_demo"
                else os.getenv("RUNTIME_WORKSPACE_IMAGE", "runtime-agent-workspace:p5")
            )
            skills = None
            if graph == "dearflow_agent":
                from importlib.resources import files

                skills = Path(
                    str(
                        files("runtime_service.services.dearflow_agent").joinpath(
                            "skills"
                        )
                    )
                )
            try:
                args = docker_workspace_args(
                    self.root,
                    image=image,
                    name=self.container,
                    protected=graph == "dearflow_agent",
                    skills=skills,
                )
            except ValueError as exc:
                raise DocumentError("terminal_backend_invalid", 409) from exc
            command = [
                docker,
                "run",
                "-it",
                "--env",
                "TERM=xterm-256color",
                *args[2:],
                "timeout",
                "-s",
                "KILL",
                str(LIFETIME_SECONDS),
                "sh",
                "-i",
            ]
            # Docker CLI needs its connection configuration; no host environment enters the container.
            for key in (
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "DOCKER_CONFIG",
                "DOCKER_TLS_VERIFY",
                "DOCKER_CERT_PATH",
            ):
                if key in os.environ:
                    env[key] = os.environ[key]
            env["DOCKER_CONFIG"] = env.get(
                "DOCKER_CONFIG", str(Path.home() / ".docker")
            )
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(
                slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0)
            )
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).with_name("terminal_child.py")),
                    *command,
                ],
                cwd=self.root,
                env=env,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
                close_fds=True,
            )
            os.set_blocking(master, False)
            self.fd = master
        except (OSError, ValueError) as exc:
            os.close(master)
            raise DocumentError("terminal_start_failed", 503) from exc
        finally:
            os.close(slave)
        self.reader = threading.Thread(
            target=self._read, name="terminal-reader", daemon=True
        )
        self.reader.start()

    def describe(self):
        with self.lock:
            return {
                "terminal_id": self.id,
                "backend": self.backend,
                "isolation": "host-development"
                if self.backend == "local"
                else "docker",
                "status": "exited" if self.finished is not None else "running",
                "exit_code": self.process.poll(),
                "reason": self.reason,
                "rows": self.rows,
                "cols": self.cols,
                "next_input_sequence": self.sequence,
                "start_offset": self.offset,
                "end_offset": self.offset + len(self.buffer),
            }

    def _read(self):
        try:
            while True:
                with self.lock:
                    fd = self.fd
                if fd is None:
                    break
                try:
                    ready = select.select([fd], [], [], 0.2)[0]
                except (OSError, ValueError):
                    break
                if not ready:
                    if self.process.poll() is not None:
                        break
                    continue
                try:
                    with self.lock:
                        if self.fd != fd:
                            break
                        data = os.read(fd, 8192)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    if exc.errno in {errno.EIO, errno.EBADF}:
                        break
                    raise
                if not data:
                    if self.process.poll() is not None:
                        break
                    continue
                with self.lock:
                    self.buffer.extend(data)
                    excess = max(0, len(self.buffer) - BUFFER_BYTES)
                    if excess:
                        del self.buffer[:excess]
                        self.offset += excess
        finally:
            self.close("shell_exit")

    def read(self, offset):
        with self.lock:
            end = self.offset + len(self.buffer)
            if offset > end:
                raise DocumentError("terminal_offset_ahead", 409)
            start = max(offset, self.offset)
            data = bytes(
                self.buffer[start - self.offset : start - self.offset + READ_BYTES]
            )
            return {
                **self.describe(),
                "data_base64": base64.b64encode(data).decode(),
                "offset": start,
                "next_offset": start + len(data),
                "truncated": offset < self.offset,
            }

    def write(self, data, sequence):
        digest = hashlib.sha256(data).hexdigest()
        with self.lock:
            if self.last_write and sequence == self.sequence - 1:
                if self.last_write[0] != digest:
                    raise DocumentError("terminal_input_conflict", 409)
                return self.last_write[1]
            if sequence != self.sequence:
                raise DocumentError("terminal_input_sequence", 409)
            if (
                self.fd is None
                or self.finished is not None
                or self.process.poll() is not None
            ):
                raise DocumentError("terminal_exited", 409)
            try:
                accepted = os.write(self.fd, data)
            except BlockingIOError:
                raise DocumentError("terminal_input_busy", 429) from None
            except OSError:
                raise DocumentError("terminal_exited", 409) from None
            self.sequence += 1
            self.last_input = time.monotonic()
            result = {"accepted_bytes": accepted, "next_input_sequence": self.sequence}
            self.last_write = (digest, result)
            return result

    def resize(self, rows, cols):
        with self.lock:
            if self.fd is None or self.finished is not None:
                raise DocumentError("terminal_exited", 409)
            try:
                fcntl.ioctl(
                    self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0)
                )
            except OSError:
                raise DocumentError("terminal_exited", 409) from None
            if self.container:
                try:
                    result = subprocess.run(
                        [
                            shutil.which("docker") or "docker",
                            "exec",
                            self.container,
                            "stty",
                            "-F",
                            "/proc/1/fd/0",
                            "rows",
                            str(rows),
                            "cols",
                            str(cols),
                        ],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    raise DocumentError("terminal_resize_failed", 503) from None
                if result.returncode:
                    raise DocumentError("terminal_resize_failed", 503)
            self.rows, self.cols = rows, cols
            return self.describe()

    def close(self, reason="closed"):
        with self.lock:
            if self.finished is not None:
                return self.describe()
            self.finished, self.reason = time.monotonic(), reason
            fd, self.fd = self.fd, None
            # Job-control shells give foreground jobs a separate process group.
            if fd is not None:
                try:
                    foreground = os.tcgetpgrp(fd)
                    if foreground > 0 and foreground != os.getpgrp():
                        os.killpg(foreground, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except OSError:
                pass
            if self.process.poll() is None:
                self.process.kill()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            if self.container:
                try:
                    result = subprocess.run(
                        [
                            shutil.which("docker") or "docker",
                            "rm",
                            "-f",
                            self.container,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        check=False,
                    )
                    if result.returncode:
                        raise OSError("docker cleanup failed")
                except (OSError, subprocess.TimeoutExpired):
                    # Container timeout remains the hard upper bound if Docker is unreachable.
                    import logging

                    logging.getLogger(__name__).warning(
                        "terminal container cleanup unavailable: %s", self.container
                    )
            return self.describe()


class TerminalManager:
    """Single-process ownership; sticky routing is required for multiple Runtime workers."""

    def __init__(self):
        self.instance = uuid4().hex
        self.sessions = {}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.janitor = None

    def create(self, owner, request_id, rows, cols):
        if not terminal_enabled():
            raise DocumentError("terminal_disabled", 409)
        with self.lock:
            for session in self.sessions.values():
                if session.owner == owner and session.request_id == request_id:
                    return session.describe()
            active = [s for s in self.sessions.values() if s.finished is None]
            if (
                len(self.sessions) >= 128
                or len(active) >= 32
                or sum(s.owner == owner for s in active) >= 4
            ):
                raise DocumentError("terminal_session_limit", 429)
            identifier = self.instance + "." + uuid4().hex
            session = TerminalSession(identifier, owner, request_id, rows, cols)
            self.sessions[identifier] = session
            if self.janitor is None:
                self.stop.clear()
                self.janitor = threading.Thread(
                    target=self._reap, name="terminal-cleanup", daemon=True
                )
                self.janitor.start()
            return session.describe()

    def get(self, owner, identifier):
        with self.lock:
            if not identifier.startswith(self.instance + "."):
                raise DocumentError("terminal_instance_changed", 409)
            session = self.sessions.get(identifier)
            if session is None or session.owner != owner:
                raise DocumentError("terminal_not_found", 404)
            return session

    def list(self, owner):
        with self.lock:
            return {
                "items": [
                    s.describe() for s in self.sessions.values() if s.owner == owner
                ],
                "instance_id": self.instance,
            }

    def sweep(self):
        now = time.monotonic()
        with self.lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            if session.finished is None:
                if not terminal_enabled():
                    session.close("disabled")
                elif now - session.created >= LIFETIME_SECONDS:
                    session.close("lifetime_expired")
                elif now - session.last_input >= IDLE_SECONDS:
                    session.close("idle_expired")
            elif now - session.finished >= RETAIN_SECONDS:
                with self.lock:
                    self.sessions.pop(session.id, None)

    def _reap(self):
        while not self.stop.wait(5):
            self.sweep()

    def shutdown(self):
        self.stop.set()
        with self.lock:
            sessions = list(self.sessions.values())
        for session in sessions:
            session.close("runtime_shutdown")
        if self.janitor:
            self.janitor.join(timeout=15)
        with self.lock:
            self.sessions.clear()
            self.janitor = None
            self.instance = uuid4().hex


terminals = TerminalManager()
