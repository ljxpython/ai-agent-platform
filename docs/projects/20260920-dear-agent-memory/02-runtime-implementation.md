# 02 Runtime：存储、提取、召回与内部接口实施

## 目标与责任

**负责人：后端/Runtime 开发者。状态：部分实施；准确进度以 [tasks.md](tasks.md) 为准。** 本文保留目标方案，标为“拟增”的段落是原实施定位，不代表当前仍缺代码。

保留 Runtime 对记忆的唯一所有权，修复现有行为，再提供供 Platform 调用的无线程管理接口。前端只能通过 Platform 访问，不持有 Runtime 委托密钥。

阅读依赖：[01 源码与边界](01-source-and-boundaries.md) → 本篇 → [03 公开契约](03-platform-api-contract.md)。函数名标为“拟增”时为实施定位，不是已有可导入 API。

## 1. 当前目录与目标改动

根目录：`apps/runtime-service/`。

```text
src/runtime_service/
├── webapp.py                         # 已有；注册新的 memory router
├── auth/platform.py                  # 已有；复用 authenticate，不另造认证
├── runtime/auth.py                   # 已有；修改 _parse_scope 的 operation 白名单
├── http/
│   ├── dear_governance.py             # 已有；旧线程入口及 call，被 dear_skills 引用
│   ├── dear_memory.py                 # 已新增；无线程 GET/POST 和 MemoryView 响应适配
│   └── dear_skills.py                 # 已有；只作为无线程授权范式参考
├── services/dearflow_agent/
│   ├── memory.py                     # 已有；命令、事实、唯一存储，主要业务改这里
│   ├── governance_storage.py         # 已有；scope 锁与连接，保持共享语义
│   ├── agent.py                      # 已有；组合顺序和开关
│   ├── capabilities.py               # 已有；保持 graph memory 布尔兼容
│   ├── middleware/memory.py          # 已有；捕获、提取、注入、状态
│   └── tools/memory.py               # 已有；search_memory/manage_memory 共用业务
├── middlewares/message_queue.py      # 已有；必要时补受信 sender 元数据，不能改成提取队列
├── messaging/inbox.py                # 已有；只复用已授权消息来源，不挪用表作提取任务
└── db/
    ├── __init__.py                   # 已有；connect/upgrade，Runtime 独立迁移链
    └── migrations/versions/0001_application.py  # 已发布基线，不编辑
tests/
├── services/dearflow_agent/test_p6_governance.py  # 已有 PG/CAS 基线，扩展
├── services/dearflow_agent/test_memory_contract.py    # 已新增；输入、召回与 HTTP 契约
├── services/dearflow_agent/test_memory_access.py      # 已新增；共享 ACL 回调
├── services/dearflow_agent/test_p6_governance.py      # 已扩展；隔离 PG、CAS、提取状态
└── runtime/test_auth.py               # 已有；新增 operation 正反例
```

新路由单独放 `http/dear_memory.py`，是因为旧 `dear_governance.call` 被 Skills 复用。不要为了改 memory 顺手删除共享文件。无需新 repository/service/provider 层，`MemoryStorage` 继续承接所有事实变更。

## 2. deer-flow 借鉴到哪个函数

参考根：`deer-flow/`。

| 参考文件/符号 | 阅读内容 | 我们的落点 | 必须保留的差异 |
|---|---|---|---|
| `backend/packages/harness/deerflow/agents/memory/backends/deermem/deermem/core/message_processing.py:extract_message_text/filter_messages_for_memory` | 文本块提取、隐藏框架消息、上传引用过滤 | `middleware/memory.py` 拟增 `_eligible_sources` | 不把 AI 最终回答当事实来源；澄清答案须走本项目真实验证链 |
| 同根 `core/updater.py:_fact_scope_gate_reason` | 标签缺失/非 user/非 durable/非 descriptive 逐项拒绝 | `Candidate` 与 `MemoryStorage.propose` | 标签是模型分类，不是实际身份；仍需 quote 和人工采纳 |
| 同根 `core/prompt.py:_format_fact_line/_select_fact_lines` | 用户文字转义、预算内选条目 | `MemoryStorage.context` | 不照搬 confidence 排序；保留个人项目 scope |
| 同根 `core/storage.py:FileMemoryStorage.apply_changes` | 一批变更的原子性与 revision | `MemoryStorage.change/_save` | 使用已有 PG 事务锁，不复制文件锁/Markdown 迁移 |
| 同根 `core/queue.py` 的 `add_nowait/flush_sync` | 合并与关机生命周期 | 提取失败/取消测试和后置方案 | 不复制进程内 Timer；本期不承诺后台恢复 |
| `backend/packages/harness/deerflow/agents/memory/summarization_hook.py:memory_flush_hook` | 压缩前保留源消息 | `abefore_agent/abefore_model` 的源快照 | 这是 deer-flow 私有钩子，不是官方 Deep Agents API |
| `backend/tests/test_memory_scope_gate.py:test_paired_removal_is_atomic_when_replacement_is_persisted` | 替换原子性 | accept+replace_fact_id 测试 | 替换由用户指定，不接受模型自行移除 |
| `backend/tests/test_memory_prompt_injection.py:test_format_memory_respects_budget_when_adding_facts` | 预算断言 | `test_memory_context.py` | 检查完整序列化块及真实权限，不只字符串长度 |

