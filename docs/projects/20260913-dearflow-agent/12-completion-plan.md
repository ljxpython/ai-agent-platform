# 迁移补齐与重新交接计划

## 目标

在已有三服务与官方DeepAgents/GraphHarbor底座上补齐可验证的Agent能力，先收尾旧承诺，再选择新增范围。沿用原专项，不另起一套重复项目。能力全集见 [11](11-20260928-capability-reassessment.md)，逐项验收见 [13](13-verification-baseline.md)，机制与效果差距见 [14](14-effect-parity-and-reliability.md)。同名能力不能作为效果等价或完成证明。

## 方案设计

### 分级、边界与复用

整体仍为**治理改动**：涉及跨服务契约、执行隔离、凭据与外部计费副作用。此轮仅完成分析和规划，未修改业务代码、依赖或数据库。原批准的单份Skills、共享Chat、本人项目记忆等继续生效；本计划新增安全行为/预算语义/媒体后台调度等不由AI自行批准。

1. `services/dearflow_agent/agent.py` 保持唯一组合根；图入口薄导出。官方已提供的摘要、文件工具、SubAgent、HITL继续复用。
2. Dear独有能力先留私有 `tools/`、`middleware/`；文件/媒体已有真实多个消费者才扩展公共 `workspace/`。不新增通用Builder、Agent循环或能力注册中心。
3. Platform负责ACL、受信Context/资源引用、网关和审计；Runtime负责业务执行与应用数据；GraphHarbor持有执行状态。新增引擎需求先做最小官方API Spike，不向发布包注入Dear业务。
4. 前端沿用 `modules/chat` 的同一SDK controller；Dear保留产品页面。普通发送、审批resume、执行中入队保持三个动作，不用新消息假装恢复审批。
5. 不接入deerflow-harness、它的Gateway/RunManager、全局配置、用户体系。上游Skill脚本逐项审核、记录provenance/license/行为差异；不复制本地未提交修改却声称来自某commit。
6. “上传/预览/下载/理解/生成”分别验收。客户端显示能力不授予权限；没有工具、凭据或供应商时给出真实限制。

### 三批交付与依赖

| 批次 | 范围 | 出口 |
|---|---|---|
| B1 现有能力收尾 | T01—T05＋T07关键可靠性切片 | 优先闭合14/E01—E07响应终止、空回答、错误完成、重复调用、预算与Todo缺口，再验现有业务；已迁19项逐项有结论 |
| B2 长任务与效率 | T07剩余长上下文/证据连续性、T08（经评审选择切片） | 长任务不丢要求、证据可核验；技能/MCP选择有实际测量与授权负例；远端计费恢复随T06验收 |
| B3 业务扩展 | T06、T09中获批项 | 音视频或其他新增场景独立可交付，不等待全部上游周边功能迁完 |
| Final | T10 | 本期选定范围全链路、安全/故障/恢复/回滚证据齐全，人工业务验收完成 |

T01为共同前置；T02为每项用户旅程提供底座；T03和T07的关键可靠性项先解决再开对应E2E。T04研究/图表与T05记忆/Skills可分别验收；T06须复用前述响应/证据门禁，不等待T07所有效率优化；不能为了音乐生成先建设Goal/定时/批处理。T09是范围选择，不是默认实施清单。

### 待人工评审的具体决定

| 决定 | 建议 | 可选范围及代价 |
|---|---|---|
| D7 本期完成定义 | 先完成B1并选最必要B2；B3独立批次 | 若要求23项全量，K14—16和K23必须明确纳入，外部供应商与桥接产品均需验收，不能继续写deferred又声称23/23 |
| D8 媒体优先级 | 按旧需求先视频/大文件；播客音乐分别排期 | 选择供应商、计费预算、取消承诺及保留时间；接口不可查询时只能保留unknown并人工对账 |
| D9 子Agent权限 | 保持只读研究；仅真实需要才新增专用数据/编码角色 | 不开无边界bash子Agent；父取消、子结果验收、独立取消是否需要分别确定 |
| D10 运行预算 | 区分默认预算和平台硬上限；硬上限取更严值 | 现有max不是硬上限；thread总限10个task是否保留也须明确，不能擅自改授权/成本策略 |
| D11 完成核验 | 先做工具返回事实与交付物核对 | 不先造通用审判LLM；无法确定的条件标unverified，真实通过才done |
| D12 上游周边 | 浏览器/IM/TUI/ACP/插件宿主继续不纳入B1 | 重新纳入时有独立安全与产品方案；Goal/定时/批处理亦不默认启动 |

