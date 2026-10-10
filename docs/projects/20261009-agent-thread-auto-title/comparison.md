# F07 源码对照与取舍

> 规划核查基线：2026-10-09（实施前）。下表保留当时缺口；本轮已补齐的内容以 `plan.md`、`tasks.md` 与 `verification.md` 为准。仅 F07 做完整调用链核查，未重审全部 DeerFlow 能力。

## 证据版本

| 项目 | 本地 HEAD | 范围 |
|---|---|---|
| ai-agent-platform | `85d63d87bdf84dabbb963f79e8dd4b2db4432ade` | 本轮开始时工作区干净 |
| deer-flow | `cc664451f03140b376611f329ae400c313530bdb` | 本地参考源码，不代表当前 upstream 最新版 |
| open-swe | `ad417d64d91cc349d63d832c7b643637dc1774cf` | 本地参考源码，不代表当前 upstream 最新版 |

源码入口：

- [DeerFlow TitleMiddleware](../../../../research/deer-flow/backend/packages/harness/deerflow/agents/middlewares/title_middleware.py)、[TitleConfig](../../../../research/deer-flow/backend/packages/harness/deerflow/config/title_config.py)。
- [DeerFlow 前端 threads hooks](../../../../research/deer-flow/frontend/src/core/threads/hooks.ts)、[ThreadTitle](../../../../research/deer-flow/frontend/src/components/workspace/thread-title.tsx)。
- [open-swe thread_title.py](../../../../research/open-swe/agent/thread_title.py)、[server.py](../../../../research/open-swe/agent/server.py)。
- [当前标题 helper](../../../apps/runtime-service/src/runtime_service/utils/title_summarizer.py)、[Runtime HTTP](../../../apps/runtime-service/src/runtime_service/http/title_summary.py)。
- [当前网关用例](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py)、[前端 service](../../../apps/platform-web/src/services/threads/session.service.ts)。

## 三种实现对比

| 维度 | DeerFlow | open-swe | 当前平台 |
|---|---|---|---|
| 触发 | `TitleMiddleware.aafter_model()` | Prepare 阶段调 `schedule_thread_title_generation()` | 首消息本地规则；侧边栏按钮显式提炼 |
| 是否必须等任务完成 | 不必须：首次模型响应即可，包括工具调用响应 | 不必须：可仅凭用户输入生成 | 显式按钮可随时调用；没有自动完成后提炼 |
| 正式标题 | Graph `state.title`，checkpoint/values 承载 | Thread `metadata.title` | Thread `metadata.title` |
| 模型入口 | `create_chat_model(name=...)`；未配模型则本地 fallback | 注入标题模型、structured output、10s timeout | `create_agent` 微型无工具图；从 `DEEPSEEK_PROXY_*` 独立构造模型 |
| 输入选择 | 一个真实 human；取首个 AI；动态提醒过滤、结构化文本规范化 | 过滤动态系统内容；用户输入优先，8,000 字符上限 | 最多前 2 + 最近 6 条；单条截取 200 字符；角色/结构化消息规范化较弱 |
| 无正文附件 | 验证文件名，本地单文件名/多文件计数，不调模型 | 不以该路径为核心设计 | 本地首标题与 HTTP schema 没有同等附件分支 |
| 隐藏模型输出 | `TAG_NOSTREAM`；继承父 tracing，避免重复挂 callbacks | 新 `contextvars.Context()`、空 callbacks、后台 task | 独立 HTTP，不处于主 Run 的图内；无须新 SSE |
| 手动标题保护 | 已有 `state.title` 则跳过；rename 与 state 缓存同步 | `title_seed` eligibility；生成后重读再写 | AI 提炼返回后直接覆盖，无生成期间改名复核 |
| 持久化/前端 | 图更新；前端 updates 中取 title 更新各缓存，组件读 values/缓存 | 写 Thread metadata，列表读取 | API 经 `thread-edit` 写 metadata；前端 HTTP 返回后改本地列表 |

上面的参考链接依赖本机同级 `research/` checkout，未把参考源码复制进平台仓库。平台已经选择 metadata + HTTP 路线，继续沿这条路线补齐最小缺口。

## 同事方案需要修正的地方

| 原提议/表述 | 核查结论 | 处理建议 |
|---|---|---|
| F07 完全未实现 | 首消息规则命名、AI 提炼和持久化均已存在；缺自动触发 | 改为“已有手动链路，自动增量待规划” |
| Graph state 新增 title | 当前列表与改名以 metadata 为事实源 | 不采纳，会产生两个标题及 fork/time-travel 同步问题 |
| `aafter_model` 等于首轮完成 | hook 在每次模型返回后执行，可能随后执行工具/HITL | 自动入口以已确认 Run success + 已落盘最终消息为准 |
| 有至少一个 AIMessage 就足够 | AIMessage 可只有 tool_calls 或 reasoning，最终答案尚未产生 | 不用于证明整轮成功；取最后一条有正文且无待执行工具的根图回答 |
| 从 AIMessage 取 `ORIGINAL_USER_CONTENT_KEY` | DeerFlow `_get_title_user_message()` 读取 human 的 additional_kwargs | 修正；本项目没有该字段时不新增同名兼容协议 |
| 过滤所有 `system_reminder/todo_reminder` | 当前参考版 helper 主要按 dynamic context 标记过滤 | 按本平台真实消息来源处理，不凭名称列表宣称等价 |
| 前端只订阅 values.title | 参考版 `hooks.ts` 还在 updates 中找 title、同步 query caches | 本项目继续 HTTP 返回 + Thread 刷新，不移植 React cache 与第二个流解析器 |
| 直接增加 title.model_name/max_words/max_chars YAML | 本平台有受管模型目录、项目策略、短期模型引用 | 不引入独立 YAML；中文现有 10 字输出规则保留，模型走项目受管配置 |
| no LLM 截取前 50 字符 | 当前初始标题为 40 字，AI helper 上限 10 字 | 保留已发布界面规则；自动失败保留初始标题，避免无理由改长短 |
| PII 脱敏直接复用 | 当前没有同等共享脱敏服务；DeerFlow 本地 fallback 也不自动证明安全 | F05 独立评审，不能为标题复制五套检测器或声称已覆盖 |