## 3. 数据与事务怎么写

### 3.1 已有权威结构

`dear_memory`：tenant_id/project_id/user_id 三元键，document JSON。`MemoryStorage._load()` 在事务内拿 `pg_advisory_xact_lock`；`_save()` 写 JSON 并增加 document revision。`FactInput` 目前 text 1—1000 字符、category=preference/fact、AwareDatetime expires_at。

scope 始终取受信 principal，禁止从命令 body、模型参数、来源记录推断当前身份。thread_id 是来源，不加入记忆主键。

### 3.2 推荐新增的内部字段

下列是设计草案；旧 JSON 在读取时补默认值，不做全库启动回填，不增加新表。

| 位置 | 字段/默认值 | 写入者与规则 |
|---|---|---|
| fact/candidate | `source_kind`，旧数据根据已知来源映射，否则 `legacy` | Runtime 写入；`management/user_message/tool/legacy` |
| fact/candidate | `source_call_id=null` | 工具路径写 tool_call_id；不再冒充用户 message ID |
| candidate | `quote` | 真实源原文子串；正式采纳后保留，用户编辑正文后清空过时 quote |
| document | `extraction_status=null` | 最后一次提取的观测状态，带 run_id、source_thread_id、epoch、时间、计数、安全 error_code |
| document | `automatic_pause_reason=null` | 幂等元数据满时设 `source_limit`/`tombstone_limit`；影响提取，不禁止人工编辑 |
| checkpoint 私有 state | `dear_memory_sources=[]` | 当前 run 的有界源快照，不能允许浏览器直接注入 |

保留旧 `sources` 的已处理摘要 ID 列表，旧 `deleted_digests`、revision、epoch 不丢失。来源 ID 构造继续使用 thread_id+message_id；任何演进不得让升级前已处理源重新变成未处理。实际升级时对 `last_extraction` 到新状态做兼容映射，无法确定成功语义则显示 unknown/never，不伪造重试历史。

**公开 response 与内部 document 分开。** 不能直接返回 `doc`；`sources/deleted_digests/内部源快照` 不出 Runtime。公开 envelope 以 03 为唯一事实源。

### 3.3 命令处理顺序（伪代码，不是本轮实现）

```text
change(scope, command, source):
  验证 action 对应字段；拒绝无关字段、伪造来源、布尔 revision、非有限日期
  begin → 获取当前 scope 的事务锁 → load document
  expected_revision != document.revision → 409，无写入
  构造当前有效 facts/candidates 工作集；不在 GET 中偷偷改 revision
  执行一个 action，验证目标属于当前文档、重复、有效容量
  根据 action 决定 epoch 和管理 revision 是否变化
  写入整个 document，一次提交；返回本次提交的文档快照和 mutation 结果
```

禁止 commit 后重新 `read()` 把他人的后续写入误当成本次响应。事务内生成 snapshot，提交成功后再返回；读不到提交结果不显示“成功”。网络超时结果不确定时，客户端重新 GET 核对，不自动重复 POST。

