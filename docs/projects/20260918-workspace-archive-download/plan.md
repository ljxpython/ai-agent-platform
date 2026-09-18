# 工作区全量文件打包下载 - 整体方案

## 背景
当前工作区面板仅支持单个文件的点击预览和单文件下载。当智能体在一轮或多轮会话中生成了多个分析结果、图表、代码和文档时，用户需要手动逐个下载，操作极其繁琐。若仅在前端通过拉取目录树 + 逐个请求内容并打包，会产生大量 HTTP 请求风暴并在前端导致浏览器内存溢出（OOM）。

## 目标
1. `runtime-service` 提供基于本地物理工作区的流式 zip 打包端点。
2. `platform-api` 网关层提供安全鉴权透传。
3. `platform-web` 工作区工具栏提供一键打包下载操作入口。

## 方案设计

### 整体架构
```
[User Browser]
      ↓ 点击【打包下载】
[platform-web]
      ↓ GET /api/langgraph/threads/{id}/workspace/zip
[platform-api Gateway] (鉴权 project.runtime.read / workspace-file-read)
      ↓ GET /internal/threads/{id}/workspace/zip
[runtime-service] (zipfile 遍历物理目录打包，生成 application/zip 二进制流)
```

### 关键改动点

#### 1. runtime-service
- **文件：** `apps/runtime-service/src/runtime_service/workspace/browser.py`
- **改动：** 增加 `create_archive(self)`，递归遍历 `root`，打包相对路径文件，返回二进制数据与文件名元数据。
- **文件：** `apps/runtime-service/src/runtime_service/http/workspace.py`
- **改动：** 新增 `GET /internal/threads/{thread_id}/workspace/zip`，响应 `application/zip`。

#### 2. platform-api
- **文件：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- **改动：** 新增 `GET /threads/{thread_id}/workspace/zip`，透传 stream。
- **文件：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- **改动：** `thread_workspace` 映射 `workspace/zip` 资源。

#### 3. platform-web
- **文件：** `apps/platform-web/src/services/threads/workspace.service.ts`
- **改动：** 增加 `downloadWorkspaceZip(projectId, threadId)`。
- **文件：** `apps/platform-web/src/composables/useThreadWorkspace.ts`
- **改动：** 增加 `downloadingArchive` 与 `downloadAllFiles()`。
- **文件：** `apps/platform-web/src/components/workspace/WorkspacePanel.vue`
- **改动：** 增加按钮，绑定触发事件。

## 链路影响与契约
- **新增接口**：
  - `GET /internal/threads/{thread_id}/workspace/zip`
  - `GET /threads/{thread_id}/workspace/zip`
- **返回类型**：`application/zip`，头信息包含 `Content-Disposition: attachment; filename="workspace-*.zip"`。
