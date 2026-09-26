# SSE 专项 — 可执行任务清单

> 2026-09-26。方案事实源为[plan.md](plan.md)，测试输入/命令见[verification.md](verification.md)。下述新文件、接口和测试均是待实施交付物，不表示当前仓库已经存在。业务代码尚未开始。

## Phase 0：交接与评审

### P0.1 现状核对与执行细化
- **改动内容：** 核对平台、指定open-swe工作树、锁定SDK及只读GraphHarbor；确定完整实例宿主、恢复层级、410限制、帧安全规则和UI保护。
- **代码位置：** 本专项README.md/plan.md/tasks.md/verification.md/open-swe-comparison.md。
- **预期结果：** 每项有唯一推荐实现；不遗留候选架构/候选阈值给实施者选择。
- **验证项：** 路径/链接检查；记录真实只读探针与未执行验证的区别。
- **状态：** [x] 2026-09-26文档细化完成；不等同功能实现。

### P0.2 人工评审门禁
- **改动内容：** 审阅plan第4—6节新增细则，记录批准人、日期、范围；用户已确认S07展示保护/S08保活范围，不重复询问这两个范围。
- **代码位置：** 本专项README.md评审记录。
- **预期结果：** 对新细则的评审可追溯；不把AI补文档当作自行批准治理改动。
- **验证项：** 明确API/Web范围、当前标签页/项目边界、无活跃线程驱逐、410降级及SDK窄补丁；批准前只允许文档/只读核对。
- **状态：** [x] 2026-09-26 本次交接确认用户已同意进入下一专项；方案就绪，仍无本轮业务编码授权。

## Phase 1：测试基线与网关（P0.2后）

### S1 展示与真实SDK基线
- **改动内容：** 保存实施时最新用户工作树的展示基线；补真实SDK隔离用例，先复现EOF停流、作用域dispose、Run尾部过滤。测试使用现有Vitest/Playwright，不新装框架。
- **代码位置：** 新增apps/platform-web/src/modules/chat/sdk-stream-recovery.test.ts、e2e/sse-event-contract.spec.ts；扩展src/modules/chat/run-actions.test.ts；基线证据记本专项implementation/01-baseline.md。
- **预期结果：** 明确本期缺口与已有行为，UI目标为当前平台；保存instanceId、run.start/input.respond/cancel计数及流连接记录。
- **验证项：** V01—V06基线、V10/V11失败复现；测试失败原因必须为目标缺口，不因坏夹具伪造红灯。
- **状态：** [ ] 待实施。

### S2 网关帧限额与安全关闭
- **改动内容：** 增量分帧，8MiB字节上限；UTF8/JSON/外层失败安全结束；心跳注释固定化；protocol/run分别验证payload；保留上游握手和finally清理。
- **代码位置：** apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::_redact_sse_frame、_redact_protocol_event_stream及三处调用；tests/test_runtime_gateway_event_redaction.py；tests/test_runtime_upstream_errors.py。
- **预期结果：** 合法业务流保真，坏帧无原文输出；无需改Runtime、HTTP读超时或DB。
- **验证项：** V14—V18；改掉旧test_preserves_fragmented_and_non_json_sse_frames中“任意非JSON透传”的断言，保留合法分片断言；所有异常分支aclose恰一次。
- **状态：** [ ] 待实施。

### S3 HTTP错误边界衔接
- **改动内容：** 复用错误专项safe parser，stream握手抛保留status/code/request_id的安全Error；现有401刷新一次；不引入另一套Envelope或重复命令重试。
- **代码位置：** apps/platform-web/src/services/langgraph/client.ts::createLanggraphAuthorizedFetch及client.spec.ts；必要时在run-actions.ts的stream请求分支调用同一parser；不对正常Response重复读body。
- **预期结果：** SDK能识别403/410/429/5xx；UI不出现原始上游堆栈/正文。
- **验证项：** V12、V13；一次401→刷新→成功、二次401退出、403零自动重试、410保留机器码。
- **状态：** [ ] 依赖错误响应专项相应公共边界交付。

