# F02 前端交接：重复工具调用提示与诊断

> 2026-10-09，实现版交接已冻结。Runtime/API及非前端验收完成；以下样例取自隔离真实HTTP/ProductionWorker链路，不代表已部署现役。唯一剩余任务T07前端/浏览器由同事实施。
> 方案、任务和后端门禁见 [15 F02专题](15-f02-loop-detection.md)；本篇只维护前端交接细节，不建立第二份任务状态机。

## 目标

前端由用户同事完成。复用现有 Chat/预算状态条/RunDiagnostics，显示后端提供的重复调用提醒与停止原因。Dear入口继续复用Chat；不用模型消息、工具名出现次数或文本重复自行判断死循环。

前端接入基线：Python 3.13.9、DeepAgents 0.7.8、LangChain 1.3.17、langchain-core 1.6.0、LangGraph 1.2.11、GraphHarbor双包0.13.0.post43。Runtime部署开关 `AGENT_LOOP_DETECTION_ENABLED=0` 默认关闭，仅接受0/1。DearFlow/Showcase主子图和Reference已接入；Workflow未接入。只监测本图声明的 `ls/read_file/glob/grep/read_reference` 交集。前端只扩展现有消费与展示，不承担开启策略。

本轮交接与上线分开：后端独立验收以15/T06、T08为准；前端完成F01-F07及真实浏览器联合后才满足F02整体验收。未发布或重启现役服务。

## 方案设计

### 1. 展示范围和复用位置

| 代码位置（从仓库根起） | 同事需要补什么 |
| --- | --- |
| `apps/platform-web/src/modules/chat/budget/types.ts` | 现有通知code加入 `tool_loop_approaching/tool_loop_reached`；增加unit `tool_rounds`，只能与run组合；`BUDGET_SAFETY_ERROR_CODES` 增加 `"runtime.loop.detected"`（注意点号支持）；Schema 使用正整数校验（limit/used/remaining），不把当前5/3/2硬编码到类型层 |
| `apps/platform-web/src/modules/chat/budget/view-model.ts` | 固定中文文案和一致性校验（`used + remaining === limit`）；hard错误精确映射 `runtime.loop.detected`，严禁全文 `text.includes` 模糊猜测；`tool_loop_reached` 在 Run 运行中保持警告态，仅在原生终态确认后翻转为 terminal error |
| `apps/platform-web/src/modules/chat/composables/useRunBudget.ts` | 复用当前custom消费、notice_id去重和Run/namespace隔离；支持子任务（Subagent）通知向主会话（根namespace）受控冒泡感知，切换至子视图时严格精准匹配；旧通知code行为不变 |
| `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue` | 复用现有budget展示；在 `formatError` 中精确拦截 `runtime.loop.detected` 机器码，统一输出标准中文兜底，避免历史刷新或降级时裸露英文；支持呈现子任务标签 |
| `apps/platform-web/src/modules/chat/diagnostics/types.ts` | Zod可选 `loop_detections`、缺省[]，使用正整数校验 `repetitions/threshold`（当前基准期望3/3与5/5），限制长度/枚举/ASCII标识；strip未知字段 |
| `apps/platform-web/src/modules/chat/diagnostics/view-model.ts` | 增加loop摘要和graph错误label；精确映射 `runtime.loop.detected`；不要用 `getModelErrorCodeLabel` 把循环标成模型服务异常 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunLoopDetectionsSection.vue`（新增） | 独立子组件，参考 `RunPreparationsSection` 模式封装循环保护记录卡片 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue` | 挂载 `RunLoopDetectionsSection`；遵循 `v-if="data.loop_detections?.length > 0"`，无记录时彻底隐藏，绝不显示空卡片或空边框 |
| `apps/platform-web/src/services/threads/diagnostics.service.ts`、`useRunDiagnostics.ts` | 继续复用GET、AbortSignal、thread/run精确校验和epoch隔离；若DTO扩展不需要改请求，不新增service |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue` | 验证同一Chat组件投影；不复制算法、网络层或状态机 |

### 2. 实时通知（实现契约）

使用现有 `custom` channel 与 `runtime_budget_notice`。v3保持官方SDK channel/原envelope及namespace；v2仍为既有custom payload。不要增加loop专用订阅或直接连接Runtime。

```json
{
  "version": 1,
  "type": "runtime_budget_notice",
  "notice_id": "budget:7e44f65c-d148-48fe-b717-69724f4f4554:c35952af634e6aafbfe2:run:tool_loop_approaching",
  "run_id": "7e44f65c-d148-48fe-b717-69724f4f4554",
  "scope": "primary",
  "budget_scope": "run",
  "code": "tool_loop_approaching",
  "limit": 5,
  "used": 3,
  "remaining": 2,
  "unit": "tool_rounds"
}
```

同次运行的reached对应 `code=tool_loop_reached/used=5/remaining=0`，notice_id末段为 `tool_loop_reached`。这里的ID是实际隔离运行抓取值，前端不能自行拼接。`used` 是连续完整重复工具批次数，不能展示成5次总工具调用、全线程配额或剩余钱数。

完整诊断及主/子抓包摘录已落到 [f02-http-samples.json](evidence/f02-http-samples.json)。`primary_diagnostics` 是实际v1完整根对象；`transport_samples` 包含v3/v2和同角色并行子任务的受控样例。样例只来自一次隔离环境，不依赖其Run ID拼接业务逻辑。

实际v3 SSE片段（原event/id及外层保持不变）：

```text
event: custom
id: 280
data: {"method":"custom","params":{"namespace":[],"data":{"version":1,"type":"runtime_budget_notice","notice_id":"budget:7e44f65c-d148-48fe-b717-69724f4f4554:c35952af634e6aafbfe2:run:tool_loop_approaching","run_id":"7e44f65c-d148-48fe-b717-69724f4f4554","scope":"primary","budget_scope":"run","code":"tool_loop_approaching","limit":5,"used":3,"remaining":2,"unit":"tool_rounds"}}}

