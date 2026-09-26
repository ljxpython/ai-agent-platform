# 跨服务链路追踪 - 验收与验证记录

## 当前状态

方案已细化；业务实现未开始；自动化、真实链路、性能及回退验证均未执行。文档验证单列，不等于业务功能验收。

## 自动化验收矩阵

| 编号 | 输入/场景 | 必须断言 |
|---|---|---|
| V01 | 普通、超长、恶意 x-request-id/x-trace-id；W3C 关联头 | 内部仍为新生成 32 位小写十六进制；不回显/记录外部原值，不以 W3C 头建立关联 |
| V02 | 成功、401/403、422、安全 500、SSE 握手 | 进入应用编号范围的响应头/错误正文/context 一致；代理提前拒绝及 CORS 直接预检除外；浏览器能读取两头 |
| V03 | 并发项目请求、普通异常、CancelledError、流迭代 | 无串号，后请求不继承旧上下文；取消继续传播；token 创建/重置同任务 |
| V04 | 网关初始 read、scoped run/审批/取消；Catalog 独立签发 | 解码 JWT 两字段与当前请求一致，Runtime 现有校验通过；内部转发头一致；每请求闭包独立 |
| V05 | 无 HTTP 上下文的 Catalog、build_forward_headers 各调用方 | 非 HTTP 调用无伪造关联；仅外部头时不向下游回退使用，原行为兼容 |
| V06 | 幂等提交重试、reserve 冲突及失败 | request_id 不同、submission_id 相同、无额外 Run；reserve 前无虚假关系或派发事件 |
| V07 | 首请求超时/响应丢失后重试；接受后 mark 失败；复用详情读取失败 | unknown 不等于未执行；已知 Run 不抹除；保存全部尝试；不武断把首请求当执行来源；命令摘要/context_hash 不变 |
| V08 | 单/多 interrupt 审批恢复 | 实际 Run/parent_run_id/interrupt_key 准确，不改审批权限及恢复语义 |
| V09 | 取消 ACK、拒绝、超时 | 目标 Run 与 accepted/rejected/unknown 准确；ACK 不宣告 Run 已取消 |
| V10 | 新 metadata、缺字段历史记录、精确组合查询 | 两白名单均通过；request_id 历史格式可查；run_id 三字段 OR，参数间 AND；total 与列表一致 |
| V11 | 相同编号/Run 出现在不同项目、无项目权限身份、仅提供编号 | 授权项目过滤和关联过滤共同生效；无跨项目数据或计数泄露 |
| V12 | 缺单边时间、反向区间、恰好/超过 7 天、时区混合、非法 UUID/控制字符/长度 | 按 plan 第 8 节验证，非法公开 422，恰好 7 天允许，request_id 单独查不强制窗口 |
| V13 | 握手失败、start 发送失败、正常 EOF、空流 | 失败无 opened；成功 start 才打开；已打开连接最多一条 closed |
| V14 | 断连、上游异常、坏帧、主动关闭、未知取消、重复清理、线程跨 Run | 六种原因分类准确；frame_rejected 不被 finally 覆盖；不解析正文、不隐式取消、不固定线程流 Run；已发 200 不改记 499/500 |
| V15 | 日志抛错、metadata 合并失败、审计 DB 写入失败 | 两个观察动作尽量独立；原业务结果不变；不重发、不吞取消、不泄露原文；既有 HTTP 审计不增加独立派发行 |
| V16 | 旧审计、旧 API 与新 API 产物回退、在途 Run | 老记录可读；回退不修改/取消/重发/重签已有 Run，无数据库变更；旧实例不承诺新编号保证 |

测试优先扩展已有 unittest/项目测试，避免重复建框架；必要时集中新增：

- apps/platform-api/tests/test_request_correlation.py（V01—V03）
- apps/platform-api/tests/test_runtime_correlation.py（V04—V09、V13—V15）
- apps/platform-api/tests/test_audit_correlation.py（V10—V12、V15—V16）

上述三个是计划路径，当前尚未创建。

## Phase 自动化执行入口

从仓库根目录、已安装锁定依赖的 API 测试环境运行；仅使用隔离测试数据。以下既有用例必须回归：

```bash
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_delegation.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_catalog_delegation.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_run_requests.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_audit_http_resolution.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_cors_middleware_order.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_core_error_handling.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_gateway_event_redaction.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_gateway_sdk_adapters.py"
```

新测试创建后按各自文件运行 unittest discover；SQLite 与 PostgreSQL 要实际执行相同 repository 过滤用例，不能仅比较 SQL 编译字符串。PG 只用现成隔离测试库/已有 schema，不执行本专项 DDL；记录驱动、DB 版本和测试数据量。

