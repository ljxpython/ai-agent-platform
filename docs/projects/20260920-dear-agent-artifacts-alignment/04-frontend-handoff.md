# 04 前端交接：Dear Agent 成果页对接与验收说明

## 1. 给接手同事的第一说明

**本文件是前端独立交接入口。前端由接手同事开发，本方只交付后端/Runtime 与接口资料。** 本轮仅规划，接口源码已存在但本专项尚未联调复验；不能把下表“已有”理解成“本轮新增开发完成”。

页面路由：`/workspace/projects/:projectId/dear-agent-artifacts?threadId=:threadId`。

目标：按当前项目 Dear 会话查询正式成果，页内预览与下载，和聊天工作区共享同一事实源。必须修复漏传项目头，停止从历史消息正则扫描正式成果。

### 1.1 后端交付状态台账

| 能力 | 代码现状 | 本次后端工作 | 前端可否开始 |
|---|---|---|---|
| 项目/线程授权 | 已有；缺项目会 400 | 补真实登录 scope smoke/负例 | 可按现有认证客户端实现 |
| 正式成果列表 | 已有 GET artifacts + cursor | 补 Dear 双服务/分页回归 | 可按本文 DTO 开发 |
| 文本/MD/图片/静态 HTML 预览 | 已有 | 补类型/边界/安全头实测 | 可按 preview_kind 分支 |
| 原字节下载与 SHA256 | 已有 | 补断流/重启/摘要一致性 | 可复用 workspace.service |
| 嵌套错误消息 | code 已提取；message 存在退化分支 | B02 拟修 | UI 依据 code，不匹配英文 message |
| 原业务文件名、发布时间、来源 run/message | 未实现 | 首批不开发 | 不显示假值，回退 hash 文件名 |
| CSV 表格、Office/PDF 原生预览 | 共享 workspace preview 未提供 | 首批不开发 | 源码/文件详情与下载降级 |
| 动态 HTML、成果编辑、成果集合 ZIP | 本专项不支持 | 后置 | 不添加功能入口 |

后端交付版本：**待填**；实际可用环境/项目/thread：**待填**；测试结果：**未执行**。只有 G1/G2 完成才能将对应行标为“本期已验证”。前端可先基于当前合同开发与 mock，但最终必须换成真实接口验收。

## 2. 前端目录、复用顺序和应该改哪里

```text
apps/platform-web/src/
├── router/routes.ts
├── composables/
│   ├── useWorkspaceProjectContext.ts   # 当前项目
│   ├── useThreadWorkspace.ts          # 列表/预览/下载状态；需补 race/error
│   └── useThreadWorkspace.spec.ts
├── services/
│   ├── http/client.ts                 # platformHttpClient；平台认证/刷新
│   ├── langgraph/client.ts            # createLanggraphAuthorizedFetch
│   └── threads/
│       ├── session.service.ts         # createSessionService(fetch, projectId)
│       ├── workspace.service.ts       # getArtifacts/Preview/ContentBlob 等
│       └── workspace.service.spec.ts
├── types/workspace.ts                 # ArtifactRef/PreviewKind/WorkspacePage
├── components/workspace/
│   ├── WorkspacePanel.vue            # 聊天工作区复用入口
│   ├── WorkspacePreview.vue          # 统一预览器
│   └── SandboxedHtmlFrame.vue         # 现有静态 iframe
└── modules/dear-agent/
    ├── pages/DearAgentArtifactsPage.vue
    ├── pages/DearAgentArtifactsPage.spec.ts
    ├── components/DearAgentSession.vue
    └── run-actions.ts                 # 已给会话操作 transport 注入项目头
```

阅读顺序：页面当前 service/loadSessionArtifacts → session.service → workspace.service/types → useThreadWorkspace → WorkspacePreview → DearAgentSession 的 busy watch。不要将同名 `services/runtime-gateway/workspace.service.ts` 当成果文件服务：本交接使用的是 `services/threads/workspace.service.ts`。

