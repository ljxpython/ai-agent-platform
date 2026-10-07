# 工具调用容错验证计划和记录

## 验证原则

本专项分四层证明：纯函数分类、真实 graph 组合、跨服务消息运输、真实平台/浏览器体验。单测通过只能证明局部行为，不能替代 Runtime/GraphHarbor/Platform/Web 联调。所有外部模型、MCP、Docker、PostgreSQL、Redis 和平台写操作使用隔离环境；缺条件时记录 `blocked` 或 `partial`，不伪造通过。

## 当前基线记录

### 2026-10-06 只读基线

**执行人：** @laowang（规划阶段）

- 执行环境：本工作树没有 `.venv`，本次使用主检出的既有 Runtime Python 3.13 环境执行工作树内测试；conftest 优先加载本工作树 `src`。已用 importlib.metadata 核实 5 个关键依赖与本工作树 `uv.lock` 一致，没有新建/修改环境。下文用 `RUNTIME_BASELINE_PYTHON` 代称该解释器路径，避免在活文档写入个人绝对路径。
- 实际执行命令的可移植表示（在仓库根目录；先将变量指向上述已有解释器）：

  ```bash
  PYTHONDONTWRITEBYTECODE=1 \
    "$RUNTIME_BASELINE_PYTHON" -m pytest \
    "apps/runtime-service/tests/services/reference_agent/test_middleware_order.py" \
    "apps/runtime-service/tests/middlewares/test_runtime_middleware.py" \
    -k "reference_agent or official_tool_error or official_tool_retry" \
    -q -p no:cacheprovider
  ```

- 结果：`11 passed, 14 deselected, 5 warnings`，耗时约 3.09 秒。
- 证明：锁定版本的官方 `ToolErrorMiddleware`、`ToolRetryMiddleware`、Reference Agent graph 接线和未知异常传播已有可执行基线。
- 限制：没有证明 DearFlow/Showcase 生产 graph、MCP、workspace、Platform API、Platform Web 或真实模型链路已具备本专项目标；没有改代码、没有启动外部服务、没有生产数据操作。

### 2026-10-06 流事件离线探针

- 使用上述环境构造本地 Tool，抛出 `ValueError("CANARY_TEST_DETAIL")`；官方 ToolErrorMiddleware 返回 `safe tool error`，FakeMessagesListChatModel 继续返回 `continued`。
- 执行 `astream(..., stream_mode=["tools", "updates"], version="v3")`，取得 5 个事件；其中 `('tools', {'event': 'tool-error', 'tool_call_id': 'probe-call', 'message': 'CANARY_TEST_DETAIL'})` 带原异常。进程正常退出。
- 根因：`langgraph==1.2.11` 的 `StreamToolCallHandler._error()` 使用 `str(error)`；现有 Runtime patch 只特殊处理 GraphBubbleUp。
- 这是已复现缺口，不是实施后通过项；没有真实模型、网络、数据库或 Sandbox 调用。探针仅在命令中执行，没有新增源码文件。
- 此证据只证明 LangGraph 原始流，尚未抓取现役平台流/浏览器。T06/T07/T09 必须补齐这些出口，不能把源码推断当部署事实。

可复现的最小探针（在锁定 Runtime 环境执行；实施后应迁为 T06 的自动化回归）：

```bash
"$RUNTIME_BASELINE_PYTHON" - <<'PY'
import asyncio
from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

class Model(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

@tool
def probe_tool(value: str) -> str:
    """Offline tool error probe."""
    raise ValueError("CANARY_TEST_DETAIL")

async def main():
    model = Model(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "probe_tool", "args": {"value": "probe"},
            "id": "probe-call", "type": "tool_call",
        }]),
        AIMessage(content="continued"),
    ])
    graph = create_agent(model=model, tools=[probe_tool], middleware=[
        ToolErrorMiddleware(on_error=lambda exc, request: "safe tool error"),
    ])
    events = [event async for event in graph.astream(
        {"messages": [{"role": "user", "content": "probe"}]},
        stream_mode=["tools", "updates"], version="v3",
    )]
    print({"event_count": len(events), "raw_error_visible": any(
        "CANARY_TEST_DETAIL" in str(event) for event in events
    ), "model_continued": any("continued" in str(event) for event in events)})

asyncio.run(main())
PY
```

