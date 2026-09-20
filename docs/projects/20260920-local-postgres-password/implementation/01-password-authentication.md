# 本地密码认证实施

日期：2026-09-20。用户已明确批准全实例方案。

## 实际变更

- 本机 `/usr/local/var/postgresql@17/pg_hba.conf`：6 条本地 trust 规则改为 scram-sha-256，
  覆盖 Unix socket、IPv4、IPv6 及复制连接。通过 pg_reload_conf 生效，没有重启 PostgreSQL。
- 数据库角色 lijiaxin：使用客户端生成的 SCRAM verifier 设置密码，与服务器交接配置中的 Runtime 密码一致。
  私密值及 verifier 不输出；平台角色原有 verifier 保持不变；没有改变角色权限或库 owner。
- `apps/runtime-service/.env`：DATABASE_URI 加入密码，权限 600。
- `~/.pgpass`：明确限定本机地址、5432 端口、两个业务角色，权限 600。
  原来没有该文件；不使用主机或用户名通配符。
- Runtime API 和 Worker 在确认无运行中任务后通过 local-stack.sh restart-one 重启。
- Platform API 原连接密码正确，保持进程；仅回收 5 条空闲 PG 连接，以 pool_pre_ping 自动重连，
  验证数据库新连接认证，未运行平台迁移。

## 私有备份和复查

备份目录：`~/.my_best/backups/postgres-auth-20260920-233424/`，目录 700、文件 600。
包含原 HBA、Runtime/Platform env、角色原密码状态、文件清单与校验、脱敏验证结果。
原密码文件不存在的状态也被记录。备份不提交仓库、不上传服务器。

持久保存的认证复查脚本不含密钥，直接读取本机受保护的应用配置。仓库根目录执行：

```bash
"apps/runtime-service/.venv/bin/python" \
  "$HOME/.my_best/backups/postgres-auth-20260920-233424/verify_auth.py" "$PWD"
```

该检查隔离密码文件，只执行 SELECT 1；预期输出 authentication_checks_passed=18。

## 回退演练

保留管理连接，首次应用后验证两个角色可用，再实际恢复原 HBA、角色密码状态和配置文件，
reload 并确认回到原认证行为；核对恢复文件与备份字节一致、lijiaxin 原密码为空。
随后重新应用批准方案并完成全部正反向验证。未操作业务表、未恢复数据库快照。
以后回退须明确批准并按备份 manifest 恢复配置和角色状态，不直接关闭当前管理连接。

## 文档和交接同步

部署手册、配置矩阵、部署契约、数据库规范、根 README、FEATURES 更新为实际密码认证状态。
服务器原始 env 备份保留交接当时内容；服务器可用 Runtime 配置原本已含同一密码，无需轮换。
新版交接包已在本机另存当前 Runtime env 快照，不包含 macOS 的 .pgpass、PG 配置或备份。
此前远端 SSH 握手连续超时；2026-09-21 重试成功，新版精简运维包已上传并通过归档、逐文件哈希和私有权限检查。服务器实际部署留给运维。

## 验证

真实认证、应用重连和跨服务 HTTP 链路见[验证记录](../verification.md)。
没有业务代码、表结构或生产部署变更，业务单测和性能压测不替代本次实际认证检查。
