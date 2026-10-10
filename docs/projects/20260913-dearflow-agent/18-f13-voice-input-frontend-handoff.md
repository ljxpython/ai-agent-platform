# F13 浏览器语音听写：前端施工交接

> 日期：2026-10-10。依据：[17 评审与任务](17-f13-voice-input-assessment.md)。
> 用户已于 2026-10-10 批准纳入实施。前端已接续完成方案实施并通过自动化与真实环境验收；非前端开发项为 0，无后端 Block。F13 任务进度只维护在 17，不复制一套勾选清单。

## 目标与边界

交给前端同事：只在共享 Chat Composer 增加主动语音听写，已确认文字进入现有草稿，用户编辑确认后使用原发送入口。普通 Chat 和 Dear Agent 使用同一实现。

不需要 Platform API/Runtime 同事新增接口、ASR 配置、音频附件、工具或消息字段。识别期间平台没有新的语音网络请求；浏览器自身仍可能使用厂商远程识别服务，所以不能对外声称音频本地处理或离线识别。

## 当前交接状态与 Worktree

- **实施位置：** `fb65/ai-agent-platform` Worktree；基线提交 `2f08c5462571cd0244a7181e5d0d1388341b79c4`。
- **已完成范围：** 原生 `useVoiceInput` 单实例实现、共享 `ChatComposer` 方案 A 极简图标与声波胶囊接入、双语国际化文案、末尾追加与 Self-echo 保护、阻断错误 Toast / 静默映射；28 项定向单测全部绿灯通过、静态代码门禁（typecheck/lint/build）全部通过、Playwright E2E 自动化测试通过；用户在真实浏览器与真实麦克风环境下验收通过。
- **非前端范围确认：** API、Runtime、GraphHarbor、数据库、依赖和后端业务代码没有 F13 改动，无后端 Block。
- **交付收口：** 本功能已在 `fb65` 完整验收闭环，准备合并回主开发分支并安全清理本 Worktree。

## 源码与改动清单

实施前读 `apps/platform-web/docs/frontend-development-playbook.md`、`control-plane-page-standard.md`、`frontend-visual-baseline-standard.md` 和 `docs/standards/worktree-development.md`。不要按原项目历史“复制独立 Dear Chat”的方案施工；当前包装关系以代码为准。

| 文件（相对仓库根） | 新增或修改 | 具体职责 |
|---|---|---|
| `apps/platform-web/src/modules/chat/composables/useVoiceInput.ts` | 新增 | 标准/WebKit 检测、原生单实例、语言、完整结果快照、stop/abort、错误、生命周期 |
| `apps/platform-web/src/modules/chat/composables/useVoiceInput.spec.ts` | 新增 | fake 原生实例，测试真实事件顺序与状态；不只测试 helper 输出 |
| `apps/platform-web/src/modules/chat/components/ChatComposer.vue` | 修改 | 消费 composable，mic/停止按钮、interim 预览、final 合并、编辑抢占、发送守卫 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 修改 | 仅把已有权限/运行状态组合为 `canDictate` 并传给 Composer；不在 Session 管理原生识别 |
| `apps/platform-web/src/components/base/BaseIcon.vue` | 修改 | 按现有路径表补 `mic`；录音中采用激活高亮/脉冲，提示“点击停止听写”，不使用易混淆的 `x` 图标 |
| `apps/platform-web/src/i18n/locales/zh-CN.ts`、`en-US.ts` | 修改 | 补 `chat.voiceInput` 所需文案；不重新国际化整个 Chat |
| `apps/platform-web/src/modules/chat/components/ChatComposer.spec.ts` | 修改 | 草稿、按钮、门禁、输入、Enter 与发送/队列不误触发；locale mock 增加可变 ref，补 UI store fixture |
| `apps/platform-web/src/modules/dear-agent/components/ChatComposer.spec.ts` | 修改 | 至少一个测试挂载本目录包装组件，确认新 prop/事件转发；当前测试导入的是公共 Composer |
| `apps/platform-web/e2e/voice-input.spec.ts` | 新增 | 页面级 fake 语音与隔离平台 fixture；不在浏览器自动化调用真实厂商 ASR |

