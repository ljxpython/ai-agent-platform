# 平台展示工作区

**实现交接：** 后端已完成，前端以 [05 实现版契约](05-frontend-handoff.md) 为准。HTML 使用静态安全版本和空 sandbox，不允许脚本；本篇为交互设计。

## 目标

在当前聊天页提供直观的线程工作区：浏览文件、查看代码/文档、预览图片和 HTML artifact、下载产物，并保留终端和审批入口的清晰边界。本专题最后开发，前提是 01/02 的后端契约冻结。

## 现有基础

- platform-web 已有 `ChatArtifactPanel`、`ThreadFile`、`ThreadImage` 和 artifact 路径提取逻辑。
- `OutputIframe`、`SandboxedHtmlFrame`、`TerminalPanel` 属于 Open SWE React 参考实现，本仓库没有这些现成组件；需按 Vue 技术栈实现，文件位置见 [04](04-code-change-map.md)。
- Dear Agent 已有独立 `DearAgentArtifactsPage`，可复用其文件列表和下载体验。
- platform-api 已有线程文件上传/读取代理及内部 Runtime 文件路由。

## 方案设计

### 右侧工作区布局

```text
┌────────────── Chat ──────────────┬──────────── Workspace ────────────┐
│ messages / approvals / tool log  │ Files | Artifacts                 │
│                                  │ ┌──── tree ────┬── preview ─────┐  │
│                                  │ │ work         │ code/markdown │  │
│                                  │ │ generated    │ image/html    │  │
│                                  │ │ outputs      │ metadata      │  │
│                                  │ └──────────────┴────────────────┘  │
└──────────────────────────────────┴───────────────────────────────────┘
```

### 交互

- 发布工具完成时刷新 Artifacts，运行终态再次刷新；提供新产物提示，不强制打断用户当前预览。
- 文件树支持按需目录展开、分页和大小/MIME 标签；全局搜索、“仅显示本轮变更”和来源消息关联后置，当前没有相应索引。
- 文本文件使用只读代码查看器，支持复制、下载和跳转到聊天引用；第一阶段不做浏览器内编辑。
- Markdown 使用 Markdown 渲染和原文切换；HTML 使用 sandboxed iframe，显示“脚本隔离”标记。
- 图片直接使用已存在的 `ThreadImage`；PPTX/ZIP/PDF 显示文件卡片和下载。
- 文件不存在、过期或 scope 不匹配时显示明确错误，不回退自然语言中的伪路径。
- Terminal 第二阶段后端现已交付；前端入口、Vue 组件位置、交互与连接协议见 [05](05-frontend-handoff.md#terminal前端开发入口)。本轮仍不实施前端功能。

### API client 与状态

- 新增 `useThreadWorkspace(threadId)`，统一 tree/files/artifacts 查询、刷新和选中项；本阶段只做设计，前端实现另立任务，不在本项目直接开发页面。
- 现有工具结果及运行终态只触发查询失效；文件内容按需读取，避免把整个工作区灌进 transcript。
- 刷新后，Artifact 页面通过虚拟 path 恢复选中项，并重新鉴权；不把宿主路径存入 localStorage。

## 前端对接契约（后端完成后再开发）

```ts
type WorkspaceEntry = {
  path: string; name: string; type: "file" | "directory"; size_bytes: number | null;
  mtime: string; mime_type: string | null;
  preview_kind: "text" | "markdown" | "image" | "html-sandbox" | "download" | null;
  is_artifact: boolean;
}
type ArtifactRef = {
  version: 1; artifact_id: string; path: string; file_name: string; mime_type: string;
  size_bytes: number; sha256: string; kind: string;
  preview_kind: Exclude<WorkspaceEntry["preview_kind"], null>;
}
```

对接流程：进入 thread 请求 `/api/langgraph/threads/{id}/workspace/tree?path=/workspace`，携带现有认证及 `x-project-id`；展开使用返回的 path，同目录翻页使用 cursor；点击文件请求同前缀 `/workspace/preview?path=...`；发布工具完成或运行结束后刷新 `/artifacts`，使用 path 选中；下载使用 `/workspace/content?path=...`。参数通过客户端编码，不手工拼接。前端不请求 Runtime `/internal`，不读取宿主路径，不从消息文本猜路径，不把全文写入 transcript/localStorage。HTML 只有服务端返回 `html-sandbox` 时才能交给新增 Vue `SandboxedHtmlFrame`，且必须使用后端受限预览文档，不把原文件直接塞进 srcdoc。

文本预览显示 `truncated` 提示；不支持预览时保留下载。目录/列表 `next_cursor=null` 表示结束；切换 thread/project 时取消在途请求并清空选中项。具体响应例子和 OpenAPI 由后端实现后补齐，本节为目标契约。

## 任务拆分

- [x] 统一 ChatArtifactPanel 与 DearAgentArtifactsPage 的 artifact/file 数据模型
- [x] 实现 Workspace 右侧面板、tab、文件树和预览路由
- [x] 接入工具结果/终态刷新、下载、复制、错误和空状态
- [x] HTML/Markdown/代码/图片/二进制五类预览组件与安全响应头
- [x] 接入多终端组件、PTY单飞轮询与跨Tab保活挂载（借鉴 open-swe）
- [ ] Playwright 覆盖浏览器 E2E 回归

## 验证要求与记录

- [x] platform-web 组件和 composable 单元测试（全量 208 个测试通过）
- [x] Platform API 契约测试覆盖 artifact/file 权限
- [x] vue-tsc 静态类型检查与 Vite 生产构建 0 错误通过
- [x] HTML iframe 纯净沙箱安全隔离（sandbox="" + referrerpolicy="no-referrer"）

## 状态

已完成：前端弹性工作区面板、目录树、五类预览器、xterm多终端会话保活管理及Chat全链路联动均已落地并验证通过。

## 前端设计交付物（本阶段不编码）

- 组件边界：`WorkspacePanel`、`WorkspaceTree`、`WorkspacePreview`、`SandboxedHtmlFrame`；页签、产物列表及下载按钮先放在面板内，避免为简单展示过度拆组件。
- 数据边界：所有内容来自 `useThreadWorkspace`；消息 transcript 只保存 artifact metadata，不内嵌大文件内容。
- 预览路由：`preview_kind=text` 用只读代码查看器；`markdown` 用渲染/源码双态并禁用原始 HTML、过滤链接；`image` 复用图片展示能力；`html-sandbox` 用新增 iframe 组件；`download` 只显示下载卡片。
- 状态边界：空工作区、加载、分页、文件消失、权限拒绝、内容损坏、过期引用均有独立状态；刷新按 thread/path 恢复。
- HTML 安全验收：iframe 无 `allow-same-origin`，不能读写父页面、不能发送网络请求、不能读取平台 token，下载仍通过 API。