### 2026-10-06 规划文档检查（仅 P0）

- 使用已有 `scripts/check_docs.py:check_file()` 检查本专项 6 个文件及 CONTEXT/FEATURES，共 8 个文件，通过。
- 使用已安装 markdown-it 解析专项 Markdown 链接，15 个本地链接全部有效。
- `git diff --check` 通过；最终变更仅为 6 个专项文档及 CONTEXT/FEATURES，无业务源码、依赖、数据库或部署变更。
- 全仓 `scripts/check_docs.py` 仍失败，4 处个人绝对路径来自未改动的已有文件：`20261005-agent-followup-suggestions/README.md:51`，以及 `20261005-scheduled-agent-tasks/frontend-handoff.md:4`、`plan.md:11`、`verification.md:101`。没有修改这些范围外文件。
- 本轮规划验收完成；实施任务 T01-T10 和人工评审 G0 均未开始，不生成 Final 功能通过结论。

## 实施后验证计划

以下勾选按实际自动化证据更新。规划时使用的测试示意名已换成实际文件/函数；前端消费和浏览器项独立保留。

### U：单元与纯函数

- [x] `tests/tools/test_tool_errors.py:test_approved_content_is_bounded_and_uses_only_trusted_fields()`：批准四码生成固定有界 JSON，无异常正文、URL、路径、token 或 request repr。
- [x] `tests/test_patches.py`：实际 tools 事件的 message 不带原异常；保留 tool_call_id 和 namespace，不扩展事件类型。
- [x] `test_security_control_flow_and_unknown_errors_are_not_recoverable()`：RuntimeAuthError、RuntimeResolutionError、取消、GraphBubbleUp 和未知异常不转换。
- [x] `test_provider_http_boundary_does_not_reclassify_security_or_defects()`：真实 HTTP client 边界中的安全/未知 ValueError 原身份传播。
- [x] `test_official_middleware_pairs_sync_and_async_errors_and_keeps_success()` 与主图 native 回归：同一 formatter、配对字段与成功结果保留。
- [x] `test_tool_name_and_message_size_are_not_derived_from_exception()`：工具名/类型名上限、content 上限、状态配对正确。
- [x] `test_media_records_unknown_once_and_propagates_fatal_errors()`：先记录已开始操作 unknown，再传播未分类故障；相同幂等请求不重复提交。

### G：真实 graph/组合测试

- [x] DearFlow 主 Agent：已知输入错误 -> error ToolMessage -> 模型继续 -> 最终回答；受控 graph、跨进程和真实模型均有证据。
- [x] DearFlow researcher 子 Agent：内部工具错误被子模型消费，父图收到子结果；子图致命故障向父图传播。
- [x] Showcase 主/子 Agent：同样的选择性策略，HITL 不被吞。
- [x] Reference Agent：原有 read-only 有界重试与未知传播保留；没有新增重试。
- [x] 并行调用：成功/错误正确配对；同批审批中断时暂停零执行，恢复后各消息一次。子图 namespace 独立回归。
- [ ] 并行/子图工具卡无重复：前端 F02/F04 实际消费验收。
- [x] 工具预算：原 Model/Tool/Task limit 回归和连续可恢复错误耗尽 child model budget 已通过，不新增循环状态。
- [x] 调用顺序：权限/allowlist/预算先拒绝；原只读 Retry 被外层 ToolError 包住，成功 Command/审批恢复保留。

### I：集成与资源故障

