# 支持 `/workspace/outputs/` 下可读文件名的成果识别与预览下载

**日期：** 2026-09-23

## 背景
在本地工作区执行模式（`RUNTIME_BACKEND=local`）或特定 Agent 执行流程中，Agent 可能直接将生成的文档/代码/图表以人类可读文件名（如 `01-header-and-strategy.md`、`ecommerce-order-payment-architecture.md`）写入或复制到 `/workspace/outputs/` 目录，而非仅通过 `present_artifacts` 生成 64 位 SHA256 哈希命名的文件。此前 `WorkspaceBrowser.list_directory(..., artifacts_only=True)` 与 `ArtifactWorkspace.read()` 硬编码了 `r"[0-9a-f]{64}\.[a-z0-9]+"` 正则校验，导致普通可读文件名的产出物在 `dear-agent-artifacts` 页面被过滤为空（`items: []`）。

## 改动内容
1. **`WorkspaceBrowser` 成果识别扩展**：在 `list_directory` 与 `read_file` 中，将 `/workspace/outputs/` 下所有非隐藏（不以 `.` 开头，排除 `.publish-*` 临时文件）、具备合法文件名前缀且扩展名在 `ARTIFACT_MIMES` 白名单内的常规文件识别为正式成果。
2. **`ArtifactWorkspace` 读取与哈希计算兼容**：
   - `list_artifacts`：若文件名为 64 位小写十六进制哈希，直接复用文件名 stem；若为普通可读文件名，动态读取文件字节计算真实 64 位 SHA256 摘要填充 `sha256` 与 `artifact_id`，并保留可读的原始 `file_name`。
   - `read`：对 64 位哈希命名的文件继续执行严格的 `digest != expected_hash` 防篡改校验（返回 409 `artifact_hash_mismatch`）；对普通可读文件名校验大小与格式后返回真实 SHA256 与可读文件名。
3. **单元测试补充**：在 `tests/test_workspace_browser.py` 中新增 `test_readable_filename_artifacts_in_outputs`，验证列表、读取、预览与隐藏临时文件过滤。

## 涉及文件
- `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py`
- `apps/runtime-service/src/runtime_service/workspace/browser.py`
- `apps/runtime-service/tests/test_workspace_browser.py`
