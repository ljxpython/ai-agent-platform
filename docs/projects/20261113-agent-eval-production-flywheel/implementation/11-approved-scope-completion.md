# 本轮剩余功能实施与阶段验证

2026-11-14，双 Worktree `344c`，仅本地合成资料。关联任务 1.1、1.5、2.0–2.4、3.2、3.4、4.0–4.3；本记录仍是阶段记录，不能代替联合验收。

用户批准以 AI 评审替代本轮人审。循环干预、正式性能、CI、独立盲测结论、缺网关说明的真实自动抽样启用继续暂缓；抽样保持 0，生产未变更。

## 初期结果与当时缺口（历史）

- 文件读取：仅在权限、路径检查通过且文件确实不存在时返回 `file_not_found`。符号链接、无权限及 I/O 故障不能伪装成缺失。新增测试最初 3 项失败，修复后连同本地文件兼容测试 12 项通过。
- 执行回执：新增 Worker 持久记录，绑定实际 API/Worker 源码、依赖、运行身份与配置，避免取消后没有 Trace 就无法核对版本。第一轮真实回归 `ecca0ebf8c3a4b258bf56f702a42890c` 中，读取、取消、审批写入行为符合预期，但回执缺失，门禁正确返回错误，不能算验收通过。
- 回执接线修复：API 版本信息改为在真正提交 Run 时写入；审批恢复仅继承原 Run 的评测标识。采集移到 Worker 执行图工厂，核对原生运行记录，避免节点执行标识与业务 Run 混用。第二轮 `71c8f08fc26c43208f16151dc81425c2` 的四个 Run 已保存回执；校验暴露了 `sha256:` 前缀处理错误，门禁仍未通过。格式修复和完整配置快照核对正在复验。
- 执行回执最新验证：`c836f36b03c04d55bddc872c7a1f089a` 的JSON读取、取消、审批写入三题均通过，整体gate 0；核对实际API/Worker及完整配置快照，取消无Trace仍有持久回执。保留 `budget_policy_not_configured`，不宣称正式预算门槛通过。
- AI 评审：已阅读全部 20 个候选及 5 个种子，接受每组一题，共 5 题；其余 15 题因同义表达冗余拒绝，不把改写数量当新覆盖。已原生发布 `d-a62176fdf18a4ed4beed1943a20b6ac1`。第一次执行因候选文件顺序与已发布版本不同，内容校验拒绝；改用冻结快照复验，不放宽版本完整性校验。
- 前端默认构建曾通过，保留 bundle size/Browserslist 警告。之后质量汇总页面又有修改，最终仍需按最新版本重测，不能沿用旧构建结论。
- 源端合成导出已实现到期清正文、撤权清正文、90 天删除导出墓碑，并限定新政策与指定项目；相关反馈、巡检、诊断范围测试 68 项通过。EvalFlow 原生内容、任务快照与日志清理正在补实际数据库测试，完整备份恢复尚未完成。

## 失败与证据位置

全部日志在所属 Worktree 的 `.local-stack/`，不提交私有配置和原始正文。

Agent：`phase-completion-file-red.log`、`phase-completion-file-green.log`、`completion-runtime.log`（21 通过、1 跳过）、`completion-platform.log`（29 通过）、`completion-retention.log`（68 通过）。

EvalFlow：`completion-core-ready.log`、`completion-core-receipts-ready.log` 保存上述两次未放行回归；`completion-reviews.log` 的三项失败为新增 UUID 校验测试替身不真实及人审文案断言未更新，修复后 `completion-reviews-green.log` 为 23 通过。配置快照校验另见 `completion-configuration.log`。

更早一次 `128617100840407eafd2729ba2ccbd49` 在服务重启未完成时启动，未取得 Run，且执行期间源码变化；这是无效验收尝试，保留失败证据，不算功能通过。

## 初期接续事项（已由下文验证）

本记录按实施顺序保留历史失败与修复，初期的‘待执行/正在复验’不是当前进度。资料生命周期、多存储隔离恢复、五题回归、评分对照、安全场景与前端截图现已补齐；当前进度以四专题任务为准，联合验收单独记在专题04。

浏览器最初缺少Basic认证；用户批准后通过原生API重置本地flywheel-reviewer密码，已验证登录成功且仍非管理员，凭据仅留私有目录，未写入项目文档。

## 本轮补充检查

