# 扩展 artifact 发布格式

历史阶段记录：以下“尚未完成”描述首次局部修复时的状态，现已由 [02 后端实现记录](02-workspace-backend.md) 补齐；最新证据见 [验证记录](../verification.md)。

## 改动时间

2026-09-17

## 相关问题

`present_artifacts({"file_path": "/workspace/work/payment_openapi.yaml"})` 返回 `unsupported_artifact_type`。

## 改动文件

- `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py`
- `apps/runtime-service/src/runtime_service/workspace/file_refs.py`
- `apps/runtime-service/src/runtime_service/workspace/media.py`
- `apps/runtime-service/src/runtime_service/http/documents.py`
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/artifacts.py`
- `apps/runtime-service/tests/services/dearflow_agent/test_files.py`

## 具体改动

- 发布/读取共用动态白名单，避免两处正则支持范围不一致。
- 增加 YAML/YML、TOML、XML、Python、Shell、SQL、TypeScript、Java、C/C++、Rust。
- 增加 PNG/JPG/WebP artifact 校验，复用现有 Pillow 图片校验；`.jpeg` 后缀和图片实际类型匹配仍待补齐。
- ZIP/PPTX 沿用已有结构校验；PDF/XLSX/XLS 有现存文档校验能力，但尚未加入 artifact 发布白名单。未知二进制仍拒绝发布。
- `present_artifacts` 工具描述改为按能力描述，不再列过时的固定扩展名。

## 验证

- `uv run --frozen pytest tests/services/dearflow_agent/test_files.py -q`：3 passed
- Ruff 定向检查通过。

## 尚未完成

这是部分 Runtime 修复记录，不代表跨服务完成：Platform API 下载 MIME 白名单、capabilities 声明、图片后缀一致性、上传与发布校验分派仍待修复。文件级后续工作见 [04](../04-code-change-map.md)。
