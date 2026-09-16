"""arXiv research; pure parsers copied from DeerFlow (MIT), network bounded locally."""
from typing import Any

NS_MAP = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _build_search_query(
    query: str,
    category: str | None,
    start_date: str | None,
    end_date: str | None,
) -> str:
    """Build arXiv's `search_query` field.

    arXiv uses its own query grammar: `ti:`, `abs:`, `cat:`, `all:`, with
    `AND`/`OR`/`ANDNOT` combinators. We search `all:` for the user's
    topic (matches title + abstract + authors) and optionally AND it
    with a category filter and a submission date range.
    """
    # Wrap multi-word queries in double quotes so arXiv's Lucene parser
    # treats them as a phrase.  Without quotes, `all:diffusion model` is
    # parsed as `all:diffusion OR model`, pulling in unrelated papers
    # that merely mention the word "model".
    if " " in query:
        parts = [f'all:"{query}"']
    else:
        parts = [f"all:{query}"]
    if category:
        parts.append(f"cat:{category}")
    if start_date or end_date:
        # arXiv date range format: [YYYYMMDDHHMM TO YYYYMMDDHHMM]
        lo = (start_date or "19910101").replace("-", "") + "0000"
        hi = (end_date or "29991231").replace("-", "") + "2359"
        parts.append(f"submittedDate:[{lo} TO {hi}]")
    return " AND ".join(parts)


def _normalise_arxiv_id(raw_id: str) -> str:
    """Convert a full arXiv URL to a bare id.

    Handles both modern and legacy arXiv ID formats:
    - Modern: "http://arxiv.org/abs/1706.03762v5" -> "1706.03762"
    - Legacy: "http://arxiv.org/abs/hep-th/9901001v1" -> "hep-th/9901001"
    """
    # Extract everything after /abs/ to preserve legacy archive prefix
    if "/abs/" in raw_id:
        tail = raw_id.split("/abs/", 1)[1]
    else:
        tail = raw_id.rsplit("/", 1)[-1]
    # Strip version suffix: "1706.03762v5" -> "1706.03762"
    if "v" in tail:
        base, _, suffix = tail.rpartition("v")
        if suffix.isdigit():
            return base
    return tail


def _parse_entry(entry: Any) -> dict:
    """Turn one Atom <entry> element into a paper dict."""
    import xml.etree.ElementTree as ET

    def _text(path: str) -> str:
        node = entry.find(path, NS_MAP)
        return (node.text or "").strip() if node is not None and node.text else ""

    raw_id = _text("atom:id")
    arxiv_id = _normalise_arxiv_id(raw_id)

    authors = [(a.findtext("atom:name", default="", namespaces=NS_MAP) or "").strip() for a in entry.findall("atom:author", NS_MAP)]
    authors = [a for a in authors if a]

    categories = [c.get("term", "") for c in entry.findall("atom:category", NS_MAP) if c.get("term")]

    pdf_url = ""
    abs_url = raw_id  # default
    for link in entry.findall("atom:link", NS_MAP):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
        elif link.get("rel") == "alternate":
            abs_url = link.get("href", abs_url)

    # Dates come as ISO 8601 (2017-06-12T17:57:34Z). Keep the date part.
    published_raw = _text("atom:published")
    updated_raw = _text("atom:updated")
    published = published_raw.split("T", 1)[0] if published_raw else ""
    updated = updated_raw.split("T", 1)[0] if updated_raw else ""

    # Abstract (<summary>) has ragged whitespace from arXiv's formatting.
    # Collapse internal whitespace to make downstream LLM consumption easier.
    abstract = " ".join(_text("atom:summary").split())

    # Silence unused import warning; ET is only needed for type hints above.
    del ET

    return {
        "id": arxiv_id,
        "title": " ".join(_text("atom:title").split()),
        "authors": authors,
        "abstract": abstract,
        "published": published,
        "updated": updated,
        "categories": categories,
        "pdf_url": pdf_url,
        "abs_url": abs_url,
    }

