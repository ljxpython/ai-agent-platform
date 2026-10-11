# 前端同事交接：后台接受回执与F12联合验收

> 状态：非前端 K01–K08 已完成并通过独立 Final，无 Block；前端交接方案已经老王技术深潜与架构审查，去除了粗糙与漏洞设计，更新为高可靠状态机与 HITL 避让最佳方案。前端 K09/K10 待实施，整体仍 partial。本次 Web 源码/测试尚未编写。按本方案严格实施及 F12 联合验收。

## 1. 工作区与读什么

- 唯一实施目录：`~/.codex/worktrees/b01-closeout/ai-agent-platform`。
- 展开的绝对路径、正式包 URL/hash、三套 head 和镜像见[实际产物清单](implementation/artifacts.json)，清单不含 token、Key 或私有环境配置。
- 来源 99f7 已合并；从集成分支 `feat/langgraph-v3-delta-evaluation` 的 `2b94585b` 创建此 detached Worktree。本轮增量**未提交 Git**，须在这个目录接手；如另建 Worktree，先由负责人完整带入本轮未提交补丁，仅从 HEAD 创建会缺少修复。
- f5a8 保留历史规划副本，99f7 是来源，均不作为此次最终联调环境。
- 阅读本页和 [plan.md](plan.md)、[tasks.md](tasks.md) K09/K10、[verification.md](verification.md) V16–V18。
- 合并后的原项目 `docs/projects/20261009-agent-generic-production-capabilities/{frontend-handoff,local-compatibility-frontend-handoff}.md` 保留F01–F11/ABF的详细设计，进度看原tasks和新tasks，旧表“拟新增”不表示需要重新开发。

## 2. 后端交付内容

GraphHarbor 正式 post45 已发布，B01 保持解除。后端复用已有最终 bytes/key/digest、固定 GET 与 reconcile-only，补齐完成续接的新 Context/签名、凭据与 callback 合并接线、Stop 后候选过滤、两套应用迁移汇合和 SQLite 历史 UUID 类型修复。本地启动已取消强制开启，API/Worker 使用登记环境 ID 作为独立执行域。非前端 Final 已通过，原 T01/T05/T08 回填完成；正常/lost ACK notify/Stop/撤权、源超时取消和回退系统组 6 passed，完成模型 1/0/0；两组合根真实受管模型及独立 Usage 已验。详见 verification 和[脱敏证据](implementation/final-evidence.json)；没有新增浏览器接受回执入口。

对前端继续沿用以下契约：

| 契约 | 读取/操作 | 前端用途 |
|---|---|---|
| `TaskListV1` | `GET /api/langgraph/threads/{thread_id}/background-tasks` | `has_unresolved`与`latest_delivery_run_id`发现任务/完成Run，不受当前分页遮蔽；后端补最新自动候选排除Stop/抑制任务，详情原run_id保留 |
| `TaskV1` | `GET /api/langgraph/threads/{thread_id}/background-tasks/{task_id}` | 命令status、cleanup_state、delivery.state/run_id分别展示 |
| `OutputV1` | 同任务`/output` | 有界纯文本，脱敏的合法任务scope，无HTML/ANSI执行 |
| 取消 | `POST`同任务`/cancel`，原`Idempotency-Key`、body`{}` | 202只接受意图；后续状态和cleanup确认后更新，不自动改“已全部停止” |
| 会话Stop | 已有cancel/stop-requests/list及report DTO | 固定旧scope/任务、confirmed/unconfirmed、notifications_suppressed_count；不受LLM空闲时no_active_run误导 |
| capability | `background_tasks`（query）、`background_tasks_start_enabled`（start） | query=false/缺省隐藏任务入口并终止探针/在途请求；query=true/start=false保留历史任务/日志/授权取消 |

公开 DTO、错误码与现有 SSE 契约保持。实际安全样例与联调方式见第 6 节；不要新增前端 Run 调度器。

## 3. 同事负责的准确代码位置与重构方案

