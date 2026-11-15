import errno
import os

import pytest

from runtime_service.workspace.browser import WorkspaceBrowser
from runtime_service.workspace.documents import DocumentError


@pytest.mark.parametrize(
    "path",
    [
        "/workspace/missing.json",
        "/workspace/missing/child.txt",
        "/workspace/outputs/new.json",
    ],
)
def test_browser_reports_only_confirmed_missing_file(tmp_path, path):
    with pytest.raises(DocumentError) as error:
        WorkspaceBrowser(tmp_path).read_file(path)
    assert error.value.code == "file_not_found"


@pytest.mark.parametrize(
    "path",
    ["/workspace/link", "/workspace/link/child.txt", "/workspace/outputs/link.json"],
)
def test_browser_does_not_call_symlink_missing(tmp_path, path):
    (tmp_path / "outputs").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "absent")
    (tmp_path / "outputs/link.json").symlink_to(tmp_path / "absent")
    with pytest.raises(DocumentError) as error:
        WorkspaceBrowser(tmp_path).read_file(path)
    assert error.value.code != "file_not_found"


@pytest.mark.parametrize("number", [errno.EACCES, errno.EIO])
def test_browser_storage_failure_is_not_missing(tmp_path, monkeypatch, number):
    original = os.open

    def fail(path, *args, **kwargs):
        if path == "failure.json":
            raise OSError(number, "read failed")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail)
    with pytest.raises(DocumentError) as error:
        WorkspaceBrowser(tmp_path).read_file("/workspace/failure.json")
    assert error.value.code != "file_not_found"


def test_browser_keeps_json_bytes(tmp_path):
    content = b'{"content":"not just this field", "value": 42}\n'
    (tmp_path / "result.json").write_bytes(content)
    assert WorkspaceBrowser(tmp_path).read_file("/workspace/result.json")[0] == content
