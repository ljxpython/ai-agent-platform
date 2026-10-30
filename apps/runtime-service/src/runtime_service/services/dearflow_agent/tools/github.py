"""Public GitHub operations from the upstream research script, with explicit bounds."""

import base64
import json
import re
from typing import Annotated, Literal
from urllib.parse import quote, urlencode

from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool
from pydantic import Field

from runtime_service.observability.logging import log_context_metric
from runtime_service.tools.errors import tool_error_handler

from .research_http import get_public
from .search import _evidence

_SOURCE_PAGE_CHARS = 12000


def build_github_tool(workspace):
    @tool(response_format="content_and_artifact")
    async def github_query(
        owner: str,
        repo: str,
        runtime: ToolRuntime,
        operation: Literal[
            "summary",
            "info",
            "readme",
            "file",
            "tree",
            "languages",
            "contributors",
            "commits",
            "issues",
            "prs",
            "releases",
            "tags",
        ],
        path: str = "",
        ref: str = "",
        page: Annotated[int, Field(ge=1, le=100)] = 1,
        per_page: Annotated[int, Field(ge=1, le=100)] = 100,
        start_line: Annotated[int, Field(ge=1)] = 1,
        max_lines: Annotated[int, Field(ge=1)] = 80,
        query: str = "",
    ):
        """Read PUBLIC GitHub repository data. No token/private access. Lists are paginated.

        operation is required; choose readme/tree/file for source, info/summary for metadata.
        owner is the GitHub account/organization; repo is only the repository name.
        Keep both from the user's task across calls; correct arguments after a missing-source error.
        Tree lists one directory at path (root by default), never the recursive tree.
        Readme uses path as a directory (empty for root); file uses an exact file path.
        File/readme/tree require an explicit ref (commit, tag, or branch); no default
        branch fallback. If the user names a commit, pass that exact SHA on every read.
        Use next_page until null; never treat one page as a total. File/readme return
        numbered lines (max_lines capped at 200); follow next_line with start_line.
        For long files, query locates the first case-insensitive literal match at or
        after start_line and returns nearby numbered lines; it is not a code search.
        A distant Markdown match includes the first complete lines in document_intro;
        both windows share the same character budget and keep separate line ranges.
        Query is only supported for file/readme and is limited to 256 characters.
        For repository research, batch readme and root tree first; skip info/summary
        statistics. After at most two directory-discovery rounds, batch relevant package
        READMEs and architecture/lifecycle docs. Read implementations only for claims
        those docs do not establish; do not enumerate nested src trees first.
        Source material is saved at an evidence path for audit
        only; never use execute or read_file on that path. For source evidence, use
        operation=file with an explicit immutable commit ref and cite the returned
        source_url/html_url. Branches and tags are unsuitable for immutable claims.
        """
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)
            or repo in {".", ".."}
            or not 1 <= page <= 100
            or not 1 <= per_page <= 100
            or len(ref) > 200
            or any(ord(c) < 32 for c in ref)
            or start_line < 1
            or max_lines < 1
            or len(query) > 256
            or any(ord(c) < 32 or ord(c) == 127 for c in query)
            or (query and operation not in {"file", "readme"})
        ):
            raise ToolException("invalid_github_query")
        max_lines = min(max_lines, 200)
        if operation not in {
            "summary",
            "info",
            "readme",
            "file",
            "tree",
            "languages",
            "contributors",
            "commits",
            "issues",
            "prs",
            "releases",
            "tags",
        }:
            raise ToolException("invalid_github_operation")
        if (operation == "file" and not path) or (
            path
            and (
                len(path) > 1000
                or path.startswith("/")
                or "\\" in path
                or any(p in (".", "..", "") for p in path.split("/"))
            )
        ):
            raise ToolException("invalid_github_path")
        if operation in {"file", "readme", "tree"} and not ref.strip():
            raise ToolException("invalid_github_ref")
        base = f"https://api.github.com/repos/{owner}/{repo}"

        async def request(url, params=None):
            raw, headers = await get_public(url, params)
            log_context_metric(
                {
                    "event": "runtime.tool_output.capture",
                    "tool_name": "github_query",
                    "tool_call_id": runtime.tool_call_id,
                    "stage": "http_capture",
                    "captured_bytes": len(raw),
                }
            )
            try:
                return json.loads(raw), headers
            except ValueError as exc:
                raise ToolException("invalid_github_response") from exc

        info, _ = await request(base)
        if not isinstance(info, dict) or info.get("private") is not False:
            raise ToolException("github_private_repository_denied")
        params = {}
        next_page = None
        if operation in {"summary", "info"}:
            data, headers, url = info, {}, base
            if operation == "summary":
                data = {
                    key: info.get(key)
                    for key in (
                        "full_name",
                        "description",
                        "html_url",
                        "stargazers_count",
                        "forks_count",
                        "open_issues_count",
                        "language",
                        "license",
                        "created_at",
                        "updated_at",
                        "pushed_at",
                        "default_branch",
                        "topics",
                    )
                }
                data["languages"], _ = await request(base + "/languages")
                contributors, contributor_headers = await request(
                    base + "/contributors", {"per_page": 100, "page": 1}
                )
                if not isinstance(contributors, list):
                    raise ToolException("invalid_github_response")
                data["contributors_observed"] = len(contributors)
                data["contributors_truncated"] = (
                    'rel="next"' in contributor_headers.get("link", "")
                )
                data["latest_releases"], _ = await request(
                    base + "/releases", {"per_page": 1}
                )
            else:
                data = {
                    key: info.get(key)
                    for key in (
                        "full_name",
                        "html_url",
                        "description",
                        "default_branch",
                        "visibility",
                        "license",
                        "updated_at",
                        "pushed_at",
                    )
                }
        else:
            if operation == "file":
                endpoint = "contents/" + quote(path, safe="/")
                params = {"ref": ref}
            elif operation == "readme":
                endpoint = "readme" + ("/" + quote(path, safe="/") if path else "")
                params = {"ref": ref}
            elif operation == "tree":
                endpoint = "git/trees/" + quote(ref, safe="")
                # Resolve only the requested directory; recursive trees can exceed HTTP bounds.
                for part in path.split("/") if path else ():
                    directory, _ = await request(base + "/" + endpoint)
                    if not isinstance(directory, dict) or not isinstance(
                        directory.get("tree"), list
                    ):
                        raise ToolException("invalid_github_response")
                    entry = next(
                        (
                            item
                            for item in directory["tree"]
                            if item.get("path") == part and item.get("type") == "tree"
                        ),
                        None,
                    )
                    if entry is None or not isinstance(entry.get("sha"), str):
                        raise ToolException("github_directory_unavailable")
                    endpoint = "git/trees/" + quote(entry["sha"], safe="")
            else:
                endpoint = "pulls" if operation == "prs" else operation
                params = {"per_page": per_page, "page": page}
                if operation in {"issues", "prs"}:
                    params["state"] = "all"
            url = base + "/" + endpoint
            data, headers = await request(url, params)
            if operation in {
                "contributors",
                "commits",
                "issues",
                "prs",
                "releases",
                "tags",
            } and not isinstance(data, list):
                raise ToolException("invalid_github_response")
            if operation in {"file", "readme"}:
                if (
                    not isinstance(data, dict)
                    or data.get("encoding") != "base64"
                    or data.get("type") != "file"
                ):
                    raise ToolException("github_file_unavailable")
                try:
                    data = {
                        "path": data["path"],
                        "sha": data["sha"],
                        "html_url": data["html_url"],
                        "text": base64.b64decode(data["content"]).decode("utf-8"),
                    }
                except (KeyError, ValueError, UnicodeError) as exc:
                    raise ToolException("github_file_not_text") from exc
            elif operation == "tree":
                if not isinstance(data, dict) or not isinstance(data.get("tree"), list):
                    raise ToolException("invalid_github_response")
                entries = data["tree"]
                offset = (page - 1) * per_page
                next_page = (
                    page + 1
                    if offset + per_page < len(entries) and page < 100
                    else None
                )
                data = {
                    "sha": data.get("sha"),
                    "path": path,
                    "ref": ref,
                    "truncated": bool(data.get("truncated")) or next_page is not None,
                    "tree": [
                        {"path": item.get("path"), "type": item.get("type")}
                        for item in entries[offset : offset + per_page]
                    ],
                }
        has_next = 'rel="next"' in headers.get("link", "")
        record = {
            "source_url": url + ("?" + urlencode(params) if params else ""),
            "title": f"{owner}/{repo} {operation}",
            "kind": "github_api",
            "operation": operation,
            "page": page,
            "per_page": per_page,
            "next_page": next_page or (page + 1 if has_next and page < 100 else None),
            "truncated": has_next
            or bool(isinstance(data, dict) and data.get("truncated")),
            "query": params,
            "content": json.dumps(data, ensure_ascii=False),
        }
        content, artifact = _evidence(workspace, runtime, [record])

        def adapted(result):
            log_context_metric(
                {
                    "event": "runtime.tool_output.adapter",
                    "tool_name": "github_query",
                    "tool_call_id": runtime.tool_call_id,
                    "stage": "tool_adapter",
                    "visible_chars": len(result),
                    "visible_bytes": len(result.encode("utf-8")),
                }
            )
            return result, artifact

        if operation == "tree":
            content = json.dumps(
                {
                    **data,
                    "next_page": record["next_page"],
                    "source_url": record["source_url"],
                    "evidence_path": artifact["sources"][0]["path"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        elif operation in {"file", "readme"}:
            lines = data["text"].splitlines()
            if start_line > len(lines) + 1:
                raise ToolException("invalid_github_query")
            match = {}
            intro = {}
            page_chars = _SOURCE_PAGE_CHARS
            if query:
                needle = query.casefold()
                matched_line = next(
                    (
                        i + 1
                        for i in range(start_line - 1, len(lines))
                        if needle in lines[i].casefold()
                    ),
                    None,
                )
                if matched_line is None:
                    return adapted(
                        json.dumps(
                            {
                                "path": data["path"],
                                "sha": data["sha"],
                                "html_url": data["html_url"],
                                "match_found": False,
                                "searched_from_line": start_line,
                                "total_lines": len(lines),
                                "evidence_path": artifact["sources"][0]["path"],
                            },
                            ensure_ascii=False,
                        )
                    )
                start_line = max(start_line, matched_line - min(3, max_lines - 1))
                if start_line > 20 and data["path"].lower().endswith(".md"):
                    opening = []
                    opening_chars = 0
                    for index, value in enumerate(lines[:20]):
                        row = f"{index + 1}: {value}"
                        if opening_chars + len(row) + 1 > 2000:
                            break
                        opening.append(row)
                        opening_chars += len(row) + 1
                    if opening:
                        intro = {
                            "document_intro": {
                                "start_line": 1,
                                "end_line": len(opening),
                                "line_truncated": False,
                                "text": "\n".join(opening),
                            }
                        }
                        page_chars -= opening_chars
                # Context must not consume the character budget before the matched line.
                context_size = sum(
                    len(f"{i + 1}: {lines[i]}") + 1
                    for i in range(start_line - 1, matched_line - 1)
                )
                if (
                    context_size
                    + min(
                        len(f"{matched_line}: {lines[matched_line - 1]}") + 1,
                        page_chars,
                    )
                    > page_chars
                ):
                    start_line = matched_line
                match = {"match_found": True, "matched_line": matched_line}
            selected = []
            characters = 0
            line_truncated = False
            for index in range(
                start_line - 1, min(len(lines), start_line - 1 + max_lines)
            ):
                line = f"{index + 1}: {lines[index]}"
                if characters + len(line) + 1 > page_chars:
                    if not selected:
                        selected.append(line[:page_chars])
                        line_truncated = True
                    break
                selected.append(line)
                characters += len(line) + 1
            end_line = start_line + len(selected) - 1
            content = json.dumps(
                {
                    **match,
                    **intro,
                    "path": data["path"],
                    "sha": data["sha"],
                    "html_url": data["html_url"]
                    + (f"#L{start_line}-L{end_line}" if selected else ""),
                    "start_line": start_line,
                    "end_line": end_line,
                    "total_lines": len(lines),
                    "next_line": end_line + 1 if end_line < len(lines) else None,
                    "line_truncated": line_truncated,
                    "text": "\n".join(selected),
                    "evidence_path": artifact["sources"][0]["path"],
                },
                ensure_ascii=False,
            )
        return adapted(content)

    github_query.handle_tool_error = tool_error_handler(github_query.name)
    return github_query
