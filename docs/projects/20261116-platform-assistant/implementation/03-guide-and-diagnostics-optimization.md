# 用户指南与排障可靠性优化实施证据

日期：2026-11-17。对应 tasks.md 的 T12–T20；本文件保存实现和验证细节，任务状态只在 tasks.md 维护。

## 用户现在怎样使用

用户询问平台操作时，同一个助手先从短目录选择指南，再读取当前正文并给出页面步骤与证据。六篇指南只介绍前端功能；修改指南后可在原会话继续问，下一轮重新读取，不保存旧文档快照。知识库项目页上传入口尚未接通实际文件提交，指南如实说明，不承诺不存在的操作结果。

用户从报错弹窗求助时，诊断包保留目标错误、原始消息和已知编号，其他近期错误单独标为未确认关联。助手按目标项目当前权限读取诊断，再按目标运行时间查询关联日志，区分事实、推测、下一步与缺证。助手依赖失败时，输入框上方仍保留现场卡片，可复制交人工处理。

## 实现位置与最小取舍

- `docs/assistant/manifest.json` 与六篇 Markdown 是唯一用户指南正文。API 的 `materials.py` 删除两份内置业务指南，未增加分词器、向量库或编目流水线。
- 原 `authorize` 返回 `document_catalog/document_status`。Runtime `CurrentAuthorization` 在同步/异步 `wrap_model_call` 中临时覆盖本轮系统消息，不污染共享请求或历史；目录不可用不阻断普通聊天。
- `search_documents(document_id="", query="", line=1)` 保留旧调用兼容；无ID返回最多32篇目录，有ID从头读当前正文，最多300行/16,000字符。源码仍保留原80行/8,000字符及revision授权。
- `service.py::require_target_project` 从Thread记录取真实项目，重载该项目当前成员角色并校验Thread ACL。首次读取、证据历史、列表/重开/续聊复核共用规则，未将助手项目等同目标项目。
- 当前栈进一步发现网关实例已持有助手项目的Runtime委托。`router.py::_target_gateway`在目标授权后使用独立请求上下文构建目标项目/角色/策略的读取网关，原助手身份和证据归属不改；在service的审计保护范围内调用，不绕过拒绝审计，也不改通用网关。
- 诊断/日志证据的 `scope.target_project_id` 表示目标项目，`scope.project_id`仍是助手会话项目。`observed_at`只是读取时间，`data.run_time`只投影Run快照的created_at/updated_at；没有新增原始日志、完整堆栈或配置外发路径。
- `logs.py` 默认取Run创建前5分钟至最后更新后5分钟。时间缺失、无时区、逆序、只给一端或扩展后超24小时均要求补充窗口；显式窗口仍校验。返回query_start/query_end及原partial/coverage，保留100条、64KB、文件尾512KB边界。
- Web诊断生成器只按明确请求关联匹配，弹窗也不再借用最近请求。复制/求助均保留原始错误，不用初步分类覆盖。无编号的页面错误分类为unknown；诊断切换后旧异步响应不能写回新目标。
- 错误卡片复用现有剪贴板工具增加“复制诊断”；发送失败保留卡片，成功或待审批后才清除同一份上下文。审批/运行中阻止额外发送，目标项目不切换助手会话绑定。
- `usePlatformAssistantSession`增加局部操作代数，绑定项目变化或新会话后丢弃旧历史、Thread创建、流及最终状态的晚到结果；审批/停止也受同一约束。Bootstrap加载中禁止发送，避免旧Thread与新项目头混用。

不增加新Agent、生产写工具、执行沙箱、Docker、数据库迁移或部署流程。数据库与源码撤权/版本、会话ACL和原只读规则保留。

## 确定性和集成回归

API在本服务 `.venv` 执行 `python -m pytest tests/test_platform_assistant.py -q`，最终50 passed（5.13秒）。覆盖六篇目录、当前正文/哈希、缺失/超限/路径/软链接、文档更新后历史可读和工具撤权、源码版本、跨项目取证及真实证据回执后的历史校验、列表/重开/继续评论、私有/缺失/撤权、旧Run时间与日志边界、安全配置/运行时间投影。新增目标委托令牌测试先1 failed，再修复通过；断言令牌真实project_id/role与目标一致，原助手请求上下文未被修改。

