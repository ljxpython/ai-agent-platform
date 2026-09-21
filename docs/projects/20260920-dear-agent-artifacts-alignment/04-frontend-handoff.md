# 04 前端交接：Dear Agent 成果页对接与验收说明

## 1. 给接手同事的第一说明

**本文件是前端独立交接入口。后端/Runtime 与交接文档已于 2026-09-21 完成；前端 F01—F08 暂未实施，由接手同事开发。** 接口主体是既有能力，本轮修复嵌套错误消息，补齐确定性、双服务与真实平台验收。页面漏项目头仍需 F01 修复。

页面路由：`/workspace/projects/:projectId/dear-agent-artifacts?threadId=:threadId`。

**目标**：按当前项目 Dear 会话查询正式成果，**页内通过右侧滑出抽屉（Drawer / Slide-over）进行预览与下载**，和聊天工作区共享同一事实源。必须修复漏传项目头，停止从历史消息正则扫描正式成果。

### 1.1 后端交付状态台账与交互决策

| 能力 | 代码现状 | 本次后端工作 | 前端可否开始 | 前端实施决策 |
|---|---|---|---|---|
| 项目/线程授权 | 已有；缺项目会 400 | 完成：真账号/跨项目/非成员负例 | 可按现有认证客户端实现 | F01 修复工厂注入与项目响应式 |
| 正式成果列表 | 已有 GET artifacts + cursor | 完成：Dear 双服务与 101 项分页 | 可按本文 DTO 开发 | F02 替换历史扫描为 `getArtifacts` |
| 成果状态管理 | 现有 `useThreadWorkspace` 耦合树/终端 | 保持树与成果独立 | 抽取独立 `useArtifacts` composable | F03 统一管理分页、游标、选中与代际控制 |
| 文本/MD/图片/静态 HTML 预览 | 已有 | 完成：类型/边界/安全头验证 | 可按 preview_kind 分支 | F04 右侧抽屉内嵌 `WorkspacePreview.vue` |
| 已知 download 类型处理 | 共享 workspace preview 遇二进制报 415 | 415 属预期非故障 | 客户端直接拦截 | **不发起 preview 请求**，直接展示下载卡片 |
| 原字节下载与 SHA256 | 已有 | 完成：断流/重启/摘要一致性 | 可复用 workspace.service | 统一触发下载并清除 loading |
| 嵌套错误消息 | 本轮补 detail.detail.message | 完成：B02 修复与全量回归 | UI 依据 code 还原 | F05 AxiosError 中解包 Blob JSON 提取 message/request_id |
| 原业务文件名、发布时间、来源 run/message | 未实现 | 延后 | 不显示假值，回退 hash 文件名 | 首批不伪造字段，展示 hash.ext |
| CSV 表格、Office/PDF 原生预览 | 共享 workspace preview 未提供 | 延后 | 源码/文件详情与下载降级 | 保持简单文本或下载降级 |
| 动态 HTML | 本专项不支持 | 不做（本阶段） | 保持静态净化与 sandbox | 严格维持 `sandbox=""` 纯静态沙箱 |
| 成果编辑、成果集合 ZIP | 本专项不支持 | 延后 | 不添加功能入口 | 不添加无用按钮与假动作 |

后端交付版本：`4c5753528beb89a0d72c04dbb156d9457dece11b` 基线 + 本专项未提交工作树。G1/G2 完成；Runtime 42 项通过，Platform 全量 207 通过/7 按集成门禁跳过，真实模型/API smoke 1 项通过。实际环境/样本见 §11；完整证据见 [实现记录](implementation/01-backend-artifact-delivery.md)。

本地 runtime-api/platform-api 已按正式脚本重启并复核：两份成果保持原 path/hash；新版 Platform 嵌套错误 message 实测保留。无需前端新增发布接口、传 Runtime 委托或改数据库。

## 2. 前端目录、复用顺序和应该改哪里

