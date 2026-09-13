import hashlib
import io
from pathlib import Path
from PIL import Image
import pytest

from runtime_service.tools.images import ImageWorkspace, ImageWorkspaceError


def make_test_png(color="red", size=(10, 10)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_put_upload_and_read_asset(tmp_path: Path):
    ws = ImageWorkspace(root=tmp_path)
    png_bytes = make_test_png()
    sha256 = hashlib.sha256(png_bytes).hexdigest()

    # 1. Successful upload
    ref = ws.put_upload(png_bytes, sha256)
    assert ref["version"] == 1
    assert ref["sha256"] == sha256
    assert ref["mime_type"] == "image/png"
    assert ref["size_bytes"] == len(png_bytes)
    assert ref["path"] == f"/workspace/uploads/{sha256}.png"

    # 2. Idempotent upload returns same ref
    ref2 = ws.put_upload(png_bytes, sha256)
    assert ref2 == ref

    # 3. Read asset
    data, read_ref = ws.read_asset(ref["path"])
    assert data == png_bytes
    assert read_ref == ref

    # 4. Describe
    desc = ws.describe(ref["path"])
    assert desc == ref


def test_put_upload_rejections(tmp_path: Path):
    ws = ImageWorkspace(root=tmp_path)
    png_bytes = make_test_png()
    actual_sha = hashlib.sha256(png_bytes).hexdigest()

    # Mismatched sha
    with pytest.raises(ImageWorkspaceError) as exc:
        ws.put_upload(png_bytes, "0" * 64)
    assert exc.value.code == "image_digest_mismatch"

    # Unsupported type (not an image)
    text_bytes = b"hello world"
    text_sha = hashlib.sha256(text_bytes).hexdigest()
    with pytest.raises(ImageWorkspaceError) as exc:
        ws.put_upload(text_bytes, text_sha)
    assert exc.value.code == "image_type_unsupported"

    # Oversize (>5MB)
    fake_large = b"\x00" * (5 * 1024 * 1024 + 1)
    with pytest.raises(ImageWorkspaceError) as exc:
        ws.put_upload(fake_large, "a" * 64)
    assert exc.value.code == "image_too_large"


def test_read_asset_rejections(tmp_path: Path):
    ws = ImageWorkspace(root=tmp_path)

    # Not found
    with pytest.raises(ImageWorkspaceError) as exc:
        ws.read_asset("/workspace/uploads/" + "f" * 64 + ".png")
    assert exc.value.code == "image_not_found"

    # Invalid path
    with pytest.raises(ImageWorkspaceError) as exc:
        ws.read_asset("/workspace/../secret.txt")
    assert exc.value.code == "image_path_invalid"
