"""Bounded arXiv search using the copied upstream Atom parser."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlencode, urlsplit

from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool

from .arxiv import NS_MAP, _build_search_query, _parse_entry
from .research_http import get_public
from .search import _evidence


def build_arxiv_tool(workspace):
    @tool(response_format="content_and_artifact")
    async def arxiv_search(query: str, runtime: ToolRuntime, max_results: int = 20,
                           category: str | None = None, start_date: str | None = None,
                           end_date: str | None = None,
                           sort_by: Literal["relevance", "submittedDate", "lastUpdatedDate"] = "relevance"):
        """Search arXiv abstracts, not full texts. Returns papers and a saved evidence path.

        Max 50 papers; versioned IDs are deduplicated. Dates use YYYY-MM-DD.
        Default relevance sorting; use a date range for recent papers.
        Empty results or missing fields must never be filled with invented papers.
        """
        if (not query.strip() or len(query) > 300 or not 1 <= max_results <= 50
            or any(c in query for c in ('"', '\\')) or any(ord(c) < 32 for c in query)
            or category is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,30}", category)):
            raise ToolException("invalid_arxiv_query")
        try:
            for value in (start_date, end_date):
                if value is not None:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError()
                    date.fromisoformat(value)
            if start_date and end_date and start_date > end_date:
                raise ValueError()
        except ValueError as exc:
            raise ToolException("invalid_arxiv_date_range") from exc
        params = {"search_query": _build_search_query(query.strip(), category, start_date, end_date),
                  "start": 0, "max_results": max_results, "sortBy": sort_by, "sortOrder": "descending"}
        endpoint = "https://export.arxiv.org/api/query"
        raw, _ = await get_public(endpoint, params)
        try:
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ValueError()
            root = ET.fromstring(raw)
            if root.tag != "{http://www.w3.org/2005/Atom}feed":
                raise ValueError()
            entries = root.findall("atom:entry", NS_MAP)
            papers = {}
            duplicates = 0
            for entry in entries[:max_results]:
                paper = _parse_entry(entry)
                if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[A-Za-z.-]+/\d{7})", paper["id"]):
                    raise ValueError()
                for key in ("abs_url", "pdf_url"):
                    if paper[key]:
                        url = urlsplit(paper[key])
                        if url.scheme not in {"http", "https"} or url.netloc not in {"arxiv.org", "export.arxiv.org"}:
                            raise ValueError()
                paper["read_scope"] = "abstract_only"
                paper["missing_fields"] = [key for key in ("title", "authors", "abstract", "published", "pdf_url") if not paper[key]]
                previous = papers.get(paper["id"])
                if previous is not None:
                    duplicates += 1
                if previous is None or paper["updated"] > previous["updated"]:
                    papers[paper["id"]] = paper
            total_raw = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
            total = int(total_raw) if total_raw is not None else None
        except (ET.ParseError, ValueError) as exc:
            raise ToolException("invalid_arxiv_response") from exc
        result = {"papers": list(papers.values()), "query": params, "returned": len(papers),
                  "total_results": total, "duplicates_removed": duplicates,
                  "truncated": total is None or total > len(entries),
                  "searched_at": datetime.now(UTC).isoformat(), "read_scope": "abstract_only"}
        _, artifact = _evidence(workspace, runtime, [{"source_url": endpoint + "?" + urlencode(params),
            "title": "arXiv: " + query, "kind": "arxiv_metadata", "content": json.dumps(result, ensure_ascii=False)}])
        result["evidence"] = artifact["sources"][0]
        return json.dumps(result, ensure_ascii=False), artifact
    arxiv_search.handle_tool_error = True
    return arxiv_search
