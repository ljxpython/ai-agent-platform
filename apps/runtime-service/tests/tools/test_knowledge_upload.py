"""Trusted byte transport, private grants and safe MCP receipts."""

import asyncio
import hashlib
import hmac
import json
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import CallToolResult, TextContent

from runtime_service.runtime import RuntimePrincipal
from runtime_service.runtime.mcp_config import configured_mcp_names
from runtime_service.runtime.resource_bindings import (
    resolve_resource_binding,
    thread_resource_metadata,
)
from runtime_service.tools import knowledge_upload as upload
from runtime_service.tools.knowledge_jobs import (
    JOB_TOOL,
    SUBMIT_TOOL,
    project_job_result,
)
from runtime_service.workspace.attachment_receipts import AttachmentReceipts
from runtime_service.workspace.documents import DocumentWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace


def receipt(**changes):
    return {
        "version": 1,
        "job_id": "kj_" + "1" * 32,
        "document_id": "kd_" + "2" * 32,
        "file_name": "项目规范.md",
        "status": "queued",
        "searchable": False,
        "error_code": None,
        "reused": False,
        "created_at": "2026-10-12T00:00:00Z",
        "updated_at": "2026-10-12T00:00:00Z",
        **changes,
    }


def result(payload=None):
    payload = payload or receipt()
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structuredContent=payload,
        _meta={"secret": "SECRET"},
    )


@pytest.fixture
def case(monkeypatch, tmp_path):
    from services.dearflow_agent.test_agent import config

    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_KEY_ID", "knowledge-v1")
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_SECRET", "synthetic-knowledge-secret-" * 2)
    monkeypatch.setenv(
        "PLATFORM_KNOWLEDGE_AUTHORIZATION_URL",
        "http://platform.invalid/api/runtime/internal/knowledge/authorize",
    )
    monkeypatch.setenv(
        "PLATFORM_THREAD_AUTHORIZATION_URL",
        "http://platform.invalid/api/runtime/internal/thread-authorization",
    )
    monkeypatch.setenv(
        "PLATFORM_RUNTIME_DELEGATION_SECRET", "synthetic-delegation-secret-" * 2
    )
    tenant, project, thread, run, user = (
        "__default",
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
    )
    principal = RuntimePrincipal(user, tenant, project, "developer", ())
    cfg = config()
    cfg["configurable"]["thread_id"] = thread
    cfg["metadata"]["run_id"] = run
    identity = cfg["configurable"]["langgraph_auth_user"]
    identity["runtime_principal"].update(
        user_id=user, tenant_id=tenant, project_id=project
    )
    identity["runtime_scope"].update(
        tenant_id=tenant, project_id=project, thread_id=thread
    )
    cfg["metadata"]["__graphharbor_thread_metadata"] = thread_resource_metadata(
        kind="mcp",
        provider="mcp_http",
        resource_id="fixture",
        principal=principal,
        thread_id=thread,
    )
    binding = resolve_resource_binding(cfg, principal, "mcp")
    runtime = SimpleNamespace(
        config=cfg,
        context={},
        state={},
        tool_call_id="call-1",
        execution_info=SimpleNamespace(thread_id=thread, run_id=run),
        server_info=SimpleNamespace(user=identity),
    )
    root = resolve_thread_workspace(tenant, project, thread, "dearflow_agent")
    data = "知识上传联调资料。".encode()
    ref = DocumentWorkspace(root).put(
        data, hashlib.sha256(data).hexdigest(), "text/markdown", "项目规范.md"
    )
    AttachmentReceipts(root).record(ref)
    return SimpleNamespace(
        runtime=runtime,
        binding=binding,
        cfg=cfg,
        root=root,
        data=data,
        ref=ref,
        requests=[],
    )


