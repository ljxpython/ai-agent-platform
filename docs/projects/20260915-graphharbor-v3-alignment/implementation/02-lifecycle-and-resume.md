# 生命周期字段与恢复链路修复

日期：2026-09-15。B1/B2 done；B3—B5与平台链路验证进行中，未发布、未切默认、未写前端代码。

## GraphHarbor修改文件

| 文件／函数 | 修复与原因 |
|---|---|
| `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/protocol.py:protocol_event` | 根running原来变成started，与官方真实线程样本不符；改为running。子生命周期data.namespace比外层更深时提升作用域，使官方SDK的子订阅能匹配；根error转换为官方字符串形状，保留可选graph_name/cause |
| 同文件`project_v3_event` | 内部pending等状态映射为running，不泄漏为额外lifecycle枚举；与RunStatus保留的状态字段分工 |
| `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/run_store.py:RunRepository.record_event` | 根生命周期从已有AssistantRow获得graph_id，覆盖常规终态与其他收尾路径；写入固定timestamp，回放不再重新生成时间。不改序列分配算法、不加表 |
| `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/graph_executor.py:invoke_graph` | 单次执行内记录已出现的scope名称，补到同scope后续生命周期；不从名字推任务ID，不增加执行状态机。真正根lifecycle仍被过滤，由事务提交后Worker事件替代，与官方一致 |
| `libs/langhost/src/langhost/protocol_api.py:protocol_commands` | 真实JS SDK拒绝缺少type的成功响应；官方响应为`type: success`，已补run.start及两种resume返回分支 |
| `libs/langgraph-runtime-pg/tests/test_vue_protocol_events.py` | 五种event、嵌套scope订阅过滤、字段和回放timestamp；根running及error字符串回归 |
| `tests/javascript/v3-lifecycle.mjs` | 真实官方SDK启动、发现两个子图、cause关联、output消费、根失败与interrupt/resume；官方Server和GraphHarbor均通过 |

GraphHarbor现有实现类名实际是`RunRepository`，规划里部分写成`RunStore`属于描述误差；代码路径正确，本记录修正函数定位。

## 平台恢复的最小修复

实际查询证实官方和GraphHarbor的Run公开详情都包含kwargs，因此无需新增RunRequest字段或数据库迁移。

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:send_thread_command`：resume从原checkpoint关联的已授权Run读取kwargs.version；首次用parent.run_id，重试用previous.parent_run_id，缺省v2。保留模型／权限快照与原有校验，不接受浏览器覆盖业务配置。
- `apps/platform-api/tests/test_run_requests.py`：原恢复用例增加v3断言；新用例模拟首次响应丢失、重新创建服务实例后重试，仍查询来源Run并发送v3。
- 测试结果：22项unittest通过，2.796秒。仅恢复组合完成，真实重启链路未因此勾选done。

## 已完成验证

- GraphHarbor public runtime／production contract／Vue事件回归：75 passed、4 skipped，24.06s；跳过既有迁出的业务层测试，未计通过。
- `tests/acceptance_app/test_v3_graphs.py`：3 passed，1.08s。覆盖真实同名分派cause、Send结果、异常与interrupt/resume、比较器差异保留。
- 官方0.13.0线程样本：根running，命名子started，成功completed／失败failed／根interrupted；toolCall的两个真实ID分别为dispatch-alpha/beta，Send和edge未输出cause时不造字段。
- 严格对照保留26项差异，主要是GraphHarbor既有status/reason/output扩展、子终态目标namespace与多一条原生子interrupted。未通过删除字段或事件假装对照全绿。新包发布／默认切换仍受验证门禁约束。

## 后续补验（2026-09-15）

- GraphHarbor独立库`graphharbor_v3_contract_20260915`迁移到006后全量`pytest -q --tb=short`：**157 passed、18 skipped，61.17s**。首次空库未迁移导致schema contract失败，迁移后重跑通过；不是业务功能错误。18项skip未作为通过。
- 修改的四个Server源文件mypy通过，修改Python文件ruff通过。
- 平台`apps/platform-api`执行`.venv/bin/python -m unittest discover -s tests -p 'test_runtime_gateway*py'`：**41项通过，2.465s**。
- 外仓`tests/javascript`执行`node v3-lifecycle.mjs`（31397）及`GRAPHHARBOR_URL=http://127.0.0.1:31398 node v3-lifecycle.mjs`：两端均报告children=2、cause verified、failed verified、interrupted verified。
- `tests/acceptance_app/run_v3_probe.py:capture`：补齐真实HTTP input.respond恢复，新Run轮询到success，源Run最终状态保持；官方响应仅确认受理、不提供run_id，探针通过独立线程的公开Run列表定位唯一新Run。此方式仅用于本探针独占线程，不能移植成平台多用户来源Run选择逻辑。
- 同文件`verify_replay`：GraphHarbor Send线程完整6条生命周期回放、游标后4条、单子scope 2条，event_id、seq、timestamp和data原样相等。新增`--verify-replay`参数，HTTP超时及场景总超时限制测试时长。