Final 运行 API 现有完整测试、项目既有 lint/类型门禁及相关 Web 错误消费/CORS 验证；不得为跑验证擅自启动带迁移的 local-stack start。环境准备参考[本地开发](../../quickstart/local-dev.md)，启动/部署须另有授权，本轮不执行。

## 真实链路验收

前提：已有可用平台测试环境、授权测试用户/项目、既有 Runtime worker、已启用并成功导出的现有观测。记录 API/Runtime/GraphHarbor 版本及 worker 身份、观测导出状态；不保存 token、密钥、模型输出或工具参数。至少两个隔离项目用于权限检查。

| 编号 | 操作 | 证据与通过条件 |
|---|---|---|
| R1 | 通过平台真实提交，并保留响应头；使用同一幂等键重试 | 两次请求编号不同；审计 request_id 查询分别返回同一 submission/thread/run；不重复创建 Run |
| R2 | 在既有 Runtime worker 确认该 Run 实际执行 | 记录真实 worker/Run 对应证据，不能用直接调用 Runtime 或 mock 代替平台链路 |
| R3 | 从已导出的观测找对应 Run | 受信 request_id/platform_trace_id 与实际执行来源一致；观测记录定位信息可复核，不凭相近时间推断 |
| R4 | GET /api/audit 以 submission_id + created_from/created_to 查询 | 查到同提交全部已记录尝试；允许 unknown，明确不保证进程崩溃时记录完整 |
| R5 | 真实审批与取消请求；以 run_id 反查 | run_id/target_run_id/parent_run_id 命中关联请求；当前身份权限仍生效；取消 ACK 与实际终态分别取证 |
| R6 | SSE 断开并重连，线程流跨 Run | 新连接新 request_id，原 Run 正常延续；打开/关闭及原因正确，无隐式取消或持久绑定错误 Run |

精确查询示例（通过既有登录态/认证方式调用，不在证据中保存凭据）：

```text
GET /api/audit?project_id=<authorized-project>&request_id=<response-request-id>
GET /api/audit?project_id=<authorized-project>&submission_id=<uuid>&created_from=<ISO8601>&created_to=<ISO8601>
GET /api/audit?project_id=<authorized-project>&run_id=<actual-run>&created_from=<ISO8601>&created_to=<ISO8601>
```

缺真实环境、权限、worker 或观测导出条件时写“未验证”及具体阻塞；mock 通过不能替代 R1—R6。

## 性能与回退门禁

- 在现成隔离 SQLite/PG 数据中覆盖代表性 7 天窗口和跨项目数据量；记录数据规模、原查询/新增查询的计划及延迟分布。按测试环境已批准查询 SLO 判定；无既有 SLO 时只报告数据、标记性能验收未验证，不临时编造阈值。
- 关联查询无索引若不达标，另行评审索引方案，本专项不执行 DDL。不得以去掉授权/时间过滤换取性能。
- 后续获准回退演练时，仅替换 API 产物；验证历史审计兼容、已接受 Run 仍可执行和后续现有操作、没有重发/重签。新字段查询在旧 API 上不作为兼容保证。
- Runtime/GraphHarbor 不变，无数据库回滚；本轮不执行回退演练。

## Phase 验证记录

### 2026-09-26 文档与静态核查

- 已核对当前工作树：Catalog service/test、Runtime memory/test、smoke/stream 脚本等既有修改保留。
- 已重新静态核对内部编号、委托入口、reserve/mark、两处审计白名单及实际流/审计关闭路径。
- 发现并纳入 T5：现有 audited_body_iterator 在取消/异常时改写状态为 499/500；目标为保留已发送状态。
- 文档检查：python3 scripts/check_docs.py、git diff --check 均通过（退出码0）；四份追踪文档的结构、T1—T8全未勾选和相对链接已检查。6份既有非文档工作区文件按SHA-256复核保持不变。
- 链接检查范围限制：docs/FEATURES.md 原有“切线程澄清”记录指向 apps/platform-web/docs/changes/20260923-fix-zombie-clarification-on-thread-switch.md，缺少相对docs目录的上级前缀。本轮新增/修改链接均有效；该无关旧链接未修改，不能宣称FEATURES全页链接全通过。
- 业务自动化/集成/真实链路/性能/回退：均未执行。无 Runtime worker 或导出通过证据。

后续每个 Phase 单独记录日期、任务、命令、环境、退出码、证据及限制；不得写进 Final 充数。

## Final 验收记录

未开始。业务实现未开始，V01—V16、R1—R6、性能及回退均未验证。不得将文档检查通过标为 done、已交付或已上线。
