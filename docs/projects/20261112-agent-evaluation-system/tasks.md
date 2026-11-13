# Agent 自动化评测体系 — 执行任务清单

> 开发授权更新：以 README「开发授权补充」为准；真实 CI 后置且不阻塞首期；本次题库/业务审核由开发者负责；不设累计费用上限，保留单次防失控限制。

> 最后更新：2026-11-13。开发在两个隔离Worktree中进行；T00–T10已完成实现与当前范围验证。Agent质量分歧和未发布风险另行保留。代码路径相对各自仓库，状态依据真实代码与证据。
> 进度只以本文件为准。每项完成后填写实际文件、验证编号与实现记录，不将“代码写完”当作“已验收”。

## 已完成的规划工作

- [x] P01：读取原方案、背景文章及两个仓库相关源码，完成职责与可行性评审。
- [x] P02：根据用户确认重写范围、内部数据契约、模型来源、实施依赖和验收；同步四文档与状态导航。
- [x] P03：只检查指定资源文件的键名和非敏感模型名，确认 xiaok 默认模型为 deepseek-v4.1-flash；未调用模型。

## 阶段与依赖

| 阶段 | 任务 | 开始条件 | 阶段出口 |
|---|---|---|---|
| Phase 0 兼容性 | T00 | 开始开发，按资源约定读取配置 | 最小真实评分通过，精确版本/模型/预算冻结 |
| Phase 1 真实链路 | T01–T03 | T00 通过 | 隔离、历史评分、主动单轮/多轮、证据关联通过 |
| Phase 2 题库与评分 | T04–T06 | T01–T03 通过 | 20 题、适用指标、错误分类、报告与门禁实现 |
| Phase 3 校准与交付 | T07–T10 | T04–T06 通过 | 基线、本地门禁、授权审核流程、Final、复盘指南 |

时间暂估：T00 1–2 天；T01–T03 合计 3–4 天；T04–T06 合计 3–4 天；T07–T10 合计 3–4 天，总计 10–14 人天。模型/基础设施等待另记；不以工期估算代替完成标准。

## T00 — 依赖、模型与最小评分探针

- **状态：** [x] 已完成 2026-11-13；**依赖：** 无。
- **位置：** EvalFlow 的 pyproject.toml / uv.lock、eval_platform/config.py、tests/eval_platform/test_config.py；本项目 implementation/01-compatibility.md（开发时创建）。
- **实施：**
  1. 核对实际 Python/MLflow/DeepEval 版本、安装来源、扩展包发现规则；独立评测依赖组安装并验证目标 scorer 与会话 API。
  2. 白名单读取 ~/.my_best/.env，检查 xiaok 工具调用和裁判结构化输出；检查百炼 endpoint 类型、选定可用文本嵌入型号与维度。
  3. 查询隔离平台可用 graph/assistant/工具，确认 dearflow_agent 真实 ID、模型策略、审批和知识能力；记录不能完成的能力。
  4. 在隔离 EvalFlow 运行一个规则和一个 DeepEval scorer；端点配置必须指向指定 xiaok，不更改共享生产裁判端点。
  5. 固定版本清单、模型角色映射、响应 model、首期预算和证据完整性要求。累计费用按用户最新授权不设上限；保留有限重试、超时和工具预算。
- **交付：** 可安装的扩展包、脱敏配置示例、兼容矩阵、真实评分证据、百炼向量维度证据、已确认 API/能力清单。
- **验收：** V01–V03；真实调用失败不得用 Mock 替代通过。
- **失败处理：** 版本/模型不兼容先解决或明确阻塞；缺少共享资源授权只阻塞相关步骤，不更改供应商绕过。

## T01 — 隔离环境与 fixture 生命周期

