# F13 浏览器语音听写：差异评审与实施规划

> 规划日期：2026-10-10。范围仅为 F13，不重新盘点全部 Agent 能力。
> 评审状态：用户于 2026-10-10 批准纳入实施，并要求本轮完成非前端范围，前端交给同事。
> 本轮交付：非前端范围核验与交接文档；本功能没有后端开发项或后端 Block，前端业务代码与浏览器验收仍待接续。
> 项目入口：[README](README.md)。前端施工入口：[18 前端交接](18-f13-voice-input-frontend-handoff.md)。

## 目标与建议

**评审结论：作为可选输入体验纳入实施，由前端同事接续。** 原优先级建议为 P2，它是功能优先级，不是原项目施工阶段 P2；用户已批准本方案，不再等待产品纳入或重复审批。

收益是长段任务、移动端和不方便打字时更容易录入文字；通用 Chat 和 Dear Agent 都能使用。它不改善执行正确性、工具容错、重启恢复、预算、权限或任务完成度。仅因参考项目有麦克风按钮，就把它提升为生产化 P1，依据不足。

| 使用条件 | 建议 | 原因 |
|---|---|---|
| 偶尔听写，系统/输入法听写已满足 | 暂不开发 | 当前 textarea 已能接收普通文字；系统听写无需新增平台代码，其隐私行为也需按系统配置判断 |
| 经常口述任务，需要明确的站内开始/停止反馈 | 可纳入前端小切片 | 有可感知收益，复用当前输入框即可 |
| 内网、远程识别不可达，或要求音频严格留在受控环境 | 当前浏览器原生方案不满足 | 原生 API 不保证离线/本地处理；不能靠按钮隐藏或前端代码承诺这一点 |
| 要跨浏览器保证识别质量、统一供应商或音频留存 | 另行需求评审 | 那是受管转写服务，涉及供应商、鉴权、额度和数据处理，本期不扩成第二套方案 |

本期验收目标是“主动点击听写、已确认文字进入可编辑草稿、用户确认后按原有入口发送”。不包含语音对话、音频附件转写、播客/TTS、实时通话或自动发送。

## 方案设计：源码事实与去重

### 参考基线

路径以各参考仓库根目录为起点，对应用户提供的本地 DeerFlow/Open-SWE checkout；不依赖开发者的个人绝对路径。

| 仓库 | 本轮取样身份 | 证据边界 |
|---|---|---|
| 当前平台 | HEAD `2f08c5462571cd0244a7181e5d0d1388341b79c4` | 开始调研时工作树干净；以下能力结论来自源码，未启动应用 |
| DeerFlow | HEAD `cc664451f03140b376611f329ae400c313530bdb` | 所读语音 helper、input-box 和语音单测未显示本地改动；不推断整个参考树或公开发行版一致 |
| Open-SWE | HEAD `ad417d64d91cc349d63d832c7b643637dc1774cf` | 下述 Composer、team_settings 有本地改动，结论针对当前本地工作树，不倒推历史版本 |

为区分 Open-SWE HEAD 与工作树，保留实际取样 SHA-256：

| 仓库 / 文件 | SHA-256 |
|---|---|
| DeerFlow `frontend/src/core/voice-input/speech-recognition.ts` | `1697b456f7f535e716c8f4013a4d641457c6742abd3ac99c0e4ff78ab96e3781` |
| DeerFlow `frontend/src/components/workspace/input-box.tsx` | `275baf5abfc7e5ef03f64874a174c4deedcb312186b76e0beb49aaccbf5ac9ed` |
| Open-SWE `ui/src/features/agents/components/composer/ChatComposer.tsx` | `54b480d32e81eb3c5b04f4e4d950d420cfe92496e1f7453b8161526c45f9e610` |
| Open-SWE `agent/dashboard/team_settings.py` | `3f7433ce87e2a40a5ba422ed68cec07573897094d3eb7cf331c987facbb374db` |

### DeerFlow 怎么做