### 2.1 第一处明确修复

```ts
// 替换页面当前未传 projectId 的 computed；这里只示范服务装配。
const service = computed(() =>
  createSessionService(createLanggraphAuthorizedFetch(), activeProjectId.value),
);
```

activeProjectId 为空时不调用 service.list/get。项目变更清空旧选择/分页/错误并重新加载。不要给所有 `createSessionService(fetch)` 调用机械加参数：chat composable 的 actions.fetch 已有项目头；本页原来传的是未经项目包装的授权 fetch。

## 3. 公开接口与认证约定

只调用 Platform API，基础地址由现有客户端配置。下面 URL 均为相对平台地址。所有请求需要登录 Bearer 与 `x-project-id`；浏览器不调用 `/internal/`，不签 Runtime 委托。

| 方法/地址 | 入参 | 响应 | 当前封装 |
|---|---|---|---|
| POST /api/langgraph/threads/search | limit=20、offset、metadata.graph_id=dearflow_agent | Thread 数组 | createSessionService(...).list({offset,metadata}) |
| GET /api/langgraph/threads/{id} | id，项目头 | Thread | service.get(id)；深链校验 |
| GET /api/langgraph/threads/{id}/capabilities | id，项目头 | 能力对象 | getWorkspaceCapabilities(projectId,id,signal) |
| GET /api/langgraph/threads/{id}/artifacts | limit=100、可选 cursor | WorkspacePage<ArtifactRef> | getArtifacts(projectId,id,params,signal) |
| GET /api/langgraph/threads/{id}/workspace/preview | path 必填 | 按 Content-Type 分支 | getWorkspacePreview(projectId,id,path,signal) |
| GET /api/langgraph/threads/{id}/workspace/content | path 必填 | 原字节附件 | getWorkspaceContentBlob(projectId,id,path,signal) |

query 参数交给客户端编码。不要把 path 手工拼接到 URL，也不要将其当 HTML 字符串插入页面。所有 private 响应 no-store；客户端状态/cache key 至少包含 projectId/threadId/path。

### 3.1 会话查询

```json
{
  "limit": 20,
  "offset": 0,
  "sort_by": "updated_at",
  "sort_order": "desc",
  "select": ["thread_id", "metadata", "status", "created_at", "updated_at"],
  "metadata": {"graph_id": "dearflow_agent"}
}
```

这是 HTTP wire 形状示意；应用代码用现有 session.service，由 SDK 处理 camelCase 到 wire 字段。结果 metadata.title 为空显示“未命名会话”，updated_at 是线程更新时间，**不是成果发布时间**。

继续 offset=20/40 加载；若未使用 count，只有“已加载 N 会话”。路由 threadId 不在第一页时调用 get：验证项目授权与 graph_id 后展示，不静默换成首个会话；无权限/不存在单独提示。

### 3.2 capabilities

相关字段示例（摘录，不代表只返回这些字段）：

```json
{
  "schema_version": 1,
  "graph_id": "dearflow_agent",
  "files": true,
  "workspace": true,
  "images": true,
  "artifacts": ["text/markdown", "image/png", "application/zip"]
}
```

artifacts 数组实际由 Runtime 全部支持 MIME 去重排序得到，示例仅列三项；它表示可发布类型，不保证可预览，也不授予写工具权限。workspace=false 与请求失败必须分开处理。

## 4. 成果 DTO 与完整样例

从 `src/types/workspace.ts` 导入，不在页面再定义另一套 RuntimeFileRef：

```ts
type PreviewKind = 'text' | 'markdown' | 'image' | 'html-sandbox' | 'download';
interface ArtifactRef {
  version: 1;
  artifact_id: string;
  path: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  kind: string;
  preview_kind: PreviewKind;
}
interface WorkspacePage<T> {
  items: T[];
  next_cursor: string | null;
}
```

以下样例对应真实可计算的 9 字节 UTF-8 `# report\n`，SHA256 已按这组字节计算；这是确定性接口示例，不是线上请求结果：

