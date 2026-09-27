# SSE 专项 — 验证执行包

> 本页定义实施验收，已执行证据见第6节。Phase证据和Final结论分区记录；未验证场景不能按通过计算。

## 1. 固定输入与断言矩阵

合成fixture只用测试ID和占位秘密。message/tool/input事件payload从现有sdk-chain.test.ts及锁定协议类型构造，外层沿用plan3.1；实际三服务样例单独采集并脱敏，不能把合成payload标成真实抓包。

| ID | 输入/步骤 | 必须断言 |
|---|---|---|
| V01 正文 | 同轮正文A→工具→正文B→终态 | 与实施前同夹具输出结构一致；A/B按现有规则保留，无新增过滤/重排 |
| V02 思考 | reasoning增量→用户折叠/展开→正文→终态 | 默认与手动状态均等于基线，无新增终态自动折叠 |
| V03 工具 | 同名tool的call-a/call-b；参数分块；a失败、b成功、Run成功 | 各ID一张卡；tool失败不改Run成功；参数/结果及现有卡片样式不变 |
| V04 子任务 | 两个同名task、不同namespace；发现事件晚于工具 | 各订阅命中正确namespace，根/子消息不串，不用name猜测 |
| V05 富文本 | 分片代码围栏/表格、产物链接、恶意HTML | 渲染/复制/安全处理与用户当前基线一致，无新渲染器 |
| V06 阅读 | 上滑到旧消息、展开卡片、输入未发草稿/附件→切B→A | 滚动与锚定模式、卡片状态、draft/附件/参数保持；后台token不抢焦点 |
| V07 真保活 | A运行，记录instanceId和命令计数→B→其他同项目页；继续推A token/终态/interrupt→A | A实例未dispose；后台仍消费；切回不重建SDK、不重放run.start；审批仍待人工 |
| V08 清理 | A/B存活→换项目/登出/epoch变更/离开Workspace；旧HTTP/event迟到 | 全部旧scope连接/监听/定时器结束；迟到结果零写入；cancel命令数不增加 |
| V09 断线 | HTTP200建立后断网/EOF/空200/45秒无字节；持续心跳无token对照 | 自动只重试stream；最多5次；健康30秒才重置；持续心跳不超时；Run不变失败 |
| V10 尾部 | lifecycle连接先送r1 completed，内容连接后送r1最终values/checkpoints；r2开始后再送r1终态 | 最终数据不被completedRunIds过滤；r2状态/动作不被r1清理 |
| V11 回放 | 同event_id重复；共享订阅扩容；不同namespace收到相同回放；远端开始r2 | 每逻辑订阅不重复应用，扩容可获取此前历史；新远端Run正常发现；不全局注入since |
| V12 HTTP | 握手401→刷新→200、401→401、403、404、429、502、错误content-type | 刷新仅一次；权限停止且清缓存；429遵守限额；502限次；机器code/status不丢；无原文 |
| V13 410 | since:9遇watermark:10→410 cursor_expired；同时两个流触发；state请求中r2开始 | 单飞恢复；失效since不反复提交；旧快照不覆盖r2；出现安全缺失提示；命令零自动重放 |
| V14 分片 | 每个字节切分UTF8/CRLF/多行data；心跳；合法未知JSON/custom字符串 | 与整帧处理等价；字段语义保持，敏感字段脱敏；心跳不变业务事件 |
| V15 大帧 | 原始帧8MiB与8MiB+1字节；单chunk包含多个小帧合计超过8MiB | 等于限额可处理，超限关闭；多小帧不误报；无完整响应缓冲 |
| V16 坏帧 | 非JSON data含fixture-secret；损坏UTF8；外层array冒充Protocol；EOF残帧 | 下游/用户/日志均无fixture-secret原文；无伪造Run error；分类日志正确；客户端有界恢复 |
| V17 双入口 | Protocol对象；标准Run JSON数组/标量；无data终止事件；Run join last_event_id | 各自保持契约；标准Run未被Protocol校验误杀；不把last_event_id改since |
| V18 关闭 | 客户端Abort、解析失败、超限、正常EOF、上游握手403/410/502 | iterator/client均释放；握手错误为真实HTTP状态；已开始流不追加HTTP Envelope |
| V19 暂停恢复 | 首次握手失败→手动恢复；5次耗尽→恢复；过滤并集旋转失败；pending ready时dispose | 同SDK/registry恢复；逻辑订阅未关闭；手动调用单飞；scope结束ready settle且不死锁 |
| V20 隔离 | A创建Thread ACK前切B；后台A onAccepted/refresh/fork；queue延时中隐藏；403后回A | 不改B URL/草稿/附件；隐藏本地队列不新提交；权限失败无缓存闪现；同Thread跨入口仅一个实例 |
| V21 取消/审批 | cancel ACK后server仍running→终态；审批ACK未知→核实；多个interrupt部分解决 | 不伪造终态、不自动批准；动作重试复用原ID/body；剩余审批仍可见 |