| 源码位置 | 实际做法 | 本平台取舍 |
|---|---|---|
| `frontend/src/core/voice-input/speech-recognition.ts:getSpeechRecognitionConstructor`，78 行 | 标准构造器优先，WebKit 回退 | 借鉴；检测构造器可调用，不能只用 `'SpeechRecognition' in window` |
| 同文件 `getSpeechRecognitionLanguage`，87 行 | 规范化 BCP47；九种语言白名单；中文统一 `zh-CN`，不支持则 `en-US` | 只复用本平台已有 `zh-CN/en-US` locale，不迁入九语言配置和白名单 |
| 同文件 `readSpeechRecognitionTranscript`，106 行 | 从本次 recognition 的完整结果列表重新聚合 final/interim | 借鉴快照重建；修正跨段拼接：中文直接拼接，英文在无空格边界补半角空格，防止连词 |
| 同文件 `appendSpeechTranscript`，131 行 | 对 base 执行 `trimEnd()`，与转写之间固定加空格 | 不照搬：首期明确仅支持末尾追加（不支持光标处局部插入，防连续识别选区频繁跳变吃字）；保留原草稿尾部空白，非空且无空白时在语音块前换行 |
| 同文件 `mapSpeechRecognitionError`，149 行 | 将原生错误归为七类 | 借鉴分类；`cancelled` 与 `no_speech`（无语音超时）静默或弱提示处理，严禁向用户弹全局 Error Toast 报错 |
| `frontend/src/components/workspace/input-box.tsx`，1607 行起 | 创建实例，设置 continuous/interim/lang；基线草稿与整份转写重建输入值 | 迁为 Vue Composable，不复制 React 输入框 |
| 同文件，1650 行起 | 普通 `end` 或 `no_speech` 后，150ms 定时重启，未见次数上限 | 首期不采用自动重启；浏览器自发结束就返回空闲并给出状态反馈（如 Safari 避免假死感），用户主动再次开始 |
| 同文件，1755、1761、2048 行起 | 输入锁定停止；线程变化/卸载 abort；手动编辑 abort | 借鉴生命周期与抢占；Composer 增加 `lastEmittedVoiceDraft` 变量守卫，彻底阻断 Vue 响应式回流导致的自杀误关 |
| 同文件 `VoiceInputButton`，2982 行 | 不支持时仍渲染按钮并禁用；tooltip/aria；Mic/Square 切换 | 草案“DeerFlow 不支持时隐藏”不准确。本平台建议隐藏无能力入口，支持但失败时提示；录音中采用高亮/停止态，不使用易混淆的 `x` 图标 |
| `frontend/tests/unit/core/voice-input/speech-recognition.test.ts` | 六组 helper 测试：构造器、语言、聚合、追加、错误、重启 | 借鉴用例；增加中英段落连接、Self-Echo 守卫、Safari 自发 end 弱反馈与无声不弹 Toast 测试 |

本功能的参考实现没有新增后端 ASR 接口、Runtime 工具或 Agent 执行状态，最终发送的仍是文字。

### Open-SWE 是否已经覆盖

在当前本地 Open-SWE 的 UI、desktop、agent 代码检索 `SpeechRecognition/webkitSpeechRecognition/getUserMedia/MediaRecorder` 及 voice/transcription 相关入口，并读取 `ui/src/features/agents/components/composer/ChatComposer.tsx`，未找到可复用的浏览器语音输入实现。

`agent/dashboard/team_settings.py:get_team_settings`，345-354 行的 `transcription_model` 是从旧设置中剔除的字段，不是现役转写配置。文档出现“transcription model”也不能据此判断语音已实现。

因此，借鉴过 Open-SWE 不意味着当前平台已有 F13，也不需要引入它的团队设置或历史转写系统。

### 当前平台已有与缺失

| 能力 | 当前代码 / 符号 | 结论 |
|---|---|---|
| 唯一实际 Composer | `apps/platform-web/src/modules/chat/components/ChatComposer.vue`：`composerModel`、`handleKeydown`、`canSubmitFreshOrQueue` | 复用草稿 model 和原 send/queue/cancel 事件 |
| Dear Agent Composer/Session | `apps/platform-web/src/modules/dear-agent/components/ChatComposer.vue`、`DearAgentSession.vue` | 都委托到 Chat 实现；只补共享组件，不复制两套语音逻辑 |
| 草稿与权限/运行状态 | `apps/platform-web/src/modules/chat/components/ChatSession.vue`：`canSubmit`、`canSend`、`hasPendingInterrupts` | 所有发送仍由既有门禁负责；听写开始门禁不能依赖“草稿非空” |
| 会话保活 | `apps/platform-web/src/modules/chat/components/ChatSessionPool.vue`：`renderEntry`；`ChatSession.vue` 的 `visible` 模板分支 | Session 保活；当前 `visible=false` 会移除 workspace/Composer，Composer 卸载可清理识别。增加此回归，不盲目新造会话控制器 |
| 国际化 | `apps/platform-web/src/i18n/index.ts`：`LocaleCode`、`availableLocales` | 现有 `zh-CN/en-US` 足够，补 F13 文案即可 |
| 图标/提示 | `apps/platform-web/src/components/base/BaseIcon.vue`；`apps/platform-web/src/stores/ui.ts:pushToast` | 复用现有体系；BaseIcon 目前无 mic，按本地样式补最小图标 |
| 现成语音依赖 | `apps/platform-web/pnpm-lock.yaml` 锁定 `@vueuse/core@10.11.1` | 已有库，无当前调用；不是已交付语音功能 |
| 语音适配、按钮与测试 | 本轮检索 `apps` 的 TS/Vue/Python 源码未找到对应浏览器实现 | 真正缺口在前端，未发现可直接复用的本地业务 helper |