不用修改 Dear Agent 的 Composer/Session 包装源码、`services/`、LangGraph SDK、`types/management.ts`、Runtime Context、后端 routes、`package.json` 或锁文件。新增文件只有有实际职责的 Composable、对应单测和 E2E，不搭通用音频层/Provider/配置框架。

两份 Composer 测试的 `useI18n` mock 目前只提供 `t`，新代码与 Composable 必须对 `locale` 增加安全兜底（`locale?.value ?? 'zh-CN'`），防止破坏其他未 mock `locale` 的已有单测；调用 `useUiStore` 后需按仓库现有 `vi.mock("@/stores/ui")` + `pushToast` spy 或 `createPinia` 模式补 fixture。纯浏览器 Composable 不调用 Pinia/i18n；由 Composer 传语言并展示错误。E2E fake 构造器需在 `window.__fakeSpeechRecognition` 暴露可控驱动句柄。fake 原生构造器、timer 和全局属性在每个测试后恢复，挂载组件及时 unmount，避免把新监听泄漏给已有测试。

## 接线契约

### 启动门禁与调用方

Composer 新增一个 `canDictate?: boolean`，默认 false，由真实调用方显式提供。不能复用 `canSubmitFreshOrQueue` 或 `canSendFreshMessage` 作为唯一语音门禁：`ChatSession.canSubmit` 包含“已有文字/附件”，空草稿会无法开始听写。

`ChatSession` 组合已有状态：`props.visible !== false && props.canWrite && canSend.value && !hasPendingInterrupts.value && !isSessionRunning.value && !runBudget.isThreadExhausted.value`。`canSend` 已含验证/暂停/提交动作/停止等条件，保留其作为事实源，不重新写这些判断。语音本期只供空闲时录入；运行中补充要求继续走已有键盘/队列入口。

`canDictate` 变 false 立即 cancel。入口不以单个浏览器 API 存在就越过平台门禁。只读、权限尚不可确认、Plan/HITL/澄清、停止未确认时均不能开启。空闲且可录入时，即使草稿空，按钮也能开始。

### Composable 的职责

只暴露调用方实际需要的：支持状态、`idle/starting/listening/stopping` 本地状态、final/interim 快照、错误分类及 `start/stop/cancel`。本地状态属于音频输入，不写入 SDK/Run 状态。

- 检测 `window` 存在、`isSecureContext` 和标准/WebKit 可调用构造器；后两者仅决定入口是否显示，不证明识别服务可用。不做 UA 白名单或权限预探测。
- 浏览器实例在点击 `start()` 时创建，直接在用户事件内启动；捕获构造/`start()` 同步异常。`starting` 后由原生 start 事件确认进入 `listening`，双击不创建第二实例。
- 语言直接取当前 `useI18n().locale`，本平台仅 `zh-CN/en-US`。locale 改变取消本次听写，下次点击重新创建实例；没有第三份语言配置或可持久化语言偏好。
- 每个 result 读取完整 `event.results`，按原生序列重建 final 和 interim；跨 final 段按语言适配拼接：中文直接拼接，英文在前后无空格边界补半角空格防连词；不要只取 `resultIndex` 的一个段，不把整份累计快照当增量 append，不按文字值去重。
- 普通 `end` 回空闲，不自动重启；continuous 只覆盖单次服务会话。错误终止、无语音也不重启，重新开始必须主动点击。针对 Safari 等浏览器因短停顿自发触发 `end` 的特性，回空闲并向外部提供自然结束原因，供界面展示轻量弱状态反馈，避免假死感。
- 用户正常停止用 `stop()`，允许 stopping 状态接收同一有效实例最后的 result；在 `end` 或异常后清理。停止若 5 秒没有 end，失效并 abort、保留已提交 final，显示收尾失败提示；该本地兜底不增加可配置参数，也不是识别延迟 SLO。
- cancel 先使 active 实例失效/解除回调，再调用 `abort()`；晚到 result/error/end 不得写草稿、弹 Toast、清除新实例或重启。终止与重复清理幂等，释放收尾 timer。
- scope dispose、Vue deactivated、`document.visibilitychange` 到 hidden 时 cancel；显式重新激活不自动开麦。首期不需要全局麦克风锁或 Pinia 识别 Store。

