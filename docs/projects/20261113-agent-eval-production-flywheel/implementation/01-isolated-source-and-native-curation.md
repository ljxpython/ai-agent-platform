# 隔离源反馈与原生审核接入（进行中）

日期：2026-11-13。相关 Task 1.2、2.1–2.4、3.1–3.2、4.1、4.3。任务完成状态仍以四专题任务卡为准；本文不代表完成验收。

## 环境与边界

- Agent：`/Users/<name>/.codex/worktrees/344c/ai-agent-platform`，环境 `wt_517a1ace499a`，Web 28808 / API 25087 / Runtime 26645。
- EvalFlow：同级 `mlflow-eval-platform`，Web 9138 / API 5011，独立 SQLite/auth 库、`.venv` 与前端依赖。
- 数据限定为专用项目中的人工合成资料；主工作区、生产部署及上游 `mlflow/` 未修改。生产外发/干预和真实 CI 尚未验收。

## 实现与理由

- Agent `apps/platform-api/src/platform_api/modules/evaluation/`：追加式反馈、项目/会话 ACL、版本与幂等校验、合成清洗授权、接收回执与撤销。源授权在每次读取及保存迟到回执时重查用户、成员、反馈和有效期，避免撤权后恢复导出。历史已验证反馈修改不依赖仍在当前 checkpoint 中的消息。
- `apps/platform-api/migrations/versions/20261113_0011_evaluation_feedback.py`：新增反馈/授权表；回退关闭功能保留事实，再升级检查已有表，不重复建表。隔离 PostgreSQL 首次升级已执行；保留数据再升级单测通过，真实 PostgreSQL 回退复验待执行。
- Agent `apps/platform-web/src/modules/chat/components/MessageFeedback.vue`：评价、修改、撤回、人工合成材料授权/投递/撤销，以及重新打开后的状态恢复。组件测试与刷新浏览器复验待完成。
- EvalFlow `eval_platform/access.py`、`app.py`：复用原生认证身份，加固定项目/实验/操作/到期约束。发现原生 auth factory 在本安装环境已返回 FastAPI，修复重复包装造成的 500；发现旧实验权限 REST 地址不存在，实际使用当前 AuthServiceClient.grant_user_permission()。
- EvalFlow `curation.py`、原生 Review Queue 的 `CurationPanel.tsx`：候选绑定原生 Trace/审核队列；审核身份从服务器读取，发布带来源关联与 hash。Registry 在所有发布/执行入口重查来源授权，并校验原生记录与已审核材料一致，防止直接编辑原生 Dataset 绕过审批。
- EvalFlow `contracts.py`、`scorers/agent_platform.py`、`gates.py`、`run.py`：v1 序列化保持；v2 provenance、严格 JSON/CSV 断言、工具证据不足报 error、确定性失败不可 soft、逐题比较。fixture 引用、完整预算、校准等仍未完成，不能宣布完整 v2 已支持。

## 已执行 Phase 证据

- Agent `apps/platform-api/.venv/bin/python -m pytest apps/platform-api/tests/test_evaluation_feedback.py -q`：14 passed；涵盖幂等/版本、跨项目、清洗、成员/账号/反馈撤权、过期、迟到回执及迁移保留事实再升级。
- EvalFlow 新契约测试上一阶段 13 passed；旧回归上一阶段 41 passed；最新局部回归正在执行，不沿用旧结果代替新验证。
- Agent vue-tsc 上一阶段成功；本次新增状态恢复后仍须复验。
- 原生认证真实 HTTP：匿名 401；source/reviewer 对实验 1 的 EDIT 授权回读成功，旧接口 404 已确认并改用本仓统一资源权限接口。
- browser-skill：专用项目新建对话，真实模型回复合成算式 17+25 为 42；Thread `cf3f5bba-e213-43a6-8324-8bc843514f85`，Run `f8491f62-df94-4e57-b42b-6f6177545d5b`，API 终态 success。后续反馈→审核→发布→主动回归未完成，不计 E2E 通过。

## Phase 接续：真实审核发布与执行

以下为同一隔离环境中的新增证据，替代前段「后续链路未完成」的当时状态；不代表生产回流或本项目 Final。

- browser-skill 实际完成源反馈授权、投递、原生审核、材料批准、冻结发布和主动回归。export `070ce437-a41a-4aa0-95e2-e9b1ec1ac09a`；候选 Trace `tr-9864a5cd7ad75d2b8eb49e0dfd72e734`；Dataset `d-561951ec96b141ee9a32d30f05ca0a76`，hash `9ca1b14ffabce0d0fab4e6ab456b162a581596a0dcc72ed5139ba1cb1daf7b6e`。
- 主动任务 `9d1da821-97d2-43da-b5c8-a50b6b483845`，MLflow Run `97b01c12b6784229a325086dbca7398a`：1/1，completion / answer_contains 均 pass，gate 0。该案例未验禁工具约束。
- 截图 `01-feedback-authorized.png`、`02-export-received.png`、`03-native-reviewed.png`、`04-frozen-published.png`、`05-regression-loading-investigation.png`、`06-regression-result.png` 保存在本目录。05 实际显示成功运行列表：调查确认 loading 来自过时浏览器观察，不是重复提交或业务卡死。05/06 已视觉复核。
- Runtime 业务 UUID 写入助手消息 `response_metadata.runtime_run_id`，区别供应商 run_id；API 只接受并核实该业务 Run。63 项 RuntimeConfig/LoopDetection 测试通过，真实 Worker 新消息锚点仍待复验。
- Agent 反馈组件新增跨消息响应隔离、未知结果保留原请求重试、丢失保存响应 GET 对账、明确 4xx 恢复编辑；反馈组件与消息列表合计 12 项通过，vue-tsc 通过。
- EvalFlow 原生审核完成身份和时间戳绑定材料批准；重新打开审核后旧批准失效；支持拒绝/补材料。CurationPanel 4 项组件测试通过。旧发布记录缺新审核快照，不伪造回填，须真实重审或新建候选。
- v2 强类型断言、空断言拒绝、JSON 布尔/数字区分、缺少取证报 error，以及 registry 重开阻断等组合 79 项通过。首次测试追加位置错误引发 NameError，修复后重跑通过。
- CLI 执行、评分及重新发布统一核对来源授权、原生审核与完整数据 hash；新增 5 项边界测试。首次运行 81 pass / 3 fail，定位为发布快照是 JSON 数组、误用 JSONL 读取，已修复，复验结果后续追加。

## 当前缺口

可靠 Assessment 投影、旁路探针真实 Worker/分母验证、抽样/预算/告警、fixture 生命周期、独立盲测、裁判校准、完整 G0–G3、CI runner、合成/安全专题及独立 Final 均保留未完成。受控副本删除、失败恢复、性能/回退证据必须继续补齐。