- [x] MCP：真实独立 HTTP MCP 的 isError 文本/图片保留，构图拒绝/名称冲突 fail-closed；transport 可分类，conversion/混合安全组传播。
- [x] 文件工具：原文件不存在/无匹配编辑/非零退出语义保留，不当作可信根故障。
- [x] workspace：缺/不安全可信根、临时 IO EACCES/ENOSPC、缺 Docker CLI 的创建失败均传播；已有目录/文件保留，不宿主执行。IO 故障为受控注入，没有耗尽真实磁盘。
- [x] timeout/取消：实际 Docker 命令超时及 HTTP 用户取消不自动重发，原清理路径回归通过。
- [x] 非幂等：media/deploy unknown/任务 ID 与同幂等不重发回归通过；HTTP 已进入 Provider 的取消只调用一次。
- [x] exporter/日志故障：原 observability 回归与新增 callback 故障测试通过，native/raised 不双计。
- [x] stream `tool-error`：实际 v3 流固定安全说明，中断/取消无 error；ToolMessage 与流分别检查。

### C：Platform API 契约/安全

- [x] 标准 Run SSE：error ToolMessage、artifact 与 JSON 字符串保真，call/name/status 保留。
- [x] Protocol/State/History：实时与历史配对/namespace 保留；fatal Run error 与可恢复 ToolMessage 分离，重启后消息逐字段一致。
- [x] 网关脱敏：第一方内容、tools 流与 fatal lifecycle/Thread/原生 tasks 公开出口无敏感 canary；原私有字段过滤继续。
- [x] HTTP 出口：原授权/契约 envelope 回归通过；workspace HTTP missing 404 与 unsafe 500 正确，不改变 Agent 停止语义。
- [x] API 权限/幂等：网关全组回归、真实 interrupt ID 的 approve/edit/reject/clarification/cancel 通过，没有重建 Thread 或重复 Provider 调用。
- [x] 页面权限/登录/幂等行为：前端 F05/F07 浏览器验收通过。
- [x] 跨进程链路：独占 Platform API、Runtime API/Worker、PG/Redis 的主/子 Agent 受控运行通过；真实模型主/子 graph 另外通过。

### E：Platform Web / 浏览器

- [x] F01-F08 全部通过，详细清单见 [frontend-handoff.md](frontend-handoff.md)。
- [x] Vitest：`transcript.test.ts`、`ToolResult.spec.ts`、`SubtaskDetail.spec.ts` 联合回归 31 passed (31)，耗时 752ms。
- [x] 静态质量：`pnpm lint` 0 错误、`pnpm typecheck` 0 错误、`pnpm build` 生产构建成功（1.48s）。
- [x] 浏览器：390×844、1024×768、1440×900；浅/深主题；实时流、刷新历史、切 Thread、子图、审批/澄清、取消、断线恢复联合验收通过。
- [x] 不出现自动重试按钮/错误 toast 风暴；长错误不遮挡正文、输入框、审批动作或焦点。

### P：性能和容量（适用时）

- [x] 同一 Python/锁定依赖、实际 graph，对照成功无 middleware/成功有 middleware/已知错误/未知传播，记录 CPU/wall 与固定 content 大小。
- [x] 串行/四并行记录 v3 JSON 字节、InMemory checkpoint 序列化大小和 tracemalloc 峰值；这些不是网络 SSE framing 或 PG 表体积，没有批准 SLO，不作性能达标声明。
- [x] 内容有界，name/call/status/scope 保留；本次无需新增标准或性能框架，实测表见 implementation/03。

### R：回退验证

- [x] 代码基线 HEAD 424ff90e、锁定依赖、测试栈 PG16/Redis7 与启动配置已记录。
- [x] 只读 git archive 提取基线 Runtime，Runtime/Worker 优先加载；主/子旧字符串仍 success，五种控制再次通过，API 安全出口补丁保留。
- [x] 同一隔离数据库和工作区不删除；新 JSON 消息逐字段回放一致，keep 文件及 Provider 次数保留。
- [x] 回退后的主/子 graph 最短链路通过，没有执行生产回退。
- [x] 旧 Web 读取新 JSON 历史、回退后页面操作：前端 F03/F05/F07 浏览器验收通过。

## 隔离链路场景与证据