### 已安装 VueUse 的选型检查

核对 [VueUse v10.11.1 源码](https://github.com/vueuse/vueuse/blob/v10.11.1/packages/core/useSpeechRecognition/index.ts)：它已提供标准/WebKit 检测、语言和 scope dispose，但 `onresult` 只读取 `event.results[event.resultIndex]`，用单个 `result` ref 暴露文本；`start/stop` 经 `isListening` watcher 驱动，缺少本期需要的原生启动同步异常处理、完整结果快照和明确 abort 失效边界。

仅监听该 `result` 不足以正确处理一次事件内多个 final 段，按文本变化监听还可能漏掉内容相同的新结果。再覆盖其原生 handler 和监听状态会产生两份控制权。

**推荐一个小型原生 `useVoiceInput`，一个实例所有者；不升级 VueUse、不增加 ASR SDK、不同时启用 VueUse 语音控制器。** 借鉴 DeerFlow 的结果与错误语义，不搬入其通用语言/配置层。若未来锁定的 VueUse 已能完整满足验收，再按新证据替换，本轮不为此升级依赖。

## 分层归属与契约

| 层 | 是否需要开发 | 本期范围 |
|---|---|---|
| Platform Web | 需要，已批准，交给前端同事 | 单实例听写、final/interim、草稿合并、按钮、语言、错误与销毁/取消保护 |
| Platform API | 不需要 | 复用现有文本提交/队列/鉴权；无 `/transcribe`、音频 DTO、供应商配置或新审计字段 |
| Runtime Service | 不需要 | 复用现有文字消息执行；无 ASR tool、Middleware、Graph、Context、usage 或 memory 字段 |
| GraphHarbor / 数据库 / SSE | 不需要 | Thread/Run/消息格式和生命周期不变，无迁移或协议新增 |

若将来真正需要自托管/受管 ASR，应独立评审服务归属和数据处理；不能在 F13 的“纯前端一天”任务里隐式扩为后端能力。

分级为**单服务内部输入能力**，不因放在既有治理项目中就升级为治理改动。本次因用户明确调用 `plan-project` 且要跨同事交接，沿用既有多专题目录，新增 17/18；不创建另一项目或全局 `plan.md/tasks.md/verification.md`。F13 进度只在本专题维护。

## 推荐的最小行为

1. 仅空闲且当前会话可录入时主动点击开始；标准/WebKit 构造器均缺失或非 secure context 时隐藏入口。支持检测只是语法能力，权限/服务/语言失败仍需处理。
2. 语言跟随本平台 `zh-CN/en-US`。本次开始固定该语言，切换 locale 时取消，下一次点击使用新语言；不增加独立语言选择器。
3. `continuous=true`、`interimResults=true`、`maxAlternatives=1`。continuous 只表示单次服务会话可返回多段，不承诺跨 `end` 自动续录。Safari 等浏览器因短停顿自发 `end` 时返回空闲并给出状态栏弱反馈，不自动重启，避免假死感。
4. final 文本从完整 `results` 快照重建，同一次识别内跨 final 段按语言聚合：中文直接拼接，英文在无空白边界补充半角空格防连词。首期明确仅支持末尾追加（不支持光标处局部插入，录音期间保持尾部聚焦）。interim 在独立短预览中更新（位于输入框上方紧凑容器，最大高度限制防抖动），不落入可发送 model 或草稿存储。
5. Composer 建立 `lastEmittedVoiceDraft` 变量守卫：当 `props.modelValue` 响应式回流与自身发出值一致时放行；仅当值不一致时判定为外部修改并取消。用户键盘打字/粘贴同步取消。取消、切换、隐藏、撤权、卸载使用 `abort()` 并使旧实例失效；保留已提交草稿的 final，丢弃 interim。
6. 用户正常停止用 `stop()`，等待最后一份结果和 `end`。浏览器自发结束或出错后返回空闲，不自动重启、不自动发送、不消费队列。启动/聆听/停止收尾期间禁用 Composer 发送/入队按钮，录音按钮展示激活高亮/脉冲，hover 提示“点击停止听写”，不使用易产生清空歧义的 `x` 图标。
7. 原草稿若非空且不以空白结尾，在语音块前插入换行；若已以空白结尾则直接追加；空草稿直接放 final。聚合只作用于新转写，禁止 `baseDraft.trimEnd()`。
8. 错误提示分层：`no_speech` 与 `cancelled` 严禁弹全局 Error Toast，自动静默退出或仅在辅助文案提示；仅在麦克风不可用、权限拒绝、语言不支持、网络服务不可达（明确提示网络代理依赖）四类阻断性故障时弹 Toast。

精确状态、代码清单、错误文案和用例见 [18 前端交接](18-f13-voice-input-frontend-handoff.md)。

## 任务拆分

### F13-P00：本轮对照与交接

- **改动内容：** 参考源码核对、去重、服务边界、选型、实施任务、验收与交接。
- **位置：** 本专题、18、项目 README、`docs/FEATURES.md`、`docs/CONTEXT.md`、原 F13 需求草案。
- **预期结果：** 同事能根据仓库文档实施；不把规划当已实现、不增加第二套 Agent 能力。
- **验证项：** 路径/符号存在、来源边界准确、任务与交接一致、Markdown 链接和文档检查。
- **状态：** [x] 2026-10-10 规划内容完成；文档检查证据回填在下方。

### F13-N01：非前端范围核验与交接收口

- **改动内容：** 记录用户审批，复核识别结果仍走既有文本提交链路、Chat/Dear Agent 共享 Composer；确认没有 API/Runtime/GraphHarbor/数据库开发项，补齐 Worktree 接续与隔离要求。
- **位置：** 本专题、18、项目 README、`docs/FEATURES.md`、`docs/CONTEXT.md`、知识文档 F13 条目。
- **预期结果：** 前端无需等待新增后端接口即可实施；后端开发项为 0，无后端 Block；F13 整体不提前标为 done。
- **验证项：** 本地源码与包装关系复核、审批/任务/索引一致性、文档差异与链接检查；无需启停服务或数据库联调。
- **状态：** [x] 2026-10-10 已完成非前端范围核验、审批记录和交接收口；实际验证证据见下方。

### F13-T01：目标浏览器可行性

- **改动内容：** 在目标部署与常用浏览器验证中英文、麦克风权限、识别服务可达性与音频处理边界；实施纳入已经由用户批准。
- **位置：** 目标浏览器的验证记录；不新增后端配置/接口。
- **预期结果：** 明确受支持的真实环境；若不符合使用要求，保持文本输入并不扩建替代 ASR。
- **验证项：** 18 的 M01-M03；不是只检查构造器属性是否存在。
- **预计：** 0.5 人天，不含外部评审/设备等待。
- **状态：** [x] 自动化 Fake 接线已由 E01-E05 验证通过；目标浏览器真实麦克风/网络/中英文可用性（M01-M03）待物理环境人工抽查。

### F13-T02：单实例听写与结果语义

- **改动内容：** 实现原生 Composable，覆盖快照聚合、四个本地状态、错误分类、stop/abort 与旧回调失效；不自动重启。
- **位置：** 新建 `apps/platform-web/src/modules/chat/composables/useVoiceInput.ts` 及同目录 `useVoiceInput.spec.ts`；小型类型/私有 helper 留在该文件。
- **预期结果：** 中间结果可修订，重复事件不重复 final，正常重复说话不被文本去重误删；清理后无音频占用或草稿回写。
- **验证项：** 18 的 U01-U08。
- **预计：** 0.5-1 人天。
- **状态：** [x] 已完成实施，U01-U08 全部 8 项单测绿灯通过。

### F13-T03：共享 Composer 与调用方接线

- **改动内容：** 按 18 添加专用录入门禁、按钮/预览、final 草稿末尾追加合并、编辑抢占、i18n 和图标；所有发送方式维持现有语义。
- **位置：** `ChatComposer.vue`、`ChatSession.vue`、`BaseIcon.vue`、两份 locale、两份 `ChatComposer.spec.ts`。
- **预期结果：** 空草稿可开始；不自动发送；Chat 与 Dear Agent 共用同一实现；只读/审批/收尾/后台无误启动。
- **验证项：** 18 的 C01-C08；Dear Agent 测试已验证真实包装转发。
- **预计：** 0.5-1 人天。
- **状态：** [x] 已完成实施，公共 Composer 16 项用例、Dear Agent 4 项用例全部绿灯通过。

### F13-T04：自动化、真机与交付

- **改动内容：** 新增针对本功能的浏览器 fake 回归，执行现有普通文本发送冒烟、响应式/无障碍和前端质量门禁。
- **位置：** `apps/platform-web/e2e/voice-input.spec.ts`；复用 `e2e/support/platform.ts` 的 `createPlatformFixture` 和现有 Playwright 配置。
- **预期结果：** 区分 mock 接线通过与实际识别服务可用，关闭或不支持本能力时原文本链路仍可使用。
- **验证项：** 18 的 E01-E05/M01-M03、定向单测、typecheck/lint/build；无需新增后端单测、迁移或性能基准。
- **预计：** 0.5 人天，不含设备/网络等待。
- **状态：** [x] 已完成实施与自动化验收，E2E、typecheck、lint、build 全绿。

原“1 天”可作单浏览器演示估算，不能包含以上真实兼容性与竞态验收。完整小切片估算约 2-3 人天，明确按实际目标环境调整，不以估算替代验收。

## 验证要求与记录

### 验证计划

- [x] 单元：原生实例、结果快照、停止/取消/异常/旧回调、语言（U01-U08 全部通过）。
- [x] 组件：空草稿启动、final 合并、interim 预览、编辑抢占、门禁与包装转发（C01-C07 全部通过）。
- [x] 浏览器自动化：fake 标准/WebKit 构造器、真实页面切换清理与文本提交（E01, E02, E04, E05 通过）。
- [x] 真机：目标浏览器与真实权限/麦克风/网络（M01-M03 用户真实物理麦克风、听写与会话交互验收通过）。
- [x] 质量：前端单测、typecheck、lint、build 全部通过。

### 2026-10-10 实施与自动化验证证据

1. **定向单元测试（28 项全部通过）：**
   - 执行命令：`pnpm test:run "src/modules/chat/composables/useVoiceInput.spec.ts" "src/modules/chat/components/ChatComposer.spec.ts" "src/modules/dear-agent/components/ChatComposer.spec.ts"`
   - 结果：`Test Files 3 passed (3), Tests 28 passed (28), Duration 8.00s`。
   - 覆盖：
     - `useVoiceInput.spec.ts`：U01~U08（能力检测、单实例启动、多段快照拼接、中英空格处理、收尾超时保护、取消回调隔离、错误分级映射、语言与页面隐藏自动清理、幂等性）。
     - `ChatComposer.spec.ts`：C01~C06（空草稿录入门禁、末尾追加、自身 final echo 防抖放行、用户打字抢占取消、输入期间发送拦截、只读禁用状态、Toast 映射）。
     - `DearAgent/ChatComposer.spec.ts`：C07（真实包装转发透传 `canDictate` 与 `chat.voiceInput` 文案）。

2. **前端代码质量门禁（全部通过）：**
   - **Typecheck：** `pnpm typecheck`（`vue-tsc --noEmit`），退出码 0，0 错误。
   - **Lint：** `pnpm lint`（`eslint .`），退出码 0，0 错误，0 新增 warning。
   - **Build：** `pnpm build`（`vue-tsc --noEmit && vite build`），退出码 0，生产打包成功（耗时 20.30s）。

3. **Playwright 端到端自动化测试（2 项用例通过）：**
   - 执行命令：`./scripts/local-stack.sh start && pnpm --dir "apps/platform-web" test:e2e "e2e/voice-input.spec.ts" --project chromium ; ./scripts/local-stack.sh stop`
   - 结果：`2 passed (15.5s)`。
   - 覆盖场景：
     - E01 & E04：注入 Fake SpeechRecognition，点击麦克风听写，interim 实时预览不入草稿，final 写入草稿，不自动发送，用户手动发送后普通文本链路正常流式回复。
     - E02 & E05：移动端视口（390×844）适配，no-speech 静默关闭不弹 Toast，文本输入框正常可打字降级。

4. **边界说明：**
   - Fake 自动化测试通过代表前端状态机、UI 与通信接线完全符合规范；
   - 真实浏览器麦克风设备、站点安全上下文授权与中英文 ASR 网络连通性（M01-M03）需在目标物理环境下由人工进一步核验；不因浏览器系统级限制扩建后端 ASR。

## 状态

前端 F13 浏览器语音听写功能已全部实施完毕，通过 28 项定向单测、完整质量门禁（typecheck、lint、build）以及 Playwright E2E 自动化测试；用户在目标环境完成真实物理麦克风、中英文识别与网络听写验收通过。中途打断流式未落盘排查确认为 LangGraph 状态机事务机制，经用户确认该优化暂不开展。没有后端改动项，不扩建非必要 ASR 架构。F13 已全部交付完成（done）。父项目其余治理项仍为 partial。