官方核对依据：[Middleware lifecycle](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[AgentMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware)。已查询 langchain-docs 与 langchain-reference MCP；官方 hook 语义与本地代码一致。

## 当前真正的缺口

| 缺口 | 直接证据 | 影响 |
|---|---|---|
| 自动触发不存在且曾主动移除 | 旧项目 `tasks.md` Task 2.4 明确清理 `onCompleted` 自动调用；现在两个 Page 只在按钮 handler 调 `summarizeTitle` | 不可简单把旧回调接回去 |
| 模型绕过当前受管路径 | `title_summarizer.py::build_title_summarizer_agent()` 加载 dotenv、直接构建 ChatDeepSeek；不消费项目 model reference | 标题可能走另一供应商/凭据，项目模型禁用与用量策略不能据此保证 |
| 自定义端点授权不足 | `title_summary.py` 仅在 authorization 非空时 authenticate，仅特判 usage-read；没有精确 Thread/Graph/context scope 校验 | 单测证明直接挂载 app 可无 token 返回；真实 Server 外层认证效果本轮未测，不能据此断言公网匿名可达 |
| API 中间读取/生成委托过宽 | `RuntimeGatewayService.summarize_thread_title()` 用 `self._upstream` 读 state 和调用生成，仅最终写操作调用 `_thread_upstream(thread-edit)` | 没有标题专属最小权限 operation；输入/模型未绑定该 Thread/Graph |
| 无明确标题调用 deadline | helper catch provider 异常，但未设总 timeout | 不能用“有 fallback”推导出有界等待 |
| 输出可误用 reasoning | helper 正文为空时把 `reasoning_content` 当标题；对 list content 使用 `str()` | 推理文字/块对象可能进入标题，清洗和截断不能替代正文提取 |
| 手动修改可能被覆盖 | API 获取旧 thread 后等待 LLM，然后直接写 title；无条件更新 | 慢模型响应会覆盖生成期间的用户改名 |
| 自动重复/来源未标识 | 没有 pending seed/完成标识 | 不能仅凭“title 非空”判断：初始规则标题本来就非空 |

### 并发不能照抄参考实现

open-swe 的 seed 和生成后复核值得借鉴，但 `GET -> check -> PATCH` 中间仍有窗口，进程级 `_inflight_thread_ids` 也不保护多实例。

当前 `LangGraphThreadsSdkAdapter._UPDATE_FIELDS` 只有 metadata/ttl。已核对 GraphHarbor `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/ops.py::Threads.patch()`：读取 ORM row 后合并 metadata，没有暴露 expected revision/metadata 的原子条件写入。原生 patch 不等于 CAS，不能在文档中保证“手动改名永不覆盖”。这项必须按 [方案门槛](plan.md#原子写入门槛) 落实。

## 相关能力只复用，不重新立项

| 能力 | 当前事实/入口 | 对本轮的意义 |
|---|---|---|
| 上下文管理、模型稳定性 | `middlewares/conversation_offloading.py`；上下文/模型专项 | 已有工程化路径，不再移植 F03 摘要中间件 |
| 运行准备、重试、预算、超时、停止 | `middlewares/run_prepare.py`、`retry.py`、`execution_budget.py`、`model_call_timeout.py`、`run_control/`；相关专项 | 标题不得重新计时主 Run、占工具预算或阻塞 Stop |
| HTTP 辅助模型调用 | `http/suggestions.py`、`services/suggestions.py`、API `generate_thread_suggestions()` | 借其 scope/model reference/timeout 边界；标题保留自己的业务方法，不新建万能辅助调用框架 |
| Todo/子智能体/Sandbox | DearFlow/Showcase `create_deep_agent` 与官方 TodoListMiddleware；ChatSession 渲染 todos | 基础能力存在；DeerFlow 强制 Todo 完成等额外语义并不等价，另审而非重复基础实现 |
| 搜索、Jina、文档读取 | `services/dearflow_agent/tools/search.py`；`tools/documents.py` | 搜索与 Jina 已有；文档按需读取不等于全量上传转 MD，本轮不改上传体系 |
| 用量/成本 | `observability/usage.py::EXCLUDED_OPERATIONS` 明列 title/suggestions；用量专项 README | 当前总计不含 HTTP 辅助调用，继续如实告知，不伪造 Run ID |
| PII、IM、TUI、输入润色等 | 不属于本轮 F07 完整核查范围 | 本轮不下“全部缺失/都要实现”的结论，不扩展开发任务 |

2026-10-05 的知识差距报告把 Todo、Jina、推荐问题等标成未实现，与当前代码和后续专项并不一致。其约 135 项统计不能作为本次排期依据；本轮仅纠正 F07，并附失效范围提示。
