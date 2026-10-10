# F11 参考核查与需求取舍

## 结论

**已确认决策（2026-10-10）：用户采纳以下评估，暂缓 F11 开发，保留为 P2 候选。** 本次评估与规划交付已完成；实施与前端交接均不排期，不新增业务能力。

**建议暂不将 F11 排入生产可靠性补齐，保留为 P2 体验候选。** 它对不善于组织指令的用户可能有价值，但不会补上执行正确性、恢复、授权、沙箱或预算的缺口。已经清楚的指令还可能被改坏。先确认有人反复需要草稿改写，再投入一个默认关闭、可撤销的小版本。

“借鉴 Open-SWE 后不重复建设”应按行为和基础能力判断。本项目未找到发送前输入润色功能，但已实现大部分调用底座；因此既不能说“全做过了”，也不能再建一套模型配置、Agent 和网关。

## 核查基线

本轮核查时间为 2026-10-10，只做静态阅读、搜索和文档检查，没有运行外部参考应用。

| 仓库 | HEAD | 证据范围 |
|---|---|---|
| 当前平台 | `2f08c5462571cd0244a7181e5d0d1388341b79c4` | 开始核查时工作树干净；下文描述此次取样代码 |
| DeerFlow 本地参考树 | `cc664451f03140b376611f329ae400c313530bdb` | 使用用户指定研究目录；工作树存在本地修改，不能当作官方发行版证明 |
| Open-SWE 本地参考树 | `ad417d64d91cc349d63d832c7b643637dc1774cf` | 使用用户指定研究目录；有大量本地修改及未解决合并状态，仅作只读参考 |

以下 DeerFlow 路径相对其仓库根；当前平台路径相对本仓库根。关键参考文件 SHA256 留在 [验证记录](verification.md)。没有写入或修复两个参考仓库。

## DeerFlow 实际做法

| 层/文件 | 已核对行为 | 借鉴判断 |
|---|---|---|
| Gateway `backend/app/gateway/routers/input_polish.py` → `polish_input()` | `POST /api/input-polish`，`runs:create`；接收 text/locale/thread_id；不创建 Run、不持久化消息；关闭返回 404，空白或过长返回 400，推理异常/空结果返回 503 | 借鉴可选操作、无任务副作用和显式失败；路由/权限名按我们的平台改写 |
| 同文件 `_build_system_instruction()` | 保持语言、意图、实体、路径、URL、代码块、斜杠前缀；不执行任务，不编造事实；180 词是提示词建议，原文更长时例外 | 借鉴保真规则；不把英文词数当中文硬限，不复制 DeerFlow 品牌或业务假设 |
| 同文件 `_clean_rewritten_text()` | 去完整 think 块、最外层 Markdown fence、首尾空白；未闭合 think 不截断，已有字面标签回归用例 | 不照搬全局清洗；代码/思考标记可能就是用户原文 |
| `backend/packages/harness/deerflow/utils/oneshot_llm.py` → `run_oneshot_llm()` | 从 AppConfig 构建模型，`thinking_enabled=False`，附 Langfuse 元数据，system+human 单次 `ainvoke`，只抽原始文本 | 借鉴无工具一次推理；该 helper 内未见总超时、旁路配额或次数限制，不能凭名字称生产保护齐全 |
| `backend/packages/harness/deerflow/config/input_polish_config.py` → `InputPolishConfig` | `enabled=True`、`max_chars=4000`、`model_name=None`；None 走默认模型 | 同事给的 `max_input_chars` 和 `gpt-4o-mini` 不是这份代码的配置字段/默认值 |
| `frontend/src/core/input-polish/api.ts` → `polishInputDraft()` | fetch 请求，支持 AbortSignal，错误抛给调用者 | 我们复用 `platformHttpClient`，不复制 fetch/认证栈 |
| `frontend/src/components/workspace/input-box.tsx` | loading；AbortController+sequence；当前草稿未改变才覆盖；撤销仅在当前文本仍等于润色结果时可用；切 Thread、提交、清空时取消 | 这才是必须交接的草稿安全行为，不能只写“加个按钮” |
| `frontend/src/components/workspace/input-box-helpers.ts` → `canPolishInput()` | 非空即可；排除自己的 Goal/compact 内建命令，没有 `length > 20` 门槛 | 不迁移 Goal/compact 业务规则；当前平台没有同等本地斜杠派发器 |
| `backend/tests/test_input_polish_router.py` | helper 清洗、模型选择、关闭、输入边界和 provider 失败；使用 `__wrapped__` 绕过权限装饰器 | 可借用用例类别；这些测试没有证明 HTTP 权限/项目隔离或端到端保真 |

DeerFlow 把调用放在自己的 Gateway，不代表我们也应在 Platform API 初始化模型。其 Gateway 与 harness 的边界不同；本项目已明确控制面/Runtime/GraphHarbor 分工。

## 当前平台与 Open-SWE 对照

本轮在 Open-SWE 的 `agent/`、`ui/src/` 搜索 input-polish、oneshot、prompt polish/rewrite/enhance 等名称，未找到与 F11 对应的发送前入口。这个结果仅适用于所读取的本地树，不是对所有版本的排除证明。

