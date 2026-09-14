# DeepSeek Harness 轨迹视图迁移 - 验证计划和记录

## 验证计划
### 单元测试
- [ ] `trajectory-adapter.spec.ts`:
  - [ ] 用户提问转换为 `user` 类型轨迹记录。
  - [ ] AI 思考链转换为 `reasoning` 类型轨迹记录。
  - [ ] AI 生成内容转换为 `assistant` 类型轨迹记录。
  - [ ] 工具调用及其返回结果关联并转换为 `tool` 类型轨迹记录。
  - [ ] 缺失耗时与 Token 字段时，数据适配层提供正确 fallback，不抛异常。
  - [ ] 工具报错时，标记 status 为 `error` 并保留错误详情。

### 类型检查与前端编译
- [ ] `pnpm --filter platform-web typecheck` (vue-tsc --noEmit) 零错误。
- [ ] `pnpm --filter platform-web lint` 零未修复错误。

### 功能与端到端验收
- [ ] 在 Chat 界面中能够正常点击 `[ 对话 | 轨迹 ]` 视图切换开关。
- [ ] 轨迹视图左侧正确展示分轮次（Turn）的事件流水。
- [ ] 点击任一流水条目，右侧检查器高亮并展示正确的 Overview、Input、Output、Reasoning、Raw JSON 内容。
- [ ] 对话流中正在进行时（isRunning），轨迹视图实时响应更新。
- [ ] 切换回普通对话视图，原聊天交互不受任何副作用影响。

## 验证记录

### 1. 适配层单元测试
执行命令：
```bash
rtk pnpm --filter platform-web test:run src/modules/chat/trajectory/trajectory-adapter.spec.ts
```
结果：
- `✓ src/modules/chat/trajectory/trajectory-adapter.spec.ts (7 tests) 25ms`
- 覆盖人类提问、思考过程提取、工具调用与结果匹配、报错态识别、Token 提取与轮次分组，全部通过。

### 2. 组件单元测试
执行命令：
```bash
rtk pnpm --filter platform-web test:run src/modules/chat/components/trajectory/TrajectoryView.spec.ts
```
结果：
- `✓ src/modules/chat/components/trajectory/TrajectoryView.spec.ts (3 tests) 511ms`
- 验证了空态渲染、带工具调用与思考记录的流水账渲染、点击记录激活检查器、以及过滤选项切换。

### 3. 类型检查
执行命令：
```bash
rtk pnpm typecheck
```
结果：
- `TypeScript: No errors found`，零类型报错。

### 4. 整体 Chat 测试套件回归
执行命令：
```bash
rtk pnpm vitest run src/modules/chat
```
结果：
- `Test Files 23 passed | 1 skipped (24)`
- `Tests 74 passed | 1 skipped (75)`
- 原有聊天与所有子组件功能保持 100% 兼容，无回归问题。


