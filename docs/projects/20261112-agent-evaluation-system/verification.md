# Agent 自动化评测体系 — 验证计划与记录

> 开发授权更新：以 README「开发授权补充」为准；真实 CI 后置且不阻塞首期；本次题库/业务审核由开发者负责；不设累计费用上限，保留单次防失控限制。

> 本文件保留原始验证计划，并在后文追加实际 Phase 与 Final 结果；计划条目不等同验证证据。
> 方案文档校验、Phase 验证、Final 联合验收分别记录，禁止混用。

## 1. 验证原则

1. 单测可用 Mock 验证边界；真实模型/嵌入/跨服务 E2E 不能用 Mock 替代。
2. 推理和裁判使用 ~/.my_best/.env 指定的 xiaok deepseek-v4.1-flash，知识嵌入使用 T00 冻结的百炼模型；记录实际请求/响应 model。
3. 只使用合成题库和所属隔离资源。历史模式第一次使用合成 Trace，不读取生产用户记录。
4. 每项证据必须包含命令、时间、源码/依赖版本、环境 ID、case/run/trace 引用、实际结果、脱敏输出位置。
5. 费用未知记 unknown；尚未执行记未执行；缺证据记 error；错误样本不能从分母里静默移除。
6. 门禁判断与体系交付判断分开：已验证的 Agent 质量 fail 应保留，不能为了“全绿”降低阈值。评测系统自身 error、缺证据和漏测不得通过 Final。

## 2. 验证矩阵

| ID | 任务 / 层级 | 场景与操作 | 必须满足的结果 |
|---|---|---|---|
| V01 | T00 / 单测 | 白名单加载配置；缺 Key、错误模型角色、日志序列化 | 缺配置明确失败；日志/快照无密钥、Authorization |
| V02 | T00 / 真实集成 | 安装锁定依赖；规则 scorer + xiaok DeepEval 最小评分 | 导入/构造成功；非空有效结果与理由；实际模型符合约定 |
| V03 | T00 / 真实集成 | xiaok 工具调用、结构化输出；百炼批量嵌入 | 真实成功；记录模型、向量维度、请求次数与用量 |
| V04 | T01 / 隔离 | 两题不同 Thread/Workspace；同题多轮；准备/清理前后对账 | 不串文件/记忆/索引；保护资源不变；只操作所属环境 |
| V05 | T02 / 单测 | 非法/重复 Case、未审核 release、错误 fixture、缺 Evidence | 校验拒绝；不得进入模型执行或生成成功成绩单 |
| V06 | T02 / 契约 | 断流/接受未知/重试/取消/当前 interrupt 恢复 | 原幂等键对账，无重复写；审批前后状态正确；unknown 不当 completed |
| V07 | T02 / 真实 E2E | 历史 Trace → scorer → EvalFlow | Agent 新调用次数 0；Assessment 与来源匹配；模式标记 historical |
| V08 | T02 / 真实 E2E | CLI → Platform API → Runtime → 单轮/多轮 → Trace → scorer | 精确 case/attempt/Run/Trace 关联；多轮 session 正确，无“最新 Trace”猜配 |
| V09 | T03 / 契约与回归 | 能力缺口清单；必要最小适配或零改动证明 | 必需证据可得；原业务调用、ACL、私有字段规则不退化 |
| V10 | T04 / 数据校验与人工审核 | 20 题、split、fixtures、预期与 rubric | 16 dev/4 holdout；七维度覆盖；审核人与版本齐全；无秘密 |
| V11 | T05 / 单测 | 错产物、错误参数、缺审批副作用、合法替代工具 | 相关硬规则判 fail；合法路径不误判；模型不能覆盖事实 |
| V12 | T05 / 契约 | TOOL/RETRIEVER spans、input_parameters、多轮乱序、缺 Trace | 映射正确；有序会话；必需证据缺失为 error |
| V13 | T05 / 真实模型 | 对所有启用语义指标运行代表题并人工复核理由 | 真模型评分有效；方向/阈值明确；不支持指标有明确处置 |
| V14 | T06 / 单测 | pass/fail/not_applicable/error 与分母、基线快照差异 | 退出码及 gate 正确；未执行和 error 阻断；不可比版本拒绝比较 |
| V15 | T06 / 故障注入 | 裁判超时、Trace 延迟/丢失、上传失败、预算超限 | 有界结束；本地事实保存；重传不再次执行 Agent |
| V16 | T06 / 集成与页面 | 打开实际实验、Assessment、对比入口 | 正确显示样本、理由、源 Trace、失败和用量；链接真实有效 |
| V17 | T07 / 真实模型 | 3 题 smoke 后，16 题 dev 同配置执行 3 次 | 完整记录每题通过次数、均值/标准差/范围、成本/时延；不承诺绝对复现 |
| V18 | T07 / 人工校准 | 复核 rubric、首轮语义结果及失败/分歧；冻结阈值 | 记录误判与修正；规则/裁判版本固定；候选运行后不改门槛 |
| V19 | T07 / 真实对比 | 单变量基线/候选；已知错误检出；holdout 冻结 | 展示真实变化及回归；不要求预设涨分幅度，不把故障变体叫真实优化 |
| V20 | T08 / 本地门禁 | 普通 PR 无密钥测试；可信 runner 真实 smoke | PR 无外部模型调用；真实 CI 退出码、预算和报告可核验 |
| V21 | T08 / 集成与人工审核 | 候选收集/去重/脱敏 → 人审 → 新题库版本 | 未审不能发布；原版本不变；期望不是从失败输出自动复制 |
| V22 | T09 / Final E2E | 最终版本运行 20 题，含真实 xiaok 与百炼知识链路 | 无漏题/必需评分 error；完整证据；质量失败明确反映且不冒充 Agent 达标 |
| V23 | T09 / 安全与撤销 | 隔离项目 ACL、审批、取消、停评测后的业务回归、资源清理 | 无跨项目泄漏或未授权写；无遗留运行；取消 CLI 不影响其它服务 |
| V24 | T09 / 静态与回归 | 扩展测试/lint、相关业务测试、上游保护及秘密扫描 | 当前改动检查通过；未改前端不虚报前端测试；无新增核心污染 |
| V25 | T10 / 复用演练 | 按指南增加临时合成用例、执行、查看报告 | 无需修改核心 runner 即可加题；指南命令可用；复盘有实际证据 |