扩大API回归首次112 passed、3 skipped、1 failed、3 subtests passed；最终追加运行诊断文件后为142 passed、3 skipped、1 failed、5 subtests passed（17.56秒）。最终命令为本服务`.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_observability_api.py tests/test_thread_fork.py tests/test_run_requests.py tests/test_thread_acl.py tests/test_run_diagnostics.py -q`。失败均为 `ThreadAclTest.test_new_thread_ignores_supplied_identity_and_acl`：update_thread mock只期望title，实际携带完整ACL metadata。先前将HEAD原网关文件仅在内存替换，同项仍失败，已证实为基线；本轮未改该网关解决范围外问题。第一次探针读取被截断导致compile失败，随后完整读取成功复现；不把探针失败当产品结论。

Runtime扩大回归命令：

```bash
# 在 apps/runtime-service，使用该服务自己的 .venv
.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_r0_baseline.py tests/http/test_diagnostics.py tests/observability/test_run_diagnostics.py tests/observability/test_diagnostics.py -q
```

最终结果79 passed（12.16秒）；保留既有Swig及langchain-community弃用警告，没有借本任务更新核心依赖。

Web命令：

```bash
# 在 apps/platform-web
pnpm test:run src/modules/platform-assistant src/services/observability/diagnostic-packet.spec.ts src/services/observability/error-buffer.spec.ts src/modules/chat/components/DiagnosticDetailModal.spec.ts src/modules/observability/pages/TraceDiagnosticsPage.spec.ts
pnpm build
```

最终相关13文件68测试通过（21.03秒）。当前栈复现项目切换后旧历史回写，补3个测试先3 failed/2 passed，修后通过；收尾再补2项403缓存回归和1项组件重复重置回归，分别先2 failed/5 passed、1 failed/2 passed，再修复通过。上述均已并入最终68项。中间Composer测试误在disabled输入框setValue，已修正测试步骤，产品禁用逻辑保留。弹窗仍有router-link stub警告；此前16文件及最终会话/组件修复4文件ESLint无错误，保留原Markdown v-html警告；指定Python文件使用离线uvx Ruff检查通过（服务.venv没有安装Ruff）。最终pnpm build包含vue-tsc，通过，Vite构建40.50秒；旧Browserslist和大chunk提示保留。

## 真实模型：回答与工具轨迹分开核对

测试入口为 `apps/runtime-service/tests/test_platform_assistant_live.py`，默认跳过，显式 `ASSISTANT_LIVE_TEST=1` 才外发。它启动 `apps/platform-api/tests/assistant_validation_server.py`：回环临时端口、独立SQLite、指南副本、合成Run/结构化日志及当前用户/项目成员。真实助手create_agent通过HMAC HTTP读取真实API router/service/evidence；Run网关事实是合成夹具，checkpoint使用InMemorySaver。

外发范围只有上述合成资料和用户指南。模型夹具阶段密钥交互输入、不回显，不写夹具、报告、日志或Git。随后当前栈真实验收仅在两个新建测试项目中通过正式API加密配置临时连接，未改共享连接或既有用户Agent；收尾已停用连接并将凭据替换为不可用随机值。

原接入失败保留：v2首选连接403额度不足，v3/v4备用连接503无可用渠道，v5另一个端点400已关闭；这些是当时的真实环境结果，不代表模型逻辑通过。

- v6虽执行了11问，但人工发现助手/目标项目被当冲突、读取时间被当事件时间，以及max_tokens=1800造成截断。不能把当轮弱断言通过当质量验收。
- v7补作用域/时间后仍出现缩写证据UUID、建议成功Run重试、空错误列表就排除模型的问题；已加强规则和完整引用断言。
- v8：11场景、46次完整引用，1 passed，150.32秒。进一步发现缺日志时尝试项目级检索；后端拒绝未授权读取，没有数据泄露，但不符合不自动扩大调查范围的目标。
- v9：11场景、40次引用，1 passed，137.86秒；所有目标Run场景未调用search_project_logs。人工仍发现把error等同没有产出、暗示启用诊断可恢复过去未采集记录的问题，已继续明确失败可能有部分产出及历史采集边界。

