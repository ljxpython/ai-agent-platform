# A/B 非 Docker 兼容：前端增量交接

**日期：** 2026-10-10。**状态：** AB01-AB03 与 ABF01-ABF03 已完成并通过独立验证。本轮前端增量已实施；既有后台任务界面的 F01-F11 保持通过。B01 已由 post45 正式接受回执专项解除，F12 全栈 Final 仍由 T10 收口。

## 1. 在哪里继续

- **代码 Worktree：** 用户指定的 99f7 平台 Worktree。环境根路径以本目录 `.local-stack/environment.json` 登记为准，在该目录继续。
- **核心需求：** [兼容 RFC](local-runner-compatibility-proposal.md)、[批准后的方案 4.3](plan.md#43-非-docker-兼容与精确降级后端已实施前端接续)。RFC 下方 A/B/C 是原候选讨论；当前以方案 4.3 和本交接为准。
- **后端改动：** [实施记录](implementation/05-local-background-compatibility.md)。**任务与证据：** [tasks.md](tasks.md)、[verification.md 的 Phase A/B](verification.md#phase-ab-非-docker-兼容独立验收2026-10-10)。
- **既有 DTO/权限/日志/Stop/完成通知规范：** [原前端交接](frontend-handoff.md)，继续沿用现有实现。

该 Worktree 同时有引擎使用方接线改动。A/B 不包含新接受回执的 U01-U03；post45 依赖、迁移和 B01 解除由接受回执专项记录。保留其他开发者改动，按文件和 diff 核对归属，不整体回退、覆盖或打包提交。

## 2. 后端已经完成什么

1. 统一查询与启动能力判断，Showcase/DearFlow 复用。local、启动开关关闭、无有效 host 或无任务存储配置时，模型看不到 `background_execute`。
2. ToolNode 内部保留启动入口供旧 checkpoint 重放。先按可信 key 查原任务，再用原 host 核对摘要；原 running/unknown/终态返回原回执，改变命令/超时/绑定仍冲突。
3. 只有数据库成功确认没有原任务、且源 Run 未被 Stop 拒绝时，预期环境限制才返回 `outcome=not_started` 与短任务恢复建议。其他权限/审批/Stop/取消/存储/程序异常保持原语义。
4. 普通 `execute` 仍默认 30 秒、最大 60 秒并要求原授权和审批；Docker 故障不会自动切宿主 shell；本轮没有 LocalBackgroundRunner。

后端直接证据：Runtime 定向 **91 passed**、真实 PG **12 passed**、Platform 能力 **2 passed**；既有 Web 三文件 **11 passed**。两个图在真实隔离栈使用 `deepseek-v4-flash`，经 Platform API→Runtime API/Worker→一次 HITL 审批→普通 execute，均得到 `AB_LOCAL_OK`/退出码0和 Run `success`，没有后台任务。此证据覆盖后端，浏览器新增用例尚未通过。

## 3. ABF01：正确消费查询与启动能力

继续调用 `GET /api/langgraph/threads/{thread_id}/capabilities`，带当前 `x-project-id`；Platform 已结合当前 ACL/tool policy 投影，前端不用再判断 Docker 或环境变量。

下表针对已经接入的两图且具备相应授权的情况；权限可能进一步关闭新启动或具体操作。

| Runtime 配置 | `background_tasks` | `background_tasks_start_enabled` | 前端行为 |
|---|---|---|---|
| 有任务存储 + docker + flag1 + 有效 host | true | true | 保留任务 Tab，沿用当前能力 |
| 有任务存储 + local | true | false | 保留任务 Tab、历史/已有任务、日志与授权取消 |
| 有任务存储 + docker + flag0，或无有效 host | true | false | 同上，不能用启动能力隐藏任务入口 |
| 无任务存储，或本图未接入后台任务 | false | false | 隐藏任务入口，停止任务探针并清理旧作用域数据 |
| 字段缺省 | 按 false | 按 false | 不猜测支持，不残留上一会话的任务 |

能力是配置与权限声明，不代表实时探测成功。查询能力为 true 时真实 API 失败继续沿用现有局部错误处理；502/504 不当撤权，不退出登录。

**已有代码与需要核对的位置：**

- `apps/platform-web/src/components/workspace/WorkspacePanel.vue` 已按 `capabilities?.background_tasks` 显示 Tab，保留这条规则。
- `src/types/workspace.ts` 已有两个可选字段，不需要新 DTO 或启动表单。
- `src/modules/chat/components/ChatSession.vue` 装配 `useBackgroundTasks`；`src/modules/chat/composables/useBackgroundTasks.ts` 当前只按 project/thread 变化立即请求，没有消费查询能力。补齐 query=false/缺省时不请求、不轮询、取消在途请求及清理旧作用域；不能仅隐藏 Tab 而在后台继续探测不支持接口。
- `src/services/threads/background-tasks.service.ts`、`BackgroundTasksPanel.vue`、`BackgroundTaskItem.vue`、`BackgroundTaskLogViewer.vue` 复用现有接口和组件。日志/取消仍看 `allowed_actions`，不从 start 位推导权限。

**验收：** Vitest 覆盖 true/false、true/true、false/false、字段缺省、能力变化/切会话/卸载；query=false 零任务请求，query=true/start=false 能正常查询、查看日志和授权取消。保留单飞、二次确认和未确认清理状态。

## 4. ABF02：消费 B 的局部恢复提示

这是原工具错误格式的加法值，出现在 `background_execute` 的 ToolMessage 中；不是新的 HTTP 错误接口，也不是 Run Fatal。

```json
{
  "status": "error",
  "code": "background_task_not_supported",
  "error": "当前环境不支持后台执行，本次调用未登记任务。短任务可改用 execute（默认30秒、最大60秒）；长任务请拆分或选择支持后台执行的环境。",
  "error_type": "BackgroundTaskNotStarted",
  "name": "background_execute",
  "recovery": "use_execute_for_short_task",
  "outcome": "not_started"
}
```

关闭新启动开关对应 `code=background_task_disabled`，格式相同；具体 error 文案由后端提供。无存储配置、数据库读失败或已有 unknown 时，后端不会给出上述“确定未启动”的建议。

**最小前端改动：** `src/modules/chat/transcript.ts::parseToolErrorSummary()` 已能解析该结构，`RECOVERY_HINT_MAP` 尚无 `use_execute_for_short_task`。补一个中文提示（如“短任务可改用前台执行，最长60秒”）及 `transcript.test.ts` 回归，复用 `components/ToolResult.vue` 的局部恢复徽章。

**验收：** 展示后端安全摘要和恢复提示，后续 Agent 回复正常；不因这一 ToolMessage 显示整轮崩溃红条。不自动 execute、approve/resume、创建完成 Run 或将工具结果伪造成用户消息。unknown/已登记结果不得出现“重新执行”建议；长任务保留拆分/受支持环境的提示，不承诺同步执行能完成它。

## 5. ABF03：真实浏览器验收与现有草稿

交接草稿在 `apps/platform-web/e2e/background-compatibility.draft.ts`，由本轮验收探索形成，**没有通过**，已经从 `.spec.ts` 改名，避免默认 Playwright 收集失败的草稿。同事修正后再改为 `.spec.ts`。未修改前端产品代码。

最近浏览器失败证据在本 Worktree 的 `apps/platform-web/test-results/background-compatibility-local：真实前台执行成功，启动能力关闭，已有任务查询入口保留-chromium/`，含脱敏 HTTP 方法/路径/状态附件、失败截图和 error-context。它只证明失败现场，不能算通过；后续运行可能覆盖。

**已定位的因素：**

- 首轮 ORM 新字段与测试库旧迁移不一致，普通 commands 500；专属平台库已迁移到 `20261010_0007`，主库未改。并行 API 热重载、PG 短暂不可用也曾产生联调失败。
- 新会话按钮可点不代表模型目录/hydration 已就绪。草稿已等待“选择对话运行模型”显示实际授权模型名，再发送；审批使用当前“批准 (Approve)”及“确认批准所选操作”。
- `qwen-plus` 最近一轮经历五个不同 interrupt，均真实接受审批，但又请求同一命令。后续脱离浏览器、直接 API 的复验同样复现：命令已真实成功，模型工具调用 `id=""`、ToolMessage 的 `tool_call_id=""`，既有 `sanitize_tool_call_messages()` 会移除对应回执（3份结果清洗后0份），下一次模型仍请求同命令。三个相关清洗/修复函数与 HEAD 的 AST 相同，定位到现有消息清洗与该模型空 ID 的兼容缺口；尚未执行完整旧源码的同模型链路，不将函数对照扩大为所有旧版本都已复现。该 qwen 链路先交 Runtime 模型适配排查，前端不靠增加自动审批次数修复。
- 已配置 `deepseek-v4-flash` 的两图真实 API 链路均一次审批成功。本轮浏览器草稿默认 fixture 选到了 qwen；接续测试显式选择同一已验模型，并保证项目授权、Agent context 和 UI 选择一致，不修改全局 fixture 来影响别的测试。

**需要完成的浏览器场景：**

1. local 的两图实际发送短命令、人工审批、得到真实 execute 输出和 Run success；无 `background_execute`，query=true/start=false，任务 Tab 空态。不要只断言 UI 文本，也核对 state 中 ToolMessage 和真实列表。
2. query=true/start=false 时已有任务仍可查看、取消；没有任务存储能力时 Tab/探针关闭。状态组合可用明确标注的组件/HTTP fixture 验证；真实旧任务需保留原 Docker 执行域，不能把 local 节点当控制器。
3. B 的局部 not_started 提示和继续对话；通过可恢复回执 fixture/已有 checkpoint 安全验证，不为了测试绕开 A 或放开生产工具。
4. 回归既有后台列表/日志/取消单飞/Stop/完成通知微胶囊、切会话和刷新。B01/T10/F12 的全量故障 Final 由相应专项收口。

## 6. 联调环境与交付要求

先读 [Worktree 资源隔离规范](../../standards/worktree-development.md)，在指定 Worktree 根目录运行：

```bash
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" doctor
# 服务未运行时，通过统一脚本启动；状态以实时 status 为准。
bash "scripts/local-stack.sh" start
```

当前专属环境 `wt_27df0f537b6d`：Web `http://127.0.0.1:24335`，Platform API `http://127.0.0.1:29336`，Runtime API `http://127.0.0.1:23608`。私有配置在 `.local-stack/`，不复制、不打印凭据，不回退主工作区的端口、数据库、`.venv` 或 `node_modules`。栈保留给并行引擎接线和前端联调，不停止别人的服务。

本环境 Runtime 已安装正式双包 `0.13.0.post45`（非 editable），仓库 `uv.lock`/部署 Dockerfile 已锁 post45，迁移 head 为 `013_run_acceptance_receipts`；B01 已解除。前端联调仍须核对实际版本，不要在并行验证时无沟通运行 `deps` 把安装还原到旧锁。

ABF01-ABF03 的定向单测、类型/lint/build及真实 Playwright 证据已记录到 tasks 与独立 Phase。全专项仍为 `partial`，T08/T10/F12 门禁保留；B01由接受回执专项独立解除，不把A/B前端完成当作全范围Final。

## 7. 可直接转发的话术

> 原交接话术（ABF01-ABF03现已完成）：在用户指定的99f7平台Worktree接续非Docker前端增量。后端A主方案+B精确兜底：不支持启动时隐藏background_execute，旧checkpoint保留回执；只有确认未登记才返回not_started，短任务经原审批使用execute，最大60秒，unknown不重跑。
>
> 先读 `docs/projects/20261009-agent-generic-production-capabilities/local-compatibility-frontend-handoff.md`，再对照 `plan.md` 4.3、RFC、`tasks.md` 的 ABF01-ABF03 和 `verification.md`。已有 F01-F11 任务界面不用重做。请补齐查询能力关闭时的探针门禁、恢复提示映射/单测，以及真实 local 浏览器验收；query=true/start=false 时必须保留任务 Tab 和已有任务的查询/授权取消。
>
> 后端 Runtime 91项、真实PG 12项、平台能力2项通过，两图使用 deepseek-v4-flash 已经真实API/Worker/审批/execute/success。浏览器草稿在 `apps/platform-web/e2e/background-compatibility.draft.ts`，尚未通过，修正后再纳入 Playwright。qwen-plus 有空工具ID导致重复执行的已有模型适配问题，诊断已写入交接，先用已验模型做本次浏览器验收。引擎B01/正式依赖接线由另一同事负责。本Worktree有并行改动，请保留并核对归属。完成后更新ABF任务和Phase证据。
