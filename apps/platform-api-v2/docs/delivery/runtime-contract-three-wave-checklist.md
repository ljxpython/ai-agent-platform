# Runtime Contract 三波次改造清单

这份清单只服务当前这一轮标准化改造：

- 后端只看 `apps/platform-api-v2`
- 前端只看 `apps/platform-web-vue`
- 历史目录不再纳入本轮改造

目标不是继续兼容旧写法，而是把 Runtime Contract 彻底收成一套简单、稳定、可测试的标准范式。

## 1. 冻结前提

- [x] 当前正式主线锁定为 `apps/platform-api-v2` + `apps/platform-web-vue`
- [x] `apps/platform-api` / `apps/platform-web` / `apps/platform-web-v2` 已归档，不再作为改造对象
- [x] 运行时字段分工已经冻结：
  - `context` 只承载运行时业务字段
  - `config` 只承载执行控制字段
  - `config.configurable` 只承载线程 / 平台 / 私有字段
- [x] 已确认 `@langchain/vue` + `@langchain/langgraph-sdk` 的 `submit(values, options)` 支持直接传 `options.context`
- [x] 当前三波次方案与文件级改造范围已评审确认

## 2. 波次一：收死 `platform-api-v2` 的 Runtime Contract

### 2.1 目标

- 建立唯一后端 runtime contract 真相源
- 让 `assistants` 与 `runtime_gateway` 共用同一套 normalize 逻辑
- 让 parameter schema 与真实 contract 严格一致

### 2.2 文件清单

- [x] 新增 `apps/platform-api-v2/app/core/runtime_contract.py`
  - 统一沉淀 runtime contract 常量与纯函数
  - 包含 runtime business keys、trusted context keys、project alias keys
  - 提供公共 normalize helper，禁止模块内重复各写一套
- [x] 修改 `apps/platform-api-v2/app/modules/assistants/application/service.py`
  - 删除本地重复 contract 常量和内联 normalize 逻辑
  - 改为复用 `app/core/runtime_contract.py`
- [x] 修改 `apps/platform-api-v2/app/modules/runtime_gateway/application/service.py`
  - 重写 `_inject_project_scope()`，统一走共享 runtime contract helper
  - 所有 run / cron / thread-run 入口统一收口为最终 contract
- [x] 修改 `apps/platform-api-v2/app/adapters/langgraph/parameter_schema.py`
  - 改为从共享 contract 生成 `config / context / configurable` 三段 schema
  - 禁止 schema 与真实运行时字段漂移
- [x] 修改 `apps/platform-api-v2/tests/test_assistants_runtime_contract.py`
  - 断言 assistant create / update 的 normalize 行为全部符合最终 contract
- [x] 新增 `apps/platform-api-v2/tests/test_runtime_gateway_runtime_contract.py`
  - 覆盖 global run / thread run / cron 入口的 payload normalize 行为
- [x] 修改 `apps/platform-api-v2/tests/test_phase6_normalization_regressions.py`
  - 只保留真正的 regression 行为
  - 去掉与主 contract 测试重复的断言
- [x] 修改 `apps/platform-api-v2/tests/test_graph_parameter_schema_provider.py`
  - 补齐最终 contract 的 schema 断言
  - 保证 `context` 中出现业务字段，`configurable` 中只出现平台 / 私有字段
- [x] 修改 `apps/platform-api-v2/docs/decisions/chat-use-stream-contract.md`
  - 把最终 runtime contract 口径写成正式标准

### 2.3 验收

- [x] 运行：
  - `uv run pytest -q tests/test_assistants_runtime_contract.py tests/test_runtime_gateway_runtime_contract.py tests/test_graph_parameter_schema_provider.py tests/test_phase6_normalization_regressions.py`
- [x] 验证 assistant create / update 不再接受业务字段落进 `config.configurable`
- [x] 验证 runtime gateway 的 run / cron / thread-run 入口统一把业务字段归位到 `context`

## 3. 波次二：收死 `platform-web-vue` 的 Assistant / Chat 提交契约

### 3.1 目标

- 前端建立唯一 runtime contract helper
- assistant create / detail 与 chat submit 共用同一套 contract 映射
- 彻底停止把业务字段塞进 `config.configurable`

### 3.2 文件清单

- [x] 新增 `apps/platform-web-vue/src/services/runtime/runtime-contract.ts`
  - 作为前端唯一 runtime contract helper
  - 负责 assistant payload normalize、chat submit options build、project alias 清理