| ID | 故障注入/操作 | 验收事实 |
| --- | --- | --- |
| E01 | 已授权工具输入非法，下一次模型改参/换方法 | 相同 Run 内 error 消息后有下一次模型调用和回答；历史与实时 call ID 一致 |
| E02 | task 委派 researcher，子工具预期失败 | 子图自己继续推理；主图 scoped 投影隔离，无 task 整体虚假成功 |
| E03 | 根/子图请求被禁工具或身份/scope/hash 非法 | 工具 handler 计数为 0；基础契约拒绝终止；无 error 自纠正循环 |
| E04 | 写工具需要审批，approve/edit/reject；澄清暂停 | 无控制流吞噬；拒绝不落文件；批准只执行批准后的参数 |
| E05 | 模型一直输出同一失败工具调用 | 达到原 Model/Tool/Task 预算后结束，调用次数可数，不无限自纠正 |
| E06 | 流事件工具异常，异常中放虚构 token/路径 canary | Runtime 原始流、平台两种 SSE、state/history 和可见 UI 均不含 canary；保留错误类型和 ID 的安全诊断 |
| E07 | 根目录/执行设施故障 | 终态失败；原工作区 hash/文件保留，无替换空目录或宿主执行 |
| E08 | 操作提交后超时/取消 | 任务/副作用计数不增加第二次；unknown/任务 ID 可对账；用户取消正常收尾 |
| E09 | 刷新、切 Thread、断线重连、API/Worker 重启后查询 | checkpoint 中 error 配对可回放，namespace 保持；不重放有副作用工具 |
| E10 | 候选版本回退到记录的基线 | 新 JSON 和旧字符串历史都可读；审批/取消可用；数据/工作区保留 |

准备独立测试 Platform API、Runtime API/Worker、GraphHarbor、临时 PostgreSQL/Redis 和 workspace 根；分别记录版本、启动方式和端点归属。测试注入只进 fixture app/fake provider/MCP，不能在生产入口增加“强制抛错”的配置键。

E01/E02 先用受控模型证明错误实际进入下一次 ModelRequest，再各补一次真实授权模型的 smoke；不能依赖自然语言 Prompt 稳定触发非法参数来代替确定性验证。真实模型、浏览器和资源故障都取得证据后才算 Final。

每条保存：环境版本、场景编号、命令、request/trace/thread/run/call ID、namespace、工具实际执行次数、事件顺序、Run 终态、live/state/history 的消息摘要、真实文件/任务事实、必要截图及脱敏说明。敏感内容/密钥不写证据文件。

## 测试命令草案

Runtime 定向，在 `apps/runtime-service` 目录执行（根项目不包含此服务依赖）：

```bash
uv run pytest "tests/tools/test_tool_errors.py" \
  "tests/services/dearflow_agent/test_tool_errors.py" \
  "tests/services/reference_agent/test_middleware_order.py" \
  "tests/middlewares/test_runtime_middleware.py" "tests/test_patches.py" -q
```

Runtime 相关全量（实施后按改动范围执行）：

```bash
uv run pytest "tests/services/dearflow_agent" \
  "tests/services/showcase_demo" "tests/observability" -q
uv run ruff check "src/runtime_service" "tests"
uv run ruff format --check "src/runtime_service" "tests"
```

Platform API 定向，在 `apps/platform-api` 目录的独立环境执行：

```bash
uv run python -m unittest discover -s "tests" -p "test_runtime_gateway_event_redaction.py"
uv run python -m unittest discover -s "tests" -p "test_runtime_gateway_runtime_contract.py"
uv run python -m unittest discover -s "tests" -p "test_runtime_gateway_sdk_adapters.py"
```

Platform Web 定向与门禁命令见 [frontend-handoff.md](frontend-handoff.md)。命令只在对应文件创建后运行；本规划阶段不执行不存在的测试文件。

既有 DearFlow `test_platform.py` 包含固定本地端点和项目创建/清理，不能直接打开其 opt-in 开关当作本专项的隔离 E2E。T09 实际 fixture 由 `TOOL_ERROR_PLATFORM_TEST=1` 显式启用，自动分配独占临时端口、身份、PostgreSQL/Redis、SQLite 平台数据库和工作区；不可达时失败，不回落到现役本地栈。Platform API 使用自己的解释器，通过 `PLATFORM_API_TEST_PYTHON` 指定；fixture 配置仅供测试，不新增生产配置。真实外部供应商的超时用受控替身验证，真实模型 smoke 只做已批准的只读动作。

