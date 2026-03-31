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
- 调用 `/_management/projects/{project_id}/testcase/role`
- 调用 `POST / PATCH / DELETE /cases`
- 支持按 `batch_id / status / query` 查询
- 左侧列表，右侧详情
- 支持新增、编辑、删除 testcase
- 支持按当前筛选结果导出 `.xlsx`
- 支持自定义导出列
- 根据 `role.can_write_testcase` 控制写权限态
- 右侧编辑区拆成：
  - 基础信息
  - 用例正文
  - 扩展信息
  - 来源文档
- `steps / expected_results` 保存前至少要求 1 条
- `test_data` 提供实时 JSON object 校验
- 表单切换时支持未保存离开确认
- 来源文档支持按文件名 / 解析状态 / document id 搜索，并显示已选数量
- 编辑态保留 `quality_review / bundle_title / bundle_summary / created_at / updated_at` 只读展示

### 2.3 PDF 解析

页面：

- `src/app/workspace/testcase/documents/page.tsx`

当前行为：

- 调用 `/_management/projects/{project_id}/testcase/overview`
- 调用 `/_management/projects/{project_id}/testcase/batches`
- 调用 `/_management/projects/{project_id}/testcase/documents`
- 调用 `/_management/projects/{project_id}/testcase/documents/export`
- 调用 `/_management/projects/{project_id}/testcase/documents/{document_id}/relations`
- 调用 `/_management/projects/{project_id}/testcase/documents/{document_id}/preview`
- 调用 `/_management/projects/{project_id}/testcase/documents/{document_id}/download`
- 支持按 `batch_id / parse_status / query` 查询
- 支持导出当前筛选结果为 `.xlsx`
- 详情区展示 `summary_for_model / parsed_text / structured_data / provenance / error`
- 详情区展示 `thread_id / run_id / agent_key / related_cases`
- 详情区展示 `Batch Context`
- 支持 `查看同批次全部用例 / 查看同批次全部文档 / 复制 batch_id`
- 支持查看同批次其他文档，并在右侧直接切换详情
- 支持复制 `document_id`
- 若存在 `storage_path`，支持在线预览与下载原始 PDF

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

## 3.1 当前项目上下文现状

当前 `projectId` 不是 testcase 工作区自己维护的，它来自全局 `WorkspaceContext`：

- `src/providers/WorkspaceContext.tsx`

真实来源顺序：

1. 当前 URL query 中的 `projectId`
2. 如果 URL 中没有，则在加载项目列表后自动回退到第一条项目

当前实现约束：

- testcase 页面虽然依赖 `projectId`，但不自己维护项目状态
- 全局项目切换入口集中放在 `Projects` 页面
- 工作区头部只负责展示当前项目，不承担切换操作
- 因此 testcase 用户需要在 `Projects` 页面切换项目，再回到 testcase 工作区继续操作

当前已知实例：

- 本轮联调使用的项目为：`5f419550-a3c7-49c6-9450-09154fd1bf7d`

后续约束：

- testcase 工作区开发不能继续假设“用户天然知道当前项目”
- testcase 页面内部只消费 `WorkspaceContext.projectId`，不自行发明新的项目状态
- 如果需要切换项目，统一回到 `Projects` 页面操作

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
6. 当前支持 `导出配置`，可切换标准列 / 完整列，并按白名单勾选列

下载结果：

- 文件名由后端返回 `Content-Disposition` 控制
- 浏览器直接下载到本地
- 当前已支持 testcase 自定义导出列与 PDF 解析记录导出

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

### 4.2 当前验收口径

前端侧这轮以“真实后端接口 + 编译通过”为主：

1. `pnpm exec tsc --noEmit` 通过
2. `platform-api` 真实导出接口返回 `200`
3. 下载文件可被 `openpyxl` 打开
4. 文件名、sheet 名称、数据行数符合预期

暂不增加：

- 专属前端自动化下载测试

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

## 6. 二期实施方案

### 6.0 工作区项目选择补齐

这是 testcase 工作区继续增强前的前置体验改造。

目标：

- 让用户在任何工作区页面都能明确看到“当前项目”
- 让用户有一个稳定、唯一的项目切换入口，而不是继续依赖 URL query

设计方案：

1. 在 `Projects` 页面顶部增加一个 `全局项目上下文` 卡片
2. 卡片内部提供：
   - 当前项目信息展示
   - 项目模糊搜索输入框
   - 项目下拉选择框
   - `切换项目` 按钮
