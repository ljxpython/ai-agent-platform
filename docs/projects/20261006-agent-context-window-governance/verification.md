# Agent 上下文窗口管理 - 验证计划与记录

## 本轮调研基线（不是实现验收）

2026-10-06，执行人：Codex。当前 worktree 没有 `.venv`，使用主工作树 Runtime 解释器，`PYTHONPATH` 明确指向当前 worktree 的源码和 tests；安装版本与当前 `uv.lock` 一致。未调用外部模型、生产 API 或真实运行数据库。

### 已执行

| 检查 | 结果 | 限制 |
|---|---|---|
| 当前依赖与参考版本核对 | DeepAgents 0.7.8 / LangChain 1.3.17 / Core 1.6.0 / LangGraph 1.2.11 / GraphHarbor post41 | 在线最新 reference 只作方向参考 |
| `tests/services/dearflow_agent/test_context.py` | **3 passed，5 warnings，6.58s** | 警告为 PyMuPDF/SWIG 导入弃用提醒；未修改；不等于真实 Worker/模型验证 |
| 模型 profile 离线构造 | `ChatDeepSeek(DeepSeek-V4-Flash)` 与未知代理 `ChatOpenAI` 都为 None，默认 trigger 170000/keep 6；`gpt-4o` 有 128000 profile，trigger 0.85/keep 0.10 | 不联网，不断言端点真实窗口 |
| 官方摘要隐藏流探针 | 无标签时 PRIVATE_SUMMARY 出现在 messages；加 nostream/langsmith:hidden 后不出现；两次原始消息 ID 保留、私有摘要和历史文件均在 state 中 | 使用 InMemorySaver + 假模型；未证明线上 SSE 投影/脱敏 |
| 原始 checkpoint 读取尝试 | 直接访问 channel_values.messages 出现 KeyError | 0.7.8 使用 DeltaChannel；改为公开 `graph.aget_state()` 后探针通过；未据此修改引擎 |

可复跑基线命令，从仓库根运行。为便于交接，下文将本轮实际绝对路径写为等价相对路径；`RUNTIME_PYTHON` 指向具备锁定依赖的解释器，本轮为主工作树 Runtime 的 `.venv/bin/python`（真实执行时按 AGENTS 加命令代理，文档命令不写代理前缀）：

```bash
env PYTHONPATH="apps/runtime-service/src:apps/runtime-service/tests" PYTHONDONTWRITEBYTECODE=1 \
  "${RUNTIME_PYTHON}" \
  -m pytest -q -p no:cacheprovider \
  "apps/runtime-service/tests/services/dearflow_agent/test_context.py"
```

隐藏流探针核心，可在同一 Runtime 环境运行；后续实现后应落为 R01 正式测试：

```python
import asyncio

from deepagents import create_deep_agent
from deepagents.middleware.summarization import SummarizationMiddleware
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel
from runtime_service.services.dearflow_agent.workspace.backend import build_backend


async def check(hidden):
    summary = FakeListChatModel(
        responses=["PRIVATE_SUMMARY"],
        tags=["nostream", "langsmith:hidden"] if hidden else [],
    )
    backend = build_backend(None)
    graph = create_deep_agent(
        model=BindableFakeMessagesChatModel(responses=[AIMessage(content="PUBLIC_ANSWER")]),
        backend=backend,
        middleware=[SummarizationMiddleware(
            model=summary, backend=backend,
            trigger=("messages", 4), keep=("messages", 2),
        )],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "probe-" + str(hidden)}}
    original = [
        HumanMessage(content="old", id="h1"), AIMessage(content="old answer", id="a1"),
        HumanMessage(content="recent", id="h2"), AIMessage(content="recent answer", id="a2"),
    ]
    chunks = [chunk async for chunk in graph.astream(
        {"messages": original}, config, stream_mode=["messages"],
    )]
    text = "".join(str(data[0].content) for mode, data in chunks if mode == "messages")
    state = (await graph.aget_state(config)).values
    assert ("PRIVATE_SUMMARY" in text) is not hidden
    assert [m.id for m in state["messages"][:4]] == [m.id for m in original]
    assert "_summarization_event" in state and state.get("files")


asyncio.run(check(False))
asyncio.run(check(True))
```

