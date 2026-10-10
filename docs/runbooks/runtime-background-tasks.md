# Runtime 后台任务运行手册

适用：单执行主机、API/Worker 连接同一 Docker daemon，Workspace 使用相同宿主绝对路径。新提交默认关闭；post45接受回执已发布并接入正式依赖锁，发布后 notify/Stop/撤权联合复验通过，[B01](../projects/20261009-agent-generic-production-capabilities/engine-handoff.md) 已解除。正式启用还须该专项T08/T10/F12、应用镜像验证和部署授权。这里只操作当前服务明确拥有的资源，不使用全局 prune。

## 安装与启动

1. 构建 `apps/runtime-service/deploy/Dockerfile`；依赖使用服务自己的 `apps/runtime-service/uv.lock` 冷安装，GraphHarbor 双包均为 `0.13.0.post45`。Workspace 镜像提前准备，不在工具执行时 pull。此版本部署断言已更新，完整Linux应用镜像重建仍由部署验收执行。
2. 原生迁移head013后执行 `python -m runtime_service.db upgrade`；Runtime应用 head 为 `0003_background_tasks`，Platform迁移head为`20261010_0007`。平台先保存最终body bytes/key/digest/非secret授权快照再发送；任务表和Stop加法字段由Runtime维护，不读写引擎runs/lease表处理业务对账。所有接收受管完成POST的API必须支持新acceptance路由及配套Auth。
3. 配置 `RUNTIME_EXECUTION_HOST_ID` 为 1-64 字符的稳定主机标识，只含字母、数字、点、下划线、连字符。变更 ID 会失去旧资源的控制域，不能用于规避额度或 unknown。
4. 配置 `RUNTIME_BACKGROUND_WORKSPACE_PATH` 为存在的宿主绝对目录。API/Worker 在同一绝对路径挂载该目录，私有日志 volume 共享；命令容器只挂当前 Workspace 和只读技能，不能挂 Docker socket。
5. Compose 使用基础文件和 `apps/runtime-service/deploy/docker-compose.runtime-background.yml`。示例只适用于已审查的受管执行主机；API/Worker 的管理 socket 有主机控制权限，不能开放给租户或任意容器。

```bash
docker compose -f "apps/runtime-service/deploy/docker-compose.runtime-service.yml" \
  -f "apps/runtime-service/deploy/docker-compose.runtime-background.yml" config --quiet
```

基础部署要求 `deploy/.env.runtime-service` 已配置。overlay 也默认关闭新提交；门禁通过后显式配置 `RUNTIME_BACKGROUND_TASKS_ENABLED=1`。停用时显式设为 0，并重建 API/Worker 容器，保留管理连接和共享挂载供 drain。开启前分别验证 API/Worker 的 Docker 连接、绝对挂载和技能 snapshot，不以 capability 或 `/ready` 代替全链路验收。

非 Docker、关闭开关或无有效 host 时，模型看不到后台新启动工具；保留配置的任务存储后，已有任务的查询/日志/授权取消入口仍可用。无任务存储配置时隐藏查询和任务 Tab。旧调用先核对原回执，只有确认无记录的环境限制才提示短任务使用普通 execute（默认 30 秒、最大 60 秒）。unknown 不重跑，数据库与 Docker 故障不泛化成“未启动”；Docker 不可用不自动落宿主 shell。切换执行 backend 前先按下文 drain，不将 local 节点当作原 Docker 执行域的对账替代。

## 受管资源与容量

- 并发上限：Thread 4、project 8、host 16。未确认资源继续占位；JWT 过期不取消已经接受的命令。
- 命令独立期限：默认 900 秒、最大 3600 秒。runner 使用单调时钟，源 Run error/timeout/确认取消会抑制通知并清理；正常 success 可延续；HITL 不自动批准。
- runner head-tail 正文最多 1 MiB；Docker local log 2 MiB × 2；HTTP 64 KiB，工具 16 KiB。私有存储按任务预留 2 MiB，host 最多 1024 份预留，总额 2 GiB；命令原文、平台 JWT、模型凭据不存入任务表。
- 日志目录为 `<RUNTIME_BACKGROUND_LOG_ROOT>/<host_id>/<task_uuid>/<fence>.log`。读写禁止软链；原子替换，旧 fence 不能发布事实。常规快照不扫描其它任务，启动准入会盘点目录容量。
- 终态确认日志按 7 天或容量提前淘汰；公开 `available=false`。幂等/Stop 最小回执不随日志删除；活跃/unknown/未确认资源不 TTL 盲删。容量满仍可启动 API 对账与清理。
- loop 每秒领取最多 20 个到期项，通常每任务 5 秒；租约 45 秒，每 10 秒续租。远端等待不占 PG 事务，不调用模型。