### 草稿与文本

`ChatComposer` 负责保存开始前 `baseDraft` 和最后一次自身写入的草稿，Composable 只认识原生事件，不认识项目/Thread/消息提交。

- **光标与插入契约**：首期明确**仅支持在草稿末尾追加（Append to End）**，不支持光标处局部插入，录音期间保持尾部聚焦与滚动。严禁在连续识别过程中因选区反复变动而导致光标跳动或吃字。
- **草稿重组**：每次 final 快照变化，以固定 base 和完整 final 重建：base 空则直接 final；base 末尾已有空白则直接追加 final；其他非空 base 在语音块前加一个换行。禁止改写 base 的空格/换行。interim 是单独预览，不能落盘或被发出；只有 final 进入 `update:modelValue`。
- **Self-Echo 守卫与编辑抢占**：Composer 必须维护一个 `lastEmittedVoiceDraft` ref。当 `props.modelValue` 响应式更新时，先与 `lastEmittedVoiceDraft.value` 严格比对：若相等则判定为自身 final 回流（self-echo），放行不取消；若不相等且当前正处于 starting/listening/stopping，才判定为外部修改并执行 `cancel()`。用户在 textarea 主动按键（`@keydown`、`@input`）或粘贴（`@paste`）时同步 cancel。取消不回滚已经进入草稿的 final。

`starting/listening/stopping` 期间禁用 Composer 发送/入队按钮，`handleKeydown` 和按钮处理都守卫，不自动先 stop 再 send。已有 Agent 停止动作不因麦克风状态被锁住。再点击 mic 在 starting 时取消、listening 时正常 stop；stopping 有明确取消出口。完成后恢复原门禁，并由用户主动确认发送。

当前 `ChatSession` 的 `visible=false` 模板分支会移除 Composer，切 Thread 时应测试其卸载清理。Session 池仍保活，不要据此假设“Session 一定卸载”；若后续代码改为隐藏而不卸载 Composer，需显式传递激活状态，不能继续只依赖 dispose。

## UI 与错误

mic 放在已有附件工具区旁；沿用 `BaseIcon` 和输入框按钮样式，32px 固定尺寸，tooltip 键盘聚焦可得，`type=button`、翻译后的 `aria-label`。聆听激活态展示高亮/脉冲光环（如红色指示，`aria-pressed=true`），hover 提示“点击停止听写”；停止/收尾期间再次点击执行停止；不使用容易混淆为“清空草稿”的 `x` 图标。

interim 采用短预览紧凑容器，固定放置在 `textarea` 上方（位于规划模式胶囊/附件预览下方、textarea 之前），限定最大高度（`max-h-12 overflow-y-auto text-xs leading-4 text-gray-500 bg-gray-50/80 dark:bg-dark-800/80 rounded px-2 py-1`）并带平滑淡入过渡，彻底杜绝中间转写频繁跳变引发整个输入框与聊天消息列表的上下剧烈抖动（Layout Shift）。状态文案由 `role=status` 宣布开始/结束。非 secure context 或无原生构造器时隐藏入口；存在构造器但权限/服务失败时保留入口与常规文本输入。

