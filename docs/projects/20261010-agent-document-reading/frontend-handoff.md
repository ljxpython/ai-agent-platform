# F10 前端交接：文档读取与附件状态

> 接收方：Platform Web 维护同事。Runtime/API 和全部非前端专项验收已完成，契约已冻结；本轮前端业务代码未改。整体仍 partial，完整门禁有范围外失败；测试证据与风险见 `verification.md` / `tasks.md`。

## 代码与资源归属

- 本次代码位于 `$HOME/.codex/worktrees/3050/ai-agent-platform`，环境 ID `wt_eea61a88d620`；基线 HEAD `2f08c5462571cd0244a7181e5d0d1388341b79c4`，改动尚未提交。
- 必须直接在这个 Worktree 接续前端。另一个 Worktree 不会自动获得未提交改动；要另开环境，先协调同步代码，再按隔离规范初始化，不能复制本目录 `.local-stack/`、`.venv` 或 `node_modules`。
- 本次 Runtime 只补同一 `parse_document` 的 DOCX/PPTX 文本读取、原字节上传/下载及读取预算；API 只扩 MIME 白名单。没有新的上传接口、数据库迁移、parse_status 或 Markdown 文件。
- reader 镜像 `runtime-agent-workspace:wt_eea61a88d620-f10`；本环境私有 runtime.env 的 `RUNTIME_WORKSPACE_IMAGE` / `RUNTIME_SHOWCASE_IMAGE` 已指向它。Docker 用于隔离不可信解析，未安装 LibreOffice，不读取旧 DOC/PPT。
- 先从仓库根运行 `bash "scripts/local-stack.sh" status`；本次登记 Web `26476`、API `29257`、Runtime `26444`。启动/重启/停止只通过同一脚本，不能用公共默认端口或 kill 其他服务。
- 验收结束已只停止本环境栈、保留数据和镜像；接续时执行 `bash "scripts/local-stack.sh" start` 后访问 status 返回的 URL。本地默认账号 `admin / admin123`，只用于隔离回环环境。

必要时重建本 Worktree 专属镜像（在 `apps/runtime-service` 目录）：

```bash
docker build -f "deploy/Dockerfile.agent-workspace" -t "runtime-agent-workspace:wt_eea61a88d620-f10" "."
```

不同环境须使用自己的镜像标签和私有配置；禁止覆盖其他 Worktree 的标签或 source 整份私有 env。

## 背景与设计原则

当前聊天已统一走共用 `ChatComposer`、`useChatAttachments`、`useSessionAttachmentUpload` 和 `FileRef v1`。Runtime 已在同一个 `parse_document` 工具上支持有限 DOCX/PPTX 读取，并彻底移除了每轮全 uploads 扫描膨胀问题。前端复用现有 raw 上传、消息引用和 ToolResult 投影。

### 借鉴与反思（DeerFlow & Open-SWE）
1. **借鉴 DeerFlow 的草稿保护机制**：无论网络异常、后端 415/413/422 拒绝还是工具读取失败，用户输入框内的文本和附件草稿必须钉死保留，**严禁自动清空用户输入，严禁上传失败时自作主张发起 Run**。
2. **规避 DeerFlow 的重度 Ingestion 陷阱**：严禁在上传时同步或异步转 Markdown，严禁在前端推断或伪造“已解析为 Markdown”状态；保持原始不可变字节与 FileRef v1，Agent 按需调用工具。
3. **借鉴 Open-SWE 的惰性有界读取与强边界防护**：严格限制单次读取字符与范围预算，前端必须准确呈现截断、段落/幻灯片索引与安全警告，不可信正文严格作为纯文本安全渲染，防范提示注入与 XSS。

### 可视状态派生与展示语义（单一事实源）

前端不持久化任何新增的 `parse_status` 字段，也不维护独立的解析全局 store。状态严格从上传草稿状态与 SDK 的 `ToolMessage/ToolResult` 派生。

展示状态按以下**绝对优先级**派生：

1. **`error`（最高优先级）**：
   - 上传阶段：网络失败、API 4xx/5xx 报错。附件卡片标红展示错误，输入框保留文本与草稿附件。
   - 读取阶段：`tool.status === 'error'` 或抛出操作失败。`ToolResult` **必须优先展示错误信息，绝不可进入成功结果渲染**！
