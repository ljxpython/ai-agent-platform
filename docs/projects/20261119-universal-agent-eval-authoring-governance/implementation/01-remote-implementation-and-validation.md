# 远端实施与阶段验证证据

> 本文保留Task1–4开发阶段事实；后续合并、验收和清理以[交付记录](05-delivery-and-cleanup.md)为准。原Worktree私有证据已归档至 sshmy1:/opt/mlflow-eval-platform/.local-stack/deliveries/20261119-universal-authoring/pre-merge-evidence/，下述相对日志路径以此为根。

2026-11-19。本文保存产品实施范围、真实执行证据和失败边界；任务状态唯一维护在 [tasks.md](../tasks.md)。以下为阶段验证（Phase），联合整体验收（Final）及用户追加批准后的预算修复、AI 委托复核与成功新运行另见[最终记录](04-delegated-review-and-final.md)。

## 开发环境及影响范围

后端遵循 EvalFlow 的 Remote-First 规范，在 `sshmy1:/opt/worktrees/evalflow-universal-authoring-20261119` 开发，基线 `f7a087f20c6cb221f90d62c094e51a3201c23b80`。Mac 的 mlflow-eval-platform 保持镜像角色，没有复制后端代码形成第二事实源。用户已允许复用生产数据库，测试状态、任务和结果保存在 Worktree 私有目录，未新增数据库隔离、迁移或结构变更。

生产 editable 安装指向主仓，若共享同一安装环境，测试可能导入主仓源码；因此为 Worktree 建立独立 Python 3.11.18 虚拟环境，复用已核对版本及 uv 缓存，不共享安装目录。已核对 mlflow/eval_platform 的实际导入路径。没有新增第三方依赖。

修改覆盖两套出题提示、Proposal Schema 描述、共享 BusinessFacts 评分步骤、配置加载/题库发布、任务选择、CLI 执行、历史证据、Trace 收集及分指标评分。出题调用新增内部输出/超时上限参数，默认评分行为保留；缺失版本错误说明实际采用的旧版本，不隐式升级或放宽验证。调用方、预算与兼容回归一同修改。上游 `mlflow/` 没有改动，Agent 两服务没有本轮产品代码修改。

收尾只读核对发现，生产主仓原有的 access.py 权限改动及其测试已由外部工作形成提交 `10d400a`（2026-11-19 11:44:28 +0800），主仓当前干净；本任务未执行该提交。Worktree仍以f7a087f为基线，未覆盖这两个文件，也未擅自重置或合并。将来获准Git交付时需保留并整合该权限修复，再对整合版本回归；当前687项证据对应本Worktree，不能冒称已验证整合后的main。

## 所属进程管理

`scripts/local-stack.sh` 复用新脚本 `scripts/local_stack_process.py` 管理进程。启动时记录 PID、psutil 创建时间和真实 cwd；停止时逐项核对，仅终止该进程树。无身份、创建时间不符、外来目录会明确拒绝，不再按端口猜测后杀死 Python/Node 进程。

5 项真实进程测试通过，实际所属后端 stop/start/restart 通过，原生产监听不受影响。最终仅重启测试 5011 加载最新代码；`service-final-health.json` 确认测试 health=200，cwd 为 Worktree、身份匹配；生产 5000 health=200，MainPID=2115014、NRestarts=0、active 前后不变。测试后端保留运行供后续验收，9138 前端未启动，专属本地 45011 隧道已核对身份后停止。未重启生产服务。

## 确定性测试与静态门禁

所有产品测试在 sshmy1 Worktree 独立环境中实际执行，日志保存在私有 `.local-stack/universal-authoring/`。以下范围重叠，不能相加当作独立测试数。

