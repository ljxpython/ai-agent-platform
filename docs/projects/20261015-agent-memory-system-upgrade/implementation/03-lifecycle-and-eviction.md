# 03 容量自治、近重复合并与平滑淘汰实现记录

## 改动时间
2026-10-15

## 相关任务
- Task 3.1: 创建 `eviction.py`，实现 Jaccard/Dice 相似度计算与多权重淘汰排序算法
- Task 3.2: 改造 `MemoryStorage.propose`，接入近重复事实合并逻辑 (Fact Dedup Gate)
- Task 3.3: 重构 `MemoryStorage._save`，以自动淘汰替代 409 异常抛出，解除僵死限制

## 改动文件
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/eviction.py` (新建)
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` (改造 _save 与 propose)
- `apps/runtime-service/tests/services/dearflow_agent/test_memory_eviction.py` (新建单测)

## 具体改动

### 1. 新建 `eviction.py`
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/eviction.py`
- 实现 `find_near_duplicate()`：基于混合分词与 Dice 相似度算法，检测新事实与已有条目的语义相似性；
- 实现 `evict_lowest_priority_items()`：按保护分类、人工确认状态、更新时间戳综合判定，当超过配额时平滑淘汰优先级最低项；
- 实现 `trim_bounded_list()`：对来源追踪与已删除墓碑执行 FIFO 滑动裁剪，杜绝元数据过度膨胀。

### 2. 改造 `MemoryStorage.propose` 接入 Fact Dedup
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- 提取候选时，先调用 `find_near_duplicate` 比对现有事实与候选：
  - 命中已有事实时，刷新其 `updated_at` 时间戳（强化事实）；
  - 命中已有候选时，提升其 `revision`，避免往列表中塞入重复的同义候选；
- 候选超出上限时自动淘汰低优先级候选，不再粗暴 break。

### 3. 改造 `MemoryStorage._save` 实现平滑淘汰
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- 彻底废除 `raise DocumentError("memory_capacity_exceeded", 409)` 抛错逻辑；
- 事实或候选数量超过 100 时，自动调用 `evict_lowest_priority_items` 淘汰最低分项，保持容量为 100；
- 对 `sources` 与 `deleted_digests` 自动进行滑动裁剪，系统在长期运行下永不发生容量爆满拒服。

## 验证
- [x] 单元测试通过：`test_memory_eviction.py` 5 项测试全部通过；
- [x] 平滑淘汰验证：`test_save_evicts_overflow_facts_gracefully` 验证在灌入 105 条事实、2100 个 sources 时，自动平滑裁剪至 100 条事实与 1800 个 sources，无任何 409 异常；
- [x] 全量契约验证：`test_memory_contract.py` 所有用例保持通过。