event: custom
id: 427
data: {"method":"custom","params":{"namespace":[],"data":{"version":1,"type":"runtime_budget_notice","notice_id":"budget:7e44f65c-d148-48fe-b717-69724f4f4554:c35952af634e6aafbfe2:run:tool_loop_reached","run_id":"7e44f65c-d148-48fe-b717-69724f4f4554","scope":"primary","budget_scope":"run","code":"tool_loop_reached","limit":5,"used":5,"remaining":0,"unit":"tool_rounds"}}}
```

实际显式v2运行的custom直接携带payload：

```text
event: custom
id: 280
data: {"version":1,"type":"runtime_budget_notice","notice_id":"budget:50944ddc-064e-4344-bba4-c4dcad683fad:53fdc052dac120de40d5:run:tool_loop_approaching","run_id":"50944ddc-064e-4344-bba4-c4dcad683fad","scope":"primary","budget_scope":"run","code":"tool_loop_approaching","limit":5,"used":3,"remaining":2,"unit":"tool_rounds"}

event: custom
id: 427
data: {"version":1,"type":"runtime_budget_notice","notice_id":"budget:50944ddc-064e-4344-bba4-c4dcad683fad:53fdc052dac120de40d5:run:tool_loop_reached","run_id":"50944ddc-064e-4344-bba4-c4dcad683fad","scope":"primary","budget_scope":"run","code":"tool_loop_reached","limit":5,"used":5,"remaining":0,"unit":"tool_rounds"}
```

**Schema 与业务校验分层规范**：
- 当前Web的 `BudgetNoticeSchema` 按 unit 做 discriminatedUnion。增加 `tool_rounds` 分支：
  - `code: z.enum(["tool_loop_approaching", "tool_loop_reached"])`
  - `budget_scope: z.literal("run")`
  - `unit: z.literal("tool_rounds")`
  - 数值类型约束使用健壮的整数验证：`limit: z.number().int().positive()`, `used: z.number().int().nonnegative()`, `remaining: z.number().int().nonnegative()`。
  - **切勿在底层 Schema 中将 limit/used/remaining 硬编码为 literal 5/3/2 或 5/5/0**，避免后续后端调整阈值或支持动态配置时导致 Zod 解析失败吞掉合法通知。
  - 数值一致性在 view-model 层面断言校验（例如 `used + remaining === limit`），且当前后端基准实现固定下发 5/3/2 与 5/5/0。

**时序与子任务展示规则表**：

| 来源 | 建议文案 | UI和状态规则 |
| --- | --- | --- |
| approaching (主任务) | 检测到重复工具调用，正在提醒智能体收尾 | 沿现有 warning/Amber 样式；`isTerminal: false`；不是已经停止，仍保留原取消操作 |
| reached (主任务) | 重复工具调用已达到保护阈值，正在等待终止 | 原生 Run 终态确认前，只表示触限警告（Amber，`isTerminal: false`）；不提前改写终态，不自动调用 cancel |
| approaching (子任务) | 子任务 [{namespace}] 正在提醒收尾（检测到重复工具调用） | 主会话允许受控冒泡子任务预警；展示 scope/namespace，保持 warning/Amber 样式 |
| reached (子任务) | 子任务 [{namespace}] 重复工具调用达到保护阈值 | 原生 Run 终态前保持警告；首期子图触限会传播导致父 Run 失败，按最终原生状态呈现 |
| 精确 hard 错误 | 检测到工具重复调用，本次运行已停止，请调整任务后继续。 | 必须等待原生 Run 失败（status: error）且确认机器码 `runtime.loop.detected`，置为 `isTerminal: true`（Red 错误态）；不要标已完成、已取消或超时 |
| 提醒后 Run 自然 success | 运行中曾触发重复调用提醒 | 诊断面板保留轻量警示记录；不把成功变失败，也不推断业务验收通过 |

### 3. 错误与诊断（实现契约）

安全hard错误码 `runtime.loop.detected`，内部异常类型是 `RuntimeExecutionError`。公开对象/字符串形状沿现有错误槽位，不修改SSE envelope；前端只读精确machine code，不从“repeating/loop/循环”等正文猜原因。它不是HTTP403或用户会话错误，不登出、不刷新权限、不清登录状态。

实际v3失败生命周期帧：

```text
event: lifecycle
id: 429
data: {"method":"lifecycle","params":{"namespace":[],"data":{"event":"failed","status":"error","reason":"business_error","error":{"code":"runtime.loop.detected","message":"检测到工具重复调用，本次运行已停止，请调整任务后继续。","type":"RuntimeExecutionError"}}}}
```

字符串槽位仅完整 `runtime.loop.detected` 作为已分类码；前后缀/类型名加正文不得归因loop。此规则有出口契约测试；不能把上述对象帧改写成字符串样例并声称是抓包。

现有接口继续：

```text
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
x-project-id: 当前项目ID
```

在现有v1根对象中增加可选字段：

```json
{
  "loop_detections": [
    {
      "observation_id": "edaf15645c334b9e8431dad277cce2da",
      "scope": "primary",
      "namespace": [],
      "code": "tool_loop_approaching",
      "repetitions": 3,
      "threshold": 3
    },
    {
      "observation_id": "a8b5ce0921ae40b9890bd85ae77f7bc4",
      "scope": "primary",
      "namespace": [],
      "code": "tool_loop_reached",
      "repetitions": 5,
      "threshold": 5
    }
  ]
}
```

此片段是上述v3运行的真实诊断摘录，完整DTO还包含既有根字段。数组缺省[]、max20；单项标识max128且ASCII合法字符，namespace最多8段；scope为primary/subagent；code只接受两个码；repetitions/threshold在 Schema 层面约束为严格正整数（`z.number().int().positive()`），当前后端基准组合 approaching 为 3/3、reached 为 5/5。未知字段剥离，非法/不符合格式的数据由 Zod 拦截。旧v1没有本字段时仍可正常解析（缺省为 `[]`）。

graph_executions.error_code可返回 `runtime.loop.detected`；model_errors只用于provider/model失败。没有工具参数、结果摘要、调用/结果hash、命令、私有state或宿主路径，前端不能补这些字段。诊断availability/truncated沿既有逻辑；空数组、disabled或unavailable不代表“未发生循环”。

**工业级报错文本降级兜底策略（Fallback Strategy）**：
1. **三路错误源统一收敛**：
   - 实时流：通过 `safeExtractBudgetSafetyError` 精确识别 `code === "runtime.loop.detected"`，生成终态 BudgetViewModel。
   - 异步诊断兜底：当页面刷新或断流重连，实时 notice 缓存为空，但原生 Run 处于 `error` 状态时，若异步 `useRunDiagnostics` 返回 `graph_executions[].error_code === "runtime.loop.detected"` 或 `loop_detections` 包含 `tool_loop_reached`，前端自动恢复终态 BudgetViewModel（`isTerminal: true`, `level: "error"`）。
   - 状态条保底映射：在 `ChatAgentStatusBar.vue` 的 `formatError` 中精确拦截 `runtime.loop.detected`（支持 `raw === "runtime.loop.detected"` 或包含 `RuntimeExecutionError("runtime.loop.detected")` 等特征），统一映射为中文文案：“检测到工具重复调用，本次运行已停止，请调整任务后继续。”，彻底杜绝给用户暴露生硬英文机器码。
2. **严禁模糊匹配单词**：
   - 严禁对任意字符串使用 `text.includes("loop")` 或 `text.includes("repeating")` 模糊判定，防止工具输出或无关日志包含该单词导致假阳性误停。
3. **未知原因保守降级**：
   - 若 Run 状态为 `error`，但诊断未启用、接口超时或未采集到精确循环机器码，显示安全泛化失败（“执行失败，请查看日志或重试”），绝不臆造“因工具循环而停止”。

### 4. 恢复和边界

- custom是已观察事件，不是终态ACK。复用SDK生命周期/Run查询，不能收到reached就主动调用cancel。
- 子任务（Namespace）通知策略：主会话监听（根 namespace）允许受控冒泡同 Run 的子图循环预警；当用户显式切换至子任务视图时，严格根据其 namespace 隔离过滤。
- 旧事件/410恢复沿既有路径。只有目标匹配的诊断或可重放错误可以解释旧Run；不能把最新Thread.error归给历史Run，也不能假定Run GET有error。
- 同Thread不同Run、同角色不同子任务、切项目/Thread时按现有epoch清理和去重；不要增加全局loop store。重复序列ID由后端区分，前端不能用“每Run仅一条”吞掉后续序列提醒。
- 未取得精确原因时展示安全泛化失败/暂无诊断，不编造“因为循环停止”。无记录时不占空白页面区域。
- 保留用户已收到的消息和工具记录。失败后允许用户调整任务再发送；不自动原样重试、不自动生成总结或绕过HITL。
- 保护停止不是用户Stop回执，不能制造StopReport、自动打开取消报告或承诺所有远程资源已取消。
- 首期只管5种已知观察工具的连续重复；高频但参数/结果推进、合法轮询、写入和execute不按本通知解释。
- 默认部署关闭。前端不新增阈值、工具override或开关管理页面；没有后端功能时保持既有UI。

## 任务拆分

状态统一回填 [15/F02-T07](15-f02-loop-detection.md)，下表是该任务的前端验收范围编号，不另维护重复进度。

| 编号 | 内容 | 最小验收 |
| --- | --- | --- |
| F01 | budget DTO/组合/纯view-model扩展 | 两个code/单位正常；正整数与一致性校验；bool/小数/Infinity/非法scope拒绝，旧通知不变 |
| F02 | SDK实时投影与状态条 | 提醒不假终止；reached在Run运行中保持警告态，终态确认后翻转；子任务冒泡感知与namespace隔离；按notice/run去重 |
| F03 | diagnostics DTO与展示 | 新字段可选、旧v1正常；独立 `RunLoopDetectionsSection`，无记录彻底隐藏（不留空卡片）；graph错误和model错误区分 |
| F04 | 精确hard错误中文与历史恢复 | 固定code精确映射，状态条 `formatError` 兜底；普通文本不冒充loop；刷新后通过诊断回查恢复终态，未知原因不猜 |
| F05 | 跨目标与生命周期回归 | 同角色子任务隔离，切换迟到响应丢弃，审批/取消/新请求正常 |
| F06 | 界面质量 | 1440/768/390，明暗模式，无重叠、无跳动，键盘/屏幕阅读器语义沿现有控件 |
| F07 | 真实三服务联合 | 后端受控循环、正常分页、子停止、断流/刷新，截图与network/Run证据归档 |

## 验证要求与记录

### 同事需要执行

扩展既有 `budget/view-model.spec.ts`、`useRunBudget.spec.ts`、`diagnostics/view-model.spec.ts`、`RunDiagnostics.spec.ts`、`diagnostics.service.spec.ts`；新增DTO边界断言与必要组件测试即可。按当前package scripts运行Vitest、vue-tsc、lint和build，不新加测试框架。

真实浏览器场景对应15/E01-E04：稳定重复提醒->失败->诊断；合法分页/变化正常结束；父子/审批/取消/重连/切项目；旧v1/观测关闭/事件过期/未知字段。mock可用于渲染与竞态单测，不能当最终端到端证据。后端提供受控provider的真实HTTP/Worker环境，另做真实模型正常任务烟测；不要依赖随机模型必定进入循环。

### 后端交付给同事的最小材料

1. 实际运行版本、默认开关和开启条件；确认哪些graph/只读工具已接入。
2. 真正抓取并脱敏的approaching/reached v2/v3帧、hard错误对象/字符串、完整v1诊断与旧响应样例。
3. 契约机器码/枚举/bounds最终值；当前基准实现中，repetitions/threshold固定下发3/3或5/5，不产生4/3等组合。前端Schema按通用正整数规范约束，业务层做合法组合断言。修改契约时同步15，不能前后端各自发明字段。
4. 可复现隔离环境入口、合成测试账号/项目和受控场景操作方法，见下节；真实凭据通过既有安全渠道提供。
5. 主/子停止与Worker不重排、正常分页/审批/取消/恢复证据，事件不可用时的降级样例。

### 隔离联调入口

前置：Runtime/API依赖已按当前锁安装，本机有 `initdb/postgres/redis-server`；`RUNTIME_TEST_PYTHON`、`API_TEST_PYTHON` 指向对应已安装依赖的解释器。命令在仓库根执行，所有数据库、账号、Worker和文件都由夹具创建在临时目录，端口随机。可用同一个已具备两服务依赖的解释器。不需要现役服务或真实模型密钥。

```bash
TOOL_ERROR_PLATFORM_TEST=1 \
PYTHONPATH="$PWD:$PWD/apps/platform-api/src" \
PLATFORM_API_TEST_PYTHON="$API_TEST_PYTHON" \
"$RUNTIME_TEST_PYTHON" -m pytest -q -s --trace -p no:cacheprovider \
  "apps/runtime-service/tests/integration/test_loop_detection_worker.py::test_http_loop_boundaries_takeover_security_and_rollback[boundaries-stack0]"
