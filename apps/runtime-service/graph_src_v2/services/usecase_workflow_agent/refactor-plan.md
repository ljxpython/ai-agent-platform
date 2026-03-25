# usecase_workflow_agent 重构实施计划

本文对应 README 中已经确认的新目标，后续代码改动以这里为执行顺序。

本轮不是重写全部代码，而是按最小闭环逐步收敛，优先解决：

- `review -> generation -> review` 自动回环
- review 后没有正确停给用户
- 普通修订输入与 HITL 执行审批边界混乱

## 1. 已确认目标

这轮后续实现必须满足：

1. 首轮需求输入允许自动跑完：
   - `analysis -> generation -> review`
2. review 完成后必须停住，把结果交给用户
3. review 不通过时进入 `awaiting_user_revision`
4. review 通过时进入 `awaiting_user_confirmation`
5. 用户新的修订输入只允许触发一次有界的：
   - `generation -> review`
6. 只有用户明确确认落库时，才进入持久化子智能体
7. 最终 HITL 仍然只拦：
   - `persist_approved_usecases`
8. HITL `edit` 视为一次新的人工修订输入
9. 新 review 结果生成后，旧确认失效，必须重新确认

## 2. 非目标

这一轮先不做：

- 改成 deepagent
- 改成显式 `StateGraph`
- 引入额外的通用抽象层
- 一次性重构整个 interaction-data-service
- 为了绕过问题而单纯调高 `recursion_limit`

## 3. 目标状态机

后续代码对外主阶段收敛为：

- `analysis`
- `generation`
- `review`
- `awaiting_user_revision`
- `awaiting_user_confirmation`
- `completed`

说明：

- `persist` 仍可作为内部执行步骤存在，但不作为主文档阶段继续扩散
- `revision_requested`、`persisting` 这类过时目标阶段从后续方案里移除

## 4. 核心设计原则

### 4.1 一次人工输入，只买一轮自动推进

这是本轮最关键的约束：

- 首轮需求输入可以买一轮完整自动链路
- 每次新的修订意见可以买一轮 `generation -> review`
- 同一轮旧输入不能让系统无限自转

### 4.2 review 必须是“停顿点”

review 完成后必须停给用户，不再允许：

- review 失败后自动重新生成
- 系统基于旧的 deficiency 自己继续改下一版

### 4.3 HITL 只负责执行审批

HITL 的职责继续收敛为：

- 最终落库动作的执行审批

HITL 不负责：

- 代替用户做普通修订对话
- 代替 review 阶段的人类判断

## 5. 分步实施顺序

## Step 1. 收紧阶段命名与文档语义

目标：

- 先让 README、计划、测试、代码讨论使用同一套阶段语言

计划动作：

- 清理文档里的 `revision_requested`
- 清理文档里的 `persisting`
- 明确：
  - `awaiting_user_revision`
  - `awaiting_user_confirmation`

完成标准：

- 模块内文档不再保留过时目标阶段
- review 后停给用户成为明确约束，而不是可选描述

## Step 2. 切断 review 失败后的自动回环

目标：

- 去掉 `reviewed_candidate_usecases + persistable=False -> generation` 这条自动回路

计划动作：

- 收紧阶段推断逻辑
- 收紧工具放行逻辑
- 让 review 不通过时停在 `awaiting_user_revision`

完成标准：

- 不再出现基于同一轮输入的自动 `generation -> review -> generation -> review`
- `recursion_limit` 不再因为这条回路被打满

## Step 3. 把“新的人工输入”做成重新进入 generation 的唯一入口

目标：

- 只有真的拿到新的修订意见，才允许再生成一次

计划动作：

- 用户自然语言修订意见进入 generation
- HITL `edit.revision_feedback` 进入 generation
- 没有新的人类输入时，不允许继续自动修订

完成标准：

- 重新生成一定有明确的人类触发来源
- 一次触发只推进一轮 `generation -> review`

## Step 4. 强制 review 后输出用户可读总结并停止

目标：

- review 不再只是系统内部 snapshot
- 每轮 review 后都必须让用户看得见结果

计划动作：

- 明确 review 后的用户可读输出内容：
  - 当前候选用例摘要
  - 评审结论
  - 缺陷或建议
  - 下一步可选动作
- 把“停下来等用户”从 prompt 建议提升为流程约束

完成标准：

- review 后总有可读回复
- review 后总会停下来等待用户，而不是继续跑工具

## Step 5. 保留并收紧最终持久化 HITL

目标：

- 保留当前已经正确下放到子智能体内部的执行审批边界

计划动作：

- 继续只让 `persist_approved_usecases` 触发 HITL
- 明确：
  - `approve` -> 真落库
  - `edit` -> 作为新的修订输入回到 `generation -> review`
  - `reject` -> 不落库，回到用户决定
- 明确新 review 结果出来后，旧确认作废

完成标准：

- 普通修订与执行审批彻底分层
- 不会在新 review 之后复用旧确认直接落库

## Step 6. 清理过时实现注释、文档和测试预期

目标：

- 删除仍在暗示“自动 review 回环是目标行为”的过时内容

计划动作：

- 清理模块 README、计划、注释中的旧描述
- 更新测试名称和断言语义
- 删除或替换误导性的过时注释

完成标准：

- 文档、测试、实现讨论口径一致
- 模块内不再残留“自动修订回环”的目标表述

## Step 7. 验证与验收

目标：

- 真实确认新状态机真的停对地方

计划动作：

- 补或调整单测，覆盖：
  - 首轮自动 `analysis -> generation -> review`
  - review 不通过后停在等待用户修订
  - 用户修订后只推进一轮 `generation -> review`
  - review 通过后等待明确确认
  - 确认后进入 HITL
  - HITL `edit` 后重新 review，再次停给用户
  - HITL `approve` 后真实落库
  - HITL `reject` 后不落库
- 使用 [services_usecase_workflow.py](/Users/bytedance/PycharmProjects/my_best/AITestLab/apps/runtime-service/graph_src_v2/tests/services_usecase_workflow.py) 做真实链路验证

完成标准：

- 不再出现 review 自动回环
- 两种人工参与模式都能稳定感知：
  - 普通对话 / 修订
  - HITL 执行审批

## 6. 推荐执行顺序

真正开始改代码时，建议按下面顺序做：

1. 先改阶段推断和工具放行，切断自动回环
2. 再改 review 后停顿与用户可读输出
3. 再改 HITL `edit` 回流语义
4. 最后收尾清理旧测试、旧注释和文档

原因很简单：

- 先止血，先把无限回环砍掉
- 再把交互边界做对
- 最后再清理零碎历史包袱