## Phase 2：协议恢复与执行事实（S1/S3后）

### S4 SDK窄补丁
- **改动内容：** 按plan5.1/5.2在现有transport循环增加EOF处理、45秒idle、重试预算/可取消退避/错误分类；新增四个连接能力；paused保留逻辑queue与订阅；ThreadStream公开转发。保留现有namespace/终态后投影补丁。
- **代码位置：** apps/platform-web/patches/@langchain__langgraph-sdk@1.10.2.patch，对应包dist/client/stream/transport/http.js/.cjs/.d.ts、dist/client/stream/index.js/.cjs/.d.ts及必要导出类型；pnpm patch更新产生的package.json/pnpm-lock.yaml；新增sdk-stream-recovery.test.ts。
- **预期结果：** 不重建useStream/registry，不重复run命令；首次握手失败也可手动恢复；SDK安装可复现。
- **验证项：** V09—V13、V19；直接导入安装SDK测试ESM，增加CJS导入冒烟；5次重试/30秒健康重置/全Abort清理；ready挂起时close不死锁；共享扩容回放和同名子任务测试不回归。
- **状态：** [ ] 待实施；只提交patch源及锁信息，禁止以手改node_modules作为交付。

### S5 去除整流Run过滤与取消误判
- **改动内容：** 删除filterStaleRunSseResponse及仅为它存在的completedRunIds/帧解析分支；保留RunAction key/body/id幂等逻辑。终态/cancel不立即disconnect，旧Run只限制状态回调，不过滤数据。
- **代码位置：** apps/platform-web/src/modules/chat/run-actions.ts::createRunActions；run-actions.test.ts；composables/useChatSession.ts::verify、stop、onCompleted。
- **预期结果：** lifecycle先到时最终values/checkpoints仍可应用；r1终态不影响r2；其他入口启动Run仍被发现。
- **验证项：** V10、V11；r1终态→r1最终values、r2开始→r1迟到终态、取消ACK→running→真实终态三组；每组命令计数精确。
- **状态：** [ ] 待实施。

### S6 会话恢复与410
- **改动内容：** 删除不存在的joinStream分支，新增reconnectStream和每Thread单飞recoverExpiredStream；连接状态订阅清理；复用verify/state/history，新增recoverySnapshot绑定，隔离generation/run_id；动作retry与连接retry分流。
- **代码位置：** apps/platform-web/src/modules/chat/composables/useChatSession.ts::verify、retry、ensureLiveEventStream、refreshAccessPolicy及新增恢复函数；components/ChatSession.vue的现有error/status及displayedMessages数据绑定；useChatSession.spec.ts。
- **预期结果：** 普通恢复不重放动作，410显示授权快照/缺失提示，不声称原子无损；主视图/历史选择/草稿不重置。
- **验证项：** V09、V12、V13、V19；410并发只查一次、状态读取期间新Run使旧快照作废、审批ID变化不自动提交；同一条目的两个流状态正确汇总。
- **状态：** [ ] 待实施。

## Phase 3：完整会话持续保活（S4—S6后）

### S7 稳定宿主与条目模型
- **改动内容：** 实现plan4.1/4.2唯一宿主、注册表、Teleport停放、不可变instanceId及每条目独享models；不新增Pinia流缓存/自研投影。实现acquire/attachView/bindThread/remove/clearScope/dispatch。
- **代码位置：** 新增apps/platform-web/src/modules/chat/components/ChatSessionPool.vue、composables/useChatSessionPool.ts及同名.spec.ts；layouts/WorkspaceLayout.vue与WorkspaceLayout.spec.ts。
- **预期结果：** 页面只绑定view，Thread实例与动作持续受管；同Thread跨聊天/Dear入口至多一个实例；草稿确认Thread不remount。
- **验证项：** V07、V08、V20；身份索引碰撞检查、旧generation丢弃、pending ready销毁、Teleport目标卸载后无残留/报错。
- **状态：** [ ] 待实施。

