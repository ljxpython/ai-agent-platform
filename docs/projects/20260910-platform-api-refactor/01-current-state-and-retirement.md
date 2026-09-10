# 01 现状审查与退役清单

## 目标

基于当前源码与可执行证据区分：需要修复的行为、可以退役的代码、应保留的业务。代码位于 `apps/platform-api/`；模块路径省略 `app/modules/`，core/adapters/bootstrap 路径省略 `app/`，tests/migrations 路径相对应用根目录。行号为 2026-09-10 审查快照。

源码发现与测试结果保留为重构前证据；以下处置已按用户批准的“全新平台层、无旧兼容、删除知识库与测试用例业务”修订，不要求延续旧数据或旧功能。

## 方案设计：审查结论

模块化单体与控制面/执行面拆分方向正确，问题在于边界没有完整落实。当前 `app/` 有 257 个 Python 文件、25,347 行；`runtime_gateway/application/service.py` 2,261 行，Operations 模块 2,944 行。行数只用于定位职责密集处，不作为删除依据。

### 优先修复

| 编号 | 优先级 | 代码与证据 | 问题与后果 | 处置 |
| --- | --- | --- | --- | --- |
| A01 | P1 | `runtime_gateway/application/service.py:1736` 的 `create_thread_run()` | 将完整请求摘要固定为 `standard:` 幂等键；同一 Thread 两次独立提交相同内容，第二次直接复用旧 Run | 用户操作身份与请求摘要分开，标准 Runs 与 commands 统一规则；已由隔离探针复现 |
| A02 | P1 | 同文件 `_launch_runtime_run():1008`、`_reserve_durable_run():741` | 先提交本地 active 占位，再请求上游；只处理特定超时。上游 422、缺 run_id 等路径没有完整收尾 | 区分明确拒绝、未知提交结果和已创建；明确拒绝释放占位，未知结果可恢复查询，不重新执行输入 |
| A03 | P1 | 同文件 `get_thread_run():2065`、`list_thread_runs()`；`runtime_gateway/presentation/http.py:51` | State/History 会去除 runtime_model_ref，Run 返回和 SSE 通用脱敏没有同等保护；引用本身可兑换模型配置，不能当普通非敏感字段 | 所有公开读面、事件、错误统一去除内部引用；内部配置端点保留认证与 scope 校验 |
| A04 | P1 | 同文件 `_assistant_belongs_project():697`、`_assert_runtime_target_allowed():713`；Agent repository `get_by_project_and_graph_id():103` | 存在记录即允许，没有检查 Agent status；记录不存在时，匹配旧 Thread metadata 也允许；Graph policy 没有参与此处决议 | 历史可读和新执行权限分开，所有新运行/恢复必须检查当前 Agent 与策略 |
| A05 | P1 | 同文件 `send_thread_command()` 的 input.respond 分支，约 1867 行起 | 合并请求 model/options 后签发新 Context 哈希，却没有复用 run.start 的完整模型/工具授权检查 | 恢复沿用原配置摘要，重新校验当前授权；禁止审批响应顺带扩大模型/工具权限 |
| A06 | P1 | `runtime_catalog/application/service.py:566,605,636` | 目录发现读取本机 langgraph.json；GET 空列表触发刷新；刷新尝试 POST /assistants，异常直接吞掉 | 远端只读发现，明确刷新，故障和陈旧状态可见；不创建上游 Assistant |
| A07 | P2 | `adapters/langgraph/parameter_schema.py:38,99,191` | 依赖邻居服务源码和 AST 推测 schema，返回绝对文件路径；扫描到的 `.get()` 不等于公开可配置字段 | 由部署端提供真实 schema，平台只投影允许编辑的字段 |
| A08 | P2 | `core/db/uow.py:55`、`core/db/session.py`；多个 async service | async commit 内实际调用同步 Session；认证也同步读 DB；知识库 health 等 HTTP await 位于 DB 事务内 | 同步数据库工作整体在线程内完成，事务之外执行网络请求；不用 async 关键字伪装非阻塞 |
| A09 | P2 | `adapters/langgraph/runtime_client.py:115`；两处 SSE 分帧逻辑 | 上游连接/错误在生成器消费时才发生；全连接 timeout=None；HTTP 已开始后难以返回正确状态。每 chunk 替换 CRLF 也不能保证跨 chunk 分帧正确 | SSE 建连先检查上游响应；统一一处流处理，有限 connect timeout，关闭时释放资源 |
| A10 | P2 | `runtime_catalog`、`runtime_policies`、`runtime_gateway` 的 `_runtime_id` | 用 runtime_base_url 去尾斜杠作为 catalog/policy 的身份；换服务器地址可能看起来像“全新目录”，不是简单配置变更 | 新设计用稳定逻辑身份或单部署常量，URL 仅作连接地址 |

