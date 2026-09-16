"""Immutable candidate packages, explicit review/evaluation, and scoped activation."""
from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from importlib.resources import files
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
        raise DocumentError("skill_package_size")
    entries = {}
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.infolist()) > 100:
                raise DocumentError("skill_package_capacity")
            for entry in archive.infolist():
                path = PurePosixPath(entry.filename)
                if entry.is_dir():
                    continue
                total += entry.file_size
                if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                        or str(path) != entry.filename or entry.filename in entries
                        or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1
                        or any(p.startswith(".") for p in path.parts)
                        or path.suffix not in {".md", ".txt", ".json", ".py", ".html", ".css", ".js", ".yaml", ".yml"}
                        or total > MAX_PACKAGE or entry.file_size > 256 * 1024):
                    raise DocumentError("unsafe_skill_package")
                entries[entry.filename] = archive.read(entry).decode("utf-8")
    except (zipfile.BadZipFile, UnicodeError, RuntimeError) as exc:
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
    digest = hashlib.sha256(raw).hexdigest()
    text = "\n".join(entries.values())
    warnings = [pattern for pattern in (r"(?i)ignore.{0,30}(previous|system)", r"(?i)(api[_-]?key|password)\s*[:=]\s*['\"]?\S{10,}",
                                        r"(?i)npx\s+skills\s+add", r"(?i)curl.+\|\s*(bash|sh)") if re.search(pattern, text)]
    return {"slug": meta["name"], "description": meta["description"], "digest": digest,
            "files": entries, "warnings": warnings, "revision": 1, "status": "candidate",
            "review": None, "evaluation": None}


class SkillStorage:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn

    def _get(self, db, scope, slug, digest):
        row = db.execute("SELECT document FROM dear_skill_versions WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s AND digest=%s",
                         (*scope, slug, digest)).fetchone()
        if row is None:
            raise DocumentError("skill_version_not_found", 404)
        return row["document"]

    def _save(self, db, scope, doc):
        db.execute("""UPDATE dear_skill_versions SET document=%s WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s AND digest=%s""",
                   (Jsonb(doc), *scope, doc["slug"], doc["digest"]))

    def create(self, scope, raw: bytes, *, source: str):
        doc = inspect_package(raw)
        if files("runtime_service.services.dearflow_agent").joinpath("skills", doc["slug"]).is_dir():
            raise DocumentError("reserved_public_skill_name")
        doc["source"] = source[:1000]
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            rows = db.execute("SELECT document FROM dear_skill_versions WHERE tenant_id=%s AND project_id=%s AND user_id=%s", scope).fetchall()
            existing = next((r["document"] for r in rows if r["document"]["digest"] == doc["digest"]), None)
            if existing:
                return self.summary(existing)
            if len(rows) >= 50:
                raise DocumentError("skill_version_capacity", 409)
            db.execute("INSERT INTO dear_skill_versions VALUES (%s,%s,%s,%s,%s,%s)",
                       (*scope, doc["slug"], doc["digest"], Jsonb(doc)))
        return self.summary(doc)

    @staticmethod
    def summary(doc):
        return {**{k: v for k, v in doc.items() if k != "files"},
                "manifest": [{"path": k, "sha256": hashlib.sha256(v.encode()).hexdigest()} for k, v in doc["files"].items()]}

    def list(self, scope):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            return [self.summary(r["document"]) for r in db.execute(
                "SELECT document FROM dear_skill_versions WHERE tenant_id=%s AND project_id=%s AND user_id=%s ORDER BY slug,digest", scope).fetchall()]

    def get(self, scope, slug, digest):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            return self._get(db, scope, slug, digest)

    def record(self, scope, slug, digest, *, expected_revision: int, kind: str, evidence: dict):
        if kind not in {"review", "evaluation"}:
            raise DocumentError("invalid_skill_evidence")
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            doc = self._get(db, scope, slug, digest)
            if doc["revision"] != expected_revision or doc["status"] == "revoked":
                raise DocumentError("skill_revision_conflict", 409)
            doc[kind] = {**evidence, "digest": digest}
            doc["revision"] += 1
            self._save(db, scope, doc)
        return self.summary(doc)

    def activate(self, scope, slug, digest, *, expected_revision: int, revoke=False):
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            doc = self._get(db, scope, slug, digest)
            if doc["revision"] != expected_revision:
                raise DocumentError("skill_revision_conflict", 409)
            if not revoke:
                if doc["status"] == "revoked" or doc["warnings"] or not all(
                    doc.get(k) and doc[k].get("passed") is True and doc[k].get("digest") == digest for k in ("review", "evaluation")
                ):
                    raise DocumentError("skill_not_approved", 409)
                rows = db.execute("SELECT document FROM dear_skill_versions WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s", (*scope, slug)).fetchall()
                for row in rows:
                    other = row["document"]
                    if other["status"] == "active" and other["digest"] != digest:
                        other.update(status="inactive", revision=other["revision"] + 1)
                        self._save(db, scope, other)
            doc.update(status="revoked" if revoke else "active", revision=doc["revision"] + 1)
            self._save(db, scope, doc)
        return self.summary(doc)

    def freeze(self, scope, thread_id: str):
        """A thread keeps its first versions. Revocation never silently upgrades it."""
        with connect(self.dsn) as db:
            lock_scope(db, scope, "skills")
            row = db.execute("SELECT versions FROM dear_skill_bindings WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND thread_id=%s", (*scope, thread_id)).fetchone()
            if row:
                versions = row["versions"]
            else:
                rows = db.execute("SELECT document FROM dear_skill_versions WHERE tenant_id=%s AND project_id=%s AND user_id=%s", scope).fetchall()
                versions = {r["document"]["slug"]: r["document"]["digest"] for r in rows if r["document"]["status"] == "active"}
                db.execute("INSERT INTO dear_skill_bindings VALUES (%s,%s,%s,%s,%s)", (*scope, thread_id, Jsonb(versions)))
            docs = [self._get(db, scope, slug, digest) for slug, digest in versions.items()]
            if any(d["status"] == "revoked" for d in docs):
                raise DocumentError("thread_skill_revoked", 409)
            return docs