def transport(
    case,
    monkeypatch,
    *,
    recover=None,
    recovery_body=None,
    corrupt_grant=False,
    revoke_after=0,
):
    native_client = httpx.AsyncClient

    def respond(request):
        case.requests.append(request)
        if request.url.path.endswith("/authorize"):
            if revoke_after and len(case.requests) > revoke_after:
                return httpx.Response(
                    403, json={"error": {"code": "knowledge_upload_denied"}}
                )
            envelope = json.loads(request.content)
            signed = envelope["values"]
            secret = "synthetic-knowledge-secret-" * 2
            assert (
                envelope["signature"]
                == hmac.new(
                    secret.encode(),
                    (
                        "knowledge-operation-request\n" + upload.canonical(signed)
                    ).encode(),
                    hashlib.sha256,
                ).hexdigest()
            )
            assert signed["credential_id"] == ""
            values = {
                **signed,
                "issuer": "platform-api",
                "audience": "rag-knowledge",
                "knowledge_base_id": "kb_" + "3" * 32,
            }
            envelope = {
                "version": 1,
                "key_id": "knowledge-v1",
                "values": values,
                "signature": hmac.new(
                    secret.encode(),
                    ("knowledge-operation-grant\n" + upload.canonical(values)).encode(),
                    hashlib.sha256,
                ).hexdigest(),
            }
            if corrupt_grant:
                values["project_id"] = str(uuid4())
            return httpx.Response(200, json=envelope)
        if request.url.path.endswith("thread-authorization"):
            return httpx.Response(
                200, json={"allowed_thread_ids": [case.binding.thread_id]}
            )
        if request.method == "PUT":
            assert request.content == case.data
            assert request.headers["authorization"] == "Bearer SYNTHETIC_PRIVATE_TOKEN"
            assert (
                json.loads(request.headers["x-knowledge-file-ref"])["sha256"]
                == case.ref["sha256"]
            )
            assert (
                json.loads(request.headers["x-knowledge-operation-grant"])["values"][
                    "operation"
                ]
                == "upload"
            )
            return httpx.Response(
                200, json={"upload_id": "ku_" + "4" * 32, "token": "SECRET"}
            )
        if request.method == "GET":
            return httpx.Response(
                200,
                json=recovery_body
                if recovery_body is not None
                else {
                    "request_id": request.url.path.rsplit("/", 1)[-1],
                    "receipt": recover,
                },
            )
        raise AssertionError(request.url)

    monkeypatch.setattr(
        upload.httpx,
        "AsyncClient",
        lambda **kwargs: native_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )


def invoke(case, handler, *, name=SUBMIT_TOOL, args=None):
    connection = {
        "url": "http://provider.invalid/mcp",
        "headers": {"Authorization": "Bearer SYNTHETIC_PRIVATE_TOKEN"},
    }
    request = MCPToolCallRequest(
        name=name,
        args=args or {"file_ref": case.ref},
        server_name="bound",
        runtime=case.runtime,
    )
    return asyncio.run(
        upload.knowledge_upload_interceptor(case.binding, connection)(request, handler)
    )


def test_upload_returns_queued_and_private_headers_never_escape(case, monkeypatch):
    transport(case, monkeypatch)
    handler = AsyncMock(
        return_value=result(
            {**receipt(), "raw_data": "SECRET /PRIVATE", "upload_id": "PRIVATE"}
        )
    )
    response = invoke(case, handler)
    assert not response.isError
    assert response.structuredContent["status"] == "queued"
    assert response.structuredContent["searchable"] is False
    assert (
        "PRIVATE" not in response.model_dump_json()
        and "SECRET" not in response.model_dump_json()
    )
    sent = handler.call_args.args[0]
    assert sent.args == {"file_ref": case.ref}
    assert sent.headers["X-Knowledge-Upload-ID"] == "ku_" + "4" * 32
    assert sent.headers["X-Knowledge-Operation-Grant"]
    assert [r.method for r in case.requests] == ["POST", "PUT", "POST"]


@pytest.mark.parametrize("ack", [True, False])
def test_lost_ack_reads_original_request_and_does_not_resubmit(case, monkeypatch, ack):
    transport(case, monkeypatch, recover=receipt() if ack else None)
    handler = AsyncMock(side_effect=httpx.ReadTimeout("SECRET /PRIVATE"))
    response = invoke(case, handler)
    assert not response.isError if ack else response.isError
    if not ack:
        assert (
            json.loads(response.content[0].text)["code"]
            == "knowledge_submission_unconfirmed"
        )
    handler.assert_awaited_once()
    put, get = [r for r in case.requests if r.method in {"PUT", "GET"}]
    assert put.url == get.url


