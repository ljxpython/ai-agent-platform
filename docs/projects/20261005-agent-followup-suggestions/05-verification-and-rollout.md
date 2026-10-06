# 验证与发布计划

## 目标

在不影响正常聊天、SSE、权限和多会话资源治理的前提下，验证建议问题链路的正确性、降级性和成本边界。

## 方案设计

### 分阶段门禁

1. **Phase 1：契约与纯函数**
   - 先锁定 Platform API/Runtime schema、scope operation、解析清洗和前端资格判断。
   - 只跑三服务定向单测，不开始真实模型调用。
2. **Phase 2：隔离集成**
   - Mock Runtime one-shot provider，验证 Platform API delegation、错误 envelope、空数组降级和无 Run/消息副作用。
   - Mock Platform API，验证前端生命周期和点击发送。
3. **Phase 3：本地最短链路**
   - `platform-web → platform-api → runtime-service → mock/本地模型`，至少验证一个 DearFlow Thread 和一个非支持 graph。
   - 核对审计字段、request_id/trace_id、Runtime token scope 和请求耗时。
4. **Phase 4：真实模型与浏览器验收**
   - 使用授权模型执行完成回答，等待建议出现，点击一项启动下一轮，确认消息顺序和普通 Run/SSE 不回归。
   - 完成后才由 `verify-change` 记录 Final 四态结果；规划阶段不提前写通过数字。

### 单元测试

- Platform API：请求 schema、线程 ACL、跨项目隔离、模型 catalog/policy、delegation operation、上游错误分类和标准 envelope。
- Runtime：scope 校验（含新增 `suggestions-generate`）、resolver/model mock、一次调用、超时、JSON/think/code fence/重复/超长清洗。
- Web：触发条件、取消和竞态、空/加载/错误状态、草稿追加/替换、无障碍和响应式关键 DOM。

### 集成测试场景

1. **成功**：完成 Agent 回答 → API 返回 1～3 条 → 前端展示 → 点击 → 复用正常 `send()` → 下一轮消息出现。
2. **配置关闭**：config `enabled=false`，前端不请求生成，正常聊天仍可用。
3. **模型失败**：Runtime provider timeout/非法 JSON，接口返回空数组，聊天消息、Run 状态、SSE 不受影响。
4. **权限拒绝**：用户失去 Thread read 或模型授权，建议请求返回明确 403；前端不把瞬态网络故障当成全局撤权。
5. **生命周期竞态**：答案 A 请求未返回即切到 Thread B/发送新消息，A 的响应不能渲染到 B；停止/审批时不产生建议。
6. **多会话**：后台 Thread 完成时只消费既有 stream，不因隐藏页面额外建立建议连接；切回后结果归属正确。
7. **副作用隔离**：调用前后 Thread messages、runs、checkpoints、workspace、tool audit 数量不因建议增加。
8. **Delegation 隔离**：`suggestions-generate` token 访问 suggestions 路由成功，访问原生 Thread/Run/workspace/tools 全部拒绝；未知 operation 和缺失 scope 仍按标准拒绝。

### 端到端测试

- 使用真实登录用户、项目、DearFlow Thread 和已授权模型。
- 验证 Network 只有浏览器 → Platform API 的建议请求；浏览器看不到 Runtime URL/JWT。
- 验证 Platform API → Runtime 的 delegation operation、thread_id、assistant_id、project_id 一致。
- 验证建议使用用户语言、问题简短且与最后一轮上下文相关；点击后新用户消息只出现一次。
- 验证正常 SSE 心跳、审批、队列、重连、权限刷新和历史回放没有被 suggestions 请求改写。

### 性能与成本

- 记录建议接口 p50/p95、超时比例、返回数量和 provider 错误分类；首版建议 p95 目标 ≤ 8 秒（目标不是硬 SLO，需运行数据后再定）。
- 单次建议最多一次模型调用，不重试；最多 5 条输出、256 output tokens、8 秒 timeout。
- 并发压测至少覆盖同一用户多 Thread 和同一 Thread 重复完成事件；前端去重，Runtime 不承诺服务端缓存。

