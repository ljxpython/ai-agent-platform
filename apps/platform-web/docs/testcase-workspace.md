# Testcase 工作区

这份文档描述 `apps/platform-web` 当前已经落地的 Testcase 工作区能力。

## 1. 入口与路由

一级导航：

- `Testcase`

二级页面：

- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`

默认跳转：

- `/workspace/testcase` -> `/workspace/testcase/generate`

## 2. 当前页面职责

### 2.1 AI 对话生成

页面：

- `src/app/workspace/testcase/generate/page.tsx`

当前行为：

- 复用 `BaseChatTemplate`
- 固定目标到 `graph = test_case_agent`
- 沿用聊天页的文件上传能力，支持真实上传 PDF
- 左侧上下文卡片同时展示：
  - 当前来源信息
  - 当前项目
  - 固定目标 graph
  - 持久化范围

### 2.2 用例管理

页面：

- `src/app/workspace/testcase/cases/page.tsx`

当前行为：

- 调用 `/_management/projects/{project_id}/testcase/overview`
- 调用 `/_management/projects/{project_id}/testcase/batches`
- 调用 `/_management/projects/{project_id}/testcase/cases`
- 支持按 `batch_id / status / query` 查询
- 左侧列表，右侧详情

### 2.3 PDF 解析

页面：

- `src/app/workspace/testcase/documents/page.tsx`

当前行为：

- 调用 `/_management/projects/{project_id}/testcase/overview`
- 调用 `/_management/projects/{project_id}/testcase/batches`
- 调用 `/_management/projects/{project_id}/testcase/documents`
- 支持按 `batch_id / parse_status / query` 查询
- 详情区展示 `summary_for_model / parsed_text / structured_data / provenance / error`

## 3. 当前集成边界

请求链路：

```text
platform-web testcase pages
  -> platform-api /_management/projects/{project_id}/testcase/*
    -> interaction-data-service /api/test-case-service/*
```

前端约束：

- `projectId` 由 `WorkspaceContext` 驱动
- 管理页不直连 `interaction-data-service`
- 页面登录态依赖本地浏览器 token

## 4. 当前已知事实

- `PDF 解析` 页面展示的是已经持久化的文档记录，不是上传后即时预览库
- 如果记录的 `parse_status=unprocessed`，详情页可能没有 `parsed_text`
- 页面是否有数据，取决于当前 `projectId` 下是否已有 `test_cases / test_case_documents`

## 5. 本地验证

```bash
pnpm exec tsc --noEmit
pnpm exec eslint "src/components/platform/workspace-shell.tsx" \
  "src/components/thread/index.tsx" \
  "src/components/platform/testcase-chat-header.tsx" \
  "src/app/workspace/testcase/generate/page.tsx" \
  "src/app/workspace/testcase/cases/page.tsx" \
  "src/app/workspace/testcase/documents/page.tsx" \
  "src/lib/management-api/testcase.ts"
```
