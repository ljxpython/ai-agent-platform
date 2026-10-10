# 源码对照与辩证分析

> 2026-10-08 至 2026-10-09 只读调研。以下“现状”为源码事实，“推荐”为待评审设计；读到测试源码不等于执行了测试。

## 参考证据边界

参考仓为用户指定的本机 open-swe，通常位于 `~/PyCharmMiscProject/research/open-swe`。本仓 HEAD 为 `85d63d87bdf84dabbb963f79e8dd4b2db4432ade`，参考 HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`。

open-swe 工作副本存在大量已暂存/未暂存改动和未合并文件，包括 `uv.lock`、`agent/dashboard/options.py`。本次依据实际文件内容，不将其等同干净 HEAD、上游稳定版本或生产验证结果；不修改、安装或运行参考仓。

| 参考文件，相对 open-swe 根 | SHA256，2026-10-09 |
| --- | --- |
| `agent/middleware/plan_mode.py` | `069394e75a3e21d630862383575e36028a7d7ffaebd16bbe2dbb41992178fb1a` |
| `agent/tools/enter_plan_mode.py` | `f103a0c168886dfc951b01ca78c15fa939841d9d600ec8db27cb7bd1a1fe7e28` |
| `agent/tools/save_plan.py` | `72b89bb1c977e8c9154dd0c219017ea2ab2d0c05a6c1309675b91b2241adc279` |
| `agent/tools/approve_plan.py` | `6ed3ac7a0f09b0ad2ed287c7481345b9c68bdc613322ff6802b49fd026cc331b` |
| `agent/dashboard/plan_api.py` | `a85e3cd8837908fe155592870b02a70abd98652065632119c81a478737e997ab` |
| `ui/src/features/agents/components/PlanReview.tsx` | `d27b102e9d27552dec828d89b41a55792db5407d3575b686ea3d2c3cfc177a9c` |

## open-swe 实际设计

| 位置 | 实际做法 | 可借鉴点与限制 |
| --- | --- | --- |
| `agent/middleware/plan_mode.py:PlanModeState/PlanModeMiddleware` | state 声明 bool；`before_agent()` 将其重置为当前 Run 的 initial；`awrap_model_call()` 按 excluded 隐藏工具 | 动态裁剪好用；没有 `wrap_tool_call` 执行门禁，新 Run 的重置规则不能直接复制 |
| `agent/server.py`，约 325 行的 Plan Mode 装配 | 排除外部变更、全部 MCP 和 `task`；注释明确保留 `write_file/edit_file/execute`，通过提示词约束 repo 只读 | 明确识别子图不继承限制；保留通用 shell/写工具不构成强权限隔离 |
| `agent/tools/enter_plan_mode.py:enter_plan_mode()` | 更新计划 store/Thread metadata，再返回 `Command(plan_mode=True)`；store 失败只记 warning | 工具切换状态可复用；状态双写、失败后继续的方式不适合放权事实源 |
| `agent/tools/save_plan.py`、`agent/dashboard/plan_store.py` | 从 `/workspace/plans/` 读取 HTML，保存计划内容、状态、评论及 Thread metadata | 有明确计划产物；HTML、sandbox、双写和评论体系不是通用核心的必需项 |
| `agent/tools/approve_plan.py:approve_plan()` | 模型可调用；从配置中的 Slack/GitHub/email 身份推导批准人，设置 approved 和 `plan_mode=False` | 可把对话批准转成状态；该工具本身没有原生人类 interrupt 校验，不能作为本平台安全放权入口 |
| `agent/dashboard/plan_api.py` | UI 会话鉴权；批准/驳回写状态后 dispatch 新 Run；批准使用进程内 lock，派发失败尝试回退 | 预览、反馈与人工动作值得借鉴；进程内锁不能替代多 Worker 幂等、版本绑定及持久恢复 |
| `ui/src/features/agents/components/PlanReview.tsx` 与 Composer | 计划独立预览、评论、批准、请求修改及模式开关 | 复用交互概念，按本仓 Vue/SDK 范式实现；不复制 React 页面与渠道属性 |
| `tests/agent/test_plan_mode.py` | 测试工具可见性；明确断言 execute、普通写文件和 approve_plan 仍在 | 证明参考的实际边界，并未证明“未批准绝不能写代码” |

所以同事给出的状态图概括了产品目标，却省略了参考实现中的提示词依赖、独立 dashboard dispatch、双事实源与模型批准路径。不能据此认为只补 bool 和模型过滤就能达到生产权限要求。

## 当前平台已有能力与差距

| 能力 | 当前事实与代码位置 | 缺口 / 本期处理 |
| --- | --- | --- |
| 会话工具审批 | `apps/runtime-service/src/runtime_service/runtime/access_policy.py:interrupts_for_access_policy()`；review/workspace_write/full_access | 控制是否逐工具审批，workspace_write 还跳过 execute 审批；不是整体只读模式，保持正交 |
| DearFlow planning | `apps/runtime-service/src/runtime_service/services/dearflow_agent/modes.py` 的 pro/ultra | 只是 Todo/分工配置；不代表人类批准前不能执行，不将 execution_mode 改成权限字段 |
| 两处工具授权 | `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py:RuntimeConfigMiddleware.awrap_model_call()/awrap_tool_call()` | 已做模型列表、响应工具名、执行时授权；新增规划限制与它取交集，不能替换 |
| 组合根 | `services/demo/showcase_demo/agent.py`、`services/dearflow_agent/agent.py`、`services/reference_agent/agent.py`，均在 Runtime 源目录 | 接线位置已存在；公共 middleware/tools 加到各自工厂，不创建统一 Builder/Registry |
| 嵌套工作流 | `services/demo/workflow_demo/agent.py:model_agent_for()`、`workflow.py:build_graph()/respond()`、`schemas.py:WorkflowBudgetState` | 独立外层 StateGraph，内部仅输入 messages/输出 response/messages，当前内部 middleware 无 RuntimeConfigMiddleware；新工具需补授权、内外计划状态传递和持久恢复测试 |
| 主子图 | Showcase `subagents.py` 有只读 research 和可写 general-purpose；Dear `subagents/researcher.py` 将默认 general-purpose 收敛为只读 | 上游子图状态不自动继承；首期规划禁 task，子图仍接执行防护，恢复执行不放大子图固有权限 |
| 人类中断 | API `modules/runtime_gateway/application/service.py:send_thread_command()` 与 `application/clarification.py` | 已校验当前 interrupt、来源 Run、原配置、审批 ACL；增加计划类型/回复验证，复用 resume |
| 运行幂等 | 同服务 `launch_runtime_run()`、RunRequestsRepository | 有 request digest、parent_run_id 和 unknown 处理；计划批准绑定确切版本，执行链需服务端签名标识 |
| 身份与审批 ACL | API `application/thread_access.py`；Runtime `auth/platform.py` | owner/manager 才能批准，共享 edit/comment 不代表审批；模型、服务账号与终端命令不能冒充人类批准 |
| Context 信任边界 | Runtime `runtime/contracts.py`、`runtime/resolver.py`；API `core/runtime_contract.py`、`core/security/tokens.py` | 白名单与 Context hash v5 已存在；新增请求选项与内部执行标识需要双端 v6 和持久快照处理 |
| 私有状态与公开投影 | API `core/runtime_contract.py:reject_private_runtime_state()`、`adapters/langgraph/sdk_client.py:redact_runtime_private_fields()` | 加计划私有字段防注入；公开投影只保留展示数据，不能把批准令牌放进 state/SSE |
| 分叉与重放 | API `application/service.py:fork_thread()` 目前复制 checkpoint values | 不得复制计划授权；需清理授权、以新执行重新审批，覆盖历史 checkpoint 启动入口 |
| 聊天审批 | Web `src/modules/chat/approvals.ts:parseReviews()`、`composables/useSessionInterrupts.ts` | 普通审批当前只排除 clarification；必须识别独立计划 interrupt，复用 SDK 生命周期 |
| 运行配置与 capability | Web `useChatRunConfig.ts`、`run-actions.ts`、`types/workspace.ts`、`services/threads/workspace.service.ts` | 加下一次 Run 开关与 capability；resume 不能附带新的 Context/config，不再建第二套 Run 状态机 |

表中 `services/...` 等简写均相对 `apps/runtime-service/src/runtime_service/`，API `application/...` 相对 `apps/platform-api/src/platform_api/modules/runtime_gateway/`。逐文件完整实施清单见 [plan.md](plan.md#代码改动清单)。

### 工具以外的真实副作用

DearFlow `services/dearflow_agent/tools/search.py:_evidence()` 和 GitHub/arXiv 调研会写 `/workspace/sources/`；`middleware/memory.py:aafter_agent()` 可自动写记忆候选。Workspace 准备、Skills 执行快照、摘要/history、checkpoint、日志与 usage 也会落盘。

因此隐藏 manage_memory、write_file、execute 不等于规划阶段零写入。推荐允许有界基础设施写入和可信调研缓存，禁止业务文件、外部变更、持久记忆候选和技能变更；详情见方案的副作用表。DearFlow 普通文件写入边界是 `/workspace/work/`，不能为了计划把 `/workspace/plans/` 加成通用可写逃生口。

## 对同事五项建议的判断

| 建议 | 判断 | 本仓推荐 |
| --- | --- | --- |
| AgentState 加 `plan_mode: bool` | 方向正确，bool 不能描述版本/当前审批/执行授权 | 用 middleware 的私有 state schema 保存计划快照和授权绑定，公开另投影；请求保留 bool 开关 |
| LLM 可调用 enter_plan_mode | 采用 | 独立工具批次切换；下一模型轮次和工具执行均限制；严格规划从首步开关进入 |
| 平台批准后调用 approve_plan | 不采用模型可调用放权工具 | submit_plan 产生原生 interrupt；平台鉴权后 input.respond，Runtime 校验回复再解锁 |
| awrap_model_call 动态过滤 | 采用但不足 | 默认允许名单、模型响应整批检查、实际 awrap_tool_call 拒绝；和 RuntimeConfig 授权取交集 |
| 允许 `/workspace/plans/` 写草案 | 首期改为受控 save_plan | Markdown checkpoint 为唯一事实源，无 workspace Agent 同样能用；文件导出不属于本期 |

## API 使用依据与待验证项

已查询 LangChain docs/reference MCP，参考 [自定义 Middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)、[interrupt](https://reference.langchain.com/python/langgraph/types/interrupt)。官方 interrupt 会在恢复时从节点开始重执行，必须使用 checkpointer；不能在它之前产生不可幂等副作用，也不能捕获它转成普通 ToolMessage。

本仓 lock 显示 LangChain 1.3.17、DeepAgents 0.7.8、LangGraph 1.2.11、GraphHarbor post43；CONTEXT 中仍有 post42/候选表述，部署现状本轮未核实，不修改版本事实。在线文档可能领先锁定版本，后续 T01 必须用当前锁版本验证 state 隐藏、middleware 顺序、工具 Command 更新与中断恢复，不能依赖文档新参数或猜测执行顺序。

调研结论是针对 Plan Mode 的差距，不是对整个 open-swe 或本仓的质量评级。未执行参考项目测试，也未测量效果、模型执行率或生产性能。
