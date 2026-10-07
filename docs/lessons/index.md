# 经验库索引

> AI 读取规则：不需要全部加载。开始处理某个服务/领域改动前，按需读取对应文件。

| 文件 | 覆盖范围 | 条数 |
|---|---|---|
| [ai-workflow.md](ai-workflow.md) | AI 工作流、Harness、Skill 设计、文档规范与发布协作 | 5 |
| [cross-service.md](cross-service.md) | Platform API、Runtime Service 跨服务契约与 Delegation | 1 |
| [runtime-service.md](runtime-service.md) | runtime-service 服务内部、模块导入、工具治理 | 2 |
| [platform-web.md](platform-web.md) | 权限状态、刷新作用域与撤权回归 | 1 |

## 新增经验的流程

1. AI 犯了错，用户纠正
2. AI（或用户）将教训蒸馏为 ≤4 行，格式：场景 + 错误 + 正确做法 + 日期
3. 判断级别：
   - 任何场景都会犯 → 写进 `AGENTS.md` 的「严禁行为」章节（≤10 条上限）
   - 特定服务/领域才会犯 → 写进 `docs/lessons/{domain}.md`
4. 如果是新 domain 文件，更新本索引文件的表格行
