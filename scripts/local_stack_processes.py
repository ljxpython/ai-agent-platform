"""Stop local stack processes by executable, listening port, and exact app directory, never killing unrelated processes."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path


def snapshot() -> dict[int, tuple[int, list[str]]]:
    output = subprocess.check_output(
        ["ps", "-ax", "-o", "pid=,ppid=,command=", "-w", "-w"], text=True
    )
    rows: dict[int, tuple[int, list[str]]] = {}
    for line in output.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            parent = int(parts[1])
            command = parts[2]
            try:
                args = shlex.split(command)
            except ValueError:
                args = command.split()
            rows[pid] = (parent, args)
        except (ValueError, IndexError):
            continue
    return rows


_cwd_cache: dict[int, Path | None] = {}


def cwd(pid: int) -> Path | None:
    if pid in _cwd_cache:
        return _cwd_cache[pid]
    proc = Path(f"/proc/{pid}/cwd")
    if proc.exists():
        try:
            res = proc.resolve()
            _cwd_cache[pid] = res
            return res
        except Exception:
            pass
    result = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        capture_output=True,
        text=True,
        check=False,
    )
    res = None
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            try:
                res = Path(line[1:]).resolve()
                break
            except Exception:
                pass
    _cwd_cache[pid] = res
    return res


def port_pids(port: int | None) -> set[int]:
    if not port:
        return set()
    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.add(int(line))
    return pids


def default_port(key: str) -> int | None:
    if key == "platform-api":
        val = os.environ.get("PLATFORM_API_PORT")
        return int(val) if val and val.isdigit() else 2142
    if key == "platform-web":
        val = os.environ.get("PLATFORM_WEB_PORT")
        return int(val) if val and val.isdigit() else 3000
    if key == "runtime-api":
        val = os.environ.get("RUNTIME_PORT") or os.environ.get("RUNTIME_SERVICE_PORT")
        return int(val) if val and val.isdigit() else 8123
    return None


def is_within(path: Path | None, parent: Path) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, RuntimeError):
        return False


def matches(key: str, args: list[str]) -> bool:
    names = [Path(arg).name for arg in args]
    if key == "platform-web":
        return any(name in {"vite", "vite.js"} for name in names) or (
            any(name in {"pnpm", "pnpm.cjs", "npm", "npm-cli.js"} for name in names)
            and "dev" in args
        )
    if key == "platform-api":
        return (
            ("uvicorn" in names and any("platform_api" in arg for arg in args))
            or ("platform_api.main:create_app" in args)
            or ("platform_api.main" in args)
        )
    mode = "worker" if key == "runtime-worker" else "serve"
    return (
        "graphharbor" in names or ("-m" in args and "langhost.cli" in args)
    ) and mode in args


def owned(
    root: Path, key: str, port: int | None = None
) -> dict[int, tuple[int, list[str]]]:
    app = "runtime-service" if key.startswith("runtime-") else key
    directory = (root / "apps" / app).resolve()
    dir_str = str(directory)
    target_port = port if port is not None else default_port(key)

    rows = snapshot()
    selected: set[int] = set()

    # 1. 快速短路扫描：只有符合命令行特征或引用了本工程目录的进程，才进行 cwd 检查
    for pid, (_, args) in rows.items():
        if not args:
            continue
        is_candidate = matches(key, args) or any(dir_str in a for a in args)
        if is_candidate:
            proc_cwd = cwd(pid)
            if proc_cwd == directory or is_within(proc_cwd, directory):
                selected.add(pid)

    # 2. 扫描对应监听端口的真实进程（通常只有 0 或 1 个 PID，代价极低）
    if target_port:
        for pid in port_pids(target_port):
            if pid in rows and pid not in selected:
                args = rows[pid][1]
                exe = Path(args[0]) if args else None
                proc_cwd = cwd(pid)
                if (
                    proc_cwd == directory
                    or is_within(proc_cwd, directory)
                    or is_within(exe, directory)
                    or any(dir_str in a for a in args)
                ):
                    selected.add(pid)

    # 3. 递归寻找子进程
    while True:
        children = {
            pid
            for pid, (parent, _) in rows.items()
            if parent in selected
            and (
                matches(key, rows[pid][1])
                or cwd(pid) == directory
                or is_within(cwd(pid), directory)
            )
        }
        added = children - selected
        if not added:
            break
        selected |= added

    # 4. 寻找直接父进程（例如 reload 主进程），前提是父进程也在该 app 目录下
    for pid in list(selected):
        parent_pid = rows.get(pid, (0, []))[0]
        if parent_pid > 1 and parent_pid in rows and parent_pid not in selected:
            p_args = rows[parent_pid][1]
            if matches(key, p_args) or any(dir_str in a for a in p_args):
                p_cwd = cwd(parent_pid)
                if p_cwd == directory or is_within(p_cwd, directory):
                    selected.add(parent_pid)

    return {pid: rows[pid] for pid in selected if pid != os.getpid()}


def stop(root: Path, key: str, port: int | None = None) -> None:
    target_port = port if port is not None else default_port(key)
    targets = owned(root, key, target_port)
    if not targets:
        return

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

    app = "runtime-service" if key.startswith("runtime-") else key
    directory = (root / "apps" / app).resolve()
    for pid, identity in targets.items():
        curr = snapshot()
        if (
            curr.get(pid, (None, []))[1] == identity[1]
            and (cwd(pid) == directory or is_within(cwd(pid), directory))
        ):
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[kill] {key} pid={pid}", flush=True)
            except ProcessLookupError:
                pass

    # 若指定了端口，再确保端口监听彻底释放
    if target_port:
        port_deadline = time.monotonic() + 2
        while time.monotonic() < port_deadline:
            pids = port_pids(target_port)
            if not pids:
                break
            for p in pids:
                if p in targets or cwd(p) == directory or is_within(cwd(p), directory):
                    try:
                        os.kill(p, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            time.sleep(0.1)


def check_port_owner(root: Path, key: str, port: int) -> tuple[str, str]:
    pids = port_pids(port)
    if not pids:
        return ("free", "")
    owned_procs = owned(root, key, port)
    for p in pids:
        if p in owned_procs:
            return ("owned", str(p))
    rows = snapshot()
    first_pid = next(iter(pids))
    cmd = " ".join(rows.get(first_pid, (0, ["<unknown>"]))[1])
    return ("external", f"{first_pid} {cmd}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("Usage: local_stack_processes.py <action|root> ...")

    first_arg = sys.argv[1]
    if first_arg in {"stop", "check", "find", "port-owner"}:
        action = first_arg
        root = Path(sys.argv[2])
        key = sys.argv[3]
        if action == "stop":
            port = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else None
            stop(root, key, port)
        elif action == "check":
            if len(sys.argv) <= 4:
                raise SystemExit("Missing pid for check")
            pid = int(sys.argv[4])
            port = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].isdigit() else None
            sys.exit(0 if pid in owned(root, key, port) else 1)
        elif action == "find":
            port = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else None
            pids = list(owned(root, key, port).keys())
            print(" ".join(str(p) for p in pids))
        elif action == "port-owner":
            if len(sys.argv) <= 4:
                raise SystemExit("Missing port for port-owner")
            port = int(sys.argv[4])
            status, detail = check_port_owner(root, key, port)
            print(f"{status} {detail}".strip())
    else:
        # Backward-compatible invocation:
        # local_stack_processes.py <root> <key> [pid]
        root = Path(sys.argv[1])
        key = sys.argv[2]
        if len(sys.argv) > 3 and sys.argv[3].isdigit():
            sys.exit(0 if int(sys.argv[3]) in owned(root, key) else 1)
        stop(root, key)
