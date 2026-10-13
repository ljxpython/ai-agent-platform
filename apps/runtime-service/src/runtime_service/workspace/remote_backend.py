"""DeepAgents contract over a bound remote workspace, with typed results."""

import asyncio
import os
from importlib.resources import files

from deepagents.backends.protocol import (
    BackendProtocol,
    DeleteResult,
    EditResult,
    FileDownloadResponse,
    FileUploadResponse,
    GlobResult,
    GrepResult,
    LsResult,
    ReadResult,
    SandboxBackendProtocol,
    WriteResult,
)

from runtime_service.workspace.execution import execute_in_workspace
from runtime_service.workspace.target import RemoteSkills


class RemoteWorkspaceBackend(SandboxBackendProtocol):
    def __init__(self, root):
        self.root = root
        self.scope = root.scope
        self.skills_root = None

    @property
    def id(self):
        return "remote-" + self.root.workspace_id

    def prepare(self):
        examples = {}
        if self.root.graph == "showcase_demo":
            examples = {
                p.name: p.read_bytes()
                for p in files("runtime_service.services.demo.showcase_demo")
                .joinpath("examples")
                .iterdir()
                if p.is_file()
            }
        return self.root.call("prepare", examples=examples)

    def is_prepared(self):
        return self.root.call("is_prepared")["prepared"]

    def ls(self, path):
        return LsResult(**self.root.call("ls", path=path))

    def read(self, file_path, offset=0, limit=2000):
        return ReadResult(
            **self.root.call("read", path=file_path, offset=offset, limit=limit)
        )

    def read_raw(self, file_path):
        return self.root.call("read_raw", path=file_path)

    def write(self, file_path, content):
        return WriteResult(**self.root.call("write", path=file_path, content=content))

    def edit(self, file_path, old_string, new_string, replace_all=False):
        return EditResult(
            **self.root.call(
                "edit",
                path=file_path,
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
            )
        )

    def delete(self, file_path):
        return DeleteResult(**self.root.call("delete", path=file_path))

    def glob(self, pattern, path=None):
        return GlobResult(**self.root.call("glob", pattern=pattern, path=path))

    def grep(self, pattern, path=None, glob=None, *, max_count=None):
        return GrepResult(
            **self.root.call(
                "grep", pattern=pattern, path=path, glob=glob, max_count=max_count
            )
        )

    def upload_files(self, files):
        return [
            FileUploadResponse(**item)
            for item in self.root.call("upload_files", files=files)
        ]

    def download_files(self, paths):
        return [
            FileDownloadResponse(**item)
            for item in self.root.call("download_files", paths=paths)
        ]

    def execute(self, command, *, timeout=None):
        return asyncio.run(self.aexecute(command, timeout=timeout))

    async def aexecute(self, command, *, timeout=None):
        dear = self.root.graph == "dearflow_agent"
        return await execute_in_workspace(
            self.root,
            command,
            timeout=timeout,
            protected=dear,
            skills=self.skills_root,
            image=os.getenv("RUNTIME_WORKSPACE_IMAGE", "runtime-agent-workspace:p5")
            if dear
            else os.getenv("RUNTIME_SHOWCASE_IMAGE", "python:3.13-slim"),
        )

    def publish_skills(self, documents, *, run_id=None):
        package = (
            "runtime_service.services.dearflow_agent"
            if self.root.graph == "dearflow_agent"
            else "runtime_service.services.demo.showcase_demo"
        )
        public = files(package).joinpath("skills")
        contents = {
            p.relative_to(public).as_posix(): p.read_bytes()
            for p in public.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
        result = self.root.call(
            "publish_skills", files=contents, documents=documents, run_id=run_id
        )
        self.skills_root = RemoteSkills(self.root, result["digest"])
        return result

    def restore_skills(self, ref):
        result = self.root.call("restore_skills", ref=ref)
        self.skills_root = RemoteSkills(self.root, result["digest"])


class RemoteSkillsBackend(BackendProtocol):
    def __init__(self, workspace):
        self.workspace = workspace

    def _read(self, operation, **arguments):
        snapshot = self.workspace.skills_root
        if snapshot is None:
            self.workspace.prepare()
            self.workspace.publish_skills([])
            snapshot = self.workspace.skills_root
        return self.workspace.root.call(operation, skills=snapshot.digest, **arguments)

    def ls(self, path):
        return LsResult(**self._read("ls", path=path))

    def read(self, file_path, offset=0, limit=2000):
        return ReadResult(
            **self._read("read", path=file_path, offset=offset, limit=limit)
        )

    def read_raw(self, file_path):
        return self._read("read_raw", path=file_path)

    def glob(self, pattern, path=None):
        return GlobResult(**self._read("glob", pattern=pattern, path=path))

    def grep(self, pattern, path=None, glob=None, *, max_count=None):
        return GrepResult(
            **self._read(
                "grep", pattern=pattern, path=path, glob=glob, max_count=max_count
            )
        )

    def download_files(self, paths):
        return [
            FileDownloadResponse(**item)
            for item in self._read("download_files", paths=paths)
        ]

    def write(self, file_path, content):
        return WriteResult(error="skill_resource_read_only")

    def edit(self, file_path, old_string, new_string, replace_all=False):
        return EditResult(error="skill_resource_read_only")

    def delete(self, file_path):
        return DeleteResult(error="skill_resource_read_only")

    def upload_files(self, files):
        return [
            FileUploadResponse(path=path, error="permission_denied")
            for path, _ in files
        ]
