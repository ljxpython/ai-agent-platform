# 10 平台侧文档文件接入方案

## 1. 当前完成度

| 层 | 状态 | 说明 |
|---|---|---|
| Runtime `parse_document` 工具 | 已完成 | 支持 PDF/TXT/Markdown/JSON/CSV，路径和大小受限 |
| Runtime Showcase 装配 | 已完成 | 已挂载 `DocumentToolsMiddleware` 和公共工具 |
| Runtime 文件引用 `FileRef v1` | 已完成 | Runtime 已校验 path、MIME、大小、hash 和消息 `extras.runtime_file` |
| Runtime `available_files` 上下文 | 已完成 | 每次模型调用以 system context 注入当前 uploads 文件清单 |
| Runtime 文件读取 HTTP 授权 | 已完成 | `workspace-file-upload/read` scope，线程 workspace 及 symlink 防护 |
| Platform API 文件上传/读取网关 | 待实施 | 可按本文件使用 Runtime 文件接口接入 |
| Platform Web 文件选择、上传、引用展示 | 未完成 | 需要复用图片链路但不能复制组件逻辑 |
| 扫描 PDF/OCR/复杂版面 | 未完成 | 后置能力 |
| 三服务真实 E2E | 未完成 | 必须单独验收 |

因此，Runtime 侧前置能力已完成；平台侧仍需实现用户上传、消息引用和前端展示，之后才能完成真实平台链路。

## 2. 目标链路

```text
Platform Web 选择文件
  -> 创建/取得 thread
  -> Platform API PUT 原始二进制
  -> Runtime 校验并写入 thread workspace/uploads
  -> Web 发送 FileRef v1（只含引用，不含 Base64）
  -> Showcase Agent 看到 available_files
  -> Agent 调用 parse_document(file_path, query, page_start, page_end)
  -> Runtime 返回页码、有限文本、截断状态
  -> Web 展示回答和页码引用
```

Platform API 管资源授权，Runtime 管解析、工具权限、路径安全和模型上下文。Web 不直接访问 Runtime，也不把宿主路径或文件正文发给模型。

## 3. 跨服务契约

### 3.1 `FileRef v1`

```json
{
  "version": 1,
  "path": "/workspace/uploads/<sha256>.pdf",
  "file_name": "合同.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 482193,
  "sha256": "<64 lowercase hex>"
}
```

Runtime 必须重新计算 hash、检查文件 magic bytes 和大小。`file_name` 只用于展示，不参与路径拼接。

支持 MIME：

| MIME | 扩展名 | Runtime 行为 |
|---|---|---|
| `application/pdf` | `.pdf` | PyMuPDF 逐页解析 |
| `text/plain` | `.txt` | UTF-8 文本 |
| `text/markdown` | `.md`, `.markdown` | UTF-8 文本 |
| `application/json` | `.json` | JSON 校验、格式化 |
| `text/csv` | `.csv` | 有限行读取 |

上传接口可以接收更宽的浏览器 MIME，但 API 必须把不支持类型拒绝为 415；不能让工具收到任意二进制后再猜格式。

### 3.2 消息承载

在正式消息中保留标准 text block，并将引用放在 `extras.runtime_file`：

```json
{
  "type": "text",
  "text": "[文档附件] 合同.pdf\n/workspace/uploads/<sha256>.pdf",
  "extras": {
    "runtime_file": {
      "version": 1,
      "path": "/workspace/uploads/<sha256>.pdf",
      "file_name": "合同.pdf",
      "mime_type": "application/pdf",
      "size_bytes": 482193,
      "sha256": "<sha256>"
    }
  }
}
```

消息队列、checkpoint、history 和 fork 必须保留 `extras.runtime_file`；任何节点丢失字段都判定契约失败。正文不能包含 Base64、Data URL 或完整文件内容。

### 3.3 工具结果

`parse_document` 返回的结果作为普通工具结果持久化，结构固定为：

```json
{
  "version": 1,
  "file": {"path": "/workspace/uploads/x.pdf", "sha256": "..."},
  "format": "pdf",
  "pages": 12,
  "matched_pages": [2, 3],
  "text": "有限文本",
  "chunks": [{"text": "...", "page": 2}],
  "truncated": false,
  "warnings": []
}
```

Web 只展示 `text`、`chunks[].page` 和 `warnings`；不能把完整工具结果原样塞进 Markdown HTML。`truncated=true` 时显示“内容已截断，可继续按页查询”。

## 4. Platform API 实施

### 4.1 文件

复用图片网关的文件结构，不新增第二套服务：

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py`
  - 增加 `upload_thread_file()`、`read_thread_file()`。
- `adapters/langgraph/runtime_gateway_upstream.py`
  - PUT 使用 raw binary streaming，不 JSON、不 Base64。
  - GET 只透传 `Content-Type`、`Content-Length`、`ETag`、`Cache-Control`。
- `runtime_gateway/application/service.py`
  - 复用 `_load_thread(write=True/False)`。
  - graph 从 thread metadata 读取，不能信任客户端字段。
- `runtime_gateway/presentation/http.py`
  - 暴露文件 PUT/GET。
- `core/security/tokens.py`
  - 复用 `image-upload/image-read` 语义，建议抽象成 `workspace-file-upload/workspace-file-read`；若暂不改名，必须在 operation 文档中明确其已经覆盖文档文件。

### 4.2 接口

```http
PUT /runtime/threads/{thread_id}/files/uploads/{sha256}
Content-Type: application/pdf
Content-Length: 482193

