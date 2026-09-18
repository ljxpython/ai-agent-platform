# 工作区全量文件打包下载（方案B）实施记录

## 1. 概述
在工作区（WorkspacePanel）实现一键打包下载全部文件（Zip 归档），避免前端递归扫描遍历的高延迟与大文件浏览器端内存溢出风险。

## 2. 涉及改动

### 2.1 runtime-service
- **文件**：`apps/runtime-service/src/runtime_service/workspace/browser.py`
  - 新增 `create_archive(self) -> tuple[bytes, str]`：利用 Python 内置 `zipfile.ZipFile` 将工作区物理目录递归打包，排除系统隐藏目录（`.git`, `__pycache__`, `.DS_Store`），针对软链接进行 `resolve().is_relative_to(root)` 防御检测，杜绝越权逃逸。
- **文件**：`apps/runtime-service/src/runtime_service/http/workspace.py`
  - 新增端点 `GET /internal/threads/{thread_id}/workspace/zip`，需要 `workspace-file-read` 权限，以 `application/zip` 流式返回，并在 `Content-Disposition` 设置规范文件名 `workspace-{thread_id[:8]}-{timestamp}.zip`。
- **测试**：`apps/runtime-service/tests/test_workspace_zip.py`
  - 覆盖空目录、嵌套文件、隐藏过滤、软链接安全与 HTTP 端点测试，3 项测试全部通过。

### 2.2 platform-api
- **文件**：`apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py`
  - `BinaryPayload` 新增 `content_disposition` 字段。
  - `RuntimeGatewayUpstreamProtocol` 增加 `workspace_zip` 抽象接口。
- **文件**：`apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py`
  - 在 `read_file` 响应中读取 upstream 的 `content-disposition` 并注入 `BinaryPayload`。
- **文件**：`apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`
  - 实现 `workspace_zip(thread_id)`，对接 `/internal/threads/{thread_id}/workspace/zip`。
- **文件**：`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
  - `thread_workspace` 支持 `resource="workspace/zip"`，校验后透传调用 upstream。
- **文件**：`apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
  - 暴露对外端点 `GET /threads/{thread_id}/workspace/zip`，返回 `RuntimeStreamingResponse`。
- **测试**：
  - `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`：矩阵鉴权与请求透传通过。
  - `apps/platform-api/tests/test_runtime_gateway_workspace.py`：包含真实双服务 loopback 联调，解压 zip 文件校验通过。

### 2.3 platform-web
- **文件**：`apps/platform-web/src/services/threads/workspace.service.ts`
  - 新增 `downloadWorkspaceZip(projectId, threadId)`，请求网关端点获取 blob，解析 `content-disposition` 并调用 `triggerBlobDownload`。
- **文件**：`apps/platform-web/src/composables/useThreadWorkspace.ts`
  - 导出 `downloadingArchive` 与 `downloadAllFiles()`，管理下载中状态。
- **文件**：`apps/platform-web/src/components/workspace/WorkspacePanel.vue`
  - 在顶部操作栏刷新按钮左侧增加【打包下载全部文件】图标按钮，支持 loading 动画、禁用防抖与失败 toast 提示。
- **测试与类型检查**：
  - `workspace.service.spec.ts` 补充单元测试，通过（6/6）。
  - `vue-tsc --noEmit` 严格检查 0 报错。
  - 全量 70 个前端测试套件全部通过（232/232）。
