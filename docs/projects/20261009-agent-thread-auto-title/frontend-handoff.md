# F07 前端交接（交给同事）

> 2026-10-09冻结交接：后端/Runtime/引擎源码与候选已完成，9场景HTTP与真实qwen-plus受管链路通过，见 `verification.md`。仅T06/T07B交前端同事；B01正式CAS双包发布/正式源接入blocked。自动默认关闭，候选不等于正式包。

## 当前可用能力

已有首条消息规则命名、手动改名和侧栏 AI 提炼按钮，全部以 `thread.metadata.title` 显示。两个 Page 已接 `service.summarizeTitle(threadId)`；Dear Agent 的会话 composable 直接共享 Chat 的实现。

| 文件 | 现有符号/责任 | 建议增量 |
|---|---|---|
| `apps/platform-web/src/services/threads/session.service.ts` | `createSessionService()` 内 create/update/summarizeTitle | 扩同一个方法的 DTO、AbortSignal 与 auto_title opt-in，不新建另一 service |
| `apps/platform-web/src/utils/thread-title.ts` | `deriveThreadTitle()`（40 字）、`deriveMessagePreview()` | 保留已有规则；附件保底沿实际 runtime_file 校验，不复制 DeerFlow 类型 |
| `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts` | `useStream()`、onCompleted 后调用 verify | 继续作为 Run/消息事实源，不在这个回调直接 await 标题生成 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | `send()` 创建初始规则标题，`verify()`/后台回查确认终态 | expose/use 既有 success 与身份，不增加新的运行循环 |
| `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts` | re-export useChatSession | 共享自动能力，避免复制实现 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 当前会话/Run/messages 的组合根 | 仅接独立标题 composable 与 scoped title-updated 事件 |
| `apps/platform-web/src/modules/chat/pages/ChatPage.vue` | `handleRenameThread()`、`handleAiSummarizeTitle()`、threads list | 合并已落库的 title 更新；账号/项目 epoch + 同 Thread 守卫 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue` | 同上 | 同等行为和竞态守卫 |
| 两处 `*ThreadSidebar.vue` | Inline rename、AI 按钮和 tooltip/loading | 基本复用，无须增加标题卡片、额外 spinner/说明面板 |

已有 `useFollowUpSuggestions.ts` 的 success/interrupt/stop/可见性守卫、`suggestions/cleaner.ts` 的纯文本提取可参考。但标题是一次性辅助动作，建议独立 `useAutomaticThreadTitle.ts`；不把建议 composable 泛化成通用 AI 回调框架。

## 已冻结的接口

现有 API URI 保持 `POST /api/langgraph/threads/{thread_id}/title/summarize`；所有请求带平台认证与 `x-project-id`。

```json
{ "mode": "auto", "run_id": "<已确认 success 的 Run UUID>" }
```

自动请求不传 messages、模型名、密钥、seed、内部 scope/config；后端以已提交状态为准。创建新普通会话时可选顶层 `auto_title: true`；只有创建时自动开关已开启，才写入首轮 seed。创建时开关关闭，即使 opt-in 也返回 `auto_title_pending:false`；之后开启不会回填。未 opt-in 的 Thread、旧会话/fork/导入没有自动行为。后端自动开关默认关闭。

```json
{
  "thread_id": "<uuid>",
  "title": "当前已落库标题",
  "metadata": { "title": "当前已落库标题", "auto_title_pending": false },
  "outcome": "applied",
  "reason": null
}
```

`outcome=applied|skipped|degraded`。`auto_title_pending` 在创建/读取/搜索 Thread 与 metadata 更新/标题响应中由服务端投影，只读。它表示 seed 尚未消费，不保证自动开关开启或调用一定成功。客户端不能提交此字段（包括 create/patch/state/input 的嵌套位置）；不要回传整个 Thread metadata，只提交明确的 title/preview 更新。

| outcome / reason | 返回与客户端行为 |
|---|---|
| `applied / null` | CAS 已确认；应用 HTTP 中的持久 title/metadata |
| `skipped / disabled` | 自动 gate 关闭；不重试 |
| `skipped / not_pending` | 未 opt-in、seed 已消费/人工改名/fork；不重试 |
| `skipped / not_first_round` | 已有多轮真实输入；不重试 |
| `skipped / run_not_ready` | Run 不是匹配的普通 success、活动 Run/interrupt、checkpoint/材料变化；只在下一次真实有效状态变化后重查 |
| `skipped / materials_missing` | 已提交材料不可确认，或附件归属不符；保留当前 title，不循环重试 |
| `skipped / conflict` | CAS 条件失效；使用已回读的当前 title，尊重用户动作 epoch |
| `degraded / model_unavailable` | 无受管模型/连接不可用，保留当前 title |
| `degraded / timeout` | 总 model connection+调用 deadline 已到，保留当前 title |
| `degraded / provider_failure` | provider 失败，不返回原错误；保留当前 title |
| `degraded / empty_output` | 正文为空/仅 reasoning，保留当前 title |

auto 的合法 degraded 会 CAS 消费 seed，因此通常返回 `auto_title_pending:false`；manual degraded 不改 title/seed。skipped 不主动消费 seed，pending 以真实响应为准。response metadata 可能还有 project/graph/ACL/allowed_actions 等既有字段，前端沿当前 Thread DTO 做投影，不扩展为任意内部对象。

manual 保留 `{}`；也接受 `{messages:[{role:"user"|"assistant"|"human"|"ai",content:"..."}]}`，1-8 条、每条最多 4000 字符、总计 12000。未知字段拒绝。auto 必须只传 mode/run_id，即使 `messages:null` 也拒绝；不需要 Idempotency-Key，不应盲重试。

| HTTP / code | 行为 |
|---|---|
| `400 invalid_title_payload` / `400 invalid_run_id` | DTO/Run UUID 错误；停止本次调用 |
| `403` / `404` | 沿当前项目/Thread 局部权限处理，不清全局登录 |
| `502 invalid_title_response` | 上游 DTO 错误；不展示候选或猜成功 |
| `503 title_cas_unavailable` | 配套引擎不支持独立 CAS 入口；待 B01，不回退普通 PATCH |
| `503 title_write_unconfirmed` | CAS 可能已提交；GET Thread 对账，使用真实 title/pending；不要重复生成 |
| 网络/浏览器超时 | 结果未知，执行同样的 GET 对账与 epoch 守卫 |

API 已将 CAS 传输超时/5xx 和不能确认的返回统一成 `503 title_write_unconfirmed`。平台既有 Runtime 401 转换为 `502 runtime_delegation_rejected`，不表示浏览器登录过期。

手动按钮保留 `{}` 调用，不自动填写 mode=auto。AI 调用需当前项目 execute + Thread comment+edit；仅有 edit 权限仍可人工改名，但不能调用模型。服务器是权限事实源，客户端 disabled 状态不能替代授权。手动 AI 和自动 AI 同样依赖 CAS 配套；发布时 API/Runtime/GraphHarbor 同步升级，不能独立上线 API 新版配旧 CAS 引擎。

## 生命周期与竞态要求

1. 等 **已确认 Run success** 与 **根图最终 assistant 正文可用** 两者同时满足；content/lifecycle SSE 到达顺序可能相反。不能只监听 isLoading 从 true 变 false，也不能只数 AIMessage。
2. 首轮恰一条真实用户消息是后端检查；前端可做轻量预判。工具中间态、审批、手动整理、error/timeout/Stop 状态均不调用；用户停止要抑制自动补偿。
3. 请求与主 send/SDK completion 解耦。自动失败静默保留原标题，不写 chat error、不 toast、不改变 busy/stop/审批状态，不创建辅助 native Run。
4. 同一 identity/sessionEpoch/project/thread/run 单飞；flush 后再次检查完整条件。只在当前身份一致时应用返回；手动 rename/manual summarize 发生时递增本地 title epoch、abort 自动展示结果。
5. AbortSignal 防止前端展示迟到结果，不代表服务端写入已取消；保住手动标题依靠后端 seed + CAS，不能用本地取消替代。
6. 后台隐藏只标待补偿，切回后复核真实终态/权限/pending，再尝试一次；切换项目/退出登录/实例销毁立即失效旧请求。关闭浏览器不承诺自动命名，初始标题保持可检索。
7. 应用 HTTP 返回中的已存 title，同时更新对应列表、active title 与已有 Thread 缓存；后续正常 Thread 刷新可补偿。旧列表 fetch 在请求后到达时不得把本地已确认新标题覆盖为旧值，可取消旧请求并复查，不必建版本账本。
8. `skipped/conflict` 用服务器当前 title；degraded 使用响应中的持久 title 和 pending。503/网络未知时读 Thread 对账，不反复生成。自动失败不无限重试；再次尝试的政策服从服务端 pending。
9. 明确 403/404 按既有 scoped 权限处理；标题局部拒绝不自动清全局登录。不要在自动失败后调用任何 run-create、resume、state-update 或消息入队接口。
10. 标题以普通文本渲染，沿用当前截断/tooltip/Inline 编辑/键盘和 aria。长文件名、英文长词、emoji/Unicode 不能挤坏手机侧栏；不使用 v-html。

## 交接验收

| 编号 | 场景 | 预期 |
|---|---|---|
| F01 | Chat/Dear Agent 新首轮 success | 从规则标题升级；双入口行为一致、刷新后保持 |
| F02 | lifecycle success 先到、最终 values 后到（及相反） | 两条件齐全后仅一次请求；不出现空标题 |
| F03 | 工具调用、reasoning-only、HITL/Stop/error/timeout | 不提前提炼、不误认完整回答；主 UI 正常 |
| F04 | 自动调用期间用户改名/手动 AI 提炼 | 用户动作优先；HTTP/刷新迟到结果都不回滚 |
| F05 | 双标签页、会话/项目/账号快速切换 | 无跨作用域覆盖；前端单飞与后端 CAS 分别验收 |
| F06 | 慢模型、超时、503/504、错误 DTO | 自动静默保底/对账；正常 send/Stop/审批不被卡住 |
| F07 | 纯附件、多个附件、图片无可读文件名 | 使用后端本地标题或保底，不触发 LLM，不展示路径/base64 |
| F08 | 编辑/评论权限差异、真实撤权、刷新瞬态失败 | disabled 与服务端拒绝一致；局部拒绝不误退登录 |
| F09 | 旧 Thread、fork、多轮、自动关闭、页面关闭再进入 | 原标题与手动按钮保持；无历史批量生成 |
| F10 | 1440/768/390 视口、长词/文件名、键盘改名 | 无重叠/溢出；截断 tooltip 可用，无布局跳动 |

定向测试落在 service/composable/Page；既有 Sidebars 测试作为回归，不写只镜像实现的快照。完成后执行 `pnpm test:run`、`pnpm typecheck`、`pnpm lint`、`pnpm build`（以当前 package scripts 为准），并进行至少一条三服务真实模型 Playwright E2E。前端由同事完成，后端定向测试不能替代这些验收。

## 发布与已知边界

- 配置：`PLATFORM_API_TITLE_AUTO_ENABLED=false`（默认）；`PLATFORM_API_TITLE_TIMEOUT_SECONDS=8`，有效区间 `(0,30]`。只在正式 CAS 双包接入及 F01-F10 验收通过后开启 auto。
- 同事可使用隔离环境和本地v2候选进行接线；PyPI现有post43没有CAS，仓库当前锁定的正式post43不能完成新版AI落库。禁止换成普通PATCH绕过条件；正式上线需B01的新唯一版本与匹配API/Runtime。
- 只服务浏览器 best-effort；页面关闭不保证生成。自动竞争可以产生多次 LLM 费用，但 CAS 最终只保存一个自动结果。
- 标题不进入 native Run/state/SSE，不计入现有 Agent Run/Thread Usage 合计；前端不要创建标题消息、进度或运行。
- filename 来自已提交且通过当前 Thread 文件归属/内容校验的引用；当前存储没有独立的原 filename 事实，不宣称原名称防伪。不引入全平台 PII 脱敏。
- 前端交付完成后将T06勾选，并在T07B补独立浏览器联合Final；本交接不能替代实际实现或验收。
