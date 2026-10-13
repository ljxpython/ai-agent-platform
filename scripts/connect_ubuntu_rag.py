#!/usr/bin/env python3
"""Start remote Ubuntu RAG service, establish SSH tunnel, configure local stack, and restart services."""
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from dotenv import set_key

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".local-stack/evidence/knowledge-platform-documents"
REMOTE_STATE = "/home/ubuntu/.local/state/rag-anything-use/platform-6394-51d57a66"

def run_ssh(cmd: str) -> str:
    return subprocess.check_output(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "sshmy2", cmd],
        text=True
    ).strip()

def main():
    print("=== Step 1: Cleaning up old processes & states ===")
    run_ssh(f"kill $(pgrep -f '[p]ython.*remote_server.py') 2>/dev/null || true")
    run_ssh(f"rm -f '{REMOTE_STATE}/listener.json' '{REMOTE_STATE}/callback.json' '{REMOTE_STATE}/resources.json'")

    # 杀掉本地旧 tunnel 进程
    subprocess.run(["pkill", "-f", f"ssh.*{REMOTE_STATE}"], stderr=subprocess.DEVNULL)

    wire_file = EVIDENCE / "wire.json"
    if not wire_file.exists():
        raise RuntimeError(f"Missing {wire_file}")
    wire = json.loads(wire_file.read_text())
    projects = wire["projects"]

    print("=== Step 2: Uploading remote_server.py & wire.json ===")
    remote_server_src = EVIDENCE / "remote_server.py"
    subprocess.run(["scp", "-q", str(wire_file), str(remote_server_src), f"sshmy2:{REMOTE_STATE}/"], check=True)

    print("=== Step 3: Launching remote RAG server ===")
    launcher = f"""import subprocess
with open('{REMOTE_STATE}/server.log', 'ab', buffering=0) as log:
    p = subprocess.Popen(
        ['/home/ubuntu/PyCharmMiscProject/rag-anything-use/.venv/bin/python', '{REMOTE_STATE}/remote_server.py', '{REMOTE_STATE}'],
        cwd='/home/ubuntu/PyCharmMiscProject/rag-anything-use',
        stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True
    )
print(p.pid)
"""
    pid = run_ssh("python3 -c " + shlex.quote(launcher))
    print(f"Remote server launched with PID: {pid}")

    print("=== Step 4: Waiting for remote listener.json ===")
    listener = None
    for _ in range(100):
        raw = run_ssh(f"test -f '{REMOTE_STATE}/listener.json' && cat '{REMOTE_STATE}/listener.json' || true")
        if raw:
            try:
                listener = json.loads(raw)
                break
            except Exception:
                pass
        time.sleep(0.2)
    if not listener:
        run_ssh(f"tail -n 30 '{REMOTE_STATE}/server.log'")
        raise RuntimeError("remote_listener_not_started")
    print(f"Remote listening on port: {listener['port']}")

    print("=== Step 5: Allocating local port & establishing SSH tunnel ===")
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    local_port = holder.getsockname()[1]
    holder.close()

    env_json = json.loads((ROOT / ".local-stack/environment.json").read_text())
    api_port = env_json["ports"]["PLATFORM_API_PORT"]

    tunnel_log_file = EVIDENCE / "tunnel.log"
    tunnel_log = open(tunnel_log_file, "w")
    tunnel = subprocess.Popen(
        [
            "ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=15", "-R", f"0:127.0.0.1:{api_port}",
            "-L", f"127.0.0.1:{local_port}:127.0.0.1:{listener['port']}", "sshmy2"
        ],
        stdin=subprocess.DEVNULL, stdout=tunnel_log, stderr=tunnel_log, start_new_session=True
    )
    print(f"Local tunnel started (PID {tunnel.pid}), local port: {local_port} -> remote {listener['port']}")

    print("=== Step 6: Capturing reverse port from tunnel.log ===")
    callback = None
    for _ in range(100):
        if tunnel_log_file.exists():
            raw = tunnel_log_file.read_text()
            match = re.search(r"Allocated port (\d+) for remote forward", raw)
            if match:
                callback = {"port": int(match[1])}
                break
        if tunnel.poll() is not None:
            raise RuntimeError("ssh_forwarding_failed")
        time.sleep(0.1)
    if not callback:
        raise RuntimeError("ssh_reverse_port_missing")
    print(f"Reverse tunnel allocated port: {callback['port']}")

    print("=== Step 7: Sending callback.json to remote ===")
    (EVIDENCE / "callback.json").write_text(json.dumps(callback))
    subprocess.run(["scp", "-q", str(EVIDENCE / "callback.json"), f"sshmy2:{REMOTE_STATE}/"], check=True)

    print("=== Step 8: Waiting for remote resources.json ===")
    resources = None
    for _ in range(150):
        raw = run_ssh(f"test -f '{REMOTE_STATE}/resources.json' && cat '{REMOTE_STATE}/resources.json' || true")
        if raw:
            try:
                resources = json.loads(raw)
                break
            except Exception:
                pass
        time.sleep(0.2)
    if not resources:
        run_ssh(f"tail -n 30 '{REMOTE_STATE}/server.log'")
        raise RuntimeError("remote_resources_not_ready")

    resources.update(
        remote_state=REMOTE_STATE,
        local_port=local_port,
        tunnel_pid=tunnel.pid,
        projects=projects
    )
    (EVIDENCE / "resources.json").write_text(json.dumps(resources, indent=2))
    print(f"Resources ready: kbs={resources['kbs']}")

    print("=== Step 9: Updating local stack env files ===")
    base = f"http://127.0.0.1:{local_port}"
    bindings, connections, mcp = {}, {}, {}
    for name, project in projects.items():
        resource = "knowledge_" + name
        scope = {"tenant_id": "__default", "project_id": project}
        bindings["__default:" + project] = resource
        connections[resource] = {
            "base_url": base,
            "token": wire["tokens"][name],
            "scope": scope,
            "knowledge_base_id": resources["kbs"][name],
        }
        mcp[resource] = {
            "url": base + "/mcp",
            "headers": {"Authorization": "Bearer " + wire["tokens"][name]},
            "scope": scope,
            "transport": "streamable_http",
            "allowed_tools": [
                "mcp_query_project_knowledge",
                "mcp_list_project_knowledge_documents",
                "mcp_get_project_knowledge_document_status",
                "mcp_submit_project_knowledge_document",
                "mcp_get_project_knowledge_ingest_job"
            ],
        }

    for app in ("runtime", "platform"):
        path = ROOT / ".local-stack" / (app + ".env")
        settings = (
            {
                "RUNTIME_MCP_CONNECTIONS_JSON": json.dumps(mcp),
                "RUNTIME_KNOWLEDGE_UPLOAD_ENABLED": "1",
                "RUNTIME_KNOWLEDGE_SOURCES_VERSION": "2",
                "RUNTIME_KNOWLEDGE_KEY_ID": wire["key_id"],
                "RUNTIME_KNOWLEDGE_SECRET": wire["secret"],
            }
            if app == "runtime"
            else {
                "PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON": json.dumps(bindings),
                "PLATFORM_API_KNOWLEDGE_CONNECTIONS_JSON": json.dumps(connections),
                "PLATFORM_API_KNOWLEDGE_UPLOAD_ENABLED": "true",
                "PLATFORM_API_KNOWLEDGE_KEY_ID": wire["key_id"],
                "PLATFORM_API_KNOWLEDGE_SECRET": wire["secret"],
            }
        )
        for key, value in settings.items():
            set_key(path, key, value, quote_mode="always")
    print("Environment variables updated.")

    print("=== Step 10: Restarting Platform API and Runtime services ===")
    subprocess.run(["./scripts/local-stack.sh", "restart-one", "platform-api"], cwd=ROOT, check=True)
    subprocess.run(["./scripts/local-stack.sh", "restart-one", "runtime-api"], cwd=ROOT, check=True)
    subprocess.run(["./scripts/local-stack.sh", "restart-one", "runtime-worker"], cwd=ROOT, check=True)

    print("Waiting 3s for services to stabilize...")
    time.sleep(3)

    print("=== Step 11: Smoke testing knowledge capabilities ===")
    alpha_id = projects["alpha"]
    test_cmd = [
        "curl", "-s",
        f"http://127.0.0.1:{api_port}/api/projects/{alpha_id}/knowledge/capabilities",
        "-H", f"x-project-id: {alpha_id}",
    ]
    # 需要带上 token 进行鉴权
    login_cmd = [
        "curl", "-s", "-X", "POST",
        f"http://127.0.0.1:{api_port}/api/identity/session",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"username": "admin", "password": "admin123456"}),
    ]
    login_res = subprocess.check_output(login_cmd, text=True)
    token = json.loads(login_res)["tokens"]["access_token"]

    cap_res = subprocess.check_output(
        [
            "curl", "-s",
            f"http://127.0.0.1:{api_port}/api/projects/{alpha_id}/knowledge/capabilities",
            "-H", f"Authorization: Bearer {token}",
            "-H", f"x-project-id: {alpha_id}",
        ],
        text=True
    )
    print("Capabilities response:", cap_res)
    caps = json.loads(cap_res)
    assert caps.get("upload_enabled") is True, f"Expected upload_enabled True, got {caps}"
    print(" SUCCESS! Local stack and Ubuntu RAG fully connected and verified!")

if __name__ == "__main__":
    main()
