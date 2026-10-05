# 定时 Agent 任务 - 验证记录

## 验证计划与范围

后端验收覆盖 schema/签名、原生时间规则、受管 Run、once/manual、SQL 分页、当前权限拒绝、服务账号生命周期、审批、并发与提交结果未知。GraphHarbor scheduler 的 DST/end_time/多实例/重启/故障按独立专项验证，平台复用相同 parser。

平台测试使用临时 SQLite 控制面；GraphHarbor 使用独立 PostgreSQL graphharbor_cron_probe_20261005 和 Redis 前缀 graphharbor:cron-probe-20261005。清库测试禁止改指现役数据库；未新增平台迁移。真实链路采用确定性图，不调用生产 LLM。

前端、生产部署、生产回退与批量负载/SLO验收不属于本次后端隔离交付；回退门禁验证 pause 阻止未来派发、delete 保留已接受 Run/历史。没有虚构 UI、生产或性能通过结果。

## Phase 验证记录

### T0.1 原生 cron 事实核查（2026-10-05）

- 结果：隔离库 SDK/恢复/双实例契约通过；见 GraphHarbor cron-parity。

### T0.1a 隔离库基线探针（2026-10-05）

- 结果：独立 graphharbor_cron_probe_20261005 基线及原生回归通过。

### T0.1b GraphHarbor post40 首次发布（2026-10-05）

- 结果：post40 PyPI JSON 200、独立 CLI 同版本；现行已升级 post41。

### T0.2 人工批准执行语义（2026-10-05）

- 结果：本会话用户明确同意方案并授权继续实施；非 AI 自行批准。

### T1.1 定义与运行事实复用（2026-10-05）

- 结果：发布包探针 CRUD、Run 关联、定义删除后历史读取通过。

### T1.2 产品接口、时间与历史分页（2026-10-05）

- 结果：schema/signature 2 tests；隔离 HTTP CRUD、preview、once、分页通过；DST/end_time 原生契约通过。

### T1.3 调度故障与重启恢复复用（2026-10-05）

- 结果：cron-parity 双实例/注入失败/重启与 post41 CI 126 passed/4 skipped。

### T2.1 受管执行与手动幂等（2026-10-05）

- 结果：发布包探针用户/服务账号/凭据/项目/Agent/模型/Thread 失效、同 key 并发与响应丢失对账通过。

### T2.2 Runtime 执行前 guard 与审批失败（2026-10-05）

- 结果：Runtime 定向 57 passed；真实 worker 审批/异常/失效 Run 均预期 error。

### T2.3 执行留痕和 Run 历史（2026-10-05）

- 结果：发布包 22 Run（8 success、14 预期 error）；错误审计断言与删除后读取通过。

### T3.0 前端正式契约交接（2026-10-05）

- 结果：与 router/schemas/service、原生历史和错误 Envelope 核对；文档链接检查。

### T4.1 后端隔离链路与发布验收（2026-10-05）

- 结果：API 320 passed/16 skipped/641 subtests，2 旧失败；Runtime 563 passed/85 skipped，1 Docker 失败；3 项在 HEAD 复现。cron 定向/发布包 E2E 全通过；Ruff/锁检查通过。

### T4.2 状态与标准同步（2026-10-05）

- 结果：双库 diff --check、专项链接与完成卡/Phase 对照检查；JWT 25 operations/10 原生/15 自定义一致。

## Final 验证记录

### 2026-10-05 后端交付核对

**结论：** 当前授权后端范围 done；前端页面/浏览器验收和现役/远端平台部署 deferred。全部 13 个后端/调研/交接任务有完成卡及独立 Phase 记录。全仓回归非全绿，下面保留 3 项已复现的外围失败。

### 自动化回归

| 范围 | 真实结果 | 证据 |
|---|---|---|
| Platform API 全量 tests | 320 passed、16 skipped、641 subtests passed、2 failed，88.96 秒 | /tmp/platform-api-cron-final-tests.log |
| Runtime 全量 tests | 563 passed、85 skipped、1 failed，123.84 秒 | /tmp/runtime-cron-final-tests.log |
| Runtime cron/auth 定向 | 57 passed | tests/runtime/test_scheduled.py 与既有授权契约 |
| GraphHarbor CI + cron live | 126 passed、4 skipped，41.85 秒 | /tmp/graphharbor-post41-tests.log；GraphHarbor cron-parity |
| 发布包隔离 E2E | passed；22 Run：8 success、14 预期 error | /tmp/scheduled-chain-published-verification.log |
| 静态门禁 | API 源码/改动测试 Ruff check/format：165 文件；Runtime 改动和探针 Ruff check 通过，最终 format 检查 11 文件通过；uv lock --check 通过 | 两服务实际执行输出 |

全量回归命令：

