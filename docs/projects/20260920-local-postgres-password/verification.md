# 验证记录

状态：已完成（done）。本地认证、回退、应用链路及配置文档验证通过，2026-09-21 远端交接同步与校验通过。

## 2026-09-20 只读检查

- PostgreSQL 17.11；password_encryption=scram-sha-256。
- lijiaxin：超级用户，可登录，无密码；platform_api：非超级用户，可登录，有 SCRAM 密码。
- 所有现有本地 HBA 规则为 trust，pg_hba_file_rules 无解析错误。
- 当前可见 Runtime 13 个客户端连接、平台 5 个客户端连接；仅是检查时快照。
- ~/.pgpass 不存在；未创建该文件。

禁用 PG 环境变量及密码文件，以 psql -w 新建连接、执行 SELECT 1：

| 角色 / 数据库 | 未提供密码 | 提供错误密码 |
|---|---|---|
| lijiaxin / graphharbor_acceptance | 连接成功（未认证） | 连接成功（未认证） |
| platform_api / platform_api | 连接成功（未认证） | 连接成功（未认证） |

结论：仅在 URL 中填写密码无法满足目标，必须修改实际匹配的 HBA 规则。

## 实施后必要验证

- [x] 两个可登录角色都有 SCRAM 密码，输出仅布尔状态，不输出 verifier；平台原密码未改。
- [x] HBA 无解析错误，6 条规则均为 scram-sha-256，没有残留 trust。
- [x] 两个业务角色正确密码的新连接成功（IPv4、IPv6、Unix socket）。
- [x] 隔离 .pgpass 后，缺密码和错误密码的新连接均拒绝；共 18 项验证。
- [x] ~/.pgpass 正常工具连接成功，文件权限 600。
- [x] 抽检 postgres、nano_brain_db、platform_api 三库与三个连接通道，共 9 项，不修改业务表。
- [x] 应用实际配置连接成功，Runtime /ready 的 graphs/postgres/schema/redis/queue 均 true；平台健康 status=ok、database_ready=true。
- [x] Runtime API/Worker 已重启；平台 5 条旧空闲连接回收后创建 5 条新的认证连接。
- [x] 回退备份校验通过；实际回退再重新实施，管理连接始终保留。
- [x] 全仓库文档检查、diff 空白检查通过；本轮 12 个文件的链接/秘密/YAML 检查和 33 段 shell 示例语法通过。

本次没有业务代码实现，普通业务单测不能替代上述真实认证检查；性能压测不适用。
如端到端或回退证据不全，最终标 partial 并列出缺项，不伪称 done。

## 真实应用链路

通过当前 Vite 前端代理（3000），依次完成：

1. 平台管理员登录和认证身份读取。
2. 平台项目列表读取（平台 PostgreSQL 新连接）。
3. 携带项目上下文访问 Runtime 网关 info。
4. Runtime threads/search 读取会话（Runtime PostgreSQL 新连接）。
5. 撤销此次验证的 refresh token。

以上全部成功。没有创建新项目、聊天、运行或调用收费模型；登录自身的会话/审计写入属于验证正常副作用。
检查时 Runtime 只有 4 条 success 运行，无排队/执行中任务；未中断业务运行。
最终四个开发进程 running，Runtime 和平台健康检查成功。

## 验证边界

- 此次数据库认证目标及跨服务读链路已验证；不宣称每个其他项目或每种驱动都已验收。
- 不读取 .pgpass 的其他客户端仍需显式配置密码。
- lijiaxin 原超级用户权限保持不变，角色拆分不属于本轮。
- 腾讯服务器只更新交接文件，未修改其数据库、认证规则或运行应用。

## 交接同步

此前 SSH 握手超时；2026-09-21 重试连接成功。
新版精简运维包（operator-deploy.tar.gz）上传至 `/root/ai-agent-platform-handoff/20260920-225507-operator/`。
远端归档 SHA-256、MANIFEST.sha256 全部文件及私有目录 700 / 文件 600 检查通过，返回 OPERATOR_UPLOAD_VERIFIED。
包含最新文档与服务器应用配置，业务密码与本地一致；不包含本机 .pgpass、PG 备份、角色 verifier 或根目录发布凭据。
本地认证与文件交接目标已完成；目标服务器的实际部署、空库初始化和模型聊天验收仍由运维执行。