- EvalFlow后端阶段全套332项通过、2条警告；源端生命周期及审计清理范围39项通过。
- 质量汇总畸形停止回执、审批项和反馈包新增测试先出现5项失败；修复后8项通过、1条警告，缺失证据计入报告缺失，不让整页异常。
- 前端两个相关组件7项通过，类型检查退出0；保留React警告，已局部调整Modal子节点，正在复验及最新默认构建。
- AI评分对照：历史三个安全案例共6次结果，以及四个正反对照共8次评分，与本轮AI标签一致。这是开发诊断，不是独立人工校准，也不是本轮重新调用模型所得结果；多轮、缺资料与既有KnowledgeRetention分歧仍需处理。

## 2026-11-14 后续实测

- AI五题回归 `568388690fc54b4aac268dd4e5e2ea1f`：5/5、gate0，无warnings，11请求/117652 Tokens；截图56显示非管理员原生结果。
- 默认前端最新构建退出0；质量汇总3项组件通过。截图57保存分母、取消与缺证据提示。
- 生命周期边界测试最终10 passed/2 warnings：任务JSONL、Trace归档路径、跨实验拒绝、当前授权期限和清理失败隔离。真实多存储恢复尚待执行。
- 七题首次 `5fb8628110c94ff7b733927ea314630a` gate2：CSV新建额外请求present_artifacts被拒绝；CSV编辑结果正确但旧审批规则误判；MCP服务命名使工具未装配。多轮正负与跨项目拒绝通过。保留原版本及失败证据。
- 审批规则改为对照执行前文件与审批前文件，缺基线报error；合成MCP资源名适配knowledge选择器。定向测试先4 failed/72 passed，修复后76 passed/1 warning。新版七题复验中，发现全新Workspace尚未初始化导致执行前读取502，继续修复；不能把这次尝试记通过。
- browser-skill新生命周期批次 `c16f32fd-02f0-40ce-8558-68593698c2cd` 已完成反馈、授权和投递；截图58已核对。后续审核、清理恢复继续。

## 2026-11-14 CSV、校准与生命周期补证

- 审批Workspace初始化定向111 passed/1 warning；此前该新增测试第一次失败源于测试Case缺artifact_correct指标，不作为产品red证据。
- 七题新版回归 `fdd93f11c56e4ccfa2f0c7bd0dc5183c` 全部pass，gate0，无warnings，17请求/169083 Tokens。日志 `completion-safety-v2-workspace-regression.log`。
- 新批次已从前端审核发布 `d-f3242954324e42da9ccf7c60d892d8bc`，回归 `4813ca1e3a5841e1bd1730292373ed05` 六规则全pass、gate0，保留未配置正式预算警告。截图59、60已查看确认。
- 新增多轮记忆与缺资料四个AI预标注合成对照，两轮8次结果一致，28次裁判请求；阈值0.7未事后调整，独立评审与正式语义发布策略仍未批准。日志 `completion-calibration.log`。
- 巡检真实SQLite发布集成通过，源授权及评分用测试替身，验证重启不重复评分、评分中撤权不发布；全25项巡检测试通过，实际自动采样仍0。
- 生命周期新增负例先2失败/32通过；修复孤立原生Dataset及坏备份阻断后34通过。90天审计、7天恢复副本和重试边界16通过；后续离线权限对账35通过。日志分别为 `completion-retention-native-red.log`、`completion-retention-native-green.log`、`completion-retention-lifecycle.log`、`completion-offline-reconciliation.log`。
- 首次多存储备份因本机默认pg_dump14与隔离库PG17不匹配失败，源服务已由finally重新启动，未生成有效快照。增加执行前版本检查，显式使用本机现有PG17工具重试，不更新共享依赖。
## 2026-11-14 撤权、清理与多存储恢复

新批次 `c16f32fd-02f0-40ce-8558-68593698c2cd` 使用独立实验7，固定题库 `d-f3242954324e42da9ccf7c60d892d8bc` 版本1，内容hash为 `d31cea9c390647f2e11b35bfef9837c9942dc8cba64f9a1b2869552090db67ad`。原生回归Run为 `85c69b843ea8416182766d826cd57b7a`，六规则通过后，从Agent前端撤权。

