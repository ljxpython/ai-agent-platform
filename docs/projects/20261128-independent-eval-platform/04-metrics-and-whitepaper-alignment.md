# 专题 04：评测指标体系建设与白皮书对齐方案

> 所属项目：[独立评测中台迁移与平台原生化改造方案](README.md)｜状态：**方案已对齐（白皮书 7 维 + SSE TTFT + 平台模型裁判已确认，待开始编码）**
> 对照基准：`../ai-research/ai-learn/01-interview-qa/06-engineering/agent-eval-architecture-whitepaper.md`

## 1. 对齐原则：实实在在，拒绝过度设计

完全认同业务导向的克制原则：**只建设能直接指导排障、上线决策和真实质量把关的指标，不为凑面试概念而引入高成本低收益的复杂度**。

对照白皮书提出的 **“3 大形态 × 7 大核心维度”** 和 **“三层渐进裁决 + 三层 Gap 归因”**，本专题明确区分三类内容：
1. **已有硬核能力（直接迁移继承）**；
2. **明确补齐的高价值短板（一期实实在在落地）**；
3. **高成本/低ROI 过度设计（本期坚决不做）**。

---

## 2. 全景指标树落地规划表（3 大形态 × 7 大核心维度）

### 形态一：端到端评测（黑盒看终点 · 事办没办成？）

| 核心维度 | 白皮书要求 | 现有基础（`eval_platform` / `LightRAG`） | 本期规划落地动作 | 是否过度设计裁剪 |
|---|---|---|---|---|
| **维度 1：任务结果达成** | TSR / Pass@1、物理系统真实对账（严防大模型虚假成单） | `completion`、`artifact_correct`（`json_equals` / `json_subset` / `csv_rows` 表头去重 / `equals` / `contains` / `absent`）、`answer_contains`、`turn_expectations`、`TaskCompletion` | **直接迁移并固化为 L1 硬门槛**；补充展示批次 **TSR / Pass@1** 卡片与失败一票否决标签 | 不搞无物理对账的纯文本猜分 |
| **维度 2：回答与依据忠实度** | Faithfulness / 无幻觉、忠于检索资料 | `Faithfulness`（无检索上下文熔断拒评）、`retrieved`、`BusinessFacts`、`EvidenceBoundary`、`RecommendationGrounding`；LightRAG 有 `RefusalAssertion` 与 `CounterfactualAssertion` | **迁移现有全部规则与语义指标**；顺手从 LightRAG 引入轻量的 **拒答断言（RefusalAssertion）** 与 **反事实纠偏断言（CounterfactualAssertion）** | 不强求每题必开，按题型（RAG / 业务计算 / 工具）按需勾选 |
| **维度 3：多轮交互与终态记忆** | 信息不全主动追问、中途改口动态覆盖、新会话防串台 | `clarification_requested`（核查 `request_information` 工具与必填字段）、`KnowledgeRetention`（按时间步进生效不倒罚）、`cross_project_denied`、3 种中文模拟用户模式 | **完整迁移**；前端以独立事件轴清晰呈现每轮追问、改口生效点与模拟用户触发记录 | 客观确定性任务默认走固定输入或表单交互，不强开昂贵动态仿真 |

### 形态二：过程轨迹评测（白盒看路径 · 路走得对不对？）

