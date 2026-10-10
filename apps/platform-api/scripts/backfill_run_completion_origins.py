"""Reauthorize enabled native crons and persist a resumable, private rollback manifest."""

import argparse
import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from starlette.requests import Request

from platform_api.config import load_settings
from platform_api.core.context.models import (
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from platform_api.core.db import build_engine, build_session_factory
from platform_api.core.errors import ForbiddenError, NotFoundError, PlatformApiError
from platform_api.modules.identity.actors import (
    load_service_account_actor,
    load_user_actor,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord as Origin,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)
from platform_api.modules.scheduled_tasks.schemas import TaskCreate
from platform_api.modules.scheduled_tasks.service import (
    ScheduledTasksService,
    require_active_project,
)


def save_manifest(path, manifest):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".completion-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(manifest, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def backfill(service, *, actor, project_id, action="dry-run", manifest_path=None):
    if action not in {"dry-run", "apply", "revert"} or (
        action != "dry-run" and manifest_path is None
    ):
        raise ValueError("Invalid backfill action or missing manifest")
    factory = service.gateway._session_factory
    require_active_project(factory, project_id)
    entries = []
    if manifest_path and Path(manifest_path).exists():
        manifest = json.loads(Path(manifest_path).read_text())
        if (
            manifest.get("version") != 1
            or manifest.get("project_id") != project_id
            or manifest.get("tenant_id") != service.tenant_id
            or manifest.get("owner") != service._owner(actor)
        ):
            raise ValueError("Manifest scope mismatch")
    else:
        manifest = {
            "version": 1,
            "project_id": project_id,
            "tenant_id": service.tenant_id,
            "owner": service._owner(actor),
            "entries": {},
        }
    offset = 0
    while True:
        page = await service.list(
            actor=actor, project_id=project_id, enabled=True, limit=100, offset=offset
        )
        entries.extend(page["items"])
        offset += len(page["items"])
        if offset >= page["total"] or not page["items"]:
            break
    report = []
    targets = (
        list(manifest["entries"])
        if action == "revert"
        else [item["id"] for item in entries]
    )
    for task_id in targets:
        try:
            row = await service.get_native(
                actor=actor, project_id=project_id, task_id=task_id, write=True
            )
            if row["thread_id"]:
                await service.gateway._load_thread(
                    actor=actor,
                    project_id=project_id,
                    thread_id=row["thread_id"],
                    write=True,
                    action="comment",
                )
        except (ForbiddenError, NotFoundError):
            report.append({"task_id": task_id, "action": "unavailable"})
            continue
        entry = manifest["entries"].get(task_id)
        with factory() as session:
            existing = session.scalar(
                select(Origin)
                .where(
                    Origin.source_id == task_id,
                    Origin.state == "active",
                    Origin.project_id == project_id,
                    Origin.runtime_id == "default",
                )
                .limit(1)
            )
            has_origin = existing is not None
        if action == "dry-run":
            report.append(
                {
                    "task_id": task_id,
                    "action": "already_bound" if has_origin else "backfill",
                }
            )
            continue
        if action == "apply" and has_origin and entry is None:
            report.append({"task_id": task_id, "action": "already_bound"})
            continue
        if entry is None:
            spec = TaskCreate.model_validate(row["metadata"]["task_spec"])
            origin_ref = await service._reserve_completion_origin(
                actor, project_id, spec
            )
            if not origin_ref:
                raise ValueError("Completion must be enabled before backfill")
            entry = {
                "origin_ref": origin_ref,
                "payload": row["payload"],
                "task_spec": row["metadata"]["task_spec"],
                "state": "prepared",
            }
            manifest["entries"][task_id] = entry
            save_manifest(manifest_path, manifest)
        if row["metadata"]["task_spec"] != entry["task_spec"]:
            raise ValueError(
                "Task changed after manifest creation; review it before continuing"
            )
        if row["payload"] != entry["payload"]:
            raise ValueError("Native task payload changed; review it before continuing")
        if entry["state"] == ("applied" if action == "apply" else "reverted"):
            report.append({"task_id": task_id, "action": entry["state"]})
            continue
        payload = {
            name: value
            for name, value in entry["payload"].items()
            if name
            in {
                "assistant_id",
                "input",
                "command",
                "config",
                "context",
                "multitask_strategy",
                "webhook",
            }
        }
        await asyncio.to_thread(
            service.gateway._assert_runtime_target_allowed,
            project_id=project_id,
            assistant_id=entry["task_spec"]["agent_key"],
        )
        await asyncio.to_thread(
            service.gateway._validate_run_options,
            project_id=project_id,
            payload=payload,
        )
        payload["thread_id"] = row["thread_id"]
        if action == "apply":
            await service._bind_completion_schedule(entry["origin_ref"], task_id)
        upstream = await service._upstream(
            actor=actor,
            project_id=project_id,
            write=True,
            payload=payload,
            thread_id=row["thread_id"],
            origin_ref=entry["origin_ref"] if action == "apply" else None,
        )
        await upstream.cron_request("PATCH", task_id, payload=payload)
        if action == "revert":
            with factory.begin() as session:
                session.get(Origin, entry["origin_ref"]).state = "retired"
        entry["state"] = "applied" if action == "apply" else "reverted"
        save_manifest(manifest_path, manifest)
        report.append({"task_id": task_id, "action": entry["state"]})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["dry-run", "apply", "revert"])
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--tenant-id", default="__default")
    parser.add_argument("--credential-id")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.action != "dry-run" and not args.manifest:
        parser.error("apply/revert require a private manifest path")
    settings = load_settings()
    engine = build_engine(settings.database_url)
    factory = build_session_factory(engine)
    try:
        actor = (
            load_service_account_actor(
                session_factory=factory,
                subject=args.owner_id,
                credential_id=args.credential_id,
                project_id=args.project_id,
            )
            if args.owner_id.startswith("service-account:")
            else load_user_actor(
                session_factory=factory,
                user_id=args.owner_id,
                project_id=args.project_id,
            )
        )
        if actor is None or not actor.project_role_set(args.project_id):
            raise ValueError("Owner is inactive or project access was revoked")
        context = PlatformRequestContext(
            RequestContext(
                str(uuid4()),
                str(uuid4()),
                "POST",
                "/internal/backfill",
                time.monotonic(),
            ),
            TenantContext(args.tenant_id),
            ProjectContext(args.project_id),
            actor,
        )
        request = Request(
            {
                "type": "http",
                "headers": [],
                "app": SimpleNamespace(
                    state=SimpleNamespace(settings=settings, db_session_factory=factory)
                ),
                "state": {"platform_context": context},
            }
        )
        gateway = get_runtime_gateway_service(request, actor)
        service = ScheduledTasksService(
            gateway,
            tenant_id=context.tenant.tenant_id,
            secret=settings.runtime_delegation_secret,
        )
        print(
            json.dumps(
                asyncio.run(
                    backfill(
                        service,
                        actor=actor,
                        project_id=args.project_id,
                        action=args.action,
                        manifest_path=args.manifest,
                    )
                )
            )
        )
    except (PlatformApiError, ValueError) as exc:
        raise SystemExit(
            json.dumps({"error_code": getattr(exc, "code", "backfill_rejected")})
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
