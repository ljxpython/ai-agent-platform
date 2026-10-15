> ⚠️ 本文档已拆分为多专题模板，导航入口见 [README.md](README.md)，本文档不再维护。

# 记忆系统架构升级 - 整体方案

## 背景

当前平台的记忆模块（`dearflow_agent` 体系）虽然具备 PostgreSQL 事务锁、三元组租户隔离（`tenant/project/user`）以及人工采纳审核（Human-in-the-loop）的基础能力，但对比参考项目 `deer-flow`（字节跳动开源 Agent 平台）的 DeerMem 系统，存在明显的架构与工程瓶颈：

1. **执行流同步阻塞**：`MemoryContextMiddleware.aafter_agent` 钩子中同步调用大模型进行结构化提取，主请求必须长时间等待（受 180s deadline 约束），严重恶化端到端响应延迟与用户体验。
2. **检索算法粗糙单薄**：`MemoryStorage.context()` 依赖简单的正则分词与 2-gram 字符集合交集进行匹配，缺乏 IDF 权重与多样性去重机制（MMR），容易被同一类高频偏好霸占 Token 预算。
3. **容量治理死板僵硬**：100 条事实 / 100 条候选的硬上限一旦达到，直接抛出 `409 memory_capacity_exceeded` 异常或进入停机维护模式，缺乏自动化淘汰（Eviction）、陈旧度审查（Staleness Review）与近重复合并（Dedup）。
4. **Token 开销高昂**：无脑对每一轮对话调用昂贵的结构化提取大模型，缺乏对寒暄、任务型指令的轻量级预筛选（Prescreening）机制。

## 目标

1. **响应提速**：解耦主执行流与记忆提取，将主请求收尾延迟降至毫秒级（提取操作下沉至后台）。
2. **成本节省**：引入 Prescreen 成本预筛与确定性信号感知，预计削减 50% 以上无意义的 Extraction LLM 调用。
3. **召回质量提升**：实现轻量级 MMR 多样性重排算法与 IDF 权重，确保注入 System Prompt 的 4000 字符内事实具备高信息密度与多维度覆盖。
4. **自治生命周期**：实现近重复去重合并与基于置信度/热度的平滑淘汰，杜绝人工反复清理或容量打满拒服的情况。
5. **保持合规底座**：百分之百继承现有的 PostgreSQL 乐观锁、租户项目用户三元组隔离及人工候选审核采纳安全线。

---

## 方案设计

### 整体架构演进

```
[ 用户对话请求 ]
       │
       ▼
[ Lead Agent 执行链路 ] ── (读取注入) ──> [ Context 检索器: MMR + IDF 重排 (内存/PG混合) ]
       │
  (对话生成结束)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼ (解耦非阻塞派发)
[ SSE 流式正常结束响应前端 ]      [ Background Memory Queue (后台异步队列) ]
                                         │
                                         ▼
                               [ Prescreen 成本门禁: 规则/信号判定 ]
                                         │
                         ┌───────────────┴───────────────┐
                         ▼ (无价值)                      ▼ (有稳定偏好/修正信号)
                     [ 直接跳过 ]              [ Extraction LLM 抽取 ]
                                                         │
                                                         ▼
                                               [ Fact Dedup 近重复检测 ]
                                                         │
                                                         ▼
                                               [ 写入候选区 Candidates ]
                                               (超限自动触发 Eviction 平滑淘汰)
```

---

### 关键改动点

#### 1. 后台异步解耦与任务编排
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`
- **改动：**
  - 在 `aafter_agent` 中剥离 `await self.model.with_structured_output(...).ainvoke(...)` 同步调用；
  - 改为构造异步提取 Payload，利用安全派发通道（`asyncio.create_task` 配合受控 Worker 池，或平台异步后台任务管理器）执行；
  - 任务上下文完整捕获当前 `tenant_id`, `project_id`, `user_id`, `thread_id`, `run_id` 及消息快照，切断对当前请求生命周期的强绑定。
- **理由：** 严格遵循非阻塞原则，释放主对话执行链。

#### 2. Prescreen 成本预筛选门禁
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prescreen.py` (新增)
- **改动：**
  - 实现基于规则与正则的轻量级检测器（`detect_memory_signals`），识别显式纠错（"不对"、"其实我更倾向于"）、强化表达（"记住这一点"、"以后默认使用"）等核心意图；
  - 判定对话轮次是否为纯代码生成、简短礼貌用语（<10个字符）、纯工具流水或问答，若未检出潜在持久事实，直接短路（Skip），记录指标并推进水位。