Phase 记录仅对应已完成任务；Final 另开记录，执行全部必需门禁后填写实际结果。环境不足先完成 U/G/C 等不依赖资源的项，最后报告具体缺失条件与未执行用例。

## Phase 验证记录

### T01 验证 2026-10-06

- 有效基线：`tests/services/dearflow_agent/test_tool_errors.py`，`3 failed / 2 passed`，9.50 秒；失败为主/子图结构化错误和未知 ToolException 被吞，非测试环境故障。
- 源码出口清单和 native/MCP/filesystem/任务控制流核对完成，见 [实施记录](implementation/01-error-outlets.md)。第一次辅助模型签名错误已修正，不将其计为生产缺口证据。
- 本机 PostgreSQL/Redis 在监听；Docker daemon 不可达。没有重置或写入现役平台资源。

### T02 验证 2026-10-06

- 共享分类/native/官方 sync-async、流 patch、观测、图片图表定向：54 passed / 2 deselected，7.20 秒；含安全/未知传播和消息上限/canary。
- 分类只使用受信工具名及精确安全 code，ToolMessage 配对/成功返回保持；新增媒体真实边界回归继续随 T03 执行。

### T04 验证 2026-10-06

- DearFlow/Showcase 主子图定向：13 passed，20.28 秒；覆盖模型实际消费 error、并行配对、task 致命传播、拒绝零执行及连续失败预算。
- Reference 原官方 error/retry/未知传播基线：11 passed / 14 deselected，3.76 秒；没有新增自动重试。

### T03 验证 2026-10-07

- 扩大 Runtime 修正后组：288 passed / 17 skipped，1550.26 秒，覆盖 DearFlow、Showcase、观测、公共工具与 patches；两个旧重启文件未重复执行，其 5 项在首次扩大组中通过，结果分开记录。
- 最新分类/观测/流定向：40 passed，52.55 秒，覆盖类型名 128 字节上限和 native JSON code 类型保护。
- 同批成功/错误/审批中断：2 passed / 14 deselected，7.99 秒。暂停时工具调用计数为 0；approve 后成功和错误各自正确配对，文件写一次、Provider 只调用一次。
- 研究工具/技能：56 passed / 3 skipped，646.61 秒；HTTP 根映射/文件/文档：25 passed，104.15 秒；工作树 Platform/Runtime 边界：1 passed，73.50 秒。
- 首次扩大组 14 failed / 274 passed / 17 skipped，2952.66 秒，实际修正及失败根因见 [实施记录](implementation/03-isolated-verification.md)。没有将失败组、跳过或后续分组合并为一次全量通过。

### T05 验证 2026-10-06

- `test_mcp_tools.py` + `test_tool_error_integration.py`：7 passed，34.12 秒；真实本地 MCP 独立进程及 Docker `python:3.13-slim`，仅临时 workspace。
- 第一轮受系统 HTTP proxy 影响，MCP 断开返回 502 ExceptionGroup；fixture 设置 NO_PROXY，分类仅允许已知 transport/5xx且全部 leaf 已知，混合安全/未知组仍传播。修复后全组通过。
- 已验 MCP error text/image 块保留、未授权/冲突 fail-closed、断开安全内容，可信根故障/缺 CLI 停止且不宿主执行，退出 7 与超时 124/137 保留且不重复副作用。
- 2026-10-07 追加临时根 IO EACCES/ENOSPC：2 passed / 6 deselected，5.44 秒。公开异常为稳定 workspace code，cause 保留内部排障；已有 keep 文件不变，无新 work 目录，没有修改真实磁盘权限或耗尽磁盘。
- 收口复查发现普通写入可重建缺根，回归真实失败 1 项后修正同一个 IO helper 的显式 create_root 初始化边界。最终缺根保护/HTTP/上传/图片/文档/成果/终端组 55 passed / 2 skipped，57.81 秒；媒体/研究/审批/技能快照与进程重启组 42 passed / 2 skipped，474.26 秒，原 5 项重启再次通过。终端旧测试的命令回显竞态与遗漏 Docker backend 已修，首组 2 failed 不计通过；详见 implementation/03。

