# 01 源码对照、目录地图与分层边界

## 1. 调研范围与证据口径

- 当前仓库：`ai-agent-platform`，以本轮工作区文件为准，已有其他任务的未提交改动未清理。
- 参考仓库：`deer-flow`，本地 HEAD `44ae7505`；结论针对本地源码，不代表上游最新版本或所有后端供应商。
- 检查了源码、既有设计、测试代码及配置声明；未通过用户登录访问真实页面，未检查运行进程实际加载配置，未调用模型或读写实际个人记忆。因此不能断言用户当前页面的唯一故障原因。
- 下面“已实现”表示有执行代码；“待验”表示需要运行证据；“拟新增”是本专项建议，不冒充已有能力。

## 2. Dear Agent 原本预期做成什么

既有依据：`docs/projects/20260913-dearflow-agent/06-context-and-memory.md`、`08-web-and-platform-contracts.md`、`phases/P6-记忆与技能治理.md`、`implementation/13-p6-memory-and-skills.md`、`implementation/19-w4-memory-and-skills-governance.md`。

三种东西必须分开：checkpoint 保存当前线程消息和任务；workspace 保存上传文件、技能及成果资源；长期记忆保存当前用户在当前项目可跨线程使用的稳定偏好和事实。Memory 页面不是聊天历史、知识库、成果文件夹，也不是系统提示词编辑器。

用户应该能完成以下过程：

1. 进入页面即知道“这是我在项目 X 的记忆，仅我使用，同项目新会话可引用”。没有聊天也能新增偏好。
2. 手动记录“默认用简洁中文解释”；刷新、重新登录后仍存在；新建会话能引用。
3. 自愿开启自动候选。在聊天中表达稳定偏好后，看到待确认内容、原文引用、来源会话和时间；采纳前不进入正式记忆上下文。
4. 修正、删除、设到期时间，或清空；看到明确结果。新 run 不再注入已删/到期内容；并发提取不能复活旧内容。
5. 导出有效事实，预览文件后追加导入；明确告知重复和无效条目，不能把“粘贴 JSON”当成完整备份闭环。
6. 区分未启用、自动候选关闭、没有事实、没有搜索结果、提取失败、容量不足和无权限。不能全部显示成“0 条”。

边界：删除长期记忆不会删除历史消息、既有 checkpoint、先前生成的答案，已经发给模型的本次请求也不能撤回。“忘记”承诺指后续记忆读取/注入，不承诺模型无法从仍在场的历史聊天中得知同一内容。

## 3. 当前与 deer-flow 对照

下表参考路径均相对 `deer-flow/`。