| 执行 | 观察结果 | 日志 |
|---|---|---|
| 修改前基线及进程修复 | 621 passed，25.59 秒，含新 5 项真实进程测试 | baseline-pytest.log |
| 第一步相关回归 | 100 passed，3.89 秒 | phase1-pytest.log |
| 第二步相关回归 | 156 passed，4.25 秒 | phase2-pytest.log |
| 扩大回归及后续提示修订 | 先后 678/679 项通过，完整日志保留 | expanded-pytest.log、final-pytest.log、final-pytest-after-prompts.log |
| 输出上限专项及当时扩大回归 | 34 passed；682 passed、21 warnings、22.82 秒 | output-ceiling-tests.log、final-682-pytest.log |
| 版本反馈及请求超时专项 | 39 passed、6 warnings、3.05 秒 | timeout-version-tests.log |
| 最终扩大回归 | **687 passed、21 warnings、23.18 秒** | final-687-pytest.log |

最终命令（完整参数亦存 `final-regression-command.json`）：

```bash
.venv/bin/python -m pytest tests/eval_platform/ \
  tests/test_authoring_api.py tests/test_authoring_assistant.py \
  tests/test_business_rubric.py tests/test_copilot_lifecycle.py \
  tests/test_legacy_entry_retirement.py tests/test_session_evidence.py \
  tests/test_simulation_boundaries.py tests/test_source_history_and_fixtures.py \
  tests/test_trace_completeness.py tests/test_turn_exactness.py \
  tests/test_work_item_results.py tests/test_work_item_retention.py \
  tests/test_work_items.py -q
```

最终 `final-static-checks.json`：18 份改动 Python 文件 AST 通过，`bash -n scripts/local-stack.sh`、`git diff --check` 通过，上游 `git status --porcelain mlflow/` 为空。Ruff 新增/修改行 0 诊断；本次覆盖文件的未修改行仍有 59 条诊断，未借机全仓格式化。早前新增测试的 PT006/E501 检查失败及修正过程保留，没有把第一次失败记成通过。

## 真实模型：固定素材与全部批次

每批均冻结同一组文件 5/文本 5，样本集合哈希为 `9ed11ac0904a4d07…`。模型 deepseek-v4.1-flash、temperature=0；每次调整提示或调用参数后另开完整批次，既有失败没有替换。每批最多 3 候选/8 步。前五批仅完成结构检查，业务列不填估计值。

| 批次 | 首稿结构 | 首稿结构+业务（AI） | 最终业务（AI） | 总秒数 | 平均秒数 | P95秒数 | 输入/输出 Token | 请求/用量未知 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3/10 | 未完整复核 | 未完整复核 | 124.485 | 12.448 | 20.756 | 121077/15440 | 21/0 |
| 2 | 8/10 | 未完整复核 | 未完整复核 | 84.422 | 8.442 | 15.526 | 78864/8878 | 14/0 |
| 3 | 4/10 | 未完整复核 | 未完整复核 | 135.25 | 13.525 | 20.809 | 143058/17092 | 24/0 |
| 4 | 6/10 | 未完整复核 | 未完整复核 | 94.903 | 9.49 | 15.153 | 92914/10665 | 16/0 |
| 5 | 8/10 | 未完整复核 | 未完整复核 | 88.858 | 8.886 | 19.929 | 87355/9499 | 15/0 |
| 6 | 10/10 | 6/10 | 未完整复核 | 64.73 | 6.473 | 9.228 | 64094/6050 | 12/0 |
| 7 | 10/10 | 5/10 | 未完整复核 | 75.323 | 7.532 | 10.772 | 66540/6824 | 12/0 |
| 8 | 9/10 | 6/10 | 7/10 | 75.183 | 7.518 | 15.711 | 83971/7671 | 14/0 |
| 9 | 9/10 | 8/10 | 9/10 | 325.474 | 32.547 | 85.297 | 82253/53548 | 14/0 |
| 10 | 9/10 | 9/10 | 9/10 | 373.152 | 37.315 | 74.545 | 70423/64613 | 12/0 |
| 11 | 8/10 | 8/10 | 8/10 | 354.676 | 35.468 | 86.272 | 78203/46848 | 14/1 |
| 12 | 10/10 | 10/10 | 10/10 | 287.105 | 28.711 | 52.304 | 70512/46657 | 12/0 |

