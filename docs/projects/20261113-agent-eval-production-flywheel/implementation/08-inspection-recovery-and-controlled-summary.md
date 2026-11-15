# 独立巡检、受控汇总、恢复副本与持久事件补扫

## 时间、范围与批准

2026-11-14；只在两个 `344c` Worktree 实施。关联 Task 1.1、1.4、1.5、2.1、4.1、4.6。本记录属于 Phase，不是全项目 Final。

用户批准 `quality_inspection` 独立用途及批次隔离；只使用人工重建合成 input/output，生产另批。用户随后批准先用受控页面，Grafana 接线等待访问范围及 Contact Point。现有匿名 Editor 配置没有修改，生产采样、通知外发及循环干预未启用。

## 实现与缺陷修复

- Agent `apps/platform-api/src/platform_api/modules/evaluation/contracts.py` / `service.py` / `router.py`：复用 EvaluationExport 保存独立用途、项目/Agent、有限字段、裁判路由、预算版本和有效期；源域清洗、幂等和撤权保留范围/hash审计。读取时重新核对当前用户、项目、管理者角色、本人 Thread 及 active Agent，禁止沿用创建时的权限。
- `service.py::inspection_agent()`：真实前端首次授权返回403，原因是 Runtime assistant_id 为 graph key 的确定 UUID，不是平台 Agent UUID。增加服务端身份解析和已完成 Run 的 thread/run 校验，再比较提交的 Agent；不是放宽权限。新 HTTP 测试首次因测试 fixture 缺 platform_context 失败，修正 fixture 后通过。
- Agent `InspectionConsent.vue`：人工合成输入输出→独立授权→提交→刷新/撤权；unknown 保留原 UUID，作用域切换抛弃迟到响应。撤权合并原接收回执，避免已接收被错误显示为“尚未接收”。
- EvalFlow `eval_platform/inspection.py`：独立有界队列、Run 去重、策略快照、采样默认0；派发前持久预留最坏请求/Token，未知用量封闭当日预算，崩溃不重放裁判。每次请求及发布前重查授权；原生发布最多8次，丢响应先按固定tag对账。仅数值结果入批次实验；不在队列落 input/output。显式 resources 配置，禁回退 home，关闭 DeepEval telemetry。
- EvalFlow `web/src/evaluation-tasks/InspectionSummaryControl.tsx`：使用既有设计系统，按当前身份/有效批次过滤，按 Agent/预算版本分层，明确样本总体；低样本不显示均分，刷新失败清旧数据。`api.ts`、`AgentRegressionControl.tsx` 和 catalog 同步。初次类型检查发现 mock返回值及Modal width属性错误，均已修复。
- `eval_platform/runtime_signals.py::recover_loop_observations()` 和 `run.py`：只读原生持久事件补扫；目标 Run / event_id 去重、冲突和缺失保守计量。Runtime `loop_detection.py` / `diagnostics.py` 增加稳定 observation_id 区分子任务；旧事件歧义则partial。畸形属性不导致整次评测失败，额外字段不进入指纹。只输出suspected，不改变业务终态；持久化前丢失无法重建。
- `eval_platform/app.py::create_app()` 增加 EVALFLOW_STATE_DIR（默认保持原目录），用于真正启动隔离恢复副本，不覆盖原服务状态。
- 默认关闭抓取模板和未加载的可用性规则见 `deploy/observability/examples/`；未创建质量下降规则或未授权接收端。

## browser-skill 真实前端证据

源 Web28808/API25087/Runtime26645，EvalFlow Web9138/API5011；源用户admin，EvalFlow非管理员flywheel-reviewer。

1. 首批 `4b6c257c-6163-470b-91f1-f85102242ee7` → 原生实验5，ready→exported/not_sampled→revoked。原生实验403、summary无可见层，后端重启后仍拒绝；前一轮本地记录保留。
2. 第二批 `74e9c115-f100-4e7f-adf5-25d8f3924ada` → 原生实验6：既有合成23+19 Run，人工重建input/output。前端授权、提交成功，受控汇总显示eligible=1、sampled/scored/error/missing/budget/pending全0、概率0%，均分不显示。源前端撤权后，汇总刷新为空；源回执保留not_sampled。
3. 两批sample_rate=0、无巡检预算文件，未调用裁判。该证据验证默认关闭路径，不证明真实provider上限、完整评分或生产容量。

