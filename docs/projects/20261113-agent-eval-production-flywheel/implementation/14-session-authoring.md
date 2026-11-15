# 06 实现与验收：从完整会话到可维护的题库

日期：2026-11-15。范围为 344c 下 Agent 与 EvalFlow 两个隔离 Worktree，使用合成资料、平台已有账号及获准的 xiaok DeepSeek。唯一进度来源是 [06 专题任务区](../06-session-to-dataset-and-ai-authoring.md)。本记录解释做了什么、怎么验证，以及失败为什么保留，不代替任务清单。

## 用户现在可以完成什么

Agent 平台只交付有授权的当前 Session 或一批 Session，包含获准的对话、执行记录及环境资料。EvalFlow 接收后由自己的评测 Agent 整理用例；也可以不选任何会话，直接新建测试。题目、预期、文件、审批和指标均在 EvalFlow 编辑，支持给 AI 反馈、查看改动并部分采纳。

保存草稿、发布版本和运行是三个独立动作。结果跟着工作项和版本保存，刷新后能从历史找回。默认结果展示本次执行的完整 Session，区分用户业务轮次与审批恢复产生的 Run；指标能定位对应轮次、Trace 或文件。模型裁判的请求、响应、失败和评分依据单独展示，不混入被测对话。补收证据与原证据重评都不重新执行 Agent。

具体操作、可复制 CSV 和每一步预期见 [人工验收手册](../manual-acceptance.md)。15 段实际录像总计约 59.6 分钟，见 [回放说明](../acceptance-replay.md)；桌面 `06-打开回放.html` 已提供逐段播放器。

## 代码放在哪里

| 所属仓库 | 主要位置 | 本轮职责 |
|---|---|---|
| Agent | `apps/platform-api/src/platform_api/modules/evaluation/` | 授权、Session 资料交付、用途及执行会话权限；整批授权锁顺序统一 |
| Agent | `apps/platform-web/src/modules/evaluation/`、聊天页及侧栏 | 当前会话/批选入口、交付状态；不维护第二套候选题库 |
| Agent | `apps/runtime-service/src/runtime_service/observability/execution_evidence.py`、`evaluation_environment.py`、工作区文件读取 | 获准环境初态与执行证据；文件读取失败与确认不存在分开 |
| EvalFlow | `eval_platform/evaluation_assistant.py`、`authoring_api.py`、`work_items*`、`work_item_results.py` | 评测 Agent、草稿及修订、发布、任务历史、解释与证据投影 |
| EvalFlow | `eval_platform/targets/agent_platform.py`、DeepEval 适配及 Session 证据模块 | 真实 Agent 执行、固定/动态对话、审批、文件取证、裁判和补收 |
| EvalFlow | `web/src/evaluation-tasks/` | 评测集工作台、AI 建议差异、用例编辑、版本/运行、完整 Session 与裁判查看 |

复用 DeepEval 4.3.4 与现有 MLflow Dataset、Run、Trace/Session 查看器。没有修改 `mlflow/` 上游核心。05 的旧 A1 入口保留历史事实；06 新流程不做旧入口兼容升级。

## 验收中发现并修复的问题

### 1. 同一批授权并发核验可能死锁

真实请求出现 500/502。检查 PostgreSQL 后发现，部分调用先锁 Export 再锁源 Thread，另一些调用顺序相反；同批含多个授权时，逐条锁还会交叉等待。

`service.py` 的 `lock_packages` 统一收齐批次及父授权：先按稳定顺序锁源 Thread，再锁 Export；通过 `populate_existing=True` 刷新当前撤权状态。`workbench_grants.py`、`assistant_control.py` 沿用相同顺序。70 项 API 测试通过；真实 PostgreSQL 使用 3 个客户端、正反输入顺序完成 36 次并发校验，无死锁。随后 S01 完整文件回归成功。

证据：[真实并发回执](phase06/authorization-pg-concurrency.json)。完整测试日志在 Agent `.local-stack/phase06-authorization-lock-tests.log`。

### 2. Agent 后续失败，不应丢掉前面已经完成的动作

旧 05.C03 先成功 `write_file`，随后请求未授权的 `present_artifacts` 被拦。旧结果取证不足，容易让人误以为报告根本没写出。新 B04 也真实出现类似情况：写完报告后额外请求 `execute`，超出该题授权而停止。

执行器现在先保存已获得的消息、待审批请求和逐轮快照；异常退出仍收集已观察到的工具与获准文件。不完整轮标明 `incomplete`，文件读取拒绝不能当成文件不存在。结果 API 只投影受控的工具名、业务轮、Run、获准文件路径与停止回执，不任意透传工具参数。页面解释失败位置，并保留真实报告。