复跑（GraphHarbor仓库；官方对照服务31398与GraphHarbor API31397/Worker均使用`tests/acceptance_app/v3.langgraph.json`）：

```bash
.venv/bin/python tests/acceptance_app/run_v3_probe.py --url http://127.0.0.1:31398 --output artifacts/v3-official-baseline.json
.venv/bin/python tests/acceptance_app/run_v3_probe.py --url http://127.0.0.1:31397 --verify-replay --output artifacts/v3-graphharbor-after.json
```

报告为本地原始证据，可能被gitignore；本记录保留结果摘要，不依赖临时文件才能理解结论。第一次成功恢复样本：官方新Run `01a0a33b-0174-7f73-b48b-db02a2d8b888`；GraphHarbor新Run `fb675cce-6b58-4134-80cf-f8faa2fcea47`。之后复跑会创建新ID。

### 官方与GraphHarbor必须区分的事实

1. 官方0.13.0的HITL发出interrupted lifecycle后，源Run的最终持久状态是success；事件到达时还可能是running。GraphHarbor源Run最终状态是interrupted。采集器先等源Run持久状态稳定再发resume，记录这一差异。**不修改GraphHarbor既有持久终态、不把success解释为无需人工输入。** 此状态差异在26项生命周期字段差异之外。
2. SDK1.9.28的`await thread.output`在失败场景也会resolve；以根lifecycle.failed及error判失败。不能给前端交接“output resolve即成功”。
3. SDK投影是`interrupts[].interruptId`和`namespace`；恢复命令字段是`interrupt_id`。测试曾误用`.id`，两端均拒绝，已按SDK类型修正。
4. SDK普通失败测试曾错误预期output reject，两端均不符合该预期，已修正为检查实际根failed事件。保留这些调试结论，避免后续重走同样的误判。

剩余门禁：完整B3/B4故障／重启／游标矩阵、B5候选包构建和安装发布、C真实平台链路、E性能及回退尚未完成；D前端代码继续deferred。当前不能宣布后端迁移整体完成。

### 成功提交失败的专项回归

- 新增外仓`libs/langgraph-runtime-pg/tests/test_production_contract.py:test_success_commit_failure_never_publishes_completed`。使用真实PostgreSQL事务，在成功状态与终态事件写入后、commit前注入一次ConnectionError；断言事务回滚、Run重新pending、数据库无终态事件、fanout无completed/failed、重试生命周期仍为running。复用现有Worker和Repository，没有新建执行机制。
- 独立用例：1 passed，1.77s；整个`test_production_contract.py`：**51 passed、4 skipped，15.69s**。ruff通过。该结果晚于157项全量回归，不能把两轮数字相加成新全量结果。
- 已有测试覆盖超时唯一终态、取消与完成竞态、数据库取消、lease回收和重试耗尽；本次运行确认通过。真实进程kill／重连全矩阵仍未以这些模拟执行器测试替代。

### 真实重启与平台恢复（本轮最后一组验证）

- 独立GraphHarbor API31397执行TERM并用相同数据库／Redis前缀重新启动。对重启前Send线程执行`verify_replay`：完整6条、cursor后4条、子scope 2条仍逐字段一致；报告`artifacts/v3-restart-replay.json`。这覆盖API进程真实重启，不代表Worker进程故障矩阵全通过。
- 平台2142通过`bash scripts/local-stack.sh restart-one platform-api`加载本轮恢复修复。
- 修改`apps/runtime-service/tests/services/dearflow_agent/test_platform.py:test_platform_creates_and_completes_dear_run`：显式v3文件模式下，每次暂停和最终resume都校验持久回放有typed lifecycle；输出每个恢复Run ID，便于定位丢失版本的位置。SSE解析允许`data:`后的标准空格。
- 实际命令（runtime-service目录）：

```bash
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_FILES_TEST=1 DEAR_PLATFORM_RESTART_TEST=1 DEAR_PLATFORM_STREAM_VERSION=v3 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
```

