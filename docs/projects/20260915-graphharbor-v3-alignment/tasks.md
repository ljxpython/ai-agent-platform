# 按阶段执行的任务清单

当前：**A/B/C后端完成，post30已发布并接入；D交接完成，E2/E3、E4消费者清点与E5文档完成。** D前端实现／浏览器、E1/E4实际默认切换deferred，由用户要求前端后置；这些不列为本次后端欠项。勾选证据见[验证矩阵](verification.md)与03记录。以下GraphHarbor路径相对独立仓库根，`apps/...`相对本仓库根；不能把外仓实现写入runtime-service。

## 阶段A：官方基线与差异

**做什么：** 用同一组最小图对照官方和GraphHarbor，确定“要补什么”。前置：本方案人工评审。预计1—2人天。

- [x] A1 冻结版本与契约。官方Server0.13.0、LangGraph1.2.11、Python SDK0.4.3、CLI0.4.31已在真实环境核实。官方本机31398启动并实测Run SSE：version=v3返回200但仍为旧形状，不能标记远程v3兼容；线程Protocol另行验收。证据见[01实施记录](implementation/01-official-baseline.md)。
- [x] A2 确定性参考图与实际事件采集完成：edge／Send／同名工具分派、失败及interrupt，原生resume测试通过；5种event和toolCall cause来自真实引擎，Send／edge未提供cause则保留缺省。新增`v3_graphs.py`、`v3.langgraph.json`、`run_v3_probe.py`和`test_v3_graphs.py`，3项测试通过，见01记录。
- [x] A3 `compare_lifecycle_reports`复用既有差分函数，归一化不保证UUID版本位的运行ID并保持关联；不删除cause/error等字段。双端原始采集及26项严格差异已保存，比较器正反例通过；这代表差异调查完成，不代表兼容全通过。
- [x] A4 两份GraphHarbor兼容矩阵已标partial，明确官方Run SSE不支持目标typed v3、线程事件待补齐范围；根API-owned终态与官方一致，无需放开原生根终态。详情见01/02记录。

**验收：** V01、V02有官方原始样本、复跑命令和差异报告；每个B改动能追到实际差异。若官方基线要升级，在plan.md写明版本与影响后评审，不边猜边改。

## 阶段B：通用Server补齐

**做什么：** 最小修复事件产生／传输／落库／回放／SDK消费，不放业务逻辑。前置：A。预计2—3人天。

- [x] B1 已修复根running与graph_name、保留实际子图名称；根终态仍由`RunRepository.finish`事务产生，没有放开原生根终态。真实Server成功／失败／中断采集及75项回归通过，见[02记录](implementation/02-lifecycle-and-resume.md)。
- [x] B2 五种event与可选graph_name/error/cause透传、未知cause、根错误文本、pending/retry映射及稳定timestamp已修复／测试；严格字节等价仍有既有扩展差异，未标整套协议done。代码与证据见02。
- [x] B3 一致的传输与scope。文件：`libs/langhost/src/langhost/streaming.py:_event_frame`、`_run_sse`、`runs_stream_existing`、`protocol_api.py:_wire_matches`、`protocol_event_stream`。分别验证Run v3与线程订阅、外层／目标namespace过滤、根与嵌套子事件、channel/depth、SSE控制帧、断点续读。必须保证官方SDK能实际消费，不只断言JSON字段存在。
- [x] B4 持久化与异常。复用`RunRepository.record_event`、现有lease／终态机制；增加失败、取消、重试、worker恢复及commit失败测试。无证据不改序列分配性能算法，无新增持久账本。
- [x] B5 测试与候选发布。补充`libs/langgraph-runtime-pg/tests/test_public_runtime.py`、`test_production_contract.py`、`test_vue_protocol_events.py`及`libs/langhost/tests/test_official_protocol_compare.py`；扩展`tests/javascript`真实SDK场景，覆盖发现子图、消息／工具投影及错误／中断。按既有release runbook锁步版本、构建、检查产物、发布候选包；文档记录兼容范围和未通过项。

**验收：** V02—V07、V10、V12通过；全套既有Server回归通过；新建干净环境安装候选wheel验证。官方Server对照缺失不能宣称全面兼容，暂停默认切换。

以下为前轮阶段性证据（其中“待验／未发布”描述当时状态，后续已由03记录补齐；B3—B5整项状态以上方为准）：

