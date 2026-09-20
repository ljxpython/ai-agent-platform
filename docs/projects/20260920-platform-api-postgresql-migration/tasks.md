# Platform API PostgreSQL 迁移专项 - 任务拆分

用户已于 2026-09-20 批准方案并授权立即真实切换。切换与本轮验收已完成（done）。生产发布另行安排，私有备份和隔离测试卷保留。

## P0 规划与评审

- [x] 阅读 ADR、数据库手册、配置/迁移/启动和清理入口，记录事实差异。
- [x] 建立专项方案、任务和验收计划，更新文档导航与功能总览。
- [x] 用户批准方案，完整保留数据、使用本地 PG，评审记录已更新。
- [x] 用户确认立即停写切换；备份保留期未另定，按规范完整保留、不自动删除。
- [x] 只读盘点现有 SQLite：20 表和字段集匹配，完整性检查通过，无外键孤儿；行数已记录。
- [x] 正式停写核验并生成 WAL 一致快照；20 表逐表核验，7 组密钥可解密，Runtime 无在途 runs。

## P1 数据库准备与迁移工具（初估 1.5–2 人天）

- [x] 复用并修正建库脚本的 SQL 转义，新增 `--platform-only`；隔离容器中创建专用非超级用户角色和库，重复运行通过。
- [x] 核验 `apps/platform-api/migrations/env.py` 配置目标及 `20260910_0001_platform_baseline.py` 的真实 PG 升级、重复升级与模型一致性；不修改已用基线。
- [x] 新增 `apps/platform-api/scripts/migrate_sqlite_to_postgres.py`：源/目标身份检查、源备份、空目标保护、按类型/外键复制、失败回滚和数据摘要核验；不复制 `alembic_version`。
- [x] 新增 `apps/platform-api/tests/test_sqlite_to_postgres_migration.py`：隔离库导入、类型边界、非空目标拒绝、坏数据失败和源库未变验证。沿用 unittest，不引入测试框架。
- [x] 工具拒绝已 bootstrap 的非空目标；容器启动/重启后管理员登录和项目数据保留。
- [x] 真实 7 组模型密钥可解密；全部 refresh token 摘要迁移一致，登录/新会话通过。源服务账号及 Runtime runs 为空，权限用契约测试、新建真实会话补证，不虚构既有记录。

## P2 启动与运维收敛（初估 1–1.5 人天）

- [x] 更新 `apps/platform-api/.env.example`、`apps/platform-api/deploy/docker-compose.example.yml`、`docs/local-deployment-contract.yaml` 为正式 PG 配置。
- [x] 修改 `scripts/local-stack.sh` 的 `validate_stack()`、`migrate()`、`start()`：实际控制面连接/版本校验，Alembic 先于 API，失败阻断；复用现有环境优先级。
- [x] 三份 Compose 配置校验通过；关闭自动建表、先 Alembic 后 API。独立 PG/API 容器的首次启动与已有数据重启通过。
- [x] 完整 Compose 六个容器（四服务 + PG/Redis）健康；当前 Runtime 源码的网关线程、Web 页面、结果域 HTTP 写读及已有卷重启持久化通过，镜像边界见实施记录。
- [x] 修改 `scripts/cleanup_env.sh` 的数据库及备份清理入口：脱敏预览、单独选择和确认、目标保护、表白名单、失败返回；不自动删迁移备份或按名称猜测可删库。
- [x] 新增启动迁移失败阻断、清理预览保留源库/备份检查；配置拒绝 SQLite/维护库及自动建表，真实 PG 清理保留其他 18 表。
- [x] 错误凭据、库不存在、不可达、权限、未迁移库均阻断；反向外键 RESTRICT 整体失败；停写声明是操作者保证，工具不声称能阻止远端写入方重启。
- [x] 更新 `apps/platform-api/README.md`、`apps/platform-api/docs/handbook/database.md`、`apps/platform-api/docs/handbook/runbook.md`、`docs/quickstart/local-dev.md`、`docs/quickstart/env-matrix.md` 与必要的部署说明。

## P3 验证、切换与收尾（初估 1.5–2.5 人天）

- [x] 完成单元、真实 PG/HTTP、浏览器聊天/管理、安全故障、2 worker/10 客户端/各 5 分钟性能及恢复；首轮失败和修复复测均保留证据。
- [x] 完成本地停写、备份、导入、20 表核验、真实切换及受控业务写入；全栈容器独立列项验收。
- [x] 隔离 SQLite 快照可登录读项目；当前 PG 双库停写备份恢复，全部表摘要及新会话 HTTP 读回通过；真实服务保持 PG，不回指旧 SQLite。
- [x] 使用 `implement-feature` 记录实施，使用 `verify-change` 如实判定 done / partial / blocked / deferred；同步专项状态及 `docs/FEATURES.md`。
- [x] ADR 已接受并关联正式规范；备份完整保留，生产发布不属于本轮本地切换。

## 进度追踪

- [x] 规划文档已建立。
- [x] P0 人工评审及数据盘点完成。
- [x] P1 迁移验证完成。
- [x] P2 配置与运维完成。
- [x] P3 本轮验收及本地切换完成。

## 补充交付（用户批准时提出）

- [x] 修复全仓文档检查发现的 10 处本机绝对路径。
- [x] 新增 `docs/guides/database-operations.md`，覆盖首次服务器部署与建库脚本、未来迁移规范及本地 PG 开发；同步现行文档入口。

## 本地运维补充

- [x] 项目清理仅保留 test；增加独立清理入口、最新备份、真实 PG/HTTP 验证。
- [x] 修复测试项目退出未回收及跟踪报告误删风险；核实全局 Graph / 项目 Agent 并修正文案。

- [x] 用户授权历史清理；新增独立入口，实际清理失效令牌、历史会话/审计和 6 个迁移测试库；双库备份恢复核验通过。
