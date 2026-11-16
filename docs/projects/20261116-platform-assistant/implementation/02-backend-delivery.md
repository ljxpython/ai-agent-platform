# 后端交付技术证据

日期：2026-11-16。当前Worktree：f119，分支feat/platform-assistant，基线d8ebfaa。所有数据源和变更均在wt_3565491667ce本地环境；未访问或变更生产业务数据，未合并main。

## 环境与实现版本

API28581、Runtime25418、Web28074、Redis29859。Platform数据库wt_3565491667ce_platform、Runtime数据库wt_3565491667ce_runtime，各服务独立.venv。API迁移到20261116_0012。Python3.13.9，langchain1.3.17、langchain-community0.4.2，新增sqlglot28.10.1。受管模型ID070cced3-350b-42ec-b678-994dd07b7078，实际deepseek-v4.1-flash。

本地专用只读角色wt_3565491667ce_assistant_ro只读assistant_data视图，底表在assistant_fixture；视图隔离另一项目的secret行。可见Demo运行两条，cost1.25/2.75。正式配置不含这些硬编码测试资源。真实工具响应、state与私有联调令牌仅保存在.local-stack，不提交原始模型推理或凭据。

## 确定性与数据库验证

在各服务目录使用其.venv运行：

```bash
# apps/platform-api
ASSISTANT_LOCAL_POSTGRES_TEST=1 .venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_platform_assistant_postgres.py tests/test_observability_api.py tests/test_thread_fork.py tests/test_run_requests.py tests/test_thread_acl.py tests/test_audit_http_resolution.py -q

.venv/bin/python -m pytest tests/test_security_boundaries.py tests/test_run_control.py tests/test_run_diagnostics.py tests/test_run_completion.py tests/test_audit_correlation.py tests/test_runtime_gateway_http_matrix.py -q

# apps/runtime-service
.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_r0_baseline.py tests/services/dearflow_agent/test_research.py tests/runtime/test_run_budget.py -q
ASSISTANT_LOCAL_POSTGRES_TEST=1 .venv/bin/python -m pytest tests/test_platform_assistant_persistence.py -q
```

- API主要回归：120 passed、3 skipped、11 subtests passed。之后批量表权限查询的小改动另复验助手+真实PG专项，46 passed；最后日志逐条Thread授权、目标Run匹配及64KB边界收尾复验助手/PG/旧日志/fork共54 passed（9.17秒）。没有把重叠测试累加为新样本数。
- API安全/运行/诊断/完成回调/审计/HTTP矩阵：84 passed、2 skipped、22 subtests passed，另1项基线测试失败，见下节。
- Runtime助手/图注册/共享检索/Run预算：65 passed、1 skipped；后续增加edit决策拒绝和approve参数不可变测试，助手专项6 passed。
- PostgreSQL持久审批：3 passed，40.58秒。每个场景使用独立子进程start、inspect、resume、再次resume。批准前及重启后无选择为0次；approve写1次，reject和恢复时撤权写0次；实际重放旧interrupt仍不增加写。测试计数表不使用去重INSERT掩盖重复执行，测试工具未发布到正式图。
- SQL覆盖单SELECT/CTE/关联聚合/集合、CASE/EXISTS/DECIMAL；拒绝写CTE、多语句、DDL、锁、系统/跨schema、角色切换、外部/副作用函数及伪装CTE作用域。实际专用角色即便关闭default_transaction_read_only也无INSERT/底表读取权。
- 权限覆盖当前项目/身份、资料/工具撤权、来源版本变化、非本人历史、禁fork、历史列表过滤、审计fail-soft、授权回执fail-closed；API已有Run幂等、伪造/过期interrupt、配置注入和取消行为继续回归。
- 对全部40个新增/修改Python文件执行Ruff，检查通过。最终差异空白、文档链接/JSON与前端零改动核对见verification收尾记录。

跳过项目沿已有测试自身条件，不作为通过；未声称运行全仓所有测试。Runtime存在既有Swig/Pydantic警告及langchain-community上游弃用提示，未隐藏警告或升级核心依赖。

## 基线测试问题与修复过程

1. 早期PostgreSQL夹具缺CONNECT，首次连接失败；只给本隔离库专用角色授CONNECT后复验成功。
2. 内置导航文档新增时漏逗号导致测试收集SyntaxError，修复后重跑。真实模型使用CASE/EXISTS暴露AST误拒，补支持并加入回归；CAST遇到自定义regclass时AttributeError也已改为明确拒绝。
3. 审查发现全局收集CTE名字可误认不同词法作用域，改用sqlglot Scope区分真实CTE引用，增加pg_settings嵌套伪装负例。助手历史fork与列表路径补当前授权校验，避免只保护state而遗漏其他读取入口。最终审查另补普通日志逐条Thread ACL及目标Thread/Run匹配，防客户端传播Trace碰撞成为授权；同项目同Trace不同私有Thread/缺Thread记录均被过滤。
4. 部分探索性测试命令因工作目录或文件名不正确而未收集测试；改为所属服务目录与实际路径执行，未把这些失败计作测试通过。
5. **未修复的既有测试缺口：** test_runtime_gateway_http_matrix.py::GatewayHttpMatrixTest::test_public_route_inventory_and_boundaries 漏列 GET /threads/{thread_id}/runs/{run_id}/execution-evidence。用git show HEAD分别核对，基线http.py已存在该路由，基线测试清单也确实没有；本次未改该路由或扩展到评测项目测试维护。此项不能标全仓回归通过。
6. 长时间联调后本地访问令牌到期，读取返回401；重新走正常登录后复核，没有放宽认证或把401当空历史。