每个用例至少记录：应用/SDK/patch版本、scope/instanceId测试标识、物理流开关计数、run.start/input.respond/cancel次数、最终消息ID/工具ID/Run状态。不要输出token、完整Authorization或真实模型秘密。截图中的时间/动画噪声可遮罩，正文/卡片/折叠/审批不得遮罩掩盖回归。

## 2. 单元与真实SDK隔离测试

以下命令从仓库根目录执行；测试文件按tasks创建后才能运行。文档中不带本机rtk前缀。无需生产服务、模型密钥或数据库变更。

```bash
"apps/platform-api/.venv/bin/python" -m pytest "apps/platform-api/tests/test_runtime_gateway_event_redaction.py" "apps/platform-api/tests/test_runtime_upstream_errors.py" -q
pnpm --dir "apps/platform-web" exec vitest run "src/modules/chat/run-actions.test.ts" "src/modules/chat/sdk-stream-recovery.test.ts" "src/modules/chat/composables/useChatSession.spec.ts" "src/services/langgraph/client.spec.ts"
pnpm --dir "apps/platform-web" exec vitest run "src/modules/chat/composables/useChatSessionPool.spec.ts" "src/modules/chat/components/ChatSessionPool.spec.ts" "src/modules/chat/pages/ChatPage.spec.ts" "src/modules/dear-agent/pages/DearAgentPage.spec.ts" "src/layouts/WorkspaceLayout.spec.ts"
pnpm --dir "apps/platform-web" typecheck
```

sdk-stream-recovery.test.ts不得mock useStream/ThreadStream；使用真实安装SDK及注入fetch、ReadableStream、可控计时器模拟传输。池测试至少一组挂真实ChatSession+SDK，证明不是仅测试Map未删对象。页面常规单测可以继续mock外部依赖。

补丁验证：干净隔离安装中运行pnpm install --frozen-lockfile并执行上述SDK测试，确认patch应用；同时ESM/CJS导入。既有namespace和终态后投影测试全部保留。不要在有用户未提交工作树内删除node_modules或用重装覆盖问题作为验证捷径。

## 3. Web→真实API→受控上游综合测试

### 测试夹具交付契约

新增apps/platform-api/tests/fixtures/sse_contract_server.py，仅测试进程启用：
- 必须RUN_SSE_CONTRACT_E2E=1；仅监听127.0.0.1:12144，环境不满足立即拒绝启动。
- 使用真实API app/router、错误转换和SSE脱敏器；权限/目录数据在临时测试存储准备。受控上游通过依赖替换提供stream/state/Run/command响应；不调用真实Runtime、模型或生产DB。
- 复用错误专项fixture已有装配，补SSE脚本；没有该fixture时S10必须先提供最小app依赖装配，不把创建生产项目当替代。
- 内部测试控制API：POST /__test/reset重置仅本进程数据；POST /__test/scenario接受V编号；POST /__test/advance推进已命名事件；GET /__test/counters返回订阅、命令、状态读取及close计数。这些路由只在fixture app注册，不进入生产router。
- fixture token为固定测试值；账号A/B、项目P/Q、Thread A/B及Dear入口按真实平台接口形状返回。前端依然运行真实路由/SDK/消息组件，不用page.route伪造最终卡片。
- SSE脚本支持LF/CRLF、任意chunk分割、双连接错序、错误状态、EOF、挂起、回放、慢读、8MiB边界；所有事件由advance确定推进，不靠真实模型时序碰运气。
- 进程退出释放自有临时资源；不得扫描/删除真实项目或用户文件。

