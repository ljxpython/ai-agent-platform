# Testcase 平台工作区一期设计

## 1. 目标

围绕 `runtime_service/services/test_case_service` 建一套最小但完整的 Testcase 工作区：

```text
platform-web Testcase 工作区
  -> platform-api testcase 管理接口
    -> interaction-data-service testcase 专属接口
      -> test_case_documents / test_cases

platform-web AI 对话生成页
  -> 固定 graph = test_case_agent
  -> runtime-service/test_case_service
```

一期目标：

1. 新增 `Testcase` 一级工作区入口
2. 一级导航支持下拉展开二级入口
3. 提供三个二级页面：
   - `AI 对话生成`
   - `用例管理`
   - `PDF 解析`
4. 后端提供 testcase 专属管理接口
5. 一期页面以读取为主，但后端 contract 一次性固定 CRUD 边界

## 2. 当前事实

### 2.1 runtime-service 当前能力

`test_case_service` 当前已经具备：

1. PDF / 图片等附件解析能力
2. 解析结果注入主 agent prompt 的能力
3. 最终调用 `persist_test_case_results` 时，把：
   - 附件解析结果写入 `test_case_documents`
   - 正式测试用例写入 `test_cases`

当前不是“上传即落库”，而是“最终正式保存时一起落库”。

### 2.2 interaction-data-service 当前能力

当前真实业务前缀为：

- `/api/test-case-service`

当前真实资源为：

- `documents`
- `test-cases`

这符合“每个 runtime 服务一个专属接口前缀”的范式。

### 2.3 platform-web 当前能力

当前工作区形态是：

1. 顶部一级横向导航
2. 部分模块页内自带二级导航

当前没有“一级导航项下拉展开二级入口”的现成实现，需要在 `workspace-shell.tsx` 中新增轻量实现。

## 3. 一期信息架构

### 3.1 一级工作区入口

新增一级入口：

- `Testcase`

### 3.2 二级入口

`Testcase` 一级导航下拉展示三个入口：

- `AI 对话生成`
- `用例管理`
- `PDF 解析`

默认路由：

- `/workspace/testcase` -> `/workspace/testcase/generate`

### 3.3 页面职责

#### 1. `AI 对话生成`

路径：

- `/workspace/testcase/generate`

职责：

1. 直接复用现有聊天模板
2. 固定目标到 `graph = test_case_agent`
3. 允许真实上传 PDF
4. 左侧上下文卡片展示 testcase 业务信息：
   - 当前项目
   - 当前 graph
   - 持久化范围

#### 2. `用例管理`

路径：

- `/workspace/testcase/cases`

职责：

1. 列表查看正式测试用例
2. 支持按 `batch_id / status / keyword` 查询
3. 支持查看详情
4. 一期前端以读为主，但后端先固定创建/更新/删除 contract

#### 3. `PDF 解析`

路径：

- `/workspace/testcase/documents`

职责：

1. 列表查看已保存的文档解析结果
2. 支持按 `batch_id / parse_status / filename` 查询
3. 查看详情时展示：
   - `summary_for_model`
   - `parsed_text`
   - `structured_data`
   - `provenance`

一期定义为：

- 展示已经完成正式保存的 testcase 批次中的 PDF 解析结果

不是：

- 上传后立即自动可见

## 4. 后端设计

## 4.1 interaction-data-service 侧

继续坚持“服务专属接口前缀”范式：

- `/api/test-case-service`

在保留现有原子资源接口基础上，新增两类聚合读接口：

- `GET /api/test-case-service/overview`
- `GET /api/test-case-service/batches`

用途：

### `overview`

返回当前项目下 testcase 数据总览，至少包括：

- `documents_total`
- `test_cases_total`
- `parsed_documents_total`
- `failed_documents_total`
- `latest_batch_id`
- `latest_activity_at`

### `batches`

返回批次维度聚合结果，至少包括：

- `batch_id`
- `documents_count`
- `test_cases_count`
- `latest_created_at`
- `parse_status_summary`

这样 `platform-api` 不需要自己扫全量数据做批次聚合。

## 4.2 platform-api 侧

新增 testcase 专属管理接口前缀：

- `/_management/projects/{project_id}/testcase`

一期接口建议固定如下：

- `GET /overview`
- `GET /batches`
- `GET /cases`
- `GET /cases/{case_id}`
- `POST /cases`
- `PATCH /cases/{case_id}`
- `DELETE /cases/{case_id}`
- `GET /documents`
- `GET /documents/{document_id}`

设计原则：

1. `platform-web` 不直连 `interaction-data-service`
2. `platform-api` 负责做 project 级权限校验
3. `platform-api` 负责透传 `project_id`
4. `platform-api` 只做轻聚合与协议整形，不复制业务数据所有权

权限建议：

- 读接口：`admin/editor/executor`
- 写接口：`admin/editor`

## 4.3 platform-api 本地 HTTP client

应抽一层本地共享 HTTP client，供后续其他业务模块复用。

抽象边界：

1. 只负责：
   - base_url
   - token
   - timeout
   - headers
   - JSON request/response
2. 不理解 testcase 业务字段
3. 由各业务模块自己组织 path 和 payload

这层共享 client 后续可继续服务其他结果域或聚合域模块。

## 5. 前端设计

## 5.1 一级导航下拉