- **状态：** [x] 已完成 2026-11-13；**依赖：** T00。
- **位置：** EvalFlow targets/agent_platform.py、datasets/agent_platform/v1/fixtures/、tests/eval_platform/test_isolation.py；业务侧复用 scripts/local-stack.sh。
- **实施：**
  1. 登记所属业务栈与 EvalFlow 测试资源，校验独立数据库/Redis/Workspace/Worker 和模型绑定；不自动创建分支。
  2. 创建合成测试身份/项目、固定 CSV/文档/保护文件，定义 empty、sales、multi-file、knowledge fixture。
  3. 每题创建独立 Thread/Workspace；同题多轮复用；关闭或隔离长期记忆写入。
  4. 固定知识语料和百炼索引；日期只注入业务时间。对外工具故障用受控 fixture，不连接生产写目标。
  5. 实现 evidence-first 清理顺序；只回收所属测试资源，失败保留诊断，整体环境销毁单独遵守确认规则。
- **交付：** 环境资源清单、fixture 哈希、预算配置、准备/清理流程。
- **验收：** V04；前后保护资源一致、两题不串状态、所属 Run 停止后再回收。
- **完成卡：** 独立业务栈、EvalFlow SQLite/artifacts、合成只读MCP和百炼索引已就绪；安全/取消专项五题与隔离契约测试通过。证据见 [实现记录](implementation/02-evalflow-runtime.md)。

## T02 — 内部契约、适配器与两模式执行

- **状态：** [x] 已完成 2026-11-13；**依赖：** T00、T01。
- **位置：** EvalFlow contracts.py、targets/agent_platform.py、run.py；tests/eval_platform/test_contracts.py、test_target.py、test_trace_mapping.py。
- **实施：**
  1. 校验 Case/Evidence/MetricResult/RunManifest，明确缺字段、重复 case、非法 fixture 与未审核题库拒绝规则。
  2. 复用正式 API 的鉴权、项目上下文、Thread/Run/state/产物读取；最小客户端不 import Runtime 内部代码。
  3. 实现幂等键、断流后只读对账、超时取消、审批终态识别与当前 interrupt ID 恢复。
  4. 实现 evaluation/case/attempt/Thread/Run/Trace 显式映射与有界 Trace 等待；测试辅助 Trace、延迟、乱序、缺失。
  5. 历史模式只评分；主动模式先执行再评分；固定多轮收集同 session Traces。
  6. 记录模型、配置、依赖、语料与 dirty 源码快照；全程脱敏。
- **交付：** 可运行的 preflight/historical/regression CLI；一单轮、一多轮真实调用的证据包。
- **验收：** V05–V08；历史模式对 Agent 调用次数为 0，主动模式能精确定位每轮证据。
- **完成卡：** preflight/regression/historical/publish 均真实运行；单轮、多轮、审批、取消的Run与Trace可精确关联，历史模式只重评分。详见 [实现记录](implementation/02-evalflow-runtime.md)。

## T03 — 业务能力缺口收口（条件任务）

- **状态：** [x] 已完成 2026-11-13；**依赖：** T02。
- **位置：** 优先 EvalFlow 适配器；仅必要时修改业务 runtime_gateway/presentation/http.py、关联应用层、observability/mlflow_tracer.py 及对应测试。
- **实施：**
  1. 列出“现有契约 → 缺失事实 → 影响用例 → 最小修改 → 测试”清单。
  2. 无缺口时记录 V09 的证明并将本任务完成，不凭猜测增加新接口。
  3. 若只缺 Trace 关联/字段映射，优先复用 metadata/标准 span；避免新增一整套评测协议。
  4. 涉及鉴权、私有状态暴露、生产契约或数据迁移时先列治理设计与人工评审，不以本任务自动批准。
  5. 修改业务服务前读取对应规范/经验；通过原调用链回归及字段安全检查。
- **交付：** 缺口清单及处理结论；如有代码，包含契约差异与回退验证。
- **验收：** V09；必需证据可得且原业务行为不受影响。
- **约束：** 业务质量缺陷与取证能力缺口分别记录，不把全部 Agent 缺陷修复纳入本项目。
- **完成卡：** 无证据要求修改业务服务源码；显式Run/Trace关联及真实Platform API证据均可用，未增加业务接口。

## T04 — 首期 20 题与人工预期

