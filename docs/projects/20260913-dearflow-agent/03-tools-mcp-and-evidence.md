# 03 工具、MCP 与结果证据

## 目标

为研究、数据处理和内容生成提供真实工具；让每次调用受授权、预算和执行边界约束，并能证明输出来自实际执行。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P1 仅基础文件交付工具；P2 搜索／MCP／证据；供应商工具随 P4—P5 的 Skill 依赖补齐。
- **必读前置：** [01 架构](01-architecture-and-boundaries.md)、[02 装配](02-agent-composition-and-modes.md)、[04 文件](04-workspace-sandbox-and-artifacts.md)；[08 C02／C04 与 F2／F4／F5](08-web-and-platform-contracts.md)。
- **输入 → 输出／对接：** 授权工具和已绑定资源 → 标准工具结果、来源证据、ArtifactRef；长任务句柄交 [09](09-background-work-and-scope.md) 管理。
- **当前切片／最近证据：** 2026-09-14 规划第二版；业务未实施，无实施验证记录；本文末尾只记录文档调研情况。
- **下一任务：** P1 提取 03/T-E 中文件交付最小切片；P2 再做 T-A／T-B／T-E 研究能力。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 1. 能力清单与参考代码

以下 DeerFlow 路径相对参考根，完整前缀按表书写；本项目拟新增业务模块都位于 `services/dearflow_agent/`。

| 点 | 具体能力 | DeerFlow 参考代码 | 实现方案／目标文件 |
|---|---|---|---|
| T01 | 多角度联网搜索，带来源与时间 | `backend/packages/harness/deerflow/community/tavily/tools.py`、`community/ddg_search/tools.py`（同 Harness 根） | `apps/runtime-service/src/runtime_service/services/dearflow_agent/search.py:search_web`（拟新增）；首个已批准 provider 用官方 MCP adapter 或已有 HTTP 依赖；不一次装齐所有供应商 |
| T02 | 读取网页正文，保留最终 URL、标题和截断说明 | `backend/packages/harness/deerflow/community/jina_ai/tools.py`、`community/firecrawl/tools.py` | 同文件 `fetch_page`（拟新增），使用 HTTP 抓取／正文提取；不引入 Playwright、浏览器会话或截图工具 |
| T03 | GitHub 与 arXiv 元数据 | `skills/public/github-deep-research/scripts/github_api.py:GitHubAPI`、`skills/public/systematic-literature-review/scripts/arxiv_search.py:search` | 保留纯解析、查询和分页逻辑；请求走受控服务工具，凭据不进入通用 Shell；详见 07 的 K03／K05 |
| T04 | 文档解析与统计执行 | `skills/public/data-analysis/scripts/analyze.py:load_files/action_query` | 04 的格式／沙箱基础＋K08；通用读取复用 `runtime_service.tools.documents`，业务 SQL 执行留在技能沙箱 |
| T05 | 图片生成、编辑与理解 | `skills/public/image-generation/scripts/generate.py:generate_image`、`backend/packages/harness/deerflow/tools/builtins/view_image_tool.py` | 复用 `apps/runtime-service/src/runtime_service/tools/images.py:build_image_tools` 和图片 Middleware；按需求补多参考图、尺寸和输出格式，不能由技能另行直连绕过审批 |
| T06 | 图表与电子表格 | `skills/public/chart-visualization/scripts/generate.js` 及 `references/` | 拟新增 `apps/runtime-service/src/runtime_service/services/dearflow_agent/chart.py`；借鉴现有官方 AntV MCP 接入，核对 26 类而非只验证柱状图；输出全部走 ArtifactRef |
| T07 | 视频、语音与音乐生成 | `skills/public/video-generation/scripts/generate.py`、`podcast-generation/scripts/generate.py`、`music-generation/scripts/generate.py` | 拟新增 `apps/runtime-service/src/runtime_service/services/dearflow_agent/media.py`；供应商请求为受控工具，远端任务句柄按 09 持久化；纯音频混合可在沙箱运行 |
| T08 | MCP 会话与工具装配 | `backend/packages/harness/deerflow/mcp/tools.py`、`mcp/cache.py` | 拟新增 `apps/runtime-service/src/runtime_service/services/dearflow_agent/mcp_tools.py:load_mcp_tools`；官方 `MultiServerMCPClient`／转换器／interceptor；复用现有 resource binding 规则，不 import `mcp_demo.loader` |
| T09 | MCP 工具发现与按需暴露 | `backend/packages/harness/deerflow/tools/builtins/tool_search.py:assemble_deferred_tools`、`agents/middlewares/deferred_tool_filter_middleware.py` | 先只装本阶段必要工具；规模达到 schema 预算后再接官方匹配能力或一个最小 discovery tool；授权筛选先于目录展示，发现工具不授予执行权限 |
| T10 | 工具错误、超时与输出预算 | `backend/packages/harness/deerflow/agents/middlewares/tool_error_handling_middleware.py:ToolErrorHandlingMiddleware`、`tool_output_budget_middleware.py:ToolOutputBudgetMiddleware`（同 middlewares 目录） | 先用官方 ToolNode／Filesystem／摘要行为和现有 timeout；仅补确实缺失的语义，拟新增服务内 `middleware.py` |
| T11 | 可验证执行证据 | `backend/packages/harness/deerflow/agents/middlewares/tool_receipt_middleware.py`、`receipt_verification.py`、`subagents/acceptance_checks.py` | 拟新增服务内 `evidence.py:validate_evidence`，证据由工具边界产生、通过 `ToolMessage.artifact` 传递，关联标准调用 ID |
| T12 | 文件交付 | `backend/packages/harness/deerflow/tools/builtins/present_file_tool.py:present_file_tool` | 服务内 `tools.py:present_artifacts`（拟新增）检查真实文件、归属、大小和 hash；返回 04 的标准产物引用 |