三个终端分别执行：

```bash
RUN_SSE_CONTRACT_E2E=1 "apps/platform-api/.venv/bin/python" "apps/platform-api/tests/fixtures/sse_contract_server.py"
```

```bash
VITE_PLATFORM_API_URL=/ VITE_DEV_PROXY_TARGET=http://127.0.0.1:12144 pnpm --dir "apps/platform-web" dev --host 127.0.0.1 --port 13002
```

```bash
RUN_SSE_CONTRACT_E2E=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:13002 pnpm --dir "apps/platform-web" exec playwright test "e2e/sse-event-contract.spec.ts" --project chromium --workers 1
```

该本地HTTP/1.1夹具仅跑不超过2个同时活跃Thread的确定性功能；8Thread容量另在HTTP/2环境验证，不能用连接排队结果冒充业务故障或容量通过。实施前后同夹具截屏对比，禁止无解释update-snapshots覆盖差异。测试数据/控制路由不允许通过线上请求头启用。

## 4. 真实三服务、安全与容量验收

必须由实际测试环境信息填实，不能写死当前开发端口为生产：
- 使用隔离的platform-api/runtime-service及Web部署，固定当前GraphHarbor post33/SDK版本，已有授权graph/model，专用测试账号及两个隔离项目。敏感凭据仅环境变量传入，不入文档/日志。
- 复用e2e/support/platform.ts，已有sdk-chain.test.ts运行真实Vue SDK→API→Runtime链路。该fixture会创建/清理测试项目，执行前需符合测试环境的数据操作授权；本轮没有执行。
- 新增sse-event-contract.spec.ts的@real场景，RUN_SSE_REAL_E2E=1启用，复用同一fixture；未设置时明确skip，不假报通过。
- 采集同Run的上游→API→浏览器三段脱敏样例，普通回复/工具/审批/取消至少各一组，关联thread_id/run_id/event_id及已有request_id/trace_id。保留字节分片与业务ID区别。

```bash
PLATFORM_CHAIN_TEST=1 pnpm --dir "apps/platform-web" exec vitest run "src/modules/chat/sdk-chain.test.ts"
RUN_SSE_REAL_E2E=1 pnpm --dir "apps/platform-web" exec playwright test "e2e/sse-event-contract.spec.ts" --grep "@real" --project chromium --workers 1
```

以上两条命令要求预先设置PLATFORM_TEST_URL、PLATFORM_TEST_USERNAME、PLATFORM_TEST_PASSWORD及PLAYWRIGHT_BASE_URL到已批准测试环境；缺失隔离环境不得执行会默认回落本机真实服务的fixture。真实测试覆盖普通流、工具失败后成功、HITL、多轮、取消、切Thread持续消费、断网后服务端继续执行。410可控触发在夹具完成，不为测试去修改Runtime保留策略/清生产事件。

容量验收目标（设计门槛，非当前已通过指标）：
1. 同一标签页8个活跃Thread并发，累计访问30条，持续30分钟。真实浏览器Network记录nextHopProtocol为h2/h3；不能只看代理到上游的协议。
2. 稳态每条已订阅Thread物理SSE不超过2条；单条过滤并集旋转可短暂3条，ready后5秒内回到2条。同时旋转上限按3×已订阅Thread核查，不能随着打开卡片持续增殖。
3. 工作区仍可切换Thread、输入，后台token/终态均收到，无额外run.start。退出scope后5秒内应用登记的controller/timer/listener为0，API打开/关闭连接计数归零。
4. 完成预热后重复同一批30条切换10轮，实例数不超过30，不因route/mountVersion持续增加；强制GC后的JS heap每轮无单调增长，最后一轮相对第一轮不超过20%。记录浏览器/硬件/实际MB，不声称跨设备统一内存SLA。
5. 断网、暂停页后恢复、撤权穿插；45秒idle不误杀正常心跳；恢复期间业务命令计数不增加。若部署仅HTTP/1.1则容量门禁不通过，不擅自把运行线程驱逐作为修复。

## 5. Final

Phase每任务只跑相应V编号及最小测试；全部实现后再跑：

```bash
"apps/platform-api/.venv/bin/python" -m pytest "apps/platform-api/tests" -q
pnpm --dir "apps/platform-web" test:run
pnpm --dir "apps/platform-web" lint
pnpm --dir "apps/platform-web" typecheck
pnpm --dir "apps/platform-web" build
python3 "scripts/check_docs.py"
git diff --check
```

