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
- 调用 `/_management/projects/{project_id}/testcase/cases/export`
- 支持按 `batch_id / status / query` 查询
- 左侧列表，右侧详情
- 支持导出当前筛选结果为 `.xlsx`

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

## 4.1 Excel 导出交互方案

导出入口：

- 放在 `用例管理` 页面

交互规则：

1. 默认导出“当前筛选结果”
2. 筛选条件与列表页保持一致：
   - `batch_id`
   - `status`
   - `query`
3. 前端不自己拼 Excel
4. 前端只调用 `platform-api` 下载 `.xlsx`
5. 当当前筛选结果为空时，导出按钮置灰

下载结果：

- 文件名由后端返回 `Content-Disposition` 控制
- 浏览器直接下载到本地
- 一期不提供“自定义列”或“导出 PDF 解析内容”

页面交互细节：

1. 页面加载完成后，先拉：
   - `overview`
   - `batches`
   - `cases`
2. 导出按钮位于筛选栏右侧
3. 以下场景按钮置灰：
   - 当前没有 `projectId`
   - 列表加载中
   - 正在导出中
   - 当前筛选结果总数为 `0`
4. 点击导出后：
   - 按当前 `batch_id / status / query` 组装请求
   - 调 `/_management/projects/{project_id}/testcase/cases/export`
   - 收到 blob 后触发浏览器下载
5. 导出成功：
   - toast 提示“导出成功”
   - 描述当前筛选命中的 testcase 总数
6. 导出失败：
   - toast 展示后端错误信息
   - 不改变当前筛选和列表态

前端模块拆分：

- 页面：`src/app/workspace/testcase/cases/page.tsx`
- API client：`src/lib/management-api/client.ts`
- testcase API：`src/lib/management-api/testcase.ts`

当前下载实现约束：

- 浏览器文件名优先使用响应头 `Content-Disposition`
- 若响应头缺失，则回退到前端时间戳文件名
- 前端不解析 Excel 内容，不参与字段拼装

### 4.2 一期验收口径

前端侧这轮以“真实后端接口 + 编译通过”为主：

1. `pnpm exec tsc --noEmit` 通过
2. `platform-api` 真实导出接口返回 `200`
3. 下载文件可被 `openpyxl` 打开
4. 文件名、sheet 名称、数据行数符合预期

暂不增加：

- 专属前端自动化下载测试
- 自定义导出列
- PDF 解析记录导出

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