### 契约与数据变化原则

- B1优先使用现行 `execution_mode`、`access_policy`、capabilities、七类Skills接口、MemoryView、files/artifacts、checkpoint_ns，不为对照上游改现有协议。
- 若能力展示需增加“不可用原因/支持操作”，由Runtime生产、Platform投影、Web消费，先写请求/响应和403/409/422/503语义；不能只给前端造字段。
- T07核验信息优先附着工具结果/现有事件允许的字段，先检查公开SSE脱敏和SDK保留能力；checkpoint仅保存必要业务状态，不另建Run镜像。
- T06若新增远端任务：Runtime应用表保存provider/task引用、幂等键、审批内容digest、状态、结果引用；Platform只做受控投影。新operation/claims/模型资源绑定需双端矩阵；媒体Range、大小上限、下载授权须同时修改两端运输层。
- `docs/standards/error-envelope.md`、`trace-propagation.md` active；JWT/SSE仍draft，缺口继承原专项。规范与当前安全/权限行为冲突须人工决定，不在此规划中宣布解决或毕业。

## 任务拆分（本轮之后的接续进度事实源）

标记仅表示本任务是否满足验收。后续专项拥有的实现不复制勾选，以对应任务和当前证据接入本表。估算是单人有效工程日，包含本切片验证，不包含外部等待/审批；T01后校准，非排期承诺。

### T01 基线与交接冻结（1—2日）
- **改动内容：** 固定当前发布包/工作树/配置开关；建立每项“实现、可用条件、最近证据、责任任务”表；核实服务真实配置。协调其他开发者避免审计中变更源码。
- **代码位置：** `apps/runtime-service/uv.lock`、`langgraph*.json`、`services/dearflow_agent/capabilities.py:graph_capabilities`、`docs/local-deployment-contract.yaml`、本专项11/13。
- **预期结果：** 同一快照可复现；证明供应商不可用与实现缺失不同；原READMEs不再用于整体完成判定。
- **验证项：** 记录三服务版本、Graph/Agent绑定、开关是否开启（不记录密钥）、源码摘要；核对19/23映射及license；schema探测无I/O。
- **状态：** [ ] 待接续（本轮已完成静态基线，真实部署态未冻结）。

