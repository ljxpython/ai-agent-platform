# 运维与验收

本手册针对本地开发和已验收后端。整套容器部署、浏览器及完整Server等价性仍后置；不把本机负载证据当作生产容量认证。

## 启动与健康

安装配置见[服务README](../../README.md)，PG初始化见[数据库](database.md)。平台只启动API；GraphHarbor API/Worker、Runtime图、Runtime数据库与Redis由Runtime侧管理。

在任意目录检查默认本地Platform端口：

```bash
curl --fail http://127.0.0.1:2142/_system/probes/live
curl --fail http://127.0.0.1:2142/_system/probes/ready
```

live返回alive；ready必须检查JSON status=ready与database_ready，不只看HTTP状态码。未启用数据库时ready也可能为ready，所以实际业务要确认配置开启。`/_system/health`反映平台数据库，不检查Runtime Worker或上游连通性。

`/_system/metrics`需要platform.config.read，返回当前进程请求快照；进程重启会清空，不是Prometheus持久化指标。关联排查使用x-request-id/x-trace-id和日志。

## 常见问题

| 表现 | 检查顺序 |
| --- | --- |
| 平台未就绪/数据库不可用 | URL、PG服务与权限、迁移版本、连接数；不查已退役平台Worker |
| 登录/刷新失败 | 用户启用、密码变更要求、JWT issuer/audience/kid、令牌撤销与轮换验证键 |
| 服务账号403 | 账号/令牌有效期与启用、项目grant、当前项目scope |
| Runtime拒绝/不可用 | 上游地址、Runtime ready、委托secret/issuer/audience、项目与Agent权限 |
| 模型连接不可用 | master key、credential_configured、模型UUID/启用与策略、Runtime兑换URL |
| Run超时或断流 | 先读原Run/state，核实结果；同动作保留key，不重发新动作 |
| 没有审计 | 是否开启平台DB、请求是否已结束、audit_write_failed日志；SSE关闭后才收尾 |

审计是独立短事务，写失败记录日志，不保证与业务原子提交；query会进入审计，勿把秘密放URL。

## 本地测试与真实联调

在 `apps/platform-api`：

```bash
uv run --frozen python -m unittest discover -s tests -p 'test_runtime_gateway*.py'
uv run --frozen python -m unittest discover -s tests -p 'test_transaction_boundaries.py'
```

最小HTTP集成位于[tests/integration](../../tests/integration/)。设置PLATFORM_RUNTIME_INTEGRATION=1、PLATFORM_API_BASE_URL、PLATFORM_API_ACCESS_TOKEN、PLATFORM_API_PROJECT_ID、PLATFORM_API_EXPECTED_UPSTREAM_URL后执行：

```bash
uv run --frozen python -m unittest discover -s tests/integration -p 'test_*.py'
```

这些值必须来自有权限的专用环境；缺条件skip不计通过。该测试创建测试Thread，不证明模型与Docker执行。

完整Showcase复用[脚本](../../../../scripts/platform_showcase_acceptance.py)，依赖已迁移的专用Runtime PG/Redis、配置好的真实模型与Docker沙箱。脚本使用Runtime虚拟环境，参数通过 `--help` 查看；会创建项目/模型/Agent并执行工具，不能对生产环境试跑。不要以宿主机命令代替Docker沙箱。

## 备份与恢复

1. 停止接入写请求并停止Runtime Worker，确认在途请求结束、两库处于稳定窗口。
2. 使用与PG服务端匹配的pg_dump客户端，以custom格式分别备份Platform/Runtime；数据库凭据走环境或安全凭据文件。备份包含敏感数据，限制访问。
3. 单独保存master key、签发/验证秘密及工具工作区。PG dump不包含Redis队列或外部副作用。
4. 恢复到两个新库，使用pg_restore --exit-on-error核对成功；逐表行数/摘要、迁移版本及父子Run关联一致后，启动API读回历史，暂不启动Worker。
5. 核实队列/lease与待处理执行再开放写入，不能盲重放旧输入或旧Redis队列。失败保留源库，停止切换；不能用旧平台版本读取新基线冒充回退。

现有[验收脚本](../../../../scripts/platform_backend_closeout.py)可对一次完成的Showcase输出复跑隔离恢复与混合负载。在仓库根目录：

```bash
apps/platform-api/.venv/bin/python scripts/platform_backend_closeout.py --help
```

实际执行需 --source 指向包含私有process-env.json/evidence.json的验收目录，--output指定不存在的新目录，--pg-bin指定匹配版本客户端目录。脚本只支持本机PG、创建新库、不启动Worker；会保留私有dump和新数据库，只停止自有进程。不要提交私有输出目录。

[真实备份与负载记录](../../../../docs/projects/20260910-platform-api-refactor/implementation/13-backend-acceptance-closeout.md)证明静止窗口数据恢复和历史读取，不保证不停写入时跨库一致快照或工具exactly-once。

## 发布检查

核对目标版本、配置、迁移和可用备份，完成相应功能测试与最短真实链路，再发布。目录变更后从干净构建目录构建wheel，检查不混入旧build缓存；源码导入通过不能替代产物验证。记录发布版本、执行命令、证据与回退边界。

新增schema以后是否能回退由对应迁移决定，不直接降库或恢复旧快照覆盖新写入。容器部署按后续专项验收，不在此处宣称已完成。