## 3. 真实测试配置与证据清单

### 环境记录（T00/T01 填写）

| 项目 | 当前状态 |
|---|---|
| EvalFlow / 业务源码版本、dirty 摘要 | 由每次 Run manifest 记录；两个 worktree 保持未提交状态 |
| MLflow / DeepEval 实际兼容组合 | Python 3.13、MLflow 3.18.1.dev0、DeepEval 4.3.4；T00真实探针通过 |
| xiaok 被测/裁判模型 | deepseek-v4.1-flash，真实调用完成 |
| 百炼模型与维度 | text-embedding-v4，1024维，真实嵌入通过 |
| 隔离业务栈、EvalFlow 存储与环境 ID | 已登记所属隔离Worktree；运行证据位于各自 `.local-stack/` |
| 首期题库/fixture/索引哈希 | v1共20题，哈希记入manifest；索引为固定合成语料 |
| 全量预算与质量阈值 | 累计费用不限；单次超时/重试有界。门禁按预先冻结配置执行 |
| 本地门禁 | pytest、Ruff、local-stack guard 与真实CLI已执行；第一版无真实CI |

### 每次执行必留

- run manifest、冻结题库引用、逐题 evidence 和 metric results、汇总报告、门禁结果与退出码。
- xiaok 被测/裁判、百炼嵌入的脱敏调用凭证（响应 model、时间、请求 ID/用量等；不含 Key）。
- Platform Thread/Run 与 MLflow Trace/Experiment 链接或 ID，实际环境地址在私有运行记录中管理。
- 固定 fixture 的前后快照/哈希、产物检查与取消/审批证据。
- 有适用权限的脱敏产物目录及保留期；公网文档不附带原始私有数据。
- 模型、网络、采样、价格、工具 fixture 替换等影响结论的限制。

### 拟执行命令

以下在 EvalFlow 仓库内执行；实际配置路径由 T01 产生，不写死生产 IP：

```bash
uv run pytest tests/eval_platform/
uv run ruff check eval_platform/ tests/eval_platform/
make guard
uv run python -m eval_platform.run preflight --config "<private-config>"
uv run python -m eval_platform.run regression --config "<private-config>" --suite smoke
uv run python -m eval_platform.run regression --config "<private-config>" --suite all --baseline "<baseline-run-id>"
```

