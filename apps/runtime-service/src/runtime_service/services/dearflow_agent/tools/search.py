"""Bounded research via Tavily. The Runtime never connects to a user-supplied host."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool

from runtime_service.tools.images import ImageWorkspace


async def public_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError()
        host = parsed.hostname.rstrip(".").lower()
        if "." not in host or host.endswith((".localhost", ".local", ".internal", ".lan")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
        # Only the fixed Tavily endpoint is contacted by Runtime. DNS and redirects
        # for extracted pages belong to Tavily; local DNS may use proxy fake IPs.
    except ValueError as exc:
        raise ToolException("research_url_denied") from exc
    return url


async def tavily(operation: str, payload: dict) -> dict:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise ToolException("research_unavailable: TAVILY_API_KEY is not configured")
    try:
        async with asyncio.timeout(30), httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
            async with client.stream("POST", "https://api.tavily.com/" + operation,
                                     headers={"Authorization": "Bearer " + key}, json=payload) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        raise ToolException("research_response_too_large")
        result = json.loads(data)
        if not isinstance(result, dict) or not isinstance(result.get("results"), list):
            raise ValueError()
        for record in result["results"]:
            if not isinstance(record, dict) or not isinstance(record.get("url"), str):
                raise ValueError()
            if any(record.get(key) is not None and not isinstance(record[key], str)
                   for key in ("title", "content", "raw_content")):
                raise ValueError()
        return result
    except (httpx.HTTPError, ValueError, TimeoutError) as exc:
        raise ToolException("research_provider_failed") from exc


def _evidence(workspace, runtime: ToolRuntime, records: list[dict]):
    if workspace is None:
        raise ToolException("research_probe_only")
    info = runtime.execution_info
    artifacts = []
    summaries = []
    io = ImageWorkspace(workspace.root)
    directory = io._directory(("sources",), create=True)
    try:
        for record in records:
            content = record.pop("content")
            raw = content.encode()
            digest = hashlib.sha256(raw).hexdigest()
            filename = digest + ".txt"
            temporary = ".source-" + uuid4().hex
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as target:
                    target.write(raw)
                    target.flush()
                    os.fsync(target.fileno())
                try:
                    os.link(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
                except FileExistsError:
                    pass
                if hashlib.sha256(io.read("/workspace/sources/" + filename)).hexdigest() != digest:
                    raise ToolException("research_source_hash_mismatch")
            finally:
                os.unlink(temporary, dir_fd=directory)
            evidence = {**record, "content_hash": digest, "path": "/workspace/sources/" + filename,
                        "tool_call_id": runtime.tool_call_id, "thread_id": info.thread_id,
                        "run_id": info.run_id, "namespace": info.checkpoint_ns,
                        "observed_at": datetime.now(timezone.utc).isoformat()}
            artifacts.append(evidence)
            summaries.append({**evidence, "preview": content[:8000], "truncated": len(content) > 8000})
    except OSError as exc:
        raise ToolException("research_source_write_failed") from exc
    finally:
        os.close(directory)
    return json.dumps(summaries, ensure_ascii=False), {"version": 1, "sources": artifacts}


def build_research_tools(workspace):
    @tool(response_format="content_and_artifact")
    async def search_web(query: str, runtime: ToolRuntime):
        """Search public web sources. Results are snippets, not verified page text."""
        if not query.strip() or len(query) > 1000:
            raise ToolException("invalid_research_query")
        result = await tavily("search", {"query": query, "max_results": 5, "include_raw_content": False})
        records = []
        rejected = 0
        for item in result.get("results", [])[:5]:
            try:
                url = await public_url(item["url"])
            except ToolException:
                rejected += 1
                continue
            records.append({"source_url": url, "title": item.get("title") or "",
                            "kind": "search_snippet", "content": item.get("content") or ""})
        content, artifact = _evidence(workspace, runtime, records)
        artifact["rejected_sources"] = rejected
        return json.dumps({"sources": json.loads(content), "rejected_sources": rejected}, ensure_ascii=False), artifact

    @tool(response_format="content_and_artifact")
    async def fetch_page(url: str, runtime: ToolRuntime):
        """Read public page text through Tavily extract, not a local browser or crawler."""
        await public_url(url)
        result = await tavily("extract", {"urls": [url], "extract_depth": "basic", "format": "text"})
        records = []
        for item in result.get("results", [])[:1]:
            final_url = await public_url(item["url"])
            content = item.get("raw_content")
            if not isinstance(content, str) or not content.strip():
                raise ToolException("research_empty_page")
            records.append({"source_url": final_url, "requested_url": url, "title": item.get("title") or "",
                            "kind": "page_text", "content": content})
        if not records:
            raise ToolException("research_extract_failed")
        return _evidence(workspace, runtime, records)

    search_web.handle_tool_error = True
    fetch_page.handle_tool_error = True
    return [search_web, fetch_page]
