# 未完成开发项收尾

日期：2026-09-11。用户已授权完成全部非后置开发与必要验证；不重复申请原方案批准。

**最终状态：本期非后置开发与自动化验收 done。下文按时间保留修复和失败记录，早期的 partial/正在执行不代表最终状态。双浏览器同 Thread 入队、完整文件/Skills API、PTY 为 deferred；无待讨论的开发阻塞。**

## 范围与实际改动

- A2/A4/U5：移除 `apps/platform-web/src/modules/examples`（17 文件）及 `examples/sub2api-reference`（262 文件），移除无消费者 vue-virtual；更新前端 README、开发/控制面/视觉活标准。正式导航已无对应路由，独立 research 仓库不受影响。
- U1/U3/I3：导航权限取自同一 `useNavigation.ts`，桌面侧栏与移动弹窗共用；增加移动历史选择和 Chat 删除确认入口；补未匹配路由状态。`BaseDialog.vue` 增加可访问名称、Tab 焦点约束及顶层 Escape 处理。
- R3/R5/I4：子任务按完整 namespace 表达层级；超长正文按需展开，复制仍使用全文；审批显示实际变更字段。
- Q4：原实现 ACK 后丢失正文，拒绝/未消费回执无法在刷新后恢复。Runtime 回执增加仅当前发送者可读的 `content`，Web 提供恢复输入框，保留已有草稿且不自动发送。
- QV09/QV11：`MessageInbox.stats()` 与 `python -m runtime_service.messaging --stats` 输出 pending 年龄、拒收/未消费数量、消费延迟聚合，无正文/身份/凭据。`RUNTIME_MESSAGE_QUEUE_ENABLED=false` 只阻止新收件，查询、既有原请求确认与消费保留。数据库拒收日志只记固定原因与状态码。
- 网络验收：隔离 runner 加载 `web_contract_graph.py`，覆盖两路真实 interrupt、typed edit/拒绝、嵌套 scoped 流；测试图仅用于隔离验收，不注册生产目录，不修改 GraphHarbor 业务边界。

## 当前验证

- 修改前 Web：69 passed / 1 skipped；全量 ESLint 零警告。
- 本轮 Runtime 真实 PostgreSQL：19 passed / 1 skipped（87.03s）；新增发送者隔离、上限、真实事务失败、旧 schema 加列与重复迁移保留数据、关闭入口后既有请求确认/GET 回执。
- 本轮 TypeScript：通过。
- 并行审批、嵌套子图、移动端、安全/性能与其余 QV：正在执行，未通过前不标完成。

## 部署与边界

关闭新队列入口使用 Runtime API 的 `RUNTIME_MESSAGE_QUEUE_ENABLED=false`，Worker 继续处理已接收消息；GET 和原 ID/key/body 重试保留。恢复时设为 true。指标从 Runtime 数据库只读聚合，收件前的拒收由结构化日志统计。回执正文只随当前发送者查询返回，不暴露 `authorization_ref` 或 claim。

双浏览器同 Thread 同时入队依用户要求 deferred；完整文件/Skills API 与 PTY 按原方案后置。当前状态 partial，后续测试结果在本记录继续更新。

## 2026-09-11 新增实测证据

