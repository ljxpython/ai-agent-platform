# T00 兼容性与隔离环境（2026-11-13）

开发位于两个 feat/agent-evaluation-system Worktree；未提交、推送或部署生产。
业务栈 wt_3a133f065724：Web 23419、API 25409、Runtime 29256、Redis 25954；
EvalFlow 后端5011、前端9138，独立SQLite和artifacts。

## 已执行证据

- EvalFlow Python3.13、MLflow3.18.1.dev0、DeepEval4.3.4、OpenAI3.49.0、MCP1.30.0；依赖在 eval_platform/requirements.lock。
- xiaok deepseek-v4.1-flash真实JSON探针返回5；百炼text-embedding-v4真实向量1024维。
- 官方MLflow TaskCompletion桥接真实判定yes；证据位于EvalFlow .local-stack/preflight-models.json、preflight-scorer.json。
- Dearflow真实单轮成功，完整Trace精确包含runtime run_id；证据 .local-stack/probe-real-3/evidence.json。
- 当前原生桥接存在多段审批Trace丢前序工具和StepEfficiency空内部Trace问题；T05使用完整Evidence映射DeepEval公开输入，效率用G-Eval，禁止修改上游mlflow/。

## 发现与处理

- 系统uv0.9.9不能读取当前配置；使用用户已安装uv0.13.7。根workspace引用缺失开发包，独立扩展安装不修改上游workspace。
- output max_tokens 16000超既有模型profile；改4096。
- 工具动作预算20与LangGraph中间件递归步数不可混用；递归上限200，工具预算独立计量。
- Thread必须metadata.graph_id；顶层graph_id不足以支撑文件接口。
- 项目可见Thread禁用个人记忆且强制review；采用题库显式路径白名单批准write_file/edit_file，保留安全策略。
- resume接口只允许assistant_id和command，不能追加evaluation metadata；以新run_id、所属独立Thread和Trace绑定。
- cancel接口要求Idempotency-Key。
- 合成MCP使用临时socket独占端口，百炼真实索引；禁用该Worktree继承的外部知识连接与知识上传，不改生产。
- 首批23项契约/门禁/隔离单测通过。Smoke仍在校验，不能作为Final。
