# 02 检索算法重构与 MMR 多样性召回实现记录

## 改动时间
2026-10-15

## 相关任务
- Task 2.1: 创建 `relevance.py`，实现分词器 `tokenize`、IDF 计算 `compute_idf` 及 `mmr_rerank`
- Task 2.2: 重构 `MemoryStorage.context()`，接入 MMR 算法，淘汰旧切词代码
- Task 2.3: 编写 MMR 召回效果与多样性算法单元测试

## 改动文件
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/relevance.py` (新建)
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` (改造 context 方法)
- `apps/runtime-service/tests/services/dearflow_agent/test_memory_relevance.py` (新建单测)

## 具体改动

### 1. 新建 `relevance.py`
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/relevance.py`
- 实现零外部依赖的混合分词器 `tokenize()`，支持英文词法和中文双字切片（bigram）；
- 实现基于语料库词频的逆文档频率计算 `compute_idf()`；
- 实现双池 MMR 贪婪重排算法 `mmr_rerank()`：
  - 匹配池：根据 Query 词法与 IDF 权重贪心选择前 7 条事实，并通过 Jaccard 相似度施加多样性惩罚；
  - 背景偏好池：在未匹配事实中，为显式偏好预留最多 3 条配额，保证用户的长期偏好不会因 Query 关键词而完全被挤出；
  - 兜底排序保证时间新鲜度（`updated_at` 降序）。

### 2. 改造 `MemoryStorage.context()`
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- 彻底废除老旧的 `len(tokens(fact["text"]) & query_tokens)` 集合交集逻辑；
- 接入 `mmr_rerank(query[:6000], facts, top_k=10, lambda_param=0.7, char_budget=4000)`；
- 严格遵循 4000 字符预算限制与安全转义规则。

## 验证
- [x] 单元测试通过：`test_memory_relevance.py` 5 项测试全部通过（分词、Jaccard、IDF、MMR 多样性、字符预算）；
- [x] 回归测试通过：`test_memory_contract.py` 所有 15 项契约测试 100% 保持通过。