- [x] B3-a 真实官方JS SDK消费同名并发、cause、根失败、interrupt与input.respond恢复；官方31398与GraphHarbor31397均通过。文件：`tests/javascript/v3-lifecycle.mjs`，见02记录。
- [x] B3-b 已结束线程原样回放、since游标续读、单子scope的depth=0过滤通过；包括event_id/seq/timestamp逐字段一致。文件：`tests/acceptance_app/run_v3_probe.py:verify_replay`。API31397真实进程重启后同样通过；过期cursor等完整矩阵仍待验。
- [x] B5-a 隔离数据库迁移后全量Server回归157 passed、18 skipped；四个修改源文件mypy与修改Python文件ruff通过。跳过项不计通过；后续候选构建／发布结果见03记录。
- [x] B4-a 新增真实PostgreSQL成功提交失败注入，确认rollback、pending重试、持久事件与fanout均无虚假completed；文件`test_production_contract.py:test_success_commit_failure_never_publishes_completed`。随后生产契约回归51 passed、4 skipped（15.69秒）；真实进程故障全矩阵仍待补。
- [x] B5-b post29本地候选锁步、四产物构建、干净Python3.11安装／CLI／导入／app构造通过；文件与hash见外仓`docs/v3-post29-candidate.md`及02记录。未发布，安装检查不等于候选完整链路通过。

## 阶段C：平台后端试用

**做什么：** 包升级和显式v3完整交互，包括暂停再继续；不动前端默认。前置：B。预计2—3人天。

- [x] C1 `apps/runtime-service/pyproject.toml`与`uv.lock`锁步post30，仅升级GraphHarbor两包；安装／API与Worker启动通过。模型／工具／MCP等76项组合回归、真实显式v2双任务通过，继续使用官方图执行器，见03。
- [x] C2 统一通用版本设置。文件：`apps/platform-api/src/platform_api/core/runtime_contract.py`、`modules/runtime_gateway/application/service.py`的`launch_runtime_run`／`send_thread_command`、`adapters/langgraph/runs_sdk_adapter.py`。核对create、stream、join、wait、run.start实际入口；显式v3支持，非法值拒绝，未指定仍v2，不将version放进业务context。
- [x] C3 恢复版本。已从checkpoint对应已授权来源Run公开kwargs.version继承，旧记录默认v2，幂等重试同样继承；无需新增字段或迁移。resume既有模型／权限保护保留。post29真实Worker重启、checkpoint保持与多次审批恢复均保留v3；具体Run见03记录。
- [x] C4 回归与真实链路。文件：`apps/platform-api/tests/test_run_requests.py`、`test_runtime_gateway_sdk_adapters.py`、`test_runtime_gateway_runtime_contract.py`；Runtime `apps/runtime-service/tests/services/dearflow_agent/test_platform.py`、`test_subagents.py`、`test_research.py`。新Run、interrupt、重复resume、重启后resume、同名双任务、失败、父取消、研究／文件审批／产物、Langfuse及v2兼容完成，逐条Run/thread、耗时与结果见03。
- [x] C5 本项目implementation／verification／README及Dear交接、FEATURES同步；后端v3试用完成，前端代码与默认切换仍deferred。

**验收：** V08—V10、V12后端范围通过；v2和线程Protocol回归不退化。需要表结构修改才做迁移，不为“可能有需要”先建表。

- [x] C3-a 已查证来源Run公开kwargs.version，`send_thread_command`首次与幂等重试都继承已授权来源Run版本，旧数据缺省v2；无需新增数据库字段。`test_run_requests.py`22项通过；真实进程重启验收仍属于C3未完成部分。
- [x] C4-a 平台`test_runtime_gateway*py`41项组合回归通过（2.465秒）。新包接入、真实模型／文件／Langfuse链路仍待验。
- [x] C3-b 现有post28真实平台澄清后重启Runtime Worker、checkpoint保持，恢复均保留显式v3；`test_platform.py`增加每次暂停／最终回放断言。Docker授权后的完整文件链路也已通过，证据及Run ID见02记录；不因此勾选新候选包C3/C4整项。
- [x] C4-b **done：Docker授权后完整文件链路通过**。澄清→Worker重启／checkpoint保持→execute审批→文件执行→present_artifacts审批／发布→下载内容与SHA256验证，恢复Run均保留v3。`test_platform.py:test_platform_creates_and_completes_dear_run`：1 passed、1 deselected，38.08秒；线程`ad4ea66c-5b60-4ee7-9c0b-504453ecbe80`。使用现有post28，不能替代post29候选接入验收。
- [x] C4-c 平台现有post28显式v3双子任务真实模型、cause归属、根子隔离与回放通过，1 passed/14.25s；Run `6c688c2f-24f8-4f7c-a440-186b56ee4404`。新候选包全链路仍属于C1/C4待验。

## 阶段D：前端接入交接

**状态：本轮只写交接，前端代码／浏览器验收deferred。** 不阻止B/C后端工作，但阻止宣布全平台切换完成。预计前端另行评估。

