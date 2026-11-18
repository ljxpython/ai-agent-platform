"""LangChain SQL tools backed by the Platform's current read authorization."""

import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from langchain.tools import ToolRuntime, tool
from langchain_community.tools.sql_database.tool import (
    InfoSQLDatabaseTool,
    QuerySQLDatabaseTool,
)
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.tools import ToolException
from langgraph.config import get_config

from runtime_service.tools.research import public_url, tavily


def platform_read(facts, operation, *, tool_call_id, **payload):
    config = get_config()
    endpoint = urlsplit(os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", ""))
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if not endpoint.hostname or not secret:
        raise ToolException("assistant_platform_unconfigured")
    body = {
        "operation": operation,
        "query": "",
        "database_id": "",
        "table_names": [],
        "table_offset": 0,
        "document_id": "",
        "line": 1,
        "target_thread_id": None,
        "target_run_id": None,
        "evidence_ids": [],
        "log_start": "",
        "log_end": "",
        "log_service": "",
        "actor_id": facts.principal.user_id,
        "project_id": facts.principal.project_id,
        "thread_id": str(UUID(config["configurable"]["thread_id"])),
        "run_id": str(UUID(str(config["metadata"]["run_id"]))),
        "tool_call_id": tool_call_id,
        **payload,
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True)
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        ("platform-assistant\n" + timestamp + "\n" + encoded).encode(),
        hashlib.sha256,
    ).hexdigest()
    url = urlunsplit(
        (
            endpoint.scheme,
            endpoint.netloc,
            "/api/platform-assistant/internal/read",
            "",
            "",
        )
    )
    try:
        with httpx.Client(
            timeout=15, follow_redirects=False, trust_env=False
        ) as client:
            with client.stream(
                "POST",
                url,
                content=encoded.encode(),
                headers={
                    "content-type": "application/json",
                    "x-assistant-time": timestamp,
                    "x-assistant-signature": signature,
                },
            ) as response:
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 256000:
                        raise ToolException("assistant_response_too_large")
                result = json.loads(data)
                if response.status_code != 200:
                    error = result.get("error", {})
                    raise ToolException(
                        str(error.get("code", "assistant_read_unavailable"))
                    )
                return result
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolException("assistant_read_unavailable") from exc


class PlatformSQLDatabase(SQLDatabase):
    """The toolkit sees a SQLDatabase; only the backend ever holds database credentials."""

    def __init__(self, read, database_id):
        self._read = read
        self._database_id = database_id

    @property
    def dialect(self):
        return "postgresql"

    def get_usable_table_names(self):
        return self._read("sql_schema", database_id=self._database_id)["data"]["tables"]

    def get_table_info_no_throw(self, table_names=None, table_offset=0):
        result = self._read(
            "sql_schema",
            database_id=self._database_id,
            table_names=table_names or [],
            table_offset=table_offset,
        )
        return json.dumps(result, ensure_ascii=False)

    def run_no_throw(self, command, *args, **kwargs):
        return json.dumps(
            self._read("sql_query", database_id=self._database_id, query=command),
            ensure_ascii=False,
        )