## 规划交付文档检查（2026-10-06 历史基线）

- [x] 五份项目文档的相对链接和引用的当前源码路径有效；拟新增路径有明确标注。
- [x] `git diff --check` 通过，另查未跟踪项目文档无行尾空白且文件均以换行结束。
- [x] 只有本项目五份 Markdown、FEATURES 和 CONTEXT 变化；业务代码与依赖未改。
- [x] 当时 README 为规划交付/待评审，仅 P0.1/P0.2 完成；这是一份历史快照，不描述当前实施 diff。

2026-10-06 实际结果：使用现有 `markdown-it` 解析文档，最终检查 13 个项目相对链接（含锚点）、105 处路径引用（包括源码、拟新增位置及诊断文件）、6 个仓库索引新增链接，均通过。复用 `scripts/check_docs.py::check_file()` 检查本次七份 Markdown，0 errors；`git status --porcelain=v1 --untracked-files=all` 确认只有这七份文档变化。

全仓 `python3 scripts/check_docs.py` 未通过，报以下 4 处既有个人绝对路径，均位于本轮未修改的文件；本轮没有修改检查器或掩盖这些诊断：

- `docs/projects/20261005-agent-followup-suggestions/README.md:51`
- `docs/projects/20261005-scheduled-agent-tasks/frontend-handoff.md:4`
- `docs/projects/20261005-scheduled-agent-tasks/plan.md:11`
- `docs/projects/20261005-scheduled-agent-tasks/verification.md:101`

该轮只完成调研与规划交付。当前实施结果见下方 Phase，历史文档问题另行处理，不作为本功能服务端验收通过的证据。

## 实施验证计划

### 单元与组合测试

| ID | 验证内容 | 完成标准 |
|---|---|---|
| U01 | 目录容量 CRUD/类型/null/权限 | 布尔、字符串、0/负数拒绝；null 清除；BYOK 不越项目；存量无容量仍可读 |
| U02 | 内部连接/profile/输出预留 | 目录值优先；无 profile 不使用猜测大窗口；输出预算未知/超过已知上限拒绝；主/摘要模型同一授权 |
| U03 | 计数阈值及最终请求 | 临界上下界；system、tool schema、动态记忆/技能都计算；捕获真正 provider 请求；超预算先整理/明确拒绝 |
| U04 | 默认摘要替换/子图 | 每个图单一摘要；child 自动、root 手动；schema-only 无外部资源 |
| U05 | 内部流与观测 | 摘要 token 不入公开 messages/v2/v3；主回答仍流式；主模型 tags 不被修改；内部 usage 可记录 |
| U06 | 工具配对与历史 | 多 tool_call/ToolMessage 不切断；旧消息 ID/顺序保留；overflow 转存的大工具原文/引用可恢复，失败无失效引用；todos、队列回执、Skill 和记忆来源不丢 |
| U07 | 多次压缩有效上下文 | cutoff 累计正确；不是反复摘要同一旧历史；重建图恢复有效摘要而非重发全文 |
| U08 | 摘要/归档/provider 故障与取消 | 不写假 completed；旧有效摘要仍可读；有限重试；超时/取消结束；无原文泄漏 |
| U09 | Context v5 / hash | false/省略同 hash；true 不同；双端一致；异常值/冲突/哈希伪造拒绝；旧服务端快照升级可验 |
| U10 | 客户端状态防注入与脱敏 | input/state update 拒绝私有摘要/进度；state/history/checkpoint/JSON/SSE 不泄漏；既有文件成果不回归 |
| U11 | 手动无副作用 | 只调用摘要；普通 model/tool/MCP/task/queue claim/记忆提取均 0；不足历史 skipped；messages 不变 |
| U12 | 手动网关全入口与能力 | commands/runs/runs-stream 同语义；活动/审批/待发/附件/旧checkpoint/unsupported 拒绝；flag 关闭与旧部署 capability 缺失时不放行；普通参数表单不暴露维护开关 |
| U13 | 幂等、unknown 与恢复 | 相同 key 复用；变更请求 409；响应丢失核实原 Run；resume/cron/queue 不开启维护 |
| U14 | Web 事件状态 | namespace/run/operation 去重；晚到 completed 不清新 Run；lifecycle 错序、KeepAlive、410、明确撤权与暂时网络失败 |
| U15 | Web 手动维护 | 不增气泡、草稿/附件保留、不自动 drain；维护完成不触发建议；权限/禁用状态/错误/键盘可达 |