| action | 主行为 | epoch / revision |
|---|---|---|
| save 新增/编辑 | text 先 strip 再校验；编辑保持 id/created_at；明确来源为 management 或 tool | 实质变化时两者 +1；完全相同 no-op 不增 |
| delete | 只能删已有 fact；记录删除指纹，清理过期数据不等于删除历史消息 | 两者 +1 |
| accept | 移候选到 facts，origin=confirmed；可选 replace_fact_id 原子删除目标并记录旧指纹 | revision +1；替换时 epoch +1，纯采纳不必取消其他提取 |
| reject | 删除候选并记指纹 | 两者 +1 |
| settings | 更新 automatic_candidates；关闭后禁止旧提取写入；值没变则 no-op | 实质变化时两者 +1 |
| restore | 1—100 FactInput，全部先校验，规范化重复跳过；不足容量整批失败 | 有新增时两者 +1；全重复不增 |
| clear | 清 facts/candidates/历史去重，关闭自动候选，清维护原因，epoch 保持单调 | 两者 +1，revision 绝不归零 |

重复键建议沿用 fingerprint(text)，**仅相同规范化文本**判重复；分类/到期不一致时不偷偷覆盖，新增返回 `memory_duplicate_fact`，显式编辑可改当前同 ID。restore 重复一律跳过并回报，不能借导入改已有项；同批重复也计入 skipped。

### 3.4 容量与耗尽

- 用户可见有效 facts ≤100、candidates ≤100；到期隐藏与写入容量计算必须一致。写事务清理过期实体，不因读请求自动增加 revision。
- sources ≤2000、deleted_digests ≤1000 是内部安全限额，不是人工 CRUD 的总开关。达到限额暂停自动提取并给出 maintenance 状态，不能从列表头直接丢幂等信息。
- 无剩余墓碑位置但用户要求删除/替换：先提升 epoch、关闭自动候选并标维护原因，再允许人工修改；不能将“无法记墓碑”变成禁止用户删除自己的数据。settings 开启时若维护原因未解除，返回 `memory_maintenance_required`。
- 待收口的维护提案：“导出有效事实→确认 clear→restore→显式重新开启”会丢失旧候选、来源去重与删除指纹，不属于无损维护，2026-09-24 用户确认未批准该维护流程。实施该部分前须冻结重置语义并验证旧源不重放；此前仅承诺满额暂停自动提取、人工管理仍可用，不承诺一键恢复。
- 到期候选不能采纳。一个与过期记录同文本的新明确输入是否可记住，按当前有效集合去重；历史用户主动拒绝/删除的指纹仍优先抑制自动候选。

## 4. 内部 HTTP 与工具怎么接

已新增 `http/dear_memory.py`：`authorize()`、`read_memory()`、`change_memory()`。使用 FastAPI、Pydantic、既有 authenticate/call 模式，不创建独立服务进程。

```text
GET /internal/dear/memory
  authenticate → 要求 operation=dear-memory-read、assistant=dearflow_agent、thread=null
  校验 scope tenant/project 与 principal 一致且 principal user 存在
  开关关闭 → 返回 disabled envelope（document=null），不查 PG
  开关开启 → asyncio.to_thread(MemoryStorage.read_management, scope)

POST /internal/dear/memory
  authenticate → 要求 dear-memory-write，身份约束同上
  开关关闭 → 409 dear_governance_disabled
  校验 MemoryCommand → change(scope, command, source_kind=management)
```

`runtime/auth.py` 和 Platform `core/security/tokens.py` **已确认都有 operation 白名单，两个文件都必须改**。新 operation 不能用于旧线程路由，旧 dear-governance-* 也不能用于新路由；测试交叉拒绝。

`tools/memory.py`：search_memory 仍可返回面向模型的有界文档与 revision；manage_memory 复用 change，保留权限/HITL，不能调用公开 Platform 接口绕一圈。治理开关在 agent 装配和执行工具边界均校验，避免仅从可用列表隐藏但可被直接调用。

旧 `http/dear_governance.py` 过渡保持线程认证、查询参数和原响应形状。共享底层命令可新加字段，但不把新 envelope 强塞给旧页面。旧路由下线依赖前端同事切换完成，不能由后端开发结束就删除。

## 5. 真实来源、提取与执行顺序

### 5.1 来源可信度先于模型

`HumanMessage` 类型本身不足以证明实际作者；公开输入规范化与队列授权链必须共同成立。

**2026-09-24 已确认的共享会话限制：** 共享会话不自动注入个人记忆、不暴露或执行记忆工具（包括查询与管理）、不自动提取候选。不能仅隐藏工具名称，执行入口也必须拒绝；不能只关提取而继续注入。无线程管理接口仍允许用户管理本人记忆。Thread owner、执行用户、队列发送者不能互相替代；分享或takeover不授予读取原owner记忆的权限。