## 真实API→Runtime→模型→工具

下列为真实API客户端链路，不是浏览器验收。数据为合成或公开资料；每次都核对Run终态及工具消息，而不是只看HTTP200。

| 场景 | Thread / Run | 观察结果 |
|---|---|---|
| 文档指导 | ed1926f7-da4b-443e-99a1-f852f31aa1ec / 900e7642-8763-4277-8740-b3394f2abc14 | success；search_documents给出历史和审批说明，引用f5c1e8d2-46d2-4f9e-ae15-6acf627c901e |
| 自生成SQL | 同Thread / 4bedb8f7-8ddd-431a-a7ff-e0d592aa0445 | success；模型自主列数据源、读结构、生成LEFT JOIN+COUNT+SUM，Demo/2/4.00；审计引用5项核实，unverified_count=0 |
| 重启续聊及创意 | 同Thread / 33fe418d-5781-487f-b51c-63f724ae899e | Runtime API/Worker实际重启，原20条消息仍可读；续聊后22条，正确复述2次/4.00并明确三个名字为假想 |
| 新会话隔离 | 716fa44d-cfeb-4da2-9dc5-0cf0933ed0f5 / 76296649-42ac-41fc-83ca-14e1a01257f7 | success；明确不知道别的会话查了什么，不编造旧项目数据 |
| 429日志与源码 | 92f63406-fcf1-49d3-a049-02d6822832f8 / 5b5bf33e-18ba-4752-941b-3b3d14fd134b | success；search_project_logs/search_source实际调用；只命中本项目安全结构化日志，说明429不足以认定欠费，源码只判断状态码；分别引用日志和源码回执 |
| 超时/语法及资料注入 | aaef9c94-0a4f-4e88-8934-cf5d1657d2fa / ac41dc83-e92f-4941-8424-2d9379f9b1d6 | success；两次日志和三次源码读取，区分两类合成错误并说明缺失细节；识别源码注释里的UPDATE/外发诱导，未调用SQL写或公网搜索，数据成本仍4.00 |
| 公开资料 | 1fd87d6e-6509-492a-b824-c416f0378d72 / ffb6fca6-ce1d-45b1-af97-97d707e84a91 | success；真实search_public_web/Tavily返回Python官方文档摘要；说明摘要时间/版本不能确认，没有把工具来源当网页全文已核实 |
| 流式 | 9033002e-c17f-4576-bf65-62d0517fc9ac | 实际metadata/lifecycle/checkpoints/debug/values/updates/messages事件；首SSE事件0.877秒，完整简单回复8.233秒 |
| 取消 | Run93ab224d-4967-4591-9a8b-cf4ff2f1db0a | cancel回执200后真实Run状态interrupted，不把200当成功完成或自动审批 |

公开搜索曾返回一个不能由本次摘要确认的Python版本号；答复标明了不确定性。该样例证明检索与说明边界工作，不是“外部搜索事实永远正确”的质量结论。

真实运行诊断接口200但availability=disabled、unavailable_reason=not_configured；关联日志入口因此返回assistant_trace_missing。随后通过获准无Run日志调查验证真实文件路径和模型分析。没有把未配置的观测后端说成已取得完整运行追踪。

## 容量、关闭与恢复

实现前固定2秒SQL、500ms锁、3秒连接、4个每进程并发、100行/64KB返回；超限拒绝/截断均有标志。真实4并发简单聚合每个50.3–55.5ms，总58.6ms；指数交叉查询实际被超时终止，101行场景截断100行。首SSE事件是协议metadata，不等于首模型Token；小合成数据和一次模型时延不能当生产SLA。

只在当前Worktree配置关闭助手并撤源码权限、重启API，实测：bootstrap503，read503，引用源码的旧会话state403且列表隐藏，无相关资料的其他历史200；旧日志授权请求200，匿名请求401。之后恢复flag和源码权限并重启；另将源码发布revision从v1改为v2，旧v1历史再次403，证实版本绑定。新会话可使用v2。

## 本次证明的边界

后端代码与前端交接具备本地技术证据，人工交付验收尚待用户确认。前端页面/移动端/键盘/刷新交互和全栈浏览器链未执行；生产连接、真实Loki、生产追踪配置和生产容量未验。正式业务写工具为空，本期证明审批机制与隔离副作用，不能外推任意未来业务操作都具备业务幂等。
