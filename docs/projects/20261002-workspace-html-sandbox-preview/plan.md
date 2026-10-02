# 工作区 HTML 现代化沙箱渲染支持 - 整体方案

## 背景
当前平台在工作区（Workspace）中预览智能体生成的单文件 HTML 网页（如博客手记、交互报表、数据大屏）时，存在严重的样式坍塌现象。
经排查，现代智能体广泛采用 `Tailwind CSS CDN`（`<script src="https://cdn.tailwindcss.com">`）配合 Google Fonts（`<link href="https://fonts.googleapis.com/...">`）作为零构建交付的标准模式。而平台既有实现采取了“一刀切”的过度防御策略：
1. 后端 `apps/runtime-service/src/runtime_service/workspace/html_preview.py` 在 `HTMLParser` 中将 `<script>` 强制腰斩剔除，标签白名单完全不包含 `<link>`，且强加 `script-src 'none'; style-src 'unsafe-inline'` 的超严苛 CSP；
2. 前端 `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue` 采用了 `sandbox=""`（完全禁用 JavaScript）。

两重限制导致任何依赖 Tailwind CSS runtime 或 Google Fonts 的 HTML 页面在预览时无法加载样式引擎，页面排版、颜色、栅格全部失效，退化为无样式的垂直裸文本。

## 目标
1. 在保持零同源信任（Zero-Origin-Trust）安全底线的前提下，恢复现代单文件 HTML（如 Tailwind CDN、Google Fonts、SVG 矢量图标）的高保真渲染展示；
2. 封死针对本地开发栈（`127.0.0.1` / `localhost`）的内网探测与凭据窃取路径；
3. 更新前端沙箱徽章提示，准确传达当前页面的隔离状态；
4. 保持端到端测试与单测的完整覆盖与向后兼容。

## 方案设计

### 整体架构与威胁模型
```
+-----------------------------------------------------------------------------------+
| Platform Web 宿主页面 (Origin: http://127.0.0.1:3000, 持有 JWT/Cookie/Storage)    |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | SandboxedHtmlFrame: <iframe sandbox="allow-scripts" srcdoc="...">        |   |
|   | 浏览器判定该 iframe Origin: "null" (Opaque Origin)                         |   |
|   |                                                                           |   |
|   |  [安全屏障 1] 无法访问 window.parent / localStorage / Cookie               |   |
|   |  [安全屏障 2] 后端 CSP: connect-src https: (拦截对 127.0.0.1 的请求)       |   |
|   |  [安全屏障 3] 后端 CSP: frame-src 'none'; object-src 'none';              |   |
|   |  [能力放通 4] Tailwind CDN / Google Fonts 正常执行与绘制样式               |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

### 关键改动点

#### 1. 前端物理隔离沙箱调整
- **文件：** `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue`
- **改动：**
  - 将 iframe 的 `sandbox=""` 调整为 `sandbox="allow-scripts"`（坚决禁止添加 `allow-same-origin`）；
  - 将状态栏的“禁用脚本与外链”徽章更新为“独立脚本沙箱 (零同源凭据)”。
- **理由：** `allow-scripts` 允许内嵌脚本与 Tailwind 运行时执行，而缺省 `allow-same-origin` 时浏览器自动将 Origin 设为 `null`，实现物理级别的宿主隔离。

#### 2. 后端 CSP 策略升级
- **文件：** `apps/runtime-service/src/runtime_service/workspace/html_preview.py`
- **改动：**
  - 升级 `HTML_CSP` 为放行公认公共 CDN 与字体的白名单：
    ```text
    default-src 'none';
    script-src 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com;
    style-src 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com;
    font-src https://fonts.gstatic.com data:;
    img-src data: https: blob:;
    connect-src https:;
    frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
    ```
- **理由：** 既保证现代样式脚本能拉取和编译，又通过 `connect-src https:` 彻底阻断了向 `http://127.0.0.1` 或 `http://localhost` 发起恶意请求的通道。

#### 3. 后端 HTML 清洗器扩充
- **文件：** `apps/runtime-service/src/runtime_service/workspace/html_preview.py`
- **改动：**
  - 白名单标签扩充：增加 `link`, `script`, `svg`, `path`, `g`, `circle`, `rect`, `polygon`, `line`, `polyline`, `head`, `meta`, `title`；
  - 移出跳过黑名单：移除 `script` 和 `svg`；
  - 属性白名单：扩充 `rel`, `href`, `src`, `crossorigin`, `type`, `integrity`, `viewbox`, `fill`, `stroke`, `d` 等；
  - 协议安全校验：`href` 与 `src` 必须限定为 `https://` 开头或 `data:`，禁止 `javascript:` 伪协议。
- **理由：** 允许合法的 CDN 脚本和字体外链进入 DOM，同时在后端层面剔除危险协议与非法嵌套。

## 链路影响

### 受影响的调用链路
```
platform-web (WorkspacePreview -> SandboxedHtmlFrame)
  → platform-api (/api/langgraph/threads/{id}/workspace/preview)
  → runtime-service (/workspace/preview -> WorkspaceBrowser.preview -> safe_html)
```

### 契约变更
- `/workspace/preview` 返回的 HTML 内容和 `Content-Security-Policy` 响应头升级为支持白名单 CDN 与脚本执行，无破坏性参数变更。

## 风险和依赖
- **风险 1：** 恶意脚本尝试探测局域网。
  - **应对：** CSP 的 `connect-src` 严格限定为 `https:`，浏览器会拒绝发起任何 `http://127.0.0.1` 或 `http://localhost` 的非安全网络连接。
- **风险 2：** DOM XSS 影响父页面。
  - **应对：** 坚决不设 `allow-same-origin`，浏览器强制 Origin 为 `null`，完全阻止跨 frame DOM 访问与存储共享。

## 实施计划
1. **Phase 1: 后端安全清洗与 CSP 升级**：修改 `html_preview.py` 并通过单测验证；
2. **Phase 2: 前端沙箱配置与展示更新**：修改 `SandboxedHtmlFrame.vue` 并更新提示文本；
3. **Phase 3: 端到端效果验证与回归**：启动本地服务栈，验证实际博客 HTML 渲染效果与控制台安全性。