```text
apps/platform-web/src/
├── router/routes.ts
├── composables/
│   ├── useWorkspaceProjectContext.ts   # 当前项目上下文
│   ├── useArtifacts.ts                # [NEW/独立] 成果列表/分页/选中/代际状态，供独立页与工作区抽屉复用
│   ├── useArtifacts.spec.ts           # [NEW] 针对分页/游标/代际取消/阻断 download 请求的测试
│   ├── useThreadWorkspace.ts          # 聊天工作区整套（树/终端/包装 useArtifacts）
│   └── useThreadWorkspace.spec.ts
├── services/
│   ├── http/client.ts                 # platformHttpClient；平台认证/刷新
│   ├── langgraph/client.ts            # createLanggraphAuthorizedFetch
│   └── threads/
│       ├── session.service.ts         # createSessionService(fetch, projectId)
│       ├── workspace.service.ts       # getArtifacts/Preview/ContentBlob 与 unwrapBlobError
│       └── workspace.service.spec.ts
├── types/workspace.ts                 # ArtifactRef/PreviewKind/WorkspacePage
├── components/workspace/
│   ├── WorkspacePanel.vue            # 聊天工作区复用入口
│   ├── WorkspacePreview.vue          # 统一预览器（含代际控制与图片并发拉取）
│   ├── SandboxedHtmlFrame.vue         # 现有静态 iframe（维持 sandbox=""）
│   └── ArtifactDrawer.vue             # [NEW/推荐] 独立成果页的右侧预览滑出抽屉
└── modules/dear-agent/
    ├── pages/DearAgentArtifactsPage.vue # 独立成果浏览器页面（网格 + 右侧抽屉）
    ├── pages/DearAgentArtifactsPage.spec.ts # 页面单元测试（重写，废弃假 history mock）
    ├── components/DearAgentSession.vue # 聊天页：接入 busy 终态刷新与成果提示
    └── run-actions.ts                 # 会话操作 transport 注入项目头
```

阅读顺序：页面当前 service/loadSessionArtifacts → session.service → workspace.service/types → useArtifacts → WorkspacePreview → ArtifactDrawer → DearAgentSession 的 busy watch。不要将同名 `services/runtime-gateway/workspace.service.ts` 当成果文件服务：本交接使用的是 `services/threads/workspace.service.ts`。

### 2.1 第一处明确修复（服务工厂装配）

```ts
// 替换页面当前未传 projectId 的 computed；根据 activeProjectId 动态创建带头服务
const service = computed(() => {
  if (!activeProjectId.value) return null;
  return createSessionService(createLanggraphAuthorizedFetch(), activeProjectId.value);
});
```

activeProjectId 为空时不调用 service.list/get。项目变更清空旧选择/分页/错误并重新加载。不要给所有 `createSessionService(fetch)` 调用机械加参数：chat composable 的 actions.fetch 已有项目头；本页原来传的是未经项目包装的授权 fetch。

## 3. 公开接口与认证约定

只调用 Platform API，基础地址由现有客户端配置。下面 URL 均为相对平台地址。所有请求需要登录 Bearer 与 `x-project-id`；浏览器不调用 `/internal/`，不签 Runtime 委托。

| 方法/地址 | 入参 | 响应 | 当前封装 |
|---|---|---|---|
| POST /api/langgraph/threads/search | limit=20、offset、metadata.graph_id=dearflow_agent | Thread 数组 | createSessionService(...).list({offset,metadata}) |
| GET /api/langgraph/threads/{id} | id，项目头 | Thread | service.get(id)；深链校验与置顶 |
| GET /api/langgraph/threads/{id}/capabilities | id，项目头 | 能力对象 | getWorkspaceCapabilities(projectId,id,signal) |
| GET /api/langgraph/threads/{id}/artifacts | limit=100、可选 cursor | WorkspacePage<ArtifactRef> | getArtifacts(projectId,id,params,signal) |
| GET /api/langgraph/threads/{id}/workspace/preview | path 必填 | 按 Content-Type 分支 | getWorkspacePreview(projectId,id,path,signal)；**仅 preview_kind !== 'download' 时调用** |
| GET /api/langgraph/threads/{id}/workspace/content | path 必填 | 原字节附件 | getWorkspaceContentBlob(projectId,id,path,signal) |

