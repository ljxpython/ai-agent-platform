# LangGraph Server Worker 对照

核对日期：2026-10-07。用户要求“GraphHarbor 要按照 LangGraph Server 的能力实现”，取代 10-06 的跨 attempt 固定总截止点设计。目标版本仍为 `langgraph-api==0.13.0`、`langgraph==1.2.11`、`langgraph-sdk==0.4.3`，不借用未知版本推断。

## 官方实际行为

| 能力 | 官方证据 | 本次 GraphHarbor 对齐 |
| --- | --- | --- |
| 后台执行硬限 | `worker.py:272` 每次 `worker(run, attempt)` 使用 `asyncio.wait_for(..., BG_JOB_TIMEOUT_SECS)`，默认 86400 秒 | 每次 claim 生成当前 attempt 的 H 与截止时间；工厂/模型/工具共用该 H |
| 重试后的时钟 | `worker.py:146/272` 新 attempt 重新初始化开始时间并等待完整 H | 同 run_id retry、重启/接管获得新 attempt H；不累计排队/停机/退避 |
| Worker 硬超时 | `worker.py:350` 设置 `status=timeout`，不会进入 retry 分支 | 复用 `RunTimedOut` 与唯一 timeout 终态 |
| 用户/provider 超时 | `worker.py:220` 将图内 TimeoutError 包成 UserTimeout；`worker.py:465` 解包并落 error | 模型 scope/provider TimeoutError 不触发整图 Worker 重试；graph 内显式 retry/fallback 保留 |
| 可重试错误 | `worker.py:ALL_RETRIABLE_EXCEPTIONS`；取消/受支持的瞬时数据库故障重新 pending | 受支持的数据库断连/序列化/死锁与 RetryableException 有界重试；普通 OSError/ConnectionError 不自动重跑图 |
| 次数上限 | 文档默认 BG_JOB_MAX_RETRIES=3；锁定源码 `worker.py:229` 拦截 attempt>3 | 按锁定源码对齐为默认最多 3 个执行 attempt，支持配置；不能把文档措辞直接算成 4 次执行 |
| 优雅停机 | 官方配置默认 180 秒、最大 3600；停止接新任务并等待，随后交接 | 保留 RunControl/checkpoint drain，宽限受当前 attempt 剩余 H 限制，之后可重新领取 |
| handoff 次数 | 官方 0.7.39 更新明确 distributed runtime handoff 不消耗 retry attempt | checkpoint drain 归还 attempt 额度；租约代次仍递增，避免旧执行污染新执行 |
| crash 恢复 | Redis heartbeat + sweeper 重新入队，PG/checkpoint 持久恢复 | 沿用 PG lease/reaper 与 Redis 心跳；失联 attempt 计入上限，后续领取有新 H |
| 模型收尾 prompt | Worker 不负责注入“请总结” | Runtime middleware 的应用能力；同 attempt 主/子共享预算，未迁入 GraphHarbor |

源码路径：GraphHarbor checkout 的 `.venv/lib/python3.11/site-packages/langgraph_api/worker.py`。本次没有修改官方安装代码。官方探针入口为独立仓库 `scripts/verify_official_worker_timeout.py`，执行真实官方 `worker()`，替换 graph 消费、数据库和状态写入为隔离 sink；验证 Worker 分支，不等同官方生产数据库/分布式部署差分。

官方来源：[环境变量](https://docs.langchain.com/langsmith/env-var-self-hosted)、[扩缩容与恢复](https://docs.langchain.com/langsmith/scalability-and-resilience)、[Agent Server 更新记录](https://docs.langchain.com/langsmith/agent-server-changelog)。文档与锁定源码的次数措辞有差异，实际测试以锁定源码为准。

## 最小实现边界

GraphHarbor 保留原 REST/SSE/RunStatus，不新增累计总期限模式、公开倒计时字段或平台业务策略。`__graphharbor_run_budget` 是供 factory 消费的私有桥接，每次 attempt 更新；UTC 可在 PG 内观察，monotonic 只在当前 Worker 使用，公开 JSON/SSE/history 不包含它。

复用已有 `retry_counters` 区分执行 attempt 和 `runs.retry_count` 租约代次，不新增 migration。正常 checkpoint handoff 可以多于三次，但实际故障执行仍有配置上限。主/子 Agent 和 workflow 重建只能共享当前 attempt 的同一预算，不自行创建时钟。

官方变量可用：`BG_JOB_TIMEOUT_SECS`、`BG_JOB_MAX_RETRIES`、`BG_JOB_SHUTDOWN_GRACE_PERIOD_SECS`。已有 GraphHarbor H/drain 配置保留为优先别名；平台模板继续使用自己的 1800/300 秒 H 和 G=120，未将平台生产时长改成官方 24 小时。

此文件只定义本次超时/重试/停机切片。GraphHarbor 自己的 lease/reaper 实现、状态 reason 扩展、流回放窗口和全部 Server 协议的兼容程度仍以独立仓库 Compatibility Profile 为准；本切片通过不等于完整 drop-in。

## 验证与交付

任务由本项目 T13 与 GraphHarbor G05-G07 跟踪；结果只写实际执行的 Phase。原“重启后 H=600 仍按首次 30 秒到期”的证据保留为原设计历史，不再作为本轮验收。

新场景已在正式PyPI post42通过：旧attempt deadline后，同run_id由新PID使用新H从checkpoint继续；模型error、唯一终态、六次drain不占故障额度、旧租约拒绝写入、SDK/HTTP/SSE脱敏均有证据。正式发布/锁定和匹配版本回退已完成；同事前端F01-F10与联合Final仍待交付，见verification的新Phase。