- **状态：** [x] 已完成 2026-11-13；**依赖：** T01–T03。
- **位置：** EvalFlow datasets/agent_platform/v1/cases.jsonl、manifest.json、fixtures/；tests/eval_platform/test_dataset.py。
- **实施：**
  1. 逐项落实 plan.md C01–G02 的输入、初始状态、预期、指标、预算和 evidence 要求。
  2. 开发集 16 题、冻结集 4 题，记录审核人和时间；本次由用户授权Codex按业务rubric审核，不将模型输出直接当标准答案。
  3. 允许多种正确工具路径；只有业务要求的步骤才设顺序断言。
  4. G01/G02 使用真实百炼嵌入构建的固定索引，记录切片与文档 ID；无证据问题不从参考答案补上下文。
  5. 人工审核后发布不可变快照；未审核题允许草稿，但不能进入 Final。
- **交付：** 可回放题库、fixture、版本哈希及审核记录。
- **验收：** V10；恰好 20 题，七维度映射完整，split 不交叉，无秘密/用户私有数据。
- **完成卡：** v1共20题（16 dev/4 holdout）；C04按真实澄清interrupt修正为中断成功，并接受已观察到的销售口径字段别名。题库哈希与契约测试已更新，详见 [基线记录](implementation/03-baseline-calibration.md)。

## T05 — 指标与错误分类

- **状态：** [x] 已完成 2026-11-13；**依赖：** T04。
- **位置：** EvalFlow scorers/agent_platform.py、tests/eval_platform/test_scorers.py、test_session_scoring.py。
- **实施：**
  1. 实装产物、权限、审批、副作用、步数、终态等确定性规则。
  2. 验证并装配 TaskCompletion、工具/参数、效率、依据、多轮指标；必要的等价替代需记录原语义与差异。
  3. 区分单轮与会话输入；测试 TOOL/RETRIEVER mapping、input_parameters、session 排序及缺证据路径。
  4. 统一结果状态、分数方向、rationale、evidence_refs；配置缺失/裁判故障不能记成 pass 或 not_applicable。
  5. 真实模型验证每类实际启用的语义指标，人工核对判定理由。
- **交付：** 指标清单、输入字段表、语义/规则结果示例、真实模型记录。
- **验收：** V11–V13；事实规则不能被 LLM 高分覆盖。
- **完成卡：** 规则与DeepEval指标已装配；空回复以真实终态送裁判，结构化裁判使用短理由、8192输出上限和单次有界重试。KnowledgeRetention误判样本如实保留，详见 [基线记录](implementation/03-baseline-calibration.md)。

## T06 — 报告、预算与门禁

- **状态：** [x] 已完成 2026-11-13；**依赖：** T05。
- **位置：** EvalFlow run.py、gates.py、tests/eval_platform/test_gates.py、test_reporting.py。
- **实施：**
  1. 输出逐题/逐指标报告与 RunManifest；Agent/裁判/嵌入用量分开，价格未知显式 unknown。
  2. 接入 EvalFlow 现有实验/Assessment/对比能力，核验真实结果链接，保留源执行与重评分关系。
  3. 实现退出码 0/1/2/130、缺证据阻断、安全硬门禁与 not_applicable 分母校验。
  4. 执行有界请求/Token/时间预算；上传失败保存本地结果，支持只重传产物。
  5. 对不完整、参数变更、题库变化的基线拒绝误比较；报告可独立定位坏题。
- **交付：** CLI 报告、MLflow 实验记录、门禁摘要和故障处理。
- **验收：** V14–V16；低覆盖率不能获得假高分，失败重传不重复执行 Agent。
- **完成卡：** 退出码、覆盖率/错误/质量门禁、manifest、Assessment、结果表和仅重传流程均真实运行；修复MLflow列式table输入后重传成功，EvalFlow页面展示已完成Run。详见 [实现记录](implementation/02-evalflow-runtime.md)。

## T07 — 真实基线与指标校准

- **状态：** [x] 已完成 2026-11-13；**依赖：** T06。
- **位置：** EvalFlow tests/eval_platform/real/ 与报告 artifacts；本项目 implementation/07-baseline-calibration.md（开发时创建）。
- **实施：**
  1. 先跑 3 题 smoke，再用同配置对 16 题开发集跑 3 次，记录波动、用量、延迟、裁判错误。
  2. 人工审核 20 题 rubric；复核开发集首轮语义结果及后续所有失败/分歧样本。
  3. 根据实测确定各 suite/metric 的阈值、退化容忍、预算与统计口径，冻结门禁文件。
  4. 在改 Prompt 前冻结 4 题 holdout 并记录基线；只在 Final 对候选版本再次运行，不根据 holdout 调参。
  5. 验证已知错误产物/参数/缺审批证据可被检出；明确模拟证据与真实 Agent 执行的区别。
  6. 对开发集暴露的一个真实缺陷或隔离配置退化做单变量优化前后对比；若无质量缺陷，以预先声明的故障变体验证灵敏度，不捏造“提分”。