@pytest.mark.parametrize("body", [[], "SECRET /PRIVATE"])
def test_malformed_recovery_is_unconfirmed_without_resubmitting(
    case, monkeypatch, body
):
    transport(case, monkeypatch, recovery_body=body)
    handler = AsyncMock(side_effect=httpx.ReadTimeout("SECRET /PRIVATE"))
    response = invoke(case, handler)
    assert response.isError
    assert json.loads(response.content[0].text) == {
        "code": "knowledge_submission_unconfirmed"
    }
    handler.assert_awaited_once()
    assert len([r for r in case.requests if r.method == "GET"]) == 1


def test_cancellation_propagates(case, monkeypatch):
    transport(case, monkeypatch)
    with pytest.raises(asyncio.CancelledError):
        invoke(case, AsyncMock(side_effect=asyncio.CancelledError()))


@pytest.mark.parametrize(
    "kind", ["path", "size", "mime", "hash", "extra", "foreign", "modified", "symlink"]
)
def test_file_forgery_and_cross_thread_access_are_rejected(case, monkeypatch, kind):
    ref = dict(case.ref)
    if kind == "path":
        ref["path"] = "/workspace/uploads/../private.md"
    elif kind == "size":
        ref["size_bytes"] += 1
    elif kind == "mime":
        ref["mime_type"] = "application/pdf"
    elif kind == "hash":
        ref["sha256"] = "0" * 64
    elif kind == "extra":
        ref["url"] = "http://evil.invalid"
    elif kind in {"foreign", "symlink"}:
        source = case.root / "uploads" / ref["path"].rsplit("/", 1)[-1]
        other = case.root.parent / "other.md"
        source.rename(other)
        if kind == "symlink":
            source.symlink_to(other)
    else:
        (case.root / "uploads" / ref["path"].rsplit("/", 1)[-1]).write_bytes(
            b"modified"
        )
    transport(case, monkeypatch)
    handler = AsyncMock()
    response = invoke(case, handler, args={"file_ref": ref})
    assert (
        response.isError
        and json.loads(response.content[0].text)["code"] == "knowledge_invalid_file_ref"
    )
    handler.assert_not_awaited()
    assert case.requests == []


def test_legacy_alias_is_replaced_and_fork_receipts_keep_trusted_names(case):
    legacy = DocumentWorkspace(case.root).put(
        b"legacy", hashlib.sha256(b"legacy").hexdigest(), "text/plain", "legacy.txt"
    )
    values = upload._identity(case.runtime, case.binding, SUBMIT_TOOL)
    raw, safe = upload._file(values, {**legacy, "file_name": "forged-alias.txt"})
    assert raw == b"legacy" and safe["file_name"] == legacy["path"].rsplit("/", 1)[-1]
    target = case.root.parent / "forked"
    shutil.copytree(case.root, target)
    AttachmentReceipts(case.root).copy_to(target)
    assert AttachmentReceipts(target).require(case.ref)


@pytest.mark.parametrize(
    "mode", ["disabled", "plan", "offload", "child", "deny", "thread", "run", "unbound"]
)
def test_execution_boundary_denies_before_transport(case, monkeypatch, mode):
    if mode == "disabled":
        monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "0")
    elif mode in {"plan", "offload"}:
        case.runtime.context = (
            {"plan_mode": True, "plan_execution_id": "fixture"}
            if mode == "plan"
            else {"offload_conversation": True}
        )
    elif mode == "child":
        case.cfg["configurable"]["checkpoint_ns"] = "child:one"
    elif mode == "deny":
        case.runtime.server_info.user["runtime_policy"]["tool_overrides"] = {
            SUBMIT_TOOL: False
        }
    elif mode == "thread":
        case.runtime.execution_info.thread_id = str(uuid4())
    elif mode == "run":
        case.cfg["metadata"]["run_id"] = str(uuid4())
    else:
        case.runtime.server_info = None
    handler = AsyncMock()
    response = invoke(case, handler)
    assert response.isError
    handler.assert_not_awaited()
    assert case.requests == []