query 参数交给客户端编码。不要把 path 手工拼接到 URL，也不要将其当 HTML 字符串插入页面。所有 private 响应 no-store；客户端状态/cache key 至少包含 projectId/threadId/path。

### 3.1 会话查询与深链处理

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

1. **会话列表分页**：按 offset=0, 20, 40... 追加加载；标题或底部提示“已加载 N 个会话”。
2. **深链 `?threadId=` 回显策略**：
   - 用户访问带 `threadId` 路由时，若首屏 20 条会话中存在，直接选中高亮；
   - 若首屏不存在，独立调用 `service.get(threadId)`：
     - 若成功且 `metadata.graph_id === 'dearflow_agent'`：将其作为临时会话**前置插入到会话列表顶部**并保持选中状态；
     - 若返回 404 或 403：右侧成果区展示明确的“会话不存在或无权访问”空态/错误态，**严禁静默 fallback 选中第一条无辜会话**！

### 3.2 capabilities

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

artifacts 数组实际由 Runtime 全部支持 MIME 去重排序得到；表示可发布类型，不保证可预览，也不授予写工具权限。workspace=false 与请求失败必须分开处理。

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

确定性接口样例（真实 9 字节 UTF-8 `# report\n`）：

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
| preview_kind | 唯一渲染分支依据 | **download 类型直接展示下载卡片，不发 preview 请求** |
| next_cursor | 原样带回下一页 | 不是页码，不从 cursor 解码出业务信息 |

没有 `total/display_name/created_at/run_id/source_message_id/slides`。首批隐藏发布时间/来源步骤，保留所属线程；不要借 checkpoint ID 或遍历消息“补齐”不存在的合同。

## 5. 分页、刷新与状态复用设计（`useArtifacts`）

为彻底解耦复杂的“工作区目录树/终端”与“纯成果展示”，**抽取独立的 `useArtifacts` composable**，聊天工作区面板 `WorkspacePanel.vue` 和独立成果页 `DearAgentArtifactsPage.vue` 均复用此 composable：

```ts
// src/composables/useArtifacts.ts 核心接口形态
export function useArtifacts(
  projectId: Ref<string>,
  threadId: Ref<string>,
) {
  const artifacts = ref<ArtifactRef[]>([]);
  const cursor = ref<string | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const hasMore = computed(() => cursor.value !== null);

  // 选中项与预览状态
  const selectedArtifact = ref<ArtifactRef | null>(null);
  const previewResult = shallowRef<WorkspacePreviewResult | null>(null);
  const loadingPreview = ref(false);
  const previewError = ref<string | null>(null);

  // 动作
  async function loadInitial(): Promise<void>;
  async function loadMore(): Promise<void>;
  async function refresh(): Promise<void>;
  async function selectArtifact(item: ArtifactRef): Promise<void>;
  function clearSelection(): void;
  async function downloadArtifact(item: ArtifactRef): Promise<void>;

  return {
    artifacts,
    cursor,
    loading,
    error,
    hasMore,
    selectedArtifact,
    previewResult,
    loadingPreview,
    previewError,
    loadInitial,
    loadMore,
    refresh,
    selectArtifact,
    clearSelection,
    downloadArtifact,
  };
}
```

### 5.1 状态管理核心规约

1. **代际保护（Scope Generation）**：
   - 每次 `projectId` 或 `threadId` 变化，递增代际编号 `generation`，中止上一个旧的 `AbortController`，清空 items、cursor 与错误；
   - 异步回调（初始加载、分页、预览）返回时，比对 `generation` 是否依然匹配；若已发生切换，立即丢弃结果，严防跨线程串台。