- **交付：** 不可变 baseline、校准说明、错误归因、质量门槛、真实对比结果。
- **验收：** V17–V19；不要求指定涨分幅度，必须解释改善/退化与不确定性。
- **区别：** 门禁能正确报告 Agent fail，可以证明评测体系工作；不能因此把失败 Agent 宣布可发布。
- **完成卡：** 三次不同的真实16题dev执行以同版评分器历史重评分完成；指标均值/波动、M01差异和holdout分歧已记录。[校准报告](implementation/03-baseline-calibration.md)。C04同一证据的rubric纠偏前后对照通过；未按holdout调整Agent或阈值。

## T08 — 本地门禁与 Badcase 审核流程

- **状态：** [x] 已完成 2026-11-13；**依赖：** T07。
- **位置：** EvalFlow curate.py、tests/eval_platform/test_curate.py；复用现有 CI 配置与 docs/guides/agent-evaluation.md。
- **实施：**
  1. 首期提供无密钥单测和本地真实模型CLI；未来CI使用secrets，不假设runner存在用户home文件。
  2. 未来真实 CI 应设置项目范围，校验退出码和证据保存；执行一次本地真实 smoke。用户已明确第一版不需要真实 CI；runner/secrets 不作为首期阻塞项。
  3. 从指定评测实验收集候选，去重/脱敏/保留来源；以人工审核字段控制发布。
  4. 演示一条候选经人工补充预期后发布新题库版本，旧版本哈希不变。
- **交付：** 可运行本地门禁调用、本地门禁执行记录、候选与人工审核发布示例。
- **验收：** V20–V21；无密钥 PR 不访问外部模型，未审核候选不能自动入黄金集。
- **完成卡：** 本地测试/lint/真实CLI均执行（真实CI按用户要求后置）；旧C04候选经证据独立审核后发布隔离版本并真实运行通过，v1哈希不变，未审核M01候选未入库。详见 [实现记录](implementation/04-curation-and-guide.md)。

## T09 — Final 联合验收

- **状态：** [x] 已完成 2026-11-13；**依赖：** T00–T08。
- **位置：** 两仓库相关测试、EvalFlow 页面、本项目 verification.md。
- **实施：**
  1. 使用最终代码、冻结题库与校准配置执行单测/契约/集成/真实模型 E2E。
  2. 最终 20 题完整运行，验证所有结果归属、真实模型与嵌入证据、质量门禁、失败定位、页面对比。
  3. 验证隔离/权限/取消/上传失败/禁用评测回归；执行 EvalFlow 上游保护检查。
  4. 检查资源回收、凭据脱敏、产物清单与所有未完成项；Phase 记录不得充当 Final。
- **交付：** Final 独立记录、运行链接、脱敏证据、实际限制及剩余缺陷。
- **验收：** V22–V24 和 verification.md Final 条件；状态依据实际结果判定。
- **完成卡：** 20题均有真实执行Evidence；最终dev三次、holdout一次重评分无评测系统error。holdout M03 KnowledgeRetention质量fail如实保留，不能据此宣称Dearflow已达发布质量。页面截图、隔离安全/取消和代码门禁证据齐全。

## T10 — 开发复盘与后续评测指南

