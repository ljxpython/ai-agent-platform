# Implementation Record: Phase 1 工具输出溢出落盘与物理截断防爆治理

- **日期：** 2026-10-28
- **责任人：** @老王
- **涉及服务：** `runtime-service`
- **关联 Task：** T1.1, T1.2, T1.3, T1.4

---

## 1. 改动背景与病灶
在案发现场二（会话 `e5492054`，全库代码剖析）与案发现场一（会话 `6f09c502`，灵巧手深度调研）中，由于：
1. 128K 窗口大模型在 `resolve_tool_output_limit` 中被计算出虚高的单工具限额（`tool_output_limit = 7270 tokens ≈ 29,080 字符`），导致 9.5KB 的 `github_query`、8KB 的 `search_web` 均被视为“合规小消息”直接放行进上下文；
2. `ResultFilesystemMiddleware._guard_message` 存在严重盲区：仅针对 `TOOLS_EXCLUDED_FROM_EVICTION`（7 个内置文件操作工具）做物理截断，将 `execute`（shell 执行）、`github_query`、`search_web` 等所有外部重度工具完全排除在外；
3. 导致 Agent 连续调用几十次工具后，累积倒出近 40 万字符，直接冲破上下文触发阈值，引发连续 6 次恶性循环压缩。

---

## 2. 核心改动明细

### 2.1 动态支持单工具驱逐门槛配置 (`conversation_offloading.py`)
- **文件**：`apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`
- **函数**：`resolve_tool_output_limit`
- **改动**：
  引入环境变量 `AGENT_TOOL_TOKEN_LIMIT_BEFORE_EVICT`。未配置时保持原有自适应计算；配置时（默认推荐 1200 Tokens，约 4800 字符），强制以该阈值作为工具输出驱逐门槛。
  超过此门槛的工具输出自动触发父类 `FilesystemMiddleware` 的持久化落盘机制，写入 `/large_tool_results/{digest}/{call_id}`，并回传带前后切片预览与路径指针的轻量 ToolMessage。

### 2.2 扩展 `ResultFilesystemMiddleware` 兜底防护与截断增强 (`filesystem.py`)
- **文件**：`apps/runtime-service/src/runtime_service/middlewares/filesystem.py`
- **类/函数**：`ResultFilesystemMiddleware._guard_message`, `truncate_tool_output_text`
- **改动**：
  1. `truncate_tool_output_text` 修正单行与多行提示模板，统一显式注入 `tool_name` 标识；
  2. `_guard_message` 引入 `AGENT_TOOL_OUTPUT_MAX_CHARS`（默认 4800 字符）作为物理截断上限；
  3. 彻底打破仅排除 7 个工具的盲区，对未被父类驱逐的 `execute` 或其他重度工具实施 Head+Tail 物理截断兜底，坚决封死任何漏网大消息。

### 2.3 环境变量规范化 (`.env`, `.env.example`)
- 在 `apps/runtime-service/.env` 与 `.env.example` 中实装：
  ```bash
  AGENT_TOOL_TOKEN_LIMIT_BEFORE_EVICT=1200
  AGENT_TOOL_OUTPUT_MAX_CHARS=4800
  ```

---

## 3. 验证结果
- **单元测试**：
  - `apps/runtime-service/tests/middlewares/test_tool_output_budget.py`：新增 3 项针对 `AGENT_TOOL_TOKEN_LIMIT_BEFORE_EVICT`、`AGENT_TOOL_OUTPUT_MAX_CHARS` 以及 `execute` 拦截的专项测试，全量 33 项单测 100% 绿灯通过；
  - `apps/runtime-service/tests/middlewares/test_conversation_offloading.py`：全量 32 项单测 100% 绿灯通过；
  - 合计 65 项单测全部 PASS。