| 维度 | deer-flow 本地实现 | 当前平台 | 借鉴与取舍 |
|---|---|---|---|
| 页面入口 | `frontend/src/components/workspace/settings/memory-settings-page.tsx:MemorySettingsPage`，设置页直接加载个人记忆 | `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`，必须先由 composable 找到 Dear 会话 | 借鉴无会话管理；保留项目 scope，不照搬全局语义 |
| 展示内容 | 事实＋工作/个人/关注点、近期/较早/长期背景摘要 | 生效 facts＋未生效 candidates | 首期保留事实/候选两栏；画像摘要不是已有产品验收的必要前置 |
| 来源 | 事实 source 可链接线程；相对时间、分类、置信度 | 后端有 source_thread_id/source_message_id/quote，页面基本只展示 origin 和更新时间 | 展示原文证据和来源；置信度不能代替人工采纳 |
| CRUD | `frontend/src/core/memory/api.ts`、`hooks.ts`；mutation 成功更新缓存 | `memory.service.ts` 已实现 save/delete/clear/accept/reject/settings/restore，带 expected_revision | 复用现成服务，不重建 CRUD 框架；完善失败与竞态处理 |
| 导入导出 | 页面文件选择与确认，`backend/app/gateway/routers/memory.py` 有 export/import；import 覆盖 | 仅文本框追加恢复，没有导出 | 借鉴文件流程；采用追加，不照搬全量覆盖 |
| 状态接口 | gateway `get_memory_config_endpoint/get_memory_status` | graph capability 只有 memory 布尔值；文档有 automatic_candidates，但无可见提取状态 | 返回最小可用状态，不能泄露完整部署配置 |
| 权限 | gateway `_resolve_memory_user_id`，manager/backend 做用户及 agent scope | Platform 项目/线程权限＋签名委托；Runtime tenant/project/user | 保留平台更明确的项目隔离，不复制默认用户回退 |
| 存储 | 默认 DeerMem 的 `core/storage.py` 管理 Markdown 事实、manifest/锁；检索索引可重建 | Runtime 私有 `dear_memory` 三元主键、JSON document、PG advisory transaction lock＋revision | 保留 PG 权威载体；不复制文件迁移及供应商插件层 |
| 提取触发 | `agents/middlewares/memory_middleware.py` → manager.add/aadd → `core/queue.py` 防抖批处理 | `MemoryContextMiddleware.aafter_agent` 在 run 生命周期内 await 模型，最长模型等待 30 秒 | 借鉴来源增量和幂等；不直接复制进程内 Timer 到多 worker |
| 提取输入 | 后端过滤 human/final-AI，更新器有来源、水位和摘要前处理 | 只取最后一个有 ID、字符串内容且无 additional_kwargs 的 HumanMessage，截前 6000 字符 | 补结构化文本、队列消息、来源资格和压缩协作；工具/AI 内容不成为事实依据 |
| 自动写入 | 默认 DeerMem 更新器在 scope/durability/authority 等门通过后写事实/摘要 | 自动只能 propose 候选，accept 才成事实 | 这是有意的产品差异，保留候选审核 |
| 注入与检索 | `core/prompt.py` 排序、Token 预算、标签转义；`core/retrieval.py` 默认 FTS5，中文分词可选 | `MemoryStorage.context` 倒序最多 10 条、4000 字符；`read(query)` 为所有词子串匹配 | 先评估有界词法相关性和旧偏好召回；不先加向量库 |
| 生命周期 | `core/eviction.py` 容量策略，updater 的陈旧审查/合并；queue 清理与关机 flush | 100 facts/100 candidates；到期仅隐藏；sources/deleted_digests 达阈值后所有写入可能失败 | 先修容量和反复操作可靠性；自动删用户事实、热度淘汰后置 |
| 验证 | scope_gate、prompt_injection、queue、user_isolation、search 等细分测试 | 已有 PG/CAS/HTTP/候选测试和 K20 跨会话脚本，页面测试主要 mock | 借鉴负例和生命周期验证，补真实 UI→模型闭环 |

注意：deer-flow 的分类标签也是模型输出。确定性门只能强制标签规则，不证明模型正确理解了语义；我们的来源校验、人工采纳和实际工具权限都不能省略。其后台队列是进程内状态，也不能据此宣称崩溃后可靠恢复。

## 4. 当前问题清单及证据

### 4.1 前端已确认的缺口

证据文件：`apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`、`apps/platform-web/src/modules/dear-agent/composables/useDearGovernanceContext.ts`、`apps/platform-web/src/services/dear-agent/memory.service.ts`。

