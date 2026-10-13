"""Trusted FileRef staging and exact authorization through official MCP interceptors."""

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from langchain_core.tools import ToolException

from runtime_service.runtime.auth import verified_delegation_from_user
from runtime_service.runtime.mcp_config import (
    knowledge_upload_enabled as upload_enabled,
)
from runtime_service.runtime.planning import read_plan
from runtime_service.runtime.runtime_config import context_from_runtime
from runtime_service.tools.errors import is_transport_error
from runtime_service.tools.images import ImageWorkspace
from runtime_service.tools.knowledge_jobs import (
    JOB_TOOL,
    SUBMIT_TOOL,
    error_result,
    project_job_result,
    receipt_result,
)
from runtime_service.workspace.attachment_receipts import AttachmentReceipts
from runtime_service.workspace.documents import DocumentWorkspace
from runtime_service.workspace.file_refs import validate_file_ref
from runtime_service.workspace.image_refs import ImageRef, validate_uploaded_image_ref
from runtime_service.workspace.scoped import resolve_thread_workspace


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _identity(runtime, binding, name):
    if runtime is None or runtime.server_info is None or runtime.execution_info is None:
        raise ToolException("knowledge_upload_denied")
    facts = verified_delegation_from_user(runtime.server_info.user)
    info = runtime.execution_info
    run_id = str(
        UUID(str(info.run_id or runtime.config.get("metadata", {}).get("run_id")))
    )
    thread_id = str(UUID(str(info.thread_id)))
    context = context_from_runtime(runtime)
    plan = read_plan(runtime.state)
    namespace = runtime.config.get("configurable", {}).get("checkpoint_ns") or ""
    task_id = getattr(info, "task_id", None)
    execution_namespace = getattr(info, "checkpoint_ns", "") or ""
    if (
        facts.scope.operation != "run-create"
        or facts.scope.assistant_id not in {"dearflow_agent", "showcase_demo"}
        or facts.scope.thread_id != thread_id
        or binding.thread_id != thread_id
        or facts.principal.tenant_id != binding.tenant_id
        or facts.principal.project_id != binding.project_id
        or name in facts.policy.denied_tool_names
        or context.plan_mode
        or context.offload_conversation
        or plan is not None
        and plan.active
        or namespace != ""
        and (
            not isinstance(task_id, str)
            or not task_id
            or namespace != f"tools:{task_id}"
        )
        or namespace != execution_namespace
        or runtime.config.get("configurable", {}).get("thread_id") != thread_id
    ):
        raise ToolException("knowledge_upload_denied")
    metadata_id = runtime.config.get("metadata", {}).get("run_id")
    if metadata_id and metadata_id != run_id:
        raise ToolException("knowledge_upload_denied")
    if not runtime.tool_call_id or len(runtime.tool_call_id) > 256:
        raise ToolException("knowledge_upload_denied")
    values = {
        "tenant_id": binding.tenant_id,
        "project_id": binding.project_id,
        "resource_id": binding.resource_id,
        "subject": facts.principal.user_id,
        "principal_type": "service_account" if facts.credential_id else "user",
        "credential_id": facts.credential_id or "",
        "graph_id": facts.scope.assistant_id,
        "thread_id": thread_id,
        "run_id": run_id,
        "tool_call_id": runtime.tool_call_id,
    }
    key = [
        values[k]
        for k in ("tenant_id", "project_id", "thread_id", "run_id", "tool_call_id")
    ]
    values["request_id"] = (
        "kr_" + hashlib.sha256(canonical(key).encode()).hexdigest()[:32]
    )
    return values


