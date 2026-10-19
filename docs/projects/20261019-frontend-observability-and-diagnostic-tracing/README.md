# 前端可观测性与端到端排障链路增强 (Frontend Observability & Diagnostic Tracing)

## 项目概述
- **时间：** 2026-10-19 至 2026-10-20
- **目标：** 建立前端运行时异常防御、网络与 SSE 错误追踪环形缓冲、对齐后端 Trace/Error Envelope 契约；深入借鉴参考 open-swe 工业级设计（去业务化），构建三层（Web → API → Runtime）端到端排障体系，支持就地查看排障模态窗、结构化原因码与 Actionable 恢复建议、无缝联动轨迹诊断，并由 Playwright + Chromium 自动化 E2E 闭环验收。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** `done`

## 快速导航
- [整体方案 (V2)](plan.md)
- [任务拆分 (V2)](tasks.md)
- [验证计划 (V2)](verification.md)

## 改动范围
- **影响服务：**
  - `platform-web`：就地排障详情模态窗 (`DiagnosticDetailModal.vue`)、状态栏交互升级、错误反解与 Actionable 恢复建议、联动轨迹视图
  - `platform-api`：Run 错误分类器（`run_error_classifier.py`，对齐 open-swe 规范）、诊断快照接口强化、全链路 `request_id` 回显
  - `runtime-service`：LangGraph Node 级异常捕获收尾校验、杜绝 SSE 流静默断连
- **改动级别：** 链路改动
- **预计工作量：** 2 人天

## 关键决策
1. **就地排障弹窗 vs 全屏白屏崩溃**：坚决禁止将业务层 Run 级失败（大模型超时、沙箱失联）粗暴重定向为全屏 CrashScreen（白屏卡片仅用于底层 Vue 语法/渲染致命崩溃）；业务报错在状态栏提供【查看排障详情】按钮，就地弹出 `DiagnosticDetailModal.vue`，保护用户正在进行的会话上下文与草稿。
2. **借鉴 open-swe 结构化错误与 Actionable Follow-up 体系**：彻底消灭“执行出错”这种空洞黑盒文案；三层统一推行标准化机器码（`provider_timeout`、`context_too_long`、`step_limit`、`sandbox_unreachable` 等），不仅直观告知用户为什么失败，更明确给出“下一步该干什么”（例如“建议新建会话重置上下文”）。
3. **与已有 TrajectoryView / RunDiagnostics 无缝桥接**：利用已有但深藏的 `RunDiagnostics.vue`，在排障模态窗中提供【前往完整轨迹】快捷入口，一键平滑切换视角并直达诊断标签页，实现轻量查看与深度剖析的双层打通。
4. **Playwright + Chromium 自动化端到端测试闭环**：通过无头/有头浏览器自动化驱动，全真模拟错误触发、弹窗查看、字段核验与视角跳转，并截图固化为不可篡改的工程证据链（`assets/` 目录下共 4 张实景留痕）。