实现前需明确 Platform 的权威 Thread ACL 如何通过受信上下文传递给 Runtime；不能信任客户端提交的 shared/private 标记，也不能因未知状态而默认允许记忆。运行中分享、撤销分享及resume时的重新判定是待完成的工程设计和验证项。私有会话后续被分享会暴露其历史回答，不承诺清除回答中已生成的个人信息。

- 普通 run：源 ID 来自已接受输入中的用户消息；拒绝客户端伪造 memory 私有 state、隐藏系统标记或来源 user_id。
- 消息队列：`MessageQueueMiddleware.abefore_model` 验证授权后，目前输出 HumanMessage 只带 id/content。若允许其他参与者向线程追加，不能把该参与者的“我喜欢…”写到 run owner 的个人记忆。**必须核对受信 sender_id；没有可靠作者证明则跳过自动候选。** 必要时在 private state 中携带 ID→sender 映射，不能把公共 additional_kwargs 当可信凭据。
- 字符串或标准 text block 提取文本；图片、附件 URI、工具结果跳过。不要把任意 dict 的 text 字段都当用户正文。
- 澄清回复只有在本项目已验证为真实用户答复时可纳入；deer-flow 的 human_input_response 结构不能直接搬作本项目认证证据。

### 5.2 源快照与压缩

锁文件当前为 deepagents 0.7.8、langchain 1.3.17、langchain-core 1.6.0、langgraph 1.2.11，实施前与安装环境核对。

已通过 langchain-docs/langchain-reference 查询确认官方 AgentMiddleware 有 abefore_agent/abefore_model/awrap_model_call/aafter_agent；Deep Agents ≥0.7 支持按同名替换默认 middleware，但**并没有因此证明 deer-flow 的 memory_flush_hook 可直接使用**。

推荐实现：abefore_agent 捕获当前 run 的合格用户输入；abefore_model 在已授权队列注入之后捕获新增消息；源快照以独立 private state 留存，摘要可以移除 messages 中旧正文但不应删除这个有界快照。必须用锁定版本的实际 middleware 顺序测试证明捕获早于源丢失；不允许仅凭自定义列表顺序猜测默认 summarizer 顺序。

每 run 最多 20 条合格源、总文本 6000 字符，确定顺序为当前 run 内的新消息顺序，超过预算标 `source_budget_exceeded`，不标“已处理”。原文截断后 quote 只能引用保留部分；UI 用 skipped 状态说明，本期不无限补读全历史。cancel/新 run 时清理不属于本 run 的暂存，resume 保留当前 run 的快照和幂等键。

官方依据：

- https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware
- https://docs.langchain.com/oss/python/deepagents/customization#override-a-default-middleware-instance

### 5.3 提取有界执行

先检查开关、maintenance、epoch、已处理 source key，再调用当前平台解析出的 model 的结构化输出。候选含 text/category/quote/source_message_id 及 scope/durability/authority。由服务把 source_message_id 绑定到本轮合格源，不接受模型自造原文或 owner。

整个 run 最多 5 条候选；模型最多两次尝试、共用一个 180 秒 deadline，第二次只在剩余预算内针对可重试传输错误，解析/标签拒绝不无脑重试。预算覆盖等待和重试间隔，不是每次180秒；首次耗尽预算时不再发起第二次。模型调用不占 PG 事务。取消向上抛出，不能被 `except Exception` 变成成功。用户接受该处理延迟run最终完成状态；180秒不包含主对话模型执行时间，也不等于整个run或HTTP请求的总超时。

原始当前实现的 read/extracted 在 try 之外，需要把**可选提取链**的存储与模型错误都转换为安全状态；显式 CRUD 错误仍必须向调用者报告。若 PG 不可写，失败状态也可能持久化不了，只能记不含正文的 trace；UI GET 应显示存储错误，不能承诺所有失败一定有状态记录。

propose 提交时重读 epoch/开关/指纹；候选 ID 由服务生成。旧任务被取消/清空后不可更新新的 extraction 状态。观测状态按 epoch+run_id+source 标识比较再更新，防止旧失败覆盖新成功。跨 worker 可能重复调用模型，但唯一源提交和 scope 锁必须保证不重复生效；本期不宣称模型调用 exactly-once。