A02 不意味着所有部署都会永久卡住：db_polling Worker 可能接手 submitted Operation；但应用当前没有区分拒绝和未知结果，redis 路径也未调度该异常分支。探针证明的是“422 后仍 active，下一请求冲突”，不是完整 Worker 故障恢复结论。

A03 使用合成引用验证返回逻辑，没有读取真实密钥。能否由某个真实事件具体携带该引用，仍需 HTTP/SSE 负面矩阵验证。

### Run 与 Operations 的重复生命周期

`runtime_runs` 同时记录上下文摘要和 active/status，并有独立活跃唯一约束；`runtime_run_interrupts` 记录 interrupt 关联；每个运行强制引用一个 Operation。读 Run、消费 SSE、下一次启动前查询上游都会回写本地状态。审批后还会替换原记录的 upstream run_id。

这是本次重构的核心：新平台只记录有业务价值的请求/审计，让可恢复状态与并发裁决回到 Agent Server。旧表和协调器退出新设计；新链路仍需证明幂等、授权与恢复正确，不能将旧协调逻辑机械拆成多个类后称为完成。

### 删除与收缩清单

| 对象 | 判断 | 删除前需要完成的工作 |
| --- | --- | --- |
| `modules/tenants/__init__.py` | 只有一行的模块占位，可删除候选 | 全仓引用检查；不删除可信 tenant scope 字段 |
| `NullUnitOfWork` | app 中只有定义和重导出，没有业务调用，可删除候选 | 检查测试/脚本和导出，保留实际事务保护 |
| 8 个 `*RepositoryProtocol` | app 内没有消费，部分仅被重导出；没有产生实际依赖反转 | 删除无使用的接口声明，保留同文件的 Stored 数据类型；不是删除全部 ports.py |
| `modules/assistants/` | 52 行兼容重导出，正式路由已经从 agents 导入 | Agent 契约测试改用新入口；Operations artifact 测试随退役业务删除，再清理兼容包 |
| Gateway global/batch/cron、prune/copy/update thread、wait/delete run 等方法 | 在当前 HTTP allowlist 中无入口；引用主要是对应 port/upstream/SDK 包装及旧测试 | 逐方法查 Python/前端/脚本调用，删整条无入口纵向链，保留真实受支持的 Thread/Run/State/History 路由 |
| `_load_static_graph_configs()` 与 AST schema provider | 跨服务路径耦合，应替换后删除 | 部署端只读发现和 schema 已通过空库/独立镜像测试 |
| Agent resync、`AssistantResyncExecutor`、同步状态字段 | 当前 resync 仅更新 ready/time/profile，未访问上游；整体删除 | 同步移除前端按钮、operation kind、接口及对应旧测试；新表不包含同步字段 |
| `delete_runtime` / `delete_threads` 参数 | Service 接受但未使用，删除 | 前端同步删除传参，新契约不承诺这些动作 |
| `/assistants` 产品别名 | 删除旧产品读写别名，统一 Agent 管理入口 | 前端和测试更新到新契约；SDK 的 assistant_id 是官方字段，必须保留 |
| models/tools refresh 旧上游路径 | 仍请求 `/internal/capabilities/models|tools`，当前 Runtime 源码/安装包未发现对应实现 | 先完成真实路由核验；模型以平台配置为主，Tools 内部授权能力不能连带删除 |
| `runtime_runs`、`runtime_run_interrupts` 与 reconciliation executor | 退出新设计，改为最小请求记录 | 新链路原子幂等、未知提交恢复和审批验证通过；不迁移旧运行或审批历史 |
| `project_knowledge` / `testcase` 及专属外部 adapters | 用户确认删除业务 | 同步清理路由、权限、配置、模型、前端页面及失效测试 |
| `operations` / 平台 Worker / 队列 / artifacts | 删除，当前注册任务均退出或可直接请求 | 目录刷新解除 Operations 依赖，清理部署入口与平台专属依赖 |

8 个未消费 RepositoryProtocol：ServiceAccounts、Projects、Assistants、Announcements、Operation、Audit、Users、RuntimeCatalog。`OperationExecutorProtocol` / `OperationDispatcherProtocol` 原本有实际调用，但随 Operations 业务整体退役，不是按“无调用接口”判定删除。

### 整体模块处置

| 模块 | 处置 | 理由 |
| --- | --- | --- |
| identity / iam / projects / users / service_accounts | 保留，简化装配和数据访问 | 都有真实认证、授权和项目治理能力，不因 open-swe 缺少这些模块就删掉 |
| announcements / audit / platform_config | 保留，校准文档和审计动作 | 公告、审计和系统设置属于控制面；audit 的 466 行 URL 判断可逐步改为路由显式声明 |
| agents / runtime_catalog / runtime_policies | 重点重构 | 产品 Agent、部署能力和模型主数据分开；策略需确实作用于执行 |
| runtime_gateway | 重点重构 | 只保留授权、协议适配、请求治理与转发 |
| operations | 删除 | 导出、知识维护、假同步与平台 Run 协调均退出；目录刷新无需通用任务框架 |
| testcase / project_knowledge | 删除平台业务和专属 adapter | 用户明确缩小首期范围；独立结果域/知识服务源码不在本次删除范围 |
| adapters | 按实际调用收缩 | 标准 SDK + 必要 HTTP 扩展即可；不建立自研完整 LangGraph SDK |