| 编号 | 事实与影响 | 优先级 |
|---|---|---|
| F01 | 管理数据按 tenant/project/user 存储，页面却显示“关联会话”“依托沙箱绑定”，无会话就要求创建；这是入口与数据归属不一致 | P0 |
| F02 | `fetchMemory` 无 AbortController/请求世代检查；切项目未关闭编辑/恢复弹窗，旧请求可覆盖当前数据，旧草稿可能在新 scope 提交 | P0 |
| F03 | composable 的 `error` 未被页面接收；列线程失败可能变成“没有会话”，读取失败仍可能显示零值/旧数据 | P0 |
| F04 | 请求带 query，本地又过滤 facts；搜索刷新后清空 query 不会自动恢复完整列表；候选不参与搜索，总数可能变成匹配数 | P1 |
| F05 | `handleActionError` 设置冲突提示后调用 `fetchMemory`，后者立即清空 errorMsg，冲突提示会被覆盖；草稿保留不等于用户得到明确指引 | P0 |
| F06 | FactItem 缺少 quote；候选卡不展示原文、分类和来源链接，用户缺乏采纳依据 | P1 |
| F07 | 导入将错误 category 静默变成 preference，text 强制 String；缺少逐项预检、文件选择、重复预览和导出 | P1 |
| F08 | 编辑到期时间先 slice 日期、保存转 UTC，可能改变原有精确时间；需定义日期所在时区和未改时间的保存规则 | P1 |
| F09 | 自制遮罩弹窗主要只有 ESC，未复用现有 BaseDialog/ConfirmDialog；开关无完整 switch 语义；加载时新增按钮仍可能可点而提交无反应 | P1 |
| F10 | 页面直接出现 PostgreSQL、epoch、环境变量名，掩盖用户真正需要知道的生效范围、清空后果和失败原因 | P1 |
| F11 | 页面读 `err.response.data.code`，实际 Platform `build_error_payload` 返回 `error.code`；冲突/未启用等分支可能无法匹配。修复F05前先修这里，测试用真实错误包 | P0 |

### 4.2 Platform 与配置情况

- `RuntimeGatewayService.dear_governance()` 已执行 `_load_thread`、Dear graph 校验、目标许可和签名委托，不是无后端。
- `LangGraphRuntimeGatewayUpstream.dear_governance()` 已转发 Runtime；`sdk_client.py:create_runtime_upstream_error` 已提取内层 detail.code，但公开包由 `core/errors/payload.py:build_error_payload` 包装在 **error.code** 下。页面读取 `err.response.data.code` 是明确的契约错配；不能只修冲突后的提示覆盖而遗漏错误包层级。
- `modules/audit/http_resolution.py` 已将旧 memory GET/POST 映射为 read/write 审计，不应另起审计系统；缺少 save/delete/clear 等动作细分。
- 当前 `.env` 声明 `RUNTIME_DEAR_GOVERNANCE_ENABLED='1'`；所查 `.env.example`、根 stack compose、local-stack 脚本未直接声明该变量。是否通过 env_file 等间接加载必须以部署配置和运行 capability 验证，不能简单认定运行时已关闭。
- `capabilities.py:graph_capabilities()` 暴露 memory 布尔值，但无法区分存储异常和提取关闭；现页面没有用它解释可用性。
- 最新 Skills 管理已用 `/api/langgraph/dear/skills` 无线程入口；其 service/授权流程是仓库内最贴近的复用对象。

### 4.3 Runtime 已确认的缺口与待验证风险

证据根：`apps/runtime-service/src/runtime_service/services/dearflow_agent/`。

| 编号 | 事实与影响 | 处理 |
|---|---|---|
| R01 | `context()` 不接 query，直接取逆序记录；4000 是字符数不是 Token 数；遇到一条放不下就 break，后续较短项也丢失 | 补有限相关性选择、稳定兜底、预算和 skip 行为测试 |
| R02 | JSON 文本直接嵌入 `<user_memory>`，JSON 序列化不会转义 `<`/`>`；恶意结束标签仍可破坏声明的文本边界 | 转义所有用户可控字段；权限仍由真实执行校验，不能靠转义声称防住所有注入 |
| R03 | 候选只有 quote 精确包含校验；scope/durability/authority 主要依赖提示词，没有结构化分类门 | 借鉴分类门；不扩大到自动批准；加入审批/密钥/临时任务负例 |
| R04 | source 只选择一个符合条件的 HumanMessage；多模态文本块、带无害 metadata 的消息、同 run 新到队列消息可能漏提取 | 从已验证消息来源提取有界增量，逐消息幂等；不能直接取消来源限制 |
| R05 | `aafter_agent` 前置 read/extracted 在 try 之外，存储异常可打断 run；模型失败只有 warning，无用户状态、无明确失败重试状态 | 可选提取失败隔离；记录安全错误码和同源有限重试，不吞掉显式 CRUD 错误 |
| R06 | `last_extraction` 内部保存但 read 不返回；没有 pending/failed/no_candidate 区别；提取调用只存最近 usage | 返回精简提取状态，复用 trace/usage 链，不泄露原始提示词 |
| R07 | 过期记录仅在 read 隐藏，仍占 100 条容量；达到 sources 2000 或墓碑 1000 后 `_save` 会阻止普通编辑/删除/settings | 事务内清理过期项；幂等元数据生命周期不能阻止人工 CRUD，也不能简单截断导致旧源复活 |
| R08 | `clear` 实际重置事实、候选、自动候选开关和去重历史并提高 epoch，页面只强调清空事实 | 保留实际语义并写清；验证旧 epoch 晚到结果被拒绝。新用户明确再次表达可形成新候选 |
| R09 | manage_memory 的 source_message_id 传入 tool_call_id；管理页是 explicit-management，不是真实用户消息 ID | 增加 source_kind/source_call_id 语义，不生成虚假消息跳转；保留旧来源显示兼容 |
| R10 | 候选只做精确文本指纹去重，显式 save/restore 未统一去重；相矛盾事实可同时存在 | 确定性重复在同 scope 处理；候选审核允许明确替换一条事实，模型不得自行删除已确认事实 |

