# SSE 专项 — 验证执行包

> 本页定义后续实施验收，不代表已通过。2026-09-26本轮只有文档与只读/隔离探针；Phase证据和Final结论分区记录。

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

## 5. Final与回退

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

API全量依赖按该服务现有测试配置准备；环境失败单列，不作代码通过。真实三服务、容量、安全和回退证据缺一项时按partial/blocked/deferred说明，不写done。

隔离回退演练：记录旧API/Web产物→部署新API+旧Web验证握手兼容→部署新Web验证V07/V09/V13→运行中回退Web→原Run仍存在且无多余cancel/start→重新打开可读快照→按实际需要回退API并验证兼容。不要回退Runtime/数据库，不在用户工作树执行git reset。安全修复回退风险单列。

## 6. 执行记录

### Phase：2026-09-26规划核实

- 静态审阅平台、指定open-swe工作树、锁定SDK和GraphHarbor post33相关代码；参考仓库含未提交改动/冲突，未启动或修改。
- 实际运行内存Node探针，退出码0：正常EOF仅一次请求；网络故障第一次since:9、第二次省略since；activate清理触发dispose一次。注入fetch，无真实服务/业务代码写入。
- 三段真实样例、浏览器视觉、线程保活、410、容量和回退均未执行；不能把上述探针当功能验收。
- 文档检查已执行且通过：python3 scripts/check_docs.py、git diff --check；本专项5份文档及父项目2份入口的相对链接/代码围栏检查通过。以上仅证明文档一致性，不证明功能实现。

### Final

未开始。方案就绪不构成功能done；用户已同意进入下一专项，等待后续明确编码指令及真实验收。