```

等待出现 `(Pdb)`，此时夹具已经启动，测试正文还未执行。停在这里保持联调环境存活；用下面的调试命令取得API地址、临时项目和模型ID，避免输出ready.json中的token：

```python
p {"api": "http://127.0.0.1:" + str(stack[1]["platform_port"]), "project_id": stack[1]["project"], "model_id": stack[1]["model"]}
```

另一终端将 `VITE_DEV_PROXY_TARGET` 设为刚取得的API地址，再启动Web；端口被占用时换一个：

```bash
VITE_DEV_PROXY_TARGET="http://127.0.0.1:<实际API端口>" \
  pnpm --dir "apps/platform-web" dev --host 127.0.0.1 --port 3010
```

浏览器登录夹具内置合成账号 `tool-error-test` / `synthetic-test-password`，选择临时项目、DearFlow或Showcase Agent及 `fixture` 模型。这些是仓库已有的测试数据，不是现役账号；实际登录接口 `/api/identity/session` 已实测成功。以普通模式开启新会话，每个场景新建Thread，发送下面的精确文本：

| 输入 | 预期行为 |
| --- | --- |
| `f02-loop` | 连续五轮，第三轮提醒，第五轮后error；诊断3/5两条 |
| `f02-warn-finish` | 第三轮提醒，随后正常success；诊断只保留approaching |
| `f02-pages` | 六轮不同offset读取后success，无循环诊断 |
| `f02-changing` | 同路径内容变化，六轮后success，无循环诊断 |
| `f02-parent` | 只读子任务循环触限，父Run最终error，诊断scope=subagent |
| `f02-parallel` | 两个同角色子任务分别提醒后success，namespace和notice_id各自隔离 |
| `f02-approval` | 写入先挂起，批准/编辑/拒绝后恢复；拒绝不产生文件 |

控制provider按实际请求里的最近用户文本和ToolMessages响应。设置精确输入即可稳定复现，不依赖随机模型生成循环；网络层、模型协议、Runtime图、Worker、PG checkpoint和API鉴权仍使用真实链路。分页默认夹具只有一行，会返回真实越界ToolMessage并正常结束；这可验证不同offset不误停，页面验收要核对成功分页时，应先经现有文件上传入口提供多行文件再使用正常模型。后端独立真实模型节点已预置8行并严格检查每页成功，不能把provider的固定终答当任务质量证明。不要在这个环境执行生产任务。`f02-cancel/f02-inbox/f02-crash` 另有自动释放/故障控制，应由自动recovery节点验证，不作为页面任意输入。

联调结束在 `(Pdb)` 输入 `q`，由pytest清理其创建的进程；Web终端按Ctrl-C。若在暂停期间手动运行了场景，不再输入 `c`执行整组测试，因为provider记录已变化；退出码2表示主动结束调试环境，不算自动测试通过。完整自动验证去掉 `--trace`；恢复组使用同一函数的精确 `[recovery-stack0]` 节点。不要用 `-k boundaries`，函数名本身含boundaries，会同时选择两组。

真实模型烟测为独立 `[real-model-stack0]` 节点，只有设置 `LOOP_MODEL_ENV_FILE` 才运行，否则明确skip；它从Runtime现有DeepSeek代理配置只读加载连接，并在隔离模型目录中加密保存，不输出密钥。未加这个变量的联调环境只使用合成provider。后端已实测 `--trace` 暂停后服务存活、参数输出和退出清理；Web连接、页面渲染及浏览器测试仍需同事执行。

### 本轮记录

2026-10-09 Runtime/API及非前端验收完成：共享33项、Runtime定向35项、API88项/168子测试；24个受控HTTP Run和3个有效真实模型Run、PG摘要、Worker接管/回退/安全有实证。真实模型独立节点1 passed、96.03s，成功分页与两次同结果复读均无误停，未写文件；三根稳定故障及v2均五轮后error、3/5两条诊断、claims=1。详情与限制见15及 [验证摘要](evidence/f02-verification-summary.json)。前端代码、Vitest、typecheck、lint、build和浏览器未执行。

## 状态

前端待同事实施F01-F07，真实联合验收结果回填15/T07及其Phase记录。后端非前端范围done，整体partial，仅T07未完成；不得把交接完成记作前端功能完成。默认关闭，未部署。
