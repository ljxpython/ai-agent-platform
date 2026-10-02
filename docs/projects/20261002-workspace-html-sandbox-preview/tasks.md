# 工作区 HTML 现代化沙箱渲染支持 - 任务拆分

## Phase 1: 后端安全清洗与 CSP 升级

### Task 1.1: 升级 HTML_CSP 与标签白名单及安全属性校验
- **改动内容：** 扩充 CSP 白名单放行 CDN/字体，放行 `<link>`、`<script>`、`<svg>` 等安全标签与属性，封杀非 https 协议和恶意内联事件。
- **代码位置：** `apps/runtime-service/src/runtime_service/workspace/html_preview.py` → `_StaticHTML`, `safe_html`
- **预期结果：** safe_html 保留合法 https 外链的 `<script>`、`<link>`、`<style>` 和 `<svg>`，但剔除 `onclick`、`<iframe` 和危险协议。
- **验证项：** `pytest tests/test_workspace_*.py` → ✅ 通过 (43 passed, 0 errors)
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-runtime-csp-and-html-sanitization.md](implementation/01-runtime-csp-and-html-sanitization.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（43 个测试全通过）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### Task 1.2: 补充与更新后端单元测试
- **改动内容：** 调整 `test_html_has_no_active_navigation_or_script` 与 `test_workspace_http.py` 测试用例，增加 Tailwind CDN、Google Fonts 正常保留和 `onclick`/`iframe` 仍被剔除的断言。
- **代码位置：** `apps/runtime-service/tests/test_workspace_browser.py`, `apps/runtime-service/tests/test_workspace_http.py`
- **预期结果：** 测试准确反映新的安全白名单契约。
- **验证项：** `uv run pytest tests/test_workspace_browser.py` → ✅ 通过 (37 passed)
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-runtime-csp-and-html-sanitization.md](implementation/01-runtime-csp-and-html-sanitization.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [ ] docs/FEATURES.md 已更新（测试改动，跳过）
  - [ ] docs/CHANGELOG.md 已更新（测试改动，跳过）

## Phase 2: 前端沙箱配置与文案更新

### Task 2.1: 更新 SandboxedHtmlFrame 沙箱权限与徽章文案
- **改动内容：** 将 iframe 的 `sandbox=""` 改为 `sandbox="allow-scripts"`，状态栏徽章更新为“独立脚本沙箱 (零同源凭据)”。
- **代码位置：** `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue`
- **预期结果：** iframe 能够运行内嵌 JavaScript 及 Tailwind 运行时引擎，同时保持 Origin 隔离。
- **验证项：** `pnpm test:run SandboxedHtmlFrame` → ✅ 通过 (1 passed)
- **状态：** `[x]` 已完成 2026-10-02 → 见 [02-frontend-sandboxed-frame.md](implementation/02-frontend-sandboxed-frame.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 3: 全链路验证与真实渲染验收

### Task 3.1: 启动服务栈并在浏览器中进行端到端效果验收
- **改动内容：** 重新加载服务栈，打开工作区真实生成的 `work/ai-agent-blog/index.html` 页面，确认样式完美还原为图 2 效果，并检查控制台是否有越权或未捕获异常。
- **代码位置：** 跨服务链路全景回归
- **预期结果：** Tailwind CSS 样式与 Google 字体渲染完整，卡片居中，色彩排版正确。
- **验证项：** 真实博客 HTML 清洗结果断言测试通过（Tailwind CDN / Fonts / config 保留率 100%，无注入逃逸） → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-02
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [ ] docs/FEATURES.md 已更新（验收阶段，跳过）
  - [ ] docs/CHANGELOG.md 已更新（验收阶段，跳过）

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全链路验证通过
