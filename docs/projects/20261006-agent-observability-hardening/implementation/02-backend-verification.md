# 后端与 Runtime 验收证据

**日期：** 2026-10-07。**范围：** E01-E05、S01-S04、Q01-Q05的后端工作；前端F01-F04和浏览器联合验收另行完成。

## 环境与证据

工作树0657，detached HEAD，基线 `0bc15df1840c83750d821c93fb65600d0d483fa4`。使用当前工作树源码，没有提交、部署或重启现役服务。

Python 3.13.9；GraphHarbor/graphharbor-runtime 0.13.0.post41；LangGraph 1.2.11、SDK 0.4.3；LangChain 1.3.17、Core/OpenAI 1.6.0；DeepAgents 0.7.8；Langfuse 4.15.1；OpenAI 2.46.0；OTel SDK 1.42.1；HTTPX 0.28.1。

- [最终原始证据](backend-runtime-evidence.json)：16个功能场景、真实安全DTO、HTTP Envelope、分段并发和startup A/B；`complete=true`仅表示脚本跑完，不能据此推断观测容量达标。
- [初次完整测量](backend-initial-evidence.json)：保留50次读超时和较高机器负载下的A/B，不用后续成功覆盖失败记录；其中不存在模型的分类尚未修正，最终以最终证据为准。
- [独立查询复测](query-capacity-evidence.json)：排除模型执行影响的1/10/50并发对照；该轮未记录供应商状态码，原因以最终复测的429证据为准。
- [隔离回退证据](rollback-evidence.json)：固定基线源码的采集/两个Agent工厂/Runtime应用，撤下平台查询入口后六个场景通过，独立于上面的16个新功能场景。

最终隔离数据库 `graphharbor_observability_dddde4d356ea`，Redis prefix `graphharbor:observability:dddde4d356ea`。Runtime执行API、Worker、provider stub和Platform API通过真实本地HTTP连接；平台使用临时SQLite，API运行于独立线程事件循环，全部服务仍在同一Python进程。数据库保留，临时平台库及本次服务已由脚本退出清理，因此这些Run ID不能直接在现役页面查询。

## Phase 回归

这些为实施过程已经执行的回归，和下方独立Final链路记录分开；数量不能相加当作互不重复的总测试数。

| 范围 | 实际结果 | 说明 |
|---|---|---|
| Runtime主定向 | 240 passed、1 skipped、5 deselected、17 warnings | 观测/middleware、四个组合根、授权、workflow与定时任务相关回归 |
| Runtime新增诊断文件，最新复跑 | 35 passed、5 warnings | 新增已安装SDK的OpenAIModelNotFoundError分类；普通404仍保守兜底 |
| Platform API组合 | 63 passed、4 skipped、524 subtests passed | DTO、权限、Run归属、JWT与HTTP矩阵 |
| debug错误槽位修正后API定向 | 37 passed、1 skipped、311 subtests passed | 普通/Protocol/v3 SSE、JSON错误出口、SDK适配 |
| 跨环境JWT契约 | 5 passed、50 subtests passed | 固定当前源码；测试TTL与启动预算独立于生产默认60秒 |
| SDK/gateway组合 | 38 passed、10 subtests passed | 原消息/工具结果保留，错误出口安全投影 |
| 扩展DearFlow | 103 passed、32 skipped、3 deselected、3 failed | 三项为测试子进程导入/启动预算超时，原命令不是全绿 |

扩展回归的跨服务向量独立复跑通过；MCP两项先在仅扩大验证进程启动预算后通过，最后原45/60秒预算复跑 **2 passed in22.86s，退出码0**，未改测试或生产源码。所有skip/deselected均不计为pass；Anthropic未配置真实连接，本期实际启用provider smoke是DeepSeek代理，不能把本地stub或SDK异常测试称作Anthropic线上验收。

原预算MCP最终命令在Runtime目录执行：

```bash
PYTHONPATH="src:tests" LANGFUSE_ENABLED="false" OTEL_ENABLED="false" \
.venv/bin/python -m pytest tests/services/dearflow_agent/test_mcp_task_probe.py \
  tests/services/dearflow_agent/test_mcp_tools.py -q --tb=short
```

最新诊断测试在Runtime服务目录执行，退出码0：

```bash
PYTHONPATH="src:tests" .venv/bin/python -m pytest \
  tests/observability/test_diagnostics.py -q --tb=short
```

API错误槽位修正后在Platform API服务目录执行四个文件；最终按下面的实际解释器复跑，37 passed、1 skipped、311 subtests passed in32.64s，退出码0：

```bash
PLATFORM_TEST_PYTHON="$HOME/PyCharmMiscProject/ai-agent-platform/apps/platform-api/.venv/bin/python"
PYTHONPATH="src" "$PLATFORM_TEST_PYTHON" -m pytest \
  tests/test_run_diagnostics.py tests/test_runtime_gateway_http_matrix.py \
  tests/test_error_response_contract.py tests/test_runtime_gateway_sdk_adapters.py \
  -q --tb=short
```

