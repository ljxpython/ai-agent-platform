# F07 最小增量方案

> 状态：2026-10-09 用户已批准 R1-R5，正在实施。新增契约以 tasks.md 与真实验证记录为准，不能把设计描述当作已部署事实。

## 要不要做

建议 **P1 修复现有标题接口的生产边界，P2 再做浏览器自动命名**。会话量多、首消息标题重复或不便检索时，自动命名有价值；若手动提炼已满足使用需求，停在 P1 就足够。

已批准实施 P1 与 P2 后端，前端交同事。本期不增加独立 `TitleMiddleware`、Graph `title` channel、新事件流、标题数据库表、后台任务队列、专用廉价模型编辑页或一套 DeerFlow YAML。

## 三层职责

| 层 | 是否需要补 | 要补什么 | 继续复用 |
|---|---|---|---|
| platform-web（同事） | 待实施 | 新会话显式 opt-in；成功 Run/最终消息双条件；单飞、取消与身份隔离；更新双入口列表 | `useChatSession`、SDK 状态、`createSessionService`、现有改名/提炼按钮 |
| platform-api | P1 必须 | 当前 ACL；受管模型引用；精确委托；输入限制；生成后再次授权；用户命名保护和条件落库 | runtime_gateway use cases、model reference、Thread SDK、标准审计/错误出口 |
| runtime-service | P1 必须 | 严格内部 schema/scope；同一个标题 helper；受管模型一次调用、总 deadline、正文清洗与 fallback | runtime auth/resolver/modeling、已有 helper/cleaner，不进入 Agent 主图 |
| GraphHarbor | 源码已实施，正式发布 B01 | 通用原子 merge 与独立 `/threads/{thread_id}/metadata/cas`；平台只走 HTTP | 原生 Thread metadata 存储 |

## 推荐流程

```text
新 Thread opt-in + 初始规则标题
  -> 正常 Agent Run/SSE（沿用当前路径）
  -> SDK/回查确认 success 且根图最终回答已可用
  -> Web 异步 POST 现有 title/summarize（不 await 在主 send 链上）
  -> API 校验 Thread/Run/seed + 受管模型/精确委托
  -> Runtime 有界 one-shot，返回 candidate/outcome
  -> API 再授权 + metadata CAS
  -> HTTP 返回真实已存标题 -> 更新对应列表，正常 Thread 刷新补偿
```

推荐首期覆盖浏览器发起的新普通会话。隐藏会话切回时可补偿一次；关闭页面、进程退出、Cron/IM/无人值守不保证标题升级，初始规则标题始终可用。若产品要求关闭浏览器也必达，应另评审服务端运行完成触发与持久任务，不把 HTTP best-effort 宣称为可靠后台执行。

## 复用与具体代码位置

| 文件（已有，除注明新增） | 符号/改动 |
|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | 现有 create/update/summarize 路由与 delegation factory；为 summarize 增有界 DTO，现有 URI 保持；title 生成单独识别 operation |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | `create_thread()` 处理 opt-in；`update_thread()` 清 pending seed；`summarize_thread_title()` 统一手动/自动编排，所有 state/read/生成/写入都用正确 scope |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | `summarize_thread_title()` 输出约束与实际消费的 `compare_thread_metadata()` |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | summarize 精确委托与独立 CAS HTTP transport；旧服务 404/405，禁止退回可能忽略条件的普通 PATCH |
| `apps/platform-api/src/platform_api/core/security/tokens.py` | 精确 `title-generate` scope 的签发白名单/必填绑定 |
| `apps/platform-api/src/platform_api/config.py` | 唯一必要 rollout 开关 `title_auto_enabled=False`；不增加模型名 YAML 或 per-Agent 设置面板 |
| `apps/runtime-service/src/runtime_service/runtime/auth.py` | 同步新 operation 的验证；保持无法访问原生 Thread/Run/工具/MCP |
| `apps/runtime-service/src/runtime_service/auth/platform.py` | 通用原生资源拒绝规则核查；新 operation 不加入原生资源允许集合 |
| `apps/runtime-service/src/runtime_service/http/title_summary.py` | mandatory authenticate；校验 tenant/project/thread/assistant/context；有界严格请求/响应，授权失败绝不 fallback 成 200 |
| `apps/runtime-service/src/runtime_service/services/thread_titles.py`（新增） | `generate_thread_title()` 做受管 config/connection 解析、附件校验和一次模型调用；沿现有 service 边界 |
| `apps/runtime-service/src/runtime_service/utils/title_summarizer.py` | 保留文本/标题清洗和 rule fallback；只接收注入的模型，不再读独立 dotenv/构造 proxy；用直接 `ainvoke`，去掉仅供本模块测试使用的微型 Agent wrapper |
| `apps/platform-web/src/services/threads/session.service.ts` | 现有 create/summarizeTitle 扩 opt-in 与模式 DTO，不新增另一个 title service |
| `apps/platform-web/src/modules/chat/composables/useAutomaticThreadTitle.ts`（同事拟新增） | 只负责已知会话的辅助请求；输入既有 Run/终态/可见性，不实现第二套运行状态机 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 最小接线与成功标题事件，不将标题塞入 transcript |
| `apps/platform-web/src/modules/chat/pages/ChatPage.vue`、`apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue` | 共享 title 更新函数/身份守卫；保留两个页面已有的 rename/summarize handlers |