### 2. 工具授权与资源绑定

有效工具集为：代码已实现 ∩ 服务已启用 ∩ 平台当前授权 ∩ 角色 allowlist ∩ 模式限制。Skills 的 `allowed-tools` 最多进一步收窄，不增加任何权限；缺失声明的敏感技能不得默认获得全部工具。

参考现有 `apps/runtime-service/src/runtime_service/runtime/resource_bindings.py:resolve_resource_binding`、`middlewares/runtime_config.py:RuntimeConfigMiddleware`。现有图片内部工具不受 `context.tools` 控制的行为需要在本项目治理评审中明确改为统一可审计策略：内部固定工具仍须检查角色与副作用权限，不能因为工具来自 Middleware 就绕过限制。旧 Agent 的权限差异先记录并迁移，不直接放开全仓库。

- 工具目录对未知名、重复名、越权名拒绝；不使用 DeerFlow 的“同名按顺序保留第一个”容错。
- MCP URL、命令、headers、模型连接与服务密钥只由服务端绑定。客户端只能选择已授权逻辑能力；不能上传模块路径或命令来注册工具。
- 研究类网络工具与通用执行 Shell 分开：Shell 默认无网络、无凭据；受控工具可访问经策略批准的外部站点。
- SSRF 校验覆盖 DNS 解析、私网／环回／metadata 地址、重定向和下载 URL；响应有大小与超时限制。HTML／工具输出视为不可信数据，不能变成系统权限指令。
- 上传、生成、部署等副作用的审批仅确认本次操作，不能授权后续任意请求。

### 3. 会话、失败与副作用语义

MCP 初始化只在真实运行／需要时发生；Schema 探测从已验证的固定 schema 或安全目录快照读取。会话按项目、用户授权及线程需要绑定，资源关闭由 Runtime 生命周期管理；退出、超时、取消必须释放会话。

搜索／读取可对短暂错误做有界重试；付费生成、发布和未知提交结果不盲重试。若供应商支持幂等键，用服务端稳定键；不支持时先查任务／结果，无法确认则显示 `unknown` 并保留恢复操作，禁止生成“成功”文件名充数。

工具错误转为标准失败 ToolMessage，但必须保留 LangGraph interrupt／GraphBubbleUp／任务取消等控制信号。大结果保存到线程私有中间文件，只给模型有界预览、是否截断与读取路径；落盘失败要明确报错，不能把失败的外置化描述为完整结果。

### 4. 结果证据协议（拟定）

`ExecutionEvidence` 拟定义在 `apps/runtime-service/src/runtime_service/services/dearflow_agent/schemas.py`：

| 字段 | 来源与含义 |
|---|---|
| `evidence_id`、`tool_call_id` | 服务端稳定生成／官方调用 ID；模型不能自行覆盖 |
| `thread_id`、`run_id`、`namespace` | 受信运行环境；支持重连与父子归属 |
| `kind` | `source`／`file`／`command`／`provider_result`，表示证据种类 |
| `source_url` 或 `artifact_id` | 实际最终 URL 或经验证产物引用；无内部绝对路径 |
| `exit_code`、`observed_at`、`content_hash` | 能采集时由工具真实记录；不存在就留空，不造数据 |

不将全部 stdout、网页全文、密钥或完整模型请求塞进证据对象。标准工具调用记录已覆盖的字段直接复用；只新增验证业务所需的少量引用。

主 Agent 汇总必须区分已验证／部分验证／无法验证。`exit_code=0` 只能证明命令成功退出，不能自动证明业务验收成立；真正的报表数值、文件格式、引用内容由确定性检查或人工验收验证。子 Agent 自称成功不等于证据。

## 任务拆分

- [ ] T-A：实现 T01／T02，`test_search.py` 覆盖响应解析、来源、超时、重定向和 SSRF；至少一次真实检索链路。
- [ ] T-B：实现 T08，`test_mcp_tools.py` 覆盖探测无 I/O、工具冲突、授权、会话关闭、断线和 scope；T09 只有 schema 预算证明必要才实施。
- [ ] T-C：统一图片、图表和文件返回契约；生产业务不 import Showcase；相关共享修改补旧能力回归。
- [ ] T-D：T07 随 K14—K16 逐个供应商接入；`test_media.py` 覆盖真实错误和 unknown，付费 smoke 显式开启。
- [ ] T-E：实现 T10—T12，`test_evidence.py` 检查伪造文件、错误 hash、无证据成功、截断／外置失败。
- [ ] T-F：将服务端工具能力和权限映射同步到 08 的 catalog，不在前端维护平行列表。

所有拟新增测试完整根目录为 `apps/runtime-service/tests/services/dearflow_agent/`。

## 验证要求与记录

- [ ] 真实搜索→抓取→引用报告；不同线程相同 tool_call_id 不串证据。
- [ ] MCP schema 与实际工具一致；非法 URL／工具／凭据注入被拒绝。
- [ ] 付费调用不因断流或重连重复提交，拒绝审批不触达供应商。
- [ ] 缺少凭据或 provider 未启用时明确 unavailable，不默默返回示例数据。
- [ ] 错误与取消不吞，证据正文按需读取，日志与 tracing 脱敏。
- 2026-09-13：参考源码和现有工具已核对，功能验证未执行。

## 状态

规划中。T01／T02／T08／T10—T12 是研究闭环基础；生成工具跟随 Skill 顺序，不一次性装齐供应商。
