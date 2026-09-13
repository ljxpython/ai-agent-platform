from pathlib import Path
import pytest

from runtime_service.workspace.scoped import hashed_thread_root, thread_scope_hash
from runtime_service.workspace.image_refs import (
    validate_image_ref,
    validate_image_path,
    parse_image_reference_block,
    build_image_reference_block,
    ImageRefValidationError,
)


def test_scoped_hash_derivation():
    h1 = thread_scope_hash("tenant-1", "proj-1", "thread-1")
    h2 = thread_scope_hash("tenant-1", "proj-1", "thread-1")
    h3 = thread_scope_hash("tenant-1", "proj-1", "thread-2")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64

    base = Path("/tmp/runtime")
    root = hashed_thread_root(base, "tenant-1", "proj-1", "thread-1")
    assert root == base.resolve() / h1


def test_validate_image_path():
    folder, filename = validate_image_path("/workspace/uploads/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.png")
    assert folder == "uploads"
    assert filename == "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.png"

    folder, filename = validate_image_path("/workspace/generated/0123456789abcdef0123456789abcdef.webp")
    assert folder == "generated"
    assert filename == "0123456789abcdef0123456789abcdef.webp"

    # Invalid paths
    with pytest.raises(ImageRefValidationError):
        validate_image_path("../outside.png")
    with pytest.raises(ImageRefValidationError):
        validate_image_path("/workspace/secret.txt")
    with pytest.raises(ImageRefValidationError):
        validate_image_path("/workspace/uploads/sub/123.png")
    with pytest.raises(ImageRefValidationError):
        validate_image_path("/workspace/uploads/123.gif")
    with pytest.raises(ImageRefValidationError):
        validate_image_path("/workspace/uploads/not-64-hex.png")


def test_validate_image_ref_and_blocks():
    valid_hash = "a" * 64
    valid_ref = {
        "version": 1,
        "path": f"/workspace/uploads/{valid_hash}.png",
        "mime_type": "image/png",
        "size_bytes": 1024,
        "sha256": valid_hash,
    }
    checked = validate_image_ref(valid_ref)
    assert checked["version"] == 1
    assert checked["sha256"] == valid_hash

    # Rejection cases
    with pytest.raises(ImageRefValidationError):
        validate_image_ref({**valid_ref, "version": 2})
    with pytest.raises(ImageRefValidationError):
        validate_image_ref({**valid_ref, "size_bytes": 0})
    with pytest.raises(ImageRefValidationError):
        validate_image_ref({**valid_ref, "size_bytes": 25 * 1024 * 1024})
    with pytest.raises(ImageRefValidationError):
        validate_image_ref({**valid_ref, "mime_type": "image/gif"})
    with pytest.raises(ImageRefValidationError):
        validate_image_ref({**valid_ref, "sha256": "b" * 64})  # mismatch uploads path

    # Block parsing and building
    block = build_image_reference_block(valid_ref, name="测试.png")
    assert block["type"] == "text"
    assert "测试.png" in block["text"]
    parsed = parse_image_reference_block(block)
    assert parsed == checked
