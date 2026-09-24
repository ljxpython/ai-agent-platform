"""Bounded, revisioned user facts. PostgreSQL is the only canonical owner."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from threading import Event
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

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
    expected_revision: int = Field(ge=0, strict=True)
    fact_id: str | None = Field(default=None, max_length=64)
    replace_fact_id: str | None = Field(default=None, max_length=64)
    fact: FactInput | None = None
    automatic_candidates: StrictBool | None = None
    facts: list[FactInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_action_fields(self):
        provided = self.model_fields_set - {"action", "expected_revision"}
        allowed = {
            "save": {"fact", "fact_id"}, "delete": {"fact_id"},
            "accept": {"fact_id", "replace_fact_id"}, "reject": {"fact_id"},
            "settings": {"automatic_candidates"}, "restore": {"facts"}, "clear": set(),
        }[self.action]
        required = {
            "save": {"fact"}, "delete": {"fact_id"}, "accept": {"fact_id"},
            "reject": {"fact_id"}, "settings": {"automatic_candidates"},
            "restore": {"facts"}, "clear": set(),
        }[self.action]
        if provided - allowed or required - provided or any(getattr(self, key) is None for key in required):
            raise ValueError("invalid_memory_command_fields")
        if self.action == "restore" and not self.facts:
            raise ValueError("memory_restore_empty")
        return self


def fresh_document():
    return {"schema_version": 1, "revision": 0, "epoch": 0, "automatic_candidates": False,
            "facts": [], "candidates": [], "deleted_digests": [], "sources": []}


def fingerprint(text):
    return hashlib.sha256(" ".join(text.split()).casefold().encode()).hexdigest()


def now():
    return datetime.now(UTC)


def visible(fact):
    return not fact.get("expires_at") or datetime.fromisoformat(fact["expires_at"]) > now()


def project_document(doc, query="", include_candidates=True):
    facts = [f for f in doc["facts"] if visible(f)]
    if query:
        terms = query.casefold().split()
        facts = [f for f in facts if all(t in f["text"].casefold() for t in terms)]
    return {"schema_version": 1, "revision": doc["revision"], "epoch": doc["epoch"],
            "automatic_candidates": doc["automatic_candidates"], "facts": facts,
            "candidates": [f for f in doc["candidates"] if visible(f)] if include_candidates else []}


def project_extraction(doc):
    extraction = doc.get("extraction", {})
    status = extraction.get("status", "never")
    deadline = extraction.get("deadline_at")
    if status == "running" and deadline and datetime.fromisoformat(deadline) <= now():
        status = "interrupted"
    return {"status": status, "updated_at": extraction.get("updated_at"),
            "source_thread_id": extraction.get("source_thread_id"),
            "candidate_count": extraction.get("candidate_count", 0),
            "error_code": extraction.get("error_code"),
            "pause_reason": doc.get("maintenance_reason")}


class MemoryStorage:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn

    def _load(self, db, scope):
        lock_scope(db, scope, "memory")
        row = db.execute("SELECT document FROM dear_memory WHERE tenant_id=%s AND project_id=%s AND user_id=%s", scope).fetchone()
        return row["document"] if row else fresh_document()

    def _save(self, db, scope, doc):
        if len(doc["facts"]) > 100 or len(doc["candidates"]) > 100:
            raise DocumentError("memory_capacity_exceeded", 409)
        doc["revision"] += 1
        self._write(db, scope, doc)

    def _write(self, db, scope, doc):
        db.execute("""INSERT INTO dear_memory VALUES (%s,%s,%s,%s)
            ON CONFLICT (tenant_id,project_id,user_id) DO UPDATE SET document=EXCLUDED.document""",
                   (*scope, Jsonb(doc)))

    def read(self, scope, query: str = "", *, include_candidates=True):
        if len(query) > 500:
            raise DocumentError("memory_query_too_long")
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
        return project_document(doc, query, include_candidates)

    def view(self, scope):
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
        return project_document(doc), project_extraction(doc)

    def change(self, scope, command: MemoryCommand, *, thread_id: str, source_id: str):
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            if command.expected_revision != doc["revision"]:
                raise DocumentError("memory_revision_conflict", 409)
            doc["facts"] = [f for f in doc["facts"] if visible(f)]
            doc["candidates"] = [f for f in doc["candidates"] if visible(f)]
            action = command.action
            mutation = {"action": action, "changed": True, "added": 0, "updated": 0, "removed": 0, "skipped": 0}
            if action == "clear":
                # Incrementing the epoch rejects every late extraction from before this clear.
                mutation["removed"] = sum(visible(f) for f in doc["facts"])
                doc = {**fresh_document(), "epoch": doc["epoch"] + 1, "revision": doc["revision"]}
            elif action == "settings":
                if command.automatic_candidates is None:
                    raise DocumentError("memory_setting_required")
                if command.automatic_candidates and doc.get("maintenance_reason"):
                    raise DocumentError("memory_maintenance_required", 409)
                if doc["automatic_candidates"] == command.automatic_candidates:
                    mutation["changed"] = False
                else:
                    doc["automatic_candidates"] = command.automatic_candidates
                    doc["epoch"] += 1
            elif action in {"delete", "accept", "reject"}:
                collection = "facts" if action == "delete" else "candidates"
                fact = next((f for f in doc[collection] if f["id"] == command.fact_id), None)
                if fact is None:
                    raise DocumentError("memory_not_found", 404)
                doc[collection].remove(fact)
                if doc.get("maintenance_reason") == "candidate_limit" and len(doc["candidates"]) < 100:
                    doc.pop("maintenance_reason", None)
                if action == "accept":
                    if not visible(fact):
                        raise DocumentError("memory_expired", 409)
                    if command.replace_fact_id:
                        replaced = next((f for f in doc["facts"] if f["id"] == command.replace_fact_id), None)
                        if replaced is None:
                            raise DocumentError("memory_not_found", 404)
                        doc["facts"].remove(replaced)
                        digest = fingerprint(replaced["text"])
                        self._remember_deleted(doc, digest)
                        if any(fingerprint(item["text"]) == fingerprint(fact["text"])
                               for item in doc["facts"]):
                            raise DocumentError("memory_duplicate_fact", 409)
                        mutation["updated"] = 1
                        doc["epoch"] += 1
                    elif any(fingerprint(f["text"]) == fingerprint(fact["text"]) for f in doc["facts"] if visible(f)):
                        raise DocumentError("memory_duplicate_fact", 409)
                    fact.update(origin="confirmed", revision=fact["revision"] + 1, updated_at=now().isoformat())
                    doc["facts"].append(fact)
                    if not command.replace_fact_id:
                        mutation["added"] = 1
                else:
                    mutation["removed"] = int(action == "delete")
                    digest = fingerprint(fact["text"])
                    self._remember_deleted(doc, digest)
                    doc["epoch"] += 1
            else:
                inputs = command.facts if action == "restore" else [command.fact]
                if not inputs or any(f is None for f in inputs):
                    raise DocumentError("memory_fact_required")
                known = {fingerprint(f["text"]) for f in doc["facts"] if visible(f)}
                for value in inputs:
                    if not value.text.strip() or value.expires_at and (value.expires_at.tzinfo is None or value.expires_at <= now()):
                        raise DocumentError("invalid_memory_fact")
                    old = next((f for f in doc["facts"] if f["id"] == command.fact_id), None) if action == "save" else None
                    if command.fact_id and action == "save" and old is None:
                        raise DocumentError("memory_not_found", 404)
                    digest = fingerprint(value.text)
                    if digest in known and (not old or fingerprint(old["text"]) != digest):
                        if action == "restore":
                            mutation["skipped"] += 1
                            continue
                        raise DocumentError("memory_duplicate_fact", 409)
                    if old:
                        if (old["text"] == value.text and old["category"] == value.category
                                and old.get("expires_at") == value.model_dump(mode="json")["expires_at"]):
                            mutation["changed"] = False
                            continue
                        doc["facts"].remove(old)
                        old_digest = fingerprint(old["text"])
                        known.discard(old_digest)
                        if old_digest != digest:
                            self._remember_deleted(doc, old_digest)
                    fact = value.model_dump(mode="json")
                    management = source_id == "explicit-management"
                    fact.update(id=old["id"] if old else str(uuid4()), origin="user", source_thread_id=thread_id or None,
                                source_kind="management" if management else "tool", source_message_id=None,
                                source_call_id=None if management else source_id, quote=None,
                                revision=old["revision"] + 1 if old else 1,
                                created_at=old["created_at"] if old else now().isoformat(), updated_at=now().isoformat())
                    doc["facts"].append(fact)
                    known.add(digest)
                    mutation["updated" if old else "added"] += 1
                if mutation["added"] or mutation["updated"]:
                    doc["epoch"] += 1
                else:
                    mutation["changed"] = False
            if mutation["changed"]:
                self._save(db, scope, doc)
            snapshot = project_document(doc)
            extraction = project_extraction(doc)
        return {**snapshot, "mutation": mutation, "extraction": extraction}

    def propose(self, scope, *, epoch: int, thread_id: str, message_id: str,
                source_text: str, candidates: list[dict], usage: dict | None = None,
                run_id: str | None = None, cancel_event: Event | None = None,
                source_messages: dict[str, str] | None = None):
        """Model suggestions never write active facts; the source is a real human message."""
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            if not doc["automatic_candidates"] or epoch != doc["epoch"]:
                return {"status": "stale_or_disabled"}
            extraction = doc.get("extraction_runs", {}).get(run_id, doc.get("extraction", {}))
            claimed_here = (run_id and extraction.get("run_id") == run_id
                and extraction.get("source") == source_key and extraction.get("status") == "running"
                and not extraction.get("model_committed"))
            if source_key in doc["sources"] and not claimed_here:
                return {"status": "duplicate"}
            if run_id and not claimed_here:
                return {"status": "stale_or_disabled"}
            if source_messages is not None and set(source_messages) != set(extraction.get("source_ids", [])):
                return {"status": "stale_or_disabled"}
            if cancel_event is not None and cancel_event.is_set():
                return {"status": "cancelled"}
            known = {fingerprint(f["text"]) for f in doc["facts"] + doc["candidates"]} | set(doc["deleted_digests"])
            added = 0
            for candidate in candidates[:5]:
                if run_id and (candidate.get("scope") != "personal" or candidate.get("durability") != "stable"
                               or candidate.get("authority") != "personal_fact"):
                    continue
                quote = candidate.get("quote", "")
                actual_id = candidate.get("source_message_id")
                if source_messages is not None:
                    if actual_id is None and len(source_messages) == 1:
                        actual_id = next(iter(source_messages))
                    if actual_id not in source_messages:
                        continue
                    actual_text = source_messages[actual_id]
                else:
                    actual_id, actual_text = message_id, source_text
                value = FactInput.model_validate({k: v for k, v in candidate.items()
                                                  if k not in {"quote", "scope", "durability", "authority", "source_message_id"}})
                # Exact quotation prevents invented provenance, but does not claim semantic safety.
                if (not quote.strip() or quote not in actual_text or not value.text.strip()
                        or value.expires_at and value.expires_at <= now()
                        or fingerprint(value.text) in known):
                    continue
                if len(doc["candidates"]) >= 100:
                    break
                fact = value.model_dump(mode="json")
                fact.update(id=str(uuid4()), origin="inferred", source_thread_id=thread_id,
                            source_kind="user_message", source_message_id=actual_id,
                            source_call_id=None, quote=quote, revision=1,
                            created_at=now().isoformat(), updated_at=now().isoformat())
                doc["candidates"].append(fact)
                known.add(fingerprint(value.text))
                added += 1
            if source_key not in doc["sources"]:
                if len(doc["sources"]) >= 2000:
                    return {"status": "source_limit"}
                doc["sources"].append(source_key)
            if source_messages is not None:
                for source_id in source_messages:
                    digest = hashlib.sha256((thread_id + ":" + source_id).encode()).hexdigest()
                    if digest not in doc["sources"]:
                        doc["sources"].append(digest)
            doc["last_extraction"] = {"source": source_key, "usage": usage or {}, "at": now().isoformat()}
            if claimed_here:
                extraction["model_committed"] = True
                if doc.get("extraction", {}).get("run_id") == run_id:
                    doc["extraction"]["model_committed"] = True
            if added:
                self._save(db, scope, doc)
            else:
                self._write(db, scope, doc)
            if cancel_event is not None and cancel_event.is_set():
                raise DocumentError("memory_extraction_cancelled", 409)
            return {"status": "proposed", "revision": doc["revision"], "added": added}

    def begin_extraction(self, scope, *, epoch: int, thread_id: str, message_id: str,
                         run_id: str, deadline_at: str, source_ids: list[str] | None = None):
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            if not doc["automatic_candidates"] or doc["epoch"] != epoch:
                return False
            doc["candidates"] = [candidate for candidate in doc["candidates"] if visible(candidate)]
            current = doc.get("extraction_runs", {}).get(run_id, doc.get("extraction", {}))
            if source_key in doc["sources"]:
                if current.get("source") == source_key and current.get("run_id") == run_id and current.get("status") == "running":
                    return ({"deadline": current["deadline_at"], "source_ids": current["source_ids"]}
                            if source_ids is not None else current["deadline_at"])
                return None
            new_ids = [source_id for source_id in (source_ids or []) if hashlib.sha256(
                (thread_id + ":" + source_id).encode()).hexdigest() not in doc["sources"]]
            if source_ids is not None and not new_ids:
                return None
            if len(doc["candidates"]) >= 100:
                doc["automatic_candidates"] = False
                doc["maintenance_reason"] = "candidate_limit"
                doc["extraction"] = {"status": "skipped", "updated_at": now().isoformat(),
                    "source_thread_id": thread_id, "candidate_count": 0,
                    "error_code": "candidate_limit", "pause_reason": "candidate_limit"}
                self._write(db, scope, doc)
                return None
            if len(doc["sources"]) + 1 + len(new_ids) > 2000:
                doc["automatic_candidates"] = False
                doc["maintenance_reason"] = "source_limit"
                doc["extraction"] = {"status": "skipped", "updated_at": now().isoformat(),
                    "source_thread_id": thread_id, "candidate_count": 0,
                    "error_code": "source_limit", "pause_reason": "source_limit"}
                self._write(db, scope, doc)
                return None
            doc["sources"].append(source_key)
            current = {"status": "running", "updated_at": now().isoformat(),
                "source_thread_id": thread_id, "candidate_count": 0, "error_code": None,
                "pause_reason": None, "source": source_key, "run_id": run_id,
                "deadline_at": deadline_at, "attempts": 0, "source_ids": new_ids}
            doc["extraction"] = current
            doc.setdefault("extraction_runs", {})[run_id] = current
            self._write(db, scope, doc)
            return {"deadline": deadline_at, "source_ids": new_ids} if source_ids is not None else deadline_at

    def reserve_extraction_attempt(self, scope, *, epoch: int, thread_id: str,
                                   message_id: str, run_id: str):
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            current = doc.get("extraction_runs", {}).get(run_id, doc.get("extraction", {}))
            if (doc["epoch"] != epoch or not doc["automatic_candidates"]
                    or current.get("source") != source_key or current.get("run_id") != run_id
                    or current.get("status") != "running" or current.get("model_committed")
                    or current.get("attempts", 0) >= 2
                    or datetime.fromisoformat(current["deadline_at"]) <= now()):
                return False
            current["attempts"] = current.get("attempts", 0) + 1
            if doc.get("extraction", {}).get("run_id") == run_id:
                doc["extraction"]["attempts"] = current["attempts"]
            self._write(db, scope, doc)
            return True

    @staticmethod
    def _remember_deleted(doc, digest):
        if digest in doc["deleted_digests"]:
            return
        if len(doc["deleted_digests"]) >= 1000:
            doc["automatic_candidates"] = False
            doc["maintenance_reason"] = "tombstone_limit"
            return
        doc["deleted_digests"].append(digest)

    def finish_extraction(self, scope, *, epoch: int, thread_id: str, message_id: str,
                          run_id: str, status: str, count: int = 0, error_code: str | None = None):
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            doc = self._load(db, scope)
            current = doc.get("extraction_runs", {}).get(run_id, doc.get("extraction", {}))
            if (doc["epoch"] != epoch or current.get("source") != source_key
                    or current.get("run_id") != run_id or current.get("status") != "running"):
                return False
            current.update(status=status, updated_at=now().isoformat(), candidate_count=count,
                           error_code=error_code)
            if doc.get("extraction", {}).get("run_id") == run_id:
                doc["extraction"].update(current)
            doc.get("extraction_runs", {}).pop(run_id, None)
            self._write(db, scope, doc)
            return True

    def extracted(self, scope, thread_id: str, message_id: str):
        source_key = hashlib.sha256((thread_id + ":" + message_id).encode()).hexdigest()
        with connect(self.dsn) as db:
            return source_key in self._load(db, scope)["sources"]

    def context(self, scope, query: str = ""):
        # ponytail: bounded lexical retrieval; add semantic ranking only after measured recall gaps.
        facts = self.read(scope, include_candidates=False)["facts"]
        def tokens(value):
            parts = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", value.casefold())
            return {part for part in parts if part.isascii()} | {
                part[index:index + 2] for part in parts if not part.isascii()
                for index in range(len(part) - 1)}
        query_tokens = tokens(query[:6000])
        scored = sorted(facts, key=lambda fact: (
            len(tokens(fact["text"]) & query_tokens), fact.get("updated_at", ""), fact["id"]), reverse=True)
        matching = [f for f in scored if query_tokens and tokens(f["text"]) & query_tokens][:7]
        remaining = [f for f in scored if f not in matching]
        preferences = [f for f in remaining if f["category"] == "preference"][:3]
        selected = (matching + preferences + [f for f in remaining if f not in preferences])[:10]
        result = []
        budget = 4000
        for fact in selected:
            text = json.dumps({k: fact.get(k) for k in ("id", "text", "category", "source_thread_id", "source_message_id")}, ensure_ascii=False)
            text = text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            if len(text) > budget:
                continue
            result.append(text)
            budget -= len(text)
        return "\n".join(result)