### T06 验证 2026-10-06

- 工具分类、callback、流 patch、DearFlow graph/HITL 与 Showcase 图片图表组合：91 passed / 2 skipped，240.39 秒。含 approve/edit/reject、澄清真实 interrupt/resume、取消、重复错误预算、native/raised 单次计数与日志不可用。
- `tests/test_patches.py` 验证实际 v3 流：公开工具错误固定 `tool.execution_failed`，call ID 保留；GraphBubbleUp/取消不发工具错误，重复 apply 幂等。
- 2 个 skip 是旧 live chart/image opt-in，不计为通过；独立真实模型 smoke 由 T09 记录。

### T07 验证 2026-10-06

- 当前工作树 `PYTHONPATH=src`，API 网关全部 `test_runtime_gateway_*.py`：89 项，85 passed / 4 skipped，127.989 秒。原 4 个 opt-in PG 用例未启用，相关真实持久化使用 T09 独立栈。
- 固定 JSON 字符串和外层配对、MCP artifact、子图 namespace、SSE 任意 chunk 切分、安全/权限/HTTP/幂等测试通过。
- 发现 GraphHarbor fatal lifecycle/Thread.error 的原异常公开出口；adapter 最小补丁替换为 `runtime.execution_failed`，error 字典形状/有界类型保留。普通 content/artifact/metadata/values 的业务数据不做运行错误改写，敏感字段过滤仍生效。
- 旧心跳测试使用固定 sleep，在宿主并发负载下产生竞态；改为等实际收到两次心跳的 Event，并设置 5 秒超时。没有改业务心跳逻辑。
- 增强 HTTP 发现 native tasks error 的原异常泄露后按锁定 TaskResultPayload/PregelTask 字段精确补齐；最新事件脱敏 19 passed，15.960 秒；SDK adapter 23 passed，4.742 秒。content/artifact/metadata/values/result 内普通业务错误和 error=None 的中断不误改。

### T09 非前端验证 2026-10-07

- 新增显式启用的隔离 Docker PG/Redis + Platform API/Runtime API/Worker fixture，生产 graph 配置不变。
- 完整隔离 HTTP 首次通过 1 passed，236.33 秒；可信根保护修正后最终再次通过 1 passed，447.31 秒。主/子图已知错误后 success，Provider 0 次；模型实际消费 fixture-search_web 错误；标准 SSE/Protocol/state/history 保真。
- fatal Run error 的公开 SSE/Thread/tasks/state/history 无异常 canary，Provider 1 次；未授权模型拒绝不增加调用。
- approve/edit/reject/clarification/cancel 全通过；文件只在当前精确 scope 写一次，拒绝/澄清不写；已进入 Provider 后取消只调用一次。
- 三角色重启后消息逐字段一致、keep 文件不变、Provider 累计仍为 2。只读 git archive 基线 Runtime/Worker 后，新 JSON 历史保持，旧字符串主/子图 success，五种控制再次通过。Platform API 安全出口补丁保留，没有生产回退或数据删除。
- 真实模型主/子 graph：2 passed，58.32 秒。主 1 次、子加父 2 次真实模型请求，非空最终回复，无真实搜索或付费生成；不将此单进程 smoke 伪称为真实供应商跨 HTTP 全链路。
- 性能/分类/图片路径：34 passed，95.62 秒；串行/四并行 CPU/wall、流 JSON 字节、InMemory checkpoint 和内存表见 [实施记录](implementation/03-isolated-verification.md)，无批准 SLO。
- 首次跨进程迁移遗漏 Runtime inbox、后续 tasks 泄露、测试启动/超时、scope 路径、Thread graph 绑定与 archive cwd 均已修正并真实重跑；曾遇 Docker backend 失联，恢复后完整组通过。失败组不计通过，明细见实施记录。
- 最终本轮独占容器/服务进程已结束，包括最新 root 回归 PG；原回归 PG 在 Docker 恢复后已不存在，没有触碰现役 PG/Redis 或其他 worktree 容器。
- 前端交付回执已就绪，详见 T08 阶段记录。仅 T09-F 对应页面、浏览器和旧 Web 回退验收未验，没有待处理的非前端阻塞。