在 `WorkspaceShell` 中把一级导航从“纯 Link 数组”升级为“Link + 可选 children”结构。

其中：

- 普通一级项仍然直接跳转
- `Testcase` 一级项支持展开下拉菜单
- 下拉项直接进入对应二级页面

实现原则：

1. 用轻量自研实现，不引入重型导航系统
2. 保持桌面端可用，移动端可退化为简单列表
3. 当前只先服务 `Testcase`，不做全站导航系统重构

## 5.2 AI 对话生成页

直接复用：

- `BaseChatTemplate`

固定参数：

- `targetType = graph`
- `graphId = test_case_agent`

页面当前实现为：

1. 基础上下文卡片继续展示 graph / assistant / thread 来源信息
2. testcase 业务信息并入同一张左侧上下文卡片
3. 不再单独占用顶部 header 区域

## 5.3 用例管理页

一期页面能力：

1. 顶部总览卡片
2. 批次筛选
3. 用例列表表格
4. 详情查看区

展示重点：

- `title`
- `module_name`
- `priority`
- `status`
- `batch_id`
- `source_document_ids`
- `updated_at`

## 5.4 PDF 解析页

一期页面能力：

1. 顶部总览卡片
2. 批次筛选
3. 文档列表
4. 详情展示：
   - 文件名
   - 解析状态
   - 文档摘要
   - 全量 `parsed_text`
   - `structured_data`

## 6. 一期数据契约建议

### 6.1 overview

```json
{
  "project_id": "uuid",
  "documents_total": 12,
  "parsed_documents_total": 11,
  "failed_documents_total": 1,
  "test_cases_total": 35,
  "latest_batch_id": "test-case-service:xxx",
  "latest_activity_at": "2026-03-30T08:00:00Z"
}
```

### 6.2 batches

```json
{
  "items": [
    {
      "batch_id": "test-case-service:xxx",
      "documents_count": 1,
      "test_cases_count": 4,
      "latest_created_at": "2026-03-30T08:00:00Z",
      "parse_status_summary": {
        "parsed": 1,
        "failed": 0
      }
    }
  ],
  "total": 1
}
```

## 7. 二期演进：上传后立即保存 PDF 解析结果

## 7.1 当前问题

当前 PDF 文档解析结果的落库时机依赖 `persist_test_case_results`。

这意味着：

1. 用户在聊天里上传 PDF 后，解析虽然发生了
2. 但如果最终没有走正式保存，文档不会写入 `interaction-data-service`
3. `PDF 解析` 页面一期只能看到“已正式保存批次”的结果

## 7.2 二期目标

调整为：

```text
用户上传 PDF
  -> MultimodalMiddleware 完成解析
  -> 在解析结果准备传给主 agent 时立即持久化 document
  -> 主 agent 继续消费解析结果
  -> 后续正式保存 testcase 时，只补充 test_cases 落库与 source_document_ids 关联
```

## 7.3 二期实现方向

建议不要把“文档即时落库”交给模型自主决定，而要做成服务内确定性逻辑。

推荐做法：

1. 在 `test_case_service` 内新增一个“文档即时持久化”服务层能力
2. 触发点位于多模态解析完成、主模型调用前
3. 为每个已解析附件生成稳定幂等键
4. 先写入 `test_case_documents`
5. 将返回的 `document_id` 回填到运行态 state
6. 后续 `persist_test_case_results` 只负责：
   - 避免重复写 document
   - 写正式 `test_cases`
   - 关联 `source_document_ids`

## 7.4 二期关键设计点

### 1. 幂等

必须基于附件 fingerprint 或稳定内容摘要做幂等，否则同一次会话反复重试会重复插入文档。

### 2. 运行态回填

建议在附件 artifact 或 runtime state 中补充：

- `persisted_document_id`
- `persist_status`
- `persisted_at`

### 3. 错误处理

文档即时落库失败时：

- 不应直接阻断主 agent 对话
- 但要在 state 中记录失败原因
- 同时允许后续正式保存阶段重试

### 4. 落库职责拆分

二期后职责应拆成：

- 文档解析阶段：保存 document
- 正式结果输出阶段：保存 test_cases 并建立引用

这样系统行为更稳定，也更符合“上传文档解析结果页实时可见”的产品预期。

## 8. 验证要求

一期验证必须基于真实链路，不做 mock：

1. 启动 `runtime-service`
2. 启动 `interaction-data-service`
3. 启动 `platform-api`
4. 启动 `platform-web`
5. 在前端 `AI 对话生成` 页面上传真实 PDF：
   - `apps/runtime-service/runtime_service/test_data/接口文档.pdf`
6. 验证：
   - 对话不报错
   - 用例生成正常
   - 正式保存后 `用例管理` 能看到数据
   - `PDF 解析` 页面能看到对应批次文档解析结果

## 9. 一期落地顺序

1. 先写本文档，冻结一期范围
2. 补 `interaction-data-service` 的 `overview / batches`
3. 补 `platform-api` 的 testcase 管理接口与共享 HTTP client
4. 实现 `platform-web` 的 `Testcase` 一级下拉导航
5. 实现三个页面：
   - `AI 对话生成`
   - `用例管理`
   - `PDF 解析`
6. 用真实前端上传 `接口文档.pdf` 完成联调验证