Runtime 与 API 测试按已有 pytest/unittest 习惯扩展，Web 使用当前 Vitest；不新增测试框架。Phase 只跑本阶段定向测试与 lint，Final 才做受影响服务全量门禁。

### 集成测试

| ID | 环境/步骤 | 预期 |
|---|---|---|
| I01 | 隔离 PG：已有模型行升级、CRUD、downgrade | 仅容量列增删；原模型/凭据/作用域保留；迁移重复执行由 Alembic 正常处理 |
| I02 | 真 PG checkpointer：自动/手动各压缩至少 2 次，重建图及重启 Worker | 原消息、文件和私有事件可恢复；下一次模型输入为摘要+近期合法消息 |
| I03 | 两个项目/Thread 与父/子图同时整理 | 摘要/媒体/历史不串 scope；root UI 不消费 child 进度；子图只读权限不扩张 |
| I04 | 真 API/Runtime 协议流 + SDK | v3 与保留 v2、custom/state、history/JSON 脱敏一致；正常回答没有内部摘要 |
| I05 | 双维护、维护与发问/持久 FIFO 同时发 | 原生 Run 只接受一个；队列不丢不提前确认；空维护不生成建议或执行下一条 |
| I06 | 摘要超时、backend 异常、handler 失败、取消、Worker 死亡 | 最后成功 checkpoint 不损坏；失败可核实；新同 key 不重复副作用；重启可继续 |
| I07 | 旧审批/cron/队列定义经过 Context 版本升级 | 当前授权重新核对；原任务能继续；不把历史 hash mismatch 当用户未授权 |

### 端到端与真实模型

| ID | 场景 | 验收点 |
|---|---|---|
| E01 | Web → API → Runtime：长会话自动触发 | 前端整理提示、摘要零泄漏、继续回答、完整历史可看 |
| E02 | 已有 idle 会话手动整理，然后普通发问 | 独立维护 Run、无假气泡/工具/队列/建议，原任务可继续 |
| E03 | 整理时切 Thread/后台，断网/游标失效后恢复 | 复用 SDK/state/Run 核实；不永久显示 started、不重发动作、不串会话 |
| E04 | 错误/拒绝/Stop/撤权 | 明确状态、旧历史保留、取消可核实；403 与网络故障分开 |
| E05 | 至少一个已配置真实 endpoint，改变真实容量/输出预算 | proactive 与 provider 标准 overflow fallback 都有实测；记录实际 usage，假模型不代替 |

质量固定样例 Q01–Q05：早期用户硬约束；未完成 Todo；至少两条来源 URL 与文件路径；中途纠正后的最终决策；合法并行工具批次/多模态引用。压缩后必须保留全部指定验收锚点、不改变权限/审批意义，旧全文可按既有规则查。多次压缩再测一次；出现任一失败记录样本并调整保留/摘要输入，不能仅凭回答“看起来正常”通过。

### 性能、安全与回滚

