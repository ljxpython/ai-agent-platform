# 会话访问策略默认调整为“全权负责 (Full access)”

## 背景

在平台 Chat 对话界面中，新建会话或草稿态下的“会话访问策略”此前硬编码默认为“审阅每项操作 (review)”。用户日常调试和使用时，每次创建新对话都需要手动展开下拉菜单、点击“Full access (全权负责)”并确认二次弹窗，操作极其繁琐。用户希望将前端默认选中的策略调整为“全权负责”。

## 改动内容

1. `apps/platform-web/src/modules/chat/components/ThreadAccessPolicySelect.vue`：
   - 将 `modelValue` 的 prop 默认值由 `"review"` 改为 `"full_access"`；
   - 将 `currentPolicy` 计算属性的 fallback 值由 `"review"` 改为 `"full_access"`；
   - 优化下拉菜单文案与徽标指示：
     - “审阅每项操作”右侧徽标由 `默认` 改为 `逐次审批`；
     - “Full access (全权负责)”右侧徽标由 `全放行` 改为 `默认 · 全放行`，消除 UI 歧义。
2. `apps/platform-web/src/modules/chat/components/ChatComposer.vue`：
   - 将 `ThreadAccessPolicySelect` 的 fallback 绑定 `:model-value="accessPolicy || 'full_access'"`。
3. `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts`：
   - 初始响应式状态 `accessPolicy` 默认值由 `"review"` 调整为 `"full_access"`；
   - 在 `applyAccessThread` 中：对于新会话或元数据未声明策略的会话，默认选用 `"full_access"`；若当前用户无 `full_access` 权限（如共享受限会话），则安全降级为 `"review"`；对于已明确声明策略的历史会话，严格尊重历史选择。
4. 单元测试更新：
   - `ThreadAccessPolicySelect.spec.ts`：补充无传入 props 时默认选中 `full_access` 的断言；
   - `useSessionConnection.spec.ts` & `useChatSession.spec.ts`：将草稿态默认策略由 `"review"` 调整为 `"full_access"` 并通过全量单测。

## 验证

- 单元测试：`ThreadAccessPolicySelect`、`useSessionConnection`、`useChatSession`、`ChatComposer` 等全量测试 100% 绿灯。
- 类型检查：`npm run typecheck`（`vue-tsc --noEmit`）0 错误。
- 静态检查：`npm run lint` 0 错误。
- 生产构建：`npm run build` 构建成功。