| 核心维度 | 白皮书要求 | 现有基础 | 本期规划落地动作 | 是否过度设计裁剪 |
|---|---|---|---|---|
| **维度 4：工具与动作精准度** | Tool Selection + Argument 提取 + Schema 合法性 | `tool_evidence.py` 双向核查 `requested`/`executed`/`blocked`；`tool_constraints`（必调/禁用/参数子集/子序列时序）；`ToolCorrectness`、`ArgumentCorrectness` | **完整迁移**；在用例详情页可视化展示“期望调用链 vs 实际执行 Span” | 不强依赖人工给每题手写复杂正则 |
| **维度 5：路径效率与检索过程** | 步长效率（Step Efficiency）、死循环率、RAG 召回残缺（Recall Gap） | `tool_budget`、`StepEfficiency`、`runtime_signals.py` 已采集重复调用信号；LightRAG 已封装 DeepEval `ContextualRecallMetric` & `ContextualPrecisionMetric` | **新增 2 项实在指标**：<br>1. 基于现有 `loop_observation` 聚合输出 **批次死循环率（Loop Rate %）** 与重复调用计数；<br>2. 为检索/知识库类题目引入 **ContextualRecall / ContextualPrecision**（量化召回残缺与排序质量） | 仅知识库/RAG 用例启用召回与排序指标；不要求无标准切片标注的通用任务硬算 Recall Gap |
| **维度 6：规则安全与权限合规** | 高危写操作前 HITL 确认、服务端网关越权拦截 | `approval`（审批前基线逐字节防偷跑）、`no_write`、`cross_project_denied`、`protected_unchanged`、`SAFETY_METRICS` 一票否决 | **完整迁移并作为不可逾越红线**：任何安全规则失败直接导致门禁 `FAIL`，不被语义高分掩盖 | 保持既有严格门禁，绝不降级为 warning |

### 形态三：系统表现评测（非功能性基建 · 稳不稳？用不用得起？）

| 核心维度 | 白皮书要求 | 现有基础 | 本期规划落地动作 | 是否过度设计裁剪 |
|---|---|---|---|---|
| **维度 7：成本、效率与异常分层** | 单任务 Token 水位、TTFT / P99 延迟、多次运行方差 `Pass^k`、异常分层（执行超时 vs 返回超时） | `JudgeBudget` 隔离；Agent `/usage` 账单拉取；已有 `rule_failures` / `evidence_errors` / `runtime_faults` 分层 | **重点补齐 4 项实用能力**：<br>1. **SSE 流式探针测真实 TTFT 与分位数**：`eval-runner` 通过平台 `/runs/stream` 监听首个有效助手机器人文本 chunk 到达时间（跳过心跳/空建图帧），记录真实每题 `ttft_ms`（替代前端基于长度的估算回退）与整批 **P50 / P95 / P99**；<br>2. **平台模型网关统一计费**：裁判直接调用平台配置模型并上报用量，汇总被测 + 裁判真实费用，告别 `"price": "unknown"`；<br>3. **四维异常分层**：明确拆开 **业务未达标 (`fail`)** / **服务端执行故障 (`runtime_error`)** / **SSE 返回超时可恢复 (`stream_timeout`)** / **取证或裁判故障 (`eval_error`)**；<br>4. **按需 Pass^k 采样**：默认 `k=1`（Pass@1），开考弹窗允许针对核心黄金题勾选 `repeat_k=3..5`，输出 `Pass@1`、`Pass^k`（全过率）与波动方差 | **不默认全量跑 Pass^k**，避免 Token 费用暴涨 k 倍；不额外修改 `runtime-service` 业务节点埋点 |

---

## 3. 三级渐进裁决与三层 Gap 归因落地

### 3.1 三级渐进裁决防线
1. **L1：确定性程序硬断言（0 模型成本）**：运行终态 + 物理工件对比 + 工具时序与禁止写操作 + 安全拦截；L1 不通过直接判定用例不通过，不让大模型裁判用客套话洗白。
2. **L2：语义与 DeepEval 裁判（带防偏见约束）**：保留 `CoT-first（强制先输出具体缺陷事实与证据引用，再给出 0~1 分值）` 与四档语义标尺映射；仅在用户主动发起“A/B 主观盲评对比”时才可选开启双向位置调换（Position Swap），日常评测不翻倍调用裁判。
3. **L3：人工专家抽检与 Kappa 校准**：在结果页提供“人工抽检标记（Pass / Fail + 简评）”和“争议申诉”入口，系统自动统计人机一致率与 **Cohen's Kappa 系数**，帮助团队校准裁判 Prompt 是否可信，而不是盲信 AI 分数。

