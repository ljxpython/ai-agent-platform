"""Fact near-duplicate deduplication gate and capacity eviction policies.

Inspired by DeerFlow's fact_dedup_enabled and deermem/core/eviction.py, adapted for
PostgreSQL JSON documents and atomic CAS transactions.
"""

from __future__ import annotations

from typing import Any

from runtime_service.services.dearflow_agent.relevance import (
    tokenize,
)


def find_near_duplicate(
    candidate_text: str,
    existing_items: list[dict[str, Any]],
    threshold: float = 0.5,
) -> dict[str, Any] | None:
    """Find an existing item with Dice token similarity >= threshold.

    If a near-duplicate exists, new proposals should merge/reinforce rather than append.
    """
    candidate_tokens = set(tokenize(candidate_text))
    if not candidate_tokens:
        return None

    best_match = None
    highest_sim = 0.0

    for item in existing_items:
        item_text = item.get("text", "")
        item_tokens = set(tokenize(item_text))
        if not item_tokens:
            continue
        intersection = len(candidate_tokens & item_tokens)
        dice_sim = (2.0 * intersection) / (len(candidate_tokens) + len(item_tokens))
        if dice_sim >= threshold and dice_sim > highest_sim:
            highest_sim = dice_sim
            best_match = item

    return best_match


def evict_lowest_priority_items(
    items: list[dict[str, Any]],
    target_count: int = 100,
    protect_categories: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Prune items exceeding target_count using priority score based on recency & origin.

    Priority:
    1. Protected categories (e.g. core preferences)
    2. Explicitly confirmed facts (origin == 'confirmed' or 'user')
    3. Most recently updated items
    """
    if len(items) <= target_count:
        return items

    protected = protect_categories or set()

    def priority_key(item: dict[str, Any]) -> tuple:
        is_protected = 1 if item.get("category") in protected else 0
        is_confirmed = 1 if item.get("origin") in {"confirmed", "user"} else 0
        updated_at = item.get("updated_at", "")
        fact_id = item.get("id", "")
        return (is_protected, is_confirmed, updated_at, fact_id)

    # Sort ascending so lowest priority items are at the beginning
    sorted_items = sorted(items, key=priority_key)
    # Keep the top `target_count` highest priority items
    kept = sorted_items[-target_count:]
    return kept


def trim_bounded_list(items: list[str], max_capacity: int, trim_to: int) -> list[str]:
    """FIFO trim for metadata collections like sources and tombstones."""
    if len(items) > max_capacity:
        return items[-trim_to:]
    return items
