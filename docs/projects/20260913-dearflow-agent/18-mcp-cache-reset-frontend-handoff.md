# F15：MCP 刷新事项前端交接

## 目标

前端同事独立阅读本篇，即可判断需要接什么、复用什么、如何验收。技术取舍与任务状态以 [17 F15 评估](17-mcp-cache-reset-assessment.md)为准，总入口为 [项目总纲](README.md)。

**2026-10-10 用户已确认不开发 F15 原案，前端无需新增能力。** 不新增 MCP reset 按钮或配置页面，继续使用已存在的“同步工具目录”。后端没有计划交付 `POST /api/mcp/cache/reset`，不得按 DeerFlow URL 先接占位接口。

本轮交接评估已关闭；前端代码、测试、浏览器验收均未实施。下方 F15-F01 是未排期参考项，只有后续另行接受现有目录回归补齐时才实施。

## 方案设计

### 1. 现有接线与责任

| 文件/符号 | 当前职责 | 交接要求 |
| --- | --- | --- |
| `apps/platform-web/src/modules/control-plane/pages/ControlPlanePage.vue::refreshCatalog` | 控制面同步 Graph/工具目录，权限校验、项目选择、busy、成功/失败提示 | 复用现有页面和状态；不放入 Chat/Agent 输入框，不新建运行状态机 |
| `apps/platform-web/src/services/runtime/runtime.service.ts::refreshRuntimeTools` | 统一 platform HTTP client 调用 `POST /api/runtime/tools/refresh` | 继续使用 `platformHttpClient` 和 `buildRuntimeHeaders(projectId)`；浏览器不直连 Runtime |
| `apps/platform-web/src/modules/control-plane/pages/ControlPlanePage.spec.ts` | 现有 Graph 同步与平台 viewer 测试 | 可在原文件补工具按钮回归，不另造页面测试框架 |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/domain/models.py::RuntimeCatalogRefreshResult` | 返回安全目录同步结果 | 若未来确需显示同步时间，按真实返回字段处理；本次不要求扩展前端 DTO/界面 |

现有权限是 `platform.catalog.refresh`。项目 ID 用于受管 Runtime 请求与审计上下文；同步的仍是部署 Runtime 全局声明目录，不是“某项目的 MCP session 池”。控件沿用当前权限和有效项目规则，不能只靠按钮隐藏代替服务端权限校验。

### 2. 当前公开契约

请求：`POST /api/runtime/tools/refresh`，无业务请求体；由统一 HTTP client 附带登录认证，`x-project-id` 使用选择的有效项目 ID。

服务端成功返回示意：

```json
{
  "ok": true,
  "count": 12,
  "last_synced_at": "2026-10-10T08:00:00Z"
}
```

`count` 是同步后的 Runtime 声明数量，包含非 MCP 工具；不能叫“重连数”“已加载远端工具数”或“清理 session 数”。`last_synced_at` 可为空，现有前端 service 只声明/使用 `count`，没有必须扩充类型的需求。错误继续使用现有平台错误出口和 UI 状态，不能以捕获异常后显示成功代替结果。

此 API 不负责重读 `.env`、获取远端 schema、更新正在执行的 Run，亦不授予新的工具权限。普通 MCP 的远端工具定义在下一次执行构图时由 Runtime loader 发现，受服务器 allowlist/绑定与现有策略限制。

### 3. 交互范围

| 场景 | 接续行为 |
| --- | --- |
| 无 `platform.catalog.refresh` | 按当前页面规则不提供同步操作；不发送 mutation 请求 |
| 未选择有效项目/同步进行中 | 保持现有 disabled/busy，重复点击不产生并发同步 |
| 请求成功 | 显示真实目录数量，保留“目录已刷新”的语义；不宣称“配置已热更新”或“所有连接已关闭” |
| 请求失败 | 展示现有安全错误、解除 busy；不清空用户界面以假装目录为空，不影响正在运行的 Chat |
| 操作中组件卸载/当前权限变化 | 沿用现有 `disposed` 和权限检查，避免异步成功提示写入失效页面 |

不新增页面说明教程、Chat toast、Run badge、SSE 类型、停止/恢复动作或浏览器侧 MCP 凭据。MCP URL/headers/token 不进入前端表单、localStorage 或 Run Context。本轮也不要求修改现有“同步工具目录”文案。

## 任务拆分

- [x] **F15-F00：交接规划。** 明确没有待接 reset API，列出既有刷新入口、权限与语义；2026-10-10 完成文档。
- [ ] **F15-F01：条件回归补齐。** 仅在同事接受该测试切片后，在原 `ControlPlanePage.spec.ts` 增加工具目录成功、失败与权限用例；mock `refreshRuntimeTools`，不改生产页面。当前未实施。

用户已采纳 17 的跳过结论，前端工作量为零，F15-F01 不进入排期，也不计为本次交付的未完成任务。若后来决定真正做配置热更新，必须以新批准的后端契约重新交接，不能自行猜测 reset 响应或把成功同步当成热更新完成。

## 验证要求与记录

### F15-F01 接受后的最小验证

1. 工具目录按钮传递当前选择的项目 ID，调用一次 `refreshRuntimeTools`，成功提示使用返回的 `count`；不调用 reset URL。
2. 未选项目、busy 或无权限时不发送工具 mutation；保留现有 Graph 同步用例。
3. Promise reject 后 busy 恢复且显示错误，不显示成功、不自动重试或重新发起 Run。
4. 若改动前端生产代码，另执行对应 lint/类型检查；跨服务行为变化才追加隔离浏览器验收。

定向命令，前提是本 Worktree 前端依赖独立安装；下列命令未在本轮执行：

```bash
pnpm --dir "apps/platform-web" exec vitest run "src/modules/control-plane/pages/ControlPlanePage.spec.ts"
```

### Phase：2026-10-10 规划核对

已只读检查现有页面/service/API 返回模型与测试；确认工具同步入口存在、当前测试主要覆盖 Graph 按钮。无前端功能测试或浏览器截图，本次不将文档检查当作 UI 验收。

### Final：前端实施验收

不适用：用户已确认不开发 F15 原案，本轮没有前端实施验收。只有另行接续 F15-F01 或新的已批准界面改动时才记录真实执行结果。

## 状态

**已完成（交接评估关闭）：2026-10-10 用户确认无需新增前端能力，条件测试未排期。** 与整个 DearFlow 项目及其他前端事项的完成状态独立。