2. **阻断无意义的 415 请求**：
   - 在 `selectArtifact(item)` 中：
     - 若 `item.preview_kind === 'download'`：直接设置 `previewResult.value = { kind: 'download', downloadOnly: true }`，**绝不调用 `getWorkspacePreview`**；
     - 若 `item.preview_kind !== 'download'`：调用 `getWorkspacePreview` 拉取预览数据。
3. **分页与追加**：
   - 首次加载或刷新：替换整个 `artifacts.value`；
   - 加载更多：按 `item.path` 去重后追加到列表末尾；
   - `cursor === null` 表示没有更多成果。
4. **游标失效恢复**：
   - 若遇到 409 `workspace_directory_changed`，自动重新加载首页最多 1 次；若依然冲突，显示提示“成果已更新，请点击刷新”。

## 6. 预览请求消费与页内抽屉交互

### 6.1 交互设计：右侧滑出抽屉（Drawer / Slide-over）

独立页面 `DearAgentArtifactsPage.vue` 保持两栏基础结构（左侧会话、右侧成果卡片网格）。点击成果卡片上的“在线预览”或卡片主体时：
1. **触发右侧滑出抽屉**：抽屉覆盖在右侧区域上方（宽度约 50%~60% 或 640px~800px，保留半透明遮罩）；
2. **内嵌 `WorkspacePreview.vue`**：在抽屉内部呈现文件预览、Markdown 源码/渲染切换、文本复制与原文件下载操作；
3. **关闭抽屉**：点击遮罩、点击右上角关闭按钮、或按下键盘 `Esc` 键，立即关闭抽屉并清理预览状态，**原列表的滚动位置与加载进度完好保留**。

### 6.2 文本/Markdown JSON

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

沿用 WorkspacePreview 渲染/源码切换与 markdown 工具。truncated=true 提示“仅显示前 256 KiB，请下载完整文件”；本期无 load-full-preview 或 Range 接口。CSV 首批展示文本，不沿用 files.service 的简易逐行 CSV 算法承诺复杂表格支持。

### 6.3 Markdown 内部图片加载保护

针对 Markdown 文本中引用的内部图片（如 `![chart](/workspace/charts/demo.png)`）：
1. **任务代际与取消**：解析图片 URL 时绑定当前任务 ID；一旦用户切换查看其他成果或关闭抽屉，立即标记失效，后续返回的 Blob 不得污染界面；
2. **并发加载**：提取所有图片路径后，采用 `Promise.allSettled` 并发获取受保护的图片 Blob，避免串行卡顿；
3. **URL 释放**：在重新解析前及组件卸载时，遍历并调用 `URL.revokeObjectURL` 释放所有生成的临时 Object URL，杜绝内存泄漏。

### 6.4 HTML 沙箱预览

响应为 Runtime safe_html 的静态净化文本。调用现有的 `SandboxedHtmlFrame.vue`：
- 维持严格的安全策略：`sandbox=""`、`referrerpolicy="no-referrer"`；
- 明确提示：本阶段为纯静态安全沙箱，禁用一切 JavaScript 与外部引用。若 HTML 含有动态交互逻辑，引导用户点击下载原文件在本地浏览器打开。

### 6.5 Download 类型（二进制/未知类型）

PDF/XLS/XLSX/PPTX/ZIP 等二进制文件，`preview_kind` 均为 `download`。在抽屉内展示文件类型徽标、完整文件路径、文件大小、SHA256 哈希值，并提供明确的“下载原文件”按钮。客户端坚决不发出无意义的 preview HTTP 请求。

## 7. 下载与错误处理（Axios Blob 异常解包）

```ts
const { blob, fileName } = await getWorkspaceContentBlob(projectId, threadId, item.path, signal);
triggerBlobDownload(blob, fileName);
```

复用已有工具，不新写 document.createElement 下载逻辑。API 返回 attachment、ETag、no-store/nosniff；文件名当前取虚拟路径末段，未来业务名称另议。下载完成/取消/异常均解除 loading；错误时不 toast“成功”。客户端不把 token 塞 query/new-tab URL。

### 7.1 Axios Blob 错误解析规范

