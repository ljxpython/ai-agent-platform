import pytest

from runtime_service.build_info import STARTUP_PACKAGE_DIGEST, package_digest


def test_package_identity_changes_with_bytes_but_not_bytecode(tmp_path):
    path = tmp_path / "agent.py"
    path.write_text("print(1)\n")
    first = package_digest(tmp_path)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "agent.pyc").write_bytes(b"generated")
    assert package_digest(tmp_path) == first
    path.write_text("print(2)\n")
    assert package_digest(tmp_path) != first
    path.rename(tmp_path / "renamed.py")
    assert package_digest(tmp_path) != first
    assert len(STARTUP_PACKAGE_DIGEST) == 64


def test_symlink_and_missing_package_cannot_attest_a_deployment(tmp_path):
    with pytest.raises(ValueError, match="file count"):
        package_digest(tmp_path)
    path = tmp_path / "source.py"
    path.write_text("pass\n")
    (tmp_path / "linked.py").symlink_to(path)
    with pytest.raises(ValueError, match="symbolic link"):
        package_digest(tmp_path)
