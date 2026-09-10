# 验证记录

日期：2026-09-10，执行：Codex。用户已批准方案。本工程状态 **done**，仅指平台文档重建与配置示例修订。

## 已验证

| 项目 | 结果 |
| --- | --- |
| 当前文档结构 | 10篇活文档；28文件归档，原位置消失、新位置存在 |
| 归档图 | 12文件与HEAD原始内容逐字节一致 |
| 链接与锚点 | 平台docs共123个本地链接检查通过；当前入口无旧delivery/decisions/diagrams引用 |
| 配置 | 示例24项均属于Settings的40字段；配置正文后缀与源码一致 |
| 数据库 | 文档20表、Base.metadata与Alembic create_table集合一致 |
| 网关 | 文档20条方法/路径与真实router注册集合一致 |
| 权限 | 29个登记权限，无Operations权限；角色矩阵按policy映射核对 |
| 相关回归 | 网关30项通过（3.842秒），事务3项通过（0.695秒），无跳过 |
| 编译 | uv run --frozen python -m compileall -q src tests通过 |
| CLI | Showcase与backend_closeout两脚本--help通过，参数与运维说明一致 |
| 应用生命周期 | 临时工作目录创建真实app，TestClient启动/关闭，live/ready响应符合文档 |
| 初始化命令 | 新临时SQLite执行Alembic upgrade head/current通过，版本20260910_0001；不访问现有开发库 |
| 文档检查 | 本工程与平台活文档的本机路径/旧宿主名规则通过，git diff --check通过 |

[脱敏检查结果](evidence/20260910-docs-check.json)。既有真实PG备份/恢复、Docker Showcase和负载证据在[后端验收](../20260910-platform-api-refactor/implementation/13-backend-acceptance-closeout.md)，本次不重复执行外部模型或工具，也不把SQLite烟测算作新PG验收。

## 可重复命令

仓库根目录：

```bash
python3 scripts/check_docs.py
git diff --check
apps/platform-api/.venv/bin/python -m unittest discover -s apps/platform-api/tests -p 'test_runtime_gateway*.py'
apps/platform-api/.venv/bin/python -m unittest discover -s apps/platform-api/tests -p 'test_transaction_boundaries.py'
apps/platform-api/.venv/bin/python scripts/platform_backend_closeout.py --help
apps/runtime-service/.venv/bin/python scripts/platform_showcase_acceptance.py --help
```

配置/路由/metadata使用一次性只读Python探针核对，未新增文档生成框架；源码锚点见plan与活文档。迁移只在临时隔离库验证，不对生产环境运行示例。

## 全仓检查的既有问题

初次执行 `python3 scripts/check_docs.py` 全仓失败：其他工程/测试产物存在24条个人绝对路径。逐行对照HEAD确认均为本次之前已有；不扩展为其他服务文档重构。

清单见[既有错误](evidence/20260910-global-docs-existing-errors.txt)。涉及根Graph发现ADR、旧Showcase报告、dispatch工程与test-results文件。此项不能标“全仓通过”，但本工程范围检查已通过。

## 四态结论

- **done**：批准的10篇活文档、归档/引用修复、配置示例与必要验证。
- **deferred（用户决定）**：前端/浏览器、整套容器部署和完整Server等价性，仍由原工程维护。
- 既有24条文档检查错误后续按用户明确授权全部修复；无新增产品功能、数据库变更或包发布。

## 后续：24处个人路径修复

用户明确要求修复后，修改13个文件中的24处引用：仓库内文件使用相对链接；命令标明从仓库根目录执行；外部open-swe引用使用checkout占位符；旧安装包或已删除源码位置保留历史文字引用，不伪装为当前源码链接。Playwright错误上下文中的个人截图目录替换为test-results相对目录，不改变历史测试结论。

全仓 `python3 scripts/check_docs.py` 和 `git diff --check` 均通过。此前错误清单作为修复前证据保留，不再代表当前未完成项。本轮未提交或推送。
