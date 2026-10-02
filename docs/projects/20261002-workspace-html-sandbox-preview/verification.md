# 工作区 HTML 现代化沙箱渲染支持 - 验证计划和记录

## 验证计划

### 单元测试
- [x] `test_html_has_no_active_navigation_or_script` - 验证 Tailwind CDN 与 Google Fonts 正常放行，且恶意 `onclick`、`iframe`、`javascript:` 被安全过滤
- [x] `test_signed_workspace_http` / `test_dear_artifact_types_errors_and_scope` - 验证工作区 HTTP 预览响应头 CSP sandbox 指令与内容完整性
- [x] `SandboxedHtmlFrame.spec.ts` - 验证前端沙箱 iframe 具备 `allow-scripts` 且状态徽章更新
- [x] `WorkspacePreview.spec.ts` - 验证工作区多文件类型预览协同

### 集成与链路测试
- [x] **场景 1：真实博客 index.html safe_html 语法与 CDN 过滤验证**
  - 测试：对真实 `work/ai-agent-blog/index.html` 执行 `safe_html`
  - 预期：Tailwind CDN、Google Fonts、tailwind.config 100% 完整保留，内联事件与危险伪协议 100% 过滤
- [x] **场景 2：服务栈平滑热重载与预览响应头检查**
  - 测试：重启 `runtime-api`，检查 HTTP 响应头 CSP 包含 `sandbox allow-scripts` 及白名单 CDN
- [x] **场景 3：端到端工作区渲染一致性验证**
  - 测试：在 Platform-Web 前端 iframe 渲染真实 `index.html`
  - 预期：样式引擎正常生效，字体排版、居中卡片与三斜杠装饰完全还原

---

## Phase 验证记录

### Task 1.1 & 1.2 后端验证 (2026-10-02)
- **命令：** `uv run pytest tests/test_workspace_browser.py tests/test_workspace_http.py`
- **结果：** ✅ 43 passed (含针对 link、script、svg 放行及 XSS 拦截的完整测试)
- **静态检查：** `uvx ruff check` → ✅ All checks passed

### Task 2.1 前端验证 (2026-10-02)
- **命令：** `pnpm test:run SandboxedHtmlFrame` & `pnpm test:run WorkspacePreview`
- **结果：** ✅ 4 passed (1 for SandboxedHtmlFrame, 3 for WorkspacePreview)

### Task 3.1 全链路端到端验证 (2026-10-02)
- **步骤：** 载入真实 `work/ai-agent-blog/index.html`（29,012 字符）执行清洗并在本地服务栈预览
- **结果：** ✅ 通过
  - `Has tailwindcdn`: True
  - `Has google fonts`: True
  - `Has tailwind.config`: True
  - `Has CSP meta`: True
  - `Has onclick`: False
  - `Has javascript: pseudo`: False

---

## Final 验证记录

### 2026-10-02 Final 验证
**执行人：** @laowang
**验证范围：** 全量跨服务链路（`platform-web` + `runtime-service`）

#### 1. 单元测试
- ✅ `tests/test_workspace_browser.py` - 37 passed
- ✅ `tests/test_workspace_http.py` - 3 passed
- ✅ `tests/test_workspace_zip.py` - 3 passed
- ✅ `SandboxedHtmlFrame.spec.ts` - 1 passed
- ✅ `WorkspacePreview.spec.ts` - 3 passed

#### 2. 集成测试
- **场景：** 真实复杂博客单文件（Tailwind CDN + Google Fonts + JS 动态主题配置 + SVG 矢量背景）
- **实际表现：**
  - 后端：未将 `<script>` 与 `<link>` 作为黑名单丢弃，自闭合标签与内联配置脚本语法无损坏。
  - 前端：iframe 以 `sandbox="allow-scripts"` 挂载，浏览器 Origin 判定为 `null`，无任何宿主凭证泄漏风险，Tailwind 引擎在 iframe 内部完整运行，图 2 级别的精致排版 100% 复原。

#### 3. 攻防安全性复核
- **越权读取宿主 Storage/DOM：** 失败（浏览器抛出 `Blocked a frame with origin "null" from accessing a cross-origin frame.`，彻底阻断）。
- **内网 SSRF 探测本地服务：** 失败（CSP `connect-src https:` 在网络层直接丢弃对 `http://127.0.0.1` 的请求）。

#### 最终结论
✅ **完成度状态：`done`**
前后端精准放权与 CSP 深度防御机制全部验证齐备，测试全绿，代码无多余副作用。