路径相对此 Worktree；检查与修补均复用现有实现，严禁无端引入外部大重构，但在状态机与时序安全性上必须做到零死穴。

**已确认的修补项（细化方案）：**

1. **`BackgroundTaskItem.vue`：状态语义纠正与 UI 投影补齐**
   - **纠正 accepted 假性完成文案**：当前将 accepted 写成“已送达通知”，必须改为“续接已接受”，并增加悬浮提示 `hover: "续接请求已由服务端接受，原生处理就绪中"`；徽章使用温和的紫灰/中性色，明确展示此状态仅为调度中间态，绝非终端回答或通知已落地。
   - **补齐 unknown 状态的显式投影**：当前 `delivery.state === 'unknown'` 时直接被 `v-if/v-else-if` 吞掉。必须补充“续接待确认”徽章及提示 `hover: "续接状态确认中，正在保持只读查询"`；**严禁**提供任何重发/重试按钮，**严禁**自动向后端发送 POST 重投或执行。
   - **保持 cleanup=unconfirmed 警示**：取消中或失败时，若 cleanup 仍为 unconfirmed，如实保留“清理未确认”，严禁宣称“资源已全部释放”或“已完全停止”。
   - **操作单飞锁与纯文本安全**：保持现有 logs 查看纯文本脱敏，cancel 单飞锁（`cancellingTaskIds`），防止重复点击。

2. **`useBackgroundTasks.ts::checkDiscoveredRuns()`：候选严苛白名单过滤与 Stop 协同**
   - **过滤严苛白名单**：遍历当前页 `items` 时，必须且仅当 `task.delivery.state === 'accepted'` 且 `task.delivery.run_id` 存在时才转交给 `options.onRunDiscovered`；**绝对禁止**将 `delivery.state === 'suppressed'`（用户 Stop 后通知被抑制但后端保留原 `run_id` 供审计）或 `unknown` / `not_ready` 的任务转交给前台 SDK！
   - **消除分页与最新字段双标**：`latestRunId` 与 `items` 循环均采用同一严苛过滤策略，防止“最新字段已过滤但列表任务发生泄露”。
   - **Stop 与会话重置协同**：在 Composable 中暴露 `clearDiscoveredRuns()` 清理方法；在 `resetScope()`（切会话或能力关闭）时清空 `discoveredRunIds`，并在外层 Stop 触发时支持协同清理，杜绝旧候选在当前页对账时被误激活。

3. **`useChatSession.ts` 与 `ChatSession.vue`：接续时序闸机（The Iron Gate）与 HITL 绝对保护**
   - **HITL 与 Busy 全面避让**：定义复合阻塞状态 `isBusyOrInterrupted = computed(() => busy.value || hasPendingInterrupts.value || reviews.value.length > 0 || clarifications.value.length > 0 || planReview.value != null || cancelling.value || stopState.value !== 'idle')`。在任一非空闲、审批中或正在停止状态下，`acceptDiscoveredRun` **绝不**直接触发 `service.runs` 或篡改 `run.value`，必须将候选 ID 安全入队 `pendingDiscoveredRunIds`（去重暂存）。
   - **异步 Await 的 Scope / Epoch 版本锁（防切会话串台）**：在 `await service.runs(currentTid)` 前记录 `scopeThreadId = threadId.value`；await 返回后严格比对 `if (disposed || threadId.value !== scopeThreadId) return;`。若在 await 期间进入 `isBusyOrInterrupted`，则重新安全入队暂缓接纳，严禁直接粗暴覆盖 `run.value` 破坏正在进行的交互。
   - **切会话队列清理（防跨会话幽灵消费）**：在 `watch(() => options.threadId)` 中，切换会话时必须清空 `pendingDiscoveredRunIds.value = []`，杜绝旧会话遗留的 Run ID 在新会话中被幽灵执行。
   - **精确恢复监听**：监听 `isBusyOrInterrupted`：当且仅当其从 true 变为 false，会话回归真实 idle 且可订阅时，调用 `flushPendingDiscoveredRuns()` 出队接纳。