- v10追加中断/运行中后触发GraphRecursionError：1 failed、103.03秒，仅保存前5场景。核对官方MCP及锁定源码确认中间件也消耗图步数，仅测试harness的recursion_limit由30改100；模型8次/工具10次预算不变，没有放宽正式预算。
- v11：13场景，1 passed、188.59秒；人工仍发现把空retries写成没有重试、把observation_id当节点、编造配置页和无依据排序，继续修正规则。
- 最终v12：13场景、60次完整证据引用，1 passed、182.11秒。覆盖普通聊天、跨指南、知识上传限制、429、恢复成功、来源不可用、超时、泛化失败、中断、运行中、缺Run、同会话指南更新前后两问。人工核对关键答案，不再根据空记录排除原因、把graph-1当节点、编造配置路径或排序无证据候选。仍有冗长和轻微措辞问题，不承诺任意故障都可诊断或建议永远准确。

每轮均断言未因length截断、引用逐字对应本轮evidence_id、合成敏感字段不入消息，以及Run调查不扩大项目日志。断言后继续人工读答案，不把测试绿灯当模型可靠性保证。

本地原始结果位于忽略目录 `.local-stack/assistant-validation-20261117-v*/results.json`。测试工具选择、目录阅读、普通聊天零工具、已恢复不重跑、429不推定欠费、缺Run不编造编号、泛化失败承认缺证，以及同会话文档更新后重新阅读，均在对应轮次保存。

## 浏览器：真实产品组件与故障夹具

使用browser-skill的后台Agent Window，预览引入实际DiagnosticDetailModal、PlatformAssistantDrawer、EvidenceDetailDrawer；API请求统一注入合成503。证据目录/正文由真实read_material生成；这验证浏览器消费者和降级行为，没有连接完整三服务运行栈。

实际操作和观察：

- 连接拒绝与无关429同时存在：弹窗显示目标错误，复制到系统剪贴板后核对目标编号/错误、未知发生时间及背景“未确认关联”均正确。
- 阅读六篇目录和当前指南：目录明确尚未读正文，正文显示标题、行号、SHA256；旧运行日志展示实际窗口和partial。
- 修前503发送会清空卡片，保留 `04-assistant-unavailable.png` 为失败证据；修后桌面 `05-assistant-unavailable-fixed.png` 保留卡片并能复制。
- 390×844手机尺寸下，无Thread/Run/Request的UI Render Crash求助并发送503后，卡片仍在；真实系统剪贴板断言原始错误、unknown、无Run、未关联Request、背景分离全部为true。修后截图 `06-mobile-unavailable-fixed.png`。
- 浏览器继续暴露弹窗借用最近请求、字符串原始错误被初步分类覆盖的问题；两处已修，组件回归和上述手机复制实测通过。长HTTP错误横幅补换行样式，避免窄屏溢出。

截图与预览在 `.local-stack/assistant-browser-validation-v1/`。该预览未配置正式public资源目录，截图中的助手头像缺失不作为产品头像验收。背景窗口Meta+V未完成粘贴，不计粘贴通过；复制结论来自按钮操作与系统剪贴板断言，不输出剪贴板原文。首次手机夹具缺viewport，补齐并重载后以实际390×844复验，不将初始缩放图算通过。浏览器窗口与自有预览进程已关闭，未停止主服务。

## 当前环境真实连续链（独立于上述夹具）

用户答复“就使用当前的环境就可以了，不需要隔离”，因此使用当前Web3000/API2142/Runtime8123，未创建Worktree、迁移数据库或重启主服务。只创建专用普通账号、个人助手项目与业务测试项目；用户在业务项目为executor。目标workflow_demo真实Run成功，回复合成短句，约5秒。

真实操作与观察：