<raw bytes>
```

成功返回 `FileRef v1`。同一线程相同 hash 重复上传必须幂等。

```http
GET /runtime/threads/{thread_id}/files/content?path=/workspace/uploads/<sha256>.pdf
```

读取接口仅给授权用户使用，路径必须属于当前线程，响应大小受服务端上限约束。

### 4.3 错误映射

| 情况 | 状态码 | 错误码 |
|---|---:|---|
| 未登录 | 401 | 现有认证错误 |
| 无线程读写权限 | 403 | `thread_access_denied` |
| 文件 hash/path 非法 | 400 | `invalid_file_ref` |
| MIME 不支持 | 415 | `unsupported_file_type` |
| 文件过大 | 413 | `file_too_large` |
| 线程不存在 | 404 | `thread_not_found` |
| Runtime 拒绝 scope | 403 | `runtime_scope_denied` |
| Runtime 超时/不可达 | 502/504 | 现有 upstream 错误 envelope |

审计记录用户、tenant、project、thread、hash、MIME、大小、结果和 request id；禁止记录文件正文、Base64、token 和解析全文。

## 5. Platform Web 实施

### 5.1 文件模型

在现有附件模型上扩展，不新建全局 store：

```ts
type RuntimeFileRef = {
  version: 1
  path: string
  file_name: string
  mime_type: string
  size_bytes: number
  sha256: string
}

type DocumentAttachment = {
  file: File
  status: 'pending' | 'hashing' | 'uploading' | 'uploaded' | 'failed'
  ref?: RuntimeFileRef
  error?: string
}
```

### 5.2 发送流程

`send()`、`queueMessage()`、`fork()` 共用 `prepareMessageFiles(threadId, attachments)`：

1. 新线程先创建 thread。
2. 浏览器计算 SHA-256。
3. 通过 Platform API PUT raw `File`。
4. 所有文件成功后构造 `extras.runtime_file`。
5. 最后创建 Run 或入队消息。
6. 任何上传失败都不启动 Run，保留文本和附件，允许重试。

fork 必须把文件上传到新分支 thread，不能复用源线程路径。

### 5.3 展示

- 文档附件显示文件名、类型、大小、hash 前缀和上传状态。
- 不把 PDF 全文直接放进消息气泡。
- 工具结果显示“已读取第 2、3 页”等引用。
- `truncated=true` 显示继续查询提示。
- 读取文件预览时走认证 GET；第一版可提供下载，不要求浏览器内置 PDF viewer。
- 403/404/网络错误必须有独立 UI 状态，不显示内部路径堆栈。

## 6. Runtime 前置完成记录

以下门槛已在 Runtime 完成，平台侧可以开始正式实现：

1. `FileRef v1` 已新增并校验 path、MIME、大小、文件名和 SHA-256。
2. `parse_document` 返回完整 `file` 引用，包含 `sha256`。
3. `available_files` 已由 `DocumentToolsMiddleware` 注入模型 system context。
4. `/internal/threads/{thread_id}/files/uploads/{sha256}` 和 `/content` 已提供 Runtime 内部接口。
5. 文件 scope 已支持 `workspace-file-upload`、`workspace-file-read`，并禁止访问原生 Server 资源。
6. PDF 已检查 `%PDF-` magic bytes、损坏文件、加密 PDF、空文档和无文本层 warning。
7. Runtime 工具已接入 Showcase 内部工具授权和 schema-only 组合。

仍然不属于 Runtime 本轮完成范围：解析缓存、OCR、复杂版面、Platform API/Web 适配和真实三服务 E2E。

## 7. 验证计划

### 契约穿透

验证 Web SDK -> Platform API -> Runtime -> checkpoint -> history -> fork 全链路保留 `extras.runtime_file`，且所有请求无 Base64。

### Runtime

- PDF 第 N 页查询返回正确页码。
- query 无匹配返回空页列表和 warning。
- 超过 20 页、12,000 字符、20 MiB 均受控截断/拒绝。
- 错路径、symlink、跨线程路径、损坏 PDF、密码 PDF 均拒绝。
- schema-only graph 不读取本地文件。

### Platform API

- raw PUT/GET、幂等 hash、MIME/大小校验。
- 错 tenant/project/thread/graph 和错误 scope。
- 审计和日志无正文、token、密钥。

### Platform Web

- 新线程先创建再上传再 Run。
- send/queue/fork 共用文件预处理。
- 上传失败保留草稿。
- 刷新后能从 history 恢复文件卡片和解析结果。
- 桌面/移动端无布局溢出。

### 真实演示

1. 上传文本 PDF，提问第 3 页付款条件，回答包含页码。
2. 上传 CSV，请求现有 chart-agent 生成图表。
3. 上传扫描 PDF，显示需要 OCR，不伪造解析结果。
4. 无权限用户访问另一线程文件，得到 403/404。

## 8. 实施顺序

- [x] **F1：** 扩展 `FileRef v1` 和消息 `extras.runtime_file`。
- [x] **F2：** Runtime 文件物化 middleware、hash/magic 校验和读取接口。
- [ ] **F3：** Platform API 文件 PUT/GET 和 workspace-file scope。
- [ ] **F4：** Platform Web 文件上传、状态、send/queue/fork 接入。
- [ ] **F5：** 工具结果页码引用、CSV -> chart-agent 展示。
- [ ] **F6：** 安全、并发、失败、浏览器和真实 Server E2E。
- [ ] **F7：** 只有真实样本证明文本 PDF 不够时，才评审 OCR/Docling/Unstructured。

依赖顺序：`F1 -> F2 -> F3 -> F4 -> F5 -> F6`。F7 不阻塞文本 PDF 第一版，但不能在 F6 前偷偷加入。
