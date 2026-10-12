# 产品范围、统计口径与现状

## 目标

让运营人员识别消耗趋势与主要来源，让项目管理员定位项目内高消耗模型/Agent，让有现有会话访问权限的人进一步追查某次运行。先保证统计范围可信、缺失可见，再考虑预算、优化建议和结算。

## 方案设计

### 当前代码事实

以下依据为 2026-10-11 工作树源码，不代表已部署生产。

| 已有能力 | 事实入口 | 对看板的意义 |
|---|---|---|
| 模型 usage 归一化、价格估算、采集去重 | `apps/runtime-service/src/runtime_service/observability/usage.py`：`normalize_usage()`、`estimate_usage_cost()`、`RuntimeUsageCallback`、`with_runtime_usage()` | 重用唯一采集链路；不能浏览器重新猜 Token |
| Run manifest 与调用台账 | `apps/runtime-service/src/runtime_service/db/migrations/versions/0002_usage.py`；`db/repositories/usage.py` | 已有 tenant/project/thread/graph/run/model/call、时间、purpose/scope/quality 与价格快照 |
| 受保护内部读取 | `apps/runtime-service/src/runtime_service/http/usage.py`；`observability/usage_query.py` | 当前仅单 Run 和单 Thread 两种查询 |
| 授权公共读取与安全 DTO | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`：`get_thread_run_usage()`、`get_thread_usage()`；`application/usage.py` | 保留原 v1 接口和当前 ACL，不扩大已有 operation |
| 模型六桶费率与版本 | `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`；`infra/sqlalchemy/models.py` 的 `pricing_json` | 历史调用的成本已有冻结快照，目录改价不改旧记录 |
| Chat Run/Thread Usage | `apps/platform-web/src/modules/chat/components/trajectory/RunUsage.vue`；`composables/useRunUsage.ts`；`services/threads/usage.service.ts` | 看板可钻取现有面板，不复制聊天控制器 |
| 固定角色 IAM 与导航裁剪 | `apps/platform-api/src/platform_api/modules/iam/application/policies.py`；`apps/platform-web/src/router/routes.ts`、`composables/useNavigation.ts` | 增加具体读权限并同步服务端/前端类型、路由与测试 |
| 项目内 Graph 唯一的 Agent 映射 | `apps/platform-api/src/platform_api/modules/agents/infra/sqlalchemy/models.py` 的 `uq_agents_project_graph_id` | V1 使用 `(project_id, graph_id)` 聚合，平台批量映射当前 Agent 展示名 |

当前缺口：跨 Thread/项目聚合、按调用时间分桶、模型/Agent排行、专用聚合权限、正式用量页面、平台量级性能验证。既有时间过滤按 `runtime_usage_runs.collection_started_at` 选整条 Run，不等于本项目按模型调用 `started_at` 统计的消耗时间。

### 产品入口与用户问题

| 用户问题 | V1 能力 | 结果可追查性 |
|---|---|---|
| 最近7天用了多少？比前7天如何？ | 汇总卡、同长度上一窗口比较；缺失或基期为0时不显示误导百分比 | 范围/时区/更新时间可见 |
| 消耗哪一天升高？ | 日/小时趋势；Token和成本分开切换 | 点击时间桶加入筛选 |
| 哪个项目/模型/Agent消耗最多？ | 维度排行、Top N与“其他”、Token/已知成本排序 | 点击行固定对应维度 |
| 高消耗来自子 Agent、摘要还是主模型？ | scope 与 purpose 分解 | 继续按项目、模型和用途交叉筛选 |
| 一次运行发生了什么？ | 有权限运行明细、期间消耗、既有 Run Usage 跳转 | 单次完整用量与窗口统计分别标明 |
| 这个数字可靠吗？ | 用量覆盖、计价覆盖、缺失/未结束调用、未计入范围 | 跳转模型价格配置或重试查询 |

### V1 功能与边界

**必做：** 平台/项目两个受控入口；时间与业务维度筛选；总览/趋势/排行；安全运行明细；真实零与未知态；历史价格、权限撤销、无权限和故障；基本可访问性与三尺寸。

**后续候选（本期不实施）：** 无 Run 辅助模型消费、用户/服务账号排行、按来源区分 chat/cron/后台续接、CSV、项目月度预算和告警、供应商账单对账、优化建议、月报、预聚合。它们需要各自的数据或授权依据，不自动纳入 V1。

初始默认建议：近7个自然日含今天，时区 `Asia/Shanghai`；可切 `UTC`。快捷范围为今日、昨日、7天、30天，自定义正向窗口不超过90天。今日为进行中的数据；对照统一取当前区间之前紧邻的等长窗口，例如今日已过10小时，对照为今日0点之前的10小时。页面展示两窗实际起止，使用“前窗变化”文案；V1不另做昨日同时段或去年同期比较。

### 核心统计规则

| 指标 | 口径 | 缺失时的展示 |
|---|---|---|
| 总 Token | `input_tokens + output_tokens`；沿现有归一化事实 | 完整才称“总量”；否则“已记录小计”并保留 `known_tokens` |
| 输入/输出 | 选中调用中对应字段的和 | 对应字段独立完整度，缺输入不妨碍展示已知输出 |
| 缓存读/写 | 输入的子集；写入总量已含5m/1h明细 | 不与输入相加；缺缓存信息与明确0区分 |
| 推理 Token | 输出子集 | 不与输出相加，不重复计费 |
| 已采集调用数 | 按持久化唯一调用键计数，真实重试/备用模型调用分别计入 | started、failed、cancelled仍可占观察次数 |
| 已采集运行数 | 筛选内有调用的 distinct native `run_id`；零调用 manifest 单独标示 | 不称“平台全部执行数”；native成功率不从manifest推算 |
| 每运行平均Token | 仅当 `summary.tokens.total_tokens` 完整且匹配的distinct native Run数>0时，期间完整total / 同一调用数据集的distinct Run数 | 否则null；这是期间平均，不是Run全生命周期平均，不用部分分子或剔除缺失Run后的分母 |
| 用量已报告比例 | reported及derived调用数 / observed调用数 | 无观察样本为null；100%仅表示已观测调用完整，不能证明供应商全部消费已覆盖 |
| 计价比例 | 保存可用成本的调用数 / observed调用数 | 同时展示缺价数；不能把未计价当免费 |
| 缓存读占比 | 仅使用输入与cache_read都已知的同一组调用：`sum(cache_read)/sum(input)` | 分母0/无样本为null，附样本覆盖数；不称缓存请求命中率 |
| 估算成本 | 调用保存的USD估算成本之和，Decimal运算、12位小数字符串 | 完整显示estimated，否则known_cost小计与unpriced数量；从不显示未知为$0 |
| 前窗变化 | 紧邻等长窗口、相同筛选、相同定义的数据比较 | 任一窗口不完整或基数0时保留两窗数值，百分比为空 |

现有成本公式继续使用互斥输入桶：普通输入、缓存读、generic写或完整TTL写桶，加输出；reasoning不另外收一次。价格为目录配置，金额标签使用“估算成本（USD）”。V1不引入汇率，不声称扣费金额、余额或供应商发票。

用量quality、调用outcome和计价状态分别计数；未结束调用也可能同时缺usage、未计价，不能将这些数字相加作为独立调用总数。所有覆盖比例标明各自分母，Run数与call数不混用。

物理调用是统计事实：重复 end callback 和 SSE重放不重复；新调用/重试/备模型增量计入；fork不复制旧费用，rollback不删除已发生费用，失败/取消里已报告的消费仍保留。Token额度是单Run保护，与月度平台预算分离。

### 时间、名称和删除语义

- 新看板按调用 `started_at` 落入半开区间 `[from, to)`；一条跨午夜调用计入开始的桶，结束后补齐该桶。结束时间不成为另一份消费。
- 查询按统一snapshot读取，返回 `as_of`；“采集完成”不能替代原生Run终态。并发更新后下一次刷新可修正旧桶，不承诺供应商账单不可变。
- Agent标签来自当前项目/Graph映射。历史改名显示当前名称；Graph删除或旧映射不存在时显示稳定 `graph_id`。V1不宣称历史Agent配置版本分析。
- 模型以catalog UUID优先，不按模型名合并不同连接；model_id缺失进入明确“未映射模型”分组，保留安全provider/model_name，不套主模型价格。
- 项目/Agent/模型名称由Platform批量解析；无权限实体不进入可见选项。详情不展示Prompt、会话标题、文件名、连接地址、密钥或原始异常。
- **2026-10-11 已批准的治理口径：** 对仍存在的授权项目，汇总继续包含已删Run/Thread曾发生的数字消费；不恢复或公开被删会话内容。删除项目默认退出可查询范围，保留台账等待原有保留政策；本项目不新增物理清理、历史重算或跨库级联。Thread 删除真实链路已验；Run 删除审计过滤的能力边界见03。

### 数据覆盖与未来演进

`usage.py::EXCLUDED_OPERATIONS` 当前明确为 `suggestions/title/non_llm_provider_fees`；`with_runtime_usage()` 仅在采集开关启用且可信native身份完整时接线。四图主子、受管理摘要/vision/memory和新后台接续产生的native Run按实际记录计入；无记录不能自行推定“免费”。

无法从现有表证明关闭开关期间漏掉的调用、未接线图的运行总数或供应商隐藏重试。因此页面常驻注明“已采集 Agent 用量”，显示最早/最近记录和排除操作；不提供“全产品覆盖100%”字段。开始统计日期不是系统上线日期，历史不从Chat字符数回填。

| 后续能力 | 必须先补的数据 | 建议投入 |
|---|---|---|
| 标题/推荐问题总消费 | 可信辅助 `operation_id`、用途、tenant/project/thread可空关联、调用级唯一键；一次可生成多个真实调用，取消/错误保留已知usage | 3–5人天，另行评审；复用归一化/价格helper，建立辅助操作事实后与native台账在查询层合并，不伪造run_id |
| 用户/服务账号排行 | 可信实际发起者 `initiator_id/actor_type`、cron/后台续接来源与原始发起者；现有owner不等于每个Run发起者 | 2–4人天；在调用/Run接收边界补不可由浏览器伪造的事实，历史未知保留unknown |
| CSV | 独立export授权、行数和时间上限、公式注入防护、审计与取消 | 1–2人天；不要把当前分页导出当全量 |
| 月度预算/告警 | 预算归属、消耗范围、时间窗、告警幂等及通知渠道；若硬扣额度还需预留与并发结算 | 单独治理立项；单Run额度不直接复用作财务预算 |
| 预聚合 | 02/05实测证明原始查询超标；修正/迟到更新与当前ACL口径已固定 | 2–4人天；派生读模型可重建，原始台账仍为唯一事实源 |

## 任务拆分

- [x] **D01 源码盘点（2026-10-11）：** 核对已有台账、采集、价格、两GET、前端面板、权限与Agent唯一映射；本节记录实际路径。
- [x] **D02 产品/数据建议（2026-10-11）：** 明确V1、指标公式、零/未知、时间、删除和辅助调用范围；不代表人工批准。
- [x] **D03 冻结业务口径（2026-10-11）：** 全部 G0 用户批准；公开 DTO、查询 schema、签名向量及全状态 fixtures 已冻结。
- [x] **D04 非前端核账（2026-10-11）：** 归一化/部分/跨日/多 Run/重复补齐与真实模型核账完成；页面口径核对属于 W03/W04，不计为本轮完成。

### Task D03：口径与契约冻结

- **改动内容：** 将获批 native Run 范围、权限/删除/时间/费用口径绑定实际 DTO。
- **代码位置：** `apps/platform-api/src/platform_api/modules/usage_analytics/contracts.py` → `UsageDashboardV1`；本项目 `fixtures/`。
- **预期结果：** 前端消费唯一公开结构，缺失与真实零可区分。
- **验证项：** Pydantic 全部响应/错误 fixture 校验；双端固定 HMAC 向量测试 → 通过。
- **状态：** `[x] done` 2026-10-11。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（与 R/A 汇总同步）。

### Task D04：非前端数字核对

- **改动内容：** 确定性测试与真实 DeepSeek 调用，对账 ledger→单 Run→项目/平台→趋势/排行。
- **代码位置：** `apps/runtime-service/tests/durable/test_usage_analytics.py`；`apps/platform-api/scripts/verify_usage_chain.py`。
- **预期结果：** input1000+output100=1100，缓存/推理不重复；部分小计不伪装完整总量。
- **验证项：** 三次真实模型470/488/471 Token，金额与账本完全一致；真实PG跨日/Top+other/distinct Run/迟到双upsert及真实Thread fork不复制旧消费 → 通过，详见05。
- **状态：** `[x] done`（本轮非前端范围）；页面标注和浏览器核对交接 W03/W04。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共同能力一行记录）。

## 验证要求与记录

### 验证要求

- [x] 确定性样本：input=1000、output=100、cache_read=200、write=100、reasoning=30，total严格为1100；不能变成1430。
- [x] 两调用其中一条缺usage：已知小计仍可用，完整总量/百分比为空；完整真实0不同于缺记录。
- [x] 跨午夜/重复回调/新调用/历史价格快照/取消样本通过单元及真实PG/Worker；真实Thread fork不复制旧消费通过。
- [ ] 辅助操作未计入、用户归因未做、删会话汇总等范围在API和页面文案一致。

### 规划记录

2026-10-11：静态核对以上源码及既有专项文档；未运行模型、数据库、后端测试或浏览器。功能验证均待实施，不能复用既有专项的通过次数冒充本项目通过。

### Phase 实施验证

D03：全G0用户批准并冻结fixtures。D04：真实模型三次、真实PG与单元核账、取消/HITL/新Run/Worker恢复30场景、真实Thread fork均已验，证据见05；辅助排除/未做用户归因/删除保留已由API冻结，页面文案待W03/W04，未据此标全栈Final。

## 状态

`done`（口径与本轮非前端核账）；页面标注核验由前端接续，项目总体 `partial`（B01已解除，联合Final/人工验收待完成）见05。
