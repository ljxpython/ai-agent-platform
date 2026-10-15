"""Relevance-aware ranking and Maximal Marginal Relevance (MMR) diversity selection.

Deterministic, network-free, zero-dependency lexical relevance and MMR diversity
selection inspired by DeerFlow's deermem/core/relevance.py.
"""

from __future__ import annotations

import math
import re
from collections import Counter


def tokenize(text: str, max_chars: int = 4096) -> list[str]:
    """Tokenize text into Latin words and CJK bigrams without external dependencies."""
    bounded = text[:max_chars].casefold()
    parts = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", bounded)
    tokens: list[str] = []
    for part in parts:
        if part.isascii():
            tokens.append(part)
        else:
            # Add character unigrams for robust CJK semantic overlap
            tokens.extend(list(part))
            # Add bigrams for phrase preservation
            for i in range(len(part) - 1):
                tokens.append(part[i : i + 2])
    return tokens


def compute_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    """Calculate smooth Inverse Document Frequency (IDF) over the facts corpus."""
    n_docs = len(corpus_tokens)
    doc_freq: Counter[str] = Counter()
    for doc in corpus_tokens:
        for token in set(doc):
            doc_freq[token] += 1
    return {
        token: math.log((n_docs + 1) / (df + 1)) + 1.0 for token, df in doc_freq.items()
    }


def jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute token Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _mmr_select(
    candidates: list[dict],
    query_tokens: set[str],
    idf: dict[str, float],
    top_k: int,
    lambda_param: float = 0.7,
) -> list[dict]:
    """Helper: select top_k diverse items from candidates using MMR."""
    if not candidates or top_k <= 0:
        return []

    token_sets = [set(tokenize(f.get("text", ""))) for f in candidates]

    # Calculate relevance for each candidate
    rel_scores: list[float] = []
    for t_set in token_sets:
        overlap = t_set & query_tokens
        score = sum(idf.get(t, 1.0) for t in overlap) if overlap else 0.1
        rel_scores.append(score)

    max_rel = max(rel_scores) if rel_scores else 1.0
    norm_rel = [s / max_rel if max_rel > 0 else 0.0 for s in rel_scores]

    selected: list[int] = []
    unselected = list(range(len(candidates)))

    while unselected and len(selected) < top_k:
        best_score = -float("inf")
        best_idx = -1

        for idx in unselected:
            rel = norm_rel[idx]
            if not selected:
                score = rel
            else:
                max_sim = max(
                    jaccard_similarity(token_sets[idx], token_sets[s]) for s in selected
                )
                score = lambda_param * rel - (1.0 - lambda_param) * max_sim

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx == -1:
            break

        selected.append(best_idx)
        unselected.remove(best_idx)

    return [candidates[i] for i in selected]


def mmr_rerank(
    query: str,
    facts: list[dict],
    top_k: int = 10,
    lambda_param: float = 0.7,
    char_budget: int = 4000,
) -> list[dict]:
    """Rank facts using dual-pool MMR: guaranteed diverse query matches + diverse preferences.

    Preserves platform's contract of at most 7 query-relevant matches plus at most 3
    general background preferences, while applying MMR diversity in both pools.
    """
    if not facts:
        return []

    # 0. Pre-sort facts by updated_at descending for deterministic recency
    sorted_facts = sorted(
        facts,
        key=lambda f: (f.get("updated_at", ""), f.get("id", "")),
        reverse=True,
    )

    query_tokens = set(tokenize(query))
    fact_token_lists = [tokenize(f.get("text", "")) for f in sorted_facts]
    idf = compute_idf(fact_token_lists)

    # 1. Partition into query-matching pool and background pool
    matching: list[dict] = []
    background: list[dict] = []
    for f in sorted_facts:
        f_tokens = set(tokenize(f.get("text", "")))
        if query_tokens and (f_tokens & query_tokens):
            matching.append(f)
        else:
            background.append(f)

    # 2. MMR selection with guaranteed background preference quota
    pref_background = [f for f in background if f.get("category") == "preference"]
    non_pref_background = [f for f in background if f.get("category") != "preference"]

    # Guarantee at least 30% quota (or up to 3) for background preferences when available
    guaranteed_pref_k = (
        min(len(pref_background), max(1, int(top_k * 0.3))) if pref_background else 0
    )
    target_matching_k = min(len(matching), max(1, top_k - guaranteed_pref_k))

    selected_matching = _mmr_select(
        matching, query_tokens, idf, top_k=target_matching_k, lambda_param=lambda_param
    )

    remaining_k = top_k - len(selected_matching)
    selected_background = _mmr_select(
        pref_background, query_tokens, idf, top_k=remaining_k, lambda_param=lambda_param
    )

    # 4. Fill remaining quota if any
    final_candidates = selected_matching + selected_background
    if len(final_candidates) < top_k:
        needed = top_k - len(final_candidates)
        leftovers = [f for f in non_pref_background if f not in final_candidates]
        final_candidates.extend(leftovers[:needed])

    # 5. Enforce character budget
    budgeted: list[dict] = []
    total_chars = 0
    for fact in final_candidates:
        text_len = len(fact.get("text", ""))
        if total_chars + text_len > char_budget and budgeted:
            continue
        budgeted.append(fact)
        total_chars += text_len

    return budgeted