该解释器实测为Python 3.13.9、pytest 9.1.1；通过PYTHONPATH确认platform_api来自本工作树。当前工作树Platform API的Python 3.14环境尚无pytest，因此复用已有3.13环境，没有安装依赖或改变环境。SWIG弃用、LangGraph v3 beta和fake模型无法解析名称的warning没有计为失败。

## Final 后端链路

最终实际命令从仓库根执行，退出码0；本机env文件仅作为配置来源，密钥和具体供应商地址不写入仓库：

```bash
PYTHONPATH="apps/runtime-service/src:apps/platform-api/src" \
OBSERVABILITY_ENV_FILE="$HOME/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/.env" \
OBSERVABILITY_EVIDENCE_PATH="/tmp/agent-observability-final-evidence.json" \
apps/runtime-service/.venv/bin/python scripts/verify_agent_observability.py
```

加入 `OBSERVABILITY_VERIFY_PROFILE="query"`只跑已有基本功能和分段容量测量，不能代替完整Final。SDK flush和最多40次等待仅用于验证观测最终一致，生产查询不flush、不循环重试；每次Langfuse查询保持2秒总预算、最多100 observations和50 traces。

| 场景 | 原始证据case/sample | 必须核对的结果 |
|---|---|---|
| 本地provider真实HTTP 429 | native_429_safe_query / provider_rate_limited | 原生error、模型码provider_rate_limited、429、同Run/trace、无canary |
| JSON/两种SSE安全出口 | public_error_and_scope_isolation | Thread/Run/state/history、普通Run SSE debug task_result、Protocol lifecycle无原文；帧身份保留 |
| 非owner共享read及真实撤权 | shared_read_and_real_revocation | 拒绝→共享read成功→撤销后403；跨项目403、不存在Run404 |
| 正常Run | native_success / success | 原生success、无模型失败记录、有startup及graph |
| 同Thread两Run | same_thread_run_isolation / same_thread_second_run | 首Run success且无失败记录；第二Run error带429；trace和执行编号分别绑定 |
| fallback恢复 | native_fallback / fallback | 原生success，同时保留一次模型429，不将模型尝试当终态 |
| 恢复后工具失败 | native_later_tool_failure / later_tool_failure | 原生error，模型尝试仍独立；graph error_code=null，不沿用429 |
| 两个并行research子任务 | parallel_subagent_run_identity / parallel_subagents | 同一原生Run、scope=subagent，两条不同namespace；正式Showcase装配，仅模型为受控fixture |
| factory失败 | native_factory_failure / factory_failure | 原生error、partial、有失败启动阶段，没有虚构graph |
| HITL/取消 | hitl_not_provider_failure、native_cancel | 原生interrupted，无provider错误；保留不同图观察结果 |
| 关闭采集回退 | disabled_capture_normal_run / disabled | 正常Run success、本地诊断仍在；查询disabled/not_configured |
| 查询无记录/连接故障 | query_outage_does_not_change_run / not_recorded、backend_unavailable | 真实API查询配合受控观测故障注入；200 unavailable，原生Run仍success |
| 安全HTTP故障 | safe_http_fault_envelopes / http_samples | 401/403/404为真实授权/不存在资源；502/503/504为应用上游错误注入，经实际HTTP出口生成安全Envelope |
| 已配置DeepSeek | real_deepseek_success、real_deepseek_error | 真实代理成功；受控不存在模型404，SDK包装后分类model_unavailable |

模型注入、factory错误、工具错误和上游HTTP错误均只在脚本fixture中构造，没有扩大生产fallback、模型重试或权限。取消时GraphHarbor checkpoint writer可能失去Run所有权：原生interrupted而graph观察failed；本期正确保留两种事实，没有修改GraphHarbor或把它误记成provider失败。

本地JSON、真实Langfuse SDK内存exporter和OTel内存exporter分别有canary断言；查询/公共错误字段只有有限白名单。GraphHarbor自有私有原异常日志按R05留在本轮范围外，不能宣称全系统原始日志已治理。

## 查询容量与降级

| 测量 | HTTP200 | 诊断availability | 整体p50/p95 ms | Langfuse段p50/p95 ms |
|---|---|---|---|---|
| 单查询 | 1/1 | 1 available | 335.86 / 335.86 | 165.62 / 165.62 |
| 10并发诊断 | 10/10 | 1 available、9 unavailable | 1449.68 / 1572.96 | 147.39 / 250.91 |
| 50并发原生Run读 | 50/50 | 不适用 | 4366.51 / 4778.55 | 不适用 |
| 50并发诊断 | 50/50 | 50 unavailable | 6819.31 / 7535.70 | 268.83 / 651.07 |

