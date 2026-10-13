"""SQLite write-ahead facts precede side effects; unresolved IDs are never replayed."""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.node_client import decode, encode


def digest(value):
    return hashlib.sha256(
        json.dumps(encode(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS workspaces (
                    key TEXT PRIMARY KEY, status TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (
                    host TEXT NOT NULL, id TEXT NOT NULL, workspace TEXT NOT NULL,
                    digest TEXT NOT NULL, status TEXT NOT NULL, result TEXT,
                    created REAL NOT NULL, PRIMARY KEY(host,id));
                CREATE TABLE IF NOT EXISTS resources (
                    host TEXT NOT NULL, id TEXT NOT NULL, workspace TEXT NOT NULL,
                    kind TEXT NOT NULL, name TEXT NOT NULL, image TEXT NOT NULL,
                    policy TEXT NOT NULL, deadline REAL NOT NULL,
                    status TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(host,id));
                CREATE TABLE IF NOT EXISTS cancellations (
                    host TEXT NOT NULL, id TEXT NOT NULL, workspace TEXT NOT NULL,
                    PRIMARY KEY(host,id));
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(workspaces)")}
            for name, kind in (("evidence", "TEXT"), ("deletion_at", "REAL")):
                if name not in columns:
                    db.execute(f"ALTER TABLE workspaces ADD COLUMN {name} {kind}")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def begin(self, host, operation_id, workspace, request):
        fingerprint = digest(request)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM operations WHERE host=? AND id=?", (host, operation_id)
            ).fetchone()
            if row:
                if row["workspace"] != workspace or row["digest"] != fingerprint:
                    raise DocumentError("sandbox_operation_conflict", 409)
                return dict(row), False
            db.execute(
                "INSERT INTO operations VALUES (?,?,?,?, 'accepted',NULL,?)",
                (host, operation_id, workspace, fingerprint, time.time()),
            )
            return None, True

    def finish(self, host, operation_id, result):
        with self.connect() as db:
            db.execute(
                "UPDATE operations SET status='finished',result=? WHERE host=? AND id=?",
                (json.dumps(encode(result)), host, operation_id),
            )

    def reject(self, host, operation_id, error):
        with self.connect() as db:
            db.execute(
                "UPDATE operations SET status='rejected',result=? WHERE host=? AND id=?",
                (
                    json.dumps({"code": error.code, "status_code": error.status_code}),
                    host,
                    operation_id,
                ),
            )

    def operation(self, host, operation_id, workspace):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM operations WHERE host=? AND id=? AND workspace=?",
                (host, operation_id, workspace),
            ).fetchone()
        if row is None:
            return {"status": "missing"}
        return {
            "status": row["status"],
            "result": decode(json.loads(row["result"])) if row["result"] else None,
        }

    def reserve(self, resource, capacity):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cancellation = db.execute(
                "SELECT workspace FROM cancellations WHERE host=? AND id=?",
                (resource["host"], resource["id"]),
            ).fetchone()
            if cancellation:
                raise DocumentError("sandbox_resource_cancelled", 409)
            count = db.execute(
                "SELECT count(*) FROM resources WHERE status IN ('reserved','running','unconfirmed')"
            ).fetchone()[0]
            if count >= capacity:
                raise DocumentError("sandbox_capacity_reached", 429)
            db.execute(
                "INSERT INTO resources(host,id,workspace,kind,name,image,policy,deadline,status) VALUES (?,?,?,?,?,?,?,?, 'reserved')",
                tuple(
                    resource[key]
                    for key in (
                        "host",
                        "id",
                        "workspace",
                        "kind",
                        "name",
                        "image",
                        "policy",
                        "deadline",
                    )
                ),
            )

    def resources(self, host=None, workspace=None):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM resources"
                + (" WHERE host=? AND workspace=?" if host else ""),
                (host, workspace) if host else (),
            ).fetchall()
        return [dict(row) for row in rows]

    def resource(self, host, resource_id, workspace):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM resources WHERE host=? AND id=? AND workspace=?",
                (host, resource_id, workspace),
            ).fetchone()
        if not row:
            raise DocumentError("sandbox_resource_not_found", 404)
        return dict(row)

    def update(self, host, resource_id, status, *, acknowledged=False):
        with self.connect() as db:
            db.execute(
                "UPDATE resources SET status=?,acknowledged=max(acknowledged,?) WHERE host=? AND id=?",
                (status, int(acknowledged), host, resource_id),
            )

    def cancellation(self, host, resource_id, workspace):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            resource = db.execute(
                "SELECT workspace FROM resources WHERE host=? AND id=?",
                (host, resource_id),
            ).fetchone()
            if resource and resource["workspace"] != workspace:
                raise DocumentError("sandbox_resource_not_found", 404)
            db.execute(
                "INSERT INTO cancellations VALUES (?,?,?) ON CONFLICT DO NOTHING",
                (host, resource_id, workspace),
            )
            row = db.execute(
                "SELECT workspace FROM cancellations WHERE host=? AND id=?",
                (host, resource_id),
            ).fetchone()
            if row["workspace"] != workspace:
                raise DocumentError("sandbox_resource_not_found", 404)
