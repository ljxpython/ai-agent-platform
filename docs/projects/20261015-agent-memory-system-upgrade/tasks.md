> ⚠️ 本文档已拆分为多专题模板，导航入口见 [README.md](README.md)，本文档不再维护。

# 记忆系统架构升级 - 任务拆分

## Phase 1: 异步解耦与成本门禁 (P0 核心破局)

### Task 1.1: 记忆提取异步化解耦
- **改动内容：** 改造 `MemoryContextMiddleware.aafter_agent`，将模型结构化抽取从主执行事件循环中移出，改由独立的后台协程（配合任务跟踪器或现有后台管理机制）触发执行，主请求处理完成立即释放。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py` → `MemoryContextMiddleware.aafter_agent`
- **预期结果：** 对话结束时无需等待提取模型响应，主对话响应延迟减少 2~5 秒；后台提取正常将候选写入数据库。
- **验证项：** 运行单元测试验证 `aafter_agent` 返回时间在 10ms 以内，且后台任务顺利完成候选提案。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 1.2: Prescreen 成本预筛选模块实现
- **改动内容：** 建立预筛选门禁，通过确定性规则与关键词检测（如纠错、明确习惯表达、指令模式），在调用 LLM 提取前对无价值输入（打招呼、纯检索、极短回复）进行快速短路过滤。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prescreen.py` (新建)
- **预期结果：** 纯问答和短文本跳过 Extraction LLM 调用，减少不必要的 Token 开销。
- **验证项：** 编写针对各类典型短句（"好的"、"收到"、"查询天气"）与明确偏好（"以后默认用 Python 回答"）的单元测试，验证短路率。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 1.3: 提取状态与错误隔离加固
- **改动内容：** 确保异步提取过程中的任何异常（网络超时、模型不可用）均被安全截获并写入 extraction 元数据，杜绝影响任何用户会话状态。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage.finish_extraction`
- **预期结果：** 提取异常记录到 `extraction.error_code`，系统平稳运行。
- **验证项：** 注入异常模拟提取失败，验证数据库状态与日志输出正确。
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

---

## Phase 2: 检索算法升级 (P1 体验提升)

### Task 2.1: Token IDF 词频与相关性重构
- **改动内容：** 替换当前 `MemoryStorage.context()` 中的纯 2-gram 字符集合匹配，实现基于 Token 覆盖与逆文档频率（IDF）加权的分数计算。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/relevance.py` (新建) & `memory.py`
- **预期结果：** 关键词得分具备区分度，低频关键概念（如特定语言、技术栈）比高频常用词拥有更高的匹配权重。
- **验证项：** 编写词法相关性测试，验证高权重专业词排在通用词前列。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 2.2: MMR (最大边际相关性) 多样性选择
- **改动内容：** 引入 MMR 贪婪选择算法，在每次挑选下一条事实时，同时衡量与查询的相关性以及与已选事实集合的差异性，防止同类事实挤占上下文。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage.context`
- **预期结果：** 在 4000 字符预算内，选出的前 10 条事实覆盖多个不同维度。
- **验证项：** 构造 5 条高度同质的偏好与 3 条不同领域的偏好，验证 MMR 能选出多元化结果。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

---

## Phase 3: 容量治理与近重复去重 (P1 稳定性提升)

### Task 3.1: Fact Dedup 近重复检测与合并
- **改动内容：** 在 `propose` 处理候选时，基于 token-Jaccard 相似度比对现有事实与候选。若发现高度同义的事实，改为置信度叠加与时间戳更新，避免盲目追加。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage.propose`
- **预期结果：** 相同意思的不同表述自动合并，避免候选列表出现大量同质噪音。
- **验证项：** 提交两个表述不同但语义一致的偏好，验证合并逻辑生效。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 3.2: 软淘汰 (Eviction) 替换硬上限抛错
- **改动内容：** 废除容量达 100 条直接报 409 异常的逻辑，实现结合置信度、新鲜度与访问频次的淘汰算法，当超出警戒容量时自动淘汰最弱项。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py` → `MemoryStorage._save` & 淘汰调度
- **预期结果：** 容量满时自动平滑腾出空间，系统永不因容量打满而拒服。
- **验证项：** 灌入 105 条事实，验证第 100 条之后低价值事实被自动淘汰，服务正常响应。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

---

## Phase 4: 全量回归与性能验证 (P1 交付验收)

### Task 4.1: 单元与集成测试全量验证
- **改动内容：** 完善针对异步队列、Prescreen、MMR 以及 Eviction 的单元与集成测试，覆盖并发争用与边界异常。
- **代码位置：** `apps/runtime-service/tests/services/dearflow_agent/`
- **验证项：** 运行 `pytest` 确保所有用例 100% 通过。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 4.2: 性能与效果基准对照 (Benchmarking)
- **改动内容：** 对比改动前后的对话完成耗时（Latency）、提取 API 调用次数及 Token 消耗率。
- **验证项：** 输出基准测试报告，验证延迟下降与成本节省指标。
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

---

## 进度追踪
- [ ] Phase 1: 异步解耦与成本门禁
- [ ] Phase 2: 检索算法升级
- [ ] Phase 3: 容量治理与近重复去重
- [ ] Phase 4: 全量回归与性能验证