| 原生错误 | 分类 | 处理 |
|---|---|---|
| `aborted` | `cancelled` | 静默回退空闲，不清草稿，不弹 Toast |
| `no-speech` | `no_speech` | 未检测到语音；静默结束本次听写，状态栏弱提示“未检测到声音，已停止”，**严禁向用户弹全局 Error Toast 报错** |
| `audio-capture` | `microphone_unavailable` | 检查麦克风硬件设备；停止并弹 Toast |
| `not-allowed` / `service-not-allowed` | `permission_denied` | 浏览器/站点未获录音权限；停止并弹 Toast |
| `language-not-supported` | `unsupported_language` | 当前识别语言不可用；停止并弹 Toast，不隐式 fallback |
| `network` | `network` | 识别服务连接失败（需网络连接/代理支持）；停止并弹 Toast 提示稍后重试 |
| 其他/启动异常/收尾超时 | `unknown` | 安全失败提示；停止并弹 Toast，不输出调试堆栈 |

全局错误提示使用 `useUiStore().pushToast`，同一次识别的 error/end 不重复弹 Toast。双语 keys 覆盖：开始、停止、取消、启动中、聆听中、收尾中、四类阻断性故障（设备/权限/语言/网络）及弱状态文案（无声结束/自然结束）。`no_speech` 与 `cancelled` 严禁弹全局红框 Toast。对音频由浏览器服务处理的边界在产品交付/评审材料准确说明，不新增一套录音授权弹窗或持久设置。

## 验证要求

所有以下功能验证都是后续计划，本轮未执行。

### 单元与组件

| ID | 断言 | 测试位置 |
|---|---|---|
| U01 | 标准优先、仅 WebKit 可用、无构造器/非安全上下文/无 window 的降级 | `useVoiceInput.spec.ts` |
| U02 | 点击后才创建/start；双击只启动一次；同步异常后可恢复空闲 | 同上 |
| U03 | 一事件含多个 final；中文直接拼接、英文在无空格边界补空格；interim 更新/缩短/消失；同一快照重放不重复；两个相同 final 段均保留 | 同上 |
| U04 | stop 收尾能接收最后 final；Safari/自然 end/no_speech 触发空闲弱反馈且不重启；停止 5 秒超时清理 | 同上 |
| U05 | cancel 后旧 result/error/end 无效；A 取消再开 B，A 的 end 不能关闭 B | 同上 |
| U06 | 错误分层映射：`cancelled` 与 `no_speech` 静默不弹 Toast；四类阻断性错误弹 Toast 且同次不重复，故障不自动再开麦 | 同上 + Composer 测试 |
| U07 | locale 改变、scope dispose/deactivated/document hidden 终止；环境无 locale mock 时安全兜底默认语言 | 同上 |
| U08 | 重复 stop/cancel 清理、timer 清理，无未处理异常/悬挂音频实例 | 同上 |
| C01 | 空草稿 `canDictate=true` 能开始，和发送按钮是否可用无关 | 公共 `ChatComposer.spec.ts` |
| C02 | 普通草稿末尾追加、代码/多行/尾部空白逐字保留；只有 final 进入 model；不支持光标处局部插入 | 同上 |
| C03 | input/paste/建议/外部修改抢占取消；自身 final 的 modelValue echo 经 `lastEmittedVoiceDraft` 放行不误取消 | 同上 |
| C04 | start/listen/stop 期间 Enter/发送/queue 均不误发，结束后原逻辑恢复 | 同上 |
| C05 | 撤掉 `canDictate` 立即清理；原 run cancel 事件仍按既有规则工作 | 同上 |
| C06 | 不支持隐藏，支持但门禁 false 禁用；mic 激活高亮/脉冲、i18n/aria/tooltip 正确，不展示 `x` 图标 | 同上 |
| C07 | 真实 Dear Composer 包装转发新增 prop/model 事件，无第二实例 | Dear `ChatComposer.spec.ts` |
| C08 | 真实 Session caller 推导门禁；空草稿可开、审批/澄清/只读/停止未确认/后台不可开；`visible=false` 清理 | E01/E03 在真实页面验接线，不能仅手动 setProps 假设成立 |

### 浏览器与真机