- [x] 修改 `apps/platform-web-vue/src/services/assistants/assistants.service.ts`
  - `createAssistant()` / `updateAssistant()` 发出前统一走 runtime contract helper
- [x] 修改 `apps/platform-web-vue/src/modules/assistants/pages/AssistantCreatePage.vue`
  - `requestBodyPreview` 和最终提交统一走共享 helper
  - 不再把 `model_id / enable_tools / tools` 写进 `config.configurable`
  - 页面说明文案同步改为最终 contract 口径
- [x] 修改 `apps/platform-web-vue/src/modules/assistants/pages/AssistantDetailPage.vue`
  - 保存前统一 normalize `config / context / metadata`
  - 不再原样回传脏 payload
- [x] 修改 `apps/platform-web-vue/src/modules/chat/composables/platform-chat-stream/helpers.ts`
  - 将 `buildRunConfig()` 改为最终提交结构
  - 输出 `context + config`，不再把业务字段塞进 `configurable`
- [x] 修改 `apps/platform-web-vue/src/modules/chat/composables/platform-chat-stream/actions.ts`
  - 所有 `submit()` 调用点统一显式传 `context` 和 `config`
  - 保留 `interruptBefore / interruptAfter` 的执行控制职责
- [x] 复核 `apps/platform-web-vue/src/modules/chat/composables/usePlatformChatStream.ts`
  - 仅在类型或透传链路需要时做最小改动
  - 已确认本轮无需改动，`submit(..., { context, config })` 透传链路成立
- [x] 新增 `apps/platform-web-vue/src/services/runtime/runtime-contract.spec.ts`
  - 覆盖 assistant payload 与 chat run options 的 contract normalize

### 3.3 验收

- [x] 运行：
  - `cd apps/platform-web-vue && pnpm test:run`
- [x] 运行：
  - `cd apps/platform-web-vue && pnpm typecheck`
- [ ] 验证 assistant create / edit 页面发出的业务字段只进入 `context`
- [ ] 验证 chat 新线程 / 旧线程继续 / resume interrupt 都通过 `context + config` 提交

## 4. 波次三：清掉假抽象、死代码和验收护栏缺口

### 4.1 目标

- 删掉没有实际价值的前端 control-plane 假抽象
- 清理无调用方的旧 runtime stream 死代码
- 把最终范式固化到文档和测试里

### 4.2 文件清单

- [x] 删除 `apps/platform-web-vue/src/services/platform/control-plane.ts`
  - 这层当前没有真实模块分流能力
  - 直接收平，避免继续制造假抽象
- [x] 修改 `apps/platform-web-vue/src/services/langgraph/client.ts`
  - 直接依赖真实的 `platformApiBaseUrl`
  - 保留绝对 `apiUrl` 与授权刷新逻辑
- [x] 修改 `apps/platform-web-vue/src/services/runtime/runtime.service.ts`
  - 去掉对 fake control-plane 的依赖
  - 直接使用正式 http client
- [x] 修改 `apps/platform-web-vue/src/services/runtime-gateway/workspace.service.ts`
  - 去掉对 fake control-plane 的依赖
  - 删除无调用方的 `createRuntimeRunStream()`
- [x] 修改 `apps/platform-web-vue/src/services/langgraph/client.spec.ts`
  - 补齐 client 收平后的 base url / auth fetch 回归断言
- [x] 修改 `apps/platform-web-vue/docs/chat-langchain-vue-migration-blueprint.md`
  - 把 chat 提交范式更新为最终 runtime contract
- [x] 修改 `apps/platform-api-v2/docs/delivery/platform-web-vue-capability-coverage.md`
  - 补记 runtime contract 收口后的正式能力对账

### 4.3 验收

- [x] 验证前端不再保留假的 module-aware control-plane client 抽象
- [x] 验证无调用方的 `createRuntimeRunStream()` 已删除
- [x] 验证文档、测试、实际代码三者的 contract 口径一致
- [ ] 联调通过：
  - assistant create
  - assistant edit
  - chat 新线程发送
  - chat 旧线程继续
  - debug continue
  - cancel run

## 5. 最终验收标准

- [ ] `project_id` 只认 `context.project_id`
- [x] runtime business fields 只允许进入 `context`
- [x] `config` 只保留执行控制字段
- [x] `config.configurable` 只保留线程 / 平台 / 私有字段
- [x] assistant 与 chat 走同一份 runtime contract helper
- [x] 后端 schema、前端提交、runtime gateway normalize 三者完全一致

## 6. 联调清单

- [x] 已建立手工联调清单：`./runtime-contract-manual-integration-checklist.md`