最终9次/50次降级均有SDK ApiError/status=429证据；这是Langfuse查询限流，和模型provider的429不同。50并发测量证实安全降级和原生Run不变，**没有证明50并发可获取完整诊断**。需要该容量时提高观测服务限额，在分进程、独立平台数据库和批准SLO下重验；本期没有批准延迟SLO，不补造达标阈值，也不以无权限缓存绕过当前ACL。

初次50请求全部ReadTimeout，p95=39562ms；该轮机器负载较高，服务/客户端共进程且客户端20秒预算。最终测量将仅验证客户端预算调至120秒以收全结果，生产ACL默认10秒、Runtime上游和Langfuse2秒预算没有提高。较低负载复测整体p95约7.54秒，仍不能归因成生产性能提升。

最终进程最大RSS 570621952 bytes（约544MiB），包含两个API、Worker、provider、采集buffer和验证数据；是峰值记录，不是单查询增量或无泄漏证明。实际连接随应用lifespan关闭，查询取消/超时由单元测试验证没有额外SDK重试。

## 启动成本

同一reference fake模型任务，每种模式预热3次、测50次；远程导出关闭，本地Python分配峰值用tracemalloc。该工具自身有开销，两组顺序执行，不用它推导生产延迟承诺。

| 指标 | baseline p50/p95 ms | enabled p50/p95 ms |
|---|---|---|
| factory | 121.835 / 160.091 | 140.384 / 268.138 |
| 首模型，从factory开始 | 163.295 / 209.743 | 185.691 / 317.921 |
| 首token，从factory开始 | 165.973 / 211.985 | 188.616 / 322.164 |
| graph执行 | 80.047 / 101.070 | 84.940 / 112.862 |

baseline/enabled Python峰值分别7950587/7103409 bytes。未将较低峰值解读为优化；不包含生产provider/MCP/workspace启动。真实队列饱和丢弃和OTLP HTTP503故障由已有SDK/exporter测试执行，进程有限计数器在JSON中保留；已安装SDK没有被本次使用的公开队列深度读取接口，因此未读取私有队列或声称测出线上队列容量。

## 完成度与交接

后端授权范围Final为 `done`：模型诊断、安全导出、启动关联、只读接口、错误投影、降级和回退已验证。项目整体 `partial`，只留前端F01-F04、FV01-FV10及浏览器联合验收，后端当前无必须等待用户条件才能继续的事项。

供应商限额和首次测量失败按以上事实保留；任何生产上线/持续联调环境并未由本轮部署，不把本地隔离通过当生产容量通过。JWT/SSE原有草案及其旧专项未完成门禁不因本轮修改而毕业。

静态门禁：本次34个Python文件 `ruff check`、`ruff format --check`及 `git diff --check`通过；本项目8份Markdown相对链接和4份JSON格式/敏感字段已核验。全仓 `scripts/check_docs.py`仍因范围外既有绝对路径退出1，本项目未命中。前端对接规则和实际样例导航见 [frontend-handoff](../frontend-handoff.md)。

## 独立回退门禁

2026-10-07实际从仓库根执行，六个场景passed，退出码0：

```bash
PYTHONPATH="apps/runtime-service/src:apps/platform-api/src" \
OBSERVABILITY_VERIFY_PROFILE="rollback" \
OBSERVABILITY_EVIDENCE_PATH="/tmp/agent-observability-rollback-evidence.json" \
apps/runtime-service/.venv/bin/python scripts/verify_agent_observability.py
```

此模式不访问Langfuse/provider远程服务；加载固定基线 `0bc15df1840c83750d821c93fb65600d0d483fa4` 的Langfuse adapter、reference/workflow工厂及Runtime custom app，关闭远程导出，并在隔离Platform app移除公开diagnostics route。真实HTTP返回安全404，Runtime路由表确认无内部diagnostics入口；普通原生Run成功且SSE保留probe-ok，审批/拒绝均从实际state读取interrupt_id后恢复为success，取消为interrupted，新诊断事件为0。隔离数据库 `graphharbor_observability_927e33f8233e`保留，本次服务已关闭。

这是源代码级隔离回退验证，未执行现役服务版本切换或部署回滚；现有数据库schema未变，不新增诊断数据库回滚。前版adapter在关闭远程导出时不装诊断回调，所以新事件数为0是预期，不等同于新版本关闭导出后的本地诊断行为。取消仍有既有GraphHarbor checkpoint writer冲突日志，原生状态维持interrupted，未修改依赖包。

脚本补证过程的三个用例问题已修正：未带Runtime委托请求不能作为路由404判据；resume不得覆盖context；resume必须按实际interrupt_id映射decisions。最终按正式网关契约通过，不把此前fixture失败记为产品成功。
