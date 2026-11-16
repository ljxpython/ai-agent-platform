"""Bounded research via Tavily. The Runtime never connects to a user-supplied host."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool

from runtime_service.tools.errors import tool_error_handler
from runtime_service.tools.images import ImageWorkspace
from runtime_service.tools.research import public_url, tavily


async def jina_extract(url: str) -> dict:
    key = (os.environ.get("JINA_API_KEY") or os.environ.get("JINA_KEY") or "").strip()
    headers = {
        "X-Return-Format": "markdown",
        "X-Timeout": "20",
        "X-No-Cache": "false",
        "Accept": "application/json",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        async with (
            asyncio.timeout(25),
            httpx.AsyncClient(
                timeout=20, follow_redirects=True, trust_env=True
            ) as client,
        ):
            async with client.stream(
                "GET",
                "https://r.jina.ai/" + url,
                headers=headers,
            ) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        raise ToolException("research_response_too_large")

        try:
            parsed = json.loads(data)
            if (
                isinstance(parsed, dict)
                and "data" in parsed
                and isinstance(parsed["data"], dict)
            ):
                inner = parsed["data"]
                content = inner.get("content") or ""
                return {
                    "url": inner.get("url") or url,
                    "title": inner.get("title") or "",
                    "content": content,
                }
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        text = data.decode("utf-8", errors="replace")
        return {
            "url": url,
            "title": "",
            "content": text,
        }
    except (httpx.HTTPError, TimeoutError) as exc:
        raise ToolException("jina_provider_failed") from exc


def _evidence(workspace, runtime: ToolRuntime, records: list[dict]):
    if workspace is None:
        raise ToolException("research_probe_only")
    info = getattr(runtime, "execution_info", None)
    thread_id = getattr(info, "thread_id", "") if info else ""
    run_id = getattr(info, "run_id", "") if info else ""
    namespace = getattr(info, "checkpoint_ns", "") if info else ""
    artifacts = []
    summaries = []
    io = ImageWorkspace(workspace.root)
    from runtime_service.workspace.target import RemoteWorkspace

    if isinstance(workspace.root, RemoteWorkspace):
        evidence_result = workspace.root.call(
            "research_evidence",
            records=records,
            tool_call_id=getattr(runtime, "tool_call_id", ""),
            thread_id=thread_id,
            run_id=run_id,
            namespace=namespace,
        )
        if isinstance(evidence_result, (list, tuple)) and len(evidence_result) == 2:
            return (evidence_result[0], evidence_result[1])
        return evidence_result
    directory = io._directory(("sources",), create=True)
    try:
        for record in records:
            content = record.pop("content")
            raw = content.encode()
            digest = hashlib.sha256(raw).hexdigest()
            filename = digest + ".txt"
            temporary = ".source-" + uuid4().hex
            fd = os.open(
                temporary,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(fd, "wb") as target:
                    target.write(raw)
                    target.flush()
                    os.fsync(target.fileno())
                try:
                    os.link(
                        temporary,
                        filename,
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    pass
                if (
                    hashlib.sha256(
                        io.read("/workspace/sources/" + filename)
                    ).hexdigest()
                    != digest
                ):
                    raise ToolException("research_source_hash_mismatch")
            finally:
                os.unlink(temporary, dir_fd=directory)
            evidence = {
                **record,
                "content_hash": digest,
                "path": "/workspace/sources/" + filename,
                "tool_call_id": getattr(runtime, "tool_call_id", ""),
                "thread_id": thread_id,
                "run_id": run_id,
                "namespace": namespace,
                "observed_at": datetime.now(UTC).isoformat(),
            }
            artifacts.append(evidence)
            summaries.append(
                {
                    **evidence,
                    "preview": content[:8000],
                    "truncated": len(content) > 8000,
                }
            )
    except OSError as exc:
        raise ToolException("research_source_write_failed") from exc
    finally:
        os.close(directory)
    return json.dumps(summaries, ensure_ascii=False), {
        "version": 1,
        "sources": artifacts,
    }


def build_research_tools(workspace):
    @tool(response_format="content_and_artifact")
    async def search_web(query: str, runtime: ToolRuntime):
        """Search public web sources. Results are snippets, not verified page text."""
        if not query.strip() or len(query) > 1000:
            raise ToolException("invalid_research_query")
        result = await tavily(
            "search", {"query": query, "max_results": 5, "include_raw_content": False}
        )
        records = []
        rejected = 0
        for item in result.get("results", [])[:5]:
            try:
                url = await public_url(item["url"])
            except ToolException:
                rejected += 1
                continue
            records.append(
                {
                    "source_url": url,
                    "title": item.get("title") or "",
                    "kind": "search_snippet",
                    "content": item.get("content") or "",
                }
            )
        content, artifact = _evidence(workspace, runtime, records)
        artifact["rejected_sources"] = rejected
        return json.dumps(
            {"sources": json.loads(content), "rejected_sources": rejected},
            ensure_ascii=False,
        ), artifact

    @tool(response_format="content_and_artifact")
    async def fetch_page(url: str, runtime: ToolRuntime):
        """Read public page text through Jina Reader or Tavily extract, not a local browser or crawler."""
        await public_url(url)
        records = []
        jina_key = (
            os.environ.get("JINA_API_KEY") or os.environ.get("JINA_KEY") or ""
        ).strip()
        if jina_key:
            try:
                jina_res = await jina_extract(url)
                content = jina_res.get("content")
                if isinstance(content, str) and content.strip():
                    final_url = await public_url(jina_res.get("url") or url)
                    records.append(
                        {
                            "source_url": final_url,
                            "requested_url": url,
                            "title": jina_res.get("title") or "",
                            "kind": "page_text",
                            "content": content,
                        }
                    )
            except ToolException as exc:
                if exc.args not in (
                    ("jina_provider_failed",),
                    ("research_url_denied",),
                ):
                    raise

        if not records:
            if os.environ.get("TAVILY_API_KEY"):
                try:
                    result = await tavily(
                        "extract",
                        {"urls": [url], "extract_depth": "basic", "format": "text"},
                    )
                    for item in result.get("results", [])[:1]:
                        final_url = await public_url(item["url"])
                        content = item.get("raw_content")
                        if not isinstance(content, str) or not content.strip():
                            raise ToolException("research_empty_page")
                        records.append(
                            {
                                "source_url": final_url,
                                "requested_url": url,
                                "title": item.get("title") or "",
                                "kind": "page_text",
                                "content": content,
                            }
                        )
                except ToolException as exc:
                    if exc.args != ("research_provider_failed",):
                        raise
            elif not jina_key:
                raise ToolException(
                    "research_unavailable: No research provider configured"
                )

        if not records:
            raise ToolException("research_extract_failed")
        return _evidence(workspace, runtime, records)

    search_web.handle_tool_error = tool_error_handler(search_web.name)
    fetch_page.handle_tool_error = tool_error_handler(fetch_page.name)
    return [search_web, fetch_page]
