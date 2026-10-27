# 修复 Markdown 渲染器放行 blob: 协议支持工作区产物图表渲染

## 背景

用户在打开智能体工作区产物库中的深度调研报告《灵巧手 2026：从“能演示”到“能干活”的最后一厘米》（Markdown 格式）时，报告中的图表全部呈现破损状态。

经过分层链路穿透排查：

1. **沙箱容器层**：智能体执行 `generate_column_chart` / `generate_pie_chart` 等工具生成的 5 张图表 PNG 均真实存在于 `/workspace/charts/`，SHA256 完好。
2. **Platform-API 网关层**：`GET /api/langgraph/threads/{threadId}/workspace/preview?path=...` 请求返回 200 OK，`image/png` 完整下发。
3. **Platform-Web 数据处理层**：`WorkspacePreview.vue` 成功拉取 Blob 并生成 `blob:http://127.0.0.1:3000/...` 替换 Markdown 中的原始文件路径。
4. **Platform-Web 渲染清洗层（根因）**：`apps/platform-web/src/utils/markdown.ts` 中 `sanitizeUrl` 的 `SAFE_PROTOCOLS` 白名单仅包含 `["http:", "https:", "mailto:"]`，未包含 `blob:`。导致所有 `blob:http://...` 被强行改写为 `#`，输出 `<img src="#" alt="...">`，最终在浏览器中表现为破图。

## 改动内容

1. `apps/platform-web/src/utils/markdown.ts`：
   - 将 `blob:` 协议纳入 `SAFE_PROTOCOLS` 白名单：
     ```ts
     const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:", "blob:"]);
     ```
   - 确保 `blob:` 协议的图片能够在 DOM 中安全且完整地输出对应 Object URL，同时保持对 `javascript:` 与 `data:` 伪协议的严格拦截与清洗。
2. `apps/platform-web/src/utils/markdown.spec.ts`：
   - 新增针对 `renderMarkdown` 的全量单测，覆盖 `blob:` URL 渲染、普通链接/图片、相对路径、XSS 伪协议防御、表格和代码块转义。
3. `apps/platform-web/src/styles/index.css` & `apps/platform-web/src/components/workspace/WorkspacePreview.vue`：
   - 治理生成图表尺寸过大（广告牌效应）：在全局 `.pw-markdown img` 与 `.pw-workspace-markdown :deep(img)` 中建立大厂研报级卡片排版规范：
     - `max-width: min(100%, 680px)`、`max-height: 460px`，纵横比 `object-contain`，彻底消除图片无节制横向膨胀挤爆屏幕的问题；
     - 居中对齐 `margin: 1.5rem auto; display: block;`；
     - 加入精致卡片内边距、微圆角 `12px`、轻边框与微阴影，适配浅色与暗色模式；
     - 让高采样率（2280px）高清图以 300px~680px 细腻缩放呈现，文字和柱线锐利清晰，完美还原投行研报排版质感。

## 涉及文件

- `apps/platform-web/src/utils/markdown.ts`
- `apps/platform-web/src/utils/markdown.spec.ts`
- `apps/platform-web/src/styles/index.css`
- `apps/platform-web/src/components/workspace/WorkspacePreview.vue`

## 验证结论

- **单元测试**：Vitest 6/6 全部通过。
- **类型检查与 Lint**：`pnpm run typecheck` 0 报错；`pnpm run lint` 0 errors。
- **Playwright E2E**：在实际会话页面打开深度报告，5 张图表全部以 `blob:http://127.0.0.1:3000/...` 正确解码渲染，`naturalWidth` 达 2280px，生成真实有效截图 `verify-charts-rendered-successfully.png`。