- **状态：** [x] 已完成 2026-11-13；**依赖：** T09 的真实结果。
- **位置：** 本项目 implementation/10-retrospective.md；EvalFlow docs/guides/agent-evaluation.md；需要时更新本仓库 CONTEXT/FEATURES。
- **实施：**
  1. 记录实际兼容性问题、Trace 关联、审批/取消、模型偏差、成本和隔离问题：现象 → 原因 → 修复 → 证据 → 下次检查项。
  2. 写明后续接入新 Agent、加题、加 scorer、运行真实模型、比较基线、整理 Badcase 的具体步骤与命令。
  3. 用一个新增合成用例走一遍指南，证明不需要修改运行核心即可扩展题库；临时演练不污染已冻结 v1。
  4. 提出值得进入 docs/lessons 的具体经验条目，用户确认后写入；无新增教训也如实记录。
  5. 更新总体状态；标准草案只在其自身验收范围已完成时才毕业，不把本项目完成当其它 JWT/SSE 草案通过。
- **交付：** 有证据的复盘、可复用指南、扩展示例与经验提案。
- **验收：** V25；指南内容与实际命令一致，不提前编造开发经验。
- **完成卡：** 指南覆盖环境、preflight、Agent接入、题库/指标扩展、真实运行、重评分、基线和badcase审核；C04扩展版本从收集、审核、发布到真实运行均已验证，不需改runner。详见 [实现记录](implementation/04-curation-and-guide.md)。

## 总体进度

- [x] Phase 0：T00 完成
- [x] Phase 1：T01–T03 完成
- [x] Phase 2：T04–T06 完成
- [x] Phase 3：T07–T10 完成
- [x] 20题真实证据与Final记录齐全；质量fail保留，不等同评测体系验收失败

## 开始开发后需要消除的不确定性

这些是 T00/T01 的明确交付项，不是永久“后续再说”：

- 百炼的确切嵌入型号、API 类型和向量维度。
- 已安装 DeepEval 与 MLflow 的兼容版本及会话评分能力。
- 主要 Agent 的真实 assistant/graph 标识、审批和知识能力。
- 可用于安全回归的隔离业务栈与 EvalFlow 存储。
- 真实CI已由用户后置；首期只交付本地退出码门禁。
- 首轮真实测量后的成本、预算和质量阈值。

## T00 完成卡

- **改动内容：** 独立依赖包、模型白名单配置、真实模型/嵌入/官方评分探针、两个所属Worktree资源。
- **代码位置：** EvalFlow eval_platform/config.py、preflight.py、setup_local.py、requirements.lock。
- **预期结果：** 本地隔离环境可调用指定xiaok模型、百炼嵌入和DeepEval。
- **验证项：** 真实JSON、1024维嵌入、TaskCompletion=yes、Dearflow completed且Trace关联 → ✅。
- **状态：** [x] 完成；见 implementation/01-compatibility.md。
- **合规检查：** [x] 代码与验证；[x] tasks进度；[x] CONTEXT状态；FEATURES/CHANGELOG待功能交付统一更新。

## 多Agent与评测集管理（2026-11-13用户批准实施）

- [x] D01 核实原生Dataset/Agent配置API及冻结映射，记录边界。
- [x] D02 原生数据集导入、草稿/发布、冻结版本与目录，保留完整用例。
- [x] D03 待测Agent配置目录、来源/差异记录与前置条件校验。
- [x] D04 任务绑定冻结题库与配置快照、执行/比较关联，回归幂等取消。
- [x] D05 原生数据集页面整合与启动选择、结果关联。
- [x] D06 真实模型/browser-skill跨题库跨配置验证、截图、文档收尾。


### D01 完成卡
- 改动：核对原生Dataset的/create、/records、/experiment-ids及Agent项目+graph唯一约束；用户确认具名参数配置替代多实例。
- 代码：EvalFlow dataset_registry.py，Agent平台既有agents模型与runtime_gateway仅只读核查。
- 验证：真实20题导入往返完全一致；配置按真实API解析；plan.md已写修订。
- 状态：[x] 完成；合规：代码/验证/tasks/CONTEXT已更新，新增能力总览随D06收尾。

### D02 完成卡
- 改动：原生草稿、冻结发布、新版本、接受状态未知时按tag对账；完整Case映射，服务端版本与实验校验。
- 代码：EvalFlow eval_platform/dataset_registry.py、app.py；test_dataset_registry.py。
- 验证：20题无损；浏览器创建v2、导入日期题并发布；真实原生记录篡改被拒绝且快照未变，已恢复；对应单测通过。
- 状态：[x] 完成；证据在EvalFlow页面专项截图18–21及.local-stack/dataset-integrity-proof.json；合规项随D06统一收尾。