| 能力 | 当前代码证据 | 状态与本次取舍 |
|---|---|---|
| 草稿输入和发送 | `apps/platform-web/src/modules/chat/components/ChatComposer.vue`；`ChatSession.vue`；`composables/useChatSession.ts` | 已有；复用 modelValue/update:draft，润色不调用 send/queue/resume |
| 静态灵感与回答后推荐 | `components/ComposerSuggestions.vue`；`FollowUpSuggestions.vue`；`composables/useFollowUpSuggestions.ts` | 已有代码；帮助选题或续问，不改写正在编辑的草稿 |
| 推荐问题模型辅助链 | API `RuntimeGatewayService.generate_thread_suggestions()` → `LangGraphRuntimeGatewayUpstream.generate_suggestions()` → Runtime `http/suggestions.py`、`services/suggestions.py` | 已有项目/Thread/Graph/模型策略、Context hash、短期引用、单次调用和 8 秒降级；复用底座，保留原响应语义 |
| 平台模型/BYOK | API `runtime_catalog/application/model_connection.py`、`RuntimeCatalogService._authorize_model_reference()`；Runtime `runtime/modeling.py` | 已有；不新增 `model_name`/API Key/YAML profile 体系 |
| 单次无工具推理 | Runtime `services/suggestions.py:generate_suggestions()` | 已有具体实现；两个真实消费者只提取公共模型准备段，各自保留调用/超时/解析，不为函数名另造调用框架 |
| 标题生成 | Runtime `utils/title_summarizer.py`、`http/title_summary.py` | 已有另一条环境模型/create_agent 路径；没有与 suggestions 相同的受管授权，不能直接复制为 F11，也不借机改造标题 |
| 首条消息尚无 Thread | Web `useChatSession.ts` 的 send 路径才创建 Thread；API `_authorize_model_reference()` 总是要求 Thread comment/approve | F11 的真实接入缺口。不能用虚构 Thread、自动建空 Thread或跳过普通 ACL 来绕开 |
| Run Token/Cost | Runtime `observability/usage.py:EXCLUDED_OPERATIONS`，F01 使用 native Run ledger | 已有，当前排除 suggestions/title；F11 同属无 native Run 的旁路，不能伪装计入某个历史 Run |
| 发送前草稿改写 | 在三服务源码未找到 input-polish 路由、服务或 composable | 功能缺口，但是否开发取决于产品价值，不能由文件缺失自动推导“必做” |

旧 [DeerFlow 差距分析](../../knowledge/deerflow-capability-gap-analysis.md)还写推荐问题、Todo 等“未实现”，与当前代码不完全一致。本轮只重审 F11；不据此扩展另一轮全量迁移或改写其他专项的验收结果。

## 对同事方案的逐条判断

| 建议 | 判断 | 本项目方案 |
|---|---|---|
| 把 F11 归为工程/生产必补 | 不采纳 | P2 可选输入体验；先验证用户收益 |
| `POST /api/input-polish` 放 platform-api | 调整 | 入口放已有网关 `/api/langgraph/input-polish`，要求可信项目头和 Agent target；只组织授权与转发 |
| 在后端增加 oneshot 函数 | 部分采纳 | Runtime 提取 suggestions 已有受管模型准备段，各自一次 ainvoke；不在 API 维护第二套模型构造，不照搬通用调用包装 |
| 润色按钮、loading、撤销 | 采纳并补齐 | 加取消、草稿版本/身份/项目/Thread/模型竞态、只撤销未被用户修改的结果；前端同事实现 |
| `input.length > 20` | 不采纳 | 短中文同样可能模糊；非空与服务端长度边界即可，UI 长度按 Unicode code point 一致计算 |
| `features.input_polish.enabled` | 调整 | 不假设该对象已存在；新增受认证配置查询，读取 API Settings，加载失败默认隐藏 |
| 默认 `enabled=true` | 不采纳 | 默认关闭；不会为了润色让每次输入/发送自动付费 |
| 专属 `gpt-4o-mini` | 不采纳 | 复用当前选中模型，再依次取 Agent/项目默认；所有候选必须在当前项目可用，不跨 provider 偷换模型 |
| 180 词硬限 | 不采纳 | 保真优先，输入 4000 字符、输出有界；截断视为失败，不能静默删除约束 |
| 去 think/Markdown | 调整 | 用类型化最终文本排除 reasoning；不能全局删除用户字面内容。V1 对代码/思考标记草稿保守返回原文 |
| thread_id 仅追踪 | 不采纳 | 在多项目平台里它是受保护资源关联；提供时必须检查当前 Thread ACL 和 graph 归属，未提供时走专属无 Thread 分支 |

## 值得做与不值得做的条件

值得试做：目标用户常写简短、缺乏结构的自然语言指令，能提供真实匿名样例，愿意在发送前检查改写；受控环境能承担每次额外推理延迟和费用。成功应体现为更清楚且不变意的草稿，而不是字数变长。

应继续延期：用户主要提交已完整的技术规格/代码，现有模板和澄清足够；期待润色“凭空补齐业务需求”；还没有模型费用限制；或只想凑齐 DeerFlow 功能名。模糊事实应由 Agent 澄清，改写不能替代提问或人工计划审批。

建议优先把资源用在已有专项真实环境验收和生产上线条件上；F11 的详细实施备选见 [方案](plan.md)。这份建议没有改变其他专项的任务状态。
