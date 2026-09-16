"""Public GitHub operations from the upstream research script, with explicit bounds."""
import base64
import json
import re
from typing import Literal
from urllib.parse import quote, urlencode

from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool

from .research_http import get_public
from .search import _evidence


def build_github_tool(workspace):
    @tool(response_format="content_and_artifact")
    async def github_query(owner: str, repo: str, runtime: ToolRuntime,
                           operation: Literal["summary", "info", "readme", "file", "tree", "languages", "contributors", "commits", "issues", "prs", "releases", "tags"] = "info",
                           path: str = "", ref: str = "", page: int = 1, per_page: int = 30):
        """Read PUBLIC GitHub repository data. No token/private access. Lists are paginated.

        Use next_page until null; never treat one page as a total. Tree can be truncated.
        Full JSON is saved at the returned evidence path; read_file it if preview is truncated.
        file takes a relative repository path; ref defaults to the repository default branch.
        """
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo) or repo in {".", ".."}
            or not 1 <= page <= 100 or not 1 <= per_page <= 100
            or len(ref) > 200 or any(ord(c) < 32 for c in ref)):
            raise ToolException("invalid_github_query")
        if operation not in {"summary", "info", "readme", "file", "tree", "languages", "contributors", "commits", "issues", "prs", "releases", "tags"}:
            raise ToolException("invalid_github_operation")
        if operation == "file" and (not path or len(path) > 1000 or path.startswith("/") or "\\" in path
                                    or any(p in (".", "..", "") for p in path.split("/"))):
            raise ToolException("invalid_github_path")
        base = f"https://api.github.com/repos/{owner}/{repo}"

        async def request(url, params=None):
            raw, headers = await get_public(url, params)
            try:
                return json.loads(raw), headers
            except ValueError as exc:
                raise ToolException("invalid_github_response") from exc

        info, _ = await request(base)
        if not isinstance(info, dict) or info.get("private") is not False:
            raise ToolException("github_private_repository_denied")
        params = {}
        if operation in {"summary", "info"}:
            data, headers, url = info, {}, base
            if operation == "summary":
                data = {key: info.get(key) for key in ("full_name", "description", "html_url", "stargazers_count", "forks_count", "open_issues_count", "language", "license", "created_at", "updated_at", "pushed_at", "default_branch", "topics")}
                data["languages"], _ = await request(base + "/languages")
                contributors, contributor_headers = await request(base + "/contributors", {"per_page": 100, "page": 1})
                if not isinstance(contributors, list):
                    raise ToolException("invalid_github_response")
                data["contributors_observed"] = len(contributors)
                data["contributors_truncated"] = 'rel="next"' in contributor_headers.get("link", "")
                data["latest_releases"], _ = await request(base + "/releases", {"per_page": 1})
        else:
            if operation == "file":
                endpoint = "contents/" + quote(path, safe="/")
                params = {"ref": ref} if ref else {}
            elif operation == "tree":
                branch = ref or info.get("default_branch")
                if not isinstance(branch, str) or not branch:
                    raise ToolException("github_default_branch_unavailable")
                endpoint = "git/trees/" + quote(branch, safe="")
                params = {"recursive": "1"}
            else:
                endpoint = "pulls" if operation == "prs" else operation
                params = {"per_page": per_page, "page": page}
                if operation in {"issues", "prs"}:
                    params["state"] = "all"
                if operation == "readme" and ref:
                    params["ref"] = ref
            url = base + "/" + endpoint
            data, headers = await request(url, params)
            if operation in {"contributors", "commits", "issues", "prs", "releases", "tags"} and not isinstance(data, list):
                raise ToolException("invalid_github_response")
            if operation in {"file", "readme"}:
                if not isinstance(data, dict) or data.get("encoding") != "base64" or data.get("type") != "file":
                    raise ToolException("github_file_unavailable")
                try:
                    data = {"path": data["path"], "sha": data["sha"], "html_url": data["html_url"],
                            "text": base64.b64decode(data["content"]).decode("utf-8")}
                except (KeyError, ValueError, UnicodeError) as exc:
                    raise ToolException("github_file_not_text") from exc
        has_next = 'rel="next"' in headers.get("link", "")
        record = {"source_url": url + ("?" + urlencode(params) if params else ""), "title": f"{owner}/{repo} {operation}", "kind": "github_api",
                  "operation": operation, "page": page, "per_page": per_page,
                  "next_page": page + 1 if has_next and page < 100 else None,
                  "truncated": has_next or bool(isinstance(data, dict) and data.get("truncated")),
                  "query": params, "content": json.dumps(data, ensure_ascii=False)}
        return _evidence(workspace, runtime, [record])

    github_query.handle_tool_error = True
    return github_query