- **理由：** 阻断无效的大模型调用，大幅降低运营成本。

#### 3. MMR (Maximal Marginal Relevance) 多样性检索算法
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage.context()`
- **改动：**
  - 移除简陋的 2-gram 集合长度计分；
  - 引入词频与逆文档频率（IDF）加权：针对 Query 计算各候选事实的关键词匹配得分；
  - 引入 MMR 贪心选择策略：每次迭代选择与 Query 高度相关且与已选事实集合重合度最低的项，结合多样性惩罚权重（$\lambda = 0.7$）；
  - 保留 4000 字符硬预算与 HTML 字符安全转义。
- **理由：** 保证注入模型上下文的事实全面且不重复，消除单一类别偏好霸屏。

#### 4. 近重复合并 (Dedup) 与容量平滑淘汰 (Eviction)
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`
- **改动：**
  - **近重复合并**：在 `propose` 阶段，利用 token-Jaccard 相似度检测新候选是否为已有候选或已有事实的同义变体。若相似度超过阈值（如 0.8），直接更新时间戳与置信度，不新增条目；
  - **容量平滑淘汰**：当 facts 或 candidates 数量逼近限制（如达到 90 条预警线）时，不再抛出 `memory_capacity_exceeded` 异常，而是按综合评分公式淘汰最弱项：
    $$\text{Score} = w_1 \cdot \text{Confidence} + w_2 \cdot \text{Recency} + w_3 \cdot \text{AccessCount}$$
- **理由：** 打造具备自我代谢能力的自循环记忆系统。

---

## 链路影响

### 受影响的调用链路
```
Web 前端 (发起对话) ──> platform-api (网关鉴权) ──> runtime-service (LangGraph 执行)
                                                            │
                                                   (完成主回答并推流结束)
                                                            │
                                                   (后台解耦 Worker 处理记忆抽取)
                                                            │
                                                   PostgreSQL (更新候选与状态)
```

### 契约变更
- **内部契约**：`MemoryStorage.propose` 与 `change` 接口增加支持近重复合并返回值与淘汰统计；
- **对外 API**：`GET /api/langgraph/dear/memory` 返回体中新增 `stats` 字段（展示当前活跃容量比例、淘汰计数与预筛选命中率），保持对已有前端字段的向后兼容。

---

## 风险和依赖

- **并发竞争风险：** 异步提取落库与用户在前端手动 Accept/Delete 可能存在轻微时序竞争。
  - **应对：** 充分利用现有基于 `epoch` 和 `revision` 的 PostgreSQL Advisory Lock 机制，一旦检测到版本冲突，自动丢弃陈旧提取结果。
- **异步任务生命周期依赖：** 服务实例重启或 Pod 滚动更新时，内存中未完成的提取任务可能丢失。
  - **应对：** 提取任务属于 Best-effort 性质，即使丢失单次提取，不影响主数据一致性；关键轮次依赖下一轮对话的增量水位兜底。

---

## 实施计划

1. **Phase 1: 异步解耦与成本门禁（P0 核心破局）**
   - 提取逻辑异步化重构；
   - Prescreen 规则预筛门禁实现与接入。
2. **Phase 2: 检索算法升级（P1 体验提升）**
   - 实现 Token IDF + MMR 多样性检索器；
   - 重构 `MemoryStorage.context()` 与多维度召回。
3. **Phase 3: 容量治理与近重复去重（P1 稳定性提升）**
   - 近重复检测与置信度合并逻辑；
   - 淘汰机制与平滑容量管理。
4. **Phase 4: 全链路回归与基准测试（P1 交付验收）**
   - 端到端验证与 Token/延迟指标对比。