若实际复用的仓库 lint/测试指令不同，开发时更新为真实命令。业务侧仅在代码变更时执行对应服务检查，完整链路仍须经过真实 Platform API。

## 4. Phase 验证记录

### 2026-11-13 — 方案修订与静态调研（开发前）

- **范围：** 文档和本地只读核对，不是产品验证。
- **已核对：** 两仓库已有网关/Trace/DeepEval 源码、会话评分输入限制、锁版本；本地 EvalFlow 元数据查询显示 mlflow 3.18.1.dev0、deepeval NOT_INSTALLED、eval_platform 目录不存在。
- **资源检查：** ~/.my_best/.env 存在；只输出相关键名与经过白名单校验的非敏感模型名。xiaok 默认模型 deepseek-v4.1-flash；百炼相关键存在，值未输出。
- **文档调整：** 明确 EvalFlow 主导、两模式执行、内部数据契约、隔离、真实模型来源、20 题、T00–T10、V01–V25 与经验交付。
- **未执行：** 模型调用、嵌入、依赖安装、服务启停、产品单测/集成/E2E、CI、生产修改。
- **文档结构/链接/一致性检查：** 已执行 Python 静态检查：四份文档代码围栏闭合、相对链接存在，T00–T10 共 11 项开发任务、V01–V25 共 25 项验证、20 个唯一 case ID 均通过；六份涉及文档与资源文件秘密值的比对扫描通过（不输出秘密）；git diff --check 通过。项目目录原为未跟踪文件，额外检查其文本，不依赖 Git diff 覆盖新文档。
- **判定：** 当时规划完成、开发未开始。后续开发和Final结果见下方独立记录。

### 后续 Phase 记录格式

每阶段追加日期、任务 ID、验证 ID、实际命令、脱敏证据路径、结果与未完成项。无真实结果时保留“未执行”，不能复制计划中的预期结果当作实测。

## 5. Final 验证记录（独立区块）

**状态：本地首期交付完成；Agent 质量门禁未通过。** 真实 CI、生产发布和新一轮盲测集为明确后置范围。

- [x] 实际模型、依赖、题库快照及隔离环境均有真实运行记录；敏感配置值未进入仓库。
- [x] EvalFlow 单测、Ruff、local-stack guard 与真实 API/Trace、MLflow 发布链路通过；Final 收尾复跑结果附记于下方。
- [x] 20题 dev/holdout均完成主动运行及评分；无评测系统 error，必需证据可关联。开发集 M01、holdout M03 的 KnowledgeRetention 质量失败如实保留。
- [x] 历史重评分与主动回归均闭环，覆盖单轮、多轮、审批、取消、检索。
- [x] rubric校准、候选比较、Badcase审核发布与扩展示例有真实记录。
- [x] 本地CLI门禁真实运行；真实CI按用户要求后置。
- [x] EvalFlow页面可查看运行、Assessment与Trace，关键截图已存入 implementation/。
- [x] 题库为合成数据，隔离资源已核对；凭据扫描不输出敏感值。
- [x] T10复盘与可复用指南已完成；新增经验提案见 implementation/04-curation-and-guide.md，待用户确认后再写入 lessons。
- [x] 未完成项已明确：真实CI、生产发布、新的未暴露holdout后置；当前质量失败意味着不能宣称Agent达到发布标准。

**项目状态：done（首期本地评测体系交付）；业务 Agent 发布结论：不通过/未达标。** holdout曾用于诊断裁判截断，非完全盲测，后续门禁需重新冻结未暴露题集。

### 四态口径

- **done：** 本期评测体系范围全部交付且上述 Final 条件满足；如 Agent 业务质量未达标，必须单独明确“不具备发布门禁通过结论”。
- **partial：** 已有部分可验证成果，但剩余任务仍可推进；属于过程状态，继续工作。
- **blocked：** 必需条件确实缺失，已完成不依赖部分并列明尝试、剩余任务、所需条件；例如本地门禁 凭据或人工题库审核尚不可得。
- **deferred：** 用户明确推迟的范围；首期已定义的后置功能不计为漏交，不能在开发中擅自将必测项改为 deferred。

## Phase 验证记录：T00（2026-11-13）

