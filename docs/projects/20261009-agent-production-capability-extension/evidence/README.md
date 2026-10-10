# 非前端验收证据

本目录仅保存脱敏的测试结果、事件/运行 UUID、统计和正式产物哈希，不保存 `.env`、签名、回调正文、HTTP headers、账号 token 或数据库文件。

- `release-manifest.json`：已发布 PyPI 的双包四产物及来源核对。
- `source-worker-*.json`：源码隔离链路的普通/定时/回填/停止/重启记录。
- `official-post44-tail.json`：原生本地正式包尾段的定时/回填已执行步骤；队列等待失败、重启未执行，不代表整项通过。
- `capacity.json`：100k 事件下20 callback/s、10 feed/s 的延迟和查询计划。
- `backlog.json`：5min接收端故障、两个dispatcher、20 snapshots恢复。
- `rollback.json`：正式post43/head011与post44/head012回退、独立Outbox保留和恢复。
- `mixed-*.json`：新旧API/引擎组合的原有运行冒烟。
- `official-post44-focused.json`：正式 PyPI post44 的成功、重试耗尽、取消/停止确认最短 completion 链路，1 passed。
- `test-results.json`：实际JUnit统计、SHA256与失败条目，包含正式包 CAS、v6/v7、最短链路和尾段；失败不会计为通过。

真实对接响应在 [frontend-contract](../frontend-contract/real-responses.json)，HTTP availability/故障夹具与真实 Worker 响应分开标注。
