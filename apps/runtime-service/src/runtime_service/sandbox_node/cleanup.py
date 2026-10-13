"""Explicit verified-orphan cleanup; retained workspaces never expire by idle time."""

import hashlib
import json
import os
import shutil
import time

from runtime_service.workspace.documents import DocumentError


def protected(node, request):
    key = node.storage.key(request)
    resources = node.ledger.resources(request.execution_host, key)
    if any(
        row["status"] in {"reserved", "running", "unconfirmed"}
        or row["kind"] == "background"
        and not row["acknowledged"]
        for row in resources
    ):
        return True
    with node.ledger.connect() as db:
        return (
            db.execute(
                "SELECT 1 FROM operations WHERE host=? AND workspace=? AND status='accepted' AND id<>? LIMIT 1",
                (request.execution_host, key, request.operation_id),
            ).fetchone()
            is not None
        )


def handle_cleanup(node, request):
    action = request.operation.split(".")[1]
    key, root = node.storage.key(request), node.storage.root(request)
    if action == "mark":
        evidence = request.arguments["evidence"]
        if (
            set(evidence)
            != {
                "kind",
                "verified_by",
                "confirmed_at",
                "thread_absent",
                "pending_work_absent",
            }
            or evidence["kind"] not in {"deleted_thread", "verified_orphan"}
            or not isinstance(evidence["verified_by"], str)
            or not evidence["verified_by"].strip()
            or evidence["thread_absent"] is not True
            or evidence["pending_work_absent"] is not True
            or type(evidence["confirmed_at"]) not in {int, float}
            or not 0 < evidence["confirmed_at"] <= time.time()
        ):
            raise DocumentError("workspace_cleanup_evidence_invalid")
        if protected(node, request):
            raise DocumentError("workspace_cleanup_protected", 409)
        with node.ledger.connect() as db:
            db.execute(
                "UPDATE workspaces SET status='deleting',evidence=?,deletion_at=? WHERE key=? AND status='retained'",
                (json.dumps(evidence, sort_keys=True), evidence["confirmed_at"], key),
            )
    with node.ledger.connect() as db:
        row = db.execute("SELECT * FROM workspaces WHERE key=?", (key,)).fetchone()
    if row is None:
        raise DocumentError("workspace_not_found", 404)
    grace = int(os.environ.get("RUNTIME_WORKSPACE_TTL_SECONDS", "604800"))
    if grace < 1:
        raise DocumentError("workspace_cleanup_policy_invalid")
    eligible = (
        row["status"] == "deleting"
        and time.time() - row["deletion_at"] >= grace
        and not protected(node, request)
    )
    token = hashlib.sha256(
        (key + str(row["deletion_at"]) + (row["evidence"] or "")).encode()
    ).hexdigest()
    result = {
        "workspace_id": request.workspace_id,
        "execution_host": request.execution_host,
        "node_id": node.config.node_id,
        "status": row["status"],
        "eligible": eligible,
        "candidate_token": token,
    }
    if action == "apply":
        if (
            row["status"] == "purged"
            and request.arguments.get("candidate_token") == token
        ):
            return result
        if not eligible or request.arguments.get("candidate_token") != token:
            raise DocumentError("workspace_cleanup_protected", 409)
        # rmtree uses directory descriptors on supported Linux hosts; links are unlinked, never followed.
        if not shutil.rmtree.avoids_symlink_attacks:
            raise DocumentError("workspace_cleanup_unsupported", 409)
        if root.parent.exists():
            shutil.rmtree(root.parent)
        with node.ledger.connect() as db:
            db.execute(
                "UPDATE workspaces SET status='purged' WHERE key=? AND status='deleting'",
                (key,),
            )
        result.update(status="purged", eligible=False)
    elif action not in {"report", "mark"}:
        raise DocumentError("sandbox_operation_invalid")
    return result
