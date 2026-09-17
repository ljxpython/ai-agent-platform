# 沙箱文件与 API 契约

## 目标

为每个 tenant/project/thread 提供稳定、可审计的工作区文件访问和产物读取契约，支持 local 与 Docker 两种 Runtime 后端。本专题优先完成 runtime-service 与 platform-api，前端只消费冻结后的契约。

## 方案设计

### 工作区分层

```text
/workspace/          # 虚拟根，由 resolve_thread_workspace 映射到线程目录
├── work/            # Agent 工作文件
├── uploads/         # 已上传文件
├── generated/       # 生成图片
├── charts/          # 图表文件
└── outputs/         # 已发布不可变副本 <sha256>.<ext>
```

根目录也可能有 Showcase 示例文件。第一阶段不新增 artifacts 目录或对象存储；线程目录仍由 Runtime 持久化。平台 API 负责鉴权与代理；Runtime 在真实文件 IO 边界执行路径、类型和大小检查。文件级落点见 [04](04-code-change-map.md)。

### API

- `GET /api/langgraph/threads/{thread_id}/workspace/tree?path=/workspace`：返回单层目录 `items/next_cursor`，entry 包含 `path/name/type/size_bytes/mtime/mime_type/preview_kind/is_artifact`；展开子目录传子目录 path，同目录翻页传 cursor。
- `GET /api/langgraph/threads/{thread_id}/workspace/content?path=...`：原文件下载，固定 attachment，未知二进制按 octet-stream，仅允许有界读取。
- `GET /api/langgraph/threads/{thread_id}/workspace/preview?path=...`：有界预览；文本返回 `text/truncated/preview_kind`，图片返回校验后的图片，HTML 返回带限制策略的预览文档。具体响应模型与 OpenAPI 在后端实施时冻结。
- `GET /api/langgraph/threads/{thread_id}/artifacts`：分页列举 outputs，返回 `items/next_cursor`，引用沿用 `artifact_id/path/file_name/mime_type/size_bytes/sha256`，新增 `preview_kind`。不虚构原始文件名、created_at 或 source_message_id。
- artifact 用 path 调用 workspace 预览/下载；保留已有 `files/content?path=...`。不新增按 artifact_id 下载的接口，也不新增刷新 POST；重新 GET 即刷新。

Platform Web 对接约定：所有请求经过 Platform API `/api/langgraph/threads/...`，沿用认证和 `x-project-id`，不要请求 Runtime `/internal/...`；初始 tree 固定请求 `/workspace`；path 原样传递且进行 URL 编码，不能拼接宿主目录；artifacts 使用 path 作为前端 key；发布工具完成或运行终态触发列表失效，不传输大文件内容；401/403/404/409/413/415 必须显示为错误，不能当空目录。

目录和产物列表带 `next_cursor`；文本预览带 `truncated`；artifact 有 sha256，普通目录枚举不计算每个文件的摘要。tenant/project/thread 不回显为可推断宿主路径；scope 只从认证上下文取得。

`preview_kind` 只允许 `text`、`markdown`、`image`、`html-sandbox`、`download`；目录为 null。PDF 首期下载，暂不引入另一种 iframe。前端依据服务端值渲染，不根据文件名自行决定是否 iframe。

### 访问和安全

- 所有接口复用 Platform API 当前 delegation + project/thread scope 校验。
- 只允许当前线程 `/workspace` 虚拟根下的普通文件/目录；拒绝 `..`、符号链接、特殊文件、绝对宿主路径和跨线程访问。发布源另受 `work/generated/charts` 白名单限制。
- 文本预览设置字节上限；二进制只允许安全 MIME 白名单。
- JS 源文件只做文本展示。HTML 使用 `sandbox=""`，不授予 `allow-same-origin`、导航、弹窗、表单、下载权限；下载由面板单独调用鉴权 API。
- HTML 使用 opaque origin 和最小 CSP：`default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'`。平台 token 不进入预览文档。第一期仅支持静态自包含 HTML；后端移除脚本、导航、表单和嵌入元素，外链/相对资源不自动代理。
- 鉴权 fetch 后转 Blob/srcdoc 会丢失原响应头 CSP；Runtime 必须生成带首部 CSP meta 的受限预览文档，平台也保留 CSP 响应头，前端不得直接加载原始下载内容。浏览器验收覆盖自导航、外链请求和恶意脚本；无法满足隔离要求时只能展示源码，不以“有 iframe”代替安全验收。
- 下载直接由 Platform API 代理，不能把 Runtime 本地路径返回给浏览器。

## 任务拆分

- [x] Runtime：实现线程工作区目录列举、普通文件读取和 artifact 列表读取
- [x] Platform API：统一代理 `/api/langgraph/threads/{thread_id}/workspace/*`、`/artifacts`
- [x] 定义 Pydantic 响应模型、MIME/大小/分页限制和错误码
- [x] 增加跨项目、跨线程、路径穿越、符号链接、HTML CSP 测试
- [x] 第一阶段使用实时目录读取，不维护索引或缓存
- [x] 冻结前端对接契约并提供 OpenAPI/示例响应；前端实现放后续阶段

## 验证要求与记录

- [x] Runtime 文件树/内容/Artifact 单元与组合测试
- [x] Platform API → Runtime 文件读取集成测试
- [x] 401/403/404/409/413/415 错误矩阵
- [x] HTML、Markdown、Python、PNG、CSV、PPTX、ZIP 的响应策略测试

## 状态

后端 done：目录、内容、列表、权限矩阵、两服务 HTTP 和双浏览器 HTML 安全验证通过。实际响应见 [05](05-frontend-handoff.md)，验证边界见 [记录](verification.md)。