`useDearAgentSession.ts` 已 re-export `useChatSession`，不在那里复制自动逻辑。schema-only 图、各 Agent 组合根、子 Agent state、Graph 注册及 `webapp.py` 的标题 router 挂载均无需为 F07 新增一套接线。

## 实施公开契约

保持 `POST /api/langgraph/threads/{thread_id}/title/summarize` 与 `PATCH /api/langgraph/threads/{thread_id}`。

| 请求 | 语义 |
|---|---|
| `{}` 或现有 `{messages:[{role,content}]}` | `mode=manual`；仍是用户显式提炼，保留现有调用形态 |
| `{ "mode": "auto", "run_id": "<uuid>" }` | 自动补齐；禁止带 messages/model/seed，全部由服务端按已提交状态与项目配置取得 |
| Thread 创建增加可选顶层 `auto_title: true` | 只表达产品 opt-in，不授予权限；仅创建时自动开关已开启才写 seed，不能接受客户端直接写内部 seed |

统一响应保留旧字段，增加有界机器态：

```json
{
  "thread_id": "<uuid>",
  "title": "当前已保存标题",
  "metadata": { "title": "当前已保存标题" },
  "outcome": "applied",
  "reason": null
}
```

- `outcome`：`applied | skipped | degraded`；`reason` 为固定枚举，不返回 provider 原错误，完整集合见前端交接。
- `skipped`：关闭/未 opt-in/非首轮/非 success/未获得完整材料/seed 已清/改名冲突。未获得材料不能伪称已生成，允许后续有效机会补偿。
- `degraded`：模型未配置、超时、provider 失败或无正文输出，返回原有规则标题；完成标识仅在获得合法首轮材料且条件写入成功时清除。
- response.title 必须反映已保存值。CAS 超时/5xx/非法确认统一 `503 title_write_unconfirmed`；前端读 Thread 对账，不能展示未落库 candidate，也不能盲重试。
- 手动 messages 限 1-8 条、单条最多 4,000 字符、总计最多 12,000；只接 user/assistant（human/ai alias 规范化为同一角色）。
- 自动必须校验 Run 属于当前 Thread/Graph、status=success、无活动 Run/未决 interrupt、恰一条真实用户输入及可用最终回答；输入读取不可确认时跳过，不拿空数组覆盖标题。
- 时间旅行/fork/导入/旧 Thread 不自动回填；新普通会话的非空初始规则标题可作为 seed，不能仅凭非空 title 判断它已被用户改名。

## 用户命名与自动幂等

借鉴 open-swe 的 `title_seed`，作为 **服务端内部 metadata 标记**：新普通会话显式 opt-in 且创建时自动开关已开启，才存初始规则标题；成功自动命名或显式改名/手动提炼后清空。创建时开关关闭则没有 seed，之后开启不回填。没有标记的历史 Thread 不自动生成。

自动仅在 `title == title_seed` 且 seed 尚未消费时尝试；生成前后都检查当前 ACL 与 eligibility。手动 PATCH title 即使改回与 seed 相同文字，也要清空 seed，从而防止“改名后又被自动命名”。preview-only PATCH 不清 seed。

客户端 create/patch/state/input 不能注入内部 seed；API 自己的 Thread 创建与通用 metadata 更新出口要过滤它，fork 不继承它。公开 DTO 只暴露 `auto_title_pending` 布尔投影，不暴露 seed 值。单飞只降低单客户端重复成本，不承诺跨实例只付费一次；最终持久化应只有一个自动结果。

### 原子写入门槛

1. 规划基线没有 CAS；本轮在 GraphHarbor 源码新增通用能力，正式 PyPI post43 仍不具备。禁止用“再 GET 一次”或进程 asyncio.Lock 宣称原子。
2. `thread_metadata.py::patch_thread_metadata()` 用单条有条件 PostgreSQL UPDATE 同时比较与合并；`Threads.patch()` 和公开 HTTP 共用。普通 metadata PATCH 也改为原子 merge，防止无关 preview 更新回写旧 title/seed。
3. Platform 只通过已批准接口使用 CAS；不连接 GraphHarbor 数据库、不在 Runtime 自定义路由写引擎 Thread 表、不新增第二份平台 title 表。
4. 条件失败读回当前 Thread，返回 skipped/conflict；手动写先完成则自动失败，自动先完成则之后手动写覆盖自动值。
5. 新入口为 `PATCH /threads/{thread_id}/metadata/cas`，必须提交 `metadata` 与非空 `if_metadata`；只比较列出的顶层键，JSON null 匹配缺失/null。条件失效 409，不可见 404，非法参数 422。普通 PATCH 的缺省/null metadata、ttl-only 与 minimal 204 保持兼容。独立路径让旧引擎明确 404/405，避免静默忽略条件。
6. 双包候选来源/哈希/冷安装与实际链路见验证记录。B01 正式新版本与正式源接入完成前，手动/自动 AI 新版都不能独立发布；人工 rename 仍走普通 PATCH，自动 gate 默认关闭。

