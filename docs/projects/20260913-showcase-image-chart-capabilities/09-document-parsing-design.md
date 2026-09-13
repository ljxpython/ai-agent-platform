# 09 文档解析能力设计：PDF 与通用文件

## 状态

- **状态：** Runtime 第一版已实现；Platform 文件上传契约、OCR、复杂版面和全链路验收仍在规划中。本文件保留为后续实施基线。
- **目标：** 在 Showcase 中增加“读取线程文件并提取内容”的公共 Runtime 能力，同时让未来 Agent 复用同一套文件引用、解析结果和安全边界。
- **首版范围：** PDF、纯文本、Markdown、JSON、CSV、DOCX（可选后置）。优先保证文本型 PDF；扫描 PDF 的 OCR 不放进首版主链路。

## 1. 结论：工具负责解析，Middleware 负责准备上下文

不要把完整文档解析塞进 Middleware。Middleware 会对每次模型调用执行，若自动扫描整个线程文件，会造成重复解析、不可预测延迟和上下文膨胀。

采用两层：

1. **公共文件 Middleware：** 在模型调用前校验文件引用、补充文件清单/解析状态，禁止把原始二进制或超长全文直接注入模型；只做轻量准备。
2. **公共 `parse_document` Tool：** Agent 明确选择文件后调用，按 MIME/扩展名解析，返回摘要、页/行范围和可继续读取的解析产物。

因此 Showcase 只需要装配公共 middleware 和 tool；业务 Agent 不实现 PDF 库调用。

## 2. LangChain/LangGraph 能力边界

LangGraph 本身提供图执行、状态、checkpoint、middleware 和 tool 编排，没有一个“通用 PDF 解析器”。LangChain 提供的是标准化 `Document`、Document Loader、Text Splitter 等 building blocks：

- 官方 PDF 示例可直接使用 `pypdf.PdfReader` 生成每页 `Document(page_content, metadata={source, page})`；再用 `RecursiveCharacterTextSplitter` 分块。
- LangChain 文档列出 Unstructured、Docling、MinerU 等 PDF loader，但这些属于不同外部依赖/服务，不能因为“LangChain 有集成”就全部装进 Runtime。
- 官方 JavaScript 文档明确 `BaseLoader.loadAndSplit` 已移除，正确做法是先 `load()` 再显式调用 splitter；Python 侧也应保持同样的分层。

本项目建议：**首版直接复用 `pypdf` + `langchain_core.documents.Document` + `RecursiveCharacterTextSplitter` 的最小组合**。表格、版面、扫描 OCR 需要真实样本证明后，再单独引入 Docling/Unstructured 等重依赖。

参考：