`running` 状态要有 expires_at；deadline 过去但进程已死时 GET 投影为 interrupted，不能永远显示推断中。其有效期应与180秒模型预算及有界存储收尾一致，具体收尾上限在实现时冻结。不启动后台轮询修复worker；失败后显示failed/interrupted，不承诺跨run自动补偿，新run不自动重放旧失败源。用户再次明确表达产生的新消息可作为新源；同一run恢复执行也不得重置次数和预算。

## 6. 召回、预算与注入怎么写

自动召回遇到存储故障时，本次模型调用不注入个人记忆，记录不含正文的降级原因，普通对话继续。前置的可选记忆读取同样隔离存储异常，不能在进入模型前打断普通对话。显式 `search_memory/manage_memory` 与管理HTTP请求仍返回明确错误，不能将异常转换为空列表或成功。只处理存储故障，不吞掉取消或授权拒绝；共享会话应先被记忆策略门拦截。

拟修改签名：`MemoryStorage.context(scope, query="")`，返回内部选中 facts 与观测元数据，再由 middleware 序列化注入。现有 search_memory(query) 的所有词子串查询可继续用于显式查找，不必强制与上下文排序同一种语义。

推荐首版确定性规则（需 Q01 测量后冻结）：

1. 只取有效、已确认事实；最多 100 条内存扫描。
2. query casefold；英文/数字词按正则提取，连续中文取相邻双字词；去掉明显标点，不加分词依赖。
3. 相关性按命中不同 query token 数排序，相同分按 updated_at、id 稳定排序；取最多 7 条命中项。
4. 追加最多 3 条尚未选中的 preference，按更新时间倒序；query 空或无命中时最多 10 条有效项作明确 fallback。
5. 序列化转义后最多 10 条、4000 字符，并设离线保守 Token 估算上限；建议 2000 estimated tokens，UI 不将估算显示为计费值。过大项跳过继续，空预算则不注入。阈值以质量测试结果修订，不假称已达标。

不新增在线 tokenizer 下载。已有 SDK 计数 API 是否能完全离线，实施时先验证；否则使用明确标注误差的离线估算。所有来源字段同样转义 `< > &`，包含块边界、身份说明的完整注入开销计入预算。

删除后正在进行的模型请求无法撤回；只保证下一次读取/模型调用使用最新有效事实。不得因缓存全 run 记忆导致用户删除后后续工具轮继续沿用；若要缓存必须按 revision 失效，首期直接复用有界读取。

## 7. 任务拆分与逐项测试

| 任务 | 开发内容 | 测试入口/验收 |
|---|---|---|
| [x] R01 | 旧 document 默认值、公开投影、内部状态 | 旧数据 fixture 读不丢字段；公开输出无 sources/墓碑 |
| [x] R02 | command 严格字段、事务 snapshot、CAS/去重/替换 | test_p6_governance：双连接同 revision 仅一个写入、非法批次全回滚 |
| [x] R03 | 到期、配额、维护/清空 | 容量边界不锁死人工删除；clear 单调 epoch；旧源晚到拒绝 |
| [x] R04 | 新路由、operation 白名单、旧路由适配 | test_memory_contract/test_auth：委托、operation、开关、真实 HTTP/PG |
| [x] R05 | 用户来源捕获、队列作者、摘要协作 | test_context/test_memory_contract/test_p6_governance：真实 sender、交付状态、同 run 多源与摘要后快照 |
| [x] R06 | 提取门、deadline、失败、usage 状态 | 可控模型两次内结束、取消传播、并发 run 状态归属、独立真实模型提取 |
| [x] R07 | query 排序、预算、转义 | 固定 10 正/10 负召回样本、预算/转义、真实模型合成事实问答 |
| [~] R08 | 工具/权限一致与真实新线程模型验证 | 独立 memory E2E：工具拒绝不写入，新会话使用已确认事实 |

## 验证记录与状态

2026-09-24 已实施无线程接口、命令与事务、受信共享检查、多条本人队列来源、有界提取和词法召回；相关代码与测试见 [阶段一](implementation/01-backend-memory.md)和[阶段二](implementation/02-source-and-model.md)。R08 的平台完整 run/SSE 分享竞态仍未验证。进度只看 [tasks.md](tasks.md)；执行结果记入 [verification.md](verification.md) 的 Phase 区，Final 尚未执行。