| 文件 | 检查/必要修补 | 对应验证 |
|---|---|---|
| `apps/platform-web/src/modules/chat/background-tasks/types.ts`及`types.spec.ts` | accepted/unknown/suppressed、可空run_id、正交cleanup与输出；拒scope错误/私有字段，兼容合并后最终DTO | 状态组合与非法响应单测 |
| `apps/platform-web/src/modules/chat/composables/useBackgroundTasks.ts`及spec | 修发现候选强过滤（仅限 accepted+run_id）；暴露 clearDiscoveredRuns；探针/AbortController/切scope、分页无关未结标志、query/start独立门禁，unknown/deadline不触发写操作 | Vitest竞态、suppressed当前页/跨页、隐藏/离线、迟到响应、ABF回归 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts`、`components/ChatSession.vue` | 修真实 HITL（reviews/clarifications/planReview）避让、异步 await 期间 scope 版本锁、busy/Stop 全面拦截及待转交队列切会话清理；discovered run 安全转交既有 SDK，suppressed 晚到 run 不抢流、不恢复审批，撤权停止新订阅 | discovered run、await期间新Run/切scope、busy/HITL/撤权单测+真实链路 |
| `apps/platform-web/src/components/workspace/BackgroundTaskItem.vue`及新增`spec` | 修 accepted 文案为“续接已接受”并补 unknown“续接待确认”提示；三类状态独立展示，原生 Run 才证明回答完成，unknown 无重发按钮，cleanup 未确认提示；取消单飞保持 | 新增独立组件单测、状态组合/纯文本日志/三视口 |
| `apps/platform-web/src/components/workspace/{BackgroundTasksPanel,WorkspacePanel}.vue`及spec | 面板容器与 Tab 联动，query=false/缺省隐藏入口，query=true/start=false 保留查询/日志/取消 | 面板状态/三视口响应式 |
| `apps/platform-web/src/modules/chat/{transcript,background-tasks/completion-parser}.ts`及测试 | 后台触发消息仍系统胶囊、无编辑重发/分支；保留较新工具输出复合key与loop/Token/Plan展示 | parser/transcript回归和浏览器截图 |
| 既有 `useThreadStopControl`、Stop报告组件和DTO | 接受回执不替代 cleanup 确认；晚到 Run 或 unconfirmed 不宣称全释放 | 停止未确认→真实确认测试 |
| `apps/platform-web/e2e/{background-tasks,background-compatibility}.spec.ts` | 补 F12 故障与合并后真实栈验收，复用现有 Playwright fixture | V17–V18，真实模型至少一条 |

现有全局失败通知中心/历史 completion 来自另一个终态通知专项。此次后台完成 Run 的系统胶囊不能覆盖、重复或重写那套通知中心。只对合并冲突涉及的调用者补回归，不扩大成全前端重构。

## 4. 必须遵守的状态语义

| 状态/窗口 | 应展示/执行 | 禁止行为 |
|---|---|---|
| 命令已 succeeded，delivery=accepted，Run=pending | 命令结果可见，徽章显示“续接已接受”，等待原生 Run 投影 | 把 accepted 画为 Agent 已经回答或用户已经收到通知 |
| delivery=unknown / 详情过期 / 查询临时失败 | 徽章显示“续接待确认”，按后端 has_unresolved 继续只读探针 | 自动换 key/event、提供“重试/重发”按钮、POST、execute、批准或把未知改失败重跑 |
| Stop 后 run_id 迟到，delivery 仍 suppressed | 保持“通知已抑制”及真实 Stop 清理状态；固定 scope 安全对账 | 将 suppressed 的 run_id 推入 onRunDiscovered、恢复用户输入、抢当前 stream、出现假用户气泡或自动 summary |
| cleanup=unconfirmed | 资源状态未确认，可刷新已授权查询，显示“清理未确认” | 用命令终态、accepted 或按钮 202 回包宣称“全部资源已释放”或“已完全停止” |
| 前台处于 busy / 工具审批 (reviews) / 澄清 (clarifications) / 计划审阅 (planReview) | 将后台发现的 Run ID 安全存入队列排队避让，严禁修改当前 run.value | 覆盖 run.value 冲毁正在展示的审批卡片、自动 resume/approve、抢占输入焦点或另起第二轮询 Run 状态机 |
| 异步 await service.runs 期间用户切换了会话 | 比对发起与返回时的 threadId，发现不一致立即丢弃请求结果 | 将老会话的后台 Run 赋值给新会话的 run.value 造成跨会话串台 |
| 用户切换会话 (threadId 变化) | 彻底清空待转交队列 pendingDiscoveredRunIds | 残留老会话的待转交 Run ID 并在新会话中触发幽灵调度 |
| 会话正在停止 (cancelling / stopState !== 'idle') | 拦截一切后台 Run 接续，保持停止状态投影 | 将后台 Run 接纳并篡改停止状态，或把会话重新置为 running |
| 用户/项目/凭据撤权 | 当前 ACL 拒绝时停止公开读/新订阅，沿已有错误出口 | 将内部固定回执例外授权给浏览器、缓存保留已撤权内容 |
| query=true/start=false | 保留任务 Tab、已有列表/日志/授权取消 | 因启动关闭隐藏未结资源或停掉必要对账 |

前端不调用 `/threads/{thread_id}/runs/acceptance`、不拿固定内部 JWT、不计算传输摘要或手工重发后台完成 Run。完成续接只由服务端触发。

## 5. 验收要求与协作

K09 单测重点补齐并全量跑通：
1. **新增 `BackgroundTaskItem.spec.ts`**：覆盖 accepted（续接已接受）、unknown（续接待确认）、suppressed（通知已抑制）、cleanup=unconfirmed（清理未确认）全状态组合渲染及 logs/cancel 交互。
2. **强化 `useBackgroundTasks.spec.ts`**：
   - 增加 `delivery.state === 'suppressed'` 但带 `run_id` 的反向用例，断言**绝不触发** `onRunDiscovered`；
   - 增加 `delivery.state === 'unknown'` 时的只读守卫，断言零写操作；
   - 增加 `clearDiscoveredRuns` / 切会话 / 作用域销毁时的清理验证。
3. **强化 `useChatSession.spec.ts`**：
   - 增加当前处于工具审批（reviews）、计划审阅（planReview）及用户输入 busy 时的入队避让断言，断言 `run.value` 不被覆盖；
   - 增加 `acceptDiscoveredRun` 异步 await 期间切换 threadId 的版本锁拦截用例，断言老会话 Run 不渗透进新会话；
   - 增加切换会话时 `pendingDiscoveredRunIds` 清空断言；
   - 增加会话 stopping / cancelling 期间拒绝转交后台 Run 的断言。
4. **静态门禁总检**：在本服务（`apps/platform-web`）执行 `vitest run`、`pnpm run typecheck`（vue-tsc）、`pnpm run lint` 及 `pnpm run build`，确保 0 errors。

K10 至少下列浏览器端到端联合验收链路（复用现有 Playwright fixture，对标真实环境）：

1. 正常后台命令与受管真实模型续接，离开/刷新/返回后只展示一个系统胶囊和一次 Agent 回答；Usage 归完成 Run。
2. Worker 暂停、创建 ACK 丢失：任务可见且通知待确认；原 GET 找回 pending Run，恢复 Worker 后正常接续；accepted 期间不伪完成。
3. 同窗口 Stop：保持 suppressed、无完成模型和假用户消息；清理从 unconfirmed 到实际 confirmed；后来的用户 Run 仍可用。
4. 同窗口撤权：公开列表/日志/订阅按当前 ACL 拒绝；内部固定 GET 对账与开始前 guard 由后端验证，完成模型 0。
5. unknown/期限/旧接口异常：没有重发/前台执行/自动批准，临时 502 不误踢用户，恢复仍同原身份；缺失查询能力停止探针。
6. busy/HITL 与切会话：完成 Run 不抢当前回答/审批卡片，scope 清理和唯一订阅；保留既有 A/B local 与关闭新启动的历史任务入口。

正常完整链用实际受管模型，故障零调用用确定性provider精确计数；两者分别标记。覆盖1440/768/390浅深主题、日志纯文本/取消单飞/Stop空闲可达。只静态截图、mock HTTP或历史E2E通过不能代替F12。

现有 `background-tasks.spec.ts` 覆盖普通真实聊天、Mock capability/任务/日志/取消交互。保留这些用例，F12 另补**真实后台命令和原生 Run**；其任务/capability/Run/Stop 核心接口需透传真实服务，截图记录实际 task/event/run。`background-compatibility.spec.ts` 的 local 短命令链保留，模型选择改为本环境已配置且可用的受管连接，不能靠扩大审批次数绕过模型适配问题。

## 6. 实际环境、启动与故障协作

环境 `wt_43727db9404e`：Web `http://127.0.0.1:29286`，Platform API `http://127.0.0.1:23818`，Runtime API `http://127.0.0.1:24548`，专属 Redis 28816。本地管理员 `admin / admin123`；独立 `.venv`、`node_modules`、两库、Workspace 和日志已初始化。2026-10-11 10:45 交付检查时 Docker 长期栈的 API/Worker/Web/Redis 均运行并核对归属，三个 HTTP 入口均 200；验收 fixture 已退出，相关任务与镜像容器无残留。服务保留给同事联调，之后实际状态以 `status` 为准，登记 URL 本身不是健康证明。

