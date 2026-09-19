"""Shared public catalog and bounded, read-only text inspection."""
import hashlib
import json
from importlib.resources import files
from pathlib import Path, PurePosixPath

import yaml

from runtime_service.services.dearflow_agent.skill_governance import SLUG, SkillStorage
from runtime_service.workspace.documents import DocumentError

MAX_TEXT = 256 * 1024
VERIFIED = {"deep-research", "academic-paper-review", "code-documentation", "newsletter-generation",
            "data-analysis", "frontend-design", "web-design-guidelines", "ppt-generation"}


def validate_path(path):
    parsed = PurePosixPath(path)
    if (not path or parsed.is_absolute() or str(parsed) != path or ".." in parsed.parts
            or "\\" in path or any(p.startswith(".") for p in parsed.parts)):
        raise DocumentError("invalid_skill_path")


def public_document(slug):
    if not SLUG.fullmatch(slug) or len(slug) > 64:
        raise DocumentError("skill_not_found", 404)
    root = Path(str(files("runtime_service.services.dearflow_agent").joinpath("skills", slug)))
    if root.is_symlink() or root.joinpath("SKILL.md").is_symlink() or not root.joinpath("SKILL.md").is_file():
        raise DocumentError("skill_not_found", 404)
    contents, manifest, hashes = {}, [], {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(p.startswith(".") or p == "__pycache__" for p in relative.parts):
            continue
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
            continue
        if not path.is_file():
            continue
        name = relative.as_posix()
        size = path.stat().st_size
        item = {"path": name, "size": size, "readable": False}
        if size > MAX_TEXT:
            item["reason"] = "file_too_large"
            # Include bounded metadata in the revision without loading large assets.
            hashes[name] = [size, path.stat().st_mtime_ns]
        else:
            raw = path.read_bytes()
            hashes[name] = hashlib.sha256(raw).hexdigest()
            try:
                text = raw.decode("utf-8")
                if "\x00" in text:
                    raise UnicodeError()
                contents[name] = text
                item["readable"] = True
            except UnicodeError:
                item["reason"] = "not_utf8_text"
        manifest.append(item)
    parts = contents.get("SKILL.md", "").split("---", 2)
    try:
        meta = yaml.safe_load(parts[1]) if len(parts) == 3 and not parts[0].strip() else {}
    except yaml.YAMLError:
        meta = {}
    meta = meta if isinstance(meta, dict) else {}
    return {"source": "public", "slug": slug, "name": str(meta.get("name", slug)),
            "description": str(meta.get("description", "")), "updated_at": None,
            "revision": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "backend_verified": slug in VERIFIED, "recommendable": slug in VERIFIED,
            "files": contents, "manifest": manifest}


def public_catalog():
    root = files("runtime_service.services.dearflow_agent").joinpath("skills")
    return [{k: v for k, v in public_document(p.name).items() if k not in {"files", "manifest"}}
            for p in sorted(root.iterdir(), key=lambda p: p.name)
            if p.is_dir() and p.joinpath("SKILL.md").is_file() and SLUG.fullmatch(p.name)]


def detail(scope, source, slug):
    doc = public_document(slug) if source == "public" else SkillStorage().get(scope, slug)
    return {k: v for k, v in (doc if source == "public" else SkillStorage.summary(doc)).items() if k != "files"}


def content(scope, source, slug, path, revision):
    validate_path(path)
    doc = public_document(slug) if source == "public" else SkillStorage().get(scope, slug)
    if revision != doc["revision"]:
        raise DocumentError("skill_revision_conflict", 409)
    if path not in doc["files"]:
        entry = next((e for e in doc.get("manifest", []) if e["path"] == path), None)
        raise DocumentError(entry.get("reason", "skill_file_not_found") if entry else "skill_file_not_found", 413 if entry else 404)
    return {"path": path, "content": doc["files"][path], "revision": doc["revision"]}
