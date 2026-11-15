# 非管理员回流、反馈撤权与前端证据

日期：2026-11-13。范围：Task 1.2、2.0–2.4、3.1–3.2、4.1、4.3 的局部实施与 Phase 验证；不构成 Final。

## 环境与身份

仅使用双 Worktree 的 `wt_517a1ace499a` 合成环境。Agent Web/API/Runtime 端口为 28808/25087/26645；EvalFlow Web/API 为 9138/5011。未部署生产、未导出生产资料、未提交或推送本轮代码。

EvalFlow 使用 basic 认证，后台 `flywheel-worker` 不是管理员，仅在实验 1、2 有 EDIT；审核人 `flywheel-reviewer` 使用原生队列。custom queue `rq-7515ef84b18b438b8700e93893d6bbb1` 由 worker 拥有、reviewer 为成员；配置不全、实验不符、审核人非成员均拒绝接收。旧个人队列保留历史。

## 实现与原因

- EvalFlow `eval_platform/feedback_projection.py`：HUMAN Assessment 使用稳定 UUID，写前持久化预期 Trace→Assessment 关联；丢响应后重读同一 ID，不重新生成。15 秒巡检、每次最多 10 事件、目录上限 1000；投影最多 8 次/15 分钟，已关联项每 60 秒复核源授权。
- 撤权不能使用 `update_assessment(valid=False)`：实际版本忽略该字段。改为创建固定 ID、`overrides=原评价ID` 的 CODE 撤销记录，原生存储使旧 HUMAN 记录失效。重读 `valid=false` 后才记 `revocation_verified=true`，不改写人类原评分。部分写入、回执丢失、撤权暂态失败均可恢复。
- EvalFlow `eval_platform/curation.py`、`dataset_registry.py`、CLI 和任务入口继续复核源授权、冻结 hash 和原生审核完成时间；旧审核缺可信时间绑定时不补造字段。
- EvalFlow `eval_platform/scorers/agent_platform.py:score_case()` 与 `run.py`：纯确定性评分不加载裁判资源、不构造模型客户端；记录裁判请求/Token 为 0。语义评分仍要求真实资源。
- EvalFlow `eval_platform/access.py:restrict_assistant()`、`app.py`：basic 服务封锁 Assistant 主机执行路由。仅隐藏按钮不能封锁反代到 localhost 的执行能力；未修改上游 `mlflow/`。
- Agent `MessageFeedback.vue`：独立显示投影状态，可刷新；刷新撤权/到期时清除旧的 exported 展示。源 `service.py:read_feedback()` 在没有投影回执时也正确返回撤权/到期不可用。
- EvalFlow `web/src/evaluation-tasks/api.ts`、`AgentRegressionControl.tsx`：确定性 4xx 拒绝允许修正输入，不再提示结果未知；网络失败/超时保留原请求快照。

## 真实 browser-skill 全链路

纯合成题：23 + 19，只返回数字，禁止工具/网络/文件；真实 Agent 输出 42。先在源前端保存反馈、授权与投递，再以非管理员在原生队列完成审核、确认 v2 材料、发布冻结版本、从评估运行页启动真实 Agent 回归并查看逐题结果。

| 关联 | ID |
| --- | --- |
| 源 Thread / Run | `61ad59cc-e450-4cec-ab13-ca2bbcf75531` / `4cde3470-7116-4ccd-8bf1-e8009f52bc3c` |
| 反馈 / export | `40865041-f3b1-4669-869a-4a9a51c21a64` / `c47b6bf7-c810-4f2d-8a54-fe8d6673e27f` |
| 候选 Trace | `tr-e064582ac5724d2aecaeb8b8d37dc6fa` |
| 源 Run Trace / HUMAN Assessment | `tr-ccc900dde1cf470024be6e10478874d9` / `750e5909-3f0c-5d58-ab5f-fea4f894f280` |
| 发布 Dataset / version | `d-6574d9cc3b694da9a0b038ed0eb1bfdb` / 1 |
| content_hash | `de38d801a47191888511369b5611c310705f38724f224e28b680a7caf9c32e54` |
| 任务 / MLflow Run | `4e082561-360f-4d97-81ff-11862d7a5c90` / `c5fc219a2c1b4be2b7a01f6d332ea6bb` |

结果：1/1 completed；completion、answer_contains、tool_budget 三项通过，gate exit 0。tool_budget 只证明零工具请求，不等同执行/阻断副作用证据已实现。纯规则裁判无模型请求。

随后从源前端撤权，同一 Dataset 再次创建任务返回 `Source authorization revoked or expired`，未新增执行。后台实际核对原 HUMAN `valid=false`、投影 `revoked` 且 `revocation_verified=true`。

截图（均保留原文件）：
- [08 源反馈恢复](08-feedback-recovered.png)：无原 502 横幅。
- [09 原生审核发布](09-worker-owned-review-published.png)：published、Dataset/hash 回执。
- [12 逐题三项通过](12-nonadmin-case-results.png)。
- [13 源前端撤权](13-source-authorization-revoked.png)。
- [14 撤权拒绝新回归](14-revoked-regression-denied.png)：保留修复前不准确的重试提示作为问题证据。
- [15 服务恢复后的运行列表](15-regression-list-recovered.png)：后端重启后重新采集，已视觉复核，无服务不可用横幅。
- 07 为 502 失败现场；10 有暂态遮罩；11 虽显示成功结果但带服务不可用横幅。三张均不能作为无异常成品验收图。

## Phase 测试记录

- 前阶段 registry/curation/contracts/evaluation/curated execution 组合：84 passed（补记前阶段实际终端结果）。
- 最新 feedback_projection、curation、access_boundary、curated_execution、flywheel_contracts：54 passed；有既有 pytest timeout 配置 warning。
- Agent `tests/test_evaluation_feedback.py`：19 passed，包含无回执撤权/到期、投影超时与 pending 区分。
- Agent `MessageFeedback.spec.ts`：9 passed，覆盖刷新、投影状态、旧请求丢响应与切消息竞态。
- EvalFlow `AgentRegressionControl.test.tsx`：5 passed；既有 React/路由弃用警告，不影响结果。
- EvalFlow 本次相关 Python 文件 Ruff check 通过。
- 重启后真实 HTTP：非管理员 GET 原生实验 200、匿名 GET 401；Assistant GET config / POST sessions 均 404。普通业务与封锁入口分别核对。

## 尚未解决的安全与验收边界

原生 Dataset 按 experiment 授权，Trace/Run 读取也要求 experiment 权限。扩展拒绝新运行、旧 HUMAN 失效，**不等于撤权后原生 Trace/Dataset/历史 Run 内容不可读**。用户已于 2026-11-13 批准「按授权批次隔离实验，撤权后封闭访问」；接续实现与测试见 [授权批次记录](03-authorization-batches-and-budgets.md)。此处旧共享实验证据不作为新方案验收证据，真实生产资料仍未启用。

可信 CI runner/secrets、独立盲测评审人经用户确认暂时没有；A04 远端沙箱准入、旧 KnowledgeRetention 分歧及两仓生产部署记录差异不因本次合成验证消失。旁路真实 Worker 分母/性能、在线抽样预算、可靠 executed/blocked 证据、G3、合成安全专题与联合恢复仍需继续实施验证。
