from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from langgraph_sdk import Auth
from runtime_service.auth.platform import (
    authenticate,
    deny_image_scope_on_server_resources,
)
from runtime_service.runtime.auth import verify_delegation_claims
from runtime_service.runtime.errors import RuntimeAuthError


async def _custom_endpoint(case: dict, token: str) -> dict:
    operation = case["endpoint"]
    authorization = f"Bearer {token}"
    thread_id = case.get("thread_id", "thread-1")
    if operation in {"image-upload", "image-read"}:
        from runtime_service.http.images import _authorize_image_request

        await _authorize_image_request(thread_id, authorization, operation)
    elif operation in {
        "workspace-file-upload",
        "workspace-file-read",
        "workspace-fork",
    }:
        from runtime_service.http.documents import _auth_scope

        with patch(
            "runtime_service.http.documents.resolve_thread_workspace",
            return_value=Path("/tmp"),
        ):
            await _auth_scope(thread_id, authorization, operation)
    elif operation in {"terminal-read", "terminal-write"}:
        from runtime_service.http.terminal import _owner

        with patch("runtime_service.http.terminal.terminal_enabled", return_value=True):
            await _owner(thread_id, authorization, write=operation == "terminal-write")
    elif operation in {"dear-skills-read", "dear-skills-write"}:
        from runtime_service.http.dear_skills import authorize

        with patch("runtime_service.http.dear_skills.enabled", return_value=True):
            await authorize(
                authorization,
                write=operation == "dear-skills-write",
                tool_name="list_skills"
                if operation.endswith("read")
                else "upload_skill",
            )
    elif operation in {"dear-memory-read", "dear-memory-write"}:
        from runtime_service.http.dear_memory import authorize

        await authorize(authorization, write=operation == "dear-memory-write")
    elif operation in {"dear-governance-read", "dear-governance-write"}:
        from runtime_service.http.dear_governance import authorize

        os.environ["RUNTIME_DEAR_GOVERNANCE_ENABLED"] = "1"
        await authorize(
            thread_id, authorization, write=operation == "dear-governance-write"
        )
    elif operation in {"message-read", "message-enqueue"}:
        from runtime_service.webapp import (
            EnqueueMessage,
            enqueue_message,
            list_messages,
        )

        run_read_token = case.get("run_read_token")
        run_read_authorization = f"Bearer {run_read_token}" if run_read_token else None
        os.environ.pop("DATABASE_URI", None)
        try:
            if operation == "message-read":
                await list_messages(thread_id, authorization, run_read_authorization)
            else:
                await enqueue_message(
                    thread_id,
                    EnqueueMessage(
                        target_run_id=uuid4(),
                        client_message_id=uuid4(),
                        idempotency_key="test",
                        content="test",
                        authorization_ref="test",
                    ),
                    authorization,
                    run_read_authorization,
                )
        except HTTPException as exc:
            if exc.status_code == 503 and exc.detail == "message inbox unavailable":
                return {"accepted": True, "boundary": "storage_unavailable"}
            raise
    elif operation == "suggestions-generate":
        from runtime_service.http.suggestions import (
            SuggestionsRequest,
            _authorize_scope,
        )

        user = await authenticate(authorization=authorization)
        _authorize_scope(
            thread_id,
            SuggestionsRequest(
                assistant_id="showcase_demo",
                messages=[{"role": "user", "content": "continue"}],
            ),
            user,
        )
    elif operation == "title-generate":
        from runtime_service.http.title_summary import (
            SummarizeTitleRequest,
            _authorize_scope,
        )

        user = await authenticate(authorization=authorization)
        _authorize_scope(
            thread_id,
            SummarizeTitleRequest(
                assistant_id="showcase_demo",
                messages=[{"role": "user", "content": "title"}],
            ),
            user,
        )
    elif operation == "diagnostics-read":
        from unittest.mock import AsyncMock

        from fastapi import Response
        from runtime_service.http.diagnostics import run_diagnostics_endpoint

        with patch(
            "runtime_service.http.diagnostics.authorize_thread_targets", AsyncMock()
        ):
            await run_diagnostics_endpoint(
                thread_id, uuid4(), Response(), authorization
            )
    elif operation == "usage-read":
        from unittest.mock import AsyncMock

        from fastapi import Response
        from runtime_service.http.usage import thread_usage_endpoint

        with patch("runtime_service.http.usage.authorize_thread_targets", AsyncMock()):
            await thread_usage_endpoint(
                str(thread_id), Response(), authorization=authorization
            )
    elif operation in {"thread-stop", "thread-stop-read"}:
        from unittest.mock import AsyncMock

        from runtime_service.http.run_control import _authorize

        with patch(
            "runtime_service.http.run_control.authorize_thread_targets", AsyncMock()
        ):
            await _authorize(authorization, thread_id, operation)
    elif operation == "run-cancellation-read":
        raise HTTPException(403, "native receipt scope cannot access custom endpoints")
    else:
        raise AssertionError("Unknown custom endpoint: " + operation)
    return {"accepted": True, "boundary": "authorized"}


def _run_case(case: dict, data: dict) -> dict:
    token = case["token"]
    try:
        if case.get("mode", "claims") == "claims":
            verified = verify_delegation_claims(
                token,
                secret=data["secret"],
                issuer=data["issuer"],
                audience=data["audience"],
                context=case.get("context"),
                expected_scope=case.get("expected_scope"),
            )
            return {
                "accepted": True,
                "operation": verified.scope.operation,
                "request_id": verified.request_id,
                "platform_trace_id": verified.platform_trace_id,
            }

        user = asyncio.run(authenticate(authorization=f"Bearer {token}"))
        if case["mode"] == "http":
            return {"accepted": True, "identity": user["identity"]}
        if case["mode"] == "custom":
            return asyncio.run(_custom_endpoint(case, token))

        calls = []

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def post(self, url, *, json, headers):
                calls.append(json)
                if case.get("acl") == "unavailable":
                    raise httpx.ConnectError("unavailable")
                allowed = [] if case.get("acl") == "deny" else json["thread_ids"]
                return httpx.Response(
                    200,
                    json={"allowed_thread_ids": allowed},
                    request=httpx.Request("POST", url),
                )

        context = SimpleNamespace(
            user=user, resource=case["resource"], action=case["action"]
        )
        with patch("runtime_service.auth.platform.httpx.AsyncClient", FakeClient):
            asyncio.run(deny_image_scope_on_server_resources(context, case["value"]))
        return {
            "accepted": True,
            "acl_calls": len(calls),
            "acl_action": calls[0]["action"] if calls else None,
            "credential_id": calls[0].get("credential_id") if calls else None,
        }
    except RuntimeAuthError as exc:
        return {"accepted": False, "code": exc.code}
    except Auth.exceptions.HTTPException as exc:
        return {"accepted": False, "status": exc.status_code}
    except HTTPException as exc:
        return {"accepted": False, "status": exc.status_code}


def main() -> int:
    data = json.load(sys.stdin)
    os.environ["PLATFORM_RUNTIME_DELEGATION_SECRET"] = data["secret"]
    os.environ["PLATFORM_RUNTIME_DELEGATION_ISSUER"] = data["issuer"]
    os.environ["PLATFORM_RUNTIME_DELEGATION_AUDIENCE"] = data["audience"]
    os.environ["PLATFORM_THREAD_AUTHORIZATION_URL"] = (
        "http://platform.test/thread-authorization"
    )
    cases = data.get("cases")
    if cases is None:
        cases = [{"token": token} for token in data["tokens"]]
    results = [_run_case(case, data) for case in cases]
    json.dump(results, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
