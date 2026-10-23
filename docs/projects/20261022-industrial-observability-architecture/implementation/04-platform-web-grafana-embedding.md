# Platform Web 内嵌工业级指标大盘（方案 B）

## 改动时间
2026-10-22

## 相关任务
- Task 5.1: 远端 Grafana 安全嵌入与免密配置
- Task 5.2: Platform Web 指标大盘内嵌组件与导航

## 改动文件
- `deploy/observability/docker-compose.yml`
- `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.vue`
- `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.spec.ts`
- `apps/platform-web/src/router/routes.ts`
- `apps/platform-web/src/modules/system-governance/pages/SystemGovernancePage.vue`

## 具体改动

### 1. 远端 Grafana 安全嵌入配置与平滑热更
- **位置：** `deploy/observability/docker-compose.yml` 与 `sshmy1:/opt/observability/docker-compose.yml`
- **改动理由：** 浏览器内嵌 iframe 要求目标站点不能携带 `X-Frame-Options: deny` 响应头，且内嵌浏览时需要免去弹窗登录阻断。
- **配置项：**
  - `GF_SECURITY_ALLOW_EMBEDDING=true`：允许跨域 iframe 嵌入。
  - `GF_AUTH_ANONYMOUS_ENABLED=true`：开启匿名只读访问。
  - `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`：严格限定为 Viewer 角色，禁止未授权写操作。
- **验证证据：**
  - 远端执行 `docker compose up -d grafana` 平滑重建容器，仅耗时 1s。
  - `curl -sI 'http://127.0.0.1:3000/d/ai-platform-overview/ai-agent-platform-infrastructure?orgId=1&kiosk'` 返回 `HTTP/1.1 200 OK`，`X-Frame-Options` 成功消除。

### 2. 前端内嵌页面 ObservabilityDashboardPage.vue
- **位置：** `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.vue`
- **体验设计：**
  - **一体化视觉（Kiosk Mode）：** 拼接 URL 携带 `&kiosk` 参数，自动隐藏 Grafana 自带的大黑顶栏和左侧抽屉，直接融入平台前端风格。
  - **主题深浅双向联动：** 实时监听 Pinia `themeStore.mode`（`dark` / `light`），动态传递 `&theme=${mode}`，实现与平台整体皮肤同步。
  - **加载态与骨架屏：** 初始显示优雅的加载动画遮罩，iframe `@load` 触发后平滑过渡显示。
  - **高频操作支持：** 顶部操作区提供“刷新图表”、“全屏看板（支持原生 Fullscreen API）”以及“独立窗口打开（外链跳至原生 Grafana 控制台）”。
  - **配置回退机制：** 优先读取 `import.meta.env.VITE_GRAFANA_DASHBOARD_URL`，默认回退至生产部署大盘地址。

### 3. 路由与菜单挂接
- **位置：** `apps/platform-web/src/router/routes.ts`
- **改动详情：**
  - 在 `workspaceChildren` 中注册 `/workspace/observability` 路由，权限要求为 `platform.config.read`。
  - 在 `navigation` 映射表中将 `workspace-observability` 挂载在「平台管理」分组下，标签为“指标大盘”，图标为 `activity`。
  - 在既有的 `SystemGovernancePage.vue`（系统探测）页面顶部增加直达“指标大盘”的快捷切换按钮。

## 验证结果
1. **类型检查：** `pnpm typecheck` → **TypeScript: No errors found**。
2. **专属单元测试：** `pnpm vitest run src/modules/observability/pages/ObservabilityDashboardPage.spec.ts` → **3 passed in 8.06s (100% 绿灯)**。
3. **路由测试：** `pnpm vitest run src/router/routes.spec.ts` → **6 passed in 5.30s (100% 绿灯)**。
4. **全量前端回归：** `pnpm test:run` → **153 passed, 906 passed (100% 绿灯)**。
5. **本地服务联调：** `curl -sI http://127.0.0.1:26631/workspace/observability` 返回 `HTTP/1.1 200 OK`。
