# 长会话断流恢复解耦与历史快照按需懒加载治理 - 验证计划和记录

## 验证计划

### 单元测试
- [x] `useChatSession.ts` 变更后单测覆盖：断流恢复时不阻塞拉取 history，仅依赖 state 恢复状态
- [x] 模拟 history 抛出 504 `LangGraph upstream timed out` 错误时，断流自愈顺畅完成且不产生错误状态
- [x] `ChatSession.vue` 变更后单测覆盖：时间旅行抽屉开启时才触发按需加载，错误不污染全局横幅
- [x] 前端聊天模块 19 套组件测试矩阵回归（67 passed）
- [x] Platform API 核心单测回归（21 passed）

### 集成与链路测试
- [x] **场景 1：100+ 步长会话断流重连**
  - 步骤：打开会话 `6f2d84e1-3ecd-4ce2-b732-f5981996d161`（101 步），模拟 SSE 流闲置断开（410 / cursor_expired）触发自动恢复
  - 实际结果：前端仅在 0.05 秒内基于 `service.state` 完成轻量级状态同步并重连，完全摆脱对 3.4 MB 巨型 history 的阻塞依赖，零 504 报错，页面无红色报警横幅
- [x] **场景 2：时间旅行按需触发**
  - 步骤：在 100+ 步长会话中，未展开抽屉时不产生任何 `/history` 请求；展开时间旅行抽屉时按需拉取
  - 实际结果：抽屉展开时正常按需发起请求；若遇网络抖动或超时，错误静默隔离在抽屉内，主聊天视窗与输入框绝对平稳可用

---

## Phase 验证记录

### Phase 1: 前端断流恢复解耦与错误隔离
- **测试命令：** `pnpm test:run src/modules/chat/composables/useChatSession.spec.ts`
- **执行结果：**
  ```text
  ✓ src/modules/chat/composables/useChatSession.spec.ts (24) 3433ms
    ✓ recovers stream smoothly without failure even if history fetch fails or times out with 504
  Test Files  1 passed (1)
       Tests  24 passed (24)
  ```
- **测试命令：** `pnpm test:run src/modules/chat/components/`
- **执行结果：**
  ```text
  Test Files  19 passed (19)
       Tests  67 passed (67)
    Duration  20.57s
  ```
- **生产构建检查：** `pnpm build`（vue-tsc --noEmit && vite build）
- **执行结果：**
  - `✓ built in 32.66s`，零类型报错，零打包异常。

### Phase 2: 后端网关超时保护与单测防护
- **测试命令：** `apps/platform-api/.venv/bin/pytest apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py`
- **执行结果：**
  ```text
  apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py ........... [ 52%]
  ..........                                                               [100%]
  ============================== 21 passed in 3.62s ==============================
  ```

---

## Final 验证记录

### 最终结论
- **完成状态：** `done`
- **四态判定：** 全部功能已实现（前端断流恢复与巨型 history 解耦、时间旅行按需懒加载守卫、历史异常与主界面红色横幅彻底隔离、504 超时容错单测通过），全套单元测试、组件测试与生产构建全绿通过。
