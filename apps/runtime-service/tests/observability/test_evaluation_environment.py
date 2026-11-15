import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from runtime_service.observability.evaluation_environment import snapshot_inputs
from runtime_service.workspace.attachment_receipts import AttachmentReceipts
from runtime_service.workspace.documents import DocumentWorkspace


def capture():
    return {
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "data_class": "synthetic",
    }


@pytest.mark.parametrize("data_class", ["synthetic", "business"])
def test_only_receipted_original_uploads_are_copied(tmp_path, data_class):
    workspace = tmp_path / "workspace"
    data = b"order_id,amount\nS1,100\n"
    ref = DocumentWorkspace(workspace).put(
        data, hashlib.sha256(data).hexdigest(), "text/csv", "sales.csv"
    )
    AttachmentReceipts(workspace).record(ref)
    (workspace / "work").mkdir()
    (workspace / "work" / "report.md").write_text(
        "generated output must not become input"
    )
    result = snapshot_inputs(workspace, {**capture(), "data_class": data_class})
    assert result["initial_files"] == {ref["path"]: data.decode()}
    assert result["attachments"] == [ref]
    assert result["memory"] == "not_copied"
    assert result["missing"] == []


def test_mutated_upload_and_symlink_are_not_copied(tmp_path):
    workspace = tmp_path / "workspace"
    data = b"original"
    ref = DocumentWorkspace(workspace).put(
        data, hashlib.sha256(data).hexdigest(), "text/plain", "input.txt"
    )
    AttachmentReceipts(workspace).record(ref)
    path = workspace / ref["path"].removeprefix("/workspace/")
    path.write_text("changed by agent")
    assert snapshot_inputs(workspace, capture())["initial_files"] == {}
    path.unlink()
    outside = tmp_path / "private.txt"
    outside.write_bytes(data)
    path.symlink_to(outside)
    value = snapshot_inputs(workspace, capture())
    assert value["initial_files"] == {} and value["missing"]


@pytest.mark.parametrize("data_class", ["synthetic", "business"])
def test_expired_or_unknown_class_capture_reads_nothing(tmp_path, data_class):
    assert snapshot_inputs(tmp_path, {**capture(), "data_class": "production"}) is None
    assert (
        snapshot_inputs(
            tmp_path,
            {
                **capture(),
                "data_class": data_class,
                "expires_at": "2000-01-01T00:00:00+00:00",
            },
        )
        is None
    )
