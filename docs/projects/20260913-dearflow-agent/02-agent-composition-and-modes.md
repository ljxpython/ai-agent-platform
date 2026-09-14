# 02 Agent 装配与执行模式

## 目标

用 Deep Agents 组成一个正式 Agent，承载理解、规划、技能选择、执行、委派与核验；用受控模式组合表达执行策略，避免增加四套工作流。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P1 基础组合／HITL；P2 模式与 Context v2；Ultra 与普通子 Agent 同步交付；独立 child 能力后置。
- **必读前置：** [01 第一轮实施包](01-architecture-and-boundaries.md)；[08 C02／C03／C05 与 F1／F2](08-web-and-platform-contracts.md)。P1 文件执行依赖 [04 基础](04-workspace-sandbox-and-artifacts.md)。
- **输入 → 输出／对接：** 受信身份、模型、工具／文件绑定 → 正式 get_agent、有效模式、标准 interrupt。模式写入前后端共同消费的 C03，不在私有页面另造字段。
- **当前切片／最近证据：** 2026-09-14 规划第二版；业务未实施，无实施验证记录；本文末尾只记录文档调研情况。
- **下一任务：** 按批准阶段先 02/C01 与 C04 的 P1 切片；C02／C03 留 P2。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 1. 能力逐项映射

| 能力点 | 是什么／DeerFlow 源码 | 本项目实现位置与方法 |
|---|---|---|
| 需求理解与任务边界 | `backend/packages/harness/deerflow/agents/lead_agent/prompt.py:apply_prompt_template` | 拟新增 `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py:render_system_prompt`；输入已解析的纯数据，区分用户目标、约束、待核验事实 |
| 主循环 | `backend/packages/harness/deerflow/agents/lead_agent/agent.py:_assemble_lead_agent` 使用 `create_agent` | 拟新增 `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:get_agent`，唯一调用 `create_deep_agent` 组成主 Agent；不用 DeerFlow factory |
| 任务规划 | `backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py:TodoMiddleware` | 按模式显式配置官方 `TodoListMiddleware`；用标准 `todos` 状态，不新增 planner 服务或第二个计划表 |
| 技能选择 | `backend/packages/harness/deerflow/agents/lead_agent/prompt.py:get_skills_prompt_section` | 官方 `skills=`／`SkillsMiddleware`，只展示当前已验收且获准启用的技能；07 定义管理能力 |
| 工具调用 | `backend/packages/harness/deerflow/tools/tools.py:get_available_tools` | 工具在组合根显式装配，官方 `FilesystemMiddleware`＋本服务真实工具＋官方 MCP adapters；03 定义授权 |
| 委派 | `backend/packages/harness/deerflow/tools/builtins/task_tool.py:task_tool` | 官方 `SubAgent`／`CompiledSubAgent` 和独立 Run；05 负责生命周期，主 Agent 对结果负责 |
| 结果核验与交付 | `backend/packages/harness/deerflow/subagents/report_contract.py`、`tools/builtins/present_file_tool.py:present_file_tool`（同 Harness 根） | 工具产生真实证据，主 Agent 检查；文件交付使用 04 的 ArtifactRef；不让模型自行宣告“已保存成功” |
| 人工审批／补充信息 | `backend/packages/harness/deerflow/agents/middlewares/clarification_middleware.py:_handle_clarification` | 标准 `interrupt_on` 或 `langgraph.types.interrupt`＋`Command(resume=...)`；不搬 `goto=END` 与自定义 human_input 事件 |

### 2. 唯一组合根的执行顺序

`get_agent(config)` 依次执行：

1. 校验受信委托，拒绝客户端注入身份、工具实现、连接地址、Backend 和测试开关。
2. 区分 schema 探测与执行。探测返回同结构的不可执行图，不兑换模型连接、不创建目录、不启动容器／MCP。
3. 对完整受支持 Context 做哈希校验；核实 tenant／project／thread／graph；读取服务端能力与策略。
4. 用 `resolve_runtime_config`／`fetch_model_connection`／`build_model` 获取获准的模型与参数；模型配置不从 DeerFlow YAML 读取。
5. 绑定 Backend、Skills、业务工具和子角色，计算实际工具权限交集。
6. `create_deep_agent` 装配官方组件；只加入已识别缺口的服务私有 Middleware。
7. 接入现有 Langfuse；只保留允许的运行配置，checkpointer／Store 的所有权遵守 01。

参考当前 `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py:get_agent`，只借鉴边界，不复制其教学预算、样例初始化或全套内嵌函数。