P95 采用最近秩，10 个样本时即最大值。供应商未返回费用；请求超时未返回用量时，Token 和费用为未知，记录的 0 不代表免费。完整 manifest、输入、输出、工具回执和失败保留在 `live-batch-N/`；逐项 AI 复核写 `quality-review.json`，不是独立人审。

早期不思考调用易生成结构或业务错误，恢复模型默认思考后改善。第 10 批首稿 9/10，但 8192 输出上限曾截断 JSON；提高出题上限至 16384 后，第 11 批又因 60 秒请求超时及漏版本时的错误反馈退至 8/10。第 11 批 F04 连续漏 schema_version，反馈只说题号无效，模型反复改题号；`approval_mode=preset` 本身是合法旧兼容值，不将其误判为错误。随后仅修正明确版本反馈及出题请求超时，不放宽校验、不自动补版本、不增加候选重试。

第 12 批冻结最终产品源码与 Schema 哈希，首稿结构 10/10、首稿结构+业务 AI 复核 10/10、最终 10/10。没有候选修复样本，条件修复率不适用；12 次请求中的两次是退款/库存必要计算。用例/批次原总预算保留，普通评分仍为 8192 输出上限、60 秒请求默认；仅出题使用 16384/180 秒。全部必要附件及换行与来源逐字比对，逐题核对题面条件、独立答案、逐轮生效点、自然语言澄清和 attempted/executed 安全阶段。审阅材料见 [03-human-review-materials.md](03-human-review-materials.md)。

这只证明该模型路线在 10 份合成素材上的冒烟结果，不证明任意 Agent 支持、长期通过率或自愈 100%。更高输出/超时上限可增加单次等待及潜在开销，实际费用未获供应商返回。

## 两类真实交付、AI 候选与独立发布

平台入口用原生 create_app()+TestClient 的真实认证 ASGI 请求、真实数据库，再经实际 HTTP Agent API2142、Runtime、EvalFlow5011 和真实模型。仅在 ASGI 内存 settings 中将 receiver 指向 5011，不改生产配置、不伪造 grant/token、不替换权限。它是实际服务与模型集成证据，不是浏览器或全程 HTTP 平台入口验收。

来源是操作员合成导入的两消息会话，不称 Agent 实际推理。第一次只有一个 checkpoint，真实采集按 history incomplete 拒绝；通过正常 state update 形成第二 checkpoint 后重新交付，原失败保留。

| 素材 | 来源 thread | 工作项及采纳修订 | 发布资产 |
|---|---|---|---|
| 文本 | 69fcf7f8-008f-4af6-98f2-d8ce18e2d9a3 | b3533e9e-9add-54c1-a690-bead6c10ede9，修订1 | d-25b57ad773254b1fb13c814e22ef3db5，v1 |
| 文件 | f0fcc939-8da2-4d30-b17d-d602254973c0 | 1ac38fb6-fb46-57d8-beb2-160b12220219，修订2 | d-6d2c089c3c0a4257a0183bc6d2e3e1fc，v1 |

文件首候选将无关重跑初态误列为缺口，经真实 AI revise 才采纳修订2。上表为最初采纳/发布事实。用户随后明确将本项目业务复核及采纳委托 AI，AI 复核文本原版本，并仅删除文件题无依据的 `max_tool_calls=20` 后发布修订3/题库v2；旧版保留。来源/发布/采纳 JSON 及日志保留在 `e2e/`，[业务复核材料](03-human-review-materials.md)展示最终资产与冻结题目，未将真实账号操作冒称独立人审。

## 历史评分与证据不足

首次历史评分任务 `080b9c1e-5ecc-48c3-8677-798e706fed93` 四项文本指标通过，来源 Run 前后均空，未执行目标。该结果发生在共享 BusinessFacts 去污染前，旧评分步骤含退款文案，保留为历史，不用它证明修复后的最终提示。