既有 `tests/services/dearflow_agent/test_p6_governance.py` 覆盖部分 CAS、隔离、clear 竞争、过期拒绝、容量和 mock 提取。`tests/services/dearflow_agent/skills/platform_batch.py` 的 K20 已有真实模型跨会话用例，但依赖批准/模型/整套技能批次，本轮未运行，不能拿测试代码存在冒充验收。


> 后续详细设计以 [Runtime](02-runtime-implementation.md)、[Platform 与公开契约](03-platform-api-contract.md)、[前端交接](04-frontend-handoff.md)、[分层验证](05-verification-and-delivery.md) 为准。前端由其他同事开发，我们只实施后端/Runtime并交接。

## 5. 两仓目录如何对应

```text
参考：deer-flow/
├── frontend/src/components/workspace/settings/memory-settings-page.tsx  # 用户页面
├── frontend/src/core/memory/{api.ts,hooks.ts,types.ts}                    # 前端请求/缓存/类型
├── backend/app/gateway/routers/memory.py                                # HTTP入口
├── backend/packages/harness/deerflow/agents/
│   ├── middlewares/memory_middleware.py                                # 运行结束时提交更新
│   └── memory/
│       ├── manager.py / tools.py / summarization_hook.py                # 业务入口/工具/压缩前通知
│       └── backends/deermem/
│           ├── deer_mem.py                                             # 默认后端装配
│           └── deermem/core/
│               ├── message_processing.py / updater.py                  # 来源筛选/候选与更新门
│               ├── queue.py                                            # 进程内防抖处理
│               ├── storage.py / retrieval.py                           # 权威文件/派生检索
│               └── prompt.py / eviction.py                             # 注入预算/容量策略
└── backend/tests/test_memory_*.py                                       # 可借鉴的边界测试

我们：ai-agent-platform/
├── apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue
├── apps/platform-web/src/services/dear-agent/memory.service.ts
├── apps/platform-api/src/platform_api/
│   ├── modules/runtime_gateway/{presentation/http.py,application/service.py,application/ports.py}
│   ├── adapters/langgraph/{runtime_gateway_upstream.py,runtime_client.py,sdk_client.py}
│   ├── core/security/tokens.py
│   ├── core/errors/{payload.py,handlers.py}
│   └── modules/audit/http_resolution.py
└── apps/runtime-service/src/runtime_service/
    ├── http/dear_governance.py                                          # 当前旧memory入口
    ├── http/dear_memory.py                                              # 拟新增无线程入口
    ├── services/dearflow_agent/{memory.py,governance_storage.py,agent.py}
    ├── services/dearflow_agent/{middleware/memory.py,tools/memory.py}
    ├── runtime/auth.py
    └── db/migrations/versions/0001_application.py
```

