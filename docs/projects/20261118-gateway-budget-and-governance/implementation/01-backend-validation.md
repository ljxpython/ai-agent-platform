# 预算后端实现与本地验证证据

> 日期：2026-11-18。本文保存实现细节与阶段证据，任务状态以 [tasks.md](../tasks.md) 为准。独立 Worktree 内的后端阶段验证不代表前端完成、生产容量或人工整体验收通过。

## 1. 实施环境与范围

Worktree 为 `/Users/<name>/PyCharmMiscProject/ai-agent-platform-gateway-budget`，分支 `feat/gateway-budget-and-governance`，基线 `84d41a46`，环境 `wt_1c4f0f7fb905`。Platform API / Runtime 使用所属独立 PostgreSQL，Web/API/Runtime 地址分别为回环端口24824/26911/24254，Redis、Workspace和依赖安装目录独立。未提交、推送、合并或部署生产。

保持 GLOBAL / PROJECT、USD、UTC 日/周日/月初、ALERT / REJECT 与首次超额通知范围。金额为 Decimal / `numeric(28,12)`，HTTP 用字符串。费用是调用开始时价格快照计算的估算，未知不补零；不做预占，已准入在途调用可造成超支。

## 2. 实现与调用路径

| 边界 | 实现位置与行为 |
|---|---|
| 控制面 | Platform API `modules/runtime_policies/` 的 budgets domain/application/infra/presentation：CRUD、当前权限、tenant revision、定义历史、软删除、同步状态和审计；迁移 `20261118_0015_gateway_budgets.py` |
| 受信通信 | 两服务独立预算签名 purpose，绑定方法、路径、请求体、时效和nonce；私有策略解析/同步/状态/事件接口不接受浏览器伪造身份 |
| 权威账本 | Runtime `db/repositories/usage.py` 保留原价格快照；`gateway_budget/ledger.py` 在同一tenant事务锁内写调用事实、contribution、所有命中窗口和outbox。初始化/回填与实时写入使用同一锁 |
| 逐调用准入 | `gateway_budget/service.py` 重新解析最新策略，先持久化开始标记再发送；同步dispatch guard负责中断，不能依赖可能吞异常的观测callback |
| 主/子图 | 正式graph通过 `with_langfuse_tracing` 进入 `with_runtime_usage`，账务不依赖Trace开启。子图/子Agent继承回调；实际工具循环与嵌套配置另有测试 |
| 模型封装 | `runtime/modeling.py::build_model` 注入模型/价格元数据，预算启用时关闭SDK隐式重试；显式模型尝试分别准入/记账 |
| 辅助调用 | `usage_only_config` 保留同步guard，供记忆抽取、视觉分析等使用。`tools/images.py::analyze_image` 的隐式重试为0；无catalog价格时REJECT拒绝，ALERT按未知规则处理 |
| 排除范围 | schema-only模型不实际推理。图片生成/编辑直接Images SDK仍属于既有 `non_llm_provider_fees` 排除范围，不声称覆盖供应商全部账单 |
| 网关与历史 | Platform API新增Run时preflight；已受理Idempotency-Key优先恢复。429/503使用现有Envelope；流内安全错误和 `gateway_budget_stop_code` 持久回读，不自造Run终态 |
| 通知 | Runtime持久outbox；Platform API事务内写receipt、站内信、外部任务后ACK。外部至少一次，成功但未记录ACK可能重复 |
| Worker保护 | `gateway_budget/worker_guard.py`、迁移 `0013_gateway_budget_worker_fence.py`：SQLAlchemy连接capability配合数据库pending→running栅栏，旧Worker/关闭开关不能领取 |

Worker栅栏是整个Runtime执行域级的粘性保护，空策略同步/能力检查也可激活。首次激活要求排空running Runs；激活后关开关不会撤销。回退要保留保护，或暂停整个执行域。不能承诺任意新旧Worker透明混跑，详见[运维手册](../backend-runbook.md)。

