# Runtime 沙箱：本地与单节点远端 Docker

适用代码：`apps/runtime-service/src/runtime_service/workspace/`、`sandbox_node/`。方案已获人工批准，三模式/两图公网完整链已验，2026-10-13 本期用户验收通过；正式整机重启/后续独立 Final 和真实编辑等 [后续事项](../projects/20261012-runtime-remote-docker-sandbox/follow-ups.md) deferred，原测试事实以[验证记录](../projects/20261012-runtime-remote-docker-sandbox/verification.md)为准。当前未授权现役平台切流，Git 合并不等于生产部署。

## 三种模式与配置归属

| 模式 | Runtime env | Docker / 文件所在位置 |
| --- | --- | --- |
| 本地开发 | `RUNTIME_BACKEND=local`，`RUNTIME_SANDBOX_TARGET=local` | 可信宿主 shell；文件在 Runtime 本地；Office 仍使用固定 Docker reader |
| 本地 Docker | `RUNTIME_BACKEND=docker`，`RUNTIME_SANDBOX_TARGET=local` | API / Worker 与 daemon 共用相同宿主绝对挂载路径 |
| 远端 Docker | `RUNTIME_BACKEND=docker`，`RUNTIME_SANDBOX_TARGET=remote` | API / Worker 经 HTTPS+mTLS 访问 Node；文件与 Docker 在 Node 本机 |

原生配置用 `apps/runtime-service/.env`，容器配置用 `apps/runtime-service/deploy/.env.runtime-service` 或对应 host-infra 文件；Worktree 用自己的 `.local-stack/runtime.env`。API / Worker 必须共享同一组目标、执行域和凭据指针。Worktree 初始化默认 local，之后 env 中显式 docker 设置生效。PG / Redis 继续用所属本地原生资源。

远端配置增加以下键，模板见[Runtime env](../../apps/runtime-service/.env.example)：

```dotenv
RUNTIME_BACKEND=docker
RUNTIME_SANDBOX_TARGET=remote
RUNTIME_EXECUTION_HOST_ID=deployment-id
RUNTIME_SANDBOX_NODE_ID=sshmy2
RUNTIME_SANDBOX_NODE_URL=https://node.example.com:19111
RUNTIME_SANDBOX_NODE_AUTH_FILE=/absolute/runtime-secrets/caller-token
RUNTIME_SANDBOX_NODE_CA_FILE=/absolute/runtime-secrets/ca.pem
RUNTIME_SANDBOX_NODE_CLIENT_CERT_FILE=/absolute/runtime-secrets/client.pem
RUNTIME_SANDBOX_NODE_CLIENT_KEY_FILE=/absolute/runtime-secrets/client-key.pem
RUNTIME_WORKSPACE_IMAGE=runtime-agent-workspace:p5-v2
RUNTIME_SHOWCASE_IMAGE=runtime-agent-workspace:p5-v2
```

凭据不写入镜像或提交 Git。AUTH / KEY 文件 600，父目录不得有软链接；证书 / CA 禁其他用户写。客户端核验 CA 与 SAN，不使用环境代理，不跟随重定向。执行失败只能按原 ID 回查，不重发命令、不换节点、不落本地 shell。Runtime 远端执行不需要本机 Docker CLI；本地 Office reader 例外仍需对应本地镜像。

## Node 安装与公网准入

Node 必须有 Linux、Python 3.13、本机 Docker socket、固定镜像和持久盘。专用非 root 账号 `runtime-sandbox` 加入 docker 组，只运行一个管理进程。Docker socket 不挂入沙箱，不监听公网 2375 / 2376。Node HTTPS 入口同时受云安全组、宿主防火墙、mTLS、caller token、执行域和源 IP 限制；SSH 用于维护。

产物使用当前 Runtime wheel 和 frozen、带哈希的依赖；API、Worker、Node 使用同一提交的协议实现。Node 使用的安装目录 `/opt/runtime-sandbox/.venv`，持久目录 `/var/lib/runtime-sandbox/{workspaces,state}`，配置 `/etc/runtime-sandbox/node.env` 与 `secrets/`；systemd 文件见[runtime-sandbox-node.service](../../apps/runtime-service/deploy/runtime-sandbox-node.service)，env 见[Node 模板](../../apps/runtime-service/deploy/.env.sandbox-node.example)。只拷贝服务器证书、服务器私钥、CA 公钥、callers.json 到 Node，客户端私钥和 CA 私钥留在各自可信环境。