正式 Runtime 双包 `0.13.0.post45`，Runtime SDK `0.4.3`，API SDK `0.4.2`。实际 head：Platform `20261011_0009`、Runtime `0004_background_token_budget`、引擎 `013_run_acceptance_receipts`。Runtime API/Worker 验收镜像为同一摘要：

```text
sha256:3b7a07136c46d7d151218571f45a40016dbd1044938ae976aff2aadc7a992601
runtime-background-closeout:wt-43727db9404e-post45-final
```

本机 Workspace 命令镜像为 `runtime-agent-workspace:p5`，摘要 `sha256:204e7d14f49f818545026345355c675dec744ae12dfbb423d1c7403cd4d99d85`。命令容器不获得控制 daemon 的 socket 或服务密钥；API/Worker 控制层和绝对挂载按运行手册配置。`local-stack` 启动的是当前 Worktree 源码进程，最终镜像验收由 E2E fixture 执行，两种证据分别记录。

先读 `docs/standards/worktree-development.md`，从本 Worktree 根执行：

```bash
bash "scripts/local-stack.sh" doctor
RUNTIME_BACKEND=docker bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" logs runtime-worker
bash "scripts/local-stack.sh" stop
```

新环境默认关闭后台新提交。本 Worktree 私有 `.local-stack/runtime.env` 已为 Docker 联调**显式设置 1**，没有修改仓库默认；`RUNTIME_EXECUTION_HOST_ID` 由登记自动固定为 `wt_43727db9404e`，后台日志固定在所属 `.local-stack/background-logs`，不要复用 `worktree-host` 或复制其他环境配置。当前脚本默认 local，Docker 场景每次启动/重启均带 `RUNTIME_BACKEND=docker`；local A/B 场景显式带 `RUNTIME_BACKEND=local`。开关变化需同时重启 Runtime API/Worker；切换 backend 前排空现有任务。本目录 Platform 私有配置及 macOS 夹具均使用标准 asyncio，避免已复现的 uvloop native abort；故障测试只在 disposable fixture 执行。

