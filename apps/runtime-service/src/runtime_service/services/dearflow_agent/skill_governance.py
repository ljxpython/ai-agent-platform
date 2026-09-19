"""One current private skill per owner; atomic writes with opaque CAS revisions."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from uuid import uuid4
import re
import stat
import zipfile
from pathlib import PurePosixPath

import yaml
from psycopg.types.json import Jsonb

from runtime_service.services.dearflow_agent.governance_storage import (
    connect,
    lock_scope,
)
from runtime_service.workspace.documents import DocumentError

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
MAX_PACKAGE = 1024 * 1024


def inspect_package(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_PACKAGE:
        raise DocumentError("skill_package_size", 413)
    entries = {}
    seen = set()
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist()) > 100:
                raise DocumentError("skill_package_capacity")
            for entry in archive.infolist():
                filename = entry.filename[:-1] if entry.is_dir() else entry.filename
                path = PurePosixPath(filename)
                total += entry.file_size
                if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                        or not filename or str(path) != filename or filename in seen
                        or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1
                        or any(p.startswith(".") for p in path.parts)
                        or not entry.is_dir() and path.suffix not in {".md", ".txt", ".json", ".py", ".html", ".css", ".js", ".yaml", ".yml"}
                        ):
                    raise DocumentError("unsafe_skill_package")
                seen.add(filename)
                if entry.is_dir():
                    continue
                if total > MAX_PACKAGE or entry.file_size > 256 * 1024:
                    raise DocumentError("skill_package_size", 413)
                entries[entry.filename] = archive.read(entry).decode("utf-8")
                if "\x00" in entries[entry.filename]:
                    raise DocumentError("invalid_skill_package")
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, NotImplementedError) as exc:
        raise DocumentError("invalid_skill_package") from exc
    skill = entries.get("SKILL.md", "")
    parts = skill.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        raise DocumentError("skill_frontmatter_required")
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise DocumentError("invalid_skill_frontmatter") from exc
    if (not isinstance(meta, dict) or not isinstance(meta.get("name"), str)
            or not SLUG.fullmatch(meta["name"]) or len(meta["name"]) > 64
            or not isinstance(meta.get("description"), str) or not 1 <= len(meta["description"]) <= 1000):
        raise DocumentError("invalid_skill_metadata")
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    text = "\n".join(entries.values())
    warnings = [pattern for pattern in (r"(?i)ignore.{0,30}(previous|system)", r"(?i)(api[_-]?key|password)\s*[:=]\s*['\"]?\S{10,}",
                                        r"(?i)npx\s+skills\s+add", r"(?i)curl.+\|\s*(bash|sh)") if re.search(pattern, text)]
    return {"slug": meta["name"], "name": meta["name"], "description": meta["description"],
            "digest": digest, "files": entries, "warnings": warnings}


class SkillStorage:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn

    def _get(self, db, scope, slug):
        row = db.execute("SELECT document FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s", (*scope, slug)).fetchone()
        if row is None:
            raise DocumentError("skill_not_found", 404)
        return row["document"]

    @staticmethod
    def summary(doc):
        return {**{k: v for k, v in doc.items() if k != "files"},
                "manifest": [{"path": k, "size": len(v.encode()), "readable": True} for k, v in sorted(doc["files"].items())]}

    @staticmethod
    def _revision(doc):
        doc.update(revision=str(uuid4()), updated_at=datetime.now(timezone.utc).isoformat())

    @staticmethod
    def _check(doc, revision):
        if not revision or doc["revision"] != revision:
            raise DocumentError("skill_revision_conflict", 409)

    def _save(self, db, scope, doc):
        self._revision(doc)
        db.execute("UPDATE dear_skills SET document=%s WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s", (Jsonb(doc), *scope, doc["slug"]))

    def create(self, scope, raw: bytes, *, source: str):
        doc = self._inspect(raw, source)
        doc["enabled"] = True
        self._revision(doc)
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            rows = db.execute("SELECT slug FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s", scope).fetchall()
            if any(r["slug"] == doc["slug"] for r in rows):
                raise DocumentError("skill_name_conflict", 409)
            if len(rows) >= 50:
                raise DocumentError("skill_capacity", 409)
            db.execute("INSERT INTO dear_skills VALUES (%s,%s,%s,%s,%s)", (*scope, doc["slug"], Jsonb(doc)))
        return self.summary(doc)

    @staticmethod
    def _inspect(raw, origin):
        doc = inspect_package(raw)
        from runtime_service.services.dearflow_agent.skill_catalog import public_catalog
        if any(doc["slug"] in {item["slug"], item["name"]} for item in public_catalog()):
            raise DocumentError("reserved_public_skill_name")
        if doc["warnings"]:
            raise DocumentError("skill_security_blocked")
        doc.update(source="custom", origin=origin[:1000])
        return doc

    def list(self, scope):
        return [self.summary(d) for d in self.documents(scope)]

    def documents(self, scope, *, enabled_only=False):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            docs = [r["document"] for r in db.execute("SELECT document FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s ORDER BY slug", scope).fetchall()]
        return [d for d in docs if d["enabled"] or not enabled_only]

    def get(self, scope, slug):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            return self._get(db, scope, slug)

    def update(self, scope, slug, raw, *, expected_revision, source="explicit-management"):
        doc = self._inspect(raw, source)
        if doc["slug"] != slug:
            raise DocumentError("skill_name_mismatch")
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            old = self._get(db, scope, slug)
            self._check(old, expected_revision)
            doc["enabled"] = old["enabled"]
            self._save(db, scope, doc)
        return self.summary(doc)

    def set_enabled(self, scope, slug, *, enabled: bool, expected_revision):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            doc = self._get(db, scope, slug)
            self._check(doc, expected_revision)
            doc["enabled"] = enabled
            self._save(db, scope, doc)
        return self.summary(doc)

    def delete(self, scope, slug, *, expected_revision):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            self._check(self._get(db, scope, slug), expected_revision)
            db.execute("DELETE FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s", (*scope, slug))
