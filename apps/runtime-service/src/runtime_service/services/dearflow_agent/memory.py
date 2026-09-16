"""Bounded, revisioned user facts. PostgreSQL is the only canonical owner."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from runtime_service.services.dearflow_agent.governance_storage import (
    connect,
    lock_scope,
)
from runtime_service.workspace.documents import DocumentError


class FactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)
    category: Literal["preference", "fact"] = "preference"
    expires_at: AwareDatetime | None = None


class MemoryCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["save", "delete", "clear", "accept", "reject", "settings", "restore"]
    expected_revision: int = Field(ge=0)
    fact_id: str | None = Field(default=None, max_length=64)
    fact: FactInput | None = None
    automatic_candidates: bool | None = None
    facts: list[FactInput] = Field(default_factory=list, max_length=100)


def fresh_document():
    return {"schema_version": 1, "revision": 0, "epoch": 0, "automatic_candidates": False,
            "facts": [], "candidates": [], "deleted_digests": [], "sources": []}


def fingerprint(text):
    return hashlib.sha256(" ".join(text.split()).casefold().encode()).hexdigest()


def now():
    return datetime.now(UTC)


def visible(fact):
    return not fact.get("expires_at") or datetime.fromisoformat(fact["expires_at"]) > now()


class MemoryStorage:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn

    def _load(self, db, scope):
        lock_scope(db, scope, "memory")
        row = db.execute("SELECT document FROM dear_memory WHERE tenant_id=%s AND project_id=%s AND user_id=%s", scope).fetchone()
        return row["document"] if row else fresh_document()

    def _save(self, db, scope, doc):
        if len(doc["facts"]) > 100 or len(doc["candidates"]) > 100 or len(doc["deleted_digests"]) > 1000 or len(doc["sources"]) > 2000:
            raise DocumentError("memory_capacity_exceeded", 409)
        doc["revision"] += 1
        db.execute("""INSERT INTO dear_memory VALUES (%s,%s,%s,%s)
            ON CONFLICT (tenant_id,project_id,user_id) DO UPDATE SET document=EXCLUDED.document""",
                   (*scope, Jsonb(doc)))

    def read(self, scope, query: str = "", *, include_candidates=True):
        if len(query) > 500:
            raise DocumentError("memory_query_too_long")
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
        facts = [f for f in doc["facts"] if visible(f)]
        if query:
            terms = query.casefold().split()
            facts = [f for f in facts if all(t in f["text"].casefold() for t in terms)]
        return {"schema_version": 1, "revision": doc["revision"], "epoch": doc["epoch"],
                "automatic_candidates": doc["automatic_candidates"], "facts": facts,
                "candidates": [f for f in doc["candidates"] if visible(f)] if include_candidates else []}

    def change(self, scope, command: MemoryCommand, *, thread_id: str, source_id: str):
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            if command.expected_revision != doc["revision"]:
                raise DocumentError("memory_revision_conflict", 409)
            action = command.action
            if action == "clear":
                # Incrementing the epoch rejects every late extraction from before this clear.
                doc = {**fresh_document(), "epoch": doc["epoch"] + 1, "revision": doc["revision"]}
            elif action == "settings":
                if command.automatic_candidates is None:
                    raise DocumentError("memory_setting_required")
                doc["automatic_candidates"] = command.automatic_candidates
                doc["epoch"] += 1
            elif action in {"delete", "accept", "reject"}:
                collection = "facts" if action == "delete" else "candidates"
                fact = next((f for f in doc[collection] if f["id"] == command.fact_id), None)
                if fact is None:
                    raise DocumentError("memory_not_found", 404)
                doc[collection].remove(fact)
                if action == "accept":
                    if not visible(fact):
                        raise DocumentError("memory_expired", 409)
                    fact.update(origin="confirmed", revision=fact["revision"] + 1, updated_at=now().isoformat())
                    doc["facts"].append(fact)
                else:
                    digest = fingerprint(fact["text"])
                    if digest not in doc["deleted_digests"]:
                        doc["deleted_digests"].append(digest)
                    doc["epoch"] += 1
            else:
                inputs = command.facts if action == "restore" else [command.fact]
                if not inputs or any(f is None for f in inputs):
                    raise DocumentError("memory_fact_required")
                for value in inputs:
                    if not value.text.strip() or value.expires_at and (value.expires_at.tzinfo is None or value.expires_at <= now()):
                        raise DocumentError("invalid_memory_fact")
                    old = next((f for f in doc["facts"] if f["id"] == command.fact_id), None) if action == "save" else None
                    if command.fact_id and action == "save" and old is None:
                        raise DocumentError("memory_not_found", 404)
                    if old:
                        doc["facts"].remove(old)
                        digest = fingerprint(old["text"])
                        if digest not in doc["deleted_digests"]:
                            doc["deleted_digests"].append(digest)
                    fact = value.model_dump(mode="json")
                    fact.update(id=old["id"] if old else str(uuid4()), origin="user", source_thread_id=thread_id,
                                source_message_id=source_id, revision=old["revision"] + 1 if old else 1,
                                created_at=old["created_at"] if old else now().isoformat(), updated_at=now().isoformat())
                    doc["facts"].append(fact)
                doc["epoch"] += 1
            self._save(db, scope, doc)
        return self.read(scope)

    def propose(self, scope, *, epoch: int, thread_id: str, message_id: str,
                source_text: str, candidates: list[dict], usage: dict | None = None):
        """Model suggestions never write active facts; the source is a real human message."""
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            if not doc["automatic_candidates"] or epoch != doc["epoch"]:
                return {"status": "stale_or_disabled"}
            if source_key in doc["sources"]:
                return {"status": "duplicate"}
            known = {fingerprint(f["text"]) for f in doc["facts"] + doc["candidates"]} | set(doc["deleted_digests"])
            for candidate in candidates[:5]:
                quote = candidate.get("quote", "")
                value = FactInput.model_validate({k: v for k, v in candidate.items() if k != "quote"})
                # Exact quotation prevents invented provenance, but does not claim semantic safety.
                if (not quote.strip() or quote not in source_text or not value.text.strip()
                        or value.expires_at and value.expires_at <= now()
                        or fingerprint(value.text) in known):
                    continue
                if len(doc["candidates"]) >= 100:
                    break
                fact = value.model_dump(mode="json")
                fact.update(id=str(uuid4()), origin="inferred", source_thread_id=thread_id,
                            source_message_id=message_id, quote=quote, revision=1,
                            created_at=now().isoformat(), updated_at=now().isoformat())
                doc["candidates"].append(fact)
                known.add(fingerprint(value.text))
            doc["sources"].append(source_key)
            doc["last_extraction"] = {"source": source_key, "usage": usage or {}, "at": now().isoformat()}
            self._save(db, scope, doc)
            return {"status": "proposed", "revision": doc["revision"]}

    def extracted(self, scope, thread_id: str, message_id: str):
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            return source_key in self._load(db, scope)["sources"]

    def context(self, scope):
        # ponytail: bounded lexical retrieval; add semantic ranking only after measured recall gaps.
        facts = self.read(scope, include_candidates=False)["facts"]
        result = []
        budget = 4000
        for fact in reversed(facts):
            text = json.dumps({k: fact[k] for k in ("id", "text", "category", "source_thread_id", "source_message_id")}, ensure_ascii=False)
            if len(text) > budget or len(result) >= 10:
                break
            result.append(text)
            budget -= len(text)
        return "\n".join(result)
