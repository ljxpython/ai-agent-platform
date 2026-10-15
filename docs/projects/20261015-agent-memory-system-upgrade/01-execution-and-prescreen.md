# 记忆系统架构升级 - 01 执行流解耦与 Prescreen 成本门禁

## 1. 目标与背景

当前平台在 `MemoryContextMiddleware.aafter_agent` 中以同步阻塞方式调用大模型进行结构化候选抽取（`Candidates`），导致主对话请求在生成完毕后依然卡顿 2~5 秒（甚至面临 180s deadline 超时）。同时，无论用户是打招呼、问天气还是执行普通代码，每一轮对话都会无差别触发昂贵的结构化抽取 LLM，造成严重的 Token 资金浪费。

本专题目标：
1. 实现主对话执行流与记忆提取的**完全异步解耦**，对话结束立即响应前端，主请求延迟降低到毫秒级；
2. 借鉴 DeerFlow 确定性信号感知与成本预筛设计，实现 **Prescreen 成本门禁**，过滤 50% 以上无持久记忆价值的对话轮次。

---

## 2. DeerFlow 怎么做的 vs 我们的差距与借鉴

### DeerFlow 设计
- **异步队列 (`MemoryUpdateQueue`)**：Middleware 在 Agent 结束时仅捕获消息并推入防抖队列，由后台独立 worker 处理，彻底与主执行流隔离。
- **确定性信号检测 (`detect_signals`)**：在调用模型前，用极快的正则检测用户是否包含纠错（Correction，如"不对，其实我是..."）或强化（Reinforcement，如"记住这一点"）信号。
- **Prescreen 成本门禁 (`prescreen`)**：在调用大模型提取前，先快速评估该文本是否包含"值得持久化记住的稳定事实"，若无则直接判定为 Skip，仅推进水位不调用大模型。

### 我们的差距
- 我们的 `MemoryContextMiddleware.aafter_agent` 是纯串行 `await model.ainvoke(...)`，直接拖慢主响应；
- 没有任何预筛，即使用户说"你好"或"好的收到"，只要开启了 `automatic_candidates`，就无脑发起抽取调用。

### 借鉴与本土化改造
- **去除 DeerFlow 的业务绑定**：DeerFlow 依赖本地单机进程内的 `threading.Timer`，在多 worker 或容器化环境下容易产生状态漂移。我们基于 `asyncio.create_task` + 平台现有的后台任务跟踪器机制，既轻量又无缝嵌入现有容器运行时；
- 保留并继承三元组安全上下文（`tenant_id, project_id, user_id`），异步任务必须安全闭包携带上下文，严防越权。

---

## 3. 具体改动位置与代码实现设计

### 3.1 运行时层 (`runtime-service`)

#### A. 新建 Prescreen 成本门禁模块
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prescreen.py`
- **核心函数：**
  ```python
  def prescreen_conversation(messages: list[dict]) -> tuple[bool, str]:
      """
      评估对话是否具备持久记忆提取价值。
      返回: (should_extract: bool, reason: str)
      """
  ```
- **规则矩阵：**
  1. **极短文本过滤**：用户输入去除空白字符后小于 8 个字符（如"好的"、"收到"、"哈哈"），直接 Skip（`reason="too_short"`）；
  2. **非自然语言过滤**：纯代码片段、纯 JSON、纯命令执行（如 `cat xxx`），直接 Skip（`reason="code_or_command"`）；
  3. **确定性强化信号识别**：正则匹配显式偏好词（如 `"默认用..."`, `"记住..."`, `"不要再..."`, `"我喜欢..."`, `"我偏好..."`），命中直接标记为必须提取（`reason="explicit_signal"`）；
  4. **常规问答无偏好过滤**：若只有疑问句且无个人代词（"我"、"我们"），直接 Skip（`reason="general_query"`）。

#### B. 改造中间件为非阻塞异步派发
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`
- **改动位置：** `MemoryContextMiddleware.aafter_agent`
- **改动逻辑：**
  - 在 `aafter_agent` 内部，完成 PII 校验与基础上下文提取后，调用 `prescreen_conversation(selected)`；
  - 若 Prescreen 判定为 Skip，直接调用 `store.finish_extraction(..., status="skipped", reason=...)` 推进水位并记录指标，耗时 < 5ms；
  - 若需要提取，构造包含全部必要上下文的 Task Payload，通过 `asyncio.create_task(self._async_extract_and_propose(...))` 触发后台执行，`aafter_agent` 立即 `return`，绝不 `await` 抽取结果！

---

## 4. 任务拆分

### Task 1.1: 创建 prescreen.py 规则初筛
- **改动内容：** 实现基于确定性强化信号和纠错信号的快速扫描，识别低价值短语直接短路。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prescreen.py` → `prescreen_conversation()`
- **预期结果：** 短文本与纯指令快速返回 `(False, "too_short" | "code_or_command")`，显式偏好正常放行。
- **验证项：** `pytest test_memory_prescreen.py` → ✅ 通过 (6 passed)
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/01-execution-and-prescreen.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新
  - [ ] CONTEXT.md 已更新（跳过，待子专题全部完成统一更新）
  - [ ] docs/FEATURES.md 已更新（跳过，内部优化）
  - [ ] docs/CHANGELOG.md 已更新（跳过，内部优化）

### Task 1.2: 重构 MemoryContextMiddleware 为非阻塞异步派发
- **改动内容：** 剥离 `aafter_agent` 内同步阻塞的 LLM 调用，采用后台任务异步执行，并提供 `drain_tasks` 排空机制。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py` → `MemoryContextMiddleware.aafter_agent()`
- **预期结果：** 主对话响应毫秒级释放，后台协程异步提取并落库。
- **验证项：** `pytest test_memory_prescreen.py -k "test_async_non_blocking_dispatch_and_drain"` → ✅ 通过 (耗时 < 0.05s)
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/01-execution-and-prescreen.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

### Task 1.3: 提取状态与错误隔离加固
- **改动内容：** 后台任务全局异常捕获，确保不产生未捕获 task 异常，错误自动回写 `status="failed"`。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py` → `_async_extract_and_propose()`
- **预期结果：** 遇到网络超时或调用失败时，平稳处理并持久化错误状态。
- **验证项：** `pytest test_memory_contract.py` 现有测试 100% 保持通过 → ✅ 通过 (15 passed)
- **状态：** `[x]` 已完成 2026-10-15 → 见 implementation/01-execution-and-prescreen.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] 状态已更新

---

## 5. 验证要求与记录

### 验证记录
#### 2026-10-15 验证
- ✅ `test_detect_signals` 与 `test_prescreen_conversation_*` 6 项测试全部通过；
- ✅ `test_async_non_blocking_dispatch_and_drain` 非阻塞测试通过，主协程返回耗时 < 5ms；
- ✅ `test_memory_contract.py` 15 项原有契约测试全部通过。

## 状态
done