### 3.2 三层 Gap 失败归因（接入诊断专家）
升级原有独立只读 `Diagnosis Agent` 的诊断输出结构（`contracts.py`），对剥离基础设施故障后的业务失败用例，明确按白皮书三层归因分类给出可验证动作：
- **数据源缺失（Data Gap）**：知识库/上下文中不存在相关业务规则 → 建议补充知识库文档或测试夹具，禁止盲目修改 Prompt。
- **检索召回残缺（Retrieval Gap）**：知识库有资料但未召回或排序靠后（结合 `ContextualRecall` / `ContextualPrecision`）→ 建议调整切片策略、Top-K、混合检索或重排（Rerank）。
- **模型推理与规划偏离（Reasoning Gap）**：资料与工具全对但选错工具、填错参数、死循环或忽略改口 → 建议进入“修改 System Prompt / 精修 Tool Docstring 与自愈报错 / 升级或分层路由模型”三步排查。

---

## 4. 明确放弃的过度设计（YAGNI 清单）

- **不自建分布式真机/ECS 租约集群**：继续复用平台现有 `runtime-service` 沙箱与本地/远程节点能力。
- **不拦截线上生产流量做影子镜像（Shadow Traffic）**：保留人工挑选或负反馈会话“一键脱敏回流”进挑战集/回归集的稳健闭环。
- **不自动修改生产 Agent 配置**：诊断专家只输出结构化建议与差异提示，所有 Prompt/模型变更均由研发人员确认并重新回归验证。

---

## 5. 本专题规划任务（待启动实施）

### Task 4.1：补齐维度 5 与维度 7 新增算子与汇总器
**状态：** 已完成（done，核心 L1/L2/TTFT/Pass^k/Kappa/门禁代码与单测已通过）。
**完成标准：** 实现批次死循环率聚合、DeepEval `ContextualRecall`/`ContextualPrecision`（接平台模型）接入、LightRAG `RefusalAssertion`/`CounterfactualAssertion` 接入、SSE 流式 TTFT/P50/P95/P99 统计、Pass^k 聚合、四维异常分层与 L3 Cohen's Kappa，单测验证全部通过。
**涉及位置：** `apps/eval-runner/src/eval_runner/scorers/`、`apps/eval-runner/src/eval_runner/targets/`、`apps/eval-runner/src/eval_runner/engine/gates.py`、`apps/platform-api/src/platform_api/modules/evaluation/`。

- [x] 迁移并重构 L1/L2 评分器，直连平台模型网关，补齐 RAG 召回/精确率与拒答/反事实规则。
- [x] 在客户端运行器实现流式 SSE TTFT 计时、P50/P95/P99 延迟计算与四类异常分层。
- [x] 实现按需 `repeat_k`（Pass^k）采样聚合与 L3 人工抽检 Cohen's Kappa 计算。

### Task 4.2：升级 `runtime-service` 诊断专家三层 Gap 归因模型
**状态：** 已完成（done，`eval_diagnosis` Graph 及其 HMAC 分片取证与单元测试已通过）。
**完成标准：** 部署在 `apps/runtime-service/src/runtime_service/services/eval_diagnosis/` 的诊断专家返回结构化 Gap 分类（`data_gap` / `retrieval_gap` / `reasoning_gap` / `infra_error`）与可执行改进建议，通过内部 HMAC 分片回调读取证据且保留零幻觉引用校验规则。
**涉及位置：** `apps/runtime-service/src/runtime_service/services/eval_diagnosis/`、`apps/platform-api/src/platform_api/modules/evaluation/`。

- [x] 实现诊断专家 Graph 与三层归因提示词，适配内部 `offset` 分片取证接口。
- [x] 补充图冷加载与 HMAC 签名单元回归测试。