- 三尺寸 1440/1024/390 复杂并行审批、嵌套 scoped 流、浅深截图、刷新恢复：3 passed，证据目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-5o9tdj5w`。发现并修复移动顶部项目选择器遮住导航按钮。
- 真正两个同名 `specialist` 节点以 LangGraph Send 并行，再嵌套子图：1440 网络浏览器复验 1 passed（32.3s），目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-1i5hzm0b`。前述三尺寸用例起初是不同父节点，本项单独补齐同名条件。
- 移动端队列 complete/cancel-before/cancel-after/revoke/unknown：5 passed（2.5min），目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-s2k192pe`；刷新后恢复未消费正文并保留草稿通过。
- 1000 条消息、200 工具、1200 次末条流更新性能及 XSS/键盘安全：1 passed（1.2min）。首次 P95=167.3ms 失败；按 turn 内容及展开/编辑状态 memo 后保持原节点/焦点，P95<=100ms。未提高性能阈值。
- 真实 DeepSeek 长工具后 before_model 注入 + PG receipt：1 passed（13.33s）。首次失败来自测试全局替换 HTTP client 干扰模型请求；将真实模型 HTTP client 显式隔离于授权 stub 后通过。授权服务 503 不注入已另测通过。
- API 撤权及委托作用域测试 7 passed；delegation 11 passed、run_requests 16 passed。
- Runtime 新增显式 `python -m runtime_service.messaging --prune-deleted` 运维入口：只读取同库 GraphHarbor threads/runs 判断已删除 Thread；保留 24h 幂等窗口及 pending/running Run，活 Thread 回执不按年龄删除。实际 PG 保留/清理测试 1 passed；缺引擎表时失败关闭。无新组件、无 GraphHarbor 业务代码。
- 删除已被新用例替代的六份旧 E2E（旧路由、明文测试密码、全量身份响应日志和个人绝对路径），删除旧 chat-harness 两脚本；当前 harness 文档指向可运行套件。编辑分支及真实 Showcase 新用例仍待本批验收，不能以文件存在判通过。

管理路由验收首轮发现 Control Plane 横向溢出；正在修复并复验。其余未通过门禁继续保持 partial。

## 后续闭环

- 管理面 16 个保留路由（1440/390）及 404：1 passed（39.3s），目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-475_ousa`；修复 SurfaceCard 网格最小宽度与长指标换行。
- 待审批期间剩余消息归为 not_consumed，resume 新 Run 不重放：1 passed（1.3min），目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-pcl6bvqa`。
- 两个真实并行 child create_agent 不消费 root inbox：PG 集成 1 passed（14.81s），root 下一模型调用收到唯一 HumanMessage。
- 回执查询先于 POST ACK：确认回调只调用一次，不把 consumed 覆盖为 queued；卸载后迟到查询不落入页面。useChatSession 2 passed。
- REST / SDK 迟到响应、并发 refresh 去重与退出后旧刷新结果：9 passed，防止跨账号回填。
- API 伪造 sender/source/config/context/resume/authorization_ref 的字段边界与原 delegation 合约：12 passed。
- 后端本批定向全量：48 passed、1 skipped（真实模型另测通过）。范围 inbox PG / runtime auth / platform auth / reference middleware。
- 当前 Web 单元批次 70 passed、1 skipped（SDK 网络测试另有独立历史实测）；新增 HTTP 3 项在后续定向批次通过，最终汇总以最后全量为准。
- 保留管理页的 DataTable 新增 error 状态，加载失败不再显示“暂无数据”；StateBanner 增加 alert/status，Control Plane 数据未齐时不宣称稳定。
- Showcase 首轮已确认 execute 输出、真实 result.txt 的 43.50；发现刷新后 SDK live calls 不包含历史工具，Inspector 改为复用 buildTranscript 关联持久 AI tool_calls 与 ToolMessage。复验仍在进行：第二轮模型把命令 stdout 重定向进文件，故 execute 输出断言未通过；测试指令明确 tee 同时输出与存文件，保留原断言，不把此轮视为通过。

## 2026-09-11 最终回归补充

- 新增会话级 AbortController 与 SDK 请求 signal 合并；dispose 会中止所有流式/普通请求，保留 SDK 自身取消语义。`run-actions.test.ts` 3 passed，vue-tsc/build/eslint 通过。
- 复杂并行 Chat 3 尺寸复验：1440/1024/390 全部通过（同名 specialist、嵌套 scoped 内容、双审批逆序决策、刷新、20 次 Thread 切换）。报告：`/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-hqaha0zj`。
- 控制面 16 路由及列表 loading/empty/error/forbidden 三状态复验：2 passed，报告：`/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-16zjdit_`。
- 生产构建在本轮源码（含顶层 `checkpoint_id` 分支修复和 signal 释放修复）上通过；未使用旧归档包作为当前证据。全量 Vitest 74 passed/1 skipped。
- 真实 Chat 桌面回归的一次失败来自 workflow demo 外部模型初始化超时；移动端同场景已通过，失败日志保留于 `q5-message-tgkmy9xe`，不将该次失败伪装成通过。

最终边界：双浏览器同一 Thread 同时入队、完整文件/Skills API、交互式 PTY 继续按用户明确要求后置；GraphHarbor 不新增业务代码或新版本。

- 最终产物恢复：归档并解包后 65 个文件 SHA-256 逐一匹配，以解包目录运行 preview；1440/1024/390 并行/嵌套/审批/刷新及 20 次切换全部通过（3 passed），报告 `q5-message-r500n7of`。归档目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/platform-web-final-20260911-e7t04s08`，tar.gz SHA-256 `d25c818bd8ec45b3762447ed9310c10806f44b68528c0173d42c0fc032212f90`。文件 raw 合计 1,198,254 bytes、逐文件 gzip 合计 388,873 bytes（非首屏）；各 chunk 见 manifest.json。未回滚数据库或恢复旧不兼容 bundle。
- 真实 Showcase 最终通过：1 passed（2.6min），`q5-message-9yzxwp9a`；批准 execute 的输出及真实 result.txt 均为 43.50，刷新后 Inspector 保留文件/Skills。一次模型超时由 Worker 重试恢复，最终 Run `89e0c985-3d23-4d40-9552-0934c25a02e7` 为 success。
- 稳定长会话测量：1000 messages、200 tools、1200 次更新/60s，input→paint P95=24.2ms、原节点与焦点保持，2 个长任务（最大 741ms），不存在每 token 全列表重挂；`/tmp/platform-web-render-final.json`。

- 最终网络恢复补验：`chat-recovery-refactor.spec.ts` 首次 run.start 503 后保留草稿，重试同 Thread/key/body；离线刷新不自动重发；取消确认后同文新动作使用新 key。恢复产物 preview 上 1 passed（18.7s），`q5-message-1bl2gmri`。
- 桌面真实模型复验：同一最终恢复产物运行 1 passed（42.2s），`q5-message-9gtn2idn`。已加强的新分支隔离与旧分支保留断言通过。外部模型等待窗口调整为 90 秒以涵盖服务已有重试；前端性能门槛未调整。
- 富结果最终浏览器复验：document/markdown/code、缺 URL 文件、安全降级、非零退出码与截断、键盘焦点、1000 消息/200 工具/1200 更新通过；P95=29ms，1 个长任务 642ms，节点/焦点稳定。`/tmp/platform-web-render-artifacts-final`。
- 迟到父 Run completed 定向单测：回调核实当前新 Run，仍 running 时保持禁发；useChatSession 3 passed。首次测试漏填动作 key 导致 mock 不符合 RunAction 契约，补齐 mock 后无未处理异常；生产实现无需额外修改。

- 竞争 Run 最终真实网关集成：1 passed（8.9s），`q5-message-ojw2tvx7`；并发两个新 key 只创建一个 Run，另一个 409；原 key/body 返回同一 Run、改正文 409。首次断言误用上游 201，平台端点实际约定 200，按平台公开路由修正测试；不改业务响应。
- 最终文档检查：check_docs.py、项目全部 Markdown 相对链接、git diff --check 通过。
