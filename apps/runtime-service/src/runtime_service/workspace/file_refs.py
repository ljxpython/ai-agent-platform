"""Versioned document references shared by HTTP, messages and tools."""

import re
from typing import TypedDict

MAX_FILE_BYTES = 20 * 1024 * 1024
MIME_EXT = {
    "application/pdf": "pdf", "text/plain": "txt", "text/markdown": "md",
    "application/json": "json", "text/csv": "csv", "application/zip": "zip",
    "text/javascript": "js",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "text/html": "html", "text/css": "css",
}


class FileRef(TypedDict):
    version: int
    path: str
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str


def validate_file_path(path: object) -> tuple[str, str]:
    extensions = "|".join(sorted(set(MIME_EXT.values())))
    match = re.fullmatch(rf"/workspace/uploads/([0-9a-f]{{64}})\.({extensions})", path) if isinstance(path, str) else None
    if match is None:
        raise ValueError("invalid_file_ref")
    return match.group(1), match.group(2)


def validate_file_ref(value: object) -> FileRef:
    if not isinstance(value, dict) or set(value) != set(FileRef.__annotations__):
        raise ValueError("invalid_file_ref")
    digest, ext = validate_file_path(value["path"])
    name = value["file_name"]
    if (type(value["version"]) is not int or value["version"] != 1
        or type(value["size_bytes"]) is not int or not 0 < value["size_bytes"] <= MAX_FILE_BYTES
        or value["sha256"] != digest or value["mime_type"] not in MIME_EXT
        or MIME_EXT[value["mime_type"]] != ext
        or not isinstance(name, str) or not 0 < len(name) <= 200
        or any(ord(ch) < 32 or ch in "/\\\x7f" for ch in name)):
        raise ValueError("invalid_file_ref")
    return FileRef(**value)
