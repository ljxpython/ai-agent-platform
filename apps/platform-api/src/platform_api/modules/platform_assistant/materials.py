"""Read an explicitly published document/source manifest, never arbitrary host files."""

import hashlib
import json
from pathlib import Path

from platform_api.core.errors import BadRequestError, ServiceUnavailableError


def read_material(root, body, *, source=False):
    # One maintained user-guide source; source snapshots keep separate semantics.
    if not root and not source:
        root = Path(__file__).resolve().parents[6] / "docs" / "assistant"
    entries = []
    revision = "current"
    base = None
    if root:
        try:
            base = Path(root).resolve(strict=True)
            manifest = base / "manifest.json"
            if manifest.is_symlink() or manifest.stat().st_size > 512000:
                raise ValueError()
            catalog = json.loads(manifest.read_text())
            if not isinstance(catalog, dict):
                raise ValueError()
            revision = str(
                catalog["revision"] if source else catalog.get("revision", "current")
            )[:128]
            entries = catalog["files"]
        except (OSError, ValueError, KeyError, TypeError):
            raise ServiceUnavailableError(
                code="assistant_material_unavailable", message="资料索引不可用。"
            ) from None
    elif source:
        raise ServiceUnavailableError(
            code="assistant_source_unavailable", message="尚未发布获准源码快照。"
        )
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ServiceUnavailableError(
            code="assistant_material_unavailable", message="资料索引超限。"
        )
    results = []
    documents = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        if body.document_id and entry["id"] != body.document_id:
            continue
        if base:
            if not isinstance(entry.get("path"), str):
                continue
            relative = Path(entry["path"])
            if relative.is_absolute() or any(
                p.startswith(".") or p in {"node_modules", "__pycache__"}
                for p in relative.parts
            ):
                continue
            if relative.suffix not in (
                {".py", ".ts", ".vue", ".js", ".sql"} if source else {".md", ".txt"}
            ):
                continue
            path = base / relative
            if any(
                p.is_symlink() for p in (path, *path.parents) if p != base
            ) or not path.resolve().is_relative_to(base):
                continue
            if not path.is_file() or path.stat().st_size > 500000:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
        else:
            content = entry["text"]
        lines = content.splitlines()
        if not source:
            if not body.document_id:
                documents.append(
                    {
                        "document_id": entry["id"],
                        "title": str(entry.get("title", entry["id"]))[:160],
                        "summary": str(entry.get("summary", ""))[:400],
                    }
                )
                if len(documents) >= 32:
                    break
                continue
            start = 0
        elif body.document_id:
            start = body.line - 1
        elif body.query:
            terms = body.query.casefold().split()
            start = next(
                (
                    i
                    for i, line in enumerate(lines)
                    if any(t in line.casefold() for t in terms)
                ),
                -1,
            )
            if start < 0:
                continue
        else:
            start = 0
        line_limit, char_limit = (80, 8000) if source else (300, 16000)
        text = "\n".join(lines[start : start + line_limit])[:char_limit]
        results.append(
            {
                "document_id": entry["id"],
                "path": entry.get("path"),
                "title": entry.get("title", entry["id"]),
                "revision": revision,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "line_start": start + 1,
                "line_end": start + len(text.splitlines()),
                "text": text,
                "truncated": start + line_limit < len(lines)
                or len("\n".join(lines[start : start + line_limit])) > char_limit,
            }
        )
        if len(results) >= 5:
            break
    if body.document_id and not results:
        raise BadRequestError(
            code="assistant_document_missing", message="未找到获准资料，请先检索目录。"
        )
    return {
        "sources": results,
        "catalog": documents,
        "revision": revision,
        "untrusted_content": True,
    }
