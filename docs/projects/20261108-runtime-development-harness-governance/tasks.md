# Runtime Agent 开发指南 - 任务拆分

## 范围确认

- [x] 用户明确聚焦 Agent 设计、开发架构、规则、案例和资料查询，同意入口纠偏。
- [x] 原 CI 接入、检查器扩展、新增服务 AGENTS 和泛化 Harness 重构移出本期。
- [x] 核对当前入口、核心组合根、能力声明、案例/测试，并查询官方 docs/reference MCP。

## Task 1：入口纠偏
- **改动：** Runtime 两级 README、standards 首页；修正当前注册链路、开发导航和规范来源说明。
- **预期结果：** 当前指南优先，历史阶段资料有适用边界。
- **验证：** Graph JSON 对照、相对文件和标题链接核验 → 通过。
- **状态：** [x] 已完成 2026-11-08。

## Task 2：Agent 开发指南
- **改动：** 新增 runtime-agent-development-guide.md；development-standard 修正案例选择、注册路径和开发流程，保留专题细节规则。
- **预期结果：** 开发者明确如何设计、划分模块、装配、接入并交付 Agent。
- **验证：** 源码函数 AST 定位、指南内容核对、三个开发场景静态走查 → 通过。
- **状态：** [x] 已完成 2026-11-08。

## Task 3：案例、资料和验证导航
- **改动：** 重写 reading-guide，补充 onboarding 的按类型测试与 Worktree 入口。
- **预期结果：** 每例有用途/限制/源码/测试，官方资料按问题分类并说明版本核对。
- **验证：** 7 个 Runtime 文件共 147 个本地链接及标题锚点通过；官方 docs/reference MCP 入口核验；三组相关测试函数定位通过。
- **状态：** [x] 已完成 2026-11-08。未运行产品测试。

## Task 4：文档验证与收尾
- **改动：** 范围收敛、verification、implementation 记录及 CONTEXT/FEATURES。
- **预期结果：** 当前状态与用户指定文档范围一致；CI 提案不再混入任务。
- **验证：** 现有文档检查定向调用、链接/锚点核验、diff 空白检查与 Markdown-only 范围检查 → 通过，见 verification。
- **状态：** [x] 已完成 2026-11-08。

## 合规与交付

- [x] 文档实现与本期必要检查完成，Phase 与 Final 分开记录。
- [x] tasks、README、plan、verification 的范围与状态一致。
- [x] CONTEXT 与 FEATURES 已同步文档交付；服务部署状态不变。
- CHANGELOG：跳过，纯 docs 变更，不新增产品功能。
- 细节见 [implementation/01-agent-developer-docs.md](implementation/01-agent-developer-docs.md)。

首轮文档交付完成。用户追加以下范围，全部核验和必要修改完成前不作整体验收。

## Task 5：Runtime docs 全文逐篇审查
- **范围：** apps/runtime-service/docs 下全部文件，包含当前标准、knowledge、平台整合子目录和 changes；连同首轮新增指南复核。
- **要求：** 逐篇阅读全文，记录用途、需修改内容、核对依据和处置；不能以目录扫描或统一历史标签代替内容审查。
- **验证：** 审查清单覆盖实际文件集；当前规范对照源码/测试，历史设计保留原始阶段语义并注明逐篇差异及替代入口。
- **状态：** [x] 已完成 2026-11-08；45 篇 docs 全文复核，逐篇处置及依据见 document-review.md。

## Task 6：案例 README 当前化
- **范围：** reference、workflow、deep_agent、mcp、backend、Showcase 及其 examples README。
- **要求：** 更新模型/Context、Graph 注册、装配与资源边界、验证命令；核对源码，不保留已知错误后只靠总导航警告。
- **状态：** [x] 已完成 2026-11-08；六篇案例 README 当前化，examples 经 CSV/代码核对保留。

## Task 7：追加范围 Final 验证
- **要求：** 全部逐篇审查、所需修改、路径/锚点与规则一致性检查完成；独立保留首轮 Final 和追加范围 Final。
- **状态：** [x] 已完成 2026-11-08；412 个本地链接/锚点、现有检查器、AST/JSON/版本/审查覆盖及 Markdown-only/diff 检查通过；未执行产品测试，详见追加 Final。

## 人工验收与交付收尾（2026-11-08）

- [x] 用户人工验收通过，并明确授权提交、推送、合并与资源清理。
- [x] 核验服务/数据库归属：本 Worktree 无本地栈登记、无所属应用进程、无本需求测试数据库，无需删除其他任务资源。
- [x] Worktree 文档提交 5ea9ea8c 已推送；整合主干提交 2b434585 后快进 main，30 个主干新增文件保持 blob 完全一致。
- [x] main 已推送至远端 2b434585；使用非强制 git worktree remove 清理 f335，路径与 Worktree 登记均已移除。收尾记录另以 docs 提交同步。