增加 ToolCorrectness 后，首次重评 `ad46967a-f01d-4aa5-94f4-8d12458ff07b` 因评分期间并行修改产品源码触发 `evaluator_package_changed_during_evaluation`；整轮作废并保留。随后冻结代码，任务 `f4793b4a-9bb3-4f95-b07c-4eddd7c9071f` 的四项文本指标各 1.0，ToolCorrectness 为 error、missing_evidence=[tools]，整体 error 明确不完整。来源 Run 前后仍空，评分步骤已无固定退款口径。`e2e/mixed-v2-end.json` 与 `mixed-v2-summary.json` 可追溯此结果。后续出题预算/反馈修改不改变此评分语义，最终扩大回归覆盖这些路径；没有声称在当前版本重复跑过全部历史真实调用。

## 显式新运行与接口核查

首次显式新任务 `1b3f422b-4860-4d76-9fa6-5c31191a6af0` 取得 evaluation-target/v1 快照并绑定 Session `844860c6-a35e-45d8-9f90-6ea4f3adda84`、Runtime Run `df443a11-baaa-468f-8eb1-2470885b8ffe`，随后因预算旧版本在模型调用前被拒绝，无回答/Trace，原失败保留。只读查询确认当时 Platform revision=0、Runtime=1、两端策略数均0；用户批准后最小状态修复已执行，详见 [02-production-budget-precondition.md](02-production-budget-precondition.md)。新任务 `a9ca7536-0828-43d5-985d-461bada1a7ee` 已成功产生回答及完整 Trace，绑定和正常接口回读证据见[最终记录](04-delegated-review-and-final.md)。

静态与真实调用共同确认：materials 负责来源采集与交付，评分使用已绑定证据；现有目标快照、运行绑定和 Worker 回执可承接新运行。本轮没有发现必须改 Agent 两服务的接口缺口，预算状态异常另行处理，不借机取消准入或扩展任意运行图。

独立负例使用私有配置将目标指向真实不可达的 `http://127.0.0.1:9`，实际 TaskStore.create/HTTP connection refused，新任务未创建，已发布题库仍可读且哈希不变。它是模块/网络集成负例，没有冒称浏览器或平台入口 E2E。首版 harness 漏捕 httpx.HTTPError，第二版修正，失败及复验均保留。

## 应用与配置回退、再升级

实际从 git HEAD 提取基线 eval_platform 包，在所属进程停止后用当前独立依赖启动基线代码的真实 5011 服务，核对实际 import 路径。基线私有配置恢复支持的 dearflow 目标后，经正常签名 read 读取两类题库与旧 Run；再停止基线、逐字节恢复私有配置并启动修改版。两版读取一致，16 份保留题库/Run 文件哈希未变，生产 5000 health=200。

首次脚本 tar 根路径断言失败发生在停服务前，已修正第二版并保留两次日志。证据为 `e2e/rollback-summary.json`、`application-rollback.log`、`application-rollback-v2.log`。本次没有迁移；这是应用包和私有配置回退，依赖未降级、共享数据库未回滚，不能扩称全栈灾备验证。

## 开发阶段证据边界

本阶段尚未执行 Git 提交、推送、合并、生产部署、生产服务重启或数据库结构调整；后续交付见05记录。预算状态写入仅限用户追加批准的版本修复，策略、用量、费用和守卫不变。未修改主仓既有 access.py 及其测试改动，未在服务器构建前端。未执行本次浏览器完整链路、独立人工盲评、供应商费用校准或大规模并发压测。

Agent仓文档校验 `python3 scripts/check_docs.py` 通过，本项目7份Markdown的本地链接与代码围栏检查通过。第一次临时链接检查命令的换行转义有误，修正该检查命令后复验通过；它没有修改产品或文档内容，不作为产品测试数量。远端回读确认CONTEXT仍为正常多行Markdown、项目块只出现一次，最终源码哈希与第12批冻结值一致。

用户已明确批准本项目由 AI 完成业务复核/采纳，独立真人复核不再是本次 Final 门槛；业务、安全、来源与发布标准保留。委托 AI 复核和成功新运行证据补齐后，另执行联合 Final，通过结果见[最终记录](04-delegated-review-and-final.md)。本阶段记录不冒充联合验收或独立人审。
