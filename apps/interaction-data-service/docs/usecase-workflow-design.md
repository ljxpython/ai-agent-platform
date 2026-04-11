# 用例生成工作流设计稿

状态：`Historical-in-place`

> 归档说明：本文对应的 `/api/usecase-generation/*` 业务接口已退役，仅保留为历史设计记录，不再作为当前实现参考。
>
> 当前正式结果域主线请改读：
> - `../README.md`
> - `README.md`
> - `test-case-service-api-design.md`

本文描述的是用例生成工作流的目标设计稿，用来约束后续 `runtime-service` 与 `interaction-data-service` 之间的结果契约。

需要特别说明：

- 这里描述的是“目标优化方向”
- 它不等于“当前代码已经全部如此”
- 当前代码真实状态请同时参考：
  - `apps/runtime-service/graph_src_v2/services/usecase_workflow_agent/README.md`
  - `apps/runtime-service/graph_src_v2/services/usecase_workflow_agent/refactor-plan.md`

## 1. 业务目标

目标不是一次对话里随手吐出一版用例，而是建立一条受控、可追踪、可反复修订的业务工作流：

1. 上传需求文档
2. 需求分析
3. 生成候选用例
4. 用例评审
5. 向用户展示评审结果与修订建议
6. 用户决定继续修改还是确认可落库
7. 人工确认后执行正式落库
8. 在平台对正式用例做 CRUD 管理

核心原则：

- 草稿和正式数据分离
- review 先于 confirmation
- confirmation 先于 persistence
- 附件解析产物保留并可追踪
- 最终正式数据仍由人工把关后写入

## 2. 目标系统边界

### 2.1 runtime-service

负责：

- 主 orchestrator 调度整条流程
- 调用四个业务 subagent
- 在每个阶段后给用户明确汇报
- 在需要人工确认时停下来等待用户决定
- 通过本地 tools 调用 `interaction-data-service`

不负责：

- 平台鉴权
- 平台 CRUD 页面本身
- 让数据库替代对话内状态流转

### 2.2 interaction-data-service

负责：

- 保存附件解析产物
- 保存最终正式用例
- 对外提供稳定 HTTP 契约
- 为平台后续查询和管理提供结果域

当前这一轮目标里，不再把它当成“中间 workflow/snapshot/review 的推荐主存储中心”。

### 2.3 platform-api

负责：

- 用户和项目上下文
- 权限控制
- 聚合 `runtime-service` 与 `interaction-data-service`

### 2.4 platform-web

负责：

- 上传文档
- 查看当前工作流汇报
- 查看候选用例与评审意见
- 输入修订意见
- 最终确认落库
- 管理正式用例

## 3. 目标 agent 拓扑

目标拓扑是：

- 一个主 orchestrator
- 四个 subagent

四个 subagent：

1. `requirement_analysis_subagent`
2. `usecase_generation_subagent`
3. `usecase_review_subagent`
4. `usecase_persist_subagent`

职责说明：

- requirement analysis
  - 提炼功能点、规则、前置条件、边界和异常
- usecase generation
  - 根据需求分析结果和用户补充意见生成候选用例
- usecase review
  - 审查候选用例覆盖性、规范性和修订建议
- usecase persist
  - 在人工确认后执行最终持久化相关动作

注意：

- persist subagent 不是无边界自由思考 agent
- 它更像一个受控执行边界，内部工具应该很少、很明确

## 4. 目标阶段模型

目标阶段建议统一为：

- `analysis`
- `generation`
- `review`
- `awaiting_user_confirmation`
- `revision_requested`
- `persisting`
- `completed`

推荐主链路：

```text
upload/input
  -> analysis
  -> generation
  -> review
  -> user-visible summary
  -> awaiting_user_confirmation
  -> persisting
  -> completed
```

推荐修订链路：

```text
awaiting_user_confirmation
  -> revision_requested
  -> generation
  -> review
  -> awaiting_user_confirmation
```

## 5. 用户可见交互规则

这条工作流必须保证“每一步都能让用户看懂当前发生了什么”。

### 5.1 analysis 后

主 orchestrator 必须说明：

- 识别到哪些核心需求
- 当前有哪些不明确项
- 接下来要生成候选用例

### 5.2 generation 后

主 orchestrator 必须说明：

- 当前生成的候选用例范围
- 是否已经准备进入评审

### 5.3 review 后

主 orchestrator 必须说明：

- 当前候选用例摘要
- 评审结论
- 需要改什么
- 现在是否建议用户确认

### 5.4 persist 后

主 orchestrator 必须说明：

- 附件解析产物是否已入库
- 最终用例是否已入库
- 当前工作流是否完成

