# 验证记录：平台助手按 Thread 检索运行与脱敏活动摘要

## 验收要求

1. **权限与范围隔离**：完整 `thread_id` 与 8–35 位前缀查询均只返回当前用户有 `read` 权限且属于活跃项目的会话；无权或不存在会话统一返回 `not_found`；多条匹配返回 `ambiguous` 候选列表；历史会话撤权后拒绝重开。
2. **脱敏边界**：`thread_runs` 与 `thread_activity` 绝不返回用户聊天原文、AI 回答原文、工具输入参数（`args`）或工具结果正文。
3. **跨服务联动**：Runtime 侧 `list_thread_runs` / `read_thread_activity` 通过签名回调 `POST /api/platform-assistant/internal/read` 与 Platform API 契约打通；非法入参转为 `ToolException` 不崩溃。
4. **文档规范**：`python scripts/check_docs.py` 校验通过，无本地绝对路径硬编码或死链。

---

## 阶段验证（Phase）

### 2026-11-25 · Runtime Service 工具、图执行与基线回归（Task 3）

- 范围：`apps/runtime-service` `platform_assistant` 工具、提示词与图基线测试（本地 `.venv`，MemorySaver + `BindableFakeMessagesChatModel`）。
- 执行：`cd apps/runtime-service && .venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_r0_baseline.py -q`
- 结果：**29 passed**（0 skipped / 0 failed）。覆盖 `list_thread_runs` 与 `read_thread_activity` 完整 UUID/短前缀参数归一、非法入参抛 `ToolException`、`create_platform_agent` 工具执行无崩溃及 `read_run_diagnostics`/`read_run_logs` 非法 UUID 容错。
- 未覆盖：未在本地调用真实大模型 API。

### 2026-11-25 · Platform API 契约、权限与脱敏投影回归（Task 1 / Task 2）

- 范围：`apps/platform-api` 平台助手、可观测、分叉、RunRequests 与 Thread ACL 测试（本地 `.venv`，SQLite 内存/临时文件会话库 + FastAPI `TestClient`）。
- 执行：
  1. `cd apps/platform-api && .venv/bin/python -m pytest tests/test_platform_assistant.py -q`
  2. `cd apps/platform-api && .venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_observability_api.py tests/test_thread_fork.py tests/test_run_requests.py tests/test_thread_acl.py -q`
- 结果：
  1. `test_platform_assistant.py`：**52 passed**（0 skipped）。验证 8 位前缀唯一/歧义/无权三种分支、跨项目 ACL、敏感正文与工具入参/出参零泄露、历史撤权拒绝以及 `POST /api/platform-assistant/internal/read` HMAC 回调。
  2. 扩大回归：**117 passed, 3 skipped, 5 subtests passed**（3 skipped 为既有环境条件跳过）。

---

## 整体验收（Final）

### 2026-11-25 · 跨进程真实 HTTP HMAC 最短链路验收（Task 4）

- 范围：`runtime-service` 真实 `make_tools` 工具调用 → 真实本机回环 TCP HTTP + HMAC-SHA256 签名请求 `POST /api/platform-assistant/internal/read` → `platform-api` FastAPI 路由与 SQLite `ThreadAccessRecord` / `AssistantEvidenceRecord` 落库与脱敏响应（Runtime 上游网关使用可控 Mock `list_thread_runs` 与 `get_thread_state` 注入含敏感文本测试载荷）。
- 执行：启动本地 `uvicorn` FastAPI 进程并通过 `apps/runtime-service/.venv/bin/python` 调用 `list_thread_runs("70f0ab34")` 与 `read_thread_activity("70f0ab34")`。
- 结果：**通过（CROSS_SERVICE_E2E_OK）**，两次调用均命中目标会话 `70f0ab34-bd4e-439b-b8ce-20a3957557f9`、写入独立 `evidence_id`，返回结构化 `run_id` 与脱敏 `tool_calls`，测试载荷中的 `RAW_USER_TEXT_DO_NOT_LEAK` / `RAW_AI_TEXT_DO_NOT_LEAK` / `RAW_ARG_DO_NOT_LEAK` / `RAW_OUT_DO_NOT_LEAK` 全部被剔除。
- 未覆盖：尚未连接线上真实 LLM 跑前端浏览器全套对话；`ruff` 未在当前 `.venv` 中安装。

### 2026-11-25 · 生产部署与服务实时读回（sshmy1）

- 范围：备份原文件后增量同步 `platform-api`（`contracts.py`/`diagnostics.py`/`evidence.py`/`service.py`）与现役 `runtime-service`（`capabilities.py`/`prompts.py`/`tools.py`），并重新打包同步 `platform-web` 静态产物至 `/www/wwwroot/agent-platform`，确认零活动 Run 后重启三服务。
- 执行：重启 `agent-runtime-api`（PID `3975735`）、`agent-runtime-worker`（PID `3975737`）、`agent-platform-api`（PID `3975736`），均 `active (running)` / `NRestarts=0`；回环验证 `/_system/probes/ready`（200）、Nginx 首页（200）及 `admin` 调用 `POST /api/platform-assistant/read`（`operation="thread_runs"` 与 `"thread_activity"`，`query="70f0ab34"`）。
- 结果：**200 OK**，命中 `70f0ab34-bd4e-439b-b8ce-20a3957557f9`，返回 6 次 Run 与 6 轮脱敏工具清单（无正文或参数泄露）。
- 未覆盖：用户浏览器前端点击复制与真实大模型对话交互待用户实测。
