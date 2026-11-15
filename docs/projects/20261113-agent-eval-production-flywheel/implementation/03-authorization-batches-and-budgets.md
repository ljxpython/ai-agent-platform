# 授权批次隔离、用途与裁判预算

日期：2026-11-13。状态：实施中；仅 Phase，不构成 Final。范围：Task 2.0–2.4、3.3、4.1–4.4。

## 已获人工决策

用户批准每个授权批次独立原生实验、撤权后关闭访问。每个 export 作为最小批次；候选 Trace、HUMAN 反馈、审核队列、Dataset、结果 Run 和产物绑定同一实验。后台服务拥有 MANAGE，审核人仅在活动期获 EDIT；撤权/到期写入 DENY，不重新打开旧批次。维护后台与原生管理员是受信角色；无法撤回已被授权用户下载到本地的副本。

用户确认暂无可信 CI runner/secrets 和独立盲测评审人；继续本地实现和验证，不把本地成功冒充 CI 或独立盲测。

## 实现边界与待验收项

- Agent 批量源授权接口只返回 ID→bool，不回传原文；每次校验当前源用户、项目成员、反馈撤回和授权到期。
- EvalFlow `authorization_batches.py` 持久化 preparing/active/revoking/revoked，复用原生实验与权限 API；每次非维护身份数据请求前复核源授权，网络/不完整响应 fail closed，不伪造撤权。覆盖普通 API、GraphQL、原生下载路由；资料响应 no-store。
- Dataset 实验关联不可被审核人扩大；registry 核对批次 Dataset 只挂一个实验。扩展目录、任务详情、发布与取消须检查批次可见性。CLI 与 worker 将结果写入可信批次实验。
- 原共享实验的已撤权合成样本保留为旧证据，不迁移后冒充新批次证据。新链路需要新合成 export；隔离 Worktree 已启用批次开关，原生 Trace/Dataset/Run/产物读取与撤权恢复尚待新批次 E2E。

## 接续前已执行的 Phase 结果

- 家族与用途：registry/contracts/curated execution 组合 42 passed。相同家族、精确 turns+fixture 复制禁止跨 dev/holdout；开发可见导入明确 blind_eligible=false，新版本保留用途。
- 裁判预算：budget/evaluation/contracts/curated execution 组合 81 passed。请求、UTF-8 输入字节、输出额度在调用前预留，SDK 禁自动重试；用量缺失/结果未知保留额度并阻止后续调用。默认值是本地试验值，未冒充生产政策；输入 tokenizer 未核实，不声称总输入 token 硬上限已完成。
- Agent vue-tsc 与 EvalFlow 主/shared type-check 通过；[16 源反馈撤权展示](16-feedback-projection-revoked.png) 已实际截图并视觉检查。
- 首次批次接线后的 EvalFlow 全套：139 passed / 2 failed；两失败因测试加载本地 basic 配置，已通过 `tests/eval_platform/conftest.py` 隔离私有环境和认证库修正，接续全套 167 passed；Agent 源授权 API 20 passed。

## 2026-11-13 接续 Phase

- 撤权在取消请求成功持久化后才标记 revoked；取消失败保留 revoking，重启可以重试。已存在批次时关闭 basic 认证或隔离守卫会拒绝启动。审核身份不得提交 host scorer/job 或扩大 Dataset 实验关联。
- 目录、Dataset 列表、任务列表/详情、创建/取消、发布/新版本的跨批次负例与正常审核人对照均已加入契约测试。尚不能替代真实原生下载与重启 E2E。
- `.github/workflows/evalflow-contracts.yml` 已增加无密钥 PR 检查，使用 GitHub hosted runner、只读权限、不持久 checkout 凭据。相同 pytest 命令本地通过；未推送，未在 GitHub 执行，也未以全新 Linux 环境演练安装。
- 原生在线能力探针：所属合成实验 3，注册自定义 scorer 返回 `INVALID_PARAMETER_VALUE`，服务未启用 custom scorers。没有启动抽样、没有模型请求；不自动打开主机代码执行。私有证据：EvalFlow `.local-stack/native-online-probe.json`。
- G3：`contracts.GateLimits` / `config.EvalConfig.gate_limits` 显式配置每题及整批 requests/total_tokens/duration_seconds；`gates._agent_resources()` 只接受身份匹配、已 finalized 的逐 Run 账本。缺计量返回 error；未知值不记零；已知超限与安全失败不被完整性错误隐藏。批次时长为各题 wall time 之和，不是并发批次历时。未配置上限显示 not_configured + warning，不宣称已通过预算门禁。门禁策略升为 3，配置进入 comparison_key，旧报告不改写。该检查是执行后门禁，不能代替运行时预扣/停止策略。
- 通过正式 Platform API 只读检查上一条合成源 Run：available/finalized，账本 1 次模型请求、11,194 total tokens；没有新模型调用。私有证据：EvalFlow `.local-stack/native-usage-probe.json`。
- 实际命令：EvalFlow `.venv/bin/python -m pytest --confcutdir="tests/eval_platform" tests/eval_platform -q` → **196 passed**；`.venv/bin/python -m ruff check eval_platform tests/eval_platform` → 通过。此前定向首跑 94 passed / 1 failed，为告警列表新增预算未配置提示后的旧断言，修正后 84 项定向通过，包含新权限负例。

## 旁路信号持久 Trace

Agent `loop_detection.py` 增加稳定 event_id、检测器版本和 started/completed 汇总；每次完整只读批次纳入 eligible_batches，无法判断的工具结果单列 ineligible_batches，同一无进展段只发一次 suspected。默认旁路开关仍关闭，不新增干预或模型请求。

`observability/langfuse.py` 将上述限定事件经原生 MLflow SpanEvent 写入当前 Trace，不依赖 Langfuse client；`MLflowFailSoftCallback` 仅在旁路开启时使用 inline 回调，保留 async 调用的 span 上下文。元数据经既有白名单清洗，不包含工具参数、路径或原文。成功导出后可随 Trace 恢复；Trace 本身丢失/服务崩溃尚没有额外可靠队列，不能声称全量恢复。completed 汇总仅覆盖正常完成的 graph invocation，失败/取消必须按权威 Run 分母另计。

真实本地 MLflow SQLite 持久化 + 合成 LangChain graph（同步/异步各一条）已验证：4 次只读批次、1 个 suspected 信号、started/completed 事件完整，输出正常且未增加调用；这不是实际 Worker 或浏览器验收。Runtime 命令 `.venv/bin/python -m pytest tests/middlewares/test_loop_detection.py tests/observability/test_mlflow_tracer.py tests/observability/test_loop_observation_mlflow.py -q` → **50 passed**；涉及文件 Ruff 通过。生产/真实 Worker 尚未开启新旁路。

## 当前依赖

浏览器验收标签页由用户接管，交还前不操作、不另开会话绕过；新批次全链路及截图尚未取得。可信 CI/独立评审人经用户确认暂无。其余可在本地推进的任务继续实施；本记录全部为 Phase，不是 Final 或发布合格证明。