## 授权、模型与内容边界

- 标题 AI 操作要求 project runtime execute + Thread comment + edit；人工 rename 沿现有 edit。受管 model reference 复用 `thread_action=comment`，不扩大 catalog 的 action 集合。edit-only AI 拒绝语义已获 R1 批准并写入交接。
- 新 `title-generate` 只绑定当前 tenant/project/thread/assistant/context_hash，并仅访问标题内部端点；`read`、`suggestions-generate`、`usage-read` 等 token 不可代用。read-state 和 metadata-write 仍各自使用原生 read/thread-edit。
- 参考 suggestions 的 `_inject_project_default_model()`、`_validate_run_options()`、`_attach_runtime_model_reference()`、`fetch_model_connection()`、`resolve_runtime_config()`、`build_model()`；使用项目批准的模型，不增加全局 gpt-4o-mini/proxy fallback。
- Runtime 总 deadline 为 8s，包含受管连接取得、模型构造与一次调用；无工具、provider 自动重试关闭。取消/权限/契约异常继续传播，不降级成正常标题。
- 模型只接有界 user/final assistant 正文；排除工具、system、动态提醒、文件正文、宿主路径、URL/base64/块对象字符串化和 reasoning。输出空正文不能读取 `reasoning_content`。
- 附件无用户正文时，在 Runtime 校验本平台 `runtime_file` 引用与文件归属后本地命名；单文件名/多文件计数经过控制字符清洗和长度限制。没有合法文件名时保留原标题。图片仅有 ID 无可读名字时不臆造文件名。无需调用 LLM 或复制 DeerFlow uploaded_files schema。
- 独立 HTTP 辅助调用不进入主 Run/Graph/state；显式非流式与 nostream，无父图 callbacks。辅助 trace 只留安全 correlation/outcome，不把对话或 provider 错误记进日志。
- 不实现 F05 全平台 PII 治理。模型材料与本地 fallback 都可能含个人信息，受管模型并不等于脱敏；若部署政策要求脱敏，这是另一个治理前置，必须先解决，不能声称截断就是脱敏。
- 沿既有 Usage 事实：HTTP title 不计入 native Run/Thread Agent cost。本轮不扩账本，不伪造父 Run；自动化会增加账单，验证记录实际调用数与耗时，辅助 usage 未单独采账，产品文档标明统计范围。

## 发布、回退与规范

API/Runtime/GraphHarbor 以匹配版本发布，前端先完成 manual 新响应兼容；CAS 正式依赖、F01-F10 与联合 Final 通过后再开启 API 自动开关。关闭开关停止新自动请求；已开始请求落库前也复核开关。手动改名继续可用，已有标题、历史消息、checkpoints 不清理。

跨版本发布须保证 API/Runtime 同步支持精确 title scope；不能退回旧无精确授权端点。引擎 CAS 通过新增兼容字段或独立通用接口接入，不改既有无条件更新的客户端签名；回退源码与已验证依赖组合，保留已保存标题。

实施同步 Delegation、API 网关、Runtime 与引擎活规范，明确源码/候选和正式发布边界。不推进 SSE/JWT 原专项的 draft 状态；F07 不新增 SSE 格式。

## 评审清单

| 编号 | 已批准的决定 | 评审建议与边界 |
|---|---|---|
| R1 | 是否补齐现有标题的精确委托、受管模型与新增 comment 授权要求 | 优先批准 P1；有意的拒绝语义变化要记录 |
| R2 | 自动命名收益是否足以排 P2，首期是否接受浏览器 best-effort 范围 | 多会话检索有痛点再做；不要求关页必达 |
| R3 | 是否批准引擎通用 CAS 的外部配套范围与发布 | CAS 缺失时不启用自动；不新建平台 title 库 |
| R4 | 8s/一次调用、正文限额、10 字 LLM 标题、附件保留策略是否合适 | 沿现有中文体验；不新增 words/YAML 配置 |
| R5 | 标题模型能否接收正文/文件名，辅助调用成本暂不入 Agent 合计是否可接受 | 沿现有模型出网政策；强制 PII 另设前置 |

评审状态：R1-R5 已获用户批准（2026-10-09）。本轮实施后端/Runtime/引擎配套并验证；前端由同事实施，外部正式包发布另行执行。