## 6. 人工确认机制

本流程有两层确认：

### 6.1 review 后的业务确认

review 完成后，用户先看：

- 当前候选用例
- 当前评审意见
- 当前修订建议

然后用户决定：

- 继续修改
- 再来一轮生成/评审
- 确认进入持久化

### 6.2 persist 前的执行确认

即使用户在业务层面说“可以落库”，执行层仍保留最终 HITL。

也就是说：

- review 后的确认是业务动作确认
- persist 前的 HITL 是最终执行防线

## 7. runtime-service 内部工具边界

推荐把工具分成四组，与四个 subagent 对齐。

### 7.1 requirement analysis 工具

- `run_requirement_analysis_subagent`
- `record_requirement_analysis_snapshot`

### 7.2 usecase generation 工具

- `run_usecase_generation_subagent`
- `record_candidate_usecases_snapshot`

### 7.3 usecase review 工具

- `run_usecase_review_subagent`
- `record_usecase_review_snapshot`

### 7.4 usecase persist 工具

- `persist_requirement_documents`
- `persist_final_usecases`
- 或一个组合 persist 工具，但内部职责必须明确拆分

推荐原则：

- 每个阶段用自己的工具
- 主 orchestrator 不直接承担重型业务推理
- 持久化工具只处理最终结果，不接管中间流程控制

## 8. interaction-data-service 数据与接口边界

这一轮目标保留两个结果域：

1. 附件解析产物
2. 最终正式用例

因此，当前目标保留的接口主面是：

- `POST /api/usecase-generation/workflows/documents`
- `GET /api/usecase-generation/workflows/documents`
- `GET /api/usecase-generation/workflows/documents/{document_id}`
- `GET /api/usecase-generation/use-cases`
- `POST /api/usecase-generation/use-cases`
- `GET /api/usecase-generation/use-cases/{use_case_id}`
- `PATCH /api/usecase-generation/use-cases/{use_case_id}`
- `DELETE /api/usecase-generation/use-cases/{use_case_id}`

这些接口分别支撑：

- 追踪解析产物
- 写入和管理最终正式用例

## 9. 清理候选接口

当前代码里仍存在一组 workflow/snapshot/review 相关接口：

- `POST /api/usecase-generation/workflows`
- `GET /api/usecase-generation/workflows`
- `GET /api/usecase-generation/workflows/{workflow_id}`
- `GET /api/usecase-generation/workflows/{workflow_id}/snapshots`
- `POST /api/usecase-generation/workflows/{workflow_id}/snapshots`
- `POST /api/usecase-generation/workflows/{workflow_id}/review`
- `POST /api/usecase-generation/workflows/{workflow_id}/approve`
- `POST /api/usecase-generation/workflows/{workflow_id}/persist`

但在本轮目标里：

- 它们不是推荐主路径
- 后续是否删除，取决于 runtime 代码是否已经完全不依赖它们

文档先把它们标记为“清理候选”，而不是假装它们已经不存在。

## 10. 附件解析产物为什么要保留

这个点已经明确：保留。

原因：

- 方便回查 PDF / 图片解析质量
- 方便排查多模态链路问题
- 方便后续展示“当前用例来自哪些附件输入”
- 方便后续做追溯和审计

当前重点字段仍然是：

- `summary_for_model`
- `parsed_text`
- `structured_data`
- `provenance`
- `confidence`
- `error`

## 11. 平台产品形态

推荐仍然拆成两个页面：

### 11.1 用例生成工作台

职责：

- 上传需求文档
- 查看 analysis / generation / review 各阶段汇报
- 查看候选用例与评审意见
- 输入修订意见
- 最终确认是否落库

### 11.2 用例管理页

职责：

- 查看正式用例
- 搜索、分页、过滤
- 查看详情
- 修改
- 删除

工作台展示过程结果，管理页只展示正式数据。

## 12. 实施方式

本设计稿不会要求“一次性全部落完”。

后续执行顺序以：

- `apps/runtime-service/graph_src_v2/services/usecase_workflow_agent/refactor-plan.md`

为准，按步骤逐步实现。

## 13. 最终结论

这条工作流的目标最优解，不是“一个会聊天的单 agent”，也不是“把所有中间过程都塞进数据库”。

更合适的结构是：

- 一个主 orchestrator
- 四个阶段职责明确的 subagent
- review 先于 confirmation
- confirmation 先于 persistence
- 保留附件解析产物落库
- 最终正式用例由人工确认后落库

只有这样，系统才能同时满足：

- 智能协作
- 阶段透明
- 人工把关
- 结果可追溯
- 正式数据可管理
