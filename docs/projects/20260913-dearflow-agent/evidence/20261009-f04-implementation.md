# F04 实施验证证据

日期：2026-10-09。生产锁版本不变；所有 PG/Redis/HTTP 服务使用隔离临时目录和随机端口，没有修改现役数据库、发布依赖或部署。前端未实现/未执行浏览器验收。

## 已执行 Phase

| 范围 | 真实结果 | 说明 |
|---|---|---|
| Runtime 四个定向文件 | 87 passed / 1 skipped，297.80s | ConversationOffloading、工具外置、Dear/Showcase装配；skip为现有Showcase live模型开关未开启，不计通过 |
| 干净锁环境定向复验 | 102 passed / 1 skipped，127.98s | 上述四文件加签名scope契约；包含新增旧路径、单行限制和180组async矩阵。仍是同一个既有Showcase live skip |
| 官方结果外置与引用保护对照 | 25 passed，90.23s | 含官方父子同ID碰撞复现、保护后父子/并行子图各自原文、多模态Command、失败/取消等；后续新增单行及矩阵另验 |
| 旧引用与单行读回限制 | 2 passed，67.98s | 新middleware可读旧路径；巨大单行明确truncation warning、不再次外置、不声称canary可恢复 |
| API event redaction / context offloading | 31 passed / 6 subtests，39.91s | 普通files大结果仍可见、private guard不拒绝普通files的现状；无API生产改动 |
| API workspace | 最新4 passed，31.72s；此前一次2 failed / 2 passed，416.05s | 失败为两个真实HTTP服务启动超时，独立重跑通过；真实HTTP/CSP/重启均覆盖，未改生产清洗逻辑 |
| 容量/并行基线 | 1 passed，95.98s；180组真正async并行 | 12K/32K/128K、1/5/10结果、五种文本与四阈值；45组校准阈值，产物见[矩阵JSON](20261009-f04-budget-matrix.json) |
| 真实模型摘要质量 / overflow | 2 passed；同轮中部用例1 failed，154.62s | 10次摘要均保留7个约束/来源/未完成锚点；注入context_length_exceeded后真实摘要/回答成功。中部题目只写middle，模型实际读第751行，canary在第601行；PG checkpoint已核对 |
| 真实模型指定中部回读 | 1 passed，101.88s；模型执行10.44s | 明确offset=600、limit=1后fetch/read/answer闭环；2次工具调用，provider input 2879/3317/3502、output 29/132/33，精确保留canary |
| 锁文件临时安装 | `uv sync --frozen --offline`通过 | 新临时venv从现有锁安装141包；DeepAgents 0.7.8、GraphHarbor双包post43，不更新锁或现役环境 |
| 真实HTTP/PG/Redis/Worker整链 | 1 passed，320.95s | Dear v3/Showcase v2主子大结果、state/history/ACL、两次Worker重启、HITL approve/reject和关闭开关回读；临时锁环境执行 |
| PG连接/摘要回退子测试 | 1 passed，8.42s | 真实两次整理跨连接保留原消息、旧wrapper读取和继续运行，不使用内存Saver代替 |
| 真模型追加子测试 | 3 passed，38.03s | 最新指定中部取证1.42s、10次摘要全部保留7锚点、overflow真实摘要/回答及普通followup |
| Thread策略/授权契约 | 9 passed，11.17s | 平台策略覆盖客户端context、授权更新、他人策略拒绝及Thread授权 |
| 前端交接启动脚本 | 真实隔离栈/登录/项目读取通过 | 直接执行交接文档Python片段；Runtime ready、API health、账号login、projects均200；没有启动Web或计浏览器通过 |
| Python质量检查 | 16文件lint/format、`git diff --check`、12份变更Markdown规则通过 | JSON结构/脱敏白名单检查和F04链接通过；全仓文档检查仅报其他专项已有本机路径 |

Runtime命令（服务目录）：

```bash
PYTHONPATH="src:tests" .venv/bin/python -m pytest \
  tests/middlewares/test_conversation_offloading.py \
  tests/middlewares/test_tool_output_budget.py \
  tests/services/dearflow_agent/test_context.py \
  tests/services/showcase_demo/test_agent.py -q -p no:cacheprovider
```

干净环境命令（服务目录；`<f04-venv>`为新临时目录，未复用现役venv）：

```bash
UV_PROJECT_ENVIRONMENT="<f04-venv>" uv sync --frozen --offline
PYTHONPATH="src:tests" <f04-venv>/bin/python -m pytest \
  tests/middlewares/test_conversation_offloading.py \
  tests/middlewares/test_tool_output_budget.py \
  tests/services/dearflow_agent/test_context.py \
  tests/services/showcase_demo/test_agent.py tests/runtime/test_auth.py \
  -q -p no:cacheprovider
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="<api-python>" \
  CONTEXT_MODEL_ENV_FILE="<managed-model-env-file>" \
  <f04-venv>/bin/python -m pytest tests/e2e/test_tool_output_budget.py \
  -q -s --tb=short -p no:cacheprovider --basetemp="<new-disposable-test-dir>"
```

API命令（服务目录；复用已具备pytest的Runtime测试解释器）：

```bash
PYTHONPATH="src:tests" ../runtime-service/.venv/bin/python -m pytest \
  tests/test_runtime_gateway_event_redaction.py \
  tests/test_runtime_gateway_context_offloading.py -q -p no:cacheprovider
```

## 容量结论与限制

校准初值 `T=max(1,min(20000,B//16))` 保留；输出256时，12K/32K/128K对应B=10720/30144/121344、T=670/1884/7584。50000字符的正文在校准下均外置；名义12500/20000仍不外置，因为比较为严格 `len>4*T`。

