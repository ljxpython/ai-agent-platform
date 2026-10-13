"""Versioned internal DTOs reject client-selected hosts, mounts and Docker options."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runtime_service.workspace.scoped import thread_scope_hash

READ_OPERATIONS = frozenset(
    {
        "is_prepared",
        "ls",
        "read",
        "read_raw",
        "glob",
        "grep",
        "download_files",
        "image.read",
        "image.read_asset",
        "document.read",
        "artifact.read",
        "artifact.list",
        "browser.list",
        "browser.read",
        "browser.preview",
        "browser.archive",
        "operation",
        "discover",
        "terminal.list",
        "terminal.read",
        "terminal.describe",
        "background.inspect",
        "background.output",
        "background.receipt",
        "cleanup.report",
        "restore_skills",
    }
)

# Only these fields can cross the control boundary; no Docker options or host paths.
ARGUMENTS = {
    "prepare": (set(), {"examples"}),
    "is_prepared": (set(), set()),
    "ls": ({"path"}, {"path", "skills"}),
    "read": ({"path"}, {"path", "offset", "limit", "skills"}),
    "read_raw": ({"path"}, {"path", "skills"}),
    "glob": ({"pattern"}, {"pattern", "path", "skills"}),
    "grep": ({"pattern"}, {"pattern", "path", "glob", "max_count", "skills"}),
    "write": ({"path", "content"}, {"path", "content"}),
    "edit": (
        {"path", "old_string", "new_string"},
        {"path", "old_string", "new_string", "replace_all"},
    ),
    "delete": ({"path"}, {"path"}),
    "upload_files": ({"files"}, {"files"}),
    "download_files": ({"paths"}, {"paths", "skills"}),
    "publish_skills": ({"files", "documents"}, {"files", "documents", "run_id"}),
    "restore_skills": ({"ref"}, {"ref"}),
    "image.read": ({"path"}, {"path"}),
    "image.read_asset": ({"path"}, {"path"}),
    "image.put_upload": ({"data", "sha256"}, {"data", "sha256"}),
    "image.save_asset": ({"data", "folder"}, {"data", "folder"}),
    "document.put": ({"data", "digest", "mime"}, {"data", "digest", "mime", "name"}),
    "document.read": ({"path"}, {"path"}),
    "artifact.publish": ({"path"}, {"path"}),
    "artifact.read": ({"path"}, {"path"}),
    "artifact.list": (set(), {"cursor", "limit"}),
    "browser.list": ({"path"}, {"path", "cursor", "limit", "artifacts_only"}),
    "browser.read": ({"path"}, {"path"}),
    "browser.preview": ({"path"}, {"path"}),
    "browser.archive": (set(), set()),
    "fork": ({"source_scope"}, {"source_scope"}),
    "research_evidence": (
        {"records", "tool_call_id", "thread_id", "run_id", "namespace"},
        {"records", "tool_call_id", "thread_id", "run_id", "namespace"},
    ),
    "execute": (
        {"command", "image"},
        {"command", "image", "timeout", "skills", "protected"},
    ),
    "cancel": ({"resource_id"}, {"resource_id"}),
    "operation": ({"resource_id"}, {"resource_id"}),
    "discover": (set(), set()),
    "terminal.create": (
        {"owner", "request_id", "rows", "cols"},
        {"owner", "request_id", "rows", "cols", "skills", "image"},
    ),
    "terminal.list": ({"owner"}, {"owner"}),
    "terminal.describe": ({"owner", "terminal_id"}, {"owner", "terminal_id"}),
    "terminal.close": ({"owner", "terminal_id"}, {"owner", "terminal_id"}),
    "terminal.read": (
        {"owner", "terminal_id", "offset"},
        {"owner", "terminal_id", "offset"},
    ),
    "terminal.write": (
        {"owner", "terminal_id", "data", "sequence"},
        {"owner", "terminal_id", "data", "sequence"},
    ),
    "terminal.resize": (
        {"owner", "terminal_id", "rows", "cols"},
        {"owner", "terminal_id", "rows", "cols"},
    ),
    "background.create": (
        {"resource_id", "command", "image", "timeout", "runner_secret"},
        {"resource_id", "command", "image", "timeout", "runner_secret", "skills"},
    ),
    "background.remove": (
        {"resource_id", "acknowledged"},
        {"resource_id", "acknowledged"},
    ),
    "cleanup.mark": ({"evidence"}, {"evidence"}),
    "cleanup.report": (set(), set()),
    "cleanup.apply": ({"candidate_token"}, {"candidate_token"}),
}
for _action in ("start", "stop", "inspect", "output", "receipt"):
    ARGUMENTS["background." + _action] = ({"resource_id"}, {"resource_id"})


def validate_arguments(request):
    import re

    from runtime_service.workspace.documents import DocumentError

    args = request.arguments
    required, allowed = ARGUMENTS.get(request.operation, (None, None))
    if required is None or not required <= args.keys() or args.keys() - allowed:
        raise DocumentError("sandbox_request_invalid")
    for key in (
        "path",
        "command",
        "image",
        "owner",
        "request_id",
        "terminal_id",
        "resource_id",
        "content",
        "old_string",
        "new_string",
    ):
        if key in args and not isinstance(args[key], str):
            raise DocumentError("sandbox_request_invalid")
    if "resource_id" in args and not re.fullmatch(r"[0-9a-f]{32}", args["resource_id"]):
        raise DocumentError("sandbox_request_invalid")
    if (
        request.operation == "background.create"
        and args["resource_id"] != request.operation_id
    ):
        raise DocumentError("sandbox_request_invalid")
    for key in ("offset", "sequence", "limit", "max_count", "rows", "cols"):
        if (
            key in args
            and args[key] is not None
            and (type(args[key]) is not int or args[key] < 0)
        ):
            raise DocumentError("sandbox_request_invalid")
    for key in ("rows", "cols"):
        if key in args and not 2 <= args[key] <= 500:
            raise DocumentError("sandbox_request_invalid")
    if "owner" in args and not 0 < len(args["owner"]) <= 256:
        raise DocumentError("sandbox_request_invalid")
    for key in ("replace_all", "protected", "artifacts_only", "acknowledged"):
        if key in args and type(args[key]) is not bool:
            raise DocumentError("sandbox_request_invalid")
    for key in (
        "path",
        "pattern",
        "glob",
        "cursor",
        "request_id",
        "terminal_id",
        "run_id",
        "namespace",
    ):
        if (
            key in args
            and args[key] is not None
            and (
                not isinstance(args[key], str)
                or len(args[key]) > 4096
                or "\0" in args[key]
            )
        ):
            raise DocumentError("sandbox_request_invalid")
    if (
        "skills" in args
        and args["skills"] is not None
        and not (
            isinstance(args["skills"], str)
            and re.fullmatch(r"[0-9a-f]{64}", args["skills"])
        )
    ):
        raise DocumentError("sandbox_request_invalid")
    if "timeout" in args and (
        type(args["timeout"]) is not int
        or not 1 <= args["timeout"] <= (60 if request.operation == "execute" else 3600)
    ):
        raise DocumentError("sandbox_request_invalid")
    for key in ("data",):
        if key in args and not (
            isinstance(args[key], dict)
            and set(args[key]) == {"$bytes"}
            and isinstance(args[key]["$bytes"], str)
        ):
            raise DocumentError("sandbox_request_invalid")
    if request.operation == "terminal.write" and len(args["data"]["$bytes"]) > 90000:
        raise DocumentError("sandbox_request_too_large", 413)
    if "paths" in args and not (
        isinstance(args["paths"], list)
        and len(args["paths"]) <= 64
        and all(isinstance(path, str) and len(path) <= 4096 for path in args["paths"])
    ):
        raise DocumentError("sandbox_request_invalid")
    if request.operation == "upload_files" and not (
        isinstance(args["files"], list)
        and len(args["files"]) <= 64
        and all(
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], dict)
            and set(item[1]) == {"$bytes"}
            and isinstance(item[1]["$bytes"], str)
            for item in args["files"]
        )
    ):
        raise DocumentError("sandbox_request_invalid")
    for key in ("examples", "files", "ref", "evidence"):
        if (
            key in args
            and request.operation != "upload_files"
            and not isinstance(args[key], dict)
        ):
            raise DocumentError("sandbox_request_invalid")
    if "runner_secret" in args and not (
        isinstance(args["runner_secret"], str)
        and re.fullmatch(r"[a-zA-Z0-9_-]{32,256}", args["runner_secret"])
    ):
        raise DocumentError("sandbox_request_invalid")
    if "documents" in args and not isinstance(args["documents"], list):
        raise DocumentError("sandbox_request_invalid")
    if "records" in args and not (
        isinstance(args["records"], list)
        and len(args["records"]) <= 100
        and all(
            isinstance(record, dict) and isinstance(record.get("content"), str)
            for record in args["records"]
        )
    ):
        raise DocumentError("sandbox_request_invalid")


class Rpc(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1]
    node_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
    execution_host: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
    scope: list[str] = Field(min_length=3, max_length=3)
    graph: Literal["dearflow_agent", "showcase_demo"]
    workspace_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    operation: str = Field(max_length=64)
    arguments: dict

    @field_validator("scope")
    @classmethod
    def scope_valid(cls, value):
        if any(
            not item or len(item) > 256 or any(ord(c) < 32 for c in item)
            for item in value
        ):
            raise ValueError("invalid scope")
        return value

    @model_validator(mode="after")
    def scope_hash(self):
        if thread_scope_hash(*self.scope) != self.workspace_id:
            raise ValueError("invalid workspace identity")
        return self