def test_job_read_rechecks_current_project_and_thread_permission(case, monkeypatch):
    transport(case, monkeypatch)
    handler = AsyncMock(return_value=result(receipt()))
    response = invoke(case, handler, name=JOB_TOOL, args={"job_id": "kj_" + "1" * 32})
    assert not response.isError and "reused" not in response.structuredContent
    assert len(case.requests) == 2
    assert all(
        json.loads(r.content)["values"]["operation"] == "read" for r in case.requests
    )


@pytest.mark.parametrize("operation", ["upload", "read"])
def test_permission_revoked_during_io_prevents_submission_or_read_result(
    case, monkeypatch, operation
):
    transport(case, monkeypatch, revoke_after=1)
    handler = AsyncMock(return_value=result(receipt()))
    response = invoke(
        case,
        handler,
        name=SUBMIT_TOOL if operation == "upload" else JOB_TOOL,
        args={"file_ref": case.ref}
        if operation == "upload"
        else {"job_id": "kj_" + "1" * 32},
    )
    assert response.isError
    if operation == "upload":
        handler.assert_not_awaited()
    else:
        handler.assert_awaited_once()


def test_legacy_receipts_with_no_private_directory_are_compatible(case):
    root = case.root.parent / "older-thread"
    ref = DocumentWorkspace(root).put(
        b"legacy", hashlib.sha256(b"legacy").hexdigest(), "text/plain", "legacy.txt"
    )
    assert AttachmentReceipts(root).require(ref) is False
    AttachmentReceipts(root).io.root.mkdir(parents=True)
    assert AttachmentReceipts(root).require(ref) is False


def test_tampered_platform_grant_never_transfers_bytes(case, monkeypatch):
    transport(case, monkeypatch, corrupt_grant=True)
    response = invoke(case, AsyncMock())
    assert response.isError
    assert [r.method for r in case.requests] == ["POST"]


@pytest.mark.parametrize(
    "kind",
    ["filename", "oversized", "wrong_job", "private_error", "structured_mismatch"],
)
def test_untrusted_provider_receipts_are_bounded(kind):
    payload = receipt()
    if kind == "filename":
        payload["file_name"] = "/PRIVATE"
    elif kind == "private_error":
        payload.update(status="failed", error_code="SECRET")
    elif kind == "wrong_job":
        payload["job_id"] = "kj_" + "9" * 32
    elif kind == "oversized":
        payload["raw_data"] = "x" * 65537
    unsafe = result(payload)
    if kind == "structured_mismatch":
        unsafe.structuredContent = {"SECRET": True}
    safe = project_job_result(unsafe, job_id="kj_" + "1" * 32)
    assert (
        safe.isError
        and "SECRET" not in safe.model_dump_json()
        and "PRIVATE" not in safe.model_dump_json()
    )


def test_disabled_submit_is_omitted_from_defaults_and_catalog(monkeypatch):
    monkeypatch.setenv(
        "RUNTIME_MCP_CONNECTIONS_JSON",
        json.dumps(
            {
                "fixture": {
                    "scope": {"tenant_id": "tenant", "project_id": "project"},
                    "allowed_tools": [SUBMIT_TOOL, JOB_TOOL],
                }
            }
        ),
    )
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "0")
    assert configured_mcp_names() == (JOB_TOOL,)
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "1")
    assert set(configured_mcp_names()) == {JOB_TOOL, SUBMIT_TOOL}


