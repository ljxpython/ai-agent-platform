# Implementation Record: Phase 2 历史工具结果动态虚拟折叠（Ephemeral Tool Pruning）

- **日期：** 2026-10-28
- **责任人：** @老王
- **涉及服务：** `runtime-service`
- **关联 Task：** T2.1, T2.2, T2.3

---

## 1. 架构目标与对标实践
在像 Cursor、Windsurf、Manus、Claude Artifacts 这样的工业级 Agent 架构中，长任务进行到中后期（例如第 40~50 步）时，早期工具执行的原始长输出（如 `ls` 列表、中间试错的错误堆栈、早期搜索的几十篇结果）对当前的即时动作决策价值已经大幅衰减。
如果每一轮都将早期全部原始工具输出喂给大模型：
1. 上下文随轮次滚雪球增长，几万到十几万 Tokens 的冗余字符导致反复触发上下文压缩；
2. 大模型的推理速度（TTFT）随 Prompt 膨胀线性恶化；
3. 大模型产生注意力分散（Lost in the Middle）。

**核心解决之道：虚拟上下文折叠（Virtual Context Folding）**
- **不可侵犯红线：** 绝不修改持久化存储（PostgreSQL Checkpoints）中的 `messages`，确保前端历史回放、审计排障与调试数据 100% 原始完整；
- **纯视口置换：** 仅在 `wrap_model_call` 拦截向 LLM 发送请求的瞬间，利用不可变 `request.override(messages=...)`，将历史工具输出置换为轻量占位符；
- **API 契约守恒：** 严格保留所有 `ToolMessage` 对象及其 `tool_call_id`、`name`、`status`，保留严格的工具配对，绝不删减节点，杜绝任何 API 报错。

---

## 2. 核心改动明细

### 2.1 纯函数虚拟折叠算法 (`tool_output_pruning.py`)
- **文件**：`apps/runtime-service/src/runtime_service/middlewares/tool_output_pruning.py`
- **函数**：`prune_messages_for_model(messages, keep_recent=4, min_chars=300)`
- **逻辑**：
  1. 识别全部 `ToolMessage` 索引；
  2. 若工具调用总数 $\le \text{keep\_recent}$（默认 4），不触发折叠，直接返回原始列表；
  3. 若工具调用总数 $> \text{keep\_recent}$，将早于保留窗口的较早工具进行折叠；
  4. 如果内容中包含已落盘文件指针（`/large_tool_results/...`），保留路径：
     `[Tool output reference: '{name}' offloaded to {file_path}. Full result ({len} chars) preserved; use read_file to inspect.]`
  5. 若为常规长文本（$> \text{min\_chars}$），折叠为：
     `[Tool output collapsed: '{name}' returned {len} chars. Full result safely preserved in database checkpoint.]`
  6. 若包含图像等多模态块（`list[dict]`），仅替换 `text` 块，多模态数据块 100% 原样保留。

### 2.2 运行时中间件集成 (`dearflow_agent/agent.py`)
- **文件**：`apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
- **挂载**：在 `dearflow_agent` 的 `middleware()` 管道中实装 `ToolOutputPruningMiddleware()`，在模型请求发送前透明执行视口精炼。

### 2.3 环境变量规范化 (`.env`, `.env.example`)
- 在 `.env` 中加入：
  ```bash
  AGENT_CONTEXT_TOOL_PRUNING_ENABLED=1
  AGENT_CONTEXT_TOOL_PRUNING_KEEP_COUNT=4
  AGENT_CONTEXT_TOOL_PRUNING_MIN_CHARS=300
  ```

---

## 3. 验证结果
- **单元测试**：
  - 新增 `apps/runtime-service/tests/middlewares/test_tool_output_pruning.py`（5 项针对保留窗口、多模态块保留、文件指针提取、异步拦截及禁用旁路的专项测试），全绿通过；
  - 全量中间件测试套件（15 个测试文件，300 项单测）**100% 全部 PASS**。
