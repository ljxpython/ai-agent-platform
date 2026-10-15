"""Unit tests for relevance ranking and MMR diversity selection."""

from runtime_service.services.dearflow_agent.relevance import (
    compute_idf,
    jaccard_similarity,
    mmr_rerank,
    tokenize,
)


def test_tokenize_latin_and_cjk():
    tokens = tokenize("I love FastAPI 和 PostgreSQL 数据库")
    assert "fastapi" in tokens
    assert "postgresql" in tokens
    assert "数据" in tokens
    assert "据库" in tokens


def test_jaccard_similarity():
    set_a = {"python", "fastapi", "docker"}
    set_b = {"python", "fastapi", "vue"}
    # intersection: 2, union: 4 -> 0.5
    assert jaccard_similarity(set_a, set_b) == 0.5
    assert jaccard_similarity(set(), set_b) == 0.0


def test_compute_idf():
    corpus = [
        ["common", "python"],
        ["common", "fastapi"],
        ["common", "docker"],
    ]
    idf = compute_idf(corpus)
    # common appears in all 3 docs, python appears in only 1 -> python has higher IDF
    assert idf["python"] > idf["common"]


def test_mmr_rerank_diversity():
    # 5 redundant facts about python and 2 facts about frontend / db
    facts = [
        {"id": "py1", "text": "Python 规范缩进 4 格", "category": "preference"},
        {"id": "py2", "text": "Python 规范使用黑体格式化", "category": "preference"},
        {"id": "py3", "text": "Python 规范类型标注严格", "category": "preference"},
        {
            "id": "py4",
            "text": "Python 代码必须写 pytest 测试",
            "category": "preference",
        },
        {"id": "fe1", "text": "前端使用 Vue3 和 TailwindCSS", "category": "preference"},
        {
            "id": "db1",
            "text": "数据库采用 PostgreSQL 和 Alembic",
            "category": "preference",
        },
    ]
    query = "请按照代码规范帮我写个 Python 脚本"
    ranked = mmr_rerank(query, facts, top_k=4, lambda_param=0.6)
    ranked_ids = [f["id"] for f in ranked]

    # The top-1 must be Python related
    assert ranked_ids[0].startswith("py")
    # MMR should penalize redundant Python facts and introduce diversity (fe1 or db1)
    has_diversity = any(item_id in {"fe1", "db1"} for item_id in ranked_ids)
    assert has_diversity, f"MMR should select diverse items, got: {ranked_ids}"


def test_mmr_rerank_respects_char_budget():
    facts = [
        {"id": f"fact-{i}", "text": "长文本偏好事实内容 " * 50, "category": "fact"}
        for i in range(10)
    ]
    ranked = mmr_rerank("长文本", facts, top_k=10, char_budget=500)
    total_len = sum(len(f["text"]) for f in ranked)
    assert total_len <= 1000
    assert len(ranked) < len(facts)


def test_project_document_query_matching_and_fallback():
    from runtime_service.services.dearflow_agent.memory import project_document

    doc = {
        "revision": 5,
        "epoch": 1,
        "automatic_candidates": True,
        "facts": [
            {
                "id": "1",
                "text": "对全世界的神话体系一直挺好奇",
                "category": "preference",
                "expires_at": None,
            },
            {
                "id": "2",
                "text": "写前端组件时一律使用 Tailwind CSS，不使用纯 CSS 或 SCSS",
                "category": "preference",
                "expires_at": None,
            },
            {
                "id": "3",
                "text": "在这个项目里你称呼我为「阿洄」",
                "category": "preference",
                "expires_at": None,
            },
        ],
        "candidates": [],
    }

    # 1. 泛化查询：大模型传 "当前项目的记忆检索" 或 "用户偏好"，应当优雅回退返回全部事实
    res_generic = project_document(doc, query="当前项目的记忆检索")
    assert len(res_generic["facts"]) == 3

    res_pref = project_document(doc, query="用户偏好")
    assert len(res_pref["facts"]) == 3

    # 2. 核心关键词命中：带泛化词的查询 "Tailwind CSS 偏好"，能够精准命中对应事实
    res_kw = project_document(doc, query="Tailwind CSS 偏好")
    assert len(res_kw["facts"]) == 1
    assert res_kw["facts"][0]["id"] == "2"

    # 3. 中文关键词命中："神话体系"
    res_myth = project_document(doc, query="神话体系")
    assert len(res_myth["facts"]) == 1
    assert res_myth["facts"][0]["id"] == "1"

    # 4. 确实不相关的具体主题词："Java 架构规范" -> 返回空列表
    res_java = project_document(doc, query="Java 架构规范")
    assert len(res_java["facts"]) == 0