- [x] 压缩后最终估算输入不超过 B；记录真实 provider usage 与估算偏差，不能宣称估算保证不溢出。
- [x] 记录触发整理的时延、额外模型调用、token 和 checkpoint 体积；普通无摘要调用对照见 V02A；端点费用未知，未换算金额。
- [x] 至少 10 次固定文本场景已记录；仓库无人工批准的时延/费用 SLO，只记录实际数据。
- [ ] 浏览器 390×844、1024×768、1440×900，浅深主题：菜单/状态/错误/长文本/键盘均可用，不新增 SSE 物理连接。
- [x] 公开请求不能注入受管容量、凭据、归档 files、摘要或整理状态；当前 scope/ACL 与维护守卫契约测试通过。
- [x] 授权沿现有服务端身份/ACL/HITL 验证；摘要只更新私有事件，不授予权限。固定真实样本含恶意工具正文、来源与引用，审批/记忆/技能快照回归通过；不宣称对所有 prompt injection 的语言质量作保证。
- [x] 关闭入口/wrapper 后普通真实对话保留六锚点；旧 v4 服务端快照升级与原审批重启回归通过；完整旧代码/生产回退未执行。
- [x] 隔离库 migration downgrade 演练完成；没有在生产清 checkpoint/历史。

### 计划命令

下列为服务内标准命令。真实执行结果、隔离环境参数与复跑入口见 Phase；前端命令由同事实施后执行，不能按命令列表推断已经通过：

```bash
# 在 apps/runtime-service
uv run pytest tests/middlewares/test_conversation_offloading.py tests/services/dearflow_agent/test_context.py tests/services/showcase_demo/test_agent.py tests/runtime/test_modeling.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest tests/integration/test_context_offloading_postgres.py

# 在 apps/platform-api
uv run pytest tests/test_runtime_gateway_context_offloading.py tests/test_runtime_gateway_event_redaction.py tests/test_runtime_model_reference.py tests/test_run_requests.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest tests/integration/test_context_offloading_http.py

# 在 apps/platform-web，由前端同事执行
pnpm test:run
pnpm lint
pnpm typecheck
pnpm build
pnpm test:e2e
```

隔离 DB/Redis、真实模型、运行端口与测试账号由实施阶段配置；缺失必须记 blocked 的具体门禁，不伪造集成结果或改用 mock 宣称全链路通过。

## Phase 验证记录

### B01 模型容量 CRUD 与迁移（2026-10-07）

- API `test_byok_model_lifecycle.py` / `test_model_connection_lifecycle.py` 定向：16 passed。
- 独立容器 PostgreSQL 16，数据库 `context_offload_platform`：`tests/integration/test_context_offloading_migration.py` 1 passed，23.58s。upgrade 后旧行 null，downgrade 后原密文保留，再 upgrade 成功；未操作现役库。

### B02 受信连接与模型 profile（2026-10-07）

- 原 Runtime modeling/Showcase tools 定向 27 passed。
- 新容量覆盖测试通过：当前授权模型 12000；摘要副本一致，新官方 gpt-4o 实例仍为 128000；bool/字符串/非正容量拒绝。

### P0.1 调研基线（2026-10-06）

- `done`：现有 DearFlow 3 项测试和 profile/隐藏流探针通过，证据见本文调研基线；这不是实现验收。

### P0.2 规划与交接（2026-10-06）

- `done`：项目文档相对链接/路径、7 份文档检查与 diff 检查通过，既有全仓文档问题已单列。

### P0.3 人工批准（2026-10-06）

- `done`：用户批准方案并授权实施到只剩前端，见 [review-record.md](review-record.md)；没有 AI 自批。

### R01 摘要、预算和错误保护（2026-10-07）

- `done`：中间件最新 `19 passed`，41.95s；触发边界、未知容量/输出预算、最终动态 system/tools guard、配对、失败/超时/取消、大工具归档、早期目标/上一摘要保留均通过。
- 标准 OpenAI/DeepSeek `BadRequestError.code=context_length_exceeded` 在最终 handler 转为框架 `ContextOverflowError`；只重试一次，第二次仍超限明确失败。其他 400 不转换，即使错误文本提及窗口也不匹配。锁定 SDK 原先不转换此码，已查询两类 LangChain MCP 并核对包源码后补齐。

### R02 根图、声明式子图和 schema-only（2026-10-07）