在可信 Runtime 主机生成独立信任域；从仓库根目录执行：

```bash
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/sandbox_node_certificates.py \
  --output /absolute/private/node-trust-v1 \
  --server-name node.example.com --execution-host deployment-id \
  --allowed-ip 203.0.113.20/32
```

CA 私钥应离线保管。叶证书有效期 90 天，CA 为 730 天；生成器拒绝覆盖已有目录和全网源 CIDR。生产 env 的 IP 必须来自 Runtime 实际公网出口，不能使用本机 TUN 网关或 SSH 别名代替业务地址。

节点初始硬上限为全节点 2 个 reserved / running / unconfirmed 容器，最低空闲盘 5 GiB。沙箱固定 `network=none`、非 root、只读根、`cap-drop=ALL`、NNP、1 CPU / 256 MiB / 64 PID，无 publish 端口。固定 reader 镜像由 `Dockerfile.agent-workspace` 构建；不要用同名旧镜像冒充包含当前 reader 的产物。sshmy2 本轮验证镜像为 `runtime-agent-workspace:p5-v2`，两个 graph 的 env 与 `SANDBOX_ALLOWED_IMAGES` 要一致，镜像 hash 见[交付产物](../projects/20261012-runtime-remote-docker-sandbox/evidence/delivery-artifacts.json)。

启用前先验证 env，再从真实 Runtime 主机执行只读 preflight；先将所属 env 安全加载到进程，禁止把秘密打印到终端：

```bash
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/validate_runtime_config.py --env-file .local-stack/runtime.env
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/sandbox_node_preflight.py
```

Worktree 修改 env 后，通过 `scripts/local-stack.sh restart-one runtime-api` 与 `restart-one runtime-worker` 同步重启。正式容器部署则重建 API / Worker，使目标和秘密挂载同时生效；当前 Compose 默认没有远端客户端秘密挂载，容器部署需把四个凭据文件只读挂入对应绝对路径，不挂 Docker socket。通过 readiness 后仍需上传→执行→产物下载、Stop、终端、后台对账和重开原 Thread 验收。

## 生命周期、回收与恢复

| 对象 | 回收依据 | 保留内容 |
| --- | --- | --- |
| 普通 execute / reader | 退出 / 1–60 秒 timeout / 原 ID Stop；Node deadline 对账 | 同 Thread 全部工作区文件和有界操作回执 |
| 终端 | close、15 分钟无输入、1 小时寿命；Node 重启关闭旧 PTY | 文件；旧 shell 的进程、内存和临时 env 不恢复 |
| 后台任务 | runner 签名回执、最长 1 小时 deadline、取消；Runtime 先持久确认日志 / 回执再 remove | 任务记录 / 日志及工作区；未 ack 的退出容器保留证据 |
| 工作区 | Thread 已删除或人工核实孤儿、宽限到期、无未决工作，精确 apply | retained Thread 永不因闲置时间被自动删除 |

页面关闭、断网、用户离开不代表任务完成。Node 对账只检查归属本节点的资源；镜像 / 挂载 / 网络 / UID / 资源限制不一致时拒绝接管，未登记容器保持原状并关闭准入。不能使用 `docker system prune` 修复登记不一致。

同一 host / tenant / project / Thread / graph 重新进入时，核验原位置并挂原持久目录到新容器；上传、产物和技能快照继续保留。位置冲突、目录缺失、已 purged 明确失败，禁止自动创建空目录假恢复。Node / Runtime 进程重启可恢复文件和原 ID 回执，旧 PTY 返回 instance changed；后台只对账，不能再次提交未知命令。

远端工作区清理使用独立精确入口，旧 R6 本地扫描器不用于 Node 哈希目录。先加载同一执行域 env，report 不删除，mark 需核实人，apply 需候选 token：