API全量依赖按该服务现有测试配置准备；环境失败单列，不作代码通过。新Web+新API+当前Runtime真实链路、容量或安全证据缺失时按partial/blocked/deferred说明，不写done。旧版本组合不验收。

新组合验证：新API+新Web运行V07/V09/V13；运行中断开并重新进入，确认原Run仍存在且无多余cancel/start、快照可读。该验证不切换旧产物，不修改Runtime/数据库。

## 6. 执行记录

## Phase 验证记录

### 2026-09-26 规划核实（实施前）

- 静态审阅平台、指定open-swe工作树、锁定SDK和GraphHarbor post33相关代码；参考仓库含未提交改动/冲突，未启动或修改。
- 实际运行内存Node探针，退出码0：正常EOF仅一次请求；网络故障第一次since:9、第二次省略since；activate清理触发dispose一次。注入fetch，无真实服务/业务代码写入。
- 当时三段真实样例、浏览器视觉、线程保活、410和容量均未执行；不能把探针当功能验收。原旧产物回退门禁已按统一版本边界取消。
- 当时文档检查已执行且通过：python3 scripts/check_docs.py、git diff --check；只证明文档一致性，不证明功能实现。

### 2026-09-26 API/Web Phase
- S2：`apps/platform-api/.venv/bin/python -m pytest apps/platform-api/tests/test_runtime_gateway_event_redaction.py apps/platform-api/tests/test_runtime_upstream_errors.py -q`，✅ 11 passed，110 subtests passed。
- S4/S6：SDK 恢复定向测试 4 passed；`useChatSession.spec.ts` 21 passed；会话池 4 passed；ESM/CJS 导入、pnpm frozen install、typecheck 和改动文件 ESLint ✅。
- S7/S8：Web 全量 Vitest ✅ 92 files passed，385 passed，1 skipped；真实 SDK 链路因环境缺失跳过，不能算通过。
- S11 构建/文档：`pnpm build` ✅；`python3 scripts/check_docs.py` ✅；`git diff --check` ❌，仅报告 pnpm 自动生成 patch 中的既有 `space before tab in indent`。
- S10 最小隔离链路：启动 `RUN_SSE_CONTRACT_E2E=1 .../sse_contract_server.py` 与 Vite 13002，执行 `RUN_SSE_CONTRACT_E2E=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:13002 pnpm ... playwright test e2e/sse-event-contract.spec.ts --project chromium --workers 1`，✅ 15 passed；证明真实 API/auth/router、SSE 脱敏器、安装 SDK、事件推进、关闭计数及受控错误/恢复/页面隔离场景可互通，不证明 V01—V21 全场景。
- S4/S5/S6 增量：真实安装 SDK 定向测试 8 passed；`useChatSession.spec.ts` 23 passed；410 状态读取期间新 Run 的旧快照丢弃、取消 ACK 后仍 running 已覆盖。首次握手 410 的 ChatPage 受控用例发现连接状态监听漏绑，修复后单例复跑 1 passed。
- S4 Phase 完成：真实安装 `ThreadStream` 注入物理 SSE，晚加入订阅可获历史回放、旧订阅不重复、旋转请求不附加全局 since；两个 namespace 订阅可分别收到同一 event_id；过滤并集旋转握手 503 后同一 ThreadStream 手动恢复成功且无命令。`sdk-stream-recovery.test.ts` 11 passed，已计入最新 Web 全量 396。
- S5 Phase 完成：`run-actions.test.ts` 4 passed，`useChatSession.spec.ts` 23 passed；终态后 values 未被过滤、r2 不被 r1 迟到完成清理、取消 ACK 后仍 waiting。受控 ChatPage 同 event_id 重放只渲染一份，安装 SDK 晚订阅及跨 namespace 回放见上条；真实 Runtime 错序归 S11 Final。
- S6 Phase 完成：`useChatSession.spec.ts` 23 passed、`useSessionInterrupts.spec.ts` 1 passed；受控 ChatPage 首次握手 410 后显示缺失提示并恢复订阅，无业务命令；旧快照遇新 Run 作废，旧审批 ID 在 state 复核变更后不提交。真实 Runtime 410/审批 Final 仍未验证。
- S7 Phase 完成：池索引/Teleport 定向测试 4 passed；真实 ChatPage+ChatSession+安装 SDK 的 A→B→A 受控浏览器用例通过，后台 A 继续消费、返回未重开订阅且 run.start 为 0。跨入口同 Thread 复用实例由池索引单测覆盖；容量留 S11。
- S9 Phase 完成：真实 ChatPage 撤权后内容/连接清零；A/B 两条会话流经 UI 登出后连接归零且命令数保持 0。`WorkspaceLayout.spec.ts` 2 passed，项目路由参数变化会调用池 `clearScope`；新旧账号和真实 Runtime 仍属 S11 Final。
- S11 最新 Web 回归：`pnpm --dir apps/platform-web test:run`，93 files / 396 passed、1 skipped；`typecheck`、专项改动文件 ESLint、受控 Playwright 15 passed、`check_docs.py` 通过；production build 已退出码 0。
- S7/S8/S9 增量：真实 ChatPage A→B→A 后 A 的后台事件可见、B 草稿保留、订阅不增加、命令为 0；撤权后内容与连接清零。同轮过程正文、思考默认展开/手动折叠回切保留、工具卡展开/结果、最终正文及根命名空间同 event_id 重复输入均有页面断言。浏览器全文件后续增量已达 15 passed。
- S10 故障脚本增量：`advance` 可确定性关闭 SSE 物理流或注入原始 chunk；真实 API→SDK 浏览器 EOF 重新订阅、后续事件到达、命令为 0，单例 1 passed。CRLF 跨 chunk 合法事件到达、含 `fixture-secret` 的非 JSON 帧安全关闭且 SDK 错误不含原文，浏览器全文件合跑通过。该受控上游不等于真实 Runtime。
- S11 静态门禁增量：Web 全量 Vitest 92 files / 391 passed、1 skipped；Web typecheck、production build、文档检查通过。全仓 Web lint 失败于未触及的 `ServiceAccountFormDialogs.vue` 7 处 `vue/no-mutating-props`，专项改动文件 lint 0 error / 3 warnings。`git diff --check` 仅在 pnpm 生成的 SDK patch 文件报告 `space before tab in indent`，排除该生成 patch 后通过。API 全量从服务目录运行：288 passed、14 skipped、5 failed、533 subtests passed；4 个失败是追踪上下文/委托 fork 测试夹具不匹配，1 个是本专项 Protocol 流旧夹具，已修正并重跑 `test_public_route_inventory_and_boundaries`：1 passed、283 subtests passed。首次从根目录运行的 9 个收集错误属于测试启动目录问题。
- 实施前视觉基线未采集；当前桌面与手机截图只能作为实施后观察，不能补记为前后对比。390px 手机宽度下顶栏文字/按钮可见重叠，因本期展示保护及缺少实施前证据未改页面样式，此项未通过视觉验收。真实三服务环境需要专用 PostgreSQL/Redis 与 migration 预检；新库初始化涉及本期排除的迁移，现有 8123/业务库未用于本专项验收。
- S8/S10 增量：受控 ChatPage 的 A Run 结束时 B 可见，A 排队消息保持本地、B 草稿未变，回 A 后恰发一次命令；同名双工具失败/成功结果分别展开。全文件首次复跑暴露夹具 `reset` 未清旧 SSE 队列，造成旧连接计入下一用例；修复 generation 隔离后重新运行 **9 passed**。新增队列用例在排队键加入用户 ID 后单独复跑 **1 passed**。夹具 Python 语法检查、Web typecheck 与改动文件 ESLint 0 error；原组件 14 warnings。production build 最终退出码 0。
- S10 namespace 增量：真实 API→浏览器传输对同一 event_id、不同 namespace 且 sequence 2→1 的两帧均交付，单例 **1 passed**；全文件最终合跑 **15 passed**。该用例证明传输层，不等于 Runtime 错序或子任务 UI 完整验收。SSE 结束原因可选回调已与追踪专项 plan 第 7 节约定，追踪侧 T6 接线仍未完成。
- S10 夹具装配复核：真实 ChatPage 的消息列表轮询发现测试 gateway 缺 `list_thread_messages`，原回归虽然通过但服务日志有 AttributeError。补齐只读响应后最终合跑 **15 passed**；服务日志仅有 V16 预期 `invalid_json`。不将此前带夹具异常的结果作为最终受控证据。