```json
{
  "items": [{
    "version": 1,
    "artifact_id": "d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624",
    "path": "/workspace/outputs/d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624.md",
    "file_name": "d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624.md",
    "mime_type": "text/markdown",
    "size_bytes": 9,
    "sha256": "d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624",
    "kind": "text",
    "preview_kind": "markdown"
  }],
  "next_cursor": null
}
```

字段解释：

| 字段 | 页面用途 | 不允许的推断 |
|---|---|---|
| path | 选择/去重/请求参数 | 不转宿主路径、不自行更改 hash |
| artifact_id / sha256 | 展示与复制摘要 | 不单独用 artifact_id 做跨类型唯一 key |
| file_name | 默认标题/下载名，当前是 hash.ext | 不声称原业务文件名 |
| mime_type | 类型标签/辅助分类 | 不以扩展名取代后端 preview_kind |
| size_bytes | 文件大小 | 不把 0/缺失统一表示为网络失败 |
| kind | 历史粗分类 | 不是完整预览策略，PDF 也可能被归为 text |
| preview_kind | 唯一渲染分支依据 | download 不代表服务故障 |
| next_cursor | 原样带回下一页 | 不是页码，不从 cursor 解码出业务信息 |

没有 `total/display_name/created_at/run_id/source_message_id/slides`。首批隐藏发布时间/来源步骤，保留所属线程；不要借 checkpoint ID 或遍历消息“补齐”不存在的合同。

## 5. 分页、刷新与选择状态怎么写

页面复用 `getArtifacts` 的最小调用：

```ts
const page = await getArtifacts(projectId, threadId, { limit: 100, cursor }, signal);
// 首次或刷新：替换 items；下一页：按 path 去重追加。
// next_cursor === null 才表示当前目录这一轮遍历结束。
```

推荐在现有 useThreadWorkspace 修复，避免页面/聊天各实现一套：

1. 每次 scope 变化递增 generation、中止旧 controller、清理状态；同 scope 的 list/capabilities 可并行，不互相取消。
2. 每个请求在发起时捕获 projectId/threadId/generation。success/catch/finally 三个出口都检查；只检查 selectedPath 不够，因为不同线程可能有同一路径。
3. 预览再增加 request sequence；同时选两份文件时后选优先。取消错误不弹用户提示。
4. load-more 单飞，失败保留已加载项与重试按钮；refresh 替换第一页并丢旧 cursor。
5. `workspace_directory_changed` 最多自动重取首页一次；连续变动显示“成果有更新，请刷新”，禁止无限递归。
6. 搜索/分类先作用于已加载集合；标题写“已加载 N 项”，不显示“全部 N 项”。筛选后仍允许加载下一页。
7. 初次列表返回不抢占已有有效选择。手动刷新后原 path 仍存在则保留；消失则清理预览。
8. 独立页不需要树/Terminal，给 composable 增简单 includeTree=false 选项（拟实现，当前不存在），不能直接假定现有 hook 已支持。

## 6. 预览请求怎样消费

### 6.1 文本/Markdown JSON

```json
{
  "path": "/workspace/outputs/d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624.md",
  "file_name": "d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624.md",
  "mime_type": "text/markdown",
  "size_bytes": 9,
  "sha256": "d2f56516fd6c35644826ae6f1876a47870b7fa19acedac3e52fb6f2a94aa2624",
  "preview_kind": "markdown",
  "text": "# report\n",
  "truncated": false
}
```

可能附带 ArtifactRef 的其他字段，消费所需字段即可。API Content-Type 是 application/json，而文件 mime_type 是 text/markdown，两者不能混淆。JSON 成果文件预览也返回这个 envelope，不是直接返回用户 JSON 文档。

沿用 WorkspacePreview 渲染/源码切换与 markdown 工具。truncated=true 提示“仅显示前 256 KiB，请下载完整文件”；本期无 load-full-preview 或 Range 接口。CSV 首批展示文本，不沿用 files.service 的简易逐行 CSV 算法承诺复杂表格支持。