3. 切换行为：
   - 调用 `WorkspaceContext.setProjectId(...)`
   - 自动清理 `threadId / assistantId`
   - 保持当前页面路由不变，只更新 query 中的 `projectId`
4. 在 `WorkspaceShell` 头部增加只读项目摘要：
   - 放在 `Workspace scope: project` 下方
   - 只展示当前项目名称
5. testcase 工作区页面继续只消费 `WorkspaceContext.projectId`，不新增局部项目状态

约束：

- 不新建第二套项目状态
- 不在 testcase 页面重复做项目下拉
- 不在 `WorkspaceShell` 头部放可编辑下拉
- 项目切换入口只保留在 `Projects` 页面

### 6.1 用例管理 CRUD

目标：

- 在不新增复杂页面层级的前提下，把 `用例管理` 补成可新增、可编辑、可删除的管理页
- 保持当前“左侧列表 + 右侧详情”的交互结构
- 在现有 CRUD 已可用的基础上，把表单交互压实到“可稳定录入和修订”

页面形态：

- `detail`：只读详情
- `create`：新增用例表单
- `edit`：编辑当前用例表单

页面动作：

- 顶部增加 `新增用例`
- 详情区增加 `编辑`
- 详情区增加 `删除`

本轮后续要继续细化的点：

- 右侧表单拆成 4 个稳定区块：
  - 基础信息
  - 用例正文
  - 扩展信息
  - 来源文档
- `steps / expected_results` 至少一条
- `test_data` 做实时 JSON 校验，而不是只在保存时报错
- 表单切换时增加未保存离开确认
- 来源文档选择区支持按文件名搜索和已选数量提示
- 来源文档展示不只给 UUID，要显示：
  - `filename`
  - `parse_status`
  - `batch_id`
  - `created_at`

表单字段分组：

1. 基础字段
   - `batch_id`
   - `case_id`
   - `title`
   - `status`
   - `module_name`
   - `priority`
   - `description`
2. 结构化字段
   - `preconditions`
   - `steps`
   - `expected_results`
   - `test_type`
   - `design_technique`
   - `test_data`
   - `remarks`
3. 关联字段
   - `source_document_ids`

表单实现约束：

- `preconditions / steps / expected_results` 使用多行文本，一行一项
- `test_data` 使用 JSON 文本框，提交前做 JSON 校验
- `source_document_ids` 从当前项目 document 列表中选择
- `batch_id` 新建时默认继承当前筛选的 `batchFilter`
- `quality_review / bundle_title / bundle_summary / created_at / updated_at` 先保持只读展示，不进入可编辑表单

联动规则：

1. 创建成功后：
   - 刷新 `overview / batches / cases`
   - 自动选中新创建记录
   - 右侧切回 `detail`
2. 编辑成功后：
   - 刷新当前详情和列表
   - 若记录因筛选条件变化不再命中，toast 提示后回到列表首项
3. 删除成功后：
   - 刷新 `overview / batches / cases`
   - 当前记录被删后自动切到下一条；若无数据则进入空态

权限态：

- `admin / editor` 可新增、编辑、删除
- `executor` 只读
- 前端不靠盲点按钮后再吃 `403`
- `WorkspaceContext` 二期需要补充 `projectRole`

错误态：

- `400`：字段校验错误，显示表单级或字段级提示
- `403`：toast 提示无权限，并刷新权限态
- `404`：提示记录不存在，刷新列表
- 删除必须二次确认，确认框展示 `title / case_id / batch_id`

交互实现建议：

1. 保持当前 `detail / create / edit` 三态，不再引入 drawer/modal 套层
2. 表单内部用本地 `dirty state` 判断是否需要离开确认
3. 校验失败优先就地提示，少用全局 toast 打断
4. 保存成功后继续停留在当前记录，不打断筛选态

### 6.2 PDF 管理二期增强

二期拆成两个阶段，避免把“解析记录增强”和“原始文件资产存储”混成一坨。

#### 6.2.1 阶段 A：解析记录增强

目标：

- 把当前 `/workspace/testcase/documents` 提升为可排查、可追溯的页面

页面增强点：

- 列表增加：
  - `filename`
  - `parse_status`
  - `batch_id`
  - `created_at`
- 详情增加：
  - `thread_id`
  - `run_id`
  - `agent_key`
  - `related_cases`
  - `related_cases_count`

数据来源约定：

- 运行态元信息优先从 `provenance.runtime` 读取
- `related_cases` 由管理接口按 `source_document_ids` 反查