```bash
# apps/platform-api
PYTHONPATH="src:." uv run --with pytest python -m pytest -q tests
# apps/runtime-service
uv run python -m pytest -q tests
```

三个外围失败均在临时导出的 HEAD 源码、同一依赖/环境定向复现；未修改工作区源码或创建分支：

- API test_runtime_gateway_workspace.py 的 test_dear_artifacts_two_service_http / test_real_two_service_http：旧断言要求删除 script，与已经生效的 HTML 沙箱/CSP 允许脚本行为不一致。HEAD 2 failed，/tmp/cron-head-api-tests.log。
- Runtime test_graph_approval_runs_real_python_and_preserves_exit_code：Docker daemon 未运行，execute exit_code=125。HEAD 1 failed，/tmp/cron-head-runtime-tests.log。该用例直接使用未修改的 services.demo.showcase_demo.agent，非 cron wrapper。
- 这些失败不由本次 cron 引入，不计为通过，也未扩大范围修改 HTML 安全契约或启动 Docker。既有短测试 key/beta/deprecation warning 保留原输出。

### 发布包真实链路

```bash
# apps/runtime-service；PYTHONPATH 不含 GraphHarbor 源码
PYTHONPATH="/Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/platform-api/src" DATABASE_URI="postgresql+asyncpg://lijiaxin@127.0.0.1:5432/graphharbor_cron_probe_20261005" REDIS_URI="redis://localhost:6379/0" GRAPHHARBOR_REDIS_PREFIX="graphharbor:cron-probe-20261005" uv run --with pydantic-settings --with asgi-lifespan python "../../scripts/verify_scheduled_tasks.py"
```

GraphHarbor 原生 app/scheduler/ProductionWorker、PostgreSQL/Redis、生产签名、Runtime guard 与 Platform API/HMAC 都是真实实现；模型图为确定性替身。源码版和已发布 post41 包各完成一次同场景探针，最终按发布包结果验收。

| 场景 | 验收结果 |
|---|---|
| CRUD/preview/owner/project 隔离 | 实际 HTTP 成功；异主体不可见/拒绝 |
| 到期 → Run → cron_id → 历史分页 | 关联与终态可读，total/offset 正确，过滤先于分页 |
| pause/resume/delete | pause 阻止后续派发；delete 保留已接受 Run 与可读历史 |
| once | 最后一次 Run 保留、定义 exhausted；标题编辑不重排、过去时间恢复拒绝 |
| manual | 原 key 重试和 3 并发只建一个 Thread/Run；提交后故障注入 502，原 key 恢复原 Run |
| 用户/项目/Agent/模型/成员失效 | 执行前 error 与 audit denied；定义保留 |
| Thread 撤权与实际删除 | ACL 拒绝或原生 thread_not_found 终态，历史留存，不永久 pending |
| 服务账号 | API 建账号/凭据/grant；scheduled 成功；2 并发 manual 唯一；账号停用、凭据撤销/过期、grant 移除全部拒绝 |
| HMAC | 伪造/过期 403，正确签名但错误 shape 400；身份作用域绑定 |
| 无人值守审批与图异常 | error，approval_required/execution_failed 留痕，不自动 approve |
| 服务端时区/截止 | 复用原生 parser；GraphHarbor DST/end_time 隔离差分通过 |

### 发布、状态与回退

GraphHarbor 双包 post41 四产物发布成功，PyPI 两包 JSON HTTP 200、每包 wheel/sdist 各一；独立 PyPI 安装 CLI/runtime 均 post41。平台 pyproject/uv.lock/.venv 已同步，锁校验通过。没有从未发布源码伪装安装验收。

JWT 增至 25 operations（10 原生、15 自定义），cron 权限和实时核验补充已同步；标准仍 draft，因为消息内部 Run 回查的现役验收属其他专项。双库任务与 CONTEXT/FEATURES/CHANGELOG 一致；13 张平台完成卡对应 13 条 Phase，GraphHarbor 8 个任务对应 8 条 Phase 对照，双库 diff --check 通过。

交付文档共 22 份、199 个本地链接已检查；专项及本次新增链接无断链。扫描同时发现 4 个 HEAD 已存在的断链（平台 FEATURES 的旧前端记录、部署指南、交接指南，以及 GraphHarbor profile 的事件留存专项）；本次不改范围外历史链接。PyPI JSON 的四个 SHA256 与 dist-post41 实际产物逐一相同，平台安装模块路径与双包 post41 版本再次核实。

无新表迁移，未执行生产数据库恢复。回退顺序见 plan.md：先 pause，处理已接受 Run，再回退应用，避免旧 Runtime 错解 marker。隔离暂停/删除门禁通过，未做生产应用回退。

**四态：** 后端接口/Runtime guard/GraphHarbor 发布/隔离 E2E/交接 done；前端与生产部署 deferred；本次范围没有 partial/blocked。整个产品上线与全仓回归全绿仍不能由此推断。