### 6.2 图片

preview 返回 image/png、image/jpeg 或 image/webp 字节。由授权 fetch 获取 Blob，再 URL.createObjectURL → img；切换/卸载 revoke。不能把受保护 API URL 直接放 img.src，因为不能附带项目/认证头。

Markdown 内部 `/workspace/...` 图片同样走授权 preview，基于文档路径处理相对引用；晚返回的图片替换不得污染新文档。对超过工作区边界的路径不请求；外链策略沿用现有安全渲染规范，不为成果页新增自动加载外部 URL 的能力。

### 6.3 HTML

响应为 Runtime safe_html 的静态净化文本。必须调用现有 SandboxedHtmlFrame：`sandbox=""`、`referrerpolicy="no-referrer"`；可用 srcdoc，保留服务端 CSP meta。

参考 DeerFlow `artifact-file-preview.tsx` 使用 `sandbox="allow-scripts allow-forms"`，**这一行不能照搬**。本方禁止加 allow-scripts/allow-same-origin/allow-forms，不将原始 HTML 下载内容塞进 v-html。下载按钮拿原始文件，与净化预览是两个不同操作。

### 6.4 download 类型

PDF/XLS/XLSX/PPTX/ZIP：显示文件信息与明确下载按钮；不要调用 preview 后把预期 415 当系统故障，也不要把“预览”按钮变成直接下载。图片型 PPTX 不自带页图关联，本页不能承诺逐页预览。

未知 future preview_kind 显示“暂不支持预览，可下载”，不要崩溃；是否允许下载仍由服务端判断。

## 7. 下载与错误处理

```ts
const { blob, fileName } = await getWorkspaceContentBlob(projectId, threadId, item.path, signal);
triggerBlobDownload(blob, fileName);
```

复用已有工具，不新写 document.createElement 下载逻辑。API 返回 attachment、ETag、no-store/nosniff；文件名当前取虚拟路径末段，未来业务名称另议。下载完成/取消/异常均解除 loading；错误时不 toast“成功”。客户端不把 token 塞 query/new-tab URL。

### 7.1 线上的错误 envelope 与 SDK 展示不同

Platform 原始错误样例：

```json
{
  "request_id": "example-request-id",
  "error": {
    "code": "project_id_required",
    "message": "x-project-id header is required",
    "details": []
  }
}
```

createLanggraphAuthorizedFetch 为 SDK 兼容可能把 `error` 转成字符串并提取顶层 code/message，因此用户看到的 HTTP 400 文本不一定等同原始响应结构。Axios 的平台客户端走另一条管线；不要按一个字符串正则解析全部错误。

preview/content 使用 responseType=blob，错误 JSON 也可能成为 Blob。前端应在现有 workspace service 边界有界解析 JSON Blob（建议只解析 application/json 且不超过 64 KiB 的错误体），提取 error.code/message/request_id；坏 JSON/HTML 网关页回退 HTTP 状态。**这是拟补充的前端能力，当前封装没有完整实现。** UI 不展示 error.extra.upstream_detail 原文。

| 状态/code | 前端动作 |
|---|---|
| 400 project_id_required | 本页接线错误/项目尚未选定；停止请求，提示项目上下文异常 |
| 400 invalid_workspace_cursor / invalid_workspace_path | 丢弃坏 cursor 或阻止请求；不能当空列表 |
| 401 | 交给统一登录刷新；刷新失败跳登录，停止当前 scope 请求 |
| 403 thread_project_denied / runtime_target_denied / file_scope_denied | 无权访问，清掉敏感预览，禁止自动重试 |
| 404 artifact_not_found / workspace_file_unavailable | 文件不可用；刷新列表/返回会话，不声称发布成功 |
| 409 workspace_directory_changed | 游标失效，最多自动重新加载一轮 |
| 409 artifact_hash_mismatch | 文件完整性异常，阻止预览/成功下载，展示 request_id 便于反馈 |
| 409 workspace_capability_unavailable | 工作区能力不可用；不当游标冲突重试 |
| 413 file_too_large / html_preview_too_large | 大 HTML 可尝试原文件下载；超原文件上限不重复下载 |
| 415 workspace_preview_unsupported | 文件详情与下载降级 |
| 422 validation_failed / 格式校验错误 | 参数/内容错误，展示可读提示，不无限重试 |
| 502/504、网络断开或截断流 | 提供手动重试，保留已有列表，下载不报成功 |