1. 业务项目切到个人项目后，旧历史请求晚到恢复旧Thread，下一次请求头与Thread项目不符而403。先补3项竞态回归，再修局部操作代数；HMR后以个人项目干净新会话继续。
2. 首轮取证仍forbidden。公开读取也得到Runtime上游403，定位为读取网关的助手项目委托未随目标权限切换。先补令牌回归复现，再按目标当前角色构建独立读取网关；未放宽Runtime或会话ACL。
3. 同一助手会话再次取证200，证据5231159b-9991-4555-bd9f-9adfb32c7cef包含助手/目标双项目、真实success和运行时间。浏览器打开证据抽屉核对原返回。
4. 新会话后打开历史列表、重开原Thread、继续追问并重新调用诊断，得到新证据3275093f-98e8-4ccb-8eed-fb5538c65e11。读取实际日志返回assistant_trace_missing，回答说明缺口，没有项目日志扩查或重跑。状态来自真实GraphHarbor持久存储，不是InMemorySaver；本轮未重启服务。
5. 删除本轮测试用户的业务项目成员关系后，原助手state与继续发送均403 assistant_history_source_revoked，目标诊断403 thread_action_denied；列表200但隐藏受限Thread，普通指南仍200。首次浏览器发送虽拒绝，但屏幕仍保留旧消息，后续修复如下；不能把该截图算作缓存清理通过。随后恢复原executor，原历史重新200；未触碰其他成员。
6. 新助手会话真实读取evaluation/chat指南并回答前端转评测集步骤，证据抽屉显示当前evaluation正文L1–L17与SHA256。未执行实际转评测集。

真实目标Thread：3561c8eb-82a4-46c9-9d77-ae9cc189c984；Run：5188b7b1-8b34-41a5-ae65-0c9ea7f1e266。助手Thread：2eb9f88b-b6e5-4089-811e-74b17116665f，最终13条持久消息；指南Thread：e1561e45-b34f-4d98-b998-62e71b406727，5条消息。只计已持久化消息，撤权后未开始的前端消息不算运行。

原始资料在忽略目录.local-stack/assistant-current-validation：state.json保存资源ID/收尾标记、summary.json保存工具/范围对账、thread-*.json保存实际状态、revocation.json保存拒绝结果，02/03为取证与历史追问、04为拒绝成功但屏幕缓存未清的修前证据、05为列表隐藏、06为指南证据、07为修后缓存清理及权限提示截图。02/06/07已打开图像核对；01在HMR后拍摄，不作为修前失败截图。首次模型配置缺少测试个人项目角色、首次目标Run缺默认Agent初始化的403及重复Graph创建409均在联调时纠正，未借此放宽权限或多建同Graph Agent。

收尾复核frontend-handoff的403要求时发现屏幕缓存遗漏。usePlatformAssistantSession仅对明确status=403清空Thread/消息/审批/证据索引与详情，设置权限变更提示；503和临时网络异常仍保留现场。真实浏览器第一次补验又发现AssistantChatView监听activeThreadId=null时重复重置，抹掉提示；新增组件回归先失败，将重置限制为本地仍有Thread时执行。最终已加载13条旧历史及证据后，仅用管理员撤目标成员，发送得到403，旧消息/证据消失，权限提示可见，identity/me和当前个人项目access仍200，没有全站登出。截图07与网络序号864保存本次结果；2个缓存和1个组件测试覆盖对应行为。

首轮补验遇到登录失效，没有将其算作资料撤权通过；后续重新登录，撤成员步骤只使用管理员会话，模型保持停用且不新增模型调用。最终恢复executor，API确认原历史200，再次执行收尾停用测试账号和模型。

收尾确认无pending/running测试Run；两个新建临时模型已disabled并替换掉原凭据，测试账号disabled且原token访问403。合成账号/项目/历史和审计保留，不删除既有数据；后台浏览器已关闭，主服务保留。当前诊断真实返回disabled/not_configured且没有platform_trace，这是来源未配置而非成功Run的故障根因。

最终静态检查：20个连续唯一任务均done、无未勾子项，42个项目相对链接存在；六篇指南ID/路径唯一，15–22行、555–740字符，未超工具限制。项目说明/指南密钥与私钥模式匹配0，限定本轮文件git diff --check通过。任务、摘要、CONTEXT、FEATURES、CHANGELOG及交接/操作说明已同步回读。

## 验收边界

夹具、真实模型与当前栈证据分别成立：当前栈证明真实跨项目连续链和当前指南读取，合成夹具证明可控失败、旧日志窗口与降级，不冒充当前真实日志采集结果。没有验证真实Loki、生产采集/容量、本轮持久checkpoint重启或新增范围用户人工验收；没有Git提交、分支、推送或生产部署。重要建议仍需回查证据和必要人工核对。