当服务端返回 HTTP 4xx/5xx 时，Axios 会抛出 `AxiosError`，错误 Payload 会被打包在 `error.response.data`（类型为 Blob）中。必须在 `workspace.service.ts` 中封装通用的异常解析工具函数：

```ts
// 错误解包工具函数：从 Axios Blob 响应中提取后端真实的 code 与 message
export async function unwrapWorkspaceError(err: unknown): Promise<Error> {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosResponse = (err as any).response;
    if (axiosResponse?.data instanceof Blob) {
      try {
        const text = await axiosResponse.data.text();
        const json = JSON.parse(text);
        if (json?.error) {
          const customErr = new Error(json.error.message || '请求失败');
          (customErr as any).code = json.error.code;
          (customErr as any).requestId = json.request_id;
          return customErr;
        }
      } catch {
        // 非 JSON blob，回退到 HTTP 状态码说明
      }
    }
  }
  return err instanceof Error ? err : new Error(String(err));
}
```

| 状态/code | 前端动作 |
|---|---|
| 400 project_id_required | 本页接线错误/项目尚未选定；停止请求，提示项目上下文异常 |
| 400 invalid_workspace_cursor / invalid_workspace_path | 丢弃坏 cursor 或阻止请求；不能当空列表 |
| 401 | 交给统一登录刷新；刷新失败跳登录，停止当前 scope 请求 |
| 403 thread_project_denied / runtime_target_denied / file_scope_denied | 无权访问，清掉敏感预览，禁止自动重试 |
| 403 project_role_missing | 真账号不是项目成员；清空数据，提示无项目权限 |
| 404 langgraph_thread_get_failed | 真实 Agent Server 会隐藏其他项目的线程；提示会话不存在或无权访问，不能当“暂无成果” |
| 404 artifact_not_found / workspace_file_unavailable | 文件不可用；刷新列表/返回会话，不声称发布成功 |
| 409 workspace_directory_changed | 游标失效，最多自动重新加载一轮 |
| 409 artifact_hash_mismatch | 文件完整性异常，阻止预览/成功下载，展示 request_id 便于反馈 |
| 409 workspace_capability_unavailable | 工作区能力不可用；不当游标冲突重试 |
| 413 file_too_large / html_preview_too_large | 大 HTML 可尝试原文件下载；超原文件上限不重复下载 |
| 415 workspace_preview_unsupported | 文件详情与下载降级（客户端正常流程已提前拦截） |
| 422 validation_failed / 格式校验错误 | 参数/内容错误，展示可读提示，不无限重试 |
| 502/504、网络断开或截断流 | 提供手动重试，保留已有列表，下载不报成功 |

## 8. 前端同事的开发任务（F01—F08 明确分工）

- [x] **F01 已完成** 修项目参数与服务装配：`service` 响应式依赖 `activeProjectId`，无项目时不调接口；修复 `DearAgentArtifactsPage.vue`。
- [x] **F02 已完成** 废除历史扫描逻辑：删除基于 `service.history()` 的正则与 extras 扫描代码，完全切换为标准 `getArtifacts`；实现会话深链校验置顶。
- [x] **F03 已完成** 实现独立 `useArtifacts` composable：包含 cursor 分页、列表去重、代际请求保护、阻断 download 类型的 preview 请求。
- [x] **F04 已完成** 独立成果页抽屉交互：在 `DearAgentArtifactsPage.vue` 接入右侧滑出抽屉（Drawer），内嵌 `WorkspacePreview.vue`；补全 `WorkspacePreview` 内部图片并发拉取与 URL 清理。
- [x] **F05 已完成** `workspace.service` 补 Axios Blob 错误解码：实现 `unwrapWorkspaceError`，让界面能准确拿到 `error.code`、`error.message` 与 `request_id`。
- [x] **F06 已完成** 聊天工作区对齐：`useThreadWorkspace` 增加 download 拦截，保持终态刷新契约。
- [x] **F07 已完成** 重写并清理单元测试：彻底移除基于 history 的造假测试用例，`useArtifacts`、`DearAgentArtifactsPage`、`WorkspacePreview` 单元测试全部通过。
- [x] **F08 已完成** 验收与回归：lint (0 errors)、typecheck (0 errors)、build (成功输出 dist) 全部绿灯通过。

