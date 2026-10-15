# 记忆系统架构升级 - 02 检索算法重构与 MMR 多样性召回

## 1. 目标与背景

当前平台在 `MemoryStorage.context()` 方法中，将数据库中存储的全部事实（最多 100 条）读入内存，采用极其简陋的逻辑进行打分：
通过正则表达式提取英文字符和中文字符的 2-gram 切片做集合交集：
`len(tokens(fact["text"]) & query_tokens)`

这种方式存在严重的工程缺陷：
1. **无逆文档频率 (IDF) 区分度**：高频泛化词（如"代码"、"项目"、"可以"）与低频关键专业词（如"PostgreSQL"、"FastAPI"）权重完全相同，极易产生误召回；
2. **缺乏多样性控制（刷屏问题）**：若用户有 5 条表述相近但细节不同的偏好（如"写代码用Python3.12"、"Python缩进4空格"、"Python类型标注严格"），一旦当前 Query 涉及 Python，这 5 条事实将霸占全部检索前排配额，导致其他领域的偏好完全被挤出 4000 字符预算。

本专题目标：
1. 废除简陋的 2-gram 集合交集，实现基于 **Token 词频与逆文档频率 (IDF)** 的相关性评分器；
2. 引入 **MMR (Maximal Marginal Relevance) 多样性选择算法**，保证召回结果在贴合查询的同时具备跨维度多样性。

---

## 2. DeerFlow 怎么做的 vs 我们的差距与借鉴

### DeerFlow 设计
- **派生全文索引**：使用 SQLite FTS5 对事实做全量索引，支持 `jieba` 分词；
- **Relevance-aware MMR 算法** (`deermem/core/relevance.py`)：
  - 提取 Query 与 Fact 的 Token 集合；
  - 结合语料库构建轻量级 IDF 权重；
  - 采用 MMR 贪心迭代选词公式：
    $$\text{MMR}(d) = \lambda \cdot \text{Sim}_1(d, Q) - (1 - \lambda) \cdot \max_{d_i \in S} \text{Sim}_2(d, d_i)$$
    其中 $\lambda$ 为相关性权重，$1-\lambda$ 为多样性惩罚权重，$S$ 为已选出的事实集合。

### 我们的差距
- 没有任何相关性加权和去冗余惩罚，纯靠字符交集长度排序。

### 借鉴与本土化改造
- **去除 DeerFlow 的业务绑定**：DeerFlow 在本地维护 SQLite 文件（`.retrieval/memory-fts5.sqlite3`），依赖本地文件系统持久化。在我们平台中，数据以 PostgreSQL 为权威存储，用户事实上限通常在 100 条以内。在内存中执行纯 Python 的 Token-IDF 与 MMR 算法，既轻量（单次计算耗时 < 1ms），又无需引入外部复杂的 FTS5 引擎维护与数据同步一致性风险，完全契合 Karpathy Guidelines 的 KISS 原则。

---

## 3. 具体改动位置与代码实现设计

### 3.1 运行时层 (`runtime-service`)

#### A. 新建轻量级相关性与 MMR 算法模块
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/relevance.py`
- **核心逻辑：**
  ```python
  import math
  import re
  from collections import Counter

  def tokenize(text: str) -> list[str]:
      """支持英文单词与 CJK 字符的双字切片分词（零额外依赖）"""
      parts = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.casefold())
      tokens = []
      for part in parts:
          if part.isascii():
              tokens.append(part)
          else:
              # 中文双字切片（bigram）
              for i in range(len(part) - 1):
                  tokens.append(part[i:i+2])
              if len(part) == 1:
                  tokens.append(part)
      return tokens

  def compute_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
      """针对当前用户事实库计算轻量级 IDF"""
      n_docs = len(corpus_tokens)
      doc_freq = Counter()
      for doc in corpus_tokens:
          for token in set(doc):
              doc_freq[token] += 1
      return {
          token: math.log((n_docs + 1) / (df + 1)) + 1.0
          for token, df in doc_freq.items()
      }

  def mmr_rerank(
      query: str,
      facts: list[dict],
      top_k: int = 10,
      lambda_param: float = 0.7,
      char_budget: int = 4000
  ) -> list[dict]:
      """基于 MMR 算法贪心筛选前 top_k 条兼顾相关性与多样性的事实"""
  ```

#### B. 改造 `MemoryStorage.context()`
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- **改动位置：** `MemoryStorage.context`
- **改动逻辑：**
  - 调用 `mmr_rerank(query, facts, top_k=10, lambda_param=0.7, char_budget=4000)`；
  - 彻底移除老旧的 2-gram 交集逻辑；
  - 保留原有 `<user_memory>` 格式以及 `<`、`>`、`&` 的安全转义。

---

## 4. 任务拆分

### Task 2.1: 创建 relevance.py 实现 IDF 与双池 MMR 算法
- **改动内容：** 建立零外部依赖的混合分词器与 IDF 权重计算，实现双池 MMR 贪心多样性重排。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/relevance.py` → `mmr_rerank()`
- **预期结果：** 对相关性 facts 施加多样性惩罚，并为背景通用偏好保障必要配额。
- **验证项：** `pytest test_memory_relevance.py` → ✅ 通过 (5 passed)
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/02-relevance-and-mmr.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

### Task 2.2: 重构 MemoryStorage.context 接入 MMR 召回
- **改动内容：** 淘汰旧有的 2-gram 集合交集逻辑，改用 `mmr_rerank`，保留安全转义与 4000 字符硬预算。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage.context()`
- **预期结果：** 关键词具备区分度，长篇与同类事实不再刷屏，上下文信息密度显著提升。
- **验证项：** `pytest test_memory_contract.py` 15 项原有契约测试全部保持通过 → ✅ 通过 (15 passed)
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/02-relevance-and-mmr.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

### Task 2.3: 编写 MMR 效果与多样性单测
- **改动内容：** 编写覆盖拉丁/中文分词、Jaccard 计算、IDF 权重、多样性防霸屏与字符预算的单元测试。
- **代码位置：** `apps/runtime-service/tests/services/dearflow_agent/test_memory_relevance.py`
- **预期结果：** 验证在存在 4 条相关 Python 事实时，MMR 成功引入前端/数据库等异质偏好。
- **验证项：** `pytest test_memory_relevance.py` → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/02-relevance-and-mmr.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

---

## 5. 验证要求与记录

### 验证记录
#### 2026-10-15 验证
- ✅ `test_tokenize_latin_and_cjk`: 中英文与双字切片分词通过；
- ✅ `test_jaccard_similarity`: Jaccard 相似度准确；
- ✅ `test_compute_idf`: 低频专业词 IDF 权重高于泛化常用词；
- ✅ `test_mmr_rerank_diversity`: 成功避免同质事实刷屏；
- ✅ `test_mmr_rerank_respects_char_budget`: 字符预算严格受控；
- ✅ `test_memory_contract.py` 全量通过。

## 状态
done