## 3. 专项测试与扩大回归

以下命令在对应服务目录执行。不要整体source私有env，不输出数据库连接信息。

### Runtime真实PostgreSQL专项

```bash
cd "apps/runtime-service"
uv run --no-sync --frozen python - <<'PY'
import os
import pytest
from dotenv import dotenv_values

dsn = dotenv_values("../../.local-stack/runtime.env")["DATABASE_URI"]
assert "wt_1c4f0f7fb905_runtime" in dsn
os.environ["GATEWAY_BUDGET_TEST_DSN"] = dsn
raise SystemExit(pytest.main([
    "tests/durable/test_gateway_budget.py", "-q", "-x", "--tb=short"
]))
PY
```

最终复测 **34 passed / 6 warnings，11.09s**。测试自身解析数据库名，只允许`wt_*_runtime`；随机批次隔离tenant和Run清理，避免另一个测试进程被误清理。真实四连接并发证明精确金额与两个作用域一致；不是用Python内存锁证明数据库一致性。

覆盖：UTC边界、两项目/两tenant、等于阈值、重复结算和可信补记、原价格快照、晚提交回填、跨周期/定义历史、采集缺口持久化、窗口不一致修复、正常在途/失联、签名重放/时效、旧Worker领取拒绝、同步/异步模型、真实LangChain工具循环、辅助/嵌套guard和控制面故障。事务故障分别注入usage、contribution、window、event、second_scope，验证全提交或全回滚。

### Platform API专项

```bash
cd "apps/platform-api"
uv run --no-sync --frozen pytest "tests/test_gateway_budgets.py" -q --tb=short
```

**30 passed，8.66s**。覆盖CRUD/版本、金额字符串/精度、布尔或浮点周期拒绝、当前权限/跨tenant、PROJECT不泄漏GLOBAL、严格Runtime响应、兼容检查/同步恢复、preflight与Envelope、最早相关reset、签名/请求绑定/nonce、事件幂等及外部投递重试。capabilities必须真实布尔，version必须真实整数，不能靠类型强制转换通过。

### 扩大回归与基线差异

Runtime扩大集合：新预算专项及 `durable/test_usage_ledger.py`、`durable/test_token_budget_ledger.py`、`observability/test_usage.py`、`observability/test_usage_lifecycle.py`、`middlewares/test_token_budget.py`、`middlewares/test_model_resilience.py`、`runtime/test_modeling.py`、`runtime/test_run_completion.py`、`http/test_usage.py`。

当时新专项为30项，扩大结果 **176 passed / 1 failed / 2 skipped，51.07s**。之后新增4个事务故障参数，专项成为34项并单独通过；不把两次结果相加。失败为 `test_real_budget_dedup_late_usage_recovery_and_database_fault`：空模型配置 `on_chat_model_start({}, [])` 触发既有 `TokenBudgetUnverifiableError`。用 `git show HEAD` 原版 `observability/usage.py` 动态加载baseline callback，替换该测试中的callback后，**同一测试仍1 failed，2.99s**，确认基线可复现，未顺手改旧Token规则。

Platform API扩大命令：

```bash
cd "apps/platform-api"
uv run --no-sync --frozen pytest \
  "tests/test_gateway_budgets.py" "tests/test_execution_budget_projection.py" \
  "tests/test_run_completion.py" "tests/test_run_usage.py" \
  "tests/test_runtime_upstream_errors.py" "tests/test_notifications_and_alerts.py" \
  "tests/test_iam_policy_engine.py" -q --tb=short
```

结果 **119 passed / 1 failed / 1 skipped / 417 subtests passed，26.52s**。失败为 `ExecutionBudgetProjectionTest.test_private_counters_and_clocks_not_public_and_defaults_have_custom`：`evaluation_target` 未被剥离。加载HEAD原函数同样得到 `baseline_retains_private_evaluation_target=True`。不是新预算字段造成的差异，仍属应单独处理的既有私有字段投影风险。

