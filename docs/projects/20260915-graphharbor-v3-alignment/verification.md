# v3 验证矩阵与证据

本轮已获批准并实施，**A/B/C后端与前端交接完成，最终平台版本post30**。失败补验发现的recursion_limit修复与最终证据见[03收口记录](implementation/03-backend-closeout.md)。以下done只代表本表声明范围，不代表官方全产品兼容。浏览器及默认切换由用户明确后置。

## 验收矩阵

| ID | 场景与断言 | 层次／证据 | 状态 |
|---|---|---|---|
| V01 | 图内v3、Run SSE、线程Protocol的版本与入口逐项确认，官方SDK确实支持目标路径 | 官方Docs＋Reference＋锁定源码＋官方Server运行报告；0.13.0 Run SSE不提供目标typed v3，线程协议实测通过 | done |
| V02 | started、running、completed、failed、interrupted真实触发；根／子覆盖官方实际适用范围 | 双端真实图／HTTP／SDK；26项扩展差异保留；attempt重试与真实SIGKILL恢复证据见03 | done（声明范围） |
| V03 | graph_name/error/cause有值原样兼容，无值不编造；工具调用、Send、edge关联正确；未知cause变体仍可透传 | 五事件字段单测＋真实双端cause/error＋SDK同名两子图通过，ID相等关系保留 | done |
| V04 | 同名并发与深层嵌套；外层scope／目标scope；channel、namespace、depth过滤 | 双端HTTP深层图与GraphHarbor传输矩阵；SDK子图/cause；stream_subgraphs开关通过 | done |
| V05 | 提交失败、Worker恢复、旧lease、重复fanout无矛盾终态 | 真实PG事务失败测试＋Server全量；SIGKILL后恢复，唯一completed，见03 | done |
| V06 | 父捕获子失败、根失败、超时、取消竞态、重试耗尽 | 双端父捕获错误后根completed、真实失败；Server超时／竞态／retry回归。官方捕获场景无子failed，不编造事件 | done（官方可观测范围） |
| V07 | 实时／回放／cursor、序号间隙、重复订阅、过期cursor与控制帧 | HTTP传输矩阵、真实API重启回放、PostgreSQL过期cursor契约；稳定ID/seq/timestamp | done |
| V08 | 根／子及多中断、重复resume、重启后恢复与来源版本 | 双端两个中断分别回答；post29平台Worker重启文件链路多次v3恢复；23项Run请求回归含权限／幂等 | done |
| V09 | 官方SDK消费消息、工具、values、custom、checkpoints、input及终态 | 双端及wheel SDK通过；GraphHarbor checkpoints/custom为10/1，官方此订阅0/0；同工具重复handle是双端SDK限制，见交接 | done（保留已知SDK差异） |
| V10 | Dear真实双任务、研究、文件审批／交付、父取消、失败及Langfuse父子关联；默认v2／显式v2兼容 | post30真实v3双任务32.69s、父取消9.90s、研究154s、重启文件134.80s、原生步数失败3.42s、显式v2双任务22.57s；Langfuse实际回读与全部Run见03 | done（后端） |
| V11 | Dear浏览器同名任务、刷新／断网、审批resume、失败／取消、旧历史；共享Chat不退化 | 前端独立实施后的浏览器trace／测试；本轮不执行 | deferred |
| V12 | 包安装、版本锁、安全scope、隔离、性能、新Run回退v2／旧v3回放 | post29已发布／接入、实际wheel HTTP／SDK，40次性能与在途回退通过；无新列，安全契约随全量回归；post30补丁收口见03 | done（后端范围） |

五种事件全覆盖不等于每次有五条；多个子任务并发允许交错，但每个scope自己的因果／终态约束必须成立。取消/HITL都可能表现为interrupted，保留事实原因，不因此向用户生成不存在的审批问题。

## 复用的验证入口

GraphHarbor仓库，在隔离PostgreSQL／Redis测试环境配置完成后运行（不得指向业务库）：

```bash
uv run pytest -q libs/langgraph-runtime-pg/tests/test_public_runtime.py libs/langgraph-runtime-pg/tests/test_production_contract.py libs/langgraph-runtime-pg/tests/test_vue_protocol_events.py
uv run pytest -q libs/langhost/tests/test_official_protocol_compare.py
uv run python scripts/compare_official_protocol.py --help
```

A阶段按实际CLI参数把官方URL、GraphHarbor URL、场景文件和输出报告命令回填；对照服务必须使用同一组确定性图。复用现有`tests/javascript`包脚本跑真实SDK消费，记录实际命令，不预先编造不存在的测试名称。B完成后运行全量既有测试／lint／类型检查／包检查，不能只跑新用例。

platform-api目录：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_run_requests.py'
.venv/bin/python -m unittest discover -s tests -p 'test_runtime_gateway_sdk_adapters.py'
.venv/bin/python -m unittest discover -s tests -p 'test_runtime_gateway_runtime_contract.py'
```

runtime-service目录（真实测试会创建验收数据并消耗模型用量，沿既有本机验收环境）：

```bash
.venv/bin/python -m pytest -q tests/services/dearflow_agent/test_subagents.py tests/services/dearflow_agent/test_research.py tests/observability/test_langfuse.py
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 DEAR_PLATFORM_STREAM_VERSION=v3 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 DEAR_PLATFORM_CANCEL_CHILDREN=1 DEAR_PLATFORM_STREAM_VERSION=v3 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
```

其余失败、resume、发布包及SDK复跑命令见03记录。opt-in skip单独列出，不能折算通过。复用共享模型不得在测试清理时禁用用户原本启用的模型。

## 文档验证与当前结论

- 2026-09-15：官方Docs／Reference、源码及双端真实Server对照完成；根／子lifecycle、过滤、并行中断与版本继承已修复。失败验收另修Worker丢失recursion_limit，post30已发布并接入。
- 最终Server回归 **162 passed、18 skipped**；平台post30 Dear／模型／MCP／观测 **76 passed、6 skipped**；平台Run请求 **23项**、网关 **41项**。双端HTTP与实际wheel官方JS SDK通过，命令、时间、Run／thread标识见03。
- Server对齐：**done（声明兼容范围）**；平台后端试用：**done**；前端交接：**done**；前端代码／浏览器与默认切换：**deferred（用户要求，D及E1/E4）**。因此整个含前端迁移项目仍是部分完成，不标全项目done。
- 两仓库diff --check、发布产物hash核对与文档相对链接检查通过。没有执行git commit／push，没有修改前端代码。
- 不宣称官方v3完整兼容或生产长期稳定性已证明；26项扩展差异、SDK投影限制、真实模型耗时波动均已保留。默认v2未变，性能基线不是带宽优化承诺。
