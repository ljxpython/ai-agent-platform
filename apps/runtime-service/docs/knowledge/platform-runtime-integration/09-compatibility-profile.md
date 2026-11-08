# Compatibility Profile

## 阅读边界（2026-11-08 复核）

本表冻结的是 2026-09 的历史联调 profile，不是当前锁定依赖，也不是本轮兼容验收。当前版本真源为各 app 的 manifest 与 lock；2026-11-08 Runtime uv.lock 静态核对 GraphHarbor 双包 post48、LangGraph 1.2.11、LangChain 1.3.17、DeepAgents 0.7.8，未重跑整套兼容矩阵。

本文件保留当时本地联调所使用的版本与协议边界；当前安装与兼容验收须重新对照锁文件和测试。

## 版本

| 组件 | 来源 | 锁定版本 |
| --- | --- | --- |
| Platform Web | `apps/platform-web/package.json` | `@langchain/vue 1.0.29`、`@langchain/langgraph-sdk 1.9.28` |
| Platform API | `apps/platform-api/uv.lock` | `langgraph-sdk 0.4.2` |
| GraphHarbor | `apps/runtime-service/pyproject.toml`、`uv.lock` | `graphharbor 0.13.0.post20` |
| Runtime graph host | `apps/runtime-service/pyproject.toml`、`uv.lock` | `langgraph 1.2.11`、`langgraph-sdk 0.4.3` |
| Runtime provider adapters | `apps/runtime-service/uv.lock` | `langchain-openai 1.6.0`、`langchain-deepseek 1.1.0` |

Platform Web 以自身 `package.json` 的 SDK 版本为浏览器兼容基线；Platform API 的 Python SDK 只负责
服务端 upstream adapter，不把 Python SDK 类型泄漏到浏览器。

## 当前允许的 Agent Server surface

- `GET /info`
- `POST /graphs/search`、`POST /graphs/count`
- Thread create/search/count/get/delete
- Thread state/history
- Thread Run create/list/get/join/stream/cancel
- Protocol v2 `POST /threads/{thread_id}/commands`
- Protocol v2 `POST /threads/{thread_id}/stream/events`

Gateway 只公开正式 Chat 需要的 allowlist。Assistant mutation、global/batch/cron/store/system 和
debug surface 不属于本 Profile。

## 验收要求

> **后续对照：** 下列是旧联调命令；新开发按 [运行与验证](../../standards/runtime-service-onboarding-and-verification.md) 选择范围和工作目录。版本表中的 post20 不应用于降级当前环境。

每次升级组件必须重跑：

```bash
npm run --prefix "apps/platform-web" typecheck
npm run --prefix "apps/platform-web" test:run
uv run --project "apps/platform-api" --frozen python -m unittest discover -s tests -p 'test*.py' -q
uv run --project "apps/platform-api" --frozen python scripts/local_stack_l2_runtime_smoke.py --restart-check
```

版本或 endpoint 变更未通过上述检查前，不得将其标记为兼容或更新生产部署说明。

## 状态

版本清单：`local-complete`。真实 GraphHarbor 负面矩阵、HITL 和浏览器完整 Chat E2E 仍按
OpenSpec `tasks.md` 标记为未完成。
