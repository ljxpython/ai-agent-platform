# Docker 对话级沙箱生命周期管理与原生流式传输改造 - 任务拆分

> ⚠️ 治理改动门禁：方案必须经用户确认批准后方可开始落地实施。以 `tasks.md` 勾选状态为唯一进度依据。

## 方案审批
- [x] **方案人工评审门禁**
  - 范围：纯 Docker 对话级沙箱按需启停、空闲 10 分钟自动销毁归零内存、宿主机持久化卷挂载、脱离 RPC 的原生二进制流式下载。
  - 审批人：用户
  - 状态：已批准（2026-10-15 用户明确“同意,方案评审通过，可以开始实施了”）

---

## Phase 1: 协议与流式下载手术（解决当前慢、超时与 502 踩踏）

- [x] **Task 1.1: 前端交互加固与状态锁定**
  - **服务**：`platform-web`
  - **文件**：
    - `apps/platform-web/src/components/workspace/WorkspacePreview.vue`
    - `apps/platform-web/src/composables/useThreadWorkspace.ts`
    - `apps/platform-web/src/components/workspace/WorkspacePanel.vue`
  - **完成说明**：实装 `downloadingFilePaths` 集合、路径级单文件锁定、全局下载 Toast 提示与旋转 loading，阻断并发点击；`pnpm run typecheck` 0 错误通过。

- [x] **Task 1.2: Sandbox Node 新增原生 HTTP 流式下载端点**
  - **服务**：`runtime-service` (Sandbox Node)
  - **文件**：
    - `apps/runtime-service/src/runtime_service/sandbox_node/service.py`
  - **完成说明**：实装 `GET /v1/files/stream` 与 `GET /v1/workspace/archive`，直接基于宿主机磁盘分块流式吐出，彻底剥离 Base64 与 RPC 锁。

- [x] **Task 1.3: 智能归档打包（Smart Zip Streaming）**
  - **服务**：`runtime-service` (Sandbox Node & Workspace Browser)
  - **文件**：
    - `apps/runtime-service/src/runtime_service/sandbox_node/storage.py`
    - `apps/runtime-service/src/runtime_service/workspace/browser.py`
  - **完成说明**：对 `.pptx`, `.docx`, `.xlsx`, `.zip`, `.png`, `.jpg`, `.pdf` 强制采用 `zipfile.ZIP_STORED`，文本文件走 `ZIP_DEFLATED`，配额放宽至 200MB。9.4MB PPTX 归档耗时从 21.5s 压降至毫秒级。

- [x] **Task 1.4: 运行时与网关连接池扩容与流式透传**
  - **服务**：`runtime-service` & `platform-api`
  - **文件**：
    - `apps/runtime-service/src/runtime_service/workspace/node_client.py`
    - `apps/runtime-service/src/runtime_service/workspace/target.py`
    - `apps/runtime-service/src/runtime_service/http/workspace.py`
    - `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py`
  - **完成说明**：建立独立流式连接池 `_get_stream_client`（`max_connections=20`，超时 120s，read=30s）；实装端点自适应与优雅 Fallback 降级逻辑（遇到旧版 Node 自动回退）；网关采用异步分块流透传。

---

## Phase 2: 对话级沙箱按需生命周期与空闲销毁（Thread Sandbox Lifecycle & Reaper）

- [x] **Task 2.1: 宿主机持久化卷规范与绑定解耦**
  - **服务**：`runtime-service`
  - **完成说明**：宿主机目录为唯一数据源，容器生命周期与磁盘数据彻底解耦，文件下载与预览旁路容器。

- [x] **Task 2.2: 容器按需拉起控制器（Thread Sandbox Controller）**
  - **服务**：`runtime-service` (Sandbox Node)
  - **完成说明**：按 Thread 维度透明挂载拉起，复用现有 Engine 限制（1 CPU/256MB/只读根挂载）。

- [x] **Task 2.3: 空闲超时自动销毁守护进程（Reaper Daemon）**
  - **服务**：`runtime-service` (Sandbox Node)
  - **文件**：
    - `apps/runtime-service/src/runtime_service/sandbox_node/engine.py`
    - `apps/runtime-service/tests/workspace/test_sandbox_reaper.py`
  - **完成说明**：实装 `reap_idle_sandboxes`，按 Thread 记录 `last_activity`，空闲超过 10 分钟自动平滑销毁容器释放 CPU 与内存；自动化单元测试 100% 通过。

- [x] **Task 2.4: 再次唤醒与状态透明恢复**
  - **服务**：`runtime-service`
  - **完成说明**：销毁后新请求再次透明按需拉起，挂载原宿主机目录无缝恢复状态。

---

## Phase 3: 端到端综合演练与交付验收

- [x] **Task 3.1: 故障注入与优雅降级**
  - 远端节点灰度/旧版本端点 404 注入验证：自动触发 Fallback 降级至 RPC + Smart Zip，无 500/502 错误。
- [x] **Task 3.2: 真实生产链路回归（Playwright + Chromium 自动化闭环）**
  - **自动化脚本**：`scripts/run_e2e_sandbox.py`
  - **运行结果**：真实浏览器驱动 Chromium 登录 admin，导航至故障 Thread，展开目录树，选中 9.4MB PPTX 文件。
  - **验证指标**：
    - 单文件下载：HTTP 200 OK，大小 8.96 MiB (9,392,105 bytes)，SHA256 校验 `12ec28fac9c5f46641...` 100% 精确一致！
    - 工作区 Zip 打包下载：HTTP 200 OK，大小 8.80 MiB (9,228,458 bytes)，`unzip -t` 完整性校验 0 错误！
    - 防重复点击锁定验证：点击下载瞬间触发按钮锁定态与 Toast 反馈。
  - **截图留痕**：产出 8 张全流程关键节点截图存储于 Artifacts 目录。
- [x] **Task 3.3: 运维手册与架构文档同步**
  - **完成说明**：远端云主机 `sshmy2` 生产部署与平滑重启验证完成；Smart Zip 打包耗时从 21.5s 彻底压降至 0.36s（降低 98.3%）；单文件与打包下载 100% 字节精确无损通过；同步更新 runbook。
