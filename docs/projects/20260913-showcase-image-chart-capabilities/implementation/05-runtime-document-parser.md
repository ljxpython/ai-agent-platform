# Runtime 公共文档解析工具

## 改动时间

2026-09-13

## 相关任务

- 09-document-parsing-design.md：D2 解析器、D3 工具、D5 Showcase 装配

## 改动文件

- `apps/runtime-service/src/runtime_service/tools/documents.py`
- `apps/runtime-service/src/runtime_service/middlewares/documents.py`
- `apps/runtime-service/src/runtime_service/middlewares/__init__.py`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`
- `apps/runtime-service/tests/services/showcase_demo/test_documents.py`
- `apps/runtime-service/src/runtime_service/workspace/file_refs.py`
- `apps/runtime-service/src/runtime_service/workspace/documents.py`
- `apps/runtime-service/src/runtime_service/http/documents.py`

## 具体改动

### 1. 公共解析器与工具

新增 `build_document_tools()` 和 `parse_document`。工具只接受当前线程 `/workspace/uploads/` 下的文件，支持 PDF、TXT、Markdown、JSON、CSV；PDF 使用已安装的 PyMuPDF 逐页提取文本，结果保留完整 `FileRef v1`（包括 sha256）、页码、匹配页、截断状态和有限 chunks。上传和读取统一复用 descriptor/O_NOFOLLOW workspace 访问。

实现了 20 MiB 文件上限、20 页单次上限、12,000 字符输出上限、UTF-8 校验、路径越界校验和不支持格式拒绝；PDF 上传/解析检查 `%PDF-` magic bytes、损坏/加密/空文档和无文本层 warning。没有引入 OCR、向量库、后台任务或供应商文件 API。

### 2. Middleware 与 Showcase 装配

新增 `DocumentToolsMiddleware`，复用现有 Runtime middleware/tool 装配方式。Showcase composition root 为运行实例创建线程 workspace、注册工具名并纳入 Runtime 内部工具授权；schema-only 图只暴露工具 schema，不访问文件。

## 验证

- [x] PDF 页码和 query 过滤测试：1 passed
- [x] Markdown 读取与路径逃逸测试：1 passed
- [x] FileRef sha256、PDF magic bytes 和损坏文件校验已接入
- [x] Runtime 文件 PUT/GET 授权接口已接入
- [ ] 全量 Showcase 回归：待执行
- [ ] Platform 文件上传适配：不在本次 Runtime 实现范围
- [ ] OCR/复杂版面：后置规划

## 注意事项

Platform API 仍需代理 Runtime 文件 PUT/GET；Runtime 接口本身不应直接暴露给浏览器。OCR、复杂版面和解析缓存明确后置。
