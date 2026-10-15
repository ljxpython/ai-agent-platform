import time
from types import SimpleNamespace

import pytest

from runtime_service.sandbox_node.config import NodeConfig
from runtime_service.sandbox_node.service import Node


@pytest.fixture
def node(tmp_path):
    path = tmp_path.resolve()
    (path / "workspaces").mkdir()
    (path / "state").mkdir()
    value = Node(
        NodeConfig(
            "test-node",
            path / "workspaces",
            path / "state",
            {},
            frozenset({"approved-image"}),
            min_free=0,
        )
    )
    value.ready = True
    yield value
    value.locks.close()


def test_reaper_cleans_up_idle_container(node, monkeypatch):
    import json

    # 设置 idle_timeout 为 2 秒测试
    node.engine.idle_timeout = 2.0

    # 模拟一个准备好的工作区和资源
    fake_request = SimpleNamespace(
        execution_host="local-test",
        operation_id="op-1",
        scope=["tenant", "project", "thread"],
        graph="dearflow_agent",
        workspace_id="ws-reaper-test",
        arguments={},
    )
    node.storage.prepare(fake_request, {})
    row = node.engine.reserve(fake_request, "execute", "approved-image", 30)

    # 模拟容器处于 Running 状态
    facts = {
        "Id": "container-123",
        "Image": "sha256:approved",
        "Config": {
            "Image": row["image"],
            "User": "1000:1000",
            "Labels": {
                "runtime.sandbox.node": node.config.node_id,
                "runtime.sandbox.host": row["host"],
                "runtime.sandbox.resource": row["id"],
                "runtime.sandbox.workspace": row["workspace"],
            },
        },
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "SecurityOpt": ["no-new-privileges"],
            "Tmpfs": {"/tmp": "rw,nosuid,nodev,size=16777216"},
            "Ulimits": [{"Name": "fsize", "Soft": 8388608, "Hard": 8388608}],
            "Memory": 256 * 1024**2,
            "PidsLimit": 64,
            "NanoCpus": 1_000_000_000,
            "PortBindings": {},
            "RestartPolicy": {"Name": "no"},
            "LogConfig": {
                "Type": "local",
                "Config": {"max-size": "2m", "max-file": "2"},
            },
        },
        "Mounts": [
            {
                "Destination": "/workspace",
                "Source": json.loads(row["policy"])["root"],
                "RW": False,
            },
            {
                "Destination": "/workspace/work",
                "Source": json.loads(row["policy"])["root"] + "/work",
                "RW": True,
            },
        ],
        "State": {"Running": True, "ExitCode": 0, "Status": "running"},
    }

    monkeypatch.setattr(node.engine, "inspect_facts", lambda r, f: facts["State"])
    monkeypatch.setattr(node.engine, "control", lambda *a, **kw: (0, b"{}"))

    # 此时刚 reserve，last_activity 是现在，reconcile 不会清理
    node.engine.reap_idle_sandboxes()
    db_res = node.ledger.resource(row["host"], row["id"], row["workspace"])
    assert db_res["status"] == "reserved"

    # 将活跃时间推到 3 秒前（超过 idle_timeout 2.0s）
    node.engine.last_activity[row["workspace"]] = time.time() - 3.0

    # 触发 reaper
    removed = []
    monkeypatch.setattr(
        node.engine, "remove", lambda r, stop=False: removed.append(r["name"]) or True
    )
    node.engine.reap_idle_sandboxes()

    assert len(removed) == 1
    assert removed[0] == row["name"]
    db_res = node.ledger.resource(row["host"], row["id"], row["workspace"])
    assert db_res["status"] == "removed"
