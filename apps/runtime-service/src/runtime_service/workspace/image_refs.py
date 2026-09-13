from __future__ import annotations

import re
from typing import Any, Mapping, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage


ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}
UPLOAD_MAX_BYTES = 5 * 1024 * 1024
ASSET_MAX_BYTES = 20 * 1024 * 1024

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
_EXT_TO_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


class ImageRef(TypedDict):
    version: int
    path: str
    mime_type: str
    size_bytes: int
    sha256: str


class ImageRefValidationError(ValueError):
    """Raised when an ImageRef fails schema or integrity constraints."""


def validate_image_path(path: str) -> tuple[str, str]:
    """Validate that virtual path is strictly under allowed folders with no traversal.

    Returns (folder, filename).
    """
    if not isinstance(path, str):
        raise ImageRefValidationError("path must be a string")
    if not path.startswith("/workspace/"):
        raise ImageRefValidationError("path must start with /workspace/")
    if "\\" in path or "\x00" in path or "/./" in path or "/../" in path or path.endswith("/.") or path.endswith("/.."):
        raise ImageRefValidationError("path contains invalid path characters")

    rel = path[len("/workspace/"):]
    parts = rel.split("/")
    if len(parts) != 2:
        raise ImageRefValidationError("path must be a direct child of allowed folders")

    folder, filename = parts
    if folder not in {"uploads", "generated", "charts"}:
        raise ImageRefValidationError(f"invalid image folder: {folder}")

    if "." not in filename:
        raise ImageRefValidationError("filename missing extension")
    name_stem, ext = filename.rsplit(".", 1)
    ext = ext.lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise ImageRefValidationError(f"unsupported extension: {ext}")

    if folder == "uploads":
        if not _HEX64_RE.match(name_stem):
            raise ImageRefValidationError("uploads filename must be 64-hex SHA-256")
    elif folder in {"generated", "charts"}:
        if not _HEX32_RE.match(name_stem):
            raise ImageRefValidationError(f"{folder} filename must be 32-hex UUID")

    return folder, filename


def validate_image_ref(
    ref: Mapping[str, Any],
    *,
    max_bytes: int = ASSET_MAX_BYTES,
) -> ImageRef:
    """Validate ImageRef schema strictly."""
    if not isinstance(ref, Mapping):
        raise ImageRefValidationError("ImageRef must be a mapping")

    version = ref.get("version")
    if version != 1 or isinstance(version, bool):
        raise ImageRefValidationError("version must be integer 1")

    path = ref.get("path")
    if not isinstance(path, str):
        raise ImageRefValidationError("path must be a string")
    folder, filename = validate_image_path(path)

    mime_type = ref.get("mime_type")
    if mime_type not in ALLOWED_IMAGE_MIMES:
        raise ImageRefValidationError(f"unsupported mime_type: {mime_type}")

    size_bytes = ref.get("size_bytes")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
        raise ImageRefValidationError("size_bytes must be a positive integer")
    if size_bytes > max_bytes:
        raise ImageRefValidationError(f"size_bytes exceeds limit {max_bytes}")

    sha256 = ref.get("sha256")
    if not isinstance(sha256, str) or not _HEX64_RE.match(sha256):
        raise ImageRefValidationError("sha256 must be 64 lowercase hex digits")

    if folder == "uploads":
        name_stem, _ = filename.rsplit(".", 1)
        if name_stem != sha256:
            raise ImageRefValidationError("uploads filename does not match sha256 claim")

    return ImageRef(
        version=1,
        path=path,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
    )


def parse_image_reference_block(block: Mapping[str, Any]) -> ImageRef | None:
    """Extract and validate ImageRef from a text block extras.runtime_image if present."""
    if not isinstance(block, Mapping):
        return None
    if block.get("type") != "text":
        return None
    extras = block.get("extras")
    if not isinstance(extras, Mapping):
        return None
    runtime_image = extras.get("runtime_image")
    if not isinstance(runtime_image, Mapping):
        return None
    return validate_image_ref(runtime_image)


def build_image_reference_block(
    ref: Mapping[str, Any],
    *,
    name: str | None = None,
) -> dict[str, Any]:
    """Construct canonical text block with extras.runtime_image."""
    validated = validate_image_ref(ref)
    clean_name = name.strip() if name and isinstance(name, str) else None
    if clean_name:
        # Sanitize control characters
        clean_name = "".join(ch for ch in clean_name if ch >= " " and ch != "\x7f")[:120]
    display_name = clean_name or validated["path"].rsplit("/", 1)[-1]

    text = f"[图片附件] {display_name}\n{validated['path']}"
    runtime_img_dict = dict(validated)
    if clean_name:
        runtime_img_dict["name"] = clean_name

    return {
        "type": "text",
        "text": text,
        "extras": {
            "runtime_image": runtime_img_dict,
        },
    }