- 项目`10c4b349-87b0-464a-a9c7-2de00361eb42`，线程`7302344b-4269-471c-b638-192158793343`。源Run `d4bfdbcd-2c0d-4eed-8407-6a9994198965`完成澄清暂停，真实重启Runtime Worker后checkpoint保持；后续恢复Run `f726e795-32fd-4e89-9432-aeea6c13408a`、`14247f91-3ee5-462c-b8b0-e0176fa0f25d`、`fceb75fb-5210-462d-b1ba-99941eeec946`、`1cf31329-286c-433f-a93d-f8519c2bf2ac`及最终`e5d062fb-460a-44b0-a038-64c66e57af5e`均保留v3回放。恢复请求不传version，来自平台继承。
- **整条文件用例失败（40.08s），不可勾为通过**：execute四次返回Docker daemon不可连接、exit125，模型没有发布产物，`present_artifacts`断言失败。版本恢复断言通过，不等于文件交付通过。首次4.67s失败是新增测试的SSE空格解析错误，已修正。
- 已启动Docker Desktop，但它停在macOS管理员授权（端口映射／socket配置）；已通知用户在本机完成授权。不得由Agent代输管理员凭据。文件交付子项暂标blocked，Docker可用后原命令重跑；Server确定性验证不依赖Docker，保持已通过结果。
- 这次真实平台使用现有安装的GraphHarbor post28；它证明平台resume修复有效，**不作为尚未发布新候选包的安装／平台集成证据**。

### 本地候选与双子任务

- GraphHarbor两包`pyproject.toml`、`uv.lock`及`scripts/check_versions.py`锁步升到**0.13.0.post29本地候选**；`uv lock`仅改变两包版本，`uv lock --check`与版本检查通过。未上传PyPI、未改平台lock到候选、未提交git。
- `uv build --package graphharbor-runtime --out-dir artifacts/v3-dist`及graphharbor构建通过（两个wheel＋两个sdist）。干净Python3.11环境安装、CLI版本、模块导入、根running投影与`create_app({"graphs":{}})`构造通过。不是完整服务启动E2E。产物hash、兼容范围与复跑说明见外仓`docs/v3-post29-candidate.md`。
- 新环境允许范围解析langchain-core1.6.3，对照环境是1.6.0；记录差异，不把导入成功当这个组合全套验证。
- 平台现有post28双子任务显式v3链路：`DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 DEAR_PLATFORM_STREAM_VERSION=v3 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s`，**1 passed，14.25s**。线程`cc1b195c-5b05-4f97-9217-fb75b1152e70`、Run `6c688c2f-24f8-4f7c-a440-186b56ee4404`，两个task结果、cause对应、根子终态隔离与回放通过。
- 平台Run请求再次回归：22项通过，2.844s；文档检查与两仓库diff检查通过。

### Docker授权后的文件交付复验：C4-b已完成

用户完成本机管理员授权后，`docker info --format '{{.ServerVersion}}'`返回28.0.4，原Docker阻塞解除。保留上面的失败记录作为排查历史，本节为文件链路最新结论。

- 本轮没有新增业务代码；复用`apps/runtime-service/tests/services/dearflow_agent/test_platform.py:test_platform_creates_and_completes_dear_run`以及上节文件模式复跑命令。
- **结果：1 passed、1 deselected，38.08秒，退出码0**；输出`file-chain verified; worker_restarted=True`。
- 校验范围：真实模型澄清中断、真实Runtime Worker重启、checkpoint不变、execute审批及执行、present_artifacts审批及发布、下载内容等于输入大写、SHA256匹配；每次暂停及最终恢复Run的持久回放均包含v3 lifecycle。
- 项目：`6c91898e-18a9-4667-ae28-7415d89acf11`；线程：`ad4ea66c-5b60-4ee7-9c0b-504453ecbe80`。
- 源Run：`9d8ff17c-edd3-46d6-9292-2a3ed99973c0`；依次恢复Run：`1eae8e44-6407-4630-b368-29f6567711ec`、`ef2a6077-848f-4ee2-a0ee-cacef656a3b4`、`d76dc67b-77d2-4021-858a-f6d560ec28a1`、`24b25501-fef4-446d-8183-add816c7ae30`。
- 平台仍使用post28与本轮平台恢复修复；post29候选发布／安装接入、完整故障矩阵、性能与回退仍未完成。前端代码未修改，默认版本未切换。
