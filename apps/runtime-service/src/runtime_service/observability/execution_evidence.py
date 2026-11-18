"""Worker-owned execution facts, outside the Agent-writable Workspace."""

import json
import logging
import os
from uuid import UUID

from runtime_service.build_info import STARTUP_MANIFEST
from runtime_service.db import connect
from runtime_service.runtime.resolver import runtime_config_snapshot

logger = logging.getLogger(__name__)


def record_execution(config, resolved, facts, graph_id, workspace=None):
    if os.getenv("RUNTIME_EVALUATION_EVIDENCE_ENABLED") != "1":
        return
    metadata = config.get("metadata") or {}
    try:
        run_id = str(UUID(str(metadata["run_id"])))
        thread_id = str(UUID(str(config["configurable"]["thread_id"])))
        if (
            facts.scope.operation != "run-create"
            or facts.scope.thread_id != thread_id
            or facts.scope.assistant_id != graph_id
        ):
            raise ValueError("Execution scope mismatch")
        with connect() as connection:
            environment = None
            if workspace is not None:
                source = connection.execute(
                    "SELECT metadata FROM threads WHERE thread_id=%s", (thread_id,)
                ).fetchone()
                capture = (
                    (source or {})
                    .get("metadata", {})
                    .get("evaluation_material_capture")
                )
                if capture:
                    from runtime_service.observability.evaluation_environment import (
                        snapshot_inputs,
                    )

                    environment = snapshot_inputs(workspace, capture)
            if not metadata.get("evaluation_attempt_id") and not environment:
                return
            # Only an engine-owned Run currently executing this factory can produce evidence.
            row = connection.execute(
                "SELECT metadata FROM runs WHERE run_id=%s AND thread_id=%s AND status='running'",
                (run_id, thread_id),
            ).fetchone()
            if not row or row["metadata"].get("evaluation_attempt_id") != metadata.get(
                "evaluation_attempt_id"
            ):
                raise ValueError("Execution identity mismatch")
            connection.execute(
                """INSERT INTO runtime_evaluation_execution
                (tenant_id,project_id,thread_id,run_id,graph_id,attempt_id,manifest,context_hash,config_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT DO NOTHING""",
                (
                    facts.principal.tenant_id,
                    facts.principal.project_id,
                    thread_id,
                    run_id,
                    graph_id,
                    str(UUID(str(metadata.get("evaluation_attempt_id") or run_id))),
                    json.dumps(
                        {
                            "runtime": STARTUP_MANIFEST,
                            "platform": metadata.get("platform_build"),
                            "configuration": runtime_config_snapshot(resolved),
                            **(
                                {
                                    "evaluation_target_hash": metadata[
                                        "evaluation_target"
                                    ]["config_hash"]
                                }
                                if metadata.get("evaluation_target")
                                else {}
                            ),
                            **({"environment": environment} if environment else {}),
                        }
                    ),
                    facts.context_hash,
                    resolved.config_hash,
                ),
            )
    except Exception as exc:
        # Evidence failure blocks evaluation, not business execution; never log credentials.
        logger.warning(
            "evaluation_execution_evidence_unavailable:%s", type(exc).__name__
        )


def read_execution(tenant_id, project_id, thread_id, run_id):
    with connect() as connection:
        row = connection.execute(
            """SELECT run_id,thread_id,graph_id,attempt_id,manifest,context_hash,config_hash,recorded_at
            FROM runtime_evaluation_execution
            WHERE tenant_id=%s AND project_id=%s AND thread_id=%s AND run_id=%s""",
            (tenant_id, project_id, thread_id, run_id),
        ).fetchone()
        if row and row["manifest"].get("environment"):
            current = connection.execute(
                "SELECT metadata FROM threads WHERE thread_id=%s", (thread_id,)
            ).fetchone()
            capture = (
                (current or {}).get("metadata", {}).get("evaluation_material_capture")
            )
            environment = row["manifest"]["environment"]
            if (
                not capture
                or not capture.get("id")
                or capture["id"] != environment.get("capture_id")
            ):
                row["manifest"].pop("environment")
    if row:
        environment = row["manifest"].get("environment")
        if environment:
            from datetime import UTC, datetime

            if datetime.fromisoformat(environment["expires_at"]) <= datetime.now(UTC):
                row["manifest"].pop("environment")
        return {
            **row,
            **{
                key: str(row[key])
                for key in ("run_id", "thread_id", "attempt_id", "recorded_at")
            },
        }
    return None
