"""Stop local stack processes by executable and exact app directory, never by port alone."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path


def snapshot() -> dict[int, tuple[int, list[str]]]:
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid=,command="], text=True)
    rows = {}
    for line in output.splitlines():
        try:
            pid, parent, command = line.strip().split(None, 2)
            rows[int(pid)] = (int(parent), shlex.split(command))
        except ValueError:
            continue
    return rows


def cwd(pid: int) -> Path | None:
    proc = Path(f"/proc/{pid}/cwd")
    if proc.exists():
        return proc.resolve()
    result = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        capture_output=True,
        text=True,
        check=False,
    )
    return next(
        (
            Path(line[1:]).resolve()
            for line in result.stdout.splitlines()
            if line.startswith("n")
        ),
        None,
    )


def matches(key: str, args: list[str]) -> bool:
    names = [Path(arg).name for arg in args]
    if key == "platform-web":
        return any(name in {"vite", "vite.js"} for name in names) or (
            any(name in {"pnpm", "pnpm.cjs", "npm", "npm-cli.js"} for name in names)
            and "dev" in args
        )
    if key == "platform-api":
        return "uvicorn" in names and "platform_api.main:create_app" in args
    mode = "worker" if key == "runtime-worker" else "serve"
    return (
        "graphharbor" in names or ("-m" in args and "langhost.cli" in args)
    ) and mode in args


def owned(root: Path, key: str) -> dict[int, tuple[int, list[str]]]:
    app = "runtime-service" if key.startswith("runtime-") else key
    directory = (root / "apps" / app).resolve()
    rows = snapshot()
    selected = {
        pid
        for pid, (_, args) in rows.items()
        if matches(key, args) and cwd(pid) == directory
    }
    # Include reload/worker children, but never their shell/terminal ancestors.
    while True:
        children = {
            pid
            for pid, (parent, _) in rows.items()
            if parent in selected and cwd(pid) == directory
        }
        added = children - selected
        if not added:
            break
        selected |= added
    return {pid: rows[pid] for pid in selected if pid != os.getpid()}


def stop(root: Path, key: str) -> None:
    targets = owned(root, key)
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[stop] {key} pid={pid}", flush=True)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while targets and time.monotonic() < deadline:
        current = snapshot()
        targets = {
            pid: identity
            for pid, identity in targets.items()
            if current.get(pid, (None, []))[1] == identity[1]
        }
        if targets:
            time.sleep(0.1)
    for pid, identity in targets.items():
        if (
            snapshot().get(pid, (None, []))[1] == identity[1]
            and cwd(pid)
            == (
                root
                / "apps"
                / ("runtime-service" if key.startswith("runtime-") else key)
            ).resolve()
        ):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    root, key = Path(sys.argv[1]), sys.argv[2]
    if len(sys.argv) > 3:
        raise SystemExit(0 if int(sys.argv[3]) in owned(root, key) else 1)
    stop(root, key)