真实xiaok JSON=5、百炼text-embedding-v4维度1024、MLflow/DeepEval TaskCompletion=yes。
Dearflow单轮completed、1条Trace精确关联；详见implementation/01-compatibility.md。
此记录不属于Final；开发前规划判断已被下方实际记录取代。

## Phase 验证记录：T01–T10（2026-11-13）

- **范围：** EvalFlow 扩展、隔离业务Worktree、20题数据集、真实基线、Badcase流程和复用指南；业务 Agent 服务源码无修改。
- **真实执行：** xiaok `deepseek-v4.1-flash`；百炼 `text-embedding-v4` 1024维。三次16题开发集及4题 holdout均完成；三次开发集门禁为0、0、1，holdout门禁为1；无评分系统错误。唯一质量失败为 KnowledgeRetention 的 M01/M03，详细分数和误判风险见 [校准报告](implementation/03-baseline-calibration.md)。
- **实现证据：** [运行链路](implementation/02-evalflow-runtime.md)、[校准报告](implementation/03-baseline-calibration.md)、[Badcase与指南演练](implementation/04-curation-and-guide.md)。浏览器截图含 EvalFlow 运行、Assessment和发布页面。
- **限制：** holdout曾用于诊断评分器截断；不得声称完全盲测。没有真实CI或生产发布；二者为用户明确后置。Agent质量门禁失败不影响评测体系能够报告结果的交付结论。
- **收尾检查：** 2026-11-13复跑 `rtk .venv/bin/pytest tests/eval_platform -q --confcutdir=tests/eval_platform`：33 passed；数据集哈希断言包含在测试内。`rtk .venv/bin/ruff check eval_platform tests/eval_platform`、`rtk bash scripts/local-stack.sh guard`、两仓 `rtk git diff --check` 均通过。pytest 有 pytest-asyncio fixture loop scope 与隔离命令未加载 timeout 插件两项配置警告，不影响本次测试通过；后续可在扩展测试配置时消除。

## 多Agent与评测集管理 Phase 验证

计划：原生Dataset多轮/fixture/评分字段无损导入；冻结版本不随编辑改变；配置变更和无权限拒绝；同集两个Agent、同Agent两个集；原生页面浏览、启动与比较；既有幂等/取消/重启回归。Final在D01–D06完成后单独记录。


### D01 Phase（2026-11-13）
真实原生20题导入后逐字段相等；API实际创建路径为/create，实验关联单独查询；Agent唯一约束证实后用户明确选择同一Agent多份配置。

### D02 Phase（2026-11-13）
原生列表显示两个集合三个版本；browser-skill完成v1→v2草稿→发布以及新集合粘贴导入/发布。真实修改发布记录后frozen()拒绝，冻结副本不变且恢复成功。导入响应丢失、不重复创建、旧版本不受新草稿编辑影响、非法ID和跨实验拒绝均有单测。


### D03 Phase（2026-11-13）
真实Agent配置变更→assert_unchanged拒绝，恢复后通过；Runtime首轮与审批恢复的温度0/0.3经GET Run验证。未适配graph/异项目/禁用模型/缺fixture测试通过。Runtime源码哈希与资源快照保留；外部供应商不保证不可变版本。

### D04 Phase（2026-11-13）
同集两配置、同配置两集合均真实passed；最终日期用例passed；新版任务取消0/2→cancelled；重启后同UUID返回原任务passed。详见外仓22/23/25证据。

### D05 Phase（2026-11-13）
browser-skill完成原生页面完整路径并保存截图18–26；原生数据集列与双Run比较复用。异集合比较明确警告；缺指标NaN改为破折号。文件上传bsk工具控制上下文错误，未提交；同入口粘贴导入真实通过，文件选择另有组件测试。

## D06 Phase（2026-11-13）

后端64项通过，最终资源哈希改动后目标配置6项补跑通过；前端共25项（任务3、导入1、原生详情路由17、比较条件3、空指标1）。主/shared TypeScript、范围ESLint、Ruff通过。最终构建成功，使用DISABLE_ESLINT_PLUGIN=true绕过既有全局formatjs/no-id基线错误；不宣称默认全局lint通过。日志在EvalFlow .local-stack/datasets-{pytest-final,target-final,jest-final,binding-test,empty-score,tsc-final,eslint-final,build-final}.log。截图28确认异题库比较警告和空指标“—”，浏览器会话已关闭。