### 依赖与规范问题

AST 静态导入检查发现模块级双向边：operations ↔ runtime_gateway/runtime_catalog/project_knowledge、runtime_catalog ↔ runtime_policies、projects ↔ service_accounts。这不等同于已经发生 Python import 崩溃，但说明模块边界互相牵制。部分来自装配代码，应先移到 app 组合根，不新增事件总线解决目录问题。

当前 handbook 仍要求每个模块统一四层、描述 assistants 实现目录和“未来预留”，与代码及 Runtime 的按需建文件原则冲突。应更新活规范，不再复制旧目录当模板。

Dockerfile 未使用 uv.lock，也未打包 migrations/alembic.ini；需要明确可复现安装和独立迁移作业如何交付。现有镜像构建成功不代表迁移工具已随镜像交付。

## 参考依据

- Runtime knowledge：11/13 的目录和边界原则；platform-runtime-integration 的 01/02/09/11/12。部分旧段落已被后续文档取代，保留历史并不代表继续实施。
- open-swe 本地 HEAD `ad417d64`：`agent/dispatch.py:241` 的配置准备、`create_durable_run():260` 的统一创建、`agent/dashboard/thread_api.py:2474` 的流式前置授权。只借鉴原则；该 thread_api 自身也很大，不作为目录模板。
- 官方 [Agent Server](https://docs.langchain.com/langsmith/agent-server)、[并发运行策略](https://docs.langchain.com/langsmith/double-texting)、[RunsClient.create](https://reference.langchain.com/python/langgraph-sdk/_async/runs/RunsClient/create)。通过 langchain-docs/reference MCP 核对；GraphHarbor 的实现兼容性必须另测。

## 任务拆分

- [x] 盘点模块、入口、未使用接口及跨模块导入。
- [x] 阅读 Runtime 设计、现有 dispatch 项目和 open-swe 对应实现。
- [x] 运行现有测试并记录失败；复现重点应用逻辑问题。
- [x] 用户确认全新平台层、无旧兼容、无旧数据迁移，删除知识库与测试用例业务。
- [x] 核查 Operations 注册任务及前端入口，确定关联收缩范围。
- [ ] 实施时逐项清理调用者、权限、配置、部署及测试，避免留下失效入口。

## 验证要求与记录

### 2026-09-10 基线

在 `apps/platform-api/` 执行：

```bash
PLATFORM_RUNTIME_INTEGRATION=0 .venv/bin/python -m unittest discover -s tests -p 'test*.py' -q
```

结果：`Ran 167 tests in 255.210s; FAILED (failures=1, skipped=3)`，即 163 通过。

结构化结果与关键源码 SHA256 见 [review-baseline.json](evidence/review-baseline.json)，用于区分工作区后续变化与本次审查基线。

- 失败：`RuntimeCatalogDelegationTest.test_refresh_graphs_preserves_static_graphs`。
- 原因：测试读取真实相邻 langgraph.json 并断言含 showcase_demo；该生产配置当前只有 reference_agent/workflow_demo，Showcase 在独立 Demo 配置中。说明该测试与目录发现均绑死了本地部署布局。
- 此失败位于审查前已有改动文件；本轮没有修改产品代码或该测试，也不以扩大生产 Graph 注册来“修绿”测试。
- 3 项真实 HTTP integration 因显式关闭外部服务测试而跳过，不计入通过。
- 测试同时报告弱测试 JWT 密钥和 SQLite 连接未关闭等 warning；基线不是完全干净状态。

行为探针见 [reproduce_current_behavior.py](evidence/reproduce_current_behavior.py)。从仓库根目录执行：

```bash
apps/platform-api/.venv/bin/python docs/projects/20260910-platform-api-refactor/evidence/reproduce_current_behavior.py apps/platform-api
```

探针复用现有测试的临时 SQLite，Mock 上游响应，不访问真实服务；断言的是当前缺陷行为，后续修复时转为正式反向回归测试，不将它作为“产品测试通过”。本轮已复现 A01/A02/A03 和 A04 中历史 metadata 的放行分支，四项均已纳入该脚本并重新执行通过。

未执行 PostgreSQL 并发、真实 GraphHarbor、真实模型和浏览器验收；不复用 Showcase 后端的通过数冒充平台验收。

## 状态

现状审查完成，基线 `partial`（有已知失败及未覆盖链路）。总体方案已确认；知识库/测试用例平台业务及其前端接入已退役，其余整改仍待完成。实际实施与验证见 04，不覆盖本篇保留的历史源码证据。