2. **`warning` / `no_text`**：
   - 工具执行成功但无文本内容（`document_no_text`）或命中警告限制。展示黄色警告条，不伪称成功读完。
3. **`truncated`**：
   - `truncated === true`。明确展示内容截断及对应的翻页/分段建议，若包含 `next_read` 则显示续读范围参数。
4. **`parsed`**：
   - 成功返回非空文本且无严重阻断。显示“已读取片段”，标明格式（DOCX/PPTX/PDF）与范围（段落/幻灯片/页码）。
5. **上传在途/完成状态**：
   - `pending`：选中文件，尚未发起上传。可移除草稿。
   - `uploading`：计算 SHA-256 并 PUT 中。按钮 loading，禁止重复触发。
   - `uploaded`：API 返回合法 `FileRef v1`。显示“已上传”，允许发送消息与创建 Run，**绝不宣传“已解析”**。

## 需要改动的现有文件与重构要点

必须遵循 KISS 与 DRY 原则，杜绝重复硬编码：

### 1. `apps/platform-web/src/utils/chat-content.ts`（MIME 与扩展名唯一事实源）
- **扩展格式定义**：
  - `SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES` 补充 DOCX（`application/vnd.openxmlformats-officedocument.wordprocessingml.document`）和 PPTX（`application/vnd.openxmlformats-officedocument.presentationml.presentation`）。
  - `SUPPORTED_FILE_EXTENSIONS` 补充 `.docx` 和 `.pptx`。
- **加固 `resolveDocumentMime(file: File)`**：
  - 针对 `.docx` 返回标准 WordprocessingML MIME。
  - 针对 `.pptx` 返回标准 PresentationML MIME。
  - 增加常见系统别名/注册表脏 MIME 规范化映射（如 `application/vnd.ms-word.document.12`、`application/msword`、`application/x-zip-compressed` 修正为标准 Office MIME）。
  - 当 `file.type` 为空字符串或非标准类型时，必须按扩展名准确推断标准 MIME，兜底才使用原 `file.type` 或抛错，**绝不能无条件回退成 `application/octet-stream` 导致后端 415 拒绝**。
- 导出通用的 MIME 解析纯函数供 `files.service.ts` 复用，杜绝多处重复定义。

### 2. `apps/platform-web/src/services/threads/files.service.ts`（文件服务层防乱码与契约加固）
- **复用统一 MIME 定义（DRY）**：
  - `ALLOWED_DOCUMENT_MIMES` 与 `ALLOWED_DOCUMENT_EXTENSIONS` 直接复用 `chat-content.ts` 导出的定义，禁止维护两套不一致的列表。
- **重构 `uploadThreadFile()`**：
  - 彻底移除 `const mimeType = file.type || "application/octet-stream"` 的危险写法！
  - 改为调用 `resolveDocumentMime(file)` 获取校验后的标准 MIME，作为 `Content-Type` 发往后端，彻底解决 Windows / 空 type 环境下的 415 报错。
- **加固 `previewThreadFileInNewTab()` 二进制下载拦截**：
  - 二进制原字节下载判定必须同时检查后缀与 MIME 类型：
    ```ts
    const isBinaryDocument =
      lower.endsWith(".zip") ||
      lower.endsWith(".pptx") ||
      lower.endsWith(".docx") ||
      lower.endsWith(".xlsx") ||
      lower.endsWith(".xls") ||
      lower.endsWith(".bin") ||
      mime.includes("wordprocessingml") ||
      mime.includes("presentationml") ||
      mime.includes("spreadsheetml") ||
      mime.includes("zip");
    ```
  - DOCX 与 PPTX 必须直接触发 `downloadThreadFile()` 原字节安全下载，**严禁调用 `readBlobAsText(blob)`**，彻底杜绝把 zip 压缩包作为 UTF-8 乱码弹窗渲染的事故。

### 3. `apps/platform-web/src/modules/chat/components/ChatAttachmentPreview.vue`（附件卡片）
- `fileTypeLabel` 计算属性扩展：
  - `.docx` / `wordprocessingml` → `Word 文档`（带文件大小）
  - `.pptx` / `presentationml` → `PPT 演示文稿`（带文件大小）
- 完善上传状态呈现（`uploading` 呈现加载态，`failed` 呈现错误态，`uploaded` 呈现已上传状态），长文件名必须有省略/防溢出保护。