- 2026-09-27 真实 Runtime/Web：`PLATFORM_CHAIN_TEST=1 pnpm --dir apps/platform-web exec vitest run src/modules/chat/sdk-chain.test.ts`，真实 `platform-web:3000 → platform-api:2142 → runtime-service:8123` 链路 **1 passed**（约 61 秒），覆盖普通 Run、断开后水合、HITL approve、终态读取及 checkpoint fork。
- 2026-09-27 真实短容量：`RUN_SSE_REAL_E2E=1 SSE_CAPACITY_THREADS=1/4 SSE_CAPACITY_DURATION_MS=10000 ... playwright test e2e/sse-event-contract-real.spec.ts` 分别 **1 passed**，均完成 30 次 state 访问；1 条和 4 条流 ready。两次结果 `nextHopProtocol` 为空，不能作为 h2/h3 证据。
- 2026-09-27 真实容量根因：本地 Web origin 为 HTTP/1.1。`SSE_CAPACITY_THREADS=8` 时浏览器前 6 条长 SSE 占满同 origin 连接槽，后 2 条在 30 秒内无法握手；`SSE_CAPACITY_THREADS=6` 时 6 条流可建立但后续 `/state` 请求因连接槽耗尽在 Playwright 121 秒总超时。Runtime `n-jobs-per-worker` 只控制 Run 执行槽，临时扩到 2/4 个 worker 不改变该现象，临时 worker 已停止。h2/h3 入口复测仍未完成。
- 2026-09-27 前端视觉：390px `mobile-chat-refactor.spec.ts` 窄屏检查 **1 passed**，修复会话头部两列重叠为两行布局；Agent 选择器、对话/轨迹、操作按钮均可见，`scrollWidth <= innerWidth`，浅色/深色截图已生成。

