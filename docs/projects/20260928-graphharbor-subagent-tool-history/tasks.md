# 任务拆分与阶段推进计划

## Phase 1: 需求交付与 GraphHarbor 团队对齐（跨团队协同）

### Task 1.1: 交付正式 RFC 文档给 GraphHarbor 团队
- **内容：** 将 [graphharbor-rfc.md](graphharbor-rfc.md) 提交给 GraphHarbor 核心研发团队并组织技术对齐会
- **预期结果：** 达成接口演进共识，确认采用方案 1（`expand_subagents`）或方案 2（`checkpoint_ns`），明确排期里程碑
- **预计：** 0.5 天
- **状态：** `[x]` 已完成（GraphHarbor 核心团队已确认痛点并正式发布 0.13.0.post37）

---

## Phase 2: platform-api 网关层承接建设

### Task 2.1: 放通子图查询参数白名单
- **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/threads_sdk_adapter.py`
- **改动内容：** 在 `_STATE_FIELDS` 与 `_HISTORY_FIELDS` 中扩展 `checkpoint_ns` 和 `checkpoint`，并在 `get_state`/`get_history` 中正确组装传给 LangGraph SDK
- **验证项：** 单元测试 `test_threads_get_state_passes_checkpoint_ns` 与 `test_threads_get_history_passes_checkpoint` 100% 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成

### Task 2.2: 状态接口扩展与路由适配
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- **改动内容：** `GET /threads/{id}/state` 增加 `checkpoint_ns` query 参数支持；新增 `POST /threads/{id}/state/checkpoint` 端点，对齐 LangGraph 官方 SDK 规范
- **验证项：** 语法检查、网关单元测试及真实 HTTP 端点调用全部通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成

---

## Phase 3: 服务栈升级与平滑重启

### Task 3.1: runtime-service 升级 graphharbor 依赖至 0.13.0.post37
- **代码位置：** `apps/runtime-service/pyproject.toml`, `apps/runtime-service/uv.lock`
- **改动内容：** 升级 `graphharbor` 及 `graphharbor-runtime` 到官方最新修复版本 `0.13.0.post37`
- **状态：** `[x]` 已完成

### Task 3.2: 执行 local-stack.sh 优雅重启并核验健康状态
- **命令：** `bash scripts/local-stack.sh restart`
- **验证项：** runtime-api (8123), runtime-worker, platform-api (2142), platform-web (3000) 全部健康拉起
- **状态：** `[x]` 已完成

---

## Phase 4: 端到端集成与真实会话回归验证

### Task 4.1: 全链路端到端真实会话验证
- **内容：** 针对真实历史 Thread `fba64a6c-0268-4609-bfc8-802c72b26dec` 和子图 `tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451`
- **验证项：**
  1. `GET /api/langgraph/threads/{thread_id}/state` 获取主图 18 条消息
  2. `GET /api/langgraph/threads/{thread_id}/state?checkpoint_ns=...` 成功获取子图 16 条消息与 10 次工具调用（`ls`, `read_file`, `grep`, `glob`）
  3. `POST /api/langgraph/threads/{thread_id}/state/checkpoint` 官方 SDK 模式成功获取 16 条消息
  4. `POST /api/langgraph/threads/{thread_id}/history` 成功获取子图 10 步历史追踪
- **状态：** `[x]` 已完成

---

## 进度追踪
- [x] RFC 需求提案文档已起草完成并就绪
- [x] GraphHarbor 团队方案确认并发布 post37 修复版本
- [x] platform-api 网关层放通并适配 checkpoint_ns 与 POST /state/checkpoint
- [x] 服务栈 local-stack.sh 完整重启
- [x] 全链路真实数据回归验证通过（10 次子智能体工具调用完整拉取）
