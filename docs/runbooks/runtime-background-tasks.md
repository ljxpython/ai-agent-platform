# Runtime 后台任务运行手册

适用：单执行主机、API/Worker 连接同一 Docker daemon，Workspace 使用相同宿主绝对路径。新提交默认关闭；本专项的所有 ACK 丢失窗口尚未闭环，正式启用受 [B01 门禁](../projects/20261009-agent-generic-production-capabilities/engine-handoff.md)约束。这里只操作当前服务明确拥有的资源，不使用全局 prune。

## 安装与启动

1. 构建 `apps/runtime-service/deploy/Dockerfile`；依赖使用 `uv.lock` 冷安装，GraphHarbor 双包均为 `0.13.0.post43`。Workspace 镜像提前准备，不在工具执行时 pull。
2. 原生迁移后执行 `python -m runtime_service.db upgrade`；应用 head 为 `0003_background_tasks`。任务表和 Stop 加法字段由 Runtime 维护，不读写引擎 runs/lease 表处理业务对账。
3. 配置 `RUNTIME_EXECUTION_HOST_ID` 为 1-64 字符的稳定主机标识，只含字母、数字、点、下划线、连字符。变更 ID 会失去旧资源的控制域，不能用于规避额度或 unknown。
4. 配置 `RUNTIME_BACKGROUND_WORKSPACE_PATH` 为存在的宿主绝对目录。API/Worker 在同一绝对路径挂载该目录，私有日志 volume 共享；命令容器只挂当前 Workspace 和只读技能，不能挂 Docker socket。
5. Compose 使用基础文件和 `apps/runtime-service/deploy/docker-compose.runtime-background.yml`。示例只适用于已审查的受管执行主机；API/Worker 的管理 socket 有主机控制权限，不能开放给租户或任意容器。

```bash
docker compose -f "apps/runtime-service/deploy/docker-compose.runtime-service.yml" \
  -f "apps/runtime-service/deploy/docker-compose.runtime-background.yml" config --quiet
```

基础部署要求 `deploy/.env.runtime-service` 已配置。overlay 也默认关闭新提交；门禁通过后显式配置 `RUNTIME_BACKGROUND_TASKS_ENABLED=1`。停用时显式设为 0，并重建 API/Worker 容器，保留管理连接和共享挂载供 drain。开启前分别验证 API/Worker 的 Docker 连接、绝对挂载和技能 snapshot，不以 capability 或 `/ready` 代替全链路验收。

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

完成交付丢响应时保留 event/key：已有平台 run_id 或 Worker 开始前 guard 回填后可恢复 accepted；两者都不存在时保持 unknown。post43 缺只读 key 回查，不能用第二次 POST、遍历引擎数据库或新 Thread 代替。Stop 的 inflight 未确认也属于这个门禁。

## 停用与回退

1. 将新提交开关设为 0，API/Worker 保留相同 host、日志和 daemon 配置，重启应用后继续对账。该开关禁止新任务与新通知准入，不能单独证明资源回收。
2. 对已接受活跃任务调用公开 cancel，或对指定 Thread 发原 key 的会话 Stop；持续 GET 核验 `cleanup_state=confirmed` 和固定后台摘要。完成通知若已接受，Stop 还需确认该固定 Run 停止。
3. 将 unknown、inflight、迟到 Run 和 daemon 不可达项逐项列出；任何未确认资源都阻止“drain 已完成”。B01 无只读回查时需先补引擎能力或由负责人受控处置。
4. 确认所有当前资源已收敛后，停止新代码的 API/Worker；使用新代码的 Alembic 配置将应用版本降到 `0002_run_control`，再回退匹配的应用源码/依赖。`0003_background_tasks` 的 downgrade 保留任务表、索引与 Stop 加法字段；旧应用忽略它们。只换旧源码会因不认识 `0003_background_tasks` 而启动失败，不能跳过版本回退；不能删回执、Workspace 或 checkpoint。
5. 不需要的本轮测试 API/Worker/PG/Redis、带专项 label 的容器及时停止。只按明确身份清理本轮资源，保留现役与其他 worktree 的服务。

验证与限制见 [专项记录](../projects/20261009-agent-generic-production-capabilities/verification.md)。正式发布/生产迁移/删除生产数据不由此手册自动授权。