async并行样本：ASCII/CJK/单行文本预览1676字符，常规多行2493，长行10745。12K的5/10个长行预览仅工具文本已估算13475/26950，超过B=10720。此条件由总预算guard/overflow安全处理；不新增第二个preview算法，不承诺所有任务均能在小窗口成功。CJK仍是字符估算，不是provider tokenizer基线。单行内中部取证无法由行offset解决，原文完整但分页可能只返回大小警示，重新格式化需要原backend可读能力，不能假定宿主shell有StateBackend文件。

## HTTP失败排查记录

- a：1 failed，502.44s；测试模型 `_generate` 未接收官方异步传入的stop/run_manager，Worker原始日志定位后修fixture签名。
- b：1 failed，315.00s；Run成功且中部canary读取成功，随后state一次502；后续c主图/权限/state/history未复现。保留异常取证，不冒充全绿。
- c：1 failed，1414.83s；Dear v3/Showcase v2主图大结果、hash、state/history/ACL和首次Worker重启回读通过；开关关闭后的连续恢复fixture复用了固定读call ID，导致重复循环。已改read_file fixture生成独立ID并补last message元数据；后续d继续核实。
- d：1 failed，573.23s；fixture请求了未注册的researcher，真实Dear研究子图注册名为general-purpose，Run成功但没有执行子图。已改测试请求，不扩生产权限。
- e：测试启动早期主动停止，修正Showcase execute追加成功回执后全文hash的预期；不计通过。
- f：setup 1 error，332.22s；Runtime启动180秒超时，日志只有fixture runpy警示，未进入业务。同期主机负载很高；之后独立webapp导入10.23s、API Workspace四项31.72s通过。没有证据将此归为生产业务异常。
- g：1 failed，161.15s；Dear主子成功，Showcase子图execute进入审批。平台按Thread策略覆盖客户端context，fixture未设置Thread策略，仍是默认review；已通过现有PATCH access-policy设置workspace_write，不改生产权限逻辑。
- h：1 passed，320.95s。全部主/子图、HITL批准/拒绝+Worker重启、关闭开关、PG及真模型子测试通过。后补PG统计仅改测试记录口径，原SQL在同一隔离PG实测三列正确，不再重跑已通过的业务链路。

上面都是Phase证据，不是F04 Final。本轮非前端已闭环；15/R05仅保留同事前端回归和完成后的Final，其他迁移事项不纳入此次F04。

## 实样本、成本与边界

[HTTP/模型/PG证据JSON](20261009-f04-http.json)保留真实隔离Run/Thread ID、原文hash、provider usage和测量口径；[前端实样本](20261009-f04-frontend-samples.json)只投影公开ToolMessage、namespace、文件键/长度与部分SSE事实，不复制完整正文、checkpoint身份配置或凭据。隔离栈已关闭，样本ID只能用于对应证据，不能在现役平台查询。

| 测量 | Dear v3 | Showcase v2 |
|---|---|---|
| 初次root结果原文bytes | 110885 | 110885 |
| 初次state HTTP bytes | 127706 | 117626 |
| 初次整Run SSE bytes | 11361954 | 1169304 |
| 初次Run检查点blobs bytes（局部） | 9993 | 656 |
| root/child/两次recover后的PG blobs / writes / JSON逻辑bytes | 151299 / 605708 / 1041234 | 113550 / 568206 / 983265 |
| 初次root链路耗时 | 17.21s | 8.38s |

两图stream设置/工具/系统提示不同，这不是受控v2-v3性能优劣对照。初次`checkpoint_blobs`不包含Delta `checkpoint_writes`或checkpoint JSON，不能据此宣称存储缩小；补测也不是物理表/索引/TOAST/WAL/备份总成本。定向对照证明有效模型输入缩短，无法推导PG或网络变小。

实测v3 `tools/tool-finished`的子图search_web输出仍有110887字符原文，后续values/ToolMessage已变短预览。浏览器SDK assembled output与落盘message可能不同，交接要求同事核验`transcript.ts`的优先级与刷新一致性，不承诺“所有流只含摘要”。普通`files`依已批准范围保留现状，私有化/直接改写防护另评审。

额外真实HTTP探针：私有state字段注入400 `invalid_runtime_payload`、私有Run input400 `runtime_private_state`、跨项目state403 `thread_action_denied`。本测试peer无Thread read也403；跨租户签名scope使用已锁定契约102通过集合里的`test_auth.py`，没有创建第二租户真实HTTP栈。

## 范围外回归问题

- API扩展三文件：28 passed / 1 failed / 4 subtests，5.32s。失败是既有`test_runtime_gateway_runtime_contract.py::test_run_launch_attaches_opaque_model_reference_from_platform_runtime_context`：`project-1`非UUID且fixture未mock新增模型稳定性查询。该文件和对应API生产文件无本轮diff；之后单独策略/授权9项通过，未把失败隐藏为skip。
- Runtime鉴权/文件边界扩展：47 passed / 1 failed，4.52s。既有`test_platform_auth.py::test_thread_auth_rechecks_signed_platform_acl`严格mock kwargs未包含当前独立ACL客户端的`verify=False`。测试/生产模块无本轮diff；服务lifespan使用的共享客户端仍默认验证TLS。没有为使测试变绿扩大F04或修改安全策略。
- `scripts/check_docs.py`全仓exit 1：38条既有本机绝对路径，分布在其他knowledge/专项；本轮12份变更Markdown调用同一`check_file`规则全部通过。

这些问题不阻塞已验证F04非前端切片，但不能宣称全仓门禁全绿。前端、部署环境、生产负载和整个F04 Final未执行；延期项保持15原范围，不新增第二套实现。