截图：`30-inspection-authorized.png`、`31-inspection-not-sampled.png`、`32-inspection-revoked.png`（历史回执显示缺陷）、`34-inspection-second-batch.png`、`35-inspection-summary-active.png`、`36-inspection-summary-revoked.png`、`37-inspection-revocation-receipt.png`。35–37已逐图核对，内容和布局可读。

私有调试证据只保留在 EvalFlow `.local-stack/inspection-browser-debug.json`、`inspection-summary-browser-debug.json`；第二次捕获28请求/6操作、无丢失，初始页面加载不在捕获范围。未导出凭据，浏览器会话已关闭；旧汇总会话曾idle自动关闭，重新打开任务窗口继续验收，没有重放授权写请求。

## 真实恢复副本与只读补扫

- `.local-stack/probe_live_restore.py` 实际启动恢复副本，独立临时端口49454（已停止）。恢复副本内使用临时非管理员凭据，保留RBAC；原服务用户/密码不变。基础实验200，撤权实验4/5均403，撤权题库目录过滤、巡检summary空、Assistant执行404；3个冻结版本hash一致，模型调用0。证据：`.local-stack/live-recovery-result.json`。
- 恢复涵盖EvalFlow本地SQLite/状态/冻结版本及权限，不涵盖Agent PostgreSQL、Redis和Workspace一致时点恢复；不能替代生产多存储恢复和旧版本回退。
- 只读重取真实Worker Trace `tr-cfa211356891c7c3b68ee62c549793af`，得到1个完整scope、eligible/ineligible/signals均0、missing_run_count=0，无Agent或模型重放。证据：`.local-stack/signal-recovery-result.json`。这是旧版无owner零工具样本；多子代理owner由契约测试覆盖，未再跑真实多子代理模型任务。

## 已执行 Phase 验证

- Agent API：37 passed（inspection+feedback，含撤权、过期、Agent禁用、Thread归属变更及Run身份负例），`.local-stack/phase-inspection-api-owner.log`。
- Runtime：51 passed / 6 warnings（loop detection/calibration、原生事件导出、tracer），`.local-stack/phase-signal-runtime.log`。
- EvalFlow补扫+评测：54 passed / 1 warning，`.local-stack/phase-signal-recovery.log`。
- 恢复副本和两条默认关闭浏览器链路如上。后续组合验证结果见下，不把先前258项结果冒充最新代码的全套结果。

## 当前边界

本地新增能力已取得下列Phase证据，剩余联合验收为blocked。真实巡检请求仍关闭：受管路由provider上限、请求/Token预算、最小样本量和性能允许增量未冻结；测试中的mock调度不等于真实裁判验收。独立评审/新盲测、可信CI runner/secrets、生产资料保留政策与生产恢复条件仍缺。Grafana实际接线/通知按用户决定等待条件。旧holdout已暴露，候选20题待人审，循环干预保持旁路。A04远端沙箱旧阻塞未重测。

## 组合验证与策略漂移修复

- 复查发现同一策略版本可被修改采样率，导致统计层混合口径；`Inspection.ingest()`现在拒绝复用版本的不同内容。发布前同时检查持久快照与当前策略，漂移丢弃结果、不再评分。新增3项测试；巡检/裁判组合27 passed。
- 补扫新增16项测试；Runtime observation_id在无上下文fallback时也统一为64字符摘要。追加原生SQLite导出断言，started/signal/completed必须同owner，Runtime相关定向47 passed/6 warnings。
- EvalFlow最新整个 `tests/eval_platform`：277 passed / 2 warnings（20.21s），`.local-stack/phase-inspection-combined-latest.log`。此前274项在策略漂移修复前，保留历史日志。
- 前端组合：EvalFlow三套件11 passed（巡检汇总、启动回归、原生审核扩展）；源平台三套件19 passed（巡检、反馈、消息列表），日志分别为 `phase-inspection-web-combined.log` / `phase-inspection-source-web.log`。
- EvalFlow主/shared TypeScript检查退出0；源平台 `pnpm build`（含vue-tsc）通过，Vite仍提示既有大chunk警告。两侧范围ESLint通过；EvalFlow全扩展/测试、Agent API与Runtime受影响范围Ruff通过。首次静态检查的复合断言/大括号/导入排版问题已修正；Agent环境无ruff，使用已有uv工具缓存执行，没有安装全局包或共享应用venv。
- 监控模板YAML可解析，scrape_configs/rule_files/alertmanagers为空，现有compose和prometheus未引用新模板；本机无promtool，未启动Prometheus或测试通知通道。
- `make guard`通过，`mlflow/`无改动；两仓 `git diff --check`通过。README/四专题/08的本地链接和代码围栏检查通过，未新增全局tasks文件。测试集有重叠，不把各数字相加当作唯一总量。