正常真实模型测试使用受管 `gpt-5.6-terra`；两组合根源 Run 与完成 Run 均有独立 Usage，费率未配置时 cost 如实为 `unknown`。模型配置来自已有受管连接，不在前端填私有 Key。

实际测试入口为 `apps/runtime-service/tests/e2e/test_background_tasks.py`，复用 `tests/fixtures/run_reliability.py`；lost ACK 用 `background-lost-ack` 文件屏障确定边界，顺序为源 Run 结束、停 Worker、设置 `lost-ack-hold`、释放命令。然后 Platform 实际重启，模式切 `reconcile` 触发固定 GET；notify/Stop/撤权各有安全 JSON 计数证据。故障模式仅存在于测试夹具，正式服务不提供注入接口；浏览器故障验收由后端在同一 fixture 配合，不可在主库/主服务注入或另造公开故障 API。

Python disposable fixture 的 API/Runtime 端口由 OS 分配，和上面的长期栈登记地址不同；当前 Playwright 配置会校验登记地址。K10 联合时由双方将真实受控 fixture 接入本环境的测试支持，保留资源登记/URL 校验和独立浏览器上下文；先停止本环境对应长期进程再占登记端口，不能关闭校验、硬改为主工作区 3000/2142/8123 或把历史 pytest JSON 当作浏览器本轮取证。此项属于 K10 联合测试工作，本轮只交付已验证的后端故障入口、源码和证据，没有开发前端 fixture 支持。