## 8. 前端同事的开发任务

- [ ] **F01** 修项目参数；空项目不请求；factory 与真实 transport 断言。
- [ ] **F02** 替换历史扫描为 getArtifacts；使用 ArtifactRef；删假时间/步骤；会话分页和深链。
- [ ] **F03** useThreadWorkspace 补 scope generation/AbortSignal/预览序号/error/分页；独立页不加载树。
- [ ] **F04** 接 WorkspacePreview 与下载型卡片；Blob 生命周期/Markdown 图片任务保护。
- [ ] **F05** workspace.service 补 Blob 错误解码；本地化 code 提示与 request_id；全链路下载失败可见。
- [ ] **F06** DearAgentSession 的 hasArtifacts 不再只看 ui；保留 busy 终态 refresh，与 WorkspacePanel 同步分页/错误/新成果提示。
- [ ] **F07** 组件/服务测试、lint/typecheck/build；补真实 HTTP 边界，mock 数据使用本页真实 hash 样例。
- [ ] **F08** 浏览器 E2E、窄屏/键盘、Showcase 回归；与本方共同完成 G4，不由本方代写页面。

## 9. 前端测试如何写、何时算完成

| 测试文件 | 重点断言 |
|---|---|
| DearAgentArtifactsPage.spec.ts | projectId 工厂参数；history 未调用；空/错/加载三态；21 会话；非首屏深链；101 成果 |
| session.service.spec.ts | 保留真实 Client，fetch 替身捕获 search/get 的 x-project-id，而非 mock 掉整个 service |
| workspace.service.spec.ts | 所有资源请求头；JSON/HTML/image 分支；Blob JSON 错误与坏 JSON fallback；文件名编码 |
| useThreadWorkspace.spec.ts | 手动控制 Promise 先后；跨 project/thread 同 path；旧 finally；取消/卸载；游标冲突只重试一次 |
| WorkspacePreview.spec.ts（拟新增） | Markdown 净化；图片授权请求与 URL 释放；旧异步解析不得污染新文档；静态 sandbox 属性 |
| e2e/dear-agent-artifacts.spec.ts（拟新增） | 真后端发布后列出/预览/下载/刷新，非只 route.fulfill；HTTP 400 不再发生 |

测试命令从 `apps/platform-web` 执行：

```bash
pnpm exec vitest run src/modules/dear-agent/pages/DearAgentArtifactsPage.spec.ts src/services/threads/session.service.spec.ts src/services/threads/workspace.service.spec.ts src/composables/useThreadWorkspace.spec.ts
pnpm exec vitest run src/components/workspace/WorkspacePreview.spec.ts
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test e2e/dear-agent-artifacts.spec.ts
```

后两条新增测试文件必须实际创建后再执行。API 接口可用但页面仍 400 时先查 factory/请求头；页面无成果时查工具回执和 /artifacts，不自动归咎历史加载。真实浏览器证据必须包括请求地址/状态、scope、下载 hash、页面截图，不留 token。

## 10. 交接状态与签收

- 文档：已形成接入草案，包含 API/字段/错误/实现顺序/测试责任。
- 本方后端：R/B/G1/G2 全部待执行，本期未宣布已交付。
- 前端同事：负责人待指定，F01—F08 待开始；本方不实施。
- 联合验收：G4 待安排，后端验收完成与页面最终完成分开标记。

实际交付时补：后端版本、运行环境、测试结果、样本线程、已知限制、接手人、签收日期、前端实施分支/版本。当前这些值均不得编造。