@pytest.mark.parametrize(
    "mode",
    [
        "unknown_mutation",
        "read_only_submit",
        "missing_idempotency",
        "extra_args",
        "invalid_property",
    ],
)
def test_loader_rejects_mutations_and_unsafe_upload_declarations(
    case, monkeypatch, mode
):
    from runtime_service.runtime.errors import RuntimeResolutionError
    from runtime_service.tools import mcp

    name = "mcp_delete_documents" if mode == "unknown_mutation" else SUBMIT_TOOL
    annotations = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    schema = {
        "type": "object",
        "required": ["file_ref"],
        "properties": {"file_ref": {"type": "object"}},
    }
    if mode == "read_only_submit":
        annotations["readOnlyHint"] = True
    elif mode == "missing_idempotency":
        annotations.pop("idempotentHint")
    elif mode == "extra_args":
        schema["properties"]["project_id"] = {"type": "string"}
    elif mode == "invalid_property":
        schema["properties"]["file_ref"] = "invalid"
    tool = SimpleNamespace(
        name=name, args_schema=schema, metadata=annotations, handle_tool_error=False
    )
    monkeypatch.setattr(
        mcp,
        "MultiServerMCPClient",
        lambda *a, **kw: SimpleNamespace(get_tools=AsyncMock(return_value=[tool])),
    )
    monkeypatch.setenv(
        "RUNTIME_MCP_CONNECTIONS_JSON",
        json.dumps(
            {
                "fixture": {
                    "scope": {
                        "tenant_id": case.binding.tenant_id,
                        "project_id": case.binding.project_id,
                    },
                    "transport": "streamable_http",
                    "url": "http://provider.invalid/mcp",
                    "allowed_tools": [name],
                }
            }
        ),
    )
    principal = RuntimePrincipal(
        case.runtime.server_info.user["runtime_principal"]["user_id"],
        case.binding.tenant_id,
        case.binding.project_id,
        "developer",
        (),
    )
    with pytest.raises(RuntimeResolutionError):
        asyncio.run(mcp.load_mcp_tools(case.cfg, principal, (name,), ()))


def test_receipt_symlink_is_rejected_without_reading_target(case):
    io = AttachmentReceipts(case.root)
    name = hashlib.sha256(io._encoded(case.ref)).hexdigest() + ".json"
    path = io.io.root / "refs" / name
    target = path.with_suffix(".private")
    path.rename(target)
    path.symlink_to(target)
    from langchain_core.tools import ToolException

    with pytest.raises(ToolException, match="knowledge_invalid_file_ref"):
        io.require(case.ref)


@pytest.mark.parametrize("searchable", [True, False])
def test_migrated_no_job_receipt_keeps_current_searchability(searchable):
    payload = receipt(job_id=None, status="ready", reused=True, searchable=searchable)
    response = project_job_result(result(payload), submit=True)
    assert (
        not response.isError and response.structuredContent["searchable"] is searchable
    )
    assert project_job_result(result(payload)).isError


@pytest.mark.parametrize("namespace", ["", "tools:trusted-task"])
def test_real_root_toolnode_namespace_is_allowed(case, monkeypatch, namespace):
    case.runtime.execution_info.task_id = "trusted-task"
    case.runtime.execution_info.checkpoint_ns = namespace
    case.cfg["configurable"]["checkpoint_ns"] = namespace
    transport(case, monkeypatch)
    response = invoke(case, AsyncMock(return_value=result(receipt())))
    assert not response.isError


@pytest.mark.parametrize(
    "namespace,execution,task",
    [
        ("tools:forged-task", "tools:forged-task", "trusted-task"),
        (
            "child:parent|tools:trusted-task",
            "child:parent|tools:trusted-task",
            "trusted-task",
        ),
        ("tools:trusted-task", "", "trusted-task"),
        ("", "child:parent", "trusted-task"),
        ("tools:None", "tools:None", None),
    ],
)
def test_namespace_forgery_and_child_execution_are_denied(
    case, monkeypatch, namespace, execution, task
):
    case.cfg["configurable"]["checkpoint_ns"] = namespace
    case.runtime.execution_info.checkpoint_ns = execution
    case.runtime.execution_info.task_id = task
    handler = AsyncMock()
    response = invoke(case, handler)
    assert response.isError
    handler.assert_not_awaited()
    assert case.requests == []


