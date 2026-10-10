# 本地栈隔离实施

2026-10-10，对应 T01-T03。方案已经用户批准；完成度以 tasks.md 为准。

## 文件与职责

- `scripts/local_stack_worktree.py`：`git_paths()` 识别 common/private Git 目录，`reserve()` 加文件锁随机分配，`record()` 检查登记一致性，`initialize()` 生成私有配置与专属数据库，`configs()` 验证 PG/Redis/回调/Workspace 归属，`database_resources()` 检查资源标记后创建或销毁。
- `scripts/local-stack.sh`：操作锁包装、配置安全注入、独立 Redis、每目录 PID/日志、只读端口预检、`deps` 共享缓存独立安装、源码解析校验、失败时只清理新启动进程。
- `scripts/local_stack_processes.py`：复用已有真实目录/命令/监听端口归属检查，增加 Redis 目录和进程支持，拒绝目录越界。
- `apps/platform-web/playwright.config.ts` 和 `e2e/support/platform.ts`：Web/API 地址、凭据文件和模型 fixture 配置指向所属环境；缺登记拒绝回退。
- `docs/standards/worktree-development.md`：完整规则与命令入口；AGENTS/README/规范索引/部署契约和指南挂载统一链接。

## 关键行为变化

- 原 `STATE_DIR=${TMPDIR}/aitestlab-local-stack` 改为每目录 `.local-stack/`，主工作区仍使用原数据和默认端口。
- 原端口预检可能停止“属于仓库的旧进程”；现在只报告冲突，显式 stop 才停止所属进程。
- Python 项目安装目录独立，uv/pnpm 包缓存复用；安装固定项目约定 Python 3.13，启动/doctor 不隐式同步依赖。
- Worktree Worker 并发 1，Redis 独立并持久保存；stop 不释放端口和数据，destroy 要求精确环境 ID。

## 验证与边界

定向单测覆盖并发登记、归属和失败回收。真实 PG/Redis 测试使用本机已有程序创建专属临时资源并清理。`scripts/verify_worktree_local_stack.py` 在临时目录复制代码并执行正式入口；Git 位置查询使用 fixture，以避免创建或修改用户 Git Worktree，其他服务、安装、数据库、Redis 和 Web 代理均为真实进程。

追加验收在临时目录注册最小 LangGraph 探针，不修改业务 graph、不调用模型：三套 Worker 并发写入/读取同名文件，返回实际 Worker 环境 ID，并通过状态与实际 Workspace 文件核对归属。原 `workspace_demo` 需要专项资源绑定，直接注册不能作为通用隔离探针。临时 Playwright 用独立上下文进行真实登录，核对登记 Web/API 地址和请求 origin。依赖及状态文件还检查父目录/软链接越界；服务子进程清除管理员 DSN 和操作锁标记。

初轮三栈真实 catalog 链路通过后，验收程序因遗漏复制已有 E2E 文档 fixture 失败；修正验收目录复制后重跑。日志还发现未指定 Python 版本时 API 会选本机 3.14，已固定 3.13 并重新安装验证。前端测试帮助函数原来直连 2142，已同步改为登记地址。

不改生产部署、业务 API 或依赖版本；模型/图片/MCP 等外部额度仍共享，不包含生产发布或真实模型效果验收。