中间件顺序以实际装配结果测试为准：公共 Runtime 校验与资源 guard → 必要工具调用边界控制；根 Agent 才有 `MessageQueueMiddleware`；官方 Skills／文件／子 Agent／摘要／工具调用修复／HITL 的顺序遵守锁版本。不要假设传入的 `middleware` 就是完整栈，必须核对同名 Middleware 替换行为与反向 after hook。

### 3. 执行模式：建议纳入

DeerFlow 参考：`frontend/src/core/threads/hooks.ts` 在提交时设置 `thinking_enabled`／`is_plan_mode`／`subagent_enabled`；`backend/packages/harness/deerflow/agents/lead_agent/agent.py` 消费这些字段。

| 模式 | 用户可见定位 | 思考／规划／委派基线 | 拟定预算上限，P0 后校准 |
|---|---|---|---|
| Flash | 简短问答和少量工具任务 | 模型支持时关闭扩展思考；无 Todo；禁委派 | 12 次模型调用、24 次工具调用 |
| Standard（默认） | 常规任务与文件处理 | 模型能力允许的默认推理；无强制 Todo；禁委派 | 24／48 |
| Pro | 多步骤研究与交付 | 支持时 medium；Todo；主 Agent 为主，禁委派 | 48／96 |
| Ultra | 有明显并行／专业分工收益的复杂任务 | 支持时 high；Todo；显式允许受控角色 | 根 48／96；每个子任务 24／48；并发 3、单父任务累计 8 |

数字是评审基线，不是性能结果。所有模式还受项目级预算和全局容量限制；不得在工具中通过新 Run 或重新构图重置同一父任务累计预算。模型不支持指定推理方式时返回明确的有效配置和原因；不声称已关闭无法关闭的思考，不盲传 provider 不接受的字段。

模式不授予权限，不修改 Skills 安装状态，不自动更换付费模型。Ultra 也只在任务独立且收益明确时委派；会写同一资源的任务串行或分工作区。

Ultra 当前使用普通同步 `SubAgent`：允许受控并行并由父 Run 汇总，所有子任务跟随父 Run 生命周期。它不提供单个 child 的独立取消、独立恢复或后台持久运行；这些能力依赖 `AsyncSubAgent`／独立 Thread／Run，统一列为 deferred，不能把普通 `task` 宣称为后台任务。

### 4. 模式 Context 与授权版本

现有 `RuntimeContext` 只有 `model_id/temperature/max_tokens/top_p/tools`，不能直接把 DeerFlow 三个布尔字段塞进去。推荐新增一个通用、类型受限的 `execution_mode`；模式到角色／预算的映射留在本服务拟新增 `modes.py:resolve_execution_mode`，公共 Runtime 不包含业务角色表。

拟修改的完整调用链：

