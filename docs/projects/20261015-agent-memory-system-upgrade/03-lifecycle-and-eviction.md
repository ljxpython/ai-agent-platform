# 记忆系统架构升级 - 03 容量自治、近重复合并与平滑淘汰

## 1. 目标与背景

当前平台设定了僵硬的硬编码容量限制：
- `facts` 最大 100 条；
- `candidates` 最大 100 条；
- `sources` 最大 2000 个；
- `deleted_digests` (tombstone) 最大 1000 个。

当事实或候选达到 100 条时，系统直接在 `_save` 中抛出 `DocumentError("memory_capacity_exceeded", 409)` 异常；或者在 `begin_extraction` 中直接将 `automatic_candidates` 置为 `False` 并挂起维护状态（`maintenance_reason="candidate_limit"`）。这要求用户在控制台手动一条条寻找、研判并删除事实，严重违背智能体自治运行的理念。同时，当模型提取出与已有事实表达相似（但字面不完全一致）的新候选时，系统会将其当作新候选盲目累加，导致候选列表充满同质噪音。

本专题目标：
1. 实现 **Fact Dedup 近重复检测与合并**，自动聚合高度同义的候选或事实；
2. 废除打满直接报 409 拒服的死板逻辑，实现基于综合权重的 **Eviction 平滑淘汰机制**，实现存储容量的自我代谢。

---

## 2. DeerFlow 怎么做的 vs 我们的差距与借鉴

### DeerFlow 设计
- **Fact Dedup 门禁**：提出新事实时，使用 token-Jaccard 相似度比对。若达到相似度阈值（默认 0.7~0.8），判定为近重复（Near-duplicate），直接合入已有事实并提升其置信度（Confidence），不产生新条目。
- **混合淘汰策略 (`hybrid-v1`)**：当容量达到上限时，根据综合评分公式自动淘汰分值最低的事实：
  $$\text{Score} = w_1 \cdot \text{Confidence} + w_2 \cdot \text{Freshness} + w_3 \cdot \text{Heat}$$
  若无外部热度指标，则按置信度 + 确认新鲜度（最近更新时间）淘汰。

### 我们的差距
- 只有严格的 `fingerprint`（完全相等的字符串 hash）去重，多一个空格或同义词就判定为全新条目；
- 满了直接报 409，完全没有自清理机制。

### 借鉴与本土化改造
- **去除 DeerFlow 的业务绑定**：DeerFlow 在文件系统侧维护了单独的 sidecar 元数据目录（`.metadata/`），每次淘汰涉及磁盘文件删除与索引刷新。我们在 PostgreSQL 中是单一 JSON Document，单次事务即可原子完成淘汰与版本递增（`revision + 1`），性能更高且无需处理文件系统碎片。

---

## 3. 具体改动位置与代码实现设计

### 3.1 运行时层 (`runtime-service`)

#### A. 新建容量治理模块
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/eviction.py`
- **核心逻辑：**
  ```python
  def token_jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
      """计算两组 Token 的 Jaccard 相似度"""
      if not tokens_a or not tokens_b:
          return 0.0
      intersection = len(tokens_a & tokens_b)
      union = len(tokens_a | tokens_b)
      return intersection / union

  def evict_lowest_priority_items(
      items: list[dict],
      target_count: int,
      protect_categories: set[str] | None = None
  ) -> list[dict]:
      """
      当条目超过 target_count 时，按优先级排序并平滑淘汰最弱项：
      优先保留: 保护分类 > 高置信度/确认项(confirmed) > 较新更新项
      """
  ```

#### B. 改造 `MemoryStorage.propose` 实现近重复自动合并
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- **改动位置：** `MemoryStorage.propose`
- **改动逻辑：**
  - 在遍历新 candidate 时，先分词计算与当前已存 `facts` 和 `candidates` 的 Jaccard 相似度；
  - 若与某已有条目相似度 $\ge 0.75$：
    - 不新建 candidate，而是更新该条目的 `updated_at` 为当前时间；
    - 若已有条目是 candidate，则将其置信度提升；
    - 记录合并指标，避免冗余条目进入候选区。

#### C. 改造 `MemoryStorage._save` 实现平滑淘汰
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- **改动位置：** `MemoryStorage._save`
- **改动逻辑：**
  - 移除 `if len(doc["facts"]) > 100: raise DocumentError("memory_capacity_exceeded", 409)`；
  - 改为：若 `len(doc["facts"]) > 100`，调用 `evict_lowest_priority_items(doc["facts"], target_count=100)` 自动裁剪多余项；
  - 对 `candidates` 同理（保持最多 100 条最相关候选）；
  - 对 `sources`（上限 2000）和 `deleted_digests`（上限 1000）按 FIFO 队列平滑滑出最老旧的 hash，而不是永久锁死。

---

## 4. 任务拆分

### Task 3.1: 创建 eviction.py 模块
- **改动内容：** 实现结合 Dice 相似度算法的近重复检测、多权重淘汰排序算法及 FIFO 滑动裁剪。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/eviction.py`
- **预期结果：** 提供稳定无外部依赖的语义近重复匹配和软淘汰优先级排序。
- **验证项：** `pytest test_memory_eviction.py` → ✅ 通过 (5 passed)
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/03-lifecycle-and-eviction.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

### Task 3.2: 改造 MemoryStorage.propose 接入近重复去重
- **改动内容：** 提取候选时先比对语义重复性，同义事实自动刷新时间戳并强化置信度，避免候选区垃圾堆积。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage.propose()`
- **预期结果：** 相同意思的不同表述自动合并，候选超出上限时平滑淘汰弱候选。
- **验证项：** `pytest test_memory_eviction.py` → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/03-lifecycle-and-eviction.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

### Task 3.3: 重构 MemoryStorage._save 实现平滑淘汰
- **改动内容：** 彻底废除 409 抛错拒服逻辑，事实/候选超过 100 条时自动淘汰最弱项，sources/tombstones 自动滑动裁剪。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage._save()`
- **预期结果：** 灌入超过 100 条事实时平稳裁剪，系统永不抛出 `memory_capacity_exceeded` 异常。
- **验证项：** `test_save_evicts_overflow_facts_gracefully` → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/03-lifecycle-and-eviction.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

---

## 5. 验证要求与记录

### 验证记录
#### 2026-10-15 验证
- ✅ `test_find_near_duplicate_high_similarity`: 近重复同义句正确识别；
- ✅ `test_find_near_duplicate_low_similarity`: 异构句子正常区分；
- ✅ `test_evict_lowest_priority_items`: 保护分类与已确认事实优先保留；
- ✅ `test_trim_bounded_list`: 达到容量后正确裁剪多余元数据；
- ✅ `test_save_evicts_overflow_facts_gracefully`: 105 条事实与 2100 个 sources 自动平滑缩减至安全限制，无异常抛出。

## 状态
done