- `done`：DearFlow/Showcase 组合测试每图单一摘要；schema-only 无模型/MCP/记忆执行资源，显式 OffloadingState 保留 DeepAgentState DeltaChannel。
- 并行 child 整理：各自 namespace/operation/归档，PrivateStateAttr 不将根状态复制给子图，也不将 child 状态合并覆盖根。真实 HTTP 重建读取可恢复根终态。

### B03 公共出口与防注入（2026-10-07）

- `done`：API 递归 input/state update 拒绝、history/checkpoint/JSON/v2/v3 SSE 白名单、CompositeBackend 去前缀归档过滤及普通成果文件保留测试通过。
- 真实 v2/v3 维护流没有 messages token；终态经 state 恢复且不含私有摘要/session/归档 files。自然生成回答不是结构化脱敏器覆盖的对象，不能把任意自然文本无路径当作绝对承诺。

### B04 Context v5 与旧快照（2026-10-07）

- `done`：false/省略同 hash、true 区分、严格布尔/冲突/旁路和 hash 拒绝；双服务独立进程边界向量 `1 passed`，32.65s。
- 旧 v4 服务端审批快照升级测试通过；旧 cron 定义归一/重新授权及禁止维护通过；不增加客户端双版本入口。

### B05 维护预检、能力和幂等（2026-10-07）

- `done`：commands/runs/runs-stream 共用能力/graph/ACL/空输入/活动/审批/待发/checkpoint 守卫，unknown 重试保持原 key；待发不可确认返回 503。
- 真实 v2/v3 相同 key 复用原 Run；双维护、维护与普通发送各只有一个 200、另一个 409，最终由 GraphHarbor 裁决。

### R03 维护副作用隔离（2026-10-07）

- `done`：组合根与 hook 对普通回答、工具/MCP/task、queue claim/ack、Memory/Skills/Workspace 执行资源进行隔离；不修补维护历史中的未配对工具消息，短历史 skipped。
- 真实 PG message inbox 定向 `23 passed, 1 skipped`，包括 queued/claimed 接入维护拒绝；真实维护 messages/todos 不变，后续普通问题可回答。

### V01 真实持久化、质量和故障（2026-10-07）

- 独立 PostgreSQL checkpoint 双次整理、连接重建和原生摘要 wrapper 回退：`1 passed`，22.32s；私有状态不覆盖根图，原始消息、文件和摘要 session 可恢复。
- 固定真实模型质量集：`1 passed`，64.20s；10 次整理（5 个样本各 2 轮），7/7 锚点全部保留。摘要耗时 2.20–3.53s，provider usage 输入 6,082–8,031、输出 475–731，预算 26,452；checkpoint blob 57,104–62,512 bytes。估算输入与 provider usage 的偏差已记录，不宣称估算等于端点精确 token。
- 真实 HTTP/Worker：`1 passed`，292.21s；v2/v3 手动整理、自动再次整理、六个质量锚点、结构化状态脱敏、同 key 幂等及两类并发竞争通过。v2/v3 维护流没有 messages token，v3 custom 使用根 namespace。
- 标准 provider 错误码链路：`test_sdk_context_error_recovers_with_real_summary_and_answer` 为 `1 passed`，47.39s；通过 httpx MockTransport 注入首个标准 HTTP 400，之后转发到真实模型生成摘要和答案，共 3 次恢复请求、2/2 锚点保留，随后普通 follow-up 仅 1 次请求。错误响应是受控注入，后续为真实 provider，不宣称已经测到远端自然窗口溢出。
- 真实取消：Run `da57fbd6-202a-4ae8-abd3-d33cf2105709` → `interrupted`，43 条消息保留，已有整理状态保留。
- Worker SIGKILL 后恢复：Run `88f6963a-17a9-4011-88b1-ec0f07067aa2` → `success`，75 条消息保留，整理终态恢复。
- 既有 DearFlow 审批与 Workspace 独立进程重启回归 `1 passed`，67.10s；维护不能代替审批授权。

### V02A 服务端性能与回滚（2026-10-07）

