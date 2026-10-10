"""Private log storage cannot follow symlinks or exceed its byte reservation."""

from uuid import uuid4

import pytest

from runtime_service.background_tasks import output
from runtime_service.runtime.errors import RuntimeWorkspaceError


@pytest.fixture
def storage(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "log-test")
    monkeypatch.setenv("RUNTIME_BACKGROUND_LOG_ROOT", str(tmp_path))
    return tmp_path / "log-test"


def row(**changes):
    return {
        "task_id": uuid4(),
        "fence": 1,
        "log_fence": 1,
        "output_available": True,
        **changes,
    }


def test_atomic_utf8_snapshot_and_response_limit(storage):
    task = row()
    text = "测试" * 100000
    output.write_output(task, (text, 0, False))
    result = output.read_output(task)
    assert len(result.encode()) <= 65536
    assert result.startswith("测试") and result.endswith("测试")
    output.delete_output(task)
    assert output.read_output(task) is None


def test_symlink_does_not_read_or_delete_other_file(storage, tmp_path):
    task = row()
    storage.mkdir()
    directory = storage / str(task["task_id"])
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private")
    (directory / "1.log").symlink_to(outside)
    assert output.read_output(task) is None
    output.delete_output(task)
    assert outside.read_text() == "private"


def test_total_limit_and_crash_temporary_files(storage, monkeypatch):
    task = row()
    monkeypatch.setattr(output, "MAX_TOTAL_BYTES", 20)
    output.write_output(task, ("first", 0, False))
    directory = storage / str(task["task_id"])
    (directory / ".snapshot-crash").write_text("temporary")
    output.write_output({**task, "fence": 2}, ("second", 0, False))
    assert not (directory / ".snapshot-crash").exists()
    with pytest.raises(RuntimeWorkspaceError, match="log_capacity"):
        output.write_output({**task, "fence": 3}, ("x" * 20, 0, False))
    assert output.read_output(task) == "first"


def test_snapshot_larger_than_hard_limit_is_rejected(storage):
    with pytest.raises(ValueError, match="output_limit"):
        output.write_output(row(), ("x" * (output.MAX_LOG_BYTES + 1), 0, False))


def test_log_snapshot_does_not_scan_other_tasks(storage, monkeypatch):
    task = row()
    output.write_output(task, ("first", 0, False))
    listed = []
    original = output.os.listdir

    def tracked(descriptor):
        listed.append(output.os.fstat(descriptor).st_ino)
        return original(descriptor)

    monkeypatch.setattr(output.os, "listdir", tracked)
    output.write_output({**task, "fence": 2}, ("next", 0, False))
    output.delete_output({**task, "fence": 2}, stale=True)
    assert storage.stat().st_ino not in listed


def test_task_directory_symlink_cannot_escape(storage, tmp_path):
    task = row()
    storage.mkdir()
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    (outside / "1.log").write_text("private")
    (storage / str(task["task_id"])).symlink_to(outside)
    assert output.read_output(task) is None
    with pytest.raises(OSError):
        output.write_output(task, ("changed", 0, False))
    assert (outside / "1.log").read_text() == "private"