### 4. `apps/platform-web/src/modules/chat/components/ToolResult.vue`（工具结果关键修复）
现有代码存在**重大结构性缺陷**，必须按以下要求重构：
- **【核心修复】错误分支绝对优先**：
  - 检查现有第 721 行 `!['write_todos', 'parse_document'].includes(tool.name)` 导致错误被排除的问题。
  - 在 `tool.name === 'parse_document'` 模板的**最顶层**，首先判定 `v-if="tool.status === 'error'"`！若出错，立即渲染结构化错误或错误详情卡片，**严禁让错误结果滑入正常文档成功模板**！
- **语义化区分文档类型（PDF vs DOCX vs PPTX）**：
  - **DOCX 语义**：
    - 总量：`typeof result.sections === 'number'` → `共 {{ result.sections }} 个段落/表格`
    - 命中：`Array.isArray(result.matched_sections)` → `已命中第 {{ result.matched_sections.join("、") }} 段`
    - 截断提示：`内容已截断，可继续指定 section_start 和 section_end 查询后续段落`
    - 顶部副标题（`displaySubtitle`）：展示 `· ${fileName} (第 ${sections.join("、")} 段)`
  - **PPTX 语义**：
    - 总量：`typeof result.pages === 'number'` → `共 {{ result.pages }} 张幻灯片`
    - 命中：`Array.isArray(result.matched_pages)` → `已命中第 {{ result.matched_pages.join("、") }} 张幻灯片`
    - 截断提示：`内容已截断，可继续指定 page_start 和 page_end 查询后续幻灯片`
    - 顶部副标题：展示 `· ${fileName} (第 ${pages.join("、")} 张幻灯片)`
  - **PDF 语义**：保留现有的 `pages` / `matched_pages` / `第 X 页` 展现。
- **Chunk 详情与偏移量**：
  - Chunk 索引标签按格式动态渲染：DOCX 显示 `第 {{ chunk.section }} 段`；PPTX 显示 `第 {{ chunk.page }} 张幻灯片`；PDF 显示 `第 {{ chunk.page }} 页`。
  - 若包含 `chunk.char_offset`（Office 格式必含），显示字符偏移量（如 `偏移: {{ chunk.char_offset }}`）。
- **`next_read` 续读建议呈现（UI 规范）**：
  - 当 `result.next_read` 存在时，在截断/警告区下方以次级胶囊标签或折叠信息条清晰展示：
    - DOCX：`建议续读参数: section_start = {{ result.next_read.read_options?.section_start }}`
    - PPTX：`建议续读参数: page_start = {{ result.next_read.read_options?.page_start }}`
  - **严禁前端根据 `next_read` 自动创建新 Run 或自动发起接口调用**！仅作可观测信息呈现，由用户或后续 Agent 自主决策。
- **文件名回显防哈希暴露**：
  - 后端在沙箱中的路径是 `/workspace/uploads/<64 hex>.docx`。
  - 组件内优先尝试从上下文或 `stream.messages` 中按 `path` 匹配 `extras.runtime_file.file_name`；若未匹配到，则安全降级为路径末尾文件名，并配以明确的格式标签，避免直接暴露混乱的 64 位长哈希。
- **Warning 字典完整补齐与未知 Warning 安全脱敏**：
  - `formatDocumentWarning` 必须覆盖以下全部映射：
    - `docx_body_only` → `已读取正文，页眉页脚等未包含`
    - `docx_table_structure_flattened` → `表格结构可能简化`
    - `presentation_text_only` → `仅读取幻灯片文本，图片与动画未解析`
    - `/^slide_(\d+)_no_text_layer_ocr_required$/` → `第 $1 张幻灯片无可读取文本`
    - `/^page_(\d+)_no_text_layer_ocr_required$/` → `第 $1 页无文本层（纯扫描页），需要 OCR 识别`
    - `document_no_text` → `文档内没有可读取的文本内容`
    - `no_query_match_in_selected_range` → 根据格式动态展示：DOCX 为 `在指定段落范围内未匹配到关键词`；PPTX 为 `在指定幻灯片范围内未匹配到关键词`；PDF 为 `在指定页码范围内未匹配到关键词`
    - `external_relationship_ignored` → `外部链接已忽略`
    - `csv_row_limit_2000` → `CSV 达到 2000 行上限，超出部分已受控截断`
    - `use_data_analysis_skill_in_sandbox` → `该表格交由数据分析工具读取`
  - **安全兜底**：未知 warning **严禁直接返回 `w` 原文**（防止 XSS 及上游异常泄漏），必须统一回退为：`文档读取提示：存在未识别的格式限制`。
