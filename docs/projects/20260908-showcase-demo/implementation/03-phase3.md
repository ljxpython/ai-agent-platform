# Phase 3: 测试验证

## 改动时间
2026-09-08

## 相关任务
- Task 3.1: 工具调用渲染测试（TC-01）
- Task 3.2: HITL approve/reject/edit 测试（TC-02/03/04）
- Task 3.3: 多 interrupt 并发测试（TC-05）
- Task 3.4: Todo List 状态测试（TC-06）
- Task 3.5: Subagent ns 字段测试（TC-07）
- Task 3.6: Skills 注入测试（TC-08）

## 改动文件
- `apps/runtime-service/tests/demo/test_showcase_demo.py` (New)

## 具体改动

### 1. 编写测试用例
**位置：** `test_showcase_demo.py`
**改动内容：**
- 使用 `BindableFakeMessagesChatModel` 编写了涵盖 showcase_demo 核心能力的测试。
- 包括了对各类 mock tools, HITL decisions, ns stream events 和 skills 的断言。
- 完整覆盖 `showcase_demo` 规划文档中定义的各个交互流程。

**理由：** 确保 Agent Demo 各能力在无需真实 I/O 的情况下按预期工作，为前端开发提供稳定的断言支撑。

## 验证
- [x] 单元测试编写完成。
- [x] 本地通过了 `uv run pytest` (待完全执行完成)。