def make_tools(facts):
    def reader(runtime):
        def read(operation, **payload):
            return platform_read(
                facts, operation, tool_call_id=runtime.tool_call_id, **payload
            )

        return read

    @tool
    def list_databases(runtime: ToolRuntime) -> str:
        """列出当前身份/项目获准且已接入助手的只读数据库；空列表不代表平台没有数据库，平台系统Run/Thread记录通过运行诊断读取。"""
        return json.dumps(reader(runtime)("sql_sources"), ensure_ascii=False)

    @tool
    def sql_db_schema(
        database_id: str,
        runtime: ToolRuntime,
        table_names: str = "",
        table_offset: int = 0,
    ) -> str:
        """发现可读表、字段、关联和版本，不采样。表目录每页100项，按next_table_offset翻页；空表名返回本页前20表结构，可用逗号分隔指定最多20表。"""
        db = PlatformSQLDatabase(reader(runtime), database_id)
        return (
            InfoSQLDatabaseTool(db=db).invoke({"table_names": table_names})
            if table_names
            else db.get_table_info_no_throw(table_offset=table_offset)
        )

    @tool
    def sql_db_query(database_id: str, query: str, runtime: ToolRuntime) -> str:
        """执行自行生成的 PostgreSQL 只读 SELECT，支持过滤/关联/聚合，结果有界且携带证据编号。"""
        return QuerySQLDatabaseTool(
            db=PlatformSQLDatabase(reader(runtime), database_id)
        ).invoke({"query": query})

    @tool
    def read_run_diagnostics(thread_id: str, run_id: str, runtime: ToolRuntime) -> str:
        """读取获准Run最终状态、时间、追踪诊断及该Run绑定的持久checkpoint摘要（失败任务、错误码、实际中断和消息类型计数）。追踪未配置时仍查持久状态；review只是策略，不能证明发生审批；不返回消息正文/审批参数/堆栈。"""
        return json.dumps(
            reader(runtime)(
                "diagnostics",
                target_thread_id=str(UUID(thread_id)),
                target_run_id=str(UUID(run_id)),
            ),
            ensure_ascii=False,
        )

    @tool
    def read_run_logs(
        thread_id: str,
        run_id: str,
        runtime: ToolRuntime,
        start: str = "",
        end: str = "",
    ) -> str:
        """读取获准Run脱敏日志；后端按已验证Trace→执行请求编号→Run关联，不要求用户提供Trace。默认运行前后5分钟；时间未知或超过24小时需补含时区start/end。说明source、availability、correlation_type与覆盖窗口；空结果不证明无故障，不能扩查项目全量。"""
        return json.dumps(
            reader(runtime)(
                "logs",
                target_thread_id=str(UUID(thread_id)),
                target_run_id=str(UUID(run_id)),
                log_start=start,
                log_end=end,
            ),
            ensure_ascii=False,
        )

    @tool
    def search_project_logs(
        runtime: ToolRuntime,
        trace_id: str = "",
        start: str = "",
        end: str = "",
        service: str = "",
    ) -> str:
        """获准研发/运维在没有Run时检索当前项目日志。可按Trace、服务及含时区时间范围筛选，最长24小时。"""
        return json.dumps(
            reader(runtime)(
                "logs",
                query=trace_id,
                log_start=start,
                log_end=end,
                log_service=service,
            ),
            ensure_ascii=False,
        )

    @tool
    def search_documents(
        runtime: ToolRuntime, document_id: str = "", query: str = "", line: int = 1
    ) -> str:
        """从已提供目录自行选择document_id，读取该篇当前用户指南正文及行号、哈希和证据；每次具体操作咨询应重新读取。无ID仅返回目录，不做关键词匹配；query/line仅为旧调用兼容，不影响指南选择。"""
        return json.dumps(
            reader(runtime)(
                "documents", query=query, document_id=document_id, line=line
            ),
            ensure_ascii=False,
        )

    @tool
    def search_source(
        query: str, runtime: ToolRuntime, document_id: str = "", line: int = 1
    ) -> str:
        """仅获准研发可检索已发布的源码快照，不能读取任意宿主路径。"""
        return json.dumps(
            reader(runtime)("source", query=query, document_id=document_id, line=line),
            ensure_ascii=False,
        )

    @tool
    async def search_public_web(query: str, runtime: ToolRuntime) -> str:
        """只搜索用户本轮原文中明确提供的公开关键词，不可拼接内部证据、标识符或日志。"""
        import asyncio

        validate_public_query(query, runtime.state.get("messages", []))
        authorization = await asyncio.to_thread(
            reader(runtime), "authorize_search", query=query
        )
        response = await tavily(
            "search", {"query": query, "max_results": 5, "include_raw_content": False}
        )
        results = []
        for item in response["results"][:5]:
            try:
                url = await public_url(item["url"])
            except ToolException:
                continue
            results.append(
                {
                    "url": url,
                    "title": item.get("title", "")[:300],
                    "snippet": item.get("content", "")[:4000],
                }
            )
        return json.dumps(
            {
                "sources": results,
                "kind": "public_search_snippet",
                "authorization_evidence_id": authorization["evidence_id"],
            },
            ensure_ascii=False,
        )

    tools = [
        list_databases,
        sql_db_schema,
        sql_db_query,
        read_run_diagnostics,
        read_run_logs,
        search_project_logs,
        search_documents,
        search_source,
        search_public_web,
    ]
    for item in tools:
        item.handle_tool_error = True
    return tools


def validate_public_query(query, messages):
    from langchain_core.messages import HumanMessage

    latest = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
    if (
        not isinstance(latest, str)
        or not query.strip()
        or len(query) > 300
        or query not in latest
        or not re.search(r"搜索|查找|查询|查一下|search|look up", latest, re.I)
    ):
        raise ToolException(
            "assistant_public_keywords_required: 请在本轮消息明确提供公开搜索关键词。"
        )
    if re.search(
        r"(?i)api.?key|password|secret|bearer|token[=: ]|-----BEGIN|https?://|[/\\]|@|[0-9a-f]{8}-[0-9a-f-]{20,}|\d{8,}|SELECT\s|INSERT\s",
        query,
    ):
        raise ToolException("assistant_public_query_private")