另有既有组合风险：`ModelResilienceMiddleware + create_agent` 的多轮工具循环第二轮 `KeyError: 'model'`，去掉预算callback仍可复现，普通create_agent无该middleware可通过。当前分开验证长工具循环预算与“预算错误不retry/fallback”，不能据此宣称完整主备/恢复组合已通过。

## 4. 真实认证、HTTP模型与Worker

可复用脚本为 `apps/platform-api/tests/acceptance/gateway_budget.py`；在Platform API目录执行：

```bash
uv run --no-sync --frozen python "tests/acceptance/gateway_budget.py"
```

脚本要求linked Worktree及本环境双库，启动OS分配端口的临时OpenAI-compatible HTTP服务；真实登录平台、经过Runtime API与Worker。公共模型管理仍拒绝私网/回环，只有隔离夹具直接登记回环模型；finally停临时服务并禁用模型。输出摘要保存在私有 `.local-stack/gateway-budget-controlled-result.json`，不包含凭据。

最新成功运行：project `946bf35e-6753-4efa-aaea-4a81fb12d76f`，policy `4a6212e0-fdc2-4c9c-8864-fde601dadddf`，thread `ec76dfd3-d327-4e5d-abe0-33090214a1ee`。五次HTTP模型请求费用依次`0.6/0.5/0.2/0.6/0.6`，窗口为`2.500000000000`。

实际观察：0.6+0.5后新请求握手前429且有request_id/Retry-After；原Idempotency-Key仍能恢复；改ALERT继续；已建立SSE后停止下一模型请求并回读安全原因；调高额度后恢复；删除Thread后2.5不减。事件 `6b84815b-c1e1-5d07-9eea-3511bd279567` 使用新签名重投两次，receipt仍1份。Thread已由验收删除，调用事实与预算保留。

这是实际HTTP/Worker链路，**模型回答、Token及费用为受控合成数据，不是供应商实际扣费成功证据**。Run ID保留在私有结果文件供现场核对。

## 5. 进程恢复、未知与通知

本地私有 `.local-stack/gateway-budget-recovery.py` 已执行prepare，依次通过local-stack重启Runtime API、Platform API和Runtime Worker，再执行check。该次恢复使用前一批project `d5bf6692-b262-4033-a41e-61ee1842cc70`、事件 `0e867ac0-a2a9-5545-ad41-0590ce53ee3d`，不能和最新HTTP脚本批次混用。

`.local-stack/gateway-budget-recovery-result.json` 观察结果：重启前后`2.500000000000`不变；模拟失联未结调用阻止REJECT；仅对已确认没发模型的夹具作可信零费用取消补记后恢复；从事实重建仍为2.5；outbox恢复投递并ACK，attempts=2，站内信前后均1份。真实供应商未知记录没有参与这次清理。

API测试 `test_external_success_before_ack_commit_can_replay` 在模拟外部发送成功、数据库记录ACK前退出后重试，站内仍1份、外部发送2次，符合至少一次边界。本环境外部notification_channels数量为0，未向真实外部接收人发送。

回填扫描已结束且无Usage的受信原生Run，把可证明的采集缺口保存为独立 `runtime_usage_runs`、`graph_id=budget_coverage_gap`、`degraded=true`；之后删除Thread不抹去缺口。无法据此证明采集启用前所有供应商历史均已覆盖。Trace不是事实来源，已核对清理无账本级联依赖，未实际清理外部Trace服务。

## 6. 性能样本与修复

私有 `.local-stack/gateway-budget-benchmark.py` 和 `gateway-budget-hotspot.py` 已执行，结果为 `gateway-budget-benchmark-result.json`。样本包含真实签名策略解析与PG准入/结算，不包含模型网络或原生Run排队；另测真实登录后的GET预算。P99采用小样本经验分位，不能作生产尾延迟保证。