| ID | 场景与预期 |
|---|---|
| E01 | `page.addInitScript` 注入 fake 标准与 WebKit 构造器并在 `window.__fakeSpeechRecognition` 暴露驱动句柄；事件驱动页面 final/interim，确认没有自动 send/queue 请求 |
| E02 | 无构造器和 fake 权限/网络失败，文本输入仍可用，阻断错误提示一次，no_speech 不弹 Toast，不触发自动重启 |
| E03 | 在真实会话池切换 A/B、离开页面、目标变化、撤权/审批门禁；A 旧事件不能修改 A/B 的新草稿或抢用麦克风 |
| E04 | fake 听写确认文字后，用户主动发送；使用隔离平台现有 fixture 的普通文字 Run，验证无新增音频字段，Thread 中用户文字只出现一次且有回复。这是原文字链路冒烟，不验证 ASR 或新增后端能力 |
| E05 | 390×844、1024×768、1440×900、浅/深主题；interim 上方容器与按钮无重叠，无明显 Layout Shift 抖动，键盘停止与 tooltip 可达；保留现有队列、附件、Plan/HITL 回归 |
| M01 | 在目标 secure origin、实际使用的 Chrome/Edge/Safari 逐个检查 API、权限和中英文真实识别；记录浏览器/OS/版本和网络，不由 Chromium/同内核推断其他浏览器可用 |
| M02 | 真机拒绝/撤销权限、无麦克风、静音、断网；按钮恢复、无重复提示、草稿保留；不支持浏览器仅验证文本降级 |
| M03 | 停止、切会话、隐藏页签、离开/撤权后核对浏览器麦克风指示关闭；不做后台或无限续录；核对目标环境的音频处理要求 |

### 运行方法

当前 Worktree 必须使用 `scripts/local-stack.sh` 管理隔离资源，不能复用别的 `.venv/node_modules` 或默认回退主工作区。未来需要安装/联调时，从仓库根执行下面的文档命令；文档不带执行代理前缀：

```bash
bash "scripts/local-stack.sh" init
bash "scripts/local-stack.sh" deps
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" status
```

`deps` 按现有 frozen 锁文件安装本 Worktree 的三服务依赖；真实 E04 需要该环境三服务及可执行 Agent。只跑单元测试无需启动全栈。Fake 语音在 browser context 内，不从公共脚本运行真实录音。

在 `apps/platform-web` 内，实施完成后执行：

```bash
pnpm test:run "src/modules/chat/composables/useVoiceInput.spec.ts" "src/modules/chat/components/ChatComposer.spec.ts" "src/modules/dear-agent/components/ChatComposer.spec.ts"
pnpm typecheck
pnpm lint
pnpm build
pnpm test:e2e "e2e/voice-input.spec.ts" --project chromium
```

Session caller 接线由真实页面 E01/E03 验证；最终共享 Composer 交付前运行一次 `pnpm test:run`。先跑定向验证，未改代码且已通过后不重复全量回归。保留测试 fixture 清理、Worktree 生成地址和 Playwright 配置的校验，不硬编码 3000/2142/8123 或独立新起第二套 Vite。

## 交付回执

实施已于 2026-10-10 完成：
- 业务代码：`useVoiceInput.ts`、`ChatComposer.vue`、`ChatSession.vue`、`BaseIcon.vue`、`zh-CN.ts`、`en-US.ts`。
- 测试代码：`useVoiceInput.spec.ts`（U01-U08）、`ChatComposer.spec.ts`（C01-C06）、Dear Agent `ChatComposer.spec.ts`（C07）、`e2e/voice-input.spec.ts`（E01, E02, E04, E05）。
- 质量门禁：定向单测 28/28 passed、typecheck 0 error、lint 0 error、build 打包成功、Playwright E2E 2/2 passed。
- 验收结论：前端接线与自动化已验，真实浏览器识别待真机抽验（M01-M03）。不因浏览器环境不支持扩展后端 ASR。已同步 17、FEATURES 与 CONTEXT。