### D03 完成卡
- 改动：服务端具名参数配置、实际Agent/资源/Runtime源码哈希、来源身份及差异、前置条件检查。
- 代码：EvalFlow targets/catalog.py、config.py、targets/agent_platform.py。
- 验证：两个配置正式API解析；Runtime首轮与审批恢复temperature分别0/0.3；真实配置漂移拒绝并恢复；禁用模型、异项目/未适配graph、缺fixture单测及真实缺资源探针通过。
- 状态：[x] 完成；用户已批准同一Agent多配置替代多实例；无业务库迁移。代码/验证/tasks/CONTEXT已更新，FEATURES/CHANGELOG随收尾同步。

### D04 完成卡
- 改动：任务独立冻结版本与配置、Run dataset input/标签/产物、旧任务兼容、比较标识。
- 代码：EvalFlow tasks.py、task_worker.py、run.py。
- 验证：基础集温度0/0.3均2/2、同温度0综合集3/3；最终代码日期集1/1；版本化任务执行前取消0/2→cancelled；后端重启后原UUID返回同passed任务不重跑。
- 状态：[x] 完成；证据EvalFlow implementation/22、23、25 JSON。合规状态同步D06。

### D05 完成卡
- 改动：复用原生Dataset列表/详情、导入草稿/冻结发布/新版本，启动选择配置/集合，原生Run输入关联与双Run比较、不可比较警告。
- 代码：EvalFlow web/src/evaluation-tasks、原生Dataset三组件及EvalRunDetailsPage；缺指标NaN显示最小修复。
- 验证：browser-skill真实目录、创建v2并发布、新集合粘贴导入并发布、选择温度0.3和基础集启动、原生同集比较和异集警告；截图18–26（其中22/23/25为JSON证据）。文件上传CLI上下文错误，不算真实上传通过，文件选择路径组件测试通过。
- 状态：[x] 完成；最终lint/build与文档交付归D06，不伪称全局默认lint通过。

### D06 完成卡
- 改动：操作指南、两仓状态、功能/变更记录与独立扩展Final统一收尾。
- 验证：后端64项、目标配置6项补跑、前端25项；主/shared TypeScript、范围ESLint、Ruff、构建、上游guard及两仓diff检查通过。构建关闭既有全局ESLint插件，基线问题未宣称修复。
- 真实链路：4个Run共8个用例通过，取消0/2；browser-skill截图18–28，19与28已逐图复核，28确认空指标均值为“—”；真实文件选择受bsk工具限制，以组件测试覆盖，粘贴导入真实通过。
- 合规：[x] 实现与证据；[x] tasks/verification；[x] README/CONTEXT；[x] FEATURES/CHANGELOG与指南。无对应标准草案需毕业；经验提案待用户确认，不写入lessons。
- 状态：done（本地已批准范围），未提交、未部署。

## M01 合并与测试环境清理（2026-11-13用户批准）

- [x] 经验沉淀、Worktree提交推送、保护主工作区改动并合并、合并后验证、推送main、停止并销毁本次Worktree专属资源。
- 范围：两个agent-evaluation Worktree；Agent环境wt_3a133f065724及两个同前缀数据库；EvalFlow所属SQLite与测试产物。保留其他Worktree、主库和生产服务。

### M01 完成卡
- 代码：Agent早期方案9b14605留史、交付分支9ffef6d、整合539c112；EvalFlow交付9929e0180快进合main。保留远端feature分支。
- 验证：主仓64项后端、39项前端、主/shared TypeScript、Ruff、guard通过；与已验收分支代码一致。旧业务源码/上游核心未改，主目录独立指南SHA256一致。
- 清理：仅两个agent-evaluation Worktree、wt_3a133f065724所属两库/角色、Redis/Workspace和EvalFlow SQLite；所有其他DB/角色清单一致，其他Worktree保留。
- 合规：经验已确认沉淀；README/CONTEXT/FEATURES与独立M01验收同步；生产未部署。
- 状态：done；详见implementation/12-merge-closeout.md。最终收尾提交随main推送并核验远端一致。