可复验命令（在对应Worktree/服务目录）：

```bash
# EvalFlow根目录
.venv/bin/python -m pytest tests/eval_platform -q
.venv/bin/ruff check eval_platform tests/eval_platform
make guard
# EvalFlow web/
npm test -- --runInBand src/evaluation-tasks/InspectionSummaryControl.test.tsx src/evaluation-tasks/AgentRegressionControl.test.tsx src/experiment-tracking/pages/experiment-review-queue/CurationPanel.test.tsx
npm run type-check
# Agent apps/platform-api/
.venv/bin/pytest tests/test_evaluation_inspection.py tests/test_evaluation_feedback.py -q
# Agent apps/runtime-service/
.venv/bin/pytest tests/middlewares/test_loop_detection.py tests/middlewares/test_loop_observation_calibration.py tests/observability/test_loop_observation_mlflow.py tests/observability/test_mlflow_tracer.py -q
# Agent apps/platform-web/
pnpm exec vitest run src/modules/chat/components/InspectionConsent.spec.ts src/modules/chat/components/MessageFeedback.spec.ts src/modules/chat/components/ChatMessageList.spec.ts
pnpm build
```

EvalFlow `.local-stack/inspection-browser-result.json`只记录两批ID/实验/状态/采样率；两条记录not_sampled，budget文件0。上述脚本日志与浏览器debug属私有验证材料，不进入Git；公开记录仅链接脱敏截图和结论。

## 最新本地服务与重启回读

通过各自 `scripts/local-stack.sh` 重启了Agent platform-api、runtime-worker、runtime-api及EvalFlow backend；Agent登记状态全部running、Runtime/API ready。EvalFlow 5011后端就绪，前端9138仍运行。重启后使用browser-skill新任务窗口，以flywheel-reviewer打开巡检汇总，仍显示撤权样本已排除；截图 `38-inspection-summary-after-restart.png` 已核对。浏览器任务窗口全部关闭，常驻本地联调服务保留；未操作主工作区或生产。

### 队列与额度补验

增加3项明确的派发前负例：队列满不再创建批次、每日请求额度耗尽不再调用、Token预算不足首请求即拒绝。巡检模块21 passed；完整EvalFlow后端再次执行为 **280 passed / 2 warnings，25.40s**，日志 `.local-stack/phase-inspection-all-280.log`。此前277/274是同轮中间结果，不与280相加。

### EvalFlow 默认构建的真实失败（不隐去）

`npm run build`退出1：ESLint报告33个文件/124条错误，其中本次新增`CurationPanel.tsx`有3处curly问题，已补大括号并执行范围ESLint和组件回归；其余32个文件/121条错误在本轮未修改文件中，主要为formatjs手工id、index.tsx导入/console及既有history使用。实际差异交集检查见私有`.local-stack/build-baseline-analysis.json`，不能只凭“以前失败过”归因。

保留失败日志`phase-inspection-eval-build.log`；另以`DISABLE_ESLINT_PLUGIN=true npm run build`执行编译检查，范围ESLint/TypeScript独立验证。即使该编译通过，也不代表默认构建或全仓lint通过；没有为本功能修改32个无关页面或放宽项目lint配置。

独立编译进程最终退出0，日志`phase-inspection-eval-build-isolated.log`明确输出`Compiled successfully.`及构建产物就绪；仍有大bundle提示。`CurationPanel`修复后组件回归为4 passed，日志`phase-curation-lint-fix-test.log`。因此结论为“范围lint/类型检查及独立编译通过；默认构建未通过”，不能将121条未修改文件中的lint错误隐去。该结果属于Phase，联合Final仍未执行。