async def _json(client, method, url, **kwargs):
    async with asyncio.timeout(30), client.stream(method, url, **kwargs) as response:
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > 65536:
                raise ValueError("knowledge_response_too_large")
        if not response.is_success:
            try:
                code = json.loads(raw)["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = "knowledge_unavailable"
            raise ToolException(code)
        return json.loads(raw)


async def _grant(client, values, *, operation="upload"):
    endpoint = os.getenv("PLATFORM_KNOWLEDGE_AUTHORIZATION_URL", "")
    key_id = os.getenv("RUNTIME_KNOWLEDGE_KEY_ID", "knowledge-v1")
    secret = os.getenv("RUNTIME_KNOWLEDGE_SECRET", "")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path != "/api/runtime/internal/knowledge/authorize"
        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key_id)
        or len(secret.encode()) < 32
        or secret
        in {
            os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET"),
            os.getenv("RUNTIME_COMPLETION_SECRET"),
        }
    ):
        raise ToolException("knowledge_authorization_unavailable")
    now = int(time.time())
    signed = {
        **values,
        "issuer": "runtime-service",
        "audience": "platform-api",
        "operation": operation,
        "iat": now,
        "exp": now + 30,
        "nonce": uuid4().hex,
    }
    envelope = {
        "version": 1,
        "key_id": key_id,
        "values": signed,
        "signature": hmac.new(
            secret.encode(),
            f"knowledge-operation-request\n{canonical(signed)}".encode(),
            hashlib.sha256,
        ).hexdigest(),
    }
    response = await _json(client, "POST", endpoint, json=envelope)
    if not isinstance(response, dict) or set(response) != {
        "version",
        "key_id",
        "values",
        "signature",
    }:
        raise ToolException("knowledge_authorization_unavailable")
    grant_values = response["values"]
    if not isinstance(grant_values, dict):
        raise ToolException("knowledge_authorization_unavailable")
    expected = hmac.new(
        secret.encode(),
        f"knowledge-operation-grant\n{canonical(grant_values)}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if (
        type(response["version"]) is not int
        or response["version"] != 1
        or response["key_id"] != key_id
        or not isinstance(response["signature"], str)
        or not hmac.compare_digest(response["signature"], expected)
        or any(grant_values.get(k) != v for k, v in values.items())
        or grant_values.get("issuer") != "platform-api"
        or grant_values.get("audience") != "rag-knowledge"
        or grant_values.get("operation") != operation
        or not re.fullmatch(
            r"kb_[a-f0-9]{32}", grant_values.get("knowledge_base_id", "")
        )
        or type(grant_values.get("iat")) is not int
        or type(grant_values.get("exp")) is not int
        or not grant_values["iat"]
        <= time.time()
        < grant_values["exp"]
        <= grant_values["iat"] + 30
    ):
        raise ToolException("knowledge_authorization_unavailable")
    encoded = canonical(response)
    if len(encoded.encode()) > 8192:
        raise ToolException("knowledge_authorization_unavailable")
    return encoded


def _file(values, ref):
    root = resolve_thread_workspace(
        values["tenant_id"],
        values["project_id"],
        values["thread_id"],
        values["graph_id"],
    )
    if isinstance(ref, dict) and set(ref) == set(ImageRef.__annotations__):
        ref = validate_uploaded_image_ref(ref)
        if ref["mime_type"] not in {"image/png", "image/jpeg"}:
            raise ToolException("knowledge_unsupported_file_type")
        trusted_ref = AttachmentReceipts(root).require_image(ref)
        try:
            raw, stored = ImageWorkspace(root).read_asset(ref["path"])
        except ToolException as exc:
            raise ToolException("knowledge_invalid_file_ref") from exc
        if stored != ref:
            raise ToolException("knowledge_invalid_file_ref")
        return raw, trusted_ref
    ref = validate_file_ref(ref)
    trusted = AttachmentReceipts(root).require(ref)
    try:
        raw, stored = DocumentWorkspace(root).read(ref["path"])
    except ToolException as exc:
        raise ToolException("knowledge_invalid_file_ref") from exc
    if any(
        ref[k] != stored[k]
        for k in ("version", "path", "sha256", "mime_type", "size_bytes")
    ):
        raise ToolException("knowledge_invalid_file_ref")
    return raw, ref if trusted else {**ref, "file_name": stored["file_name"]}


