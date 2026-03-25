# usecase_workflow_agent 当前实现与确认后的收敛目标

本文只做两件事：

- 说明这个模块当前代码已经真实实现了什么
- 记录这轮讨论后已经确认的新目标状态机与交互边界

这份文档是接下来改代码的约束。代码还没全部改到位前，以这里的目标行为为准，不再以旧的自动回环设计为准。

## 1. 模块当前真实职责

当前 `usecase_workflow_agent` 负责一条业务链路：

1. 接收文本需求或附件
2. 结合多模态中间件结果做需求分析
3. 生成候选用例
4. 评审候选用例
5. 在用户明确确认后进入最终落库

当前目录结构：

```text
graph_src_v2/services/usecase_workflow_agent/
  __init__.py
  graph.py
  prompts.py
  schemas.py
  tools.py
  workflow_policy.py
  README.md
  refactor-plan.md
```

当前代码职责分布：

- `graph.py`
  - 装配主 agent
  - 挂载 `WorkflowToolSelectionMiddleware`
  - 挂载 `MultimodalMiddleware`
- `workflow_policy.py`
  - 定义阶段允许工具
  - 做阶段推断
  - 处理“等待用户确认”阶段的工具放行
- `tools.py`
  - 定义四个子智能体调用工具
  - 定义三个 snapshot 工具
  - 定义最终持久化执行工具
- `schemas.py`
  - 定义状态字段和 workflow snapshot 结构
- `prompts.py`
  - 定义主 agent 与各子智能体提示词

## 2. 当前真实实现边界

### 2.1 当前 agent 结构

当前实现基于 `create_agent(...)`，不是显式 `StateGraph`。

当前实际存在的子智能体：

- `requirement_analysis_subagent`
- `usecase_generation_subagent`
- `usecase_review_subagent`
- `usecase_persist_subagent`

当前实际存在的 snapshot 工具：

- `record_requirement_analysis`
- `record_generated_usecases`
- `record_usecase_review`

### 2.2 当前人工交互边界

当前有两类“需要人参与”的交互，但它们不是同一层：

1. 普通对话 / 业务修订输入
   - 这是普通用户消息
   - 不触发 `HumanInTheLoopMiddleware`
   - 系统应该自然回复并等待下一轮用户输入
2. 最终执行审批
   - 只在 `usecase_persist_subagent` 内部发生
   - 由 `HumanInTheLoopMiddleware` 拦截 `persist_approved_usecases`
   - 允许的决策是：
     - `approve`
     - `edit`
     - `reject`

当前唯一真正被 `HumanInTheLoopMiddleware` 拦截的动作是：

- `persist_approved_usecases`

### 2.3 当前对 interaction-data-service 的真实写入边界

当前代码对 `interaction-data-service` 的真实 HTTP 写入只发生在最终持久化执行阶段。

当前最终持久化会写两类结果：

- 需求附件解析产物
- 最终批准用例

## 3. 当前已经确认的问题

这轮讨论后，已经明确一个需要收敛的核心问题：

- 当前 workflow 允许 `review -> generation -> review` 自动回环
- 真实模型只要连续给出 deficiency，就可能一直自转
- 最终会撞上 LangGraph 的 `recursion_limit`

这不是单纯调大 `recursion_limit` 就能解决的问题，本质上是状态机边界设计不对。

## 4. 已确认的新目标行为

这部分是后续代码修改必须遵守的目标，不再以旧文档中的自动修订回环为准。

### 4.1 总原则

新目标遵守三条原则：

1. 首轮需求输入可以自动跑完整个分析链
2. 每一次新的人工输入，只允许触发一次有界的自动推进
3. 每次 review 完成后，系统必须把控制权交还给用户

这里的“人工输入”包括两类：

- 用户自然语言修订意见
- HITL `edit` 给出的 `revision_feedback`

### 4.2 新的状态机

对外收敛后的主阶段只保留：

- `analysis`
- `generation`
- `review`
- `awaiting_user_revision`
- `awaiting_user_confirmation`
- `completed`

说明：

- `persist` 仍然存在，但它是内部执行步骤，不再作为对外主阶段重点描述
- 不再保留过时的 `revision_requested`
- 不再把 `reviewed_candidate_usecases + persistable=False` 直接等价成重新进入 `generation`

### 4.3 新的用户可感知交互模式

#### 模式 A：讨论 / 修订

这是普通多轮对话，不是 HITL。

行为要求：

- review 完成后，无论结果是否可落库，都先把评审结果返回给用户
- 如果 review 不通过，进入 `awaiting_user_revision`
- 系统只说明问题、建议和下一步，不自动继续生成下一版
- 必须等待用户提供新的修订意见

#### 模式 B：执行审批

这是 HITL。

行为要求：

- 只有 review 通过且用户明确确认“当前版本可以落库”时，才允许进入 `usecase_persist_subagent`
- 进入 `usecase_persist_subagent` 后，再由 `HumanInTheLoopMiddleware` 对 `persist_approved_usecases` 做最终执行审批
- `approve / edit / reject` 只属于执行审批层，不属于普通讨论层

### 4.4 有界推进规则

后续代码必须遵守下面这条硬规则：

> 一次新的人工输入，只允许触发一次有界的自动推进，不允许基于同一轮旧输入无限回环。

具体落地规则：

1. 首次需求输入
   - 允许自动执行：
     - `analysis -> generation -> review`
   - review 完成后必须停住
2. 用户给出修订意见
   - 允许自动执行一次：
     - `generation -> review`
   - review 完成后必须再次停住
3. 用户明确确认落库
   - 允许进入：
     - `usecase_persist_subagent`
     - 内部 HITL
4. HITL `edit`
   - 把 `revision_feedback` 视为一次新的人工修订输入
   - 允许自动执行一次：
     - `generation -> review`
   - review 完成后必须再次停住，重新等待用户确认
5. HITL `reject`
   - 本次不落库
   - 不自动重试持久化
   - 必须回到用户决定

### 4.5 明确禁止的旧行为

以下行为后续必须移除：

1. review 失败后自动重新进入 generation
2. 基于同一轮用户输入无限执行 `generation -> review -> generation -> review`
3. 在新的 review 结果出来后，继续沿用旧的“确认落库”语义
4. 把普通业务修订对话和最终执行审批混成一个确认点

## 5. 目标链路

### 5.1 首轮自动链路

```text
用户提供需求 / PDF
  -> analysis
  -> generation
  -> review
  -> 返回评审结果给用户
  -> awaiting_user_revision 或 awaiting_user_confirmation
```

### 5.2 修订链路

```text
用户提供修订意见
  -> generation
  -> review
  -> 返回新一轮评审结果给用户
  -> awaiting_user_revision 或 awaiting_user_confirmation
```

### 5.3 确认落库链路

```text
用户明确确认当前版本可以落库
  -> run_usecase_persist_subagent
  -> persist_approved_usecases
  -> HITL approve / edit / reject
  -> completed 或返回修订等待状态
```

## 6. 文档收敛结论

这轮文档确认后的结论是：

- 当前最重要的收敛点不是“把链路跑得更自动”，而是“把边界停对地方”
- review 后必须停给用户，不能让系统自己一直改
- HITL 只保留在最终执行落库这一层
- 普通讨论和执行审批必须区分成两种不同的交互模式

## 7. 下一步

下一步不直接凭感觉改代码，而是按 [refactor-plan.md](/Users/bytedance/PycharmProjects/my_best/AITestLab/apps/runtime-service/graph_src_v2/services/usecase_workflow_agent/refactor-plan.md) 里新的实施计划逐步推进。