### V01—V21 覆盖核对

| 场景 | 已执行证据 | 未覆盖边界 |
|---|---|---|
| V01—V02 | ChatPage 同轮正文/工具/正文、思考默认展开与手动折叠回切 | 无实施前视觉基线 |
| V03—V05 | 双同名工具失败/成功分别展开、`transcript.test.ts` 的多工具/namespace、现有富文本组件测试 | 同名子任务与富文本浏览器截图 |
| V06—V08 | A→B→A 草稿/折叠保留、后台事件、隐藏队列不发送且回 A 恰发一次、350ms 定时窗口、附件/滚动回切、登出/撤权连接清零 | 跨项目/账号真实连接清理 |
| V09—V11 | 安装 SDK EOF/idle/重试、尾帧与取消 ACK 单测、根事件重复与晚订阅回放、受控跨 namespace 同 ID 错序传输 | 真实 Runtime 错序/远端新 Run |
| V12—V13 | 客户端握手定向测试、受控 410 SDK 和 ChatPage 恢复 | 全 HTTP 故障浏览器矩阵、双流同时 410 |
| V14—V18 | API 11 tests / 110 subtests，受控 CRLF 分片/坏帧浏览器关闭 | 真实链路三段样例和日志脱敏抽检 |
| V19—V21 | SDK 手动/旋转恢复、池回切、审批 ID 变化、取消 ACK 及 350ms 队列/附件浏览器链路 | 多 interrupt 浏览器链路 |

以上表格为 Phase 覆盖盘点；任何一行有未覆盖边界都不按整组 V 编号通过计算。

## Final 验证记录

**状态：blocked（2026-09-27）**

- 已完成：真实普通 SDK 链路、1/4 条短容量、390px 前端视觉检查；S1—S10 任务实现和受控链路证据已在 Phase 区记录。
- 阻塞：8 条真实 Runtime-backed SSE 在当前 worker 边界下无法在 30 秒内全部握手；本地浏览器入口为 HTTP/1.1，未满足 h2/h3；30 分钟持续容量、堆增长、退出后资源归零及三段脱敏样例未形成 Final 证据。
- 本期不改变 Runtime/GraphHarbor，不执行迁移、部署、旧版本兼容矩阵或 Git 操作；因此不能把该 Final 标为 done。
