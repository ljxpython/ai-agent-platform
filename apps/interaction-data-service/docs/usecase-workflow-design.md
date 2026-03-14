# 用例生成工作流设计稿

本文定义一个真实业务案例：

> 用户上传需求文档，系统通过多智能体协作生成候选用例，按规范评审，支持人工查看与反复修改，最终在人工确认后落库，并在平台提供正式 CRUD 管理页面。

这份文档不是补充聊天体验，而是在 `interaction-data-service` 的总设计上，给出第一条可落地的业务工作流。

## 1. 业务目标

目标不是“一次对话生成用例”，而是建立一条受控工作流：

1. 上传需求文档
2. 需求分析
3. 生成候选用例
4. 用例评审
5. 人工查看与提出修改意见
6. 多轮修订
7. 人工确认
8. 正式落库
9. 在平台 CRUD 管理

核心原则：

- 草稿与正式数据分离
- 评审结果结构化保存
- 只有人工确认后才允许落库
- 聊天页负责协作，CRUD 页负责管理正式数据

## 2. 系统边界

### 2.1 `runtime-service`

负责：

- deepagent 工作流编排
- 文档理解、需求分析、用例生成、用例评审
- 调用本地 LangGraph tools 访问 `interaction-data-service`

不负责：

- 平台鉴权
- 最终业务数据主权
- 前端页面状态管理

### 2.2 `interaction-data-service`

负责：

- 工作流记录、快照、评审报告存储
- 正式用例数据存储
- 统一 HTTP 契约
- `record_type` / `workflow_type` 路由和 schema 校验

不负责：

- 用户鉴权与项目权限判定
- 智能体执行

### 2.3 `platform-api`

负责：

- 当前用户、项目上下文、权限控制
- 对 `runtime-service` 和 `interaction-data-service` 做平台级聚合
- 向 `platform-web` 暴露统一管理接口

### 2.4 `platform-web`

负责：

- 用例生成工作台
- 正式用例 CRUD 页面
- 用户确认、重跑、落库入口

## 3. 目标产品形态

推荐拆成两个页面面：

### 3.1 用例生成工作台

建议路由：

- `/workspace/usecase-agent`

页面职责：

- 上传需求文档
- 发起智能体分析
- 展示候选用例
- 展示评审意见
- 输入补充说明
- 触发重新生成/重新评审
- 点击确认落库

这个页面基于现有：

- `apps/platform-web/src/components/chat-template/base-chat-template.tsx`
- `apps/platform-web/src/hooks/use-file-upload.tsx`
- `apps/platform-web/src/components/thread/artifact.tsx`

### 3.2 用例管理页

建议路由：

- `/workspace/usecases`
- `/workspace/usecases/[usecaseId]`
- `/workspace/usecases/new`

页面职责：

- 查看正式用例列表
- 查询、分页、过滤
- 查看详情
- 修改
- 删除

这个页面复用现有管理页模式，例如：

- `apps/platform-web/src/app/workspace/projects/page.tsx`
- `apps/platform-web/src/lib/management-api/projects.ts`

## 4. runtime-service 工作流设计

## 4.1 父智能体

建议新增一个 graph：

- `usecase_workflow_agent`

它不是单轮聊天 agent，而是 deepagent 父智能体，负责整条流程编排。

### 4.2 子智能体建议

建议至少有两个真正的业务子智能体：

- `requirement_analysis_subagent`
  - 解析需求文档
  - 提炼功能点、规则、前置条件、边界场景、异常场景
- `usecase_review_subagent`
  - 审查候选用例
  - 输出缺失点、歧义点、规范问题、改进建议

不建议把“落库”实现成一个自由思考的子智能体。

落库更适合做成：

- 一个明确的本地 tool
- 或一个确定性的 workflow step

### 4.3 工作流阶段

建议父智能体按显式状态推进：

- `uploaded`
- `analyzing`
- `generated`
- `reviewed`
- `awaiting_user_confirmation`
- `revision_requested`
- `approved_for_persistence`
- `persisted`
- `failed`

### 4.4 推荐步骤

1. `ingest_requirement_document`
2. `analyze_requirement`
3. `generate_candidate_usecases`
4. `review_candidate_usecases`
5. `build_revision_summary`
6. `await_user_confirmation`
7. `persist_final_usecases`

## 5. 人工确认机制

这个案例的关键不是“能生成”，而是“不能自动变正式数据”。

必须保证：

- 评审后只生成候选版本
- 用户可以继续给意见
- 用户可以触发再次修订
- 只有用户明确确认后，才能执行持久化

因此系统需要区分三类内容：

- 当前候选用例
- 当前评审报告
- 当前是否允许落库的判断

推荐由后端返回明确字段，例如：

- `workflow_status`
- `latest_snapshot_id`
- `persistable`
- `review_summary`
- `deficiency_count`

## 6. interaction-data-service 数据设计