### 回滚和灰度

- 通过全局 `suggestions_enabled` kill switch 关闭；关闭后无需回滚正常聊天代码路径。
- Platform API route 保留但返回空数组；Runtime capability 可独立禁用。
- 发现模型成本、权限或资源问题时先关开关，再保留日志和请求样本摘要排查。
- 不做数据库迁移，因此没有数据回滚步骤；只需回滚三服务代码/配置。

## 任务拆分

- [x] Task 5.1：补三层契约和单元测试矩阵。Platform API 与 Runtime 定向契约/服务测试已完成，前端测试待交接。
- [ ] Task 5.2：完成 Mock Runtime/Platform 集成测试。
- [ ] Task 5.3：完成本地三服务最短链路和副作用核对。
- [ ] Task 5.4：完成真实模型浏览器 E2E、性能采样和 kill switch 验证。
- [/] Task 5.5：调用 `verify-change`，已记录当前单测/Ruff 证据；集成、E2E、性能/安全和四态结论仍待补齐。

## 验证要求与记录

### 验证要求

- [x] Platform API 定向 pytest 通过。
- [x] Runtime 定向 pytest 通过。
- [ ] Platform Web 定向 Vitest、`vue-tsc`、生产构建通过。
- [ ] 三服务最短 E2E 通过，失败降级和权限拒绝均有证据。
- [ ] 关键链路无新增 Run、消息、checkpoint、工具副作用。

### 验证记录

#### 2026-10-06 Phase 验证

**执行范围：** Platform API + Runtime Service 后端实现。

- ✅ Platform API suggestions + delegation 定向测试：8 passed，48 个参数化子测试通过。
- ✅ Runtime Service suggestions 定向测试：10 passed。
- ✅ Platform API/Runtime 改动文件 Ruff 检查通过。
- ✅ Delegation operation、请求 schema、模型策略、Thread ACL、输出清洗、超时/provider 降级和无副作用路径均有定向覆盖。
- ⚠️ Platform API 全量 pytest：323 passed、16 skipped、643 个参数化子测试；2 个既有 workspace HTML 脚本过滤断言失败，与本项目无关。
- ⚠️ Runtime Service 全量 pytest：572 passed、85 skipped；真实 DeepSeek 配置缺失 1 项失败，Docker daemon 未启动导致 1 项失败。
- ⚠️ 三服务 Mock 集成、真实模型 E2E、Platform Web Vitest/类型检查/构建和浏览器验收尚未执行。

#### 2026-10-06 Final 四态判定

**结论：** `partial`

- **已通过：** 后端代码实现、后端定向单元/契约测试、改动文件 Ruff；前端交接文档已冻结。
- **未完成：** Platform Web 业务接入、前端测试与浏览器验收；真实 `platform-web → platform-api → runtime-service` 链路；真实模型性能/成本采样；正式 Delegation 标准人工评审。
- **阻塞原因：** 前端业务由同事接手，当前会话不修改 `apps/platform-web`；本地未具备可复现的三服务真实运行与授权模型验收条件。
- **回滚准备：** `suggestions_enabled` kill switch 已实现；关闭后 Platform API 返回空数组，不影响正常聊天路径；未新增数据库表，无数据回滚动作。

#### 未执行项与下一步

1. 前端同事按 [Platform Web 前端交接](04-platform-web-handoff.md) 完成 API/composable/UI/测试。
2. 具备本地三服务和授权模型后执行 Mock/真实 E2E，并核对无消息、Run、checkpoint、workspace、tool 副作用。
3. 完成前端浏览器验收、性能采样和 Delegation 标准人工评审后，再将项目状态从 `partial` 更新为 `done`。

## 状态

部分完成

后端实现与定向验证完成；全量测试存在已识别的环境/既有测试失败，前端与真实链路尚未完成。