## Final：D01–D06评测集与具名配置扩展（2026-11-13）

- 四态判定：**done**（本地已批准范围）；D01–D06全部完成，与既有首期Final独立。
- 原生20题完整导入、冻结发布、新草稿/版本；三个逻辑集合、四个发布版本集中查看。任务绑定同一Agent两份具名参数配置，结果关联版本、配置及原生Trace/比较。
- 真实模型：基础集温度0为2/2、综合集smoke为3/3、浏览器启动温度0.3为2/2、最终日期集为1/1；另有版本化任务cancelled 0/2。审批恢复后实际参数分别保持0/0.3。均使用授权xiaok模型；这些冒烟结果不替代20题完整质量基线。
- 真实边界：冻结原生记录篡改被拒绝；Agent配置漂移被拒绝且已恢复；缺fixture被拒绝；重启后同UUID返回原任务不重复跑。
- 证据：EvalFlow docs/projects/20261113-evaluation-task-ui/implementation/22、23、25 JSON及18–21、24、26、28截图；完整索引27-dataset-profiles.md。26为修复前历史图，最终空均值修复以28为准。
- 限制：文件选择路径组件测试通过，bsk上传控制上下文失败，真实导入使用JSON粘贴；冻结registry/profiles必须与MLflow数据一起备份；外部无版本API资源不保证完全不可变。真实CI/生产发布/多实例与任意graph支持不在本期。未提交或推送。
- 文档：两仓状态、操作指南、功能及变更记录同步；无本项目对应draft标准需毕业。新增经验仅提案，等待用户确认后沉淀。

最终上游guard通过，mlflow/零修改；两仓git diff --check在修正文档末尾空行后通过。

## M01 Phase：主分支合并复验与清理（2026-11-13）

主工作区复跑后端64项、前端8套件39项，主/shared TypeScript、Ruff与guard通过。两仓与已验证分支代码一致，Agent旧业务源码及EvalFlow上游不变；早期方案保留在Git父提交，独立指南哈希一致。两Worktree及专属数据已删除，PG其他库/角色清单相等，7端口释放。

## Final：M01合并收尾（2026-11-13）

判定done（Git集成、本地复验与测试资源清理）。经验已写入EvalFlow经验库；两feature分支已推送，main实现已推送，最终收尾文档随本轮提交继续推送并核验。原开发环境已销毁，历史本地Run链接不可用；截图和脱敏JSON保留。未重跑真实模型/浏览器，合并代码与此前已验收版本完全一致；未部署生产。详见[合并清理记录](implementation/12-merge-closeout.md)。

## A01–A04 验证计划（2026-11-13）

初始化重复执行不增加项目或模型；显式项目ID错误/多同名/资源冲突安全拒绝；缺失Worktree配置不得回退主目录。fixture仅改变目标项目绑定，动态知识/上传与其他项目设置逐字段保持；实际业务test项目Agent与策略前后相同。主环境真实运行基础/审批与知识用例；浏览器看到专用项目、冻结题库和两配置入口。开发单测使用tmp资源；真实验证写专用项目，历史首期Final不替代本扩展验收。

## A01–A04 Phase验证记录（主环境扩展，2026-11-13）
- A01：正式API建/复用项目、项目专属模型；用户确认刷新可见；两原生数据集20/5题导入冻结通过。
- A02：主环境/Worktree路径、身份、幂等、冲突测试与真实重复初始化通过。
- A03：scope/平台binding/MCP初始化检查通过；test项目Agent/模型/Graph/工具策略快照完全一致，其他env配置保留。
- A04进行中：主环境真实模型/嵌入/DeepEval探针通过；browser-skill启动5题任务并查看失败证据。远端沙箱TLS受准入阻塞，真实Agent成功链路尚未通过；此为Phase记录，不是Final。
- 证据：EvalFlow页面专项implementation/30–34；脱敏汇总34-primary-project-evidence.json。私有完整报告位于EvalFlow .local-stack/results/95fe2a8b75104c01a614f525796128a8/。

A04当前blocked：75项后端测试、9项前端测试、TypeScript/范围ESLint/Prettier/Ruff/guard通过；真实模型探针和配置保留核对通过。远端抓包确认新源IP未准入，安全策略未擅自改动；无本扩展Final通过结论。
