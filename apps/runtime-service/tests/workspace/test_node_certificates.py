"""Trust material uses a stable offline CA and never overwrites existing keys."""

import importlib.util
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes


def generator():
    path = Path(__file__).resolve().parents[2] / "scripts/sandbox_node_certificates.py"
    spec = importlib.util.spec_from_file_location("node_certificates_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate


def test_rotation_reuses_ca_changes_leaf_and_token_and_keeps_ca_key_offline(tmp_path):
    root = tmp_path.resolve()
    original, rotated = root / "original", root / "rotated"
    generate = generator()
    generate(original, "127.0.0.1", "test-host", "127.0.0.1/32")
    generate(rotated, "127.0.0.1", "test-host", "127.0.0.1/32", original)
    assert (rotated / "ca.pem").read_bytes() == (original / "ca.pem").read_bytes()
    assert not (rotated / "ca-key.pem").exists()
    assert (rotated / "caller-token").read_bytes() != (
        original / "caller-token"
    ).read_bytes()
    first = x509.load_pem_x509_certificate((original / "server.pem").read_bytes())
    second = x509.load_pem_x509_certificate((rotated / "server.pem").read_bytes())
    assert first.fingerprint(hashes.SHA256()) != second.fingerprint(hashes.SHA256())
    assert all(path.stat().st_mode & 0o077 == 0 for path in rotated.iterdir())
    original_key = (original / "ca-key.pem").read_bytes()
    with pytest.raises(ValueError, match="empty"):
        generate(original, "127.0.0.1", "test-host", "127.0.0.1/32")
    assert (original / "ca-key.pem").read_bytes() == original_key


def test_invalid_source_and_open_network_do_not_leave_partial_secrets(tmp_path):
    root = tmp_path.resolve()
    target = root / "output"
    generate = generator()
    with pytest.raises(ValueError, match="restricted"):
        generate(target, "127.0.0.1", "test-host", "0.0.0.0/0")
    assert not target.exists()
    real = root / "real"
    real.mkdir()
    linked = root / "linked"
    linked.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        generate(linked / "secrets", "127.0.0.1", "test-host", "127.0.0.1/32")
    assert not list(real.iterdir())