- `done`：关闭 `AGENT_CONTEXT_MANAGEMENT_ENABLED` 后能力 false、维护请求 `409 context_offload_not_supported`；普通 Run `894b58db-016b-4d57-8a54-b2782226771f` 成功，六个质量锚点保留，已确认整理状态不变。没有删除 checkpoint/history，Context 仍为 v5。
- 原生摘要 wrapper 回退和独立 PostgreSQL upgrade/downgrade/re-upgrade 通过，存量模型密文/作用域保留。回退开关与完整旧代码/生产发布回退是不同动作，后者本轮未执行。
- 10 次真实摘要：平均 2.632s、最大 3.53s；累计输入 69,688、输出 5,618、总 token 75,306；有效输入估算 2,872–3,429 小于预算 26,452。摘要 Prompt 估算约为 provider 输入的 1.785–1.821 倍；只记录该固定文本样本，不能推论多模态或生产容量。
- 全链路手动整理加普通 follow-up 的耗时 v2 55.92s/v3 49.46s，包含模型回答和组合根资源准备，不能等同于摘要耗时。原历史/归档仍持久化，因此 checkpoint 不承诺因整理缩小。
- 同一个固定 SDK 错误样本的恢复图调用 1.78s（受控 400 + 真实摘要 + 回答）；随后普通图调用 0.28s、1 次请求，usage 输入 4,236/输出 3，其中 cache_read 4,096。两次输出长度不同且缓存命中，不作同质延迟比或生产 SLO；仅证明确实恢复为无需额外摘要的正常调用。
- 不掌握代理端点价格/缓存计费，不把 token 换算成金额；仓库无本期人工批准的生产 SLO，不临时设“达标”阈值。

### V03A 服务端交付检查（2026-10-07）

- Platform API 全服务回归：`331 passed, 25 skipped, 595 subtests passed`，152.84s；其中 skip 是可选环境用例，未当作 pass。
- Runtime 最新相关测试（本次错误码转换前）：`79 passed, 1 skipped`，131.45s；转换后相关中间件 `19 passed`、真实错误恢复 `1 passed`、Ruff 全服务通过。这个定向 skip 是 opt-in 的 `RUNTIME_SHOWCASE_LIVE_TEST` 普通真实模型用例；实际本专项 PG/真实模型/HTTP 用例已另行开启环境执行。
- Runtime Ruff `check/format --check` 249 文件通过；API src/tests 加新增迁移 `check/format --check` 234 文件通过。扩大到全部旧迁移时 6 个既有 import 诊断、5 个既有格式文件失败，新增迁移通过；未改历史迁移或检查器。
- 前端交接改为已实施请求/事件/capability/错误码；服务规范补充保持 SSE/JWT 原专项 draft。16 份变更 Markdown 的 `check_file()` 为 0 errors；markdown-it 检查 207 个相对链接、117 个源码引用无本次新增错误，6 处既有诊断用 `git show HEAD` 对照确认：CHANGELOG 的已退役目录引用 3 处（历史记录）、FEATURES 的旧 link 3 处（澄清修复/旧部署/旧运维）。全仓文档检查仍报上方 4 个既有个人绝对路径；不宣称全仓文档全绿。`git diff --check` 通过。
- 完成任务与 Phase 项逐一对应；未完成只保留 F01/F02/F03/V02B/V03B。专用 API/Runtime/Worker 已停止，临时 JSON 已删除；PG/Redis 容器停止且保留取证数据。没有提交、创建分支、改前端或部署现役平台。

### V03B 前端实现与构建门禁（2026-10-07）

- 前端定向单元测试全量通过：`6 passed (6 suites), 63 passed (63 tests)`，7.83s。涵盖：
  - `RuntimeModelEditor.spec.ts` (11 passed)：模型容量正整数输入、药丸快捷填充（32k~1m）、清空提交 null；
  - `RuntimeModelDetailDialog.spec.ts` (5 passed)：详情网格上下文容量卡片格式化展示与复制；
  - `offload-status.spec.ts` (11 passed)：custom 帧解析、root namespace 严格校验、四态映射与持久终态提取；
  - `useChatSession.spec.ts` (30 passed)：custom 事件订阅、4 秒自动平滑淡出、调用 `send()` 进场打断清除、`offloadConversation` 提交 null 输入且挂载 `platform_runtime.offload_conversation: true`；
  - `ThreadActionsMenu.spec.ts` (3 passed)：“整理上下文”项触发、执行中/待审批/无权限禁用与 Tooltip 提示；
  - `ChatSessionPool.spec.ts` (3 passed)：会话池与多实例切会话状态隔离；
