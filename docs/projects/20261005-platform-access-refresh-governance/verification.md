# 平台权限状态与刷新治理 - 验证记录

## 验证计划与范围
- 前端全量单测；相关 API/Runtime 授权契约与生命周期测试；类型、Lint、构建。
- 浏览器使用隔离 Platform SQLite 数据库，测试 API 12142、Web 13000、独立 Runtime API 18123，Runtime 回查测试 API。
- 真实链路覆盖项目撤权、双标签页、Thread 创建/读取/state/共享撤销/子资源隔离/服务账号撤权/删除。
- 故障注入覆盖快照 503、首次读取失败恢复、HTTP/聊天 Fetch 续期 503、无关拒绝与突发刷新。
- 不调用模型、不改动生产配置。模型生成质量和长时间模型流不是本次授权逻辑修改范围；现有条件 SDK 模型测试未开启，不记为通过。useChatSession 27 项及 SDK 恢复 11 项随前端全量执行。
- 回退：无 schema/公开契约改变；验证独立鉴权无 lifespan fallback 与新前端兼容现有 API 契约；未执行生产版本回退操作。

## Phase 验证记录
### Task 1.1 — 2026-10-05
✅ workspace 9、guards 6、route-access 6、Layout 4；页面草稿在临时失败时保留，真实角色降级移除对应页面。
### Task 1.2 — 2026-10-05
✅ HTTP 4、LangGraph 13；浏览器两个实际客户端续期 503 保留登录通过。
### Task 2.1 — 2026-10-05
✅ access-events 1、SessionConnection 7；精确事件、不重复 SSE 广播、Thread 权威复核。
### Task 2.2 — 2026-10-05
✅ 同项目并发请求合并；浏览器 60 秒刷新 + focus/visibility + 无关拒绝在短窗口内只产生 1 个 /access；后台会话周期撤权单测通过。
### Task 3.1 — 2026-10-05
✅ Runtime tests/runtime 114 passed；池模块分离后 test_platform_auth.py + app_lifespan 定向 41 passed（含动态加载共用 transport）；API 13 passed + 299 subtests passed。
真实 Runtime 创建/读取/state/共享撤销/删除链路通过。无效 ACL 响应 503，明确空 allowed 列表 403。
### Task 3.2 — 2026-10-05
✅ 见 Final。初期发现问题和修复见下方；全部本期实现任务已有证据。

## 执行中发现的问题
- 原 workspace 测试以普通 Error 模拟撤权，期望清空权限；改为明确 HTTP 403，并覆盖网络/空权限/404 路由错误。
- 浏览器时钟须在导航前安装才能接管已有定时器；已修正。
- 用户名同时存在顶栏和成员区，撤权断言改为成员页面内容。
- 首次失败没有旧快照时不显示“已保留页面”横幅，避免重复重试入口。
- GraphHarbor 按文件路径加载鉴权模块，池放在 platform.py 会产生两份实例；移至普通导入的 acl_client.py，并补动态加载回归。
- pytest 不在全局 PATH；Runtime 用 uv run，API 用 uv run python -m pytest 保证 tests 包可导入。

## Final 验证记录
### 2026-10-05 — 执行者：Codex；方案批准：用户本会话
- Platform Web：pnpm exec vitest run → 105 suites passed / 1 skipped，473 tests passed / 1 skipped。最后横幅条件改动后 Layout 4 项再验通过。
- 类型和构建：pnpm run build → vue-tsc、Vite build 通过。
- Web Lint：0 errors、26 条既有 warnings；本次改动没有新增 lint error。
- Runtime：uv run python -m pytest tests/runtime -q → 114 passed；最后池模块分离后定向 41 passed（含 lifespan 2 项），Ruff check/format 通过。
- API：uv run python -m pytest tests/test_runtime_gateway_http_matrix.py tests/test_security_boundaries.py tests/test_iam_project_governance.py -q → 13 passed、299 subtests passed。
- 故障浏览器：RUN_LOCAL_GOVERNANCE_E2E=1 pnpm exec playwright test e2e/access-refresh-resilience.spec.ts --reporter=line --workers=1 → 4 passed。
- 真实安全浏览器：platform-access-governance.spec.ts 中 private sharing and no-project / private child resources / service account needs / removing membership → 4 passed。独立 Runtime 从当前源码启动，非 mock upstream。
- 性能边界：焦点/可见性/无关 403 突发只产生 1 次项目快照请求；池复用 2 次 ACL 请求只创建 1 个客户端，生命周期退出关闭；未声明并发吞吐 SLO。
- 证据图：/tmp/access-refresh-retained.png、/tmp/access-refresh-revoked.png；用例已提交到工作区，可复跑，不含用户凭据。

### 结论与交付边界
done：本次修复实现与本地必要验证完成；真实拒绝未放宽，网络不可用不再伪装成撤权。
未执行生产部署或灰度，不代表投诉环境已经更新；Runtime 部分需正常发布重启。没有数据库迁移，没有自动 git commit/push。
原 SDK 模型测试因未开启 PLATFORM_CHAIN_TEST 跳过，不计入通过；本次以真实授权链路和现有 SDK 单测验证改动边界。