页面动作：

- 增加 `导出 PDF 解析`
- 增加 `复制文档 ID`
- 若存在原始资产，再显示 `在线预览 PDF / 下载原始 PDF`

当前下一步要补的增强点：

- 从“单 document 详情”提升到“带批次上下文的 document 详情”
- 让用户能从一份 PDF 快速回看整个 batch 的输入和产出

#### 6.2.2 阶段 B：原始文件回看与下载

目标：

- 页面不只展示解析结果，还能回看真实上传的 PDF

设计约束：

- 不把 PDF 二进制塞进数据库字段
- 不把 base64 原文塞进 `documents` JSON
- 原始文件走资产存储
- 解析结果继续走 `documents` 记录

前端交互：

- 若 document 存在可用资产：
  - 显示 `在线预览 PDF`
  - 显示 `下载原始 PDF`
- 若 `storage_path` 为空：
  - 按钮置灰
  - 显示“该记录未保存原始文件，仅保留了解析结果”

#### 6.2.3 阶段 C：批次关联展示增强

目标：

- 让 `PDF 解析` 页面具备“围绕 batch 排查”的能力，而不是只看单条 document

页面结构建议：

1. 详情区顶部增加 `Batch Context`
2. 展示：
   - `batch_id`
   - 当前 batch 的 `documents_count`
   - 当前 batch 的 `test_cases_count`
   - 当前 batch 的 `latest_created_at`
   - 当前 batch 的 `parse_status_summary`
3. 详情区增加两个关联区域：
   - `本文档关联用例`
   - `同批次其他文档`

交互规则：

1. 点击“同批次其他文档”中的任一项，右侧直接切换详情
2. 提供：
   - `查看同批次全部用例`
   - `查看同批次全部文档`
   - `复制 batch_id`
3. 如果当前 document 没有 `batch_id`，则退回单 document 详情模式

数据来源：

- `overview`
- `batches`
- 当前 `document.batch_id`
- 当前 `relations`
- 当前列表已加载的同批次 `documents`

实现约束：

- 先基于已有接口拼出批次上下文，不急着新增后端聚合接口
- 如果后续发现页面侧拼装成本过高，再补 `batch detail` 专属接口
- 当前不做复杂关系图和跨 batch 时间线

### 6.3 Excel 导出二期

#### 6.3.1 用例导出增强

目标：

- 在保持后端统一生成 workbook 的前提下，支持前端选择导出列

前端交互：

- `用例管理` 页导出按钮旁增加 `导出配置`
- 弹层中提供：
  - 固定列白名单复选框
  - `标准列`
  - `完整列`
- 前端将选择结果作为 `columns` 传给后端
- 不在浏览器内拼装 Excel

一期默认列行为保持不变：

- 若不传 `columns`，继续使用稳定默认列

#### 6.3.2 PDF 解析记录导出

目标：

- 支持从 `PDF 解析` 页面导出当前筛选结果

前端交互规则：

1. 导出当前筛选结果
2. 条件与列表页保持一致：
   - `batch_id`
   - `parse_status`
   - `query`
3. 当前筛选结果为空时按钮置灰
4. 成功后 toast 提示导出条数

#### 6.3.3 大结果集导出

约束：

- 前端不感知后端分页细节
- 超大结果集先由后端同步分页拉取
- 若超过系统上限，前端直接展示后端错误信息

当前不做：

- 前端异步导出任务页
- 专属前端自动化下载测试

## 7. 二期真实验证口径

禁止 mock。

验证必须基于：

1. 真实登录态
2. 真实项目
3. 真实 testcase 数据
4. 真实 PDF 上传记录
5. 真实 `platform-api -> interaction-data-service` 链路

至少验证：

1. 新增一条 testcase，列表、详情、overview、batches 同步变化
2. 编辑一条 testcase，结构化字段和详情展示同步变化
3. 删除一条 testcase，二次确认与联动刷新正常
4. PDF 详情可看到 `batch_id / thread_id / run_id / related_cases`
5. 导出 testcase Excel 能按当前列配置和筛选条件正确下载
6. 导出 PDF 解析记录时条数、sheet、字段符合预期
7. 若已保存原始 PDF，页面预览和下载可用
8. 全局切换 `projectId` 后，testcase 三个二级页面都能跟随刷新且无脏状态残留
9. PDF 页面可从当前 document 跳转查看同批次其他 document 和同批次用例