## 查询与故障处理

通过 Platform `/api/langgraph/threads/{thread_id}/background-tasks` 查询，携带当前项目和用户权限。元数据、日志、取消使用独立 delegation operation。Task 的 success 不表示完成通知 Run success，accepted 仅表示新 Run 已受理。

Docker 控制失败时查看安全日志 `Background reconciliation unavailable task_id=... kind=...`、`Background source unavailable task_id=...`；对照任务 reason/cleanup/delivery。日志不含命令或管理凭据。`unknown` 不能直接释放额度、清空行或重新跑命令。

确认 host 和私有记录的 container name/ID/labels 三者一致后检查受管容器：

```bash
docker ps -a --filter "label=runtime.background.host=<已核验 host_id>"
docker inspect --type=container "<任务私有记录中的 container_name>"
```

不要把完整 inspect/env/argv 放入聊天或审计。名称不匹配、daemon 不可达或资源被外部删除时保留 unknown/unconfirmed，恢复原 daemon/挂载后由同一 reconciler 核验。外部已经删除的资源可能无法重建执行结果；只能由负责人按真实证据处置，禁止伪造 succeeded 或重放副作用。

完成交付丢响应时保留event/key及已保存最终传输事实：`reconcile_only`通过内部短期固定`run-acceptance-read`委托GET原回执，校验原event/source/scope与Thread/key/digest后绑定同一run_id。撤权不阻止固定回执对账；当前公开ACL和执行前guard继续拒绝新执行。Stop已suppressed时回填也不恢复通知，只有精确取消/持久清理证据才confirmed。GET、unknown或普通4xx均不触发第二次POST、换event/key或重新授权模型。

旧记录没有保存body或旧API404/405时，仅在当前读取ACL内最多10页×100项进行event/task/source全部匹配的正向找回；无匹配仍unknown。新ledger长期pending/running保留详情，首次观察终态/删除后默认7天；到期unknown，原key仍永久封住，需人工核实，不自动再执行。部署保留期必须覆盖最长通知/Stop对账窗口。

## 停用与回退

1. 将新提交开关设为 0，API/Worker 保留相同 host、日志和 daemon 配置，重启应用后继续对账。该开关禁止新任务与新通知准入，不能单独证明资源回收。
2. 对已接受活跃任务调用公开 cancel，或对指定 Thread 发原 key 的会话 Stop；持续 GET 核验 `cleanup_state=confirmed` 和固定后台摘要。完成通知若已接受，Stop 还需确认该固定 Run 停止。
3. 将unknown、inflight、迟到Run和daemon不可达项逐项列出；任何未确认资源都阻止“drain已完成”。先GET原接受回执、绑定原Run并精确停止；无回执/到期/旧记录且无当前ACL正向证据时，由负责人受控处置。
4. 确认所有当前资源已收敛后，停止新代码的 API/Worker；使用新代码的 Alembic 配置将应用版本降到 `0002_run_control`，再回退匹配的应用源码/依赖。`0003_background_tasks` 的 downgrade 保留任务表、索引与 Stop 加法字段；旧应用忽略它们。只换旧源码会因不认识 `0003_background_tasks` 而启动失败，不能跳过版本回退；不能删回执、Workspace 或 checkpoint。
5. 不需要的本轮测试 API/Worker/PG/Redis、带专项 label 的容器及时停止。只按明确身份清理本轮资源，保留现役与其他 worktree 的服务。

引擎013与平台0007均拒绝删除接受事实的downgrade；Runtime应用0003保留表的downgrade是另一套迁移，不能混用。引擎/平台代码回退必须保留ledger、墓碑及最终传输字段；旧unknown不切换namespace重投。备份恢复到接受前快照会失去防重事实，须冻结新受管提交并人工对账。

验证与限制见 [专项记录](../projects/20261009-agent-generic-production-capabilities/verification.md)。正式发布/生产迁移/删除生产数据不由此手册自动授权。