- `apps/runtime-service/src/runtime_service/runtime/contracts.py:RuntimeContext`、`resolver.py:parse_runtime_context/runtime_context_hash`、`middlewares/runtime_config.py:RuntimeConfigMiddleware`。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:_runtime_context_snapshot` 及公开参数校验。
- `apps/platform-api/src/platform_api/core/security/tokens.py:empty_runtime_context_hash` 与受信委托生成；目录 schema 和前端运行参数类型同步修改。
- `apps/platform-web/src/modules/dear-agent/components/ExecutionModePicker.vue`（拟新增）承载专属模式交互；`apps/platform-web/src/services/agents/context.ts`／`types.ts` 同步受支持字段，现有 Chat `composables/useChatSession.ts` 负责公共传递与校验。确有两个消费者需要时再扩展 `ChatRunOptionsDialog.vue`，不把 Dear 专属布局写进 Chat。

协议采用显式 `runtime-context/v2` 哈希域；规范化字段、null／缺省、tools 排序由双端共享测试向量校验。旧 checkpoint 不批量改写；进入升级维护窗口后新 Run 统一 v2；恢复已有审批时根据已保存的契约版本读取原配置并重新授权。若存量 Run 缺少可判定版本，升级前排空待运行／待审批，不猜测哈希或静默放宽校验。保存请求版本可复用现有配置快照，是否需新增字段由 P0 确认。

不支持模式的 Graph 只接受缺省，不接受用户自定义 execution_mode。审批 resume 继续禁止覆盖模式、模型、输入和 Context；模式只用于新的普通运行动作。

### 5. 禁委派要落实到实际调用

Deep Agents 默认可能添加 `general-purpose`，`subagents=[]` 不足以关闭。P0 必须验证实例级公开配置方式：若锁版本无法按实例移除默认角色，使用明确的最小权限默认角色＋Runtime 在模型可见列表及工具执行处双重禁止 `task`，并在模式提示词中去掉委派指引。不修改全进程 model profile，不使用私有 `_harness_profile_for_model`，避免并行不同模式互相污染。

### 6. 官方人机交互

#### 6.1 DeerFlow 实际怎样提问

以下源码相对 `../research/deer-flow/`，调研日期 2026-09-14：

| 步骤 | 参考文件／符号 | 实际行为 |
|---|---|---|
| 模型提出问题 | `backend/packages/harness/deerflow/tools/builtins/clarification_tool.py:ask_clarification_tool` | 工具声明 `return_direct=True`，参数含 question、clarification_type、context、options、fields；工具函数主体是占位实现 |
| 阻止混合工具先执行 | `backend/packages/harness/deerflow/agents/middlewares/clarification_middleware.py:_drop_parallel_non_clarification_tools` | `after_model` 检测有效／无效 clarification 调用，移除同批其他工具，并处理 provider content 中对应 tool-use 块 |
| 生成提问卡片数据 | 同文件 `_build_human_input_payload`／`_normalize_fields` | 自由文本、选项使用 v1，表单使用 v2；字段类型为 text／textarea／number／select／multi_select／checkbox／date；校验重复名、危险属性名、长度和数量 |
| 结束本轮 | 同文件 `_handle_clarification` | 创建 `ToolMessage(artifact={"human_input": payload})`，返回 `Command(update={"messages": [...]}, goto=END)`；此处没有调用 `interrupt()`，也没有保存该工具的待返回值 |
| 前端识别／提交 | `frontend/src/core/messages/human-input.ts`；`frontend/src/components/workspace/chats/chat-page.tsx:handleSubmitHumanInput` | 读取请求卡片，回答通过 `sendMessage` 作为新 human 消息提交，附带 `additional_kwargs.human_input_response` 关联问题，部分消息隐藏原始文本展示 |
| 下一轮继续 | `frontend/src/core/threads/hooks.ts` 的 `sendMessage` | 同线程开启后续对话，模型读历史中的问题／答案再决定操作；表单回复在该实现中归纳成可读文本，不等于结构化函数返回值 |

因此，“自定义提问终止协议”准确指 **ToolMessage 中的自定义 UI 数据＋END 结束本轮＋新用户消息继续**。它仍使用官方 Command／消息类型，并不是脱离 LangGraph 的全部自建实现；中间件注释里的“interrupt”描述了用户体验，不能据此认定调用了官方动态中断。

#### 6.2 两种机制的能力与语义对照

| 对比点 | DeerFlow 上述路径 | 官方 interrupt／HITL／resume 路径 |
|---|---|---|
| 提问后控制流 | 转 END，本轮停止 | 动态中断保存待恢复任务；在引擎中可见 interrupted |
| 回答载体 | 新 human 消息＋自定义关联 metadata | `Command(resume=...)`，平台按官方 interrupt ID 传递 |
| 后续执行 | 模型重新读历史继续推理 | 恢复被中断计算，答案成为 `interrupt()` 返回值；HITL 则处理对应 decisions |
| 文本／单选／多选／多字段表单 | 自定义卡片实现 | 可以实现相同体验：JSON payload 描述字段，Vue 渲染；官方不会自动生成表单 |
| 结构化答案 | 当前表单主要提交可读摘要 | 可传 JSON 对象，确定性校验后供工具使用，不必让模型从自然语言反向猜字段 |
| 重启与持久化 | 对话消息持久化，后续一轮读取 | 依赖持久 checkpointer 与相同 thread 恢复；不保存 Python 调用栈 |
| 原执行位置 | 不返回原提问工具继续 | 从中断节点开始重执行；中断前代码可能再次运行，必须无副作用或幂等 |
| Run ID | 回答开启下一轮 | 服务端 resume 也可能创建新的 Run ID；以 thread／checkpoint／interrupt 关联，不承诺原 Run ID 不变 |
| 并行工具安全 | 主动剔除同批其他工具 | 工具内部 interrupt 不会撤销已并行执行的兄弟工具；必须在工具批次执行前检查 |
| 问题关联与过期 | 应用层 request_id／历史配对 | 官方 interrupt ID／namespace＋最新状态检查；UI 草稿可附 fingerprint，不造另一套中断 ID |
| 非交互运行 | 可配置跳过 clarification 并让模型继续 | 必要问题保持 interrupted 待 Web；明确允许的可选假设另走业务规则，不能自动批准副作用 |

结论：用户可见能力可以用官方体系实现。迁移保留提问类型、表单、提示和保护要求，控制流统一为官方机制；不搬 DeerFlow 的 END／新消息恢复路径，也不新增 HumanInputManager 或审批表。

#### 6.3 官方内部也有两种合适用法

| 场景 | 实现基线 | 选择理由 |
|---|---|---|
| 缺参数、需求澄清、方案选择、多字段表单 | `request_information` 工具内调用 `interrupt(payload)`；用户值经 `resume` 返回 | 可返回结构化答案并在业务工具内校验；本项目的推荐提问路径 |
| 删除／写入／付费／部署前批准、编辑、拒绝 | Deep Agents `interrupt_on` 装配官方 `HumanInTheLoopMiddleware` | 官方 action_requests／review_configs／decisions 与现有审批组件吻合 |
| 用户直接代替工具给一个文本结果 | 官方 HITL `allowed_decisions=["respond"]`，返回 `{"type":"respond","message":"..."}` | 锁定本地 LangChain 已支持；跳过真实工具，生成成功 ToolMessage；纯文本问答可采用，但不作为另一条同时上线的提问实现 |

`respond` 并非官方“不支持提问”的缺口；只是它返回 message 文本，对强类型多字段业务仍需额外验证。本项目先选动态 interrupt 作为统一提问路径，工具审批保持现有 approve／edit／reject。确有直接代答工具需求时再单独启用 respond 并补前端支持，不因官方存在就把它开放给所有敏感工具。

敏感工具必须显式配置允许的 decisions，避免 `True` 隐式包含当前 UI 不支持的 respond；未进入 `interrupt_on` 的工具默认不触发官方审批，仍要经过 03 的执行权限与副作用策略。`request_information` 本身不再配置一层 HITL 审批，否则会出现“先批准提问，再回答问题”的重复交互。

#### 6.4 提问与回答契约（拟定 v1）

业务 payload 放在官方 `Interrupt.value` 内；C05 的官方 envelope、interrupt ID／namespace、SDK 和网关运输方式不变。`kind`／字段只描述 UI 和输入契约，不是另一个暂停／恢复协议。

请求示例：

```json
{
  "kind": "clarification",
  "schema_version": 1,
  "question": "请补充这份报告的要求",
  "context": "时间范围和语言会影响检索及输出。",
  "fields": [
    {"name": "period", "label": "时间范围", "type": "select", "required": true,
     "options": [{"value": "month", "label": "最近一个月"}, {"value": "quarter", "label": "最近一个季度"}]},
    {"name": "language", "label": "输出语言", "type": "text", "required": true}
  ]
}
```

回答示例：

```json
{
  "schema_version": 1,
  "status": "answered",
  "values": {"period": "quarter", "language": "中文"}
}
```

统一用 fields 表达单问和多问：自由文本是单个 text 字段，单选是 select，多选是 multi_select。支持原七种字段，日期采用 ISO `YYYY-MM-DD`，number 必须有限值，checkbox 必须 JSON boolean。选项以稳定 value 校验，不能拿可修改 label 当身份；拒绝额外字段、重复字段／选项、原型属性名和错类型。required checkbox 的语义明确为必须勾选，不把 false 当同意。

初始上限沿用经审查的上游预算：16 字段、每字段 24 选项、名称／标签／选项／placeholder 各 200 字符；请求整体不超过 16 KiB；question／context 各最多 2000 字符；回答文本总量最多 8000 字符且 JSON 不超过 16 KiB。前后端与网关共用测试向量；字段 schema 损坏时让模型修正或明确失败，不能删掉必填字段后显示完整表单。

P1 先验 text／select；其余类型在 P2 验收前不暴露给模型。客户端尚不支持的 schema_version／字段类型显示不支持及重连／升级提示，禁止降级成通用“批准”按钮。是否“暂不回答”属于产品选择：本轮可关闭卡片但中断仍在；停止任务走标准 cancel，不能把关闭 UI 等同 resume 或业务成功。

#### 6.5 Runtime 实现位置与核心流程

| 完整目标文件 | 拟新增／修改内容 |
|---|---|
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/human_input.py`（拟新增） | `request_information`、`validate_request`、`validate_answer`；纯校验后调用 interrupt，无外部提交／数据库写入 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/schemas.py`（拟新增） | `ClarificationRequest`、`ClarificationField`、`ClarificationAnswer`；extra 禁止，回答按本次请求动态校验 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware.py`（按需新增） | `ClarificationBatchGuard`：执行前拒绝混合提问批次；通过官方 Middleware hook 实现 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`／`subagents.py`（拟新增） | 显式装配工具、guard、官方 HITL 与角色能力；root／child 都要遵守，不能只保护主 Agent |

核心流程示意，**不是已实现可直接部署代码**；示例中的校验函数和 schema 按本节实现，官方 API 已核对：

```python
from langchain.tools import tool
from langgraph.types import interrupt