### T02 Dear用户旅程联合验收（2—4日）
- **改动内容：** 补Dear入口真实浏览器用例，复用现有Chat状态与网关；根据失败定位最小修复。
- **代码位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`、`modules/chat/components/ChatSession.vue`、`modules/chat/composables/useChatSession.ts`、`modules/chat/components/SubtaskDetail.vue`；API `modules/runtime_gateway/presentation/http.py`；Runtime `middleware/clarification.py`、`messaging/`。
- **预期结果：** 四模式→上传→追问→审批→工具→成果→刷新/分叉；Ultra两研究子任务历史可回放、取消无串线；补充消息入队可消费。
- **验证项：** V01—V04；复用post37历史修复并实测Dear入口；分别覆盖父取消、断流恢复、两个同角色任务及撤权后的resume。
- **状态：** [ ] 待接续。不得把Chat通用单测计为Dear产品E2E。

### T03 核实并修复可用性/预算差异（2—4日）
- **改动内容：** 对预算上限、思考模型支持、图片输入、能力展示逐项复现；先明确语义再修。明确网页prompt与已实现预览的行为；检查未验公共技能的推荐标签，不改变已批准“全部只读可见”。
- **代码位置：** Runtime `services/dearflow_agent/agent.py:get_agent`、`modes.py:apply_reasoning`、`skill_catalog.py:VERIFIED/public_catalog`、`prompts.py`、`middlewares/images.py`、`runtime/modeling.py`；前端 `modules/chat/components/ChatRunOptionsDialog.vue`。
- **预期结果：** 调低硬上限确实收紧；不支持的模型参数可解释；图片理解不能只暴露上传按钮；技能可见/可用/已验清晰分开。
- **验证项：** 用真实组合根测试env=5/模式=100等边界、图重建与长thread预算；不同模型参数请求记录；图片上传→模型实际识别；关闭凭据/开关时前后端一致。
- **状态：** [ ] 待评审预算语义后实施。14/E06已用真实组合根复现env=1仍执行3次模型调用；不再仅为静态疑点。当前test_limits_config只测helper和默认数值，不证明硬上限。

### T04 K01—K13现有业务闭环（5—9日）
- **改动内容：** 按11的每个K补齐当前真实模型、工具供应商和浏览器证据；仅修复复现失败；K03/K05不先换实现绕开历史限流，K09补26图型，K12补多图。
- **代码位置：** Runtime `services/dearflow_agent/tools/{search,github,arxiv_search,media}.py`、`skills/`、`tools/chart.py`、`workspace/media.py`；`tests/e2e/test_dearflow_skills.py`、`tests/services/dearflow_agent/test_platform.py`；前端成果/工具展示。
- **预期结果：** 每项有输入/工具/产物/内容断言/负例/版本，不用一个“研究成功”替代13项。
- **验证项：** V05的逐K矩阵；图表数据与报告来源正确，图片/PPTX可下载且字节校验；缺凭据/429/unknown如实分类。
- **状态：** [ ] 待接续；历史供应商问题保持“历史待验”，不是本轮已确认blocked。

### T05 K17—K21和记忆/Skills新方案收尾（3—5日）
- **改动内容：** 沿用20260919、20260920批准方案；完成F02、R08/V03及Dear浏览器联验。补远端精确commit导入；不复活候选发布/多版本回滚。
- **代码位置：** Runtime `skill_governance.py:SkillStorage`、`middleware/skills.py:ExecutionSkillsMiddleware`、`tools/skills.py:import_skill`、`memory.py:MemoryStorage`、`memory_access.py`、`middleware/memory.py`；API skills/memory网关；Web `services/dear-agent/`与记忆/技能页面。
- **预期结果：** 无线程管理、409保留草稿、更新/停用/删除后新run采用最新内容，旧interrupt恢复保留快照；候选需采纳，共享线程无私人记忆。
- **验证项：** V06/V07；两用户两项目隔离，执行中分享竞态、清空epoch晚到、PG短断降级；远端导入不运行脚本。
- **状态：** [ ] 待接续。既有CRUD/HTTP/PG单测代码已经存在。

### T06 媒体与部署（分支独立验收，约10—18日，范围批准后细排）
- **改动内容：** 先验K22静态部署；若纳入K14—16，逐供应商交付submit→receipt→status→artifact，支持有界下载/Range。动态网页部署单列，不把静态成功视为全框架支持。
- **代码位置：** Runtime `tools/media.py:build_media_tools`、`external_task_storage.py:ExternalTaskStorage`、`tools/deployment.py:build_deployment_tool`、`workspace/media.py`、`workspace/artifact_refs.py`、`http/workspace.py`；API `runtime_gateway`和下载adapter；Web `modules/dear-agent/pages/DearAgentArtifactsPage.vue`及共用预览；必要迁移在Runtime `db/migrations/`。
- **预期结果：** 持久供应商任务与Run关联；unknown不重复付费；重启可对账；音视频真实播放/下载；仅审批批准内容可上传。
- **验证项：** V08；提交ACK丢失、重复请求/通知、取消竞态、撤权、worker退出、文件不完整、Range206/416、跨租户下载负例；真实供应商计费调用需事先确定测试预算。
- **状态：** [ ] 候选范围待评审；K14/K15/K16原deferred不自动转为实施。K22真实发布属于单独明确授权的外部写动作。

### T07 任务连续性、结果核验和可靠性（4—8日）
- **改动内容：** 按14第6节先补模型length/safety终止、空终态、错误/重复无进展及完成证据；这部分进入B1。之后验证并补压缩后关键要求、子任务停止原因、来源连续性与文件日志回读。继续复用官方摘要/历史工具调用修复，避免复制所有上游Middleware。
- **代码位置：** Runtime `services/dearflow_agent/agent.py`、`prompts.py`、`middleware/`（新增业务核验模块仅在测试证明需要时）、`subagents/researcher.py`、`workspace/artifact_refs.py`；Web共用ToolResult/轨迹展示。
- **预期结果：** 工具失败不能被最终回答当成功；引用来源可回查；未完成清单/不确定核验可见；压缩不丢来源和用户追加约束；只读附件枚举有明确预算。
- **验证项：** V09；伪造“done”、未执行工具却报已创建文件、错误退出码、空响应、length截断调用、同失败循环、长上下文恢复；先确定性断言再真实长任务。
- **状态：** [ ] 待评审切片后实施。14/E01—E05、E07已复现，不再记“待核实是否有缺口”；响应终止应覆盖主/子Agent，组合测试确认Safety/限额/Todo/loop不会互相重新触发。权限/PII/注入规则变更必须人审，不凭上游名字判定缺陷。

### T08 Skills/MCP按需选择（2—5日，度量后选择）
- **改动内容：** 明确显式Skill选择、实际使用快照是否要产品化；若工具schema或目录tokens已成为瓶颈，再补延迟发现。任何allowed-tools只收紧平台授权，不授予新权限。
- **代码位置：** Runtime `middleware/skills.py`、`tools/mcp.py:load_mcp_tools`、`capabilities.py`、`runtime/resource_bindings.py`；API run Context白名单及签名；Web ChatComposer/ToolResult。
- **预期结果：** 用户显式选技能可解释、历史使用可查；发现/可见/执行均受当前授权；秘密值不进入prompt/浏览器/日志。
- **验证项：** V10；目录tokens前后比较、不存在/停用Skill、更新后历史快照、未知MCP名/撤权/重名工具；未证明收益不引入新检索层。
- **状态：** [ ] 候选待评审；当前没有要求就不构建secret管理/市场。

### T09 新版上游范围决策（0.5—1日评审；开发不在此估算）
> 2026-10-10：A31/F17 的代码评估与前端交接已完成，用户确认本期不开发自建知识产品；未来有真实服务后优先复用知识 MCP，见 [专项](../20261010-agent-knowledge-retrieval-assessment/README.md)。本次不启动知识接入，不改变 T09 其他候选项和原专项总体状态。

- **改动内容：** 对A13/A19/A25—27/A31—37、K23逐项选择纳入/延期/不做；纳入后单独形成最小方案和契约Spike。
- **代码位置：** 当前无待改代码；仅评审本专项D7—D12。未来执行业务留Runtime，授权留Platform，通用调度先查引擎现成API，页面留Web。
- **预期结果：** 需求清单完整但有边界；不会把项目资料架当IAM项目，或用普通task冒充batch，或继续保留含糊的“全部迁移”。
- **验证项：** 每项选择有理由、验收场景、责任服务、权限/数据影响；新选项实施前补精确文件/符号与独立测试。
- **状态：** [ ] 待人工范围决定；不借本轮分析自动启动这些功能。

### T10 Final验收、运维与交接（3—5日）
- **改动内容：** 汇总各任务后执行当前范围全量回归、生产等价Docker隔离、恢复/回滚演练；更新功能总览与当前标准。已有JWT/SSE/业务边界专项的未验项按原任务接续。
- **代码位置：** 当前两服务tests、Web e2e、Runtime `deploy/Dockerfile.agent-workspace`、根启动/部署配置、`docs/standards/`；详细证据落本专项13或后续implementation。
- **预期结果：** 可向下一位维护者交付能力表、配置前置、可复现命令、故障定位和回退步骤；不以本地local测试替代生产隔离。
- **验证项：** V11/V12；两租户隔离、真实worker重启、DB故障、积压/容量、内存/磁盘上限、关闭功能后通用Chat回归、隔离库恢复；生产实际发布另行授权。
- **状态：** [ ] 待各纳入任务完成。

## 验证要求与记录

本轮完成了11能力矩阵、当前实现入口、T01—T10、D7—D12、13验收设计及14机制/效果审计。原粗估B1为13—24工程日、B2为6—13工程日、Final为3—5工程日；14确认可靠性缺口后，T07切片提前且须补主/子Agent组合与配对效果测试，原分批估算不再作为排期依据。T01后按获批切片重估，不含T06及未定新版范围、外部等待；不按“19/23个目录”估完成率。

每个阶段使用implement-feature记录实际变化，verify-change记录阶段验证；Final独立。失败先分类为实现、配置、供应商、引擎或证据过期，再派生修复任务；不要见旧blocked就重复写工具。

## 状态

规划已交付，新增治理实施范围待人工评审。以上未勾选项是后续开发/验收任务，不表示本轮分析未完成；尚未获得本计划新增范围的实施批准。