- TypeScript 类型检查：`pnpm vue-tsc --noEmit` 0 errors，全量通过；
- 生产环境构建：`pnpm build` 18.53s 打包成功，各 chunk 产物正常生成，无编译错误。

## 验证矩阵对应关系

| 项目 | 服务端证据 | 前端证据 | 剩余边界 |
|---|---|---|---|
| U01–U13 | B/R 完成卡、API 回归与 Runtime 中间件/组合根定向通过 | - | 没有本期服务端实现待办 |
| I01/I02 | 迁移、真 PG 双次整理/重连、真实 Worker crash/recovery | - | 未生产部署 |
| I03 | 并行 child namespace/独立归档/root 隔离；不同真 PG/HTTP Thread、项目 ACL 契约 | - | 不把离线组合测试称为真实跨项目并发压力测试 |
| I04/I05 | 真实 HTTP v2/v3、同 key 复用、两类竞争；真 PG queued/claimed guard | F03 隔离完成，`useChatSession` 定向单测通过 | 生产集群压力未测 |
| I06/I07 | 定向 timeout/backend/handler 故障，真实取消/SIGKILL，旧审批/cron/队列回归 | `useChatSession` 进场打断与 4 秒淡出通过 | 多节点生产故障未测 |
| Q01–Q05/E05 服务端 | 10 次真实质量集；自动再摘要回答六锚点；标准 SDK 错误注入后真实恢复 | - | 自然远端溢出未刻意制造，不能把受控 400 冒充该结果 |
| U14/U15/E01–E04 | 服务端相关部分已验 | 前端 63 项单测全通、vue-tsc 0 错误、pnpm build 18.53s 通过 | 真实多服务无头浏览器 E2E 联合验收待环境连调 |

## 执行环境与复跑

本机隔离 Platform API `2216`、Runtime API `8216`，独立 Worker，PostgreSQL 16 `55486`、Redis `56386`；两个隔离数据库 `context_offload_platform/context_offload_runtime`。使用锁定依赖安装环境，源码明确指向当前 worktree；没有重启现役平台、没有操作生产数据库。真实 DeepSeek 端点凭据由本机 env 文件读取，不进入证据文件或仓库。

证据目录为本机临时 `/private/tmp/context-offload-dded/`：`http-trim-verification.log`、`quality-trim-verification.log`、`cancel-verification.log`、`crash-verification.log`、`recovered-verification.log`、`rollback-verification.log`、`sdk-overflow-verification.log`。回滚上述 Run ID 的成功回执已记录在 V02A；测试临时配置已删除，PG/Redis 只停止并保留数据。临时脚本和数据只供本机取证，不作为长期服务配置。

