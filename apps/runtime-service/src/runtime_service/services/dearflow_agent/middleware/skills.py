"""Checkpointed snapshot references; a resumed node never reads today's skills."""
import asyncio
import fcntl
import hashlib
import json
import re
from typing import Annotated, NotRequired

from deepagents.middleware.skills import SkillsMiddleware, SkillsState
from langchain.agents.middleware.types import PrivateStateAttr

from runtime_service.runtime import RuntimeAuthError, verified_delegation_from_user
from runtime_service.services.dearflow_agent.skill_governance import SkillStorage
from runtime_service.services.dearflow_agent.workspace.backend import prepare_custom_skills, skills_hash


class SnapshotState(SkillsState):
    dear_skill_snapshot: NotRequired[Annotated[dict, PrivateStateAttr]]


class ExecutionSkillsMiddleware(SkillsMiddleware):
    state_schema = SnapshotState

    def __init__(self, workspace, backend, *, custom_enabled):
        super().__init__(backend=backend, sources=["/skills/", "/skills/custom/"] if custom_enabled else ["/skills/"])
        self.workspace = workspace
        self.custom_enabled = custom_enabled

    def _restore(self, ref):
        if self.workspace is None or not isinstance(ref, dict) or not re.fullmatch(r"skills-[0-9a-f]{64}", ref.get("directory", "")):
            raise RuntimeAuthError("runtime.skill.snapshot_missing")
        root = self.workspace.root.parent / ref["directory"]
        # ponytail: hash the bounded snapshot on access; cache only with an immutable storage guarantee.
        if root.is_symlink() or not root.is_dir() or ref["directory"] != "skills-" + str(ref.get("digest")) or skills_hash(root) != ref.get("digest"):
            raise RuntimeAuthError("runtime.skill.snapshot_mismatch")
        self.workspace.skills_root = root
        # Each graph factory constructs its own workspace/backend. Child tools share it.
        self._backend.routes["/skills/"].cwd = root

    def _prepare(self, scope, run_id):
        if not run_id:
            raise RuntimeAuthError("runtime.skill.execution_required")
        self.workspace.prepare()
        directory = self.workspace.root.parent / ".skill-executions"
        directory.mkdir(exist_ok=True)
        key = hashlib.sha256(str(run_id).encode()).hexdigest()
        record = directory / (key + ".json")
        # Persist before the first checkpoint, so retrying that node cannot refresh content.
        with (directory / (key + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if record.exists():
                ref = json.loads(record.read_text())
            else:
                docs = SkillStorage().documents(scope, enabled_only=True) if self.custom_enabled else []
                prepare_custom_skills(self.workspace, docs)
                ref = {"directory": self.workspace.skills_root.name, "digest": skills_hash(self.workspace.skills_root)}
                staged = record.with_suffix(".tmp")
                staged.write_text(json.dumps(ref))
                staged.replace(record)
            self._restore(ref)
            return ref

    async def abefore_agent(self, state, runtime, config):
        if self.workspace is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        facts = verified_delegation_from_user(runtime.server_info.user)
        if (facts.principal.tenant_id, facts.principal.project_id, runtime.execution_info.thread_id) != self.workspace.scope:
            raise RuntimeAuthError("runtime.workspace.scope_mismatch")
        ref = await asyncio.to_thread(self._prepare,
            (facts.principal.tenant_id, facts.principal.project_id, facts.principal.user_id), runtime.execution_info.task_id)
        # DeepAgents caches metadata for a thread; a fresh execution must reload it.
        clean = {k: v for k, v in state.items() if k not in {"skills_metadata", "skills_load_errors"}}
        update = await super().abefore_agent(clean, runtime, config)
        return {"skills_load_errors": [], **(update or {}), "dear_skill_snapshot": ref}

    async def awrap_model_call(self, request, handler):
        await asyncio.to_thread(self._restore, request.state.get("dear_skill_snapshot"))
        return await super().awrap_model_call(request, handler)

    async def awrap_tool_call(self, request, handler):
        await asyncio.to_thread(self._restore, request.runtime.state.get("dear_skill_snapshot"))
        return await handler(request)