```bash
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/sandbox_workspace_cleanup.py \
  --tenant TENANT --project PROJECT --thread THREAD --graph dearflow_agent
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/sandbox_workspace_cleanup.py \
  --tenant TENANT --project PROJECT --thread THREAD --graph dearflow_agent \
  --action mark --verified-by OPERATOR
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/sandbox_workspace_cleanup.py \
  --tenant TENANT --project PROJECT --thread THREAD --graph dearflow_agent \
  --action apply --candidate-token REPORT_TOKEN
```

默认宽限 7 天，retained / pending / interrupted / unknown / 回执和 delivery 未决均阻止清理。apply 二次检查 Runtime 事实、Node 资源与候选 token，并写 deleting / purged；为防删除与新工作竞态，人工 mark / apply 会在事务中短暂阻止相关事实表写入，应在维护窗口操作。实际用户数据删除需批准具体候选；测试只销毁本轮专属 fixture。

## Drain、证书 / IP 轮换与回退

先设置 `RUNTIME_BACKGROUND_TASKS_ENABLED=0` 并暂停新 Run 入口，保留原 host / Node 连接；终端 close、已知命令 Stop，后台保存回执。unknown / unconfirmed / 未 ack 阻止 drain 完成，不能靠切换 target 释放原位置。Node 停服务会关闭准入并有界清理 PTY，持久记录和数据保留。

叶证书 / token 轮换仍使用原离线 CA，新目录输出不会带出 CA 私钥：

```bash
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/sandbox_node_certificates.py \
  --output /absolute/private/node-trust-v2 --ca-source /absolute/private/node-trust-v1 \
  --server-name node.example.com --execution-host deployment-id --allowed-ip 203.0.113.20/32
```

本期单 caller token，轮换需 drain 后同步替换 Node auth / server leaf 与 Runtime client leaf / token，重启 Node 与 API / Worker，再 preflight。保持 host、node_id、CA、state 和 workspaces 不变；旧 token 应被拒绝。CA 轮换使用新信任域并在维护窗口同步更换全部信任材料，不能暂时关闭证书检查。

出口 IP 改变先核实真实新源，仅在云安全组、宿主防火墙与 callers.json 加精确 CIDR；确认新路径 mTLS 通过后撤旧 CIDR。公网失败先分查路由 / 云安全组 / 宿主监听与包到达；TCP connect 返回成功不证明请求真正抵达 Node，更不能用 SSH 隧道的成功代替公网业务验收。

应用回退必须保留完整迁移链和当前 `runtime_app_alembic_version` head；0006–0008 拒绝破坏性 downgrade。不 stamp，不删绑定 / 操作 / 资源 / 回执，不切 local 后为旧远端 Thread 造空目录。旧应用只接本地原有独立 Thread，远端旧 Thread 在新版本维护入口只读 / 对账。显式跨节点迁移和自动 failover 后置。

## 备份与故障边界

单机持久盘能承受进程 / 主机重启，不能承诺磁盘损坏、误删或整机丢失后的恢复。维护窗口 drain 后停止 Node，用 SQLite backup API 备份 `state/node.sqlite3`，保留整个 workspaces 与技能快照；同时备份 Runtime 应用位置 / 资源 / 后台表与 GraphHarbor Thread / checkpoint。禁止仅复制正在写的 SQLite 主文件而漏 WAL。备份保密并存到另一个故障域，恢复保持 execution host / node ID 和文件权限。

还原到原单节点后先启动对账，旧 PTY清理、后台按原 ID 读取事实；镜像 digest / UID / 路径改变导致 policy mismatch 时保持不准入，由维护人员核实，不自动重跑。跨服务器恢复需另行评审；本专项没有部署自动备份服务。

## 整机重启验收门禁

整机重启需要明确的节点重启授权与维护窗口，不能把部署许可、异步提问工具 accepted=true 或等待超时视为批准；sshmy2 同机还运行 site_total.service，窗口须包含其短暂中断。当前用户保留 I10，稍后提供窗口，禁止现在重启。

窗口获准后，沿用原 execution host/node/Thread，先核验无未决后台和活跃容器并保存文件/hash/checkpoint/原操作 ID/boot ID；重启后检查 Docker/Node/同机业务 active，再按原 ID 只读恢复回执、核对文件及历史、验证新容器与旧 PTY。不重发 unknown 命令、不删除 retained 工作区。先前未获授权重启的技术恢复记录不替代正式验收。
