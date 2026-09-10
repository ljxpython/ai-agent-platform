# Phase 1: 基础建设

## 改动时间
2026-09-08

## 相关任务
- Task 1.1: 创建 schemas.py
- Task 1.2: 创建 tools.py
- Task 1.3: 创建 Skills 文件

## 改动文件
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/schemas.py` (New)
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/tools.py` (New)
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/skills/showcase-notes/SKILL.md` (New)

## 具体改动

### 1. 创建 schemas.py
**位置：** `schemas.py`
**改动内容：**
- 新增 `ShowcaseTodo` 和 `ShowcaseState`
- 使用了 `Annotated[list, add_messages]` 作为 `messages` 字段，保证 LangGraph 正确处理消息流。
- 包含了 `todos`, `scenario`, `requires_confirmation`, `confirmation` 等字段。

**理由：** 为 Showcase Demo 提供 StateGraph 所需的状态类型定义，支持 Todo List。

### 2. 创建 tools.py
**位置：** `tools.py`
**改动内容：**
- 新增 7 个 mock 工具 (`read_project_file`, `write_project_file`, `execute_command`, `search_code`, `fetch_documentation`, `write_todos`, `confirming_completion`)。
- 每个工具按照要求设置了特定的参数名称（如 `CommandLine`, `SearchDirectory`, `path`, `todos`），使得前端可以依据参数名称解析出工具类别 (kind) 以及标题信息。

**理由：** 提供在 Agent Demo 中展示前端各个能力（读取、编辑、执行、搜索等）的工具调用。

### 3. 创建 SKILL.md
**位置：** `skills/showcase-notes/SKILL.md`
**改动内容：**
- 包含 YAML frontmatter (`name`, `description`)
- 说明了 Showcase Demo 支持的触发词和演示场景，作为供 Agent 自己搜索查询的说明。

**理由：** 验证 Agent 的 Skills 注入和知识检索能力。

## 验证
- [x] 类型检查（通过 IDE 和静态分析确认代码符合 TypedDict/tool 定义）

## 注意事项
- 工具只是 mock 实现，实际不涉及真实 I/O，以避免对环境造成破坏，重点在于覆盖各个交互 kind。
