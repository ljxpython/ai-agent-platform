# 验证入口及首轮历史记录

最新验收计划与分层完成标准见 [05 验证与交付](05-verification-and-delivery.md)。本页分开保留本次 Phase、未来 Final 和首轮历史记录，不维护第二套测试清单。

## Phase 验证记录（2026-09-24）

- R02/R04/B02/B04/B05：Runtime 记忆及权限相关七文件 68 passed；Platform 网关、审计与 Skills 回归六模块 34 tests OK。覆盖事务 CAS、导入计数、替换、委托、ACL、审计和公开路由。真实 Platform HTTP→Runtime HTTP→隔离 PostgreSQL schema 的 CRUD、409、422 脱敏、413 体积限制及重启读取均通过。
- R01/R03/R05/R06/R07：后续增量测试覆盖旧 JSON、候选/sources/墓碑边界、本人队列多源、并发 run 来源隔离、固定 10 正例＋10 负例召回。`test_memory_contract.py` 15 passed；`test_p6_governance.py`、`test_memory_access.py`、`test_context.py` 共 28 passed；授权三模块 20 passed、5 skipped（环境门控），均退出码 0。
- B01/B03：后续 Platform 六模块 50 tests OK，退出码 0，覆盖 OpenAPI、递归私有 state 注入拒绝、409/422/413 真实 HTTP/request_id、503/504 脱敏 adapter。回环夹具起初缺 request_id，补合成请求上下文后全组通过；正式服务错误处理无需修改。
- 独立 MAOMAO 模型：`DEAR_MEMORY_REAL_MODEL=1`＋Runtime `.env`＋独立 PG schema 的 `test_dear_memory_real.py` 1 passed（30.57s），候选 quote/来源、人工采纳、合成代号问答通过。第一次测试因同一异步客户端跨两个 `asyncio.run()` 失败，修正测试事件循环后通过；不计作生产模型故障。
- R08/B06/V03/V04：未取得平台完整 run/SSE、分享中途竞态、浏览器和可交接联调环境证据；真实 PG 断连完整链路、性能基线与部署回退尚未执行。MAOMAO 独立测试不能替代这些门禁。
- 环境：本机 PostgreSQL 的独立测试 schema；Docker daemon 不可用。测试用例创建并清理临时 schema，未写业务数据。依赖的 Runtime `.env` 仅在进程内加载，凭据不写文档。
- 静态检查：两服务改动相关 Python 文件 `compileall -q`、`git diff --check` 均退出码 0。前端现有 `run-actions.test.ts` 3 passed；该测试只表明现有 action 行为，不证明用户 3000 端口进程已更新。
- F01/F02/F03/F04/F05/F06/F07（Platform Web 前端实施与门禁验证）：
  - 执行 `pnpm --dir "apps/platform-web" test:run "src/services/dear-agent/memory.service.spec.ts" "src/modules/dear-agent/pages/DearAgentMemoryPage.spec.ts" "src/modules/chat/components/ThreadAccessControl.spec.ts" --maxWorkers=1 --minWorkers=1` → ✅ 3 Test Files passed (16 tests passed)，覆盖无线程 `/api/langgraph/dear/memory`、`MemoryView`、`ready_empty`、`disabled`、`ready_readonly`、候选 `quote` 与 `replace_fact_id`、409 `memory_revision_conflict` 草稿保留、跨项目反序响应 `scopeGeneration` 隔离、503 `request_id`、本地日期原样保留、Fresh GET 导出及非法分类拦截/服务端计数导入预览、共享会话隐私提示。
  - 执行 `pnpm --dir "apps/platform-web" typecheck`（`vue-tsc --noEmit`）→ ✅ 退出码 0（零类型错误）。
  - 执行 `pnpm --dir "apps/platform-web" exec eslint`（针对全部改动文件）→ ✅ 退出码 0（0 errors, 0 warnings）。
  - 孤儿文件 `useDearGovernanceContext.ts` 与 `useDearGovernanceContext.spec.ts` 已安全删除。

## Final 验证记录

未执行。状态 `partial`：后端管理 HTTP/PG、多来源和独立真实模型已有证据，但平台完整 run/SSE、浏览器联验和部署交接未完成，不能判定项目 done。

## 首轮实际记录


- 已完成：两仓源码链路核查、既有设计与历史验收记录对照；本地参考 HEAD `44ae7505`。
- 已确认：本地 runtime `.env` 声明启用治理；未读取/输出模型密钥或数据库连接串；未验证运行中进程加载值。
- 首次前端基线命令包含 MemoryPage、memory.service 和 useDearGovernanceContext 三个测试文件；退出码 1，三套均在 Vite/esbuild 转换阶段报 `The service is no longer running`，0 条断言执行。此结果是测试基础设施失败，不能推断记忆业务测试失败或通过。
- 单 worker 定向复验：相同命令追加 `--maxWorkers=1 --minWorkers=1`，退出码 0；MemoryPage 4、memory.service 7、useDearGovernanceContext 4，共 3 文件 15 条通过，耗时 46.27 秒。这些测试使用 mock，不证明真实存储、权限和模型闭环。
- 首轮未执行真实 PG 写入、实际用户页面诊断、模型调用、端到端、安全/性能和回滚演练；该条仅描述首轮调研，不覆盖上方本次 Phase 结果。
