# 后端 CSP 策略升级与 HTML 清洗器扩充

## 改动时间
2026-10-02

## 相关任务
- Task 1.1: 升级 HTML_CSP 与标签白名单及安全属性校验
- Task 1.2: 补充与更新后端单元测试

## 改动文件
- `apps/runtime-service/src/runtime_service/workspace/html_preview.py`
- `apps/runtime-service/src/runtime_service/http/workspace.py`
- `apps/runtime-service/tests/test_workspace_browser.py`
- `apps/runtime-service/tests/test_workspace_http.py`

## 具体改动

### 1. CSP 策略与标签白名单升级
**位置：** `apps/runtime-service/src/runtime_service/workspace/html_preview.py:7-140`

**改动内容：**
- 将 `HTML_CSP` 扩充为公认安全前端 CDN 与字体库的白名单：放行 `https://cdn.tailwindcss.com`, `https://fonts.googleapis.com`, `https://cdn.jsdelivr.net`, `https://cdnjs.cloudflare.com`, `https://unpkg.com`，并将 `connect-src` 严格限定为 `https:`（禁止连接 `http://127.0.0.1` 内网）；
- 扩充 `TAGS` 支持 `<link>`, `<script>`, `<head>`, `<meta>`, `<title>`, `<svg>` 及一系列矢量绘图标签；
- 扩充 `ATTRS` 支持 `rel`, `href`, `src`, `crossorigin`, `integrity`, `viewbox`, `fill`, `stroke` 等合法属性；
- 属性过滤：剔除所有以 `on` 开头的内联事件，禁止 `javascript:` 伪协议；
- 自闭合标签与数据保持：修复 `base` 标签等无闭合标签元素误触发 `skip` 的 Bug；保留 `script` 和 `style` 内部原始内容不被 html escape 转义。

### 2. HTTP 响应头 CSP sandbox 指令对齐
**位置：** `apps/runtime-service/src/runtime_service/http/workspace.py:135`

**改动内容：**
- 将 `sandbox;` 对齐为 `sandbox allow-scripts;`，确保直接 GET `/workspace/preview` 也能执行脚本并维持 `Origin: null` 隔离。

### 3. 测试套件契约对齐
**位置：** `apps/runtime-service/tests/test_workspace_browser.py` 与 `test_workspace_http.py`

**改动内容：**
- 测试用例断言升级，确保放行合法 Tailwind CDN、Google Fonts 与内联配置脚本，同时严格断言剔除 `onclick`, `iframe`, `base`, `javascript:`。

## 验证
- [x] 单元测试通过 (`43 passed`)
- [x] Ruff Lint 通过 (`All checks passed`)