- [LangChain PDF loaders](https://docs.langchain.com/oss/python/integrations/document_loaders/index#pdfs)
- [LangChain load and split a PDF](https://docs.langchain.com/oss/python/langchain/knowledge-base#load-and-split-a-pdf)
- [DeepAgents retrieval building blocks](https://docs.langchain.com/oss/python/deepagents/retrieval#building-blocks)

## 3. 文件引用契约

复用 04 的线程 workspace 和 `ImageRef` 思路，新增 `FileRef v1`。图片也是文件，但图片识别仍走现有图片工具；`parse_document` 只接受文档 MIME。

```json
{
  "version": 1,
  "path": "/workspace/uploads/<sha256>.pdf",
  "file_name": "合同.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 482193,
  "sha256": "<64hex>"
}
```

约束：

- `path` 只能属于当前线程 `/workspace/uploads/`；工具不得读取用户传入的宿主绝对路径。
- `sha256`、大小、MIME、扩展名和文件 magic bytes 必须由 Runtime 再校验，不能信任前端。
- 文件上传仍通过现有 Platform API -> Runtime 二进制网关；不把 Base64 放进消息队列。
- 历史消息中只保存 `FileRef` 和解析摘要，不保存完整全文。

## 4. `parse_document` Tool 契约

```python
@tool
def parse_document(
    file_path: str,
    query: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> DocumentParseResult:
    """解析当前线程 workspace 中的文档；不接受宿主文件路径。"""
```

首版返回稳定结构，不直接返回一大段字符串：

```json
{
  "version": 1,
  "file": {"path": "/workspace/uploads/a.pdf", "sha256": "..."},
  "format": "pdf",
  "pages": 12,
  "matched_pages": [2, 3],
  "text": "最多 12000 字符的相关内容",
  "chunks": [
    {"text": "...", "page": 2, "start_index": 1200}
  ],
  "truncated": false,
  "warnings": []
}
```

行为规则：

- 没有 `query` 时返回首页/指定页范围的有限文本，不把整本大文件塞进上下文。
- 有 `query` 时先按页提取，再在服务端做简单关键词匹配；首版不引入向量库和后台索引。
- `page_start/page_end` 为 1-based、闭区间，超出范围返回参数错误。
- 默认单次最多读取 20 页、返回 12,000 字符；达到上限设置 `truncated=true`，Agent 可继续按页调用。
- 返回 metadata：页码、行/字符偏移、原文件 hash，便于回答时引用“第 N 页”。
- 解析失败返回受控错误和 `warnings`，不返回堆栈、宿主路径或文件正文。

## 5. 格式策略

| 格式 | 首版策略 | 解析器 |
|---|---|---|
| PDF 文本层 | 支持，逐页保留页码 | `pypdf` |
| 扫描 PDF | 明确提示需要 OCR，首版不自动调用视觉模型 | 后置 Docling/OCR 服务 |
| TXT/Markdown | 支持，按字符范围分块 | Python stdlib |
| JSON | 支持，格式化后按路径/行范围返回 | Python stdlib |
| CSV | 支持表头和有限行范围；不把整表放上下文 | Python `csv` |
| DOCX | 后置；评估 `python-docx` 后再加入 | 独立依赖 |
| XLSX/PPTX | 后置，不与 PDF 需求捆绑 | 独立评估 |
| 图片 | 继续走识图工具，不走 `parse_document` | 现有多模态 tool |

## 6. Middleware 设计

新增 `DocumentContextMiddleware`，职责保持很小：

1. 识别当前消息中的 `FileRef v1`，校验它属于当前 thread。
2. 在 Runtime context 中注入 `available_files`（文件名、MIME、大小、hash、是否已解析），不注入全文。
3. 为模型提示补一句固定能力说明：需要内容时调用 `parse_document`，回答必须引用页码/范围。
4. 对旧 Base64/非法路径做拒绝或兼容物化，沿用图片 Middleware 的安全策略。

Middleware 不做网络下载、不调用 OCR、不自动解析所有附件、不修改 checkpoint 中的原始文件引用。

## 7. 缓存与产物

首版使用线程 workspace 下的派生文本缓存：

```text
/workspace/parsed/<sha256>.json
```

缓存 key 为文件 hash + parser version + parser options。相同文件重复解析直接复用；解析器版本变化自然失效。缓存只存解析文本和页 metadata，不存模型 prompt、用户 token 或完整审计正文。

不引入数据库、向量库、后台任务队列和跨线程共享缓存。后续确实需要跨轮检索时，再新增索引层项目。

## 8. 安全与资源限制

- 只允许当前 thread workspace 文件；禁止 `..`、symlink、NUL、宿主绝对路径和跨租户路径。
- 上传沿用文件大小/数量限制；解析再设置单文件解析上限、页数上限、解压后大小上限和单次 CPU/超时上限。
- PDF 解压炸弹、恶意嵌入文件、脚本和外链全部按纯文本处理，不执行嵌入内容。
- 日志只记录 thread、hash、格式、页数、耗时、结果和错误码，不记录正文。
- 解析结果必须经过输出截断；工具不可因一个大文件耗尽 Agent 上下文。

## 9. Showcase 演示场景

1. 上传一份文本 PDF，提问“第 3 页的付款条件是什么”，Agent 调用 `parse_document`，回答带页码。
2. 上传 CSV，提问“按月份汇总销售额”，Agent 先解析有限行/表头，再交给现有图表子 Agent 生成图表。
3. 上传扫描 PDF，Agent 明确返回“未检测到文本层，需要 OCR”，不假装已经读懂。
4. 上传 Markdown/JSON，验证通用 `FileRef` 和页/行范围引用。

图表子 Agent 仍只接收结构化解析结果或临时 CSV 文件引用，不直接读取宿主路径。

## 10. 实施任务与门禁

- [ ] **D0 样本集：** 准备文本 PDF、扫描 PDF、超大 PDF、恶意/损坏 PDF、CSV/JSON/Markdown 样本。
- [ ] **D1 契约：** 在当前 04 文档后补 `FileRef v1`、上传 MIME 白名单和 history 兼容测试。
- [x] **D2 解析器：** 已新增公共 `runtime_service/tools/documents.py`，实现 PDF/TXT/MD/JSON/CSV 最小解析器。
- [x] **D3 工具：** 已实现 `parse_document`，接入当前 thread workspace 和限制；解析缓存后置，避免首版过度设计。
- [ ] **D4 Middleware：** 注入 `available_files` 和能力说明，不自动解析全文。
- [x] **D5 Showcase：** 已装配 middleware/tool；真实 PDF 问答与 CSV 图表示例待全链路验收。
- [ ] **D6 平台适配：** 复用现有图片 PUT/GET 网关，补文件 MIME、下载和错误测试。
- [ ] **D7 验证：** 增加页码引用、越权、截断、并发、损坏文件、扫描 PDF 明确失败和浏览器 E2E。

门禁：先完成 D0 样本集和 D1 契约，再写 D2；没有真实扫描 PDF 和大文件样本，不批准引入 Docling/Unstructured/OCR 依赖。

## 11. 为什么不直接用“模型文件工具”

模型原生 file search、代码解释器或供应商文件 API 可以作为后置适配器，但不能替代 Runtime 公共解析工具：它们会引入供应商锁定、异步生命周期和不同的数据保留策略，也无法保证 `/workspace`、线程权限和审计契约一致。首版先做本地确定性解析，必要时再把 OCR/复杂版面作为显式 provider adapter。