def image_case(case, *, receipt=True, image_format="PNG"):
    import io

    from PIL import Image

    from runtime_service.tools.images import ImageWorkspace

    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(buffer, format=image_format)
    case.data = buffer.getvalue()
    case.ref = ImageWorkspace(case.root).put_upload(
        case.data, hashlib.sha256(case.data).hexdigest()
    )
    if receipt:
        AttachmentReceipts(case.root).record_image(
            case.ref, "项目架构图." + image_format.lower()
        )
    return case


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_uploaded_image_is_converted_only_from_private_receipt(
    case, monkeypatch, image_format
):
    image_case(case, image_format=image_format)
    transport(case, monkeypatch)
    handler = AsyncMock(return_value=result(receipt()))
    response = invoke(case, handler)
    assert not response.isError
    sent = handler.call_args.args[0].args["file_ref"]
    assert sent == {**case.ref, "file_name": "项目架构图." + image_format.lower()}
    assert len(case.ref) == 5
    target = case.root.parent / "image-fork"
    shutil.copytree(case.root, target)
    AttachmentReceipts(case.root).copy_to(target)
    assert AttachmentReceipts(target).require_image(case.ref) == sent


@pytest.mark.parametrize(
    "forgery",
    [
        "missing_receipt",
        "name",
        "size",
        "mime",
        "foreign",
        "modified",
        "symlink",
        "generated",
        "webp",
    ],
)
def test_untrusted_image_never_transfers_bytes(case, monkeypatch, forgery):
    image_case(
        case,
        receipt=forgery != "missing_receipt",
        image_format="WEBP" if forgery == "webp" else "PNG",
    )
    if forgery == "name":
        case.ref["file_name"] = "fake.png"
    elif forgery == "size":
        case.ref["size_bytes"] += 1
    elif forgery == "mime":
        case.ref["mime_type"] = "image/jpeg"
    elif forgery == "generated":
        case.ref["path"] = "/workspace/generated/" + "f" * 32 + ".png"
    elif forgery in {"foreign", "modified", "symlink"}:
        path = case.root / "uploads" / case.ref["path"].rsplit("/", 1)[-1]
        if forgery == "modified":
            path.write_bytes(b"changed")
        else:
            other = case.root.parent / "other.png"
            path.rename(other)
            if forgery == "symlink":
                path.symlink_to(other)
    transport(case, monkeypatch)
    handler = AsyncMock()
    response = invoke(case, handler)
    assert response.isError
    handler.assert_not_awaited()
    assert case.requests == []


def test_image_name_is_first_upload_fact_and_receipt_symlink_denied(case):
    image_case(case)
    receipts = AttachmentReceipts(case.root)
    receipts.record_image(case.ref, "another-name.png")
    assert receipts.require_image(case.ref)["file_name"] == "项目架构图.png"
    path = receipts.io.root / "images" / receipts._image_key(case.ref)
    other = path.with_suffix(".private")
    path.rename(other)
    path.symlink_to(other)
    from langchain_core.tools import ToolException

    with pytest.raises(ToolException, match="knowledge_invalid_file_ref"):
        receipts.require_image(case.ref)


def test_submit_schema_accepts_document_or_image_but_never_filename_on_image():
    from jsonschema import Draft202012Validator

    from runtime_service.tools import mcp

    tool = SimpleNamespace(
        name=SUBMIT_TOOL,
        args_schema={
            "type": "object",
            "required": ["file_ref"],
            "properties": {"file_ref": {"type": "object"}},
        },
    )
    mcp._knowledge_schema(tool)
    validator = Draft202012Validator(tool.args_schema)
    image = {
        "version": 1,
        "path": "/workspace/uploads/" + "a" * 64 + ".png",
        "mime_type": "image/png",
        "size_bytes": 12,
        "sha256": "a" * 64,
    }
    assert validator.is_valid({"file_ref": image})
    assert validator.is_valid(
        {
            "file_ref": {
                **image,
                "path": image["path"].replace(".png", ".md"),
                "mime_type": "text/markdown",
                "file_name": "readme.md",
            }
        }
    )
    assert not validator.is_valid({"file_ref": {**image, "name": "fake.png"}})
    assert not validator.is_valid({"file_ref": {**image, "file_name": "fake.png"}})
    assert not validator.is_valid({"image_ref": image})


def test_read_delegation_never_authorizes_a_submit(case):
    case.runtime.server_info.user["runtime_scope"]["operation"] = "read"
    handler = AsyncMock()
    assert invoke(case, handler).isError
    handler.assert_not_awaited()
    assert case.requests == []