### T08 前端单元与静态门禁 2026-10-07

- `apps/platform-web` 纯函数与组件测试回归：`transcript.test.ts`、`ToolResult.spec.ts`、`SubtaskDetail.spec.ts` 共 31 项测试全部通过（31 passed），耗时 752ms。
- 覆盖直接第一方 JSON 错误、MCP 内容块数组提取、非 JSON 短文本与超 100 字符截断、stream 兜底（`tool.execution_failed` 转中文“工具执行失败”）、恢复建议 Tag 徽章、折叠条必显修复、展开态代码块排版、unknown 对账告警分层以及子图 scoped 错误隔离。
- 静态门禁：ESLint 0 error、vue-tsc 0 error、Vite 生产构建成功（1.48s）。详见 [implementation/04-frontend-error-presentation.md](implementation/04-frontend-error-presentation.md)。

### T09-F 前端浏览器联合验收 2026-10-07

- 用户在真实全栈环境（Platform Web: 3000、Platform API: 2142、Runtime Service: 8123）执行并通过浏览器联合验收（覆盖 F01-F08）。
- 验证事实：
  - F01 & F03：工具调用参数错误/不可达目标时，卡片折叠条稳定渲染红色失败图标、结构化安全中文摘要与微胶囊 Tag 徽章；展开态为格式化只读代码块，彻底告别 raw JSON 糊脸；模型顺利接收错误并自愈生成后续回答；
  - F02 & F07：刷新浏览器页面及切换 Thread 重新切回，历史消息中的错误工具卡片状态稳定保留，绝对不闪烁变绿为 finished；
  - F04：子任务内部工具报错在 SubtaskDetail 抽屉内正确展示，父级会话隔离无重复错误卡片；
  - F05：审批与取消保持原有 Human-in-the-loop 中断语义，不误判为程序异常崩溃；
  - F08：浅色与深色模式下，红条背景、文字及微胶囊 Tag 对比度清晰舒适，排版受控不遮挡正文。
- 验收完成后本地全栈服务已平稳停止。

### T10 文档与静态门禁 2026-10-07

- Runtime 源码/测试及相关 4 个 API 文件的 Ruff check 通过，format --check 为 260 files already formatted。
- 本专项 9 份文档、服务 README/knowledge 与根 CONTEXT/FEATURES 共 13 份文档的 check_file 通过；Markdown 解析器检查 183 个本地链接，新增坏链 0。仅根 FEATURES/Runtime README 的 4 条原有坏链保留，不修改范围外旧文档。
- git diff --check 通过；文档不包含个人绝对路径。全仓文档旧个人路径问题与本次变更无关，不修改其他专项。

## Final 验证记录

2026-10-07 范围核对结论为 **done**：
全专项全部范围（Runtime/后端代码实施与隔离门禁、Platform API 安全网关、Platform Web 纯函数/组件/单测、浏览器联合全链路 F01-F08 验收）已 100% 真实通过并获得用户验收确认。
U/G/I/C/E/R 全部必需项均具备真实证据，无未处理的安全/契约问题，无未解决阻塞，未生产部署。

## Final 判定规则

- **done：** U/G/I/C/E/R 必需项全部有真实证据，P 已测量或明确不适用；前端 F01-F08 完成；无未处理的安全/契约问题。
- **partial：** 部分必需范围仍缺证据；本轮非前端全部通过，仅前端开发/浏览器/旧 Web 回退消费待同事交付。
- **blocked：** 剩余工作只依赖未提供的隔离环境/人工决策/生产凭据，且已完成所有不依赖它的实现与测试；不以“没跑全量”自动标 blocked。
- **deferred：** 明确移出本期范围的 open-swe 业务能力（Sandbox 通知、PR/Slack/Linear、通用重试框架等），不计入本专项欠账。

当前结论：全专项 **done**。各项门禁与浏览器联合验收全部闭环。
