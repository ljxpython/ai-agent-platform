# 技术方案：平台助手按 Thread 检索运行与脱敏活动摘要

## 1. 背景与问题

在现有平台助手能力中（见 [平台助手运维手册](../20261116-platform-assistant/backend-operations.md)）：
- `read_run_diagnostics` 与 `read_run_logs` 强依赖同时传入完整 36 位 `thread_id` 和 `run_id`。
- `diagnostics` 操作为保护隐私只统计消息数量（`human`/`ai`/`tool`），不输出任何工具调用名称或会话过程。
- 当用户只拿到 `thread_id`（甚至是顶栏展示的 8 位前缀）并询问“帮我查下这个会话”或“之前几轮都干了什么”时，助手缺少列出 Run 和查看脱敏活动轨迹的工具。

## 2. 跨服务契约设计

沿用既有 `Runtime -> Platform API` HMAC 回调链路（`POST /api/platform-assistant/internal/read` 与 `POST /api/platform-assistant/read`），**不新增 Delegation JWT operation 或 SSE 事件类型**（现有 `delegation-jwt.md` / `sse-event.md` 草案状态保持不变）。

### 2.1 新增 `ReadRequest.operation`

在 [contracts.py](../../../apps/platform-api/src/platform_api/modules/platform_assistant/contracts.py) 的 `ReadRequest.operation` 中新增两项：

1. `"thread_runs"`（对应工具 `list_thread_runs`）
   - **输入**：`target_thread_id`（完整 36 位 UUID）或 `query`（8–35 位十六进制短前缀，允许含 `-`，匹配 `^[0-9a-f-]{8,35}$`）。
   - **鉴权与前缀解析**：
     - 完整 UUID：沿用 `require_target_project(factory, actor, thread_id)` 核对当前用户在目标项目的成员身份与 `thread_access` 读权限。
     - 短前缀：在 `thread_access` 表按 `thread_id LIKE '<prefix>%'` 检索候选行（上限 20 条），逐条装载目标项目 `target_actor` 并经过 `thread_access.allowed(..., "read")` 与项目 `status == "active"` 过滤。
       - 0 条授权匹配：`{"match_status": "not_found", "thread_id": None, "candidates": [], "runs": []}`（不泄露未授权会话是否存在）。
       - 多条授权匹配：`{"match_status": "ambiguous", "thread_id": None, "candidates": [...], "runs": []}`，引导用户确认具体 `thread_id`。
       - 唯一授权匹配：返回 `{"match_status": "matched", "thread_id": "...", "runs": [...], "truncated": ...}`。
   - **Run 投影字段（白名单）**：每条仅包含 `run_id`、`status`、`created_at`、`updated_at`、`error_code`（仅标准错误标识，不返回原始报错堆栈）、`configuration`（`model_id` / `access_policy` / `plan_mode`）。最多返回最近 20 条。

2. `"thread_activity"`（对应工具 `read_thread_activity`）
   - **输入**：同 `"thread_runs"`（支持完整 `target_thread_id` 或 `query` 前缀）。
   - **数据来源**：先通过同一授权与解析过程定位唯一 `thread_id`，再在目标项目权限范围内调用 `target_gateway.list_thread_runs`（限 20 条）与 `target_gateway.get_thread_state`（8 秒超时保护）。
   - **严格脱敏投影**：
     - 遍历最新状态消息列表（最多取最近 200 条消息，超限时标 `truncated: true`），按 `human` 消息划分轮次（`turn_index` 1..N）。
     - 每轮仅输出：`turn_index`、`ai_messages`（计数）、`tool_calls`（仅包含经 `identifier()` 清洗的 `tool_name` 与 `status`: `"success"` / `"error"` / `"unknown"`）以及当前 `interrupts_observed` / `approval_pending` 布尔值。
     - **严禁输出**：用户提示词原文、AI 回复正文、工具输入参数（`args`）和工具返回正文。

### 2.2 权限、策略与历史撤权

- 工具覆盖映射：在 `service.py` 的 `resolve_tool_overrides` 中绑定 `"thread_runs": "list_thread_runs"` 和 `"thread_activity": "read_thread_activity"`。
- 历史回执保护：在 `evidence.py` 的 `save_evidence` 中记录解析后的 `target_thread_id`；在 `require_history_access` 中对 `"thread_runs"` 与 `"thread_activity"` 复核目标会话当前 `require_target_project` 与工具策略，撤权后历史助手会话拒绝继续读取。

### 2.3 Runtime Service 侧变更

- 在 [capabilities.py](../../../apps/runtime-service/src/runtime_service/services/platform_assistant/capabilities.py) 的 `TOOL_NAMES` 中增加 `"list_thread_runs"` 与 `"read_thread_activity"`。
- 在 [tools.py](../../../apps/runtime-service/src/runtime_service/services/platform_assistant/tools.py) 实现两项工具，通过通用参数校验辅助函数（兼容 36 位 UUID 或 8–35 位前缀，非法字符或长度不足 8 位抛出 `ToolException`）。
- 在 [prompts.py](../../../apps/runtime-service/src/runtime_service/services/platform_assistant/prompts.py) 更新排障与证据指引，明确：
  - 只拿到 `thread_id`（或 8 位前缀）时，先调 `list_thread_runs` 获取 `run_id`，再按需调用 `read_run_diagnostics` / `read_run_logs`。
  - 回答“对话里干了什么”时调用 `read_thread_activity`，并只陈述返回的结构化工具动作、轮次与 Run 状态，不得脑补正文内容。

## 3. 范围边界与取舍

- **不直接吐出原消息正文**：遵循平台助手最小暴露原则，若用户确需阅读原始聊天正文，应在前端历史会话列表中直接打开原会话。
- **独立于前端本地热修**：前端非 HTTPS 剪贴板兼容与 Runtime 非法 UUID 容错属于既有单服务缺陷修复，不在本项目规划中重复占位，但验证时确保兼容。
- **生产发布边界**：本次完成本地代码实现与自动化测试验证；是否构建发布至 `sshmy1` 另行由用户确认窗口执行。