各层更细的测试目录与函数落点见02/03/04；interaction-data-service、GraphHarbor私有表和参考仓源码都不在本次修改范围。

## 6. 建议源码阅读顺序（可交给后续开发直接排查）

1. 我们的 `memory.service.ts:readMemory/changeMemory` → `presentation/http.py:read_dear_governance/write_dear_governance` → `service.py:dear_governance` → `runtime_gateway_upstream.py:dear_governance` → Runtime `dear_governance.py:authorize/read_memory/change_memory` → `MemoryStorage.read/change`。这一条证明当前不是占位接口。
2. Runtime `agent.py` 搜 MemoryContextMiddleware/build_memory_tools → `middleware/memory.py:abefore_agent/awrap_model_call/aafter_agent` → `MemoryStorage.propose/context`。这一条区分“管理页有数据”和“模型确实读到它”。
3. `core/errors/payload.py:build_error_payload` → `DearAgentMemoryPage.vue:handleActionError`，核对最终错误包，不停留在Runtime detail形状。
4. 参考仓先看 `memory-settings-page.tsx` 的来源/文件交互，再看 gateway memory.py，再看 MemoryMiddleware与message_processing/updater/prompt。最后读test_memory_scope_gate和test_memory_prompt_injection，不先复制整个manager抽象。
5. 我们现成 `dear_skills.py:authorize`、`RuntimeGatewayService.dear_skills` 和 `test_runtime_gateway_skills.py:SkillsGatewayTest` 是本项目无线程管理与跨服务测试范式，比直接照搬参考仓网关更贴合。

源码定位命令（在对应仓库运行，开发文档不写命令代理前缀）：

```bash
rg -n 'dear/memory|dear_governance|MemoryContextMiddleware|build_memory_tools' "apps"
rg -n 'create_runtime_delegation_token|dear-governance|dear-skills' "apps/platform-api/src" "apps/runtime-service/src"
rg -n 'def _fact_scope_gate_reason|def filter_messages_for_memory|def _format_fact_line|def memory_flush_hook' "backend/packages/harness/deerflow/agents"
```

前两条在我们仓库；第三条在deer-flow。实现前再次检索全部旧调用者，尤其`skills/platform_batch.py`的K20、旧前端service和HTTP测试矩阵，不能只改页面指向的新入口。

## 7. 分层职责、边界与不做什么

| 工作 | 我们的后端/Runtime | 前端同事 | 联合 |
|---|---|---|---|
| 受信作用域与签名委托 | Platform授权、Runtime复核 | 使用登录态与project header，不传owner | 真实只读/越权验证 |
| canonical facts与候选 | Runtime唯一存储、CAS/epoch/来源/过期 | 展示与提交命令 | 冲突、删除与恢复 |
| 提取和模型注入 | Runtime主Agent链路、模型/预算/trace | 显示返回状态，不调用提取模型 | 新会话确实记住/忘记 |
| API、错误、审计 | Platform公开契约与最小审计 | 正确解析error.code、处理pending/失败 | 对照真实HTTP包 |
| 页面、样式、文件下载上传 | 给契约/fixture/联调支持 | 实现service、组件、文件交互、无障碍 | 浏览器端到端 |

不新增多供应商插件层、第二份记忆库、独立服务、前端状态库或事件总线。画像摘要、语义索引、持久后台提取、跨项目全局偏好后置。当前已有100条上限适合有界全量管理与内存排序，先用质量测试判断是否需要更重检索。

## 8. 任务与核查记录

- [x] 调研既有Dear目标、前后端真实调用、Runtime存储与deer-flow参考实现。
- [x] 补充完整目录、符号映射和公开错误包的事实纠正。
- [x] 明确我们只实施Platform/Runtime，前端交由同事；方案按层拆分。
- [ ] 实施开始前核对参考仓版本、当前工作区差异和运行环境；本轮未验证用户现场页面唯一故障原因。

状态：调研文档完成，业务未实施。首轮旧前端测试记录不是当前链路验收。升级为多专题后，旧plan/tasks只是导航，不再维护另一套实施事实源。