任务详情的关键状态样例（其余字段沿现有 `TaskV1`）：

```json
{"status":"succeeded","cleanup_state":"confirmed","delivery":{"state":"accepted","run_id":"4154d418-4e55-484d-9e23-f594ec83e5e9","reason_code":null}}
```

Stop 迟到时同一个 `run_id` 可以保留，但 `delivery.state` 为 `suppressed`，且 `latest_delivery_run_id` 不投影该 Run；unknown 的 `run_id` 可空。没有接受回执不代表命令失败，公开查询撤权仍按原 403 出口处理。精确错误白名单沿原交接，不从服务日志猜测错误码。

## 7. 可直接转发的话术

> 99f7 已合并，GraphHarbor post45 已完成，B01 已解除；非前端 K01–K08 已开发、验证和交付，无 Block。请在 `~/.codex/worktrees/b01-closeout/ai-agent-platform` 接手。这个 Worktree 基于 `2b94585b`，后端修复、迁移和专项文档尚未提交，不能只从 HEAD 另建目录，否则会缺少本轮增量。
>
> 先读 `docs/projects/20261011-background-acceptance-closeout/frontend-handoff.md`，再看 `tasks.md` 的 K09/K10、`verification.md` 的 V16–V18 和独立 Final。文档写明环境、启动、版本、契约与故障协作；Web 地址为 `http://127.0.0.1:29286`，本地管理员 `admin / admin123`，交付时服务已启动，接手前用 status 复核。
>
> 前端已完成深度架构与状态机审查，确认实施最佳方案：
> 1. `BackgroundTaskItem.vue`：accepted 改为“续接已接受”并加 hover 调度说明；补齐 unknown 显式“续接待确认”灰/黄徽章且禁止重试按钮；cleanup=unconfirmed 坚守“清理未确认”防假宣称；
> 2. `useBackgroundTasks.ts`：候选转交实施严苛白名单（仅 accepted + run_id 放行，彻底封杀 suppressed/unknown 候选）；补齐 clearDiscoveredRuns 及 Stop/切会话协同清理；
> 3. `useChatSession.ts` 与 `ChatSession.vue`：落地接续时序闸机（The Iron Gate）——全面的 busy 与 HITL（reviews/clarifications/planReview）避让排队；await 期间 scopeThreadId 版本锁阻断跨会话串台；切会话彻底清空待转交队列；精准 Watcher 收敛恢复。
>
> 单元测试需新增 `BackgroundTaskItem.spec.ts` 并强化 `useBackgroundTasks.spec.ts` 与 `useChatSession.spec.ts` 的定向时序/避让用例。全量跑通 Vitest、类型、lint、build 后，再按 K10 在隔离栈进行 6 大真实浏览器链路验收（至少 1 条真实模型完整链），保留 390/768/1440 响应式截图。无新接受回执页面，不接内部 token，不自动重投。后端证据已交付，最后共同收口原 T10/F12 和 K11。