def knowledge_upload_interceptor(binding, connection):
    parsed = urlsplit(connection["url"])
    origin = f"{parsed.scheme}://{parsed.netloc}"
    headers = dict(connection.get("headers") or {})

    async def intercept(request, handler):
        if request.name not in {SUBMIT_TOOL, JOB_TOOL}:
            return await handler(request)
        try:
            values = _identity(request.runtime, binding, request.name)
            async with httpx.AsyncClient(
                timeout=30, trust_env=False, follow_redirects=False
            ) as client:
                if request.name == JOB_TOOL:
                    if (
                        set(request.args) != {"job_id"}
                        or not isinstance(request.args["job_id"], str)
                        or not re.fullmatch(r"kj_[a-f0-9]{32}", request.args["job_id"])
                    ):
                        raise ToolException("knowledge_not_found")
                    values["job_id"] = request.args["job_id"]
                    await _grant(client, values, operation="read")
                    result = await asyncio.wait_for(handler(request), timeout=30)
                    await _grant(client, values, operation="read")
                    return project_job_result(result, job_id=request.args["job_id"])
                if not upload_enabled():
                    raise ToolException("knowledge_upload_disabled")
                if set(request.args) != {"file_ref"}:
                    raise ToolException("knowledge_invalid_file_ref")
                try:
                    ref = request.args["file_ref"]
                    if isinstance(ref, dict) and set(ref) == set(
                        ImageRef.__annotations__
                    ):
                        ref = validate_uploaded_image_ref(ref)
                    else:
                        ref = validate_file_ref(ref)
                except (ValueError, TypeError) as exc:
                    raise ToolException("knowledge_invalid_file_ref") from exc
                raw, ref = await asyncio.to_thread(_file, values, ref)
                values.update(
                    {
                        k: ref[k]
                        for k in ("sha256", "size_bytes", "file_name", "mime_type")
                    }
                )
                grant = await _grant(client, values)
                stage_url = (
                    origin + "/internal/knowledge/uploads/" + values["request_id"]
                )
                private_headers = {
                    **headers,
                    "X-Knowledge-Operation-Grant": grant,
                    "X-Knowledge-File-Ref": canonical(ref),
                }
                staged = await _json(
                    client,
                    "PUT",
                    stage_url,
                    content=raw,
                    headers={**private_headers, "Content-Type": ref["mime_type"]},
                )
                if (
                    not isinstance(staged, dict)
                    or not isinstance(staged.get("upload_id"), str)
                    or not re.fullmatch(r"ku_[a-f0-9]{32}", staged["upload_id"])
                ):
                    raise ToolException("knowledge_unavailable")
                # Refresh the lease after the potentially slow byte transfer.
                grant = await _grant(client, values)
                updated = request.override(
                    args={"file_ref": ref},
                    headers={
                        **headers,
                        "X-Knowledge-Upload-ID": staged["upload_id"],
                        "X-Knowledge-Operation-Grant": grant,
                    },
                )
                try:
                    return project_job_result(
                        await asyncio.wait_for(handler(updated), timeout=30),
                        submit=True,
                    )
                except Exception as exc:
                    if not is_transport_error(exc):
                        raise
                    try:
                        grant = await _grant(client, values)
                        receipt = await _json(
                            client,
                            "GET",
                            stage_url,
                            headers={**headers, "X-Knowledge-Operation-Grant": grant},
                        )
                        if (
                            isinstance(receipt, dict)
                            and receipt.get("request_id") == values["request_id"]
                            and receipt.get("receipt") is not None
                        ):
                            return receipt_result(receipt["receipt"], submit=True)
                    except (
                        ToolException,
                        ValueError,
                        TypeError,
                        KeyError,
                        httpx.HTTPError,
                        TimeoutError,
                    ):
                        pass
                    return error_result("knowledge_submission_unconfirmed")
        except (
            ToolException,
            ValueError,
            TypeError,
            KeyError,
            httpx.HTTPError,
            TimeoutError,
        ) as exc:
            return error_result(
                str(exc) if isinstance(exc, ToolException) else "knowledge_unavailable"
            )

    return intercept
