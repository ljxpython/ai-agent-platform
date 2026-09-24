"""Check Platform's current Thread ACL before using personal memory in a run."""
import hashlib
import hmac
import logging
import os
import time

import httpx

from runtime_service.runtime import verified_delegation_from_user

logger = logging.getLogger(__name__)


async def memory_allowed(runtime_or_user, thread_id: str | None = None) -> bool:
    user = getattr(getattr(runtime_or_user, "server_info", None), "user", runtime_or_user)
    facts = verified_delegation_from_user(user)
    if thread_id is None:
        info = getattr(runtime_or_user, "execution_info", None)
        thread_id = str(info.thread_id) if info else None
    endpoint = os.getenv("PLATFORM_RUNTIME_MEMORY_AUTH_URL", "")
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if not endpoint or not secret or not thread_id or facts.scope.operation != "run-create":
        return False
    stamp = str(int(time.time()))
    project_id, user_id = facts.principal.project_id, facts.principal.user_id
    message = f"{stamp}\n{project_id}\n{thread_id}\n{user_id}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(endpoint, params={"project_id": project_id, "thread_id": thread_id,
                                                        "user_id": user_id},
                                        headers={"x-runtime-memory-timestamp": stamp,
                                                 "x-runtime-memory-signature": signature})
        response.raise_for_status()
        return response.json().get("allowed") is True
    except (httpx.HTTPError, ValueError):
        logger.warning("memory_acl_check_failed project_id=%s thread_id=%s", project_id, thread_id)
        return False
