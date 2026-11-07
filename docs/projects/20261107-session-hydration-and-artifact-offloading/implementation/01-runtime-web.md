# Runtime 与 Web 实现记录

## 改动时间
2026-11-07

## 改动内容

- `ImageReferenceFilesystemMiddleware` 替换主图和子图的 `read_file` 工具入口，在同步/异步工具返回被公开前把 PNG/JPEG/WebP Base64 保存到 Workspace，并返回既有 `extras.runtime_image` 引用。
- 模型调用 middleware 只在请求副本中按引用读取、核对 SHA-256 并恢复 `data:image/...;base64`，不回写 checkpoint。
- `dearflow_agent` 主图和子图接入该 middleware；GraphHarbor 保持未修改。
- `ChatSession.vue` 首屏和会话切换依赖 SDK 当前 state snapshot，历史仅在抽屉打开时按需读取，保留已有运行态、终态队列刷新与权限逻辑。
- 新增 Playwright Chromium 场景，使用本地 xiaok DeepSeek 创建新会话，上传可识别图片，要求 Agent 调用 `read_file`，检查 state 无内联 Base64，验证图片预览和刷新恢复。

## 影响与边界

- 仅覆盖本版本新建会话和当前支持的 PNG/JPEG/WebP；不实现存量兼容、迁移、双格式读取或旧逻辑回退。
- 失败时明确抛出外置/引用校验错误，不发布悬空引用。

## 验证

- Runtime 图片 middleware：同步/异步工具入口和模型副本测试通过。
- Runtime 相关回归：63 passed，6 skipped。
- Web chat 相关 Vitest：554 passed，1 skipped；`vue-tsc` 通过。
- Playwright Chromium + xiaok DeepSeek：1 passed；state 含 `runtime_image` 且不含 `data:image/*;base64`，刷新后图片和答复恢复。