### S8 页面与组件必要接线
- **改动内容：** ChatPage/DearAgentPage去掉mountVersion会话重建，loading/error只影响视图；原resetDraft/restoreDraft改为条目初始化，created/fork/refresh事件按条目处理；传visible，暂停后台DOM副作用和未发送队列drain。
- **代码位置：** apps/platform-web/src/modules/chat/pages/ChatPage.vue及.spec.ts；modules/dear-agent/pages/DearAgentPage.vue及.spec.ts；modules/dear-agent/components/DearAgentSession.vue；modules/chat/components/ChatSession.vue。
- **预期结果：** A后台完成不改B路由/输入/附件；打开抽屉/参数作用于当前线程；隐藏弹层不盖B；原展示与操作一致。
- **验证项：** V01—V08、V20；延时350ms途中切页不新发消息；已提交收据继续更新；新建Thread ACK期间切B不清B草稿；回A滚动/折叠保留。
- **状态：** [ ] 待实施。

### S9 权限与作用域清理
- **改动内容：** 明确denied状态优先于hasCachedContent；403/404清条目及其缓存/草稿，网络故障不冒充撤权；换项目/账号/登出/离开工作区统一清作用域；删除Thread成功通知池。
- **代码位置：** apps/platform-web/src/modules/chat/composables/useChatSession.ts::refreshAccessPolicy、canRead；useChatSessionPool.ts；stores/useChatSessionStore.ts::removeSession/clearAll；WorkspaceLayout.vue；两页面deleteThread。
- **预期结果：** 旧页面KeepAlive/迟到请求不能恢复越权数据；释放不取消Run；不同身份不共享SDK。
- **验证项：** V08、V12、V20；撤权后再次导航无缓存闪现；network/5xx保留已授权快照但新操作重新校验；所有controller/timer/listener清零。
- **状态：** [ ] 待实施。

## Phase 4：综合验证与交接

### S10 可控全链路夹具
- **改动内容：** 建立测试专用受控上游和真实平台路由装配，提供事件推进/故障脚本/请求计数，浏览器跑真实Vue SDK；不在生产header加入测试开关。
- **代码位置：** 新增apps/platform-api/tests/fixtures/sse_contract_server.py；扩展apps/platform-web/e2e/sse-event-contract.spec.ts。优先复用错误专项fixture装配，SSE场景仍独立计数与端口。
- **预期结果：** 可重复验证Web→API→受控上游，真实三服务另验，不拿夹具当Runtime验证。
- **验证项：** verification第3节命令和fixture契约；所有V编号有断言/截图/请求计数或日志证据。
- **状态：** [ ] 待实施。

### S11 Final验收、回退与现状文档
- **改动内容：** 执行全量Web/API相关测试及真实链路、容量/权限/回退；更新现役规范、CONTEXT/FEATURES/父项目；按implement-feature记实现、verify-change记Final四态。
- **代码位置：** 本专项implementation/、verification.md；apps/platform-web/docs/frontend-development-playbook.md；apps/platform-api/docs下受影响现役规范；docs/CONTEXT.md、docs/FEATURES.md、父项目README.md。
- **预期结果：** 没有未解释UI改动；无新跨Runtime契约；测试证据明确通过/失败/未测，未通过门禁不宣布完成。
- **验证项：** verification第4—6节；真实链路故障/取消/HITL、8活跃+30访问30分钟、隔离回退及三段脱敏样例。
- **状态：** [ ] 待实施；本轮不执行发布、删除测试数据或git提交。

## 进度

- [x] 独立专项及父项目关联。
- [x] 用户确认线程保活及展示保护。
- [x] 实施方案、函数任务、输入/断言/命令、回退文档细化。
- [ ] 新增技术细则人工评审。
- [ ] S1—S10实施与Phase验收。
- [ ] S11 Final验收。
