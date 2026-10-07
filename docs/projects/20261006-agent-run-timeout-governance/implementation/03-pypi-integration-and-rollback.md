# 正式包接入、停止确认交接与匹配回退

日期：2026-10-07；对应T10/T13、T12非前端门禁。用户确认取消专项结束并恢复工作。进度只看tasks.md；平台整体仍partial，仅剩同事前端与联合Final。

## 发布包与依赖

复用GraphHarbor取消专项已发布的post42四产物；两个PyPI版本的SHA256等于正式发布清单，未重复上传或使用历史同版本候选包。本轮不需要再读取发布令牌。

`apps/runtime-service/pyproject.toml` 与 `uv.lock` 仅将GraphHarbor双包提升到 `0.13.0.post42` 并替换产物信息；其他依赖版本不漂移。Runtime `uv sync --frozen`、141项依赖check及独立冻结环境142项check通过。API自己的锁文件不变，SDK0.4.2/Python3.14.6另行通过85项定向unittest。

## 验收脚本与停止事实

- `scripts/verify_run_timeout_budget.py`：纠正cancel验收断言，平台响应实际为HTTP200 `{"ok":true}`，原生GraphHarborwait=false的202不能套用到网关。修正后二轮正式包完整12组通过，包含真实SIGTERM/PID接管、SSE/竞态/防注入。
- `scripts/verify_run_timeout_rollback.py`：新增匹配源码/双包回退验收。复用GraphHarbor CLI、原生API/Worker和stdlib临时目录；真实Reference Agent组合根、fake model及测试Auth，不增加供应商依赖。独立固定测试库/Redis前缀守卫、进程退出与资源清理；暂停提交/drain后切换旧Runtime/post41，断言同Run checkpoint继续且prepare不重执行、pending/历史/产物保留、普通/取消/HITL可用。
- `apps/platform-api/tests/test_run_timeout_contract.py:test_stop_confirmation_is_preserved_by_stream_projection_and_redaction`：补生命周期投影与脱敏的公开停止字段回归，true/false及lease_fenced保持，私有预算过滤；无需新网关接口或业务状态表。

前端须通过同一路径JSON body `{"wait":true,"action":"interrupt"}` 或目标Run `execution_stopped=true` 事件确认停止。平台路由不转发SDK query wait/action；默认ACK/GET interrupted可早于资源退出。新SDK query参数不能代替平台body，502/504结果保持待核实。具体状态、代码位置及F01-F10见frontend-handoff。

## 证据与交付

真实结果记录在 [verification.md](../verification.md) 新Phase，原始日志/回退JSON/冻结依赖/四产物清单和微基准保存在 [evidence](../evidence/README.md)。Runtime/API全量各两项旧失败已在旧源码复现；不改无关PTY/HTML逻辑，不把skip或重叠定向数字算作通过。

README/方案/任务/服务标准/CONTEXT/FEATURES/CHANGELOG统一为正式post42接入事实；原404/高负载/暂停轮次保留在历史Phase。前端源码由同事实现，平台Final等待其交付；其他SSE/JWT草案不毕业。当前detached HEAD，基点 `0bc15df1840c83750d821c93fb65600d0d483fa4`，没有分支/commit/push，未重启共享现役或部署远端。

## 详细前端交接与经验沉淀

2026-10-07用户要求详细交接并批准写入经验库。核对实际service/composable/组件与锁定JS SDK后，补充[交接第7节](../frontend-handoff.md#7-接手即执行的开发稿)：可见timeout、JSON wait=true停止确认、目标Run/epoch守卫、各发送与队列入口、非success推荐门禁、UI状态/开发顺序/真实环境与回执。推荐一个wait=true请求即可完成提交与确认，保留默认ACK路径时仍须额外确认；核实按钮不能因持续待确认而永久禁用。

现有三处事实缺口已明确：timeout文案只在sr-only中；stop/verify/finally可能把公开interrupted提前当作退出；推荐问题只看运行结束与末条AI消息。前端源码由同事实现，T11/F01-F10与联合Final仍未完成。用户批准的多会话发布产物归属经验写入[AI工作流经验库](../../../lessons/ai-workflow.md)，索引及CONTEXT同步；本次没有新增Web执行证据。