| 场景 | 样本/并发 | P50 ms | P95 ms | P99 ms | 次/秒 |
|---|---:|---:|---:|---:|---:|
| 无匹配 | 16/1 | 120.78 | 129.29 | 129.29 | 8.28 |
| 无匹配 | 32/8 | 401.86 | 553.72 | 605.76 | 17.26 |
| ALERT | 16/1 | 129.65 | 134.24 | 134.24 | 7.70 |
| ALERT | 32/8 | 583.95 | 701.97 | 707.53 | 13.01 |
| REJECT | 16/1 | 174.83 | 182.03 | 182.03 | 5.76 |
| REJECT | 32/8 | 734.88 | 952.32 | 1000.11 | 10.04 |
| GLOBAL ALERT热点 | 32/8 | 515.86 | 589.56 | 618.76 | 14.89 |
| 认证列表查询 | 16/1 | 147.39 | 162.82 | 162.82 | 6.53 |

GLOBAL首次回填118.07ms，数据仅本地几百条量级。8并发锁往返P99为212–355ms，GLOBAL热点211.52ms；往返包含调度/SQL开销，不等同纯锁等待。热点数据库增量包含维护：commit277、insert194、update129，不能当作每调用固定写放大。

最初8并发在250ms锁超时下失败；先缩小每调用窗口处理到当前项目/GLOBAL，保留tenant revision一致性，仍再次超时。随后将预算准入/记账限定为statement2s/lock1s、同步回填4s/1s，普通Usage只读保留750ms/250ms，以上样本才通过。先优化处理范围再调整有界写超时，不掩盖两次失败，也不声称零开销。

尚无人工确认的SLO/增量阈值，未测完整Run吞吐、大窗口容量及长稳压力，**F9仍未通过**。

## 7. 迁移、外部失败与交付边界

通过本环境 `bash "scripts/local-stack.sh" migrate` 执行前向及重复升级成功：API `20261118_0015`，Runtime应用0013，引擎014。真实PG测试验证旧session、新session、关开关后的领取保护。账务迁移拒绝破坏性downgrade；未执行生产旧版本包全栈回退/再升级演练，不把session测试当作F10通过。

首选catalog provider实际拼写为 `maomaoai`，模型 `deepseek-v4.1-flash`。真实请求返回403 `insufficient_user_quota`；project `a1d4175c-86fd-43b2-88f7-757ce9677164`，Run `06764964-5c6e-49c5-bab8-d3bda1084c89`，model_call `01a1ee36-c241-7080-8097-ea65f1fd63d7`。费用继续未知，未当零清账，未换其他付费供应商或盲重试。更早recursion_limit=6未到模型的失败保留，后续以32执行新可控链路成功，不覆盖旧失败。

前端交接已交付 [frontend-handoff.md](../frontend-handoff.md)，本轮未改前端产品代码。仍待同事页面/组件和浏览器验收、供应商账户维护者补额度、真实主备/异步恢复组合、性能阈值、完整兼容回退及人工整体验收。标准中的draft不因本地阶段验证而毕业。

## 8. 收尾检查

42个变更/新增Python文件执行Ruff检查及内存compile，通过；两服务预算contracts AST相同。20个新增Python文件格式检查曾发现新增事务故障参数装饰器需要换行，已仅格式化该测试文件并复查。未全仓格式化或安装产品依赖。

7份项目Markdown的35处本地链接/锚点、行尾空白、Task1–5与六个2/3子项、P1–P6、F1–F10及2done/3partial状态核对通过；`git diff --check`通过。前端产品改动计数为0；README、CONTEXT、FEATURES与任务状态一致，CHANGELOG仅记Unreleased后端能力。

通过本环境 `bash "scripts/local-stack.sh" status` 回读：runtime-api、runtime-worker、platform-api、platform-web、Redis均running，runtime-ready与platform-api检查均yes。服务保留供同事联调；临时合成模型服务已结束，不能用它作为持久可用模型。未执行Git提交、推送、合并或部署。
