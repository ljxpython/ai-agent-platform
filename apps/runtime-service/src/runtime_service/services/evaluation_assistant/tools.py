"""Bounded pure arithmetic and grant-checked evaluation reads; no host execution."""

import ast
import hashlib
import hmac
import json
import os
import time
from decimal import Decimal, InvalidOperation, localcontext
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from langchain.tools import tool

from runtime_service.errors import RuntimeAuthError


def calculate(expression: str) -> str:
    if not expression or len(expression) > 500:
        raise ValueError("算式长度必须在1到500字符之间。")
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 100:
        raise ValueError("算式最多100个节点。")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return Decimal(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div) and right:
                return left / right
        raise ValueError("只允许数字、括号和加减乘除，除数不能为零。")

    with localcontext() as ctx:
        ctx.prec = 28
        result = visit(tree.body)
        if not result.is_finite() or abs(result) > Decimal("1e24"):
            raise ValueError("计算结果超出合成验证范围。")
        return format(result, "f")


async def platform_evidence(
    facts, thread_id, work_item_id, job_id, *, operation="read", payload=None
):
    endpoint = urlsplit(os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", ""))
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if not endpoint.scheme or not endpoint.netloc or not secret:
        raise RuntimeAuthError("evaluation.platform_unconfigured")
    body = {
        "project_id": facts.principal.project_id,
        "actor_id": facts.principal.user_id,
        "thread_id": str(UUID(thread_id)),
        "work_item_id": str(UUID(work_item_id)),
        "job_id": str(UUID(job_id)),
        "operation": operation,
        "payload": payload or {},
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True)
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        ("evaluation-assistant\n" + timestamp + "\n" + encoded).encode(),
        hashlib.sha256,
    ).hexdigest()
    url = urlunsplit(
        (endpoint.scheme, endpoint.netloc, "/api/evaluation/internal/assistant", "", "")
    )
    async with httpx.AsyncClient(
        timeout=20, trust_env=False, follow_redirects=False
    ) as client:
        response = await client.post(
            url,
            content=encoded.encode(),
            headers={
                "content-type": "application/json",
                "x-evaluation-time": timestamp,
                "x-evaluation-signature": signature,
            },
        )
    if response.status_code != 200:
        raise RuntimeAuthError("evaluation.material_unavailable")
    return response.json()


def make_tools(read_current):
    @tool
    async def decimal_calculate(expression: str) -> str:
        """确定计算合成数字的加减乘除，不执行代码。"""
        await read_current()
        try:
            return calculate(expression)
        except (ValueError, SyntaxError, InvalidOperation, OverflowError):
            return "无法计算：仅支持有界数字及加减乘除，请检查算式。"

    @tool
    async def read_evidence(reference: str) -> str:
        """按本次资料中的证据编号读取内容，不能指定URL、文件路径或其他项目。"""
        snapshot = await read_current()
        evidence = snapshot.get("evidence", {})
        return json.dumps(
            evidence.get(reference, {"unavailable": "未找到获准证据编号"}),
            ensure_ascii=False,
        )

    @tool
    async def validate_test_plan(proposal_json: str) -> str:
        """校验方案JSON能否执行；不会批准、发布或启动评测。"""
        if len(proposal_json) > 250_000:
            return "方案过大。"
        try:
            proposal = json.loads(proposal_json)
        except ValueError:
            return "方案不是合法JSON。"
        return json.dumps(
            await read_current(operation="validate", payload={"proposal": proposal}),
            ensure_ascii=False,
        )

    return [decimal_calculate, read_evidence, validate_test_plan]