真实 B04 的报告为销售 1800、退款 300、净收入 1500，文件正确与源文件保护两项均为 1；缺完整最终回答的 TaskCompletion/对话质量仍无法评分，总体仍是 error。没有放宽工具权限，也没有改写旧失败。

证据：[旧 C03 根因](phase06/phase06-legacy-c03-cause.json)、[B04 精选执行证据](phase06/b04-partial-evidence.json)、[新页面完整 Session 与报告](phase06/phase06-final-b04-session-loaded.png)。B04 真实运行早于最后追加的不完整轮快照小修；该小修由异常分支自动化测试覆盖，旧记录没有回填。

### 3. 任务取消和底层停止确认不是同一件事

S01 取消测试恰好发生在第一轮结束前后：后两轮没有启动，没有生成报告。初始停止回执为 `confirmation_unavailable`，稍后同一回执变为 `no_active_run`，确认没有继续执行，资源清理 `not_required`。

`wait_run` / `stop_pending` 不再把暂时无法确认当最终状态，最多查询原回执 15 次，不重复发送取消。页面同时展示任务状态和底层回执；确认不到时不声称资源已经释放。`test_stop_confirmation_recovers_without_resending_cancel` 覆盖延迟确认；真实取消前后及修复后同幂等键核实保存在 [取消回执](phase06/phase06-cancel-proof.json)。后续 API 核实不在取消视频内，原报告也未改写。

## 真实链路结果

| 场景 | 实际结果 | 可复核标识 / 证据 |
|---|---|---|
| A：当前 Session 历史评分 | passed；只评分原会话，源仍 2 个 Run | task `f8dc523f-dba8-4a16-b648-d817ff34aee9` |
| A：批量交付 | 两段 Session 各 4 条消息、2 个 Run，成功进入 EvalFlow；此批量工作项没有继续生成/发布 | [批量交付截图](phase06/phase06-batch-delivered.png) |
| B：固定批准/拒绝 | 原证据重评后两分支通过，旧报告及运行数量不变；原缺文件分支因缺轮不能评分，未抹去 | task `0547ad40-eee0-4e73-9eaf-118e4408b941`；[不重跑核对](phase06/phase06-no-rerun-proof.json) |
| B03：缺文件表单修订 | 新版本单轮请求真实 `request_information`，工具 GEval 为 1 | task `10822d5b-2c6f-4b61-899b-ca887558fcd8`；[裁判截图](phase06/phase06-b03-tools-judge-expanded.png) |
| S01：源初态文件回归 | 只带两份原始 CSV、不带旧报告；三业务轮四 Run；审批中重启后恢复，四项均 1，源工作区不变 | task `3c567d4b-e464-4de9-abd9-00137d2fa02d`；[恢复核对](phase06/phase06-source-recovery-proof.json)、[源不变](phase06/phase06-source-unchanged-proof.json) |
| C：无来源直接新建 | 固定两轮 55/45 通过；动态用户也得到 55/45，对话质量 0.9，生成固定回归草稿（新增题未发布） | 固定 task `3d979d56-8f53-4ff2-993c-7fb726cc8179`；动态 task `33ae9b24-1cdd-49b6-a3d0-c57d8b5e3026` |
| B04：动态后续工具越权 | 报告保留、文件检查通过，但未授权 execute 被拦；总体 error | task `fed53969-129c-4834-9fde-bdc963fefd3d`；Session `d552a664-0954-463d-aa76-1ed7a2bba4db` |
| Trace 部分缺失 | 自动化覆盖 5 Run/4 Trace 补到 5/5；浏览器使用明确标注夹具，隐藏真实 2 Run 中 1 条，补收恢复两条、不重跑 | [缺失提示](phase06/phase06-trace-injected-visible.png)、[补收后](phase06/phase06-trace-real-restored.png) |
| 取消 | 第一轮结束、后两轮不启动，停止回执后续确认无活跃运行 | task `cbfc78f3-94a6-4fd3-8c01-748016c55aef`；[回执](phase06/phase06-cancel-proof.json) |
| SEC06：撤权 | 撤前动态评分 0.8、工具预算 1，裁判可查看；撤后资料、版本、结果、模拟、裁判清空，执行接口拒绝 | [撤前](phase06/phase06-revoke-before.json)、[撤后](phase06/phase06-revoke-after.json)、[页面清空](phase06/phase06-security-after-revoke.png) |

SEC06 是独立破坏性样本，不再作为用户可操作例子。平台工作台撤前可读、撤后拒绝；原生非管理测试账号对实验/Run/Dataset/Trace 撤后全 403，但撤前也无新批次权限，不能描述为该账号 200→403。

## 最后自动化与构建检查

以下是相关范围，不是两个仓库或 MLflow 上游全量测试；不同批次可能重叠，数字不相加。

