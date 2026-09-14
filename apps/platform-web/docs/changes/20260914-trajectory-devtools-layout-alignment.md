# 智能体轨迹排障视图深度对齐与工业级 DevTools 体验重构

## 背景与诉求
此前第一版轨迹视图（`TrajectoryView`）采用了移动端风格的卡片式布局（Card-based），每个事件均有厚重的圆角外边框和大边距，单屏信息密度不足 30%。相比业界标杆（`deepseek-harness` 的 `ui-trajectory`），缺少多通道时间流（Gantt Strip）时序感知、缺少纵向树状连接线、类别徽章不规范、右侧检查器信息层级散乱。

## 变更内容
1. **多通道甘特时间线 (`TrajectoryTimeline.vue`)**：
   - 新增顶部甘特图组件，提供 `Input`（系统/上下文/用户）、`Model`（思考/助手输出）、`Tools`（工具/子智能体）三层独立横向轨道。
   - 实现横向时间片投影与颜色编码（蓝/绿/紫/黄），支持点击色块与下方列表高亮联动。
2. **事件账本表格紧凑重构 (`TrajectoryLedger.vue`)**：
   - 移除厚重卡片外框，采用 Chrome DevTools Network 风格单行行内展示（高度 ~32px），单屏可同时扫描 15~20 个事件。
   - 实现左侧外挂 Turn 标识、垂直贯穿树线（Turn Rail）与节点连接圆点。
   - 规范微型徽章系统：`SYSTEM`（深灰）、`USER`（亮蓝）、`CONTEXT`（翠绿）、`ASSISTANT`（紫蓝）、`TOOL`（琥珀金）。
   - 选中行采用左边缘 3px 鲜艳指示竖条，取消笨重外边框。
3. **检查器详情面板重构 (`TrajectoryInspector.vue`)**：
   - 对齐 `Summary` / `Preview` / `Raw` 三档 Tab 结构。
   - `Summary` 提供极简两列无边框属性列表（Source, Status, Duration, Tokens）并在下方内联直出富文本/Markdown 预览区，无需切 Tab 即可审视内容。
   - `Preview` 支持独立全屏沉浸式 Markdown 阅读与内容复制；`Raw` 提供格式化代码与一键复制。
4. **数据适配层增强 (`trajectory-adapter.ts` & `types.ts`)**：
   - 拓展 `TrajectoryRecordKind` 支持 `system` 与 `context` 类型。
   - 自动识别 `<system-reminder>` 与运行时指令作为 `context` 类别，实现高精度分类。
   - 提取各事件的 `durationMs`，为时间线甘特切片提供真实/估算时长支持。
5. **视图总控与指标底栏 (`TrajectoryView.vue`)**：
   - 顶部集成即时搜索框（支持实时按事件名、类型、内容过滤）。
   - 底部补充工业级性能小字（轮次、步骤、工具调用数、Token 输入输出统计）。
6. **质量与测试保障**：
   - 新增 `TrajectoryTimeline.spec.ts` 并更新 `TrajectoryView.spec.ts`。
   - 全量 47 个测试套件（143 项单元测试）100% 通过。
   - `vue-tsc` 0 类型错误，`eslint` 0 error 0 warning，`vite build` 生产构建通过。

## 涉及文件
- [NEW] `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryTimeline.vue`
- [NEW] `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryTimeline.spec.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryLedger.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryInspector.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryView.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryView.spec.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/trajectory/types.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts`
