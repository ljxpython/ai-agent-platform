"""Unit tests for memory fact deduplication and capacity eviction."""

from runtime_service.services.dearflow_agent.eviction import (
    evict_lowest_priority_items,
    find_near_duplicate,
    trim_bounded_list,
)


def test_find_near_duplicate_high_similarity():
    existing = [
        {
            "id": "1",
            "text": "用户喜欢使用 Python 进行后端开发",
            "category": "preference",
        },
        {"id": "2", "text": "前端偏好 Vue3 框架", "category": "preference"},
    ]
    candidate = "用户偏好使用 Python 写后端开发代码"
    match = find_near_duplicate(candidate, existing, threshold=0.5)
    assert match is not None
    assert match["id"] == "1"


def test_find_near_duplicate_low_similarity():
    existing = [
        {
            "id": "1",
            "text": "用户喜欢使用 Python 进行后端开发",
            "category": "preference",
        }
    ]
    candidate = "数据库使用 PostgreSQL"
    match = find_near_duplicate(candidate, existing, threshold=0.7)
    assert match is None


def test_evict_lowest_priority_items():
    items = [
        {
            "id": "old_inferred",
            "origin": "inferred",
            "updated_at": "2020-01-01",
            "category": "fact",
        },
        {
            "id": "new_inferred",
            "origin": "inferred",
            "updated_at": "2026-01-01",
            "category": "fact",
        },
        {
            "id": "confirmed",
            "origin": "confirmed",
            "updated_at": "2021-01-01",
            "category": "fact",
        },
        {
            "id": "protected_pref",
            "origin": "inferred",
            "updated_at": "2019-01-01",
            "category": "core_pref",
        },
    ]
    # Prune from 4 down to 2
    pruned = evict_lowest_priority_items(
        items, target_count=2, protect_categories={"core_pref"}
    )
    pruned_ids = {item["id"] for item in pruned}

    # Protected core_pref and confirmed fact should be preserved over old_inferred
    assert "protected_pref" in pruned_ids
    assert "confirmed" in pruned_ids or "new_inferred" in pruned_ids
    assert "old_inferred" not in pruned_ids


def test_trim_bounded_list():
    items = [f"item_{i}" for i in range(2500)]
    trimmed = trim_bounded_list(items, max_capacity=2000, trim_to=1500)
    assert len(trimmed) == 1500
    assert trimmed[-1] == "item_2499"


def test_save_evicts_overflow_facts_gracefully():
    from runtime_service.services.dearflow_agent.memory import MemoryStorage

    store = MemoryStorage()
    doc = {
        "revision": 0,
        "facts": [
            {
                "id": f"f_{i}",
                "text": f"fact {i}",
                "origin": "inferred",
                "updated_at": f"2020-01-0{i % 9 + 1}",
            }
            for i in range(105)
        ],
        "candidates": [],
        "sources": [f"s_{i}" for i in range(2100)],
        "deleted_digests": [f"d_{i}" for i in range(1100)],
    }
    saved_doc = {}
    store._write = lambda db, scope, d: saved_doc.update(d)
    store._save(None, ("t", "p", "u"), doc)

    # Automatically pruned to 100 facts, 1800 sources, 900 tombstones without raising 409
    assert len(saved_doc["facts"]) == 100
    assert len(saved_doc["sources"]) == 1800
    assert len(saved_doc["deleted_digests"]) == 900
    assert saved_doc["revision"] == 1