## 9. 前端测试如何写、何时算完成

| 测试文件 | 重点断言 |
|---|---|
| `DearAgentArtifactsPage.spec.ts` | 验证 projectId 工厂参数；**断言 history 未被调用**；使用 mock getArtifacts 验证三态展示；测试非首屏深链 threadId 置顶逻辑 |
| `useArtifacts.spec.ts` (新) | 验证游标分页追加；切换 threadId 立即中止旧请求；`preview_kind === 'download'` 时**断言未发起 preview 请求**；409 游标冲突只重试一次 |
| `session.service.spec.ts` | 保留真实 Client，fetch 替身捕获 search/get 的 x-project-id，而非 mock 掉整个 service |
| `workspace.service.spec.ts` | 所有资源请求头；JSON/HTML/image 分支；Axios Blob 错误正确还原结构化错误及 request_id |
| `WorkspacePreview.spec.ts` | Markdown 内部图片并发加载与 URL revoke；任务代际切换不污染新文档；静态 sandbox 属性断言 |
| `e2e/dear-agent-artifacts.spec.ts` | 真后端发布后列出/抽屉预览/下载/刷新；无项目头 400 不再发生；按 Esc 正常退出抽屉 |

测试执行命令：

```bash
pnpm exec vitest run src/modules/dear-agent/pages/DearAgentArtifactsPage.spec.ts src/services/threads/session.service.spec.ts src/services/threads/workspace.service.spec.ts src/composables/useArtifacts.spec.ts
pnpm exec vitest run src/components/workspace/WorkspacePreview.spec.ts
pnpm lint
pnpm typecheck
pnpm build
```

## 10. 交接状态与签收

- 文档：已按审查意见完成全面更新，敲定右侧抽屉交互、独立 `useArtifacts` 状态管理、主动拦截 download 请求与 Axios Blob 错误解包机制。
- 本方后端：R/B/G1/G2 完成；未新增另一套成果接口。
- 前端同事：待根据更新后的本文档方案实施 F01—F08。
- 联合验收：G4 等待前端接入后进行真实端到端验收。

## 11. 可直接用于联调的真实样本

2026-09-21 本地栈 API：`http://127.0.0.1:2142`。使用前端既有登录流程；不要把 token 写入源码或 URL。

| 字段 | 实测值 |
|---|---|
| 项目 A（成功样本） | `bac27f9b-ac91-414c-a452-c4172a61802d` |
| 项目 B（跨项目拒绝） | `f654bf74-a485-4e15-b310-7010d0747f7a` |
| graph_id | `dearflow_agent` |
| threadId | `71e93b45-86c7-45c1-97c7-f7859e8e8958` |
| 最终 run | `55257898-08fc-4d05-90e5-96f26b07c399`，success |
| MD 内容/字节数 | `# report\n`，9 字节；path/hash 与 §4 示例完全一致 |
| CSV 内容/字节数 | `name,value\nsample,1\n`，20 字节 |
| CSV path | `/workspace/outputs/1760a6c53e823ca2878437a5eaf5cb3ede6984f742fa77ad6de132adaa56fe88.csv` |
| CSV SHA256 | `1760a6c53e823ca2878437a5eaf5cb3ede6984f742fa77ad6de132adaa56fe88` |
| CSV 类型 | `mime_type=text/csv`、`kind=text`、`preview_kind=text` |
| 列表 | 两项，按 hash 文件名顺序 CSV→MD，`next_cursor=null` |

接入后的页面深链：`/workspace/projects/bac27f9b-ac91-414c-a452-c4172a61802d/dear-agent-artifacts?threadId=71e93b45-86c7-45c1-97c7-f7859e8e8958`。