这个场景不适合只靠一张通用记录表。

建议分成“工作流表”和“正式业务表”两层。

### 6.1 工作流过程表

- `requirement_documents`
  - 上传的原始需求文档元数据
- `usecase_workflows`
  - 一次从需求到用例的任务主记录
- `usecase_workflow_snapshots`
  - 每轮生成后的候选版本
- `usecase_review_reports`
  - 每轮评审报告

### 6.2 正式业务表

- `use_cases`
- `use_case_steps`（如需要）
- `test_cases`（若与 use case 分离）

### 6.3 公共登记层

如果继续保留 `interaction_records` 的统一入口思路，建议：

- 工作流快照和评审报告仍登记到公共记录层
- 正式用例数据落专有业务表

也就是说：

- 公共记录层解决统一索引与追踪
- 业务表解决正式数据表达

## 7. 建议表关系

```text
requirement_documents
  -> usecase_workflows
       -> usecase_workflow_snapshots
       -> usecase_review_reports
       -> use_cases
            -> use_case_steps
            -> test_cases
```

说明：

- 一个 workflow 可以有多个 snapshot
- 一个 snapshot 可以对应一个 review report
- 只有被批准的 snapshot 才能提升为正式 use cases

## 8. HTTP API 设计

建议按两类资源暴露接口。

### 8.1 工作流接口

- `POST /api/workflows`
  - 创建工作流，挂接需求文档
- `GET /api/workflows`
  - 查询工作流列表
- `GET /api/workflows/{workflow_id}`
  - 获取工作流详情
- `GET /api/workflows/{workflow_id}/snapshots`
  - 获取历史候选版本
- `POST /api/workflows/{workflow_id}/revision`
  - 提交用户反馈并触发新一轮修订
- `POST /api/workflows/{workflow_id}/approve`
  - 标记用户确认通过
- `POST /api/workflows/{workflow_id}/persist`
  - 将已确认 snapshot 提升为正式数据

### 8.2 正式用例 CRUD 接口

- `GET /api/use-cases`
- `POST /api/use-cases`
- `GET /api/use-cases/{usecase_id}`
- `PATCH /api/use-cases/{usecase_id}`
- `DELETE /api/use-cases/{usecase_id}`

如业务需要，再补：

- `GET /api/test-cases`
- `PATCH /api/test-cases/{testcase_id}`

## 9. runtime-service 本地 tools 设计

这类工具不进入公共 `tools registry`。

每个业务 agent 自己在本地定义高语义工具。

推荐工具分为两类：

### 9.1 工作流过程工具

- `create_usecase_workflow`
- `save_requirement_analysis_snapshot`
- `save_usecase_review_report`
- `get_current_workflow_snapshot`
- `mark_workflow_ready_for_confirmation`

### 9.2 最终落库工具

- `persist_final_usecases`

这些工具内部调用不同 HTTP 接口，而不是统一落到一个模糊入口。

## 10. 前端交互设计

### 10.1 工作台页面要展示什么

至少展示三类内容：

- 需求分析结果
- 当前候选用例
- 当前评审报告

建议 UI 操作包括：

- 上传文档
- 发起生成
- 查看当前版本
- 录入补充说明
- 重新生成
- 重新评审
- 确认落库

### 10.2 CRUD 页面要展示什么

正式用例管理页建议支持：

- 列表
- 搜索
- 分页
- 详情
- 修改
- 删除

它只展示正式数据，不展示未确认草稿。

## 11. 平台职责划分

### 11.1 `platform-api`

建议作为唯一平台入口：

- 接收前端请求
- 校验当前用户和项目权限
- 调用 `runtime-service`
- 调用 `interaction-data-service`
- 向前端返回统一视图

### 11.2 `platform-web`

继续只调用 `platform-api`，不要直接访问 `interaction-data-service`。

## 12. 第一阶段建议实施范围

为了尽快闭环，第一期建议只做：

1. 一个 `usecase_workflow_agent`
2. 两个 subagent：需求分析、用例评审
3. 一套工作流状态机
4. 四张核心表：
   - `requirement_documents`
   - `usecase_workflows`
   - `usecase_workflow_snapshots`
   - `use_cases`
5. 一个工作台页面
6. 一个正式用例列表页
7. 一个人工确认后落库动作

## 13. 第二阶段建议

第二期再扩展：

- 版本 diff
- 审批轨迹
- review 标准配置化
- `test_cases` 独立管理
- 详情页/编辑页

## 14. 最终结论

这个真实案例最优解不是“单个用例生成 agent”，而是：

- 一个 deepagent 驱动的工作流
- 一个保存工作流过程和正式结果的 `interaction-data-service`
- 一个聊天式工作台页面
- 一个正式用例 CRUD 页面
- 一个必须由人工触发的最终落库关口

只有这样，系统才能同时满足：

- 智能生成
- 规范评审
- 人工把关
- 结果可追溯
- 正式数据可管理