- [x] D交接文档已完成：[具体文件、接口、SDK差异、消费者与验收顺序](frontend-handoff.md)。以下D1—D3是后续前端工作，不属于本次后端未完成项。

| 接入点 | 后续负责人需要做什么 | 后端要提供什么／验收什么 |
|---|---|---|
| `apps/platform-web/src/services/langgraph/client.ts`、`src/services/threads/session.service.ts` | 核对现有SDK线程订阅／命令实际调用；只在对应API支持时传版本，保留鉴权与幂等 | A协议样本、C恢复约束；确认非简单“全局version开关” |
| `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts` | 组合现有useStream处理执行、完成、失败、HITL、父取消；先用官方subgraphs／interrupts投影 | 暂停可继续、取消ACK不算终态、断流不显示成功 |
| 同模块`composables/useTranscriptMessages.ts`、`transcript.ts`、`trajectory/trajectory-adapter.ts` | 验证消息／工具／内容块／usage和子scope，不自己重建SDK聚合 | 根子不串线，文本／工具参数无重复，未知usage保留未知 |
| 同模块`components/SubagentCard.vue`、`components/SubtaskDetail.vue` | 移除实际存在的名称／调用ID拼namespace错误兜底；以官方投影和真实cause关联 | 两同名任务及嵌套可区分，子失败不误伤已成功父结果 |
| `apps/platform-web/package.json`及现有SDK patch | 锁版本，验证既有补丁与官方新版本交互；仅证实必要才升级／删补丁 | SDK单测、类型检查、Dear浏览器E2E及共享Chat回归 |

- [ ] D1 独立前端实施前核实上述路径与锁版本，记录要修改的最小集合。
- [ ] D2 新运行、HITL/resume、父取消、失败、断线／刷新、旧v2历史和跨Run订阅全部浏览器通过，截图或trace证据链接回填V11。
- [ ] D3 共享Chat回归；当前用户要求只交接，未授权实施前不得勾选D完成。

本轮后端验证给前端的具体交接：官方SDK1.9.28的`await thread.output`在失败时也可能resolve，必须检查根lifecycle.failed／interrupted；投影中断ID是`interrupts[].interruptId`，发命令用`interrupt_id`并携带该项namespace。官方0.13.0的HITL Run持久状态可为success，不能只看Run.status决定是否展示审批。GraphHarbor保留现有interrupted持久终态；这不是要求前端重建执行状态机。以上结论在两端SDK脚本中有实际证据，前端锁定版本仍须自行验收。

## 阶段E：默认切换与回退

**做什么：** C/D通过后逐入口切换，而不是修改Server全局默认。预计1—2人天，含观察。

- [ ] E1 Dear新Run入口默认切换：deferred，用户要求前端仅交接，依赖D浏览器验收；若仍走线程Protocol保留官方协议名称。显式v2保留。后续记录切换入口／包版本／时间／具体变更集合。
- [x] E2 实测V12：相同确定性图v2/v3各至少20次，首事件延迟、提交后终态可见延迟、事件数／字节、内存及错误率；明显退化先定位，不预建性能框架。真实模型耗时分开记录。
- [x] E3 验证回退到v2的新Run入口；实际wheel在途v3期间新建v2均成功，旧v3保留lifecycle回放。证据03及外仓artifacts/v3-inflight-rollback.json；不修改历史数据或原Run版本。
- [x] E4-a 消费者清点完成：Dear、共享Chat、overview、workspace、Python／HTTP；具体路径与保持原路径的约束见frontend-handoff.md。
- [ ] E4-b 其他消费者逐项验收再切换：deferred，依赖D浏览器验收。没有验收的入口留在原路径，不能因Dear通过自动切Chat／其他客户端。
- [x] E5 收口文档、兼容矩阵与FEATURES：分别标Server声明兼容范围、平台后端、Dear前端、其他入口状态。前端／默认迁移后置，26项扩展差异与SDK限制保留；post30源码／发布hash／真实验收索引见03。

## 每次交付记录格式

`任务ID → 需求行为 → 实际修改文件/函数 → 命令 → 结果/证据路径 → 遗留限制`。

不以“代码已存在”标done，不以mock代替真实Server／浏览器，不以一次成功代替生产稳定性门禁。不自动创建分支、提交或推送。

## 本轮完成项索引

B3/B4/B5、C1—C5、D交接、E2/E3/E4清点/E5 → [03后端收口记录](implementation/03-backend-closeout.md)：真实HTTP／SDK、故障／恢复、post30最终162项Server回归、平台76项组合回归、真实模型链路、发布与消费者审计。既有B/C子项中的“未发布／待验”是此前阶段记录，最新状态以本索引及03记录为准。