- 撤权发生在2026-11-14 16:44:22（北京时间），在线副本在16:45:50清理完成。Run/Trace计数为0，产物目录消失，题库目录隐藏；普通实验1仍为200，实验7为403。证据：EvalFlow `.local-stack/completion-retention-result.json`。
- PostgreSQL备份使用本机PG17工具，覆盖platform 28张表、runtime 39张表；同时保存Workspace、Redis持久文件、EvalFlow两SQLite、原生文件、任务、结果与私有配置。源服务暂停后复制，SQLite通过backup接口包含WAL，finally恢复源服务。仅创建新的隔离副本，7天失效，不覆盖源库。
- 第一次恢复因将导出表主键误写为id而失败，真实字段为export_id；第二次在启动HTTP前调用了通过HTTP发现实验的DatasetRegistry入口，造成重试。已将离线清理改为使用对账得到的实验ID，不依赖尚未启动的HTTP。新增测试先1失败，修复后生命周期18通过；失败日志保留。
- 成功恢复目录为 `managed-restores/3834ac207e8e4ef0b2d7880c9dcfebfc`，日志 `completion-restore-v3.log`。两PG库全部67张表的行数和排序行hash一致，6715个Workspace文件hash一致；Redis从持久文件实际启动并载入34个当前有效键，没有启动Worker，也没有重放模型请求。
- 在对外提供HTTP前，对本次目标export应用当前源端撤权并清除恢复PG中的导出正文；EvalFlow对4个历史关闭批次先封闭，清除原生受限副本。未对账副本拒绝启动；完成后临时EvalFlow服务实验1为200、实验7为403、题库隐藏。演练创建的所有服务已停止。结果：`completion-multistore-restore.json`。

恢复边界：这是显式指定export的本地多存储演练，不是生产灾备。没有启动恢复副本的Agent API或Worker；Redis验证持久文件和实际加载，TTL自然流逝，不宣称逐键业务等价。源端撤权同步验证的是本次目标export，不能据此宣称所有生产主体都已自动对账。旧二进制滚动回退、生产RPO/RTO和正式性能仍未验证。

## 2026-11-14 撤权详情页修复与浏览器证据

撤权后的GraphQL可能返回 `mlflowGetRun: null` 且没有errors。页面原来把它当作成功请求，显示空表和持续加载。`useEvalRunProgress.tsx`现在在请求结束且无Run时复用已有错误页，中文说明记录已移除或访问授权失效。新增测试先失败，修复后该hook与原详情页18项通过；翻译使用项目自动生成的消息ID，不手写ID。

| 截图 | 实际核对的页面 |
|---|---|
| [56 五题结果](56-ai-reviewed-native-results.png) | AI接受的五个开发题真实回归结果 |
| [57](57-quality-summary-denominators.png) | 受控质量汇总的完成、取消、缺失与分母说明 |
| [58](58-lifecycle-source-authorization.png) | 源反馈、合成复现授权及关联回执 |
| [59](59-lifecycle-published-dataset.png) | 非管理员原生审核、AI评审说明和固定版本 |
| [60](60-lifecycle-regression-results.png) | 新批次六规则通过及原生回归结果 |
| [61 源端撤权](61-source-grant-revoked.png) | 源页面显示导出授权已撤销，关联题库不可新运行 |
| [62 修复前结果页](62-revoked-result-closed.png) | 撤权后空表/持续加载的失败证据，不当作通过 |
| [63 修复后结果页](63-revoked-result-message.png) | 明确显示无法加载记录与可能的访问失效原因 |

截图56–61、63已逐张查看；62保留修复前问题。63首次捕获超时，重新同步确认页面后再次截图成功，没有重放撤权操作。

本轮新增功能之外，核对两个历史审批测试会话并通过正式取消接口停止；最终均为no_active_run，没有批准遗留写操作或删除会话。私有记录：`completion-old-approval-cancel.json`。

## 最新验证交接

- EvalFlow后端扩展：354通过、2条警告，`final-evalflow-backend.log`。
- Agent API反馈/巡检/诊断范围：68通过，`final-source-api.log`；Runtime相关范围：82通过、6条警告，`final-source-runtime.log`。
- EvalFlow前端6套件37项通过，`final-evalflow-ui.log`；包含回归操作、题库绑定、质量汇总、审核和运行详情。保留既有React/act警告。
- 主/shared TypeScript、所改详情页lint、EvalFlow扩展及测试与恢复脚本Ruff通过；日志 `completion-types-fixed.log`、`completion-page-lint-fixed.log`、`completion-ruff-final.log`。
- 最新后端经所属local-stack重启，普通实验200、撤权实验403、Assistant入口404、撤权题库隐藏，自动采样0；私有摘要 `completion-final-live-check.json`。

这些测试范围有历史重叠，不相加冒充唯一用例数，也不声称运行整个上游测试库。最终默认构建、版本摘要与批准范围结论集中记录在专题04的独立Final区。
