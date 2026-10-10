# F02 重复工具调用保护实施记录

## 改动时间与范围

2026-10-09，用户已完成G0评审并授权所有非前端工作。对应15/F02-T01—T06、T08；T07由前端同事实施。进度与Phase/Final记录以15专题为准。

## 共享判定与接线

- 新增 `apps/runtime-service/src/runtime_service/middlewares/loop_detection.py`：`LoopDetectionMiddleware` 的 sync/async官方hooks；普通私有checkpoint channel保存owner、消息游标、用户边界和固定摘要；不新增Executor、进程历史或ToolMessage克隆。
- `_completed_batch()` 只读最近64条消息、最多32个调用；单结果最多65536字符、批次最多262144字符；非JSON/多模态/外置/已知截断/不完整配对跳过。参数JSON最多16384字符、1024节点、16层深度。call ID不参与语义签名，排序保留重复项和结果关联。
- `read_file`仅补实际默认offset=0/limit=100，其他参数完整比较；同步只读观察集合固定为ls/read_file/glob/grep/read_reference，与组合根传入集合求交。
- 连续第3批后复用system收尾提示与预算custom；第5批后抛 `RuntimeExecutionError("runtime.loop.detected")`，没有第6次模型请求。
- DearFlow、Showcase主子与Reference显式装配同一实现，位于预算后、已消费inbox之后、最终上下文预算检查之前；Workflow不接。`AGENT_LOOP_DETECTION_ENABLED`严格0/1、默认0，lifespan启动校验。

## API、诊断与安全出口

- Runtime auth和Platform core拒绝递归私有字段注入；SDK共享投影递归去掉runtime_loop_state。保留普通模型/工具正文。
- 复用runtime_budget_notice的两个精确码与run/tool_rounds组合；固定5/3/2和5/5/0，未知字段剥离。
- 可信错误类型和完整loop码精确投影，不substring匹配；固定安全中文文案，保持原有对象/字符串形状。
- Runtime安全事件 `runtime.loop.transition`，query增加v1可选loop_detections(max20)，API严格DTO组合校验；graph错误可含loop码，model_errors不接受loop。

## Phase与问题

- 首轮共享判定27项通过（sync/async compiled graph、恢复、默认参数、多重集、保守跳过）；API新契约28项通过。
- 借用API解释器会默认加载主checkout；所有后续API验证显式设置当前worktree/src的PYTHONPATH。先前旧源码测试失败不算新实现证据。
- 共享测试的固定AI ID会覆盖旧checkpoint消息，恢复用例改为每次独立ID；错误断言读code，不依赖LangGraph追加task注释的展示文本。
- 已有API用例project-1非UUID和Runtime ACL测试verify参数期望过期，另行对照HEAD记录，不借本轮修改无关生产逻辑。
- 真实ls返回列表包含 `/large_tool_results/` 目录，不能以目录子串判断结果已外置；已收窄为DeepAgents实际外置提示并增加回归。RuntimeConfig补配对的占位ToolMessage标记 `_runtime_tool_call_repaired`，detector跳过；不将“补齐历史”误认作“真实执行”。
- API的共享SSE递归清洗原先会把已精确投影的loop对象再泛化；现按完整loop码保留安全投影，已测幂等、伪异常负例和v2/v3真实帧。
- PostgreSQL摘要测试显式降低官方摘要trigger，五轮中确认至少一次自动摘要；维护/new Run复验通过。清理失败续跑用 `aupdate_state(..., None, as_node="__end__")`，与锁版本源码一致。
- Worker验收按pytest参数拆为boundaries/recovery，既有隔离stack继续复用；inbox夹具补Idempotency-Key、随机RUNTIME_SELF_URL与消息授权回调，不访问默认8123。真实样例已保存到 `evidence/f02-http-samples.json`，不记录token、参数/结果签名或工具原文。
- Runtime全量1002 passed、15 failed；API全量421 passed、35 failed。Runtime12项和API35项在原HEAD复现；两项inbox崩溃窗口也在原HEAD同样失败；向量跨服务测试指定API解释器后通过。不宣称全仓测试全绿。
- 真实boundaries正文17场景通过；`-k boundaries` 会因函数名误选recovery，重复组在启动时主动清理，整会话不记通过。独立recovery退出码0：Worker崩溃接管claims=2、五轮已提交工具且3/5状态不丢；cancel/inbox、ACL分享/撤权、私有输入、410/OpenAPI、PG摘要和关闭/旧HEAD/重开均已验证。
- 增加真实模型独立节点，正常分页预置8行；用平台真实请求上下文的DEFAULT_TENANT_ID推导工作区，不能用临时Project表的tenant UUID代替委托范围。检查实际read_file参数/成功结果、两次复读同结果及原文件未变，避免只断言Run success。先前单行分页两次越界不作正常分页证据，provider_timeout及冷启动未ready也如实记录。
- P01同负载两次模型调用，最后模型步骤6/9、私有状态2/378 bytes；新增hook有步骤成本，不提高recursion_limit。高负载延迟差分仅实验记录，不能视为生产SLO。
- 前端交接补真实HTTP登录及pytest --trace隔离入口；随机API地址/项目/model通过Pdb指定字段取得，合成账号复用现有fixture。禁止输出完整ready.json或把调试退出当自动测试通过。
- 最终真实模型独立节点1 passed、96.03s：读取分析1次、不同offset成功分页3次、同参数同结果复读2次，三Run均success/claims=1/loop空，原8行内容及文件数不变。Runtime/API lint、新增6个Python文件format、变更Markdown链接和diff空白均无新增问题；根目录44项lint和4个既有文档坏链接另行注明。
- 本轮只完成非前端范围，整体Final留给T07；实际任务勾选和全部验证详见15，安全摘要已持久化到 `evidence/f02-verification-summary.json`。