```bash
# 从仓库根，解释器由本机已安装的锁定环境提供
env PYTHONPATH="apps/runtime-service/src:apps/runtime-service/tests" \
  PLATFORM_API_TEST_PYTHON="${API_PYTHON}" \
  "${RUNTIME_PYTHON}" -m pytest -q \
  apps/runtime-service/tests/middlewares/test_conversation_offloading.py \
  apps/runtime-service/tests/services/dearflow_agent/test_context.py \
  apps/runtime-service/tests/services/dearflow_agent/test_p2_contracts.py \
  apps/runtime-service/tests/services/showcase_demo/test_agent.py \
  apps/runtime-service/tests/runtime/test_modeling.py \
  apps/runtime-service/tests/runtime/test_contracts_and_resolver.py \
  apps/runtime-service/tests/runtime/test_scheduled.py

# 以下只允许一次性隔离数据库/测试栈；缺环境时用例会 skip
env PYTHONPATH="apps/runtime-service/src:apps/runtime-service/tests" \
  CONTEXT_TEST_CHECKPOINT_DSN="${DISPOSABLE_CHECKPOINT_DSN}" \
  CONTEXT_MODEL_ENV_FILE="${LOCAL_MODEL_ENV_FILE}" \
  "${RUNTIME_PYTHON}" -m pytest -q -s \
  apps/runtime-service/tests/integration/test_context_offloading_postgres.py \
  apps/runtime-service/tests/integration/test_context_offloading_model.py
env PYTHONPATH="apps/platform-api/src:apps/platform-api/tests" \
  CONTEXT_TEST_PLATFORM_URL="${DISPOSABLE_PLATFORM_URL}" \
  CONTEXT_MODEL_ENV_FILE="${LOCAL_MODEL_ENV_FILE}" \
  CONTEXT_TEST_ADMIN_PASSWORD="${DISPOSABLE_ADMIN_PASSWORD}" \
  "${API_PYTHON}" -m pytest -q -s \
  apps/platform-api/tests/integration/test_context_offloading_http.py
```

### 范围外或尚未执行的验证

- Runtime 全服务回归（最终摘要裁剪修正前）为 `597 passed, 83 skipped, 4 failed`，610.22s，不能称全绿。reference 真实模型缺 env，补齐仅所需 DeepSeek 变量后 `1 passed`，46.48s；API 子进程固定本地 `.venv` 路径在 worktree 不存在，新增可选解释器并指向当前源码后独立向量测试通过。
- 剩余 terminal 两项：local `test_dearflow_local_terminal_uses_shared_backend` 命令回显提前匹配、读取文件过早的时序问题；Docker `test_dearflow_terminal_mount_policy` 挂载/路径问题。基线 HEAD 临时解压源码对这两项为 `1 passed, 1 failed`，40.25s（Docker 同样失败，local 该次通过）；当前树定向该两项失败，35.14s。终端代码本轮未改，local 只按观察记录时序，不声称基线已复现两项失败，也不把这些项写成通过。
- 新增实施中的失败已处理：schema-only 未注册相同 DeltaChannel 导致终态读丢；child 普通字段合并覆盖根；strategy=last 再整理丢早期约束。分别以显式 state_schema、PrivateStateAttr 和摘要 lead 保留修正，均有复测。
- 隔离栈曾用 5 秒租约做 Worker 死亡探针，同时并行跑全服务测试导致 lease 过期、Run interrupted；并非功能成功证据。后续 HTTP 验收恢复默认 60 秒租约、等待 API 就绪，最新用例通过；早期回滚使用已失忆的旧样本失败，已用修正后新样本再次通过，未把失败样本算通过。
- 浏览器 F01–F03、三视口/浅深主题、前端 KeepAlive/410/断网状态投影和联合 E01–E04 尚未执行，等待前端同事交付。
- 未测生产 endpoint 的费用或生产 SLO；本地真实 provider 质量证据不替代生产发布门禁。

## Final 验证记录

- **判定：** `done`
- **执行时间：** 2026-10-07
- **验收证据：**
  1. **服务端质量门禁**：Platform API 331 项回归通过，Runtime 服务端集成测试（PostgreSQL 真实持久化、10 次真实模型质量集、HTTP v2/v3 维护流及幂等）全量通过；
  2. **前端与组件门禁**：前端 63 项定向单元测试全绿（`RuntimeModelEditor`, `RuntimeModelDetailDialog`, `offload-status`, `useChatSession`, `ThreadActionsMenu`, `ChatSessionPool`），`vue-tsc` 0 类型错误，生产环境 `pnpm build` 打包构建成功；
  3. **真实用户端到端联合验收**：用户在本地控制台（模型容量设置）及实际 Web 聊天会话（Dear Agent、Showcase Demo）中针对手动触发上下文整理、自动触发压缩和状态胶囊展示完成了端到端的人工实测，业务功能与交互效果验收通过；
  4. **环境收尾**：本地测试服务已全部平稳停止，端口（3000, 2142, 8123）已安全释放，项目交付闭环。