@tool
def request_information(question: str, fields: list[dict], context: str = "") -> dict:
    """收集继续当前任务所必需的信息；本轮只调用这个工具。"""
    request = validate_request(question=question, fields=fields, context=context)
    # 这里只允许可重复的纯计算，不提交付费调用或创建外部资源。
    response = interrupt(request.model_dump(mode="json"))
    return validate_answer(request, response).model_dump(mode="json")
```

前端／Platform 在接受 resume 之前也要校验（见 08），Runtime 保留最终业务校验。无效回答不能当成成功 ToolMessage；若预校验被绕过，Runtime 明确停止本次恢复并报告，禁止继续执行依赖错误值的副作用。校验失败重试必须区分“请求尚未提交”与“resume 已受理”，不能无条件循环 interrupt 后重复提交同一个已消费幂等键。

#### 6.6 “先问再做”的批次保护

这项不能仅靠提示词或工具内 interrupt。目标是当前模型新发出的同批操作在澄清之前都不执行；不承诺撤销之前已经运行的独立 child 或远端任务，后者遵守 05／09 取消策略。

1. 工具执行前检查最后一个 AIMessage 的有效与无效工具调用。只有一个合法 `request_information` 且无其他调用才允许进入工具节点。
2. 混合批次、多个提问调用或提问参数损坏：阻止整个批次执行，请模型重发一个合法提问（多问题合成 fields）。不要回答后自动继续先前准备的 bash／付费参数，它们可能因答案而失效。
3. 对可解析且 ID 完整的调用，优先保留原 AIMessage，用每个 tool_call_id 对应的 `ToolMessage(status="error")` 明确“本批未执行，请先澄清”，通过官方 `after_model`＋`hook_config(can_jump_to=["model"])` 返回 `jump_to="model"`。无需搬 DeerFlow 的 provider-specific content 删除器。sync／async hook 行为一致。
4. 缺失／重复 ID 或 provider 的 invalid_tool_calls 无法合法补齐消息时，不能伪造 ID 继续执行；在模型响应边界做有界修正或明确失败，保留协议证据。最多两次修正（计入预算），耗尽后输出失败原因；不绕回工具执行。
5. guard 必须早于官方 HITL after_model 的审批和工具执行。Deep Agents 会自动装配 Middleware，实际顺序取决于锁版本；P0 记录节点／hook 顺序并验证两种调用路径。无法证明时阻塞本项，不能假设传入数组顺序等于执行顺序。

与副作用授权保持分工：guard 只解决“提问混批”，HITL 负责具体工具批准，03 的工具权限负责用户是否有权调用。即使用户明确回答“可以”，也不会自动变成后续任意工具的批准。

#### 6.7 持久恢复、取消和多中断

- 使用已验证的持久 checkpointer 和同一个 thread；动态 interrupt 不是 sleep，不占 worker 等待用户，也不需要自建问题等待表。
- 本平台恢复可创建新的 Run，必须继承原受信配置并保留 parent_run_id；日志按原／恢复 Run 与 interrupt 关联，费用按真实调用计量。
- 多 interrupt 按官方 ID 映射，批量审批内部 decisions 保持 action_requests 原顺序；同名工具／同名 child 不能按名称配回答。
- 提问前只能有纯校验与数据组装；文件写入、付费提交、发消息等副作用移到回答验证之后，并仍做幂等。部署期间不任意调整已有节点中 interrupt 的调用顺序；旧中断协议兼容或按 02 的升级策略排空。
- 关闭页面、断网、重启都不等于拒绝或取消；重新读取引擎的 pending interrupts。取消后不再允许旧答案恢复，权限撤销后也必须拒绝。
- 不把一次性回答直接写长期记忆；bootstrap 等明确保存偏好的任务另走 06 的确认／持久化流程。
- 独立 child 有自己的 thread／Run／委托；父页先校验归属，再从对应 child 官方中断流答复，不能将 child ID 塞进根 resume map。

#### 6.8 官方依据与本地差距

2026-09-14 已通过 LangChain Docs／Reference MCP 核对，并读取本地安装的 `langchain/agents/middleware/human_in_the_loop.py`：

- [interrupt API](https://reference.langchain.com/python/langgraph/types/interrupt)：需要 checkpointer，恢复会重执行节点。
- [HumanInTheLoopMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop/HumanInTheLoopMiddleware)：允许 decisions 与 respond 语义。
- [hook_config](https://reference.langchain.com/python/langchain/agents/middleware/types/hook_config)／[官方 Middleware 跳转](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps)：公开的模型重试／工具前检查入口。

当前 Web `approvals.ts:parseReviews` 只处理 action_requests／review_configs；`useChatSession.ts:approve` 只构建 approve／edit／reject，然后 `stream.respondAll`。普通动态提问会被当作 unsupported review。因此“SDK 支持 interrupt”不等于“现有产品已支持表单”；08 必须完成类型识别、卡片、共用 resume 执行和所有 pending 中断的发送门禁。

## 任务拆分

- [ ] C01：实现 `get_agent`、纯提示词和不可执行探测图；拟新增测试 `tests/services/dearflow_agent/test_agent.py`。
- [ ] C02：实现 `modes.py` 与预算解析，双重委派 guard；拟新增 `test_modes.py`，覆盖并行不同模式互不污染。
- [ ] C03：完成 Context v2 双端签发／验证／恢复与 Web 参数，新增测试向量，覆盖每一个哈希调用者。
- [ ] C04：官方人机交互完整交付，按以下切片执行，全部通过才能勾选。
  - [ ] C04-a／P0：确认官方动态 interrupt、HITL／respond、guard 顺序、重复中断 ID 与现有 resume 幂等；形成锁版本证据。
  - [ ] C04-b／P1：`human_input.py`／schemas、text／select、工具审批、混批执行前保护；对接 08/W05 的预校验与统一恢复、F1 卡片。
  - [ ] C04-c／P2：全部七种字段、多字段校验、畸形请求修正／预算、前端表单和未知版本处理。
  - [ ] C04-d：根／普通子图的中断归属和多 ID；独立 child 中断、单任务取消及授权续期 deferred。
  - [ ] C04-e／P7：重启、双窗口回答竞态、超时未知、旧协议升级／排空、无重复副作用联合验收。
- [ ] C05：记录装配快照中的有效模型、模式、prompt／skills／policy 哈希；日志不含正文或凭据。

## 验证要求与记录

- [ ] 四模式工具可见性、执行权限、预算上限、模型不支持思考参数的明确行为。
- [ ] Context 任意字段篡改被拒绝；旧审批升级恢复或安全排空路径可复现。
- [ ] 未授权模式／工具／角色、伪造调用、默认 general-purpose 绕过均被拒绝。
- [ ] 中间件顺序、根消息队列只消费一次、探测不触发外部资源。
- [ ] 审批多 action、多 interrupt、拒绝／编辑／重复／过期／越项目，以及重启恢复。
- [ ] 单独提问无副作用，`request_information + execute`、多个提问、invalid_tool_calls 等组合均在执行前阻断；回答后由模型重新形成工具参数。
- [ ] 七种字段／必填／额外字段／类型／上限／危险名称均有确定性正负样例，答案不能提升工具或模型权限。
- [ ] 当前 Web 中非审批 interrupt 可渲染／答复，所有 pending interrupt 都阻止普通发送；未知类型不能误判为“无待处理”。
- [ ] 多窗口同 ID 相同答案重试、不同答案冲突、合法新一轮中断 ID 复用风险都有真实引擎＋网关证据；不靠新生成 request_id 冒充官方关联。
- [ ] 拟新增 `apps/runtime-service/tests/services/dearflow_agent/test_human_input.py`／`test_clarification_batch_guard.py`，以及 `apps/runtime-service/tests/durable/test_dearflow_human_input.py`；测试体包含真实重启和混批工具计数为零的断言。
- 2026-09-13：仅完成设计；上述测试未执行。
- 2026-09-14：补充 DeerFlow／官方机制对比、请求／回答样例、实现位置、批次保护和 C04-a—e；官方 API 与本地源码已核对，方案代码未实施、功能测试未执行。

## 状态

规划中；D1 待评审，依赖 01 的 S0／S1，完整交互依赖 08。