- **正文纯文本安全渲染**：
  - `chunk.text` 与 `result.text` 维持现有的 `whitespace-pre-wrap` 文本插值渲染，严禁使用 `v-html`，防止不可信文档正文造成 XSS。

### 5. `apps/platform-web/src/modules/chat/composables/useChatAttachments.ts`
- 保持现有的 8 个文件 / 总量 30 MiB / 单文档 20 MiB 限制。
- Toast 报错文案更新：将原有的“当前聊天支持图片（JPEG/PNG/WEBP）以及文档（PDF/TXT/MD/JSON/CSV）”修正为包含 Word (DOCX) 与 PPT (PPTX)。

### 6. `apps/platform-web/src/modules/chat/composables/useSessionAttachmentUpload.ts`
- 保持“上传成功后才挂载 FileRef 提交消息”的时序。
- 单个附件上传失败必须阻断消息提交，弹出明确 Toast，但**保留当前未完成上传的草稿附件与用户输入框文本**，不得发起无效 Run。

---

## 后端输入/输出契约（已冻结）

### 上传端点
`PUT /api/langgraph/threads/{thread_id}/files/uploads/{sha256}?file_name=...`
- 请求 Header：`Content-Type` 必须为准确的 Office MIME（DOCX: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`；PPTX: `application/vnd.openxmlformats-officedocument.presentationml.presentation`）。
- 请求 Body：原始二进制 bytes。
- 成功响应：严格返回 `RuntimeFileRef` 六字段（禁止增加/假设 `markdown_*`、`parsed` 等假状态）：
```ts
type RuntimeFileRef = {
  version: 1;
  path: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
};
```

### 消息文本块契约
```json
{
  "type": "text",
  "text": "[文档附件] 方案.docx\n/workspace/uploads/<sha256>.docx",
  "extras": {
    "runtime_file": {
      "version": 1,
      "path": "/workspace/uploads/<sha256>.docx",
      "file_name": "方案.docx",
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "size_bytes": 1234,
      "sha256": "<64位十六进制哈希>"
    }
  }
}
```

### `parse_document` 输出契约（已验证样本）

#### 1. DOCX 返回样本
```json
{
  "version": 1,
  "file": {
    "version": 1,
    "path": "/workspace/uploads/<64 hex>.docx",
    "file_name": "<64 hex>.docx",
    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "size_bytes": 36746,
    "sha256": "<64 hex>"
  },
  "format": "docx",
  "sections": 45,
  "read_range": [1, 20],
  "matched_sections": [2],
  "chunks": [
    {
      "section": 2,
      "char_offset": 0,
      "text": "交付时间为周五。"
    }
  ],
  "text": "交付时间为周五。",
  "truncated": true,
  "warnings": ["docx_body_only", "docx_table_structure_flattened"],
  "next_read": {
    "file_path": "/workspace/uploads/<64 hex>.docx",
    "query": "交付",
    "read_options": { "section_start": 21 }
  }
}
```

#### 2. PPTX 返回样本
```json
{
  "version": 1,
  "file": {
    "version": 1,
    "path": "/workspace/uploads/<64 hex>.pptx",
    "file_name": "<64 hex>.pptx",
    "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "size_bytes": 52140,
    "sha256": "<64 hex>"
  },
  "format": "pptx",
  "pages": 12,
  "read_range": [1, 5],
  "matched_pages": [1, 3],
  "chunks": [
    {
      "page": 1,
      "char_offset": 0,
      "text": "季度架构总结汇报"
    }
  ],
  "text": "季度架构总结汇报",
  "truncated": true,
  "warnings": ["presentation_text_only"],
  "next_read": {
    "file_path": "/workspace/uploads/<64 hex>.pptx",
    "query": null,
    "read_options": { "page_start": 6 }
  }
}
```

---

## 前端专项验收清单

- [ ] **MIME 与上传健壮性 (Vitest)**：
  - 测试 `.docx` / `.pptx` 文件正常识别并解析出标准 MIME。
  - 测试 `file.type === ""`、大写扩展名 `.DOCX`、别名/脏 MIME 下，`resolveDocumentMime` 能稳定推断出合法标准 MIME。
  - 测试 `uploadThreadFile` 真正发出的请求 Header 中包含确切的 MIME，而非 `application/octet-stream`。
  - 测试上传失败时，草稿文本与附件状态不丢失，不触发 Run 创建。
- [ ] **下载与防乱码验证 (Vitest)**：
  - 测试 `previewThreadFileInNewTab` 在文件名包含 `.docx` 或 MIME 包含 `wordprocessingml` 时，直接路由至 `downloadThreadFile` 原字节下载，绝不调用 `readBlobAsText`。
- [ ] **ToolResult 投影与错误优先 (Vitest)**：
  - 测试 `tool.status === 'error'` 时，`parse_document` 优先渲染错误信息，不渲染空白成功卡片。
  - 测试 DOCX 渲染：正确展示 `sections`、`matched_sections`（“段”），截断提示含 `section_start/section_end`。
  - 测试 PPTX 渲染：正确展示 `pages`、`matched_pages`（“幻灯片”），截断提示含 `page_start/page_end`。
  - 测试 `next_read` 正确呈现建议续读参数。
  - 测试全部 7 类 warning 转换文案正确；测试未知 warning 返回安全脱敏文案，无 XSS 风险。
  - 测试 Excel 特殊标记 `use_data_analysis_skill_in_sandbox` 转换提示正确。
- [ ] **全量静态门禁**：
  - `pnpm --filter platform-web typecheck`（0 errors）
  - `pnpm --filter platform-web lint`（0 errors）
  - `pnpm --filter platform-web build`（编译成功）
- [ ] **E2E 浏览器验收 (Playwright)**：
  - Showcase DOCX 完整上传、Agent 读取与 ToolResult 渲染。
  - DearFlow PPTX 完整上传、Agent 读取与 ToolResult 渲染。
  - 刷新页面与分支 Fork 后，历史 DOCX/PPTX ToolResult 正常重放与恢复。
  - 上传非法文件或权限拒绝 (403) 时的友好错误呈现。
  - 移动端窄屏与深浅双色主题下样式无溢出。

---

## 可直接转发话术

请接续 F10 通用文档读取的前端开发。代码在 `$HOME/.codex/worktrees/3050/ai-agent-platform`（环境 ID `wt_eea61a88d620`），后端改动尚未提交，请在此 Worktree 接续。Runtime/API 已完成 DOCX/PPTX 原字节上传下载和同一 `parse_document` 的有界文本读取，沿现有 FileRef/Agent/Docker 隔离链路，没有上传自动转 Markdown，也没有新增解析状态接口。

前端交接文档已完成全面审查与重构升级，排除了“错误被模版吞掉”、“MIME 空 type 触发 415 拒绝”、“DOCX 预览二进制乱码”以及“DOCX/PPTX 被粗暴当成 PDF 页码”等多项设计缺陷，并明确了 DRY 统一事实源与纯文本安全防护规范。

请仔细阅读 `docs/projects/20261010-agent-document-reading/frontend-handoff.md`。你负责：
1. **Task 3.1**：在 `chat-content.ts` 统一定义 DOCX/PPTX MIME 与扩展名；重构 `files.service.ts` 的 `uploadThreadFile` 解决空 type/alias 隐患；补全 `previewThreadFileInNewTab` 的 DOCX/MIME 原字节下载拦截；在 `ChatAttachmentPreview.vue` 补齐类型标签与状态。
2. **Task 3.2**：重构 `ToolResult.vue` 保证【错误绝对优先】；按 DOCX（段落/表格 sections）与 PPTX（幻灯片 pages）语义化展示范围、命中、截断和 next_read；补齐全部 7 类 warning 映射并对未知 warning 脱敏；确保纯文本安全渲染，不自动创建续读 Run。
3. **验收**：通过 Vitest 单元测试、typecheck、lint、build，以及 Playwright 双图 Office 读取、刷新/fork、失败、窄屏和深浅色验收，并回填 tasks/verification。

联调仅使用本 Worktree 根目录脚本：`bash "scripts/local-stack.sh" start/status/stop`。前端验收完成前，整项目保持 partial 状态。