| 检查 | 结果 | 日志（相对于所属 Worktree） |
|---|---|---|
| EvalFlow 执行器、用例、助手、结果、保留策略、Session、模拟、规则、资料、Trace、逐轮评分 | 465 passed，16 warnings，65.99 秒 | `.local-stack/phase06-final-verified-backend.log` |
| EvalFlow 五个页面/组件测试文件 | 5 suites / 18 passed | `.local-stack/phase06-final-verified-ui.log` |
| EvalFlow 主/shared TypeScript | exit 0 | `.local-stack/phase06-final-verified-types.log` |
| EvalFlow 最新前端构建 | exit 0；包体积与 Browserslist 等警告保留 | `.local-stack/phase06-final-verified-build.log` |
| 最新三处前端文件直接 ESLint | exit 0；Browserslist 提示保留 | `.local-stack/phase06-final-verified-lint-direct.log` |
| 最新五处 Python 文件，Worktree Ruff 0.16.8 | All checks passed | 本轮工具执行回执 |
| Agent 授权/工作台相关 API | 70 passed，12.55 秒 | `.local-stack/phase06-authorization-lock-tests.log` |
| Agent 资料与历史相关 API | 27 passed，2.67 秒；与 70 项可能重合 | `.local-stack/phase06-material-full-tests.log` |
| Runtime 环境/执行证据相关 | 6 passed，5 warnings，6.72 秒 | `.local-stack/phase06-runtime-latest.log` |
| 双仓差异空白、MLflow 上游不变 | `git diff --check` 通过，`git status --porcelain mlflow/` 空 | 最终文档检查回执 |

最后重试的 `yarn` lint 被 Node 引擎检查拦住（项目声明 `^24.14.0`，本机 `22.22.2`），未执行；随后用同一 Worktree 已安装的 ESLint 直接检查修改文件并通过。误用旧 Ruff 0.12.8 时不认识仓库的 RUF068，改用该 Worktree 现有 0.16.8 后通过。未更新核心依赖或放宽项目 lint 规则。Node 24 环境下的标准 Yarn 命令仍需环境复验，不把当前通过解释为 Node 24 兼容认证。

前期构建遇到新文件绝对 URL / 闭包 lint 错误，已在源码修复，最新构建通过。既有测试警告（配置/弃用）、包体积等没有被当作功能失败，也没有删除以美化结果。

## 权限、清理与恢复

新派生字段的保留策略测试覆盖模拟题、助手调用、解释、fixture 清理及重复清理。7 天隔离恢复限制、先应用当前撤权、未对账副本拒绝服务由现有恢复测试覆盖。05 的真实隔离恢复演练仍适用，相关底座未改：67 张 PostgreSQL 表、9843 文件、Redis 10 键、18 个旧会话拒绝读取；本轮没有重新搭建生产恢复环境，不称生产灾备验证。

本次证据只使用合成内容。长期留在项目目录的是必要截图和小型精选回执；密钥、Token、配置文件正文不进入记录。源授权最长 24 小时的验收条目到期后应新建，不绕过到期继续使用。

## 文档与服务交接检查

最终核对9份文档中的444处本地链接，本专题新增链接可达；FEATURES中4处无关既有断链与首次规划检查一致，未扩大范围修改。12个任务编号连续、无未勾选子项，代码围栏配对；两仓`git diff --check`和上游guard通过。精选10份JSON未发现凭据字段或Token模式，最后补入本检查回执；截图均为合成样本。

所属local-stack状态确认Agent四服务及Redis运行、Runtime/API就绪；EvalFlow Web9138返回200，API5011运行，无凭据探针401为预期鉴权。最后已登录浏览器可读取B04完整Session和报告，自建browser-skill会话已关闭，服务保留。15个录像经ffprobe核对存在且可读，桌面HTML的15个本地视频地址匹配。[最终检查回执](phase06/final-checks.json)记录范围和限制。

## 交付边界

- 动态用户支持普通文字对话及预设文件审批，不自动填写任意业务表单，也不支持动态 live 真人审批；固定回归支持 live 审批。复杂表单用固定场景验证。
- 文件通过真实上传 API 和“文件名＋正文”路径验证；浏览器原生文件选择器未录通，手册采用已验证路径。
- 批量入口验证完整资料交付，后续整理/发布/运行通过当前 Session 来源和无来源路径验证；不声称那个批量条目已经运行。
- AI 生成仍可能超时或设计不完整，支持反馈修订；AI 评审不等于独立盲测。被测 Agent 工具越权、缺最终回答等真实失败保留。
- 停止无效循环、正式性能、真实 CI、独立盲测、缺网关说明的真实自动采样、Grafana/通知、生产均按原决定暂缓；采样保持 0。
- 用户亲自验收表留空。本轮未提交、推送、合并或部署生产。没有本专题对应的待毕业标准，未把无关 JWT/SSE 草案改为 active。
