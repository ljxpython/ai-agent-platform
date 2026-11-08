# Runtime Agent 开发指南 - 验证记录

## 当前范围与验证策略

用户纠偏后的范围为入口修正、Agent 开发指南、案例/资料导航及本地验证说明；原 CI 接入与检查器扩展移出本期。没有改动 Python 业务代码、契约、运行配置、依赖或 CI。

因此本轮验证文档内容、文件/标题链接、源码符号、图配置和开发场景可操作性。产品单元、数据库集成、真实模型、浏览器 E2E 不作为本轮已通过证据；生产行为、性能与回滚演练不适用于此次纯文档变更。

## Phase 0：2026-11-08 现状检查

执行者：本次 AI 会话。审查对象为用户指定主工作区；规划输出位于关联 Worktree。

| 检查 | 实际结果 | 解释 |
|---|---|---|
| 两处 `git rev-parse --short HEAD` 与 `git status --short` | HEAD 均为 `1f2283e6`；Worktree 初始干净，主工作区存在其他未提交修改 | 没有改动主工作区；本轮 Runtime 静态基线可对照 |
| Runtime docs 文件清单 | docs 下 44 个 Markdown：根入口 1、standards 7、knowledge 32、changes 4 | 仅清点数量，不代表逐篇核验 |
| Runtime 测试清单 | 192 个 `test_*.py` | 文件数量不是测试用例数量，不代表通过 |
| JSON 解析 `langgraph.json` | reference_agent、workflow_demo、showcase_demo、dearflow_agent 共 4 图 | 入口都经过 `src/runtime_service/graphs/` |
| 现有 docs 检查器定向调用 | `self_check()` 通过；对 9 个入口/standards 文件调用 `check_file()` 得到 0 错误 | 该检查器未覆盖链接存在性；没有宣称全仓检查通过 |
| 相对 Markdown 文件链接定向扫描 | 检查 44 个链接目标；1 个不存在 | `apps/runtime-service/README.md:83` 指向 `../../docs/quickstart/deployment-guide.md` |
| README 中代码格式的证据路径检查 | 旧 OpenSpec verification 相对路径不存在 | 需要定位历史材料，不假设记录已丢失 |
| CI 与测试源码检查 | 无 Runtime pytest job；已有基线/依赖方向、schema、组合和安全测试 | 应复用现有资产接入 CI |
| Runtime 子树 AGENTS 清点 | 未发现 AGENTS.md | 根规则、standards 和 Skills 仍组成现有 Harness，不等于完全缺失 |

检查通过临时 Python 标准库脚本及 `runpy.run_path` 调用现有检查器完成；没有安装依赖、启动服务、读取私有 env、连接数据库或调用真实模型。路径存在性扫描只检查 Markdown 行内相对文件目标，不证明标题锚点、外部链接或文档语义正确。

以上是原始静态审查记录。CI 缺口保留为历史发现，不是本期实施任务。

## Phase 验证记录

### Task 1：入口纠偏
- 对照 `langgraph.json` 确认 4 个正式图均经过 graphs 稳定入口。
- 应用 README 的旧 standards 未生成描述已替换；失效部署链接指向当前 guides 路径。
- docs/README 的首读入口为当前开发指南，knowledge 保留为按需设计背景。
- 结果：通过静态核验。

### Task 2：Agent 开发指南
- 设计问题、选型、模块职责、目录、构图生命周期、接入步骤、能力规则、交付清单均存在。
- AST 核对 reference 的 get_agent/_build_agent、graph_tools/tool_catalog 及 graph_capabilities 真实定义位置。
- 依据当前代码说明 Graph 包装、capability 重导出位置和运行身份绑定；没有通过文档偷偷迁移源码。
- 结果：通过内容与源码定位核验；没有宣称新 Agent 实际执行通过。

### Task 3：案例、资料和验证导航
- 官方资料先查询 langchain-docs 与 langchain-reference MCP，取得 create_agent/create_deep_agent API 入口及相关教程；检查 docs 虚拟目录并读取 workflow、interrupt、backend、skill、subagent 等资料。
- 7 个 Runtime 指南/入口文件中共 147 个本地链接目标及其中的 Markdown 标题锚点检查通过。
- 三个静态开发场景走查：普通只读 Agent → reference 身份/策略与 schema 断言；确定流程 → Workflow 分支/审批恢复断言；文件与委派 → R4 机制及 Showcase 资源/探测/审批断言。相关测试函数均经 AST 确认存在，未执行。
- 标明旧案例 README 的版本/Context/注册描述差异，以及 fake、进程内状态和真实平台验收的区别。
- 结果：通过静态导航与场景走查。

### Task 4：记录与范围
- 当前计划、任务和状态索引同步为用户明确后的文档范围，移除旧 CI 提案的实施任务。
- 修改范围现有文档检查通过；新增文档检查尾随空白与本地链接。
- `git diff --check` 通过；差异仅涉及 Markdown 文档。无 CI、测试脚本、依赖、业务代码变更。
- 结果：完成记录核对；最终范围检查见下。

## Final 验证记录

### 2026-11-08 文档范围 Final

- 入口、指南、案例、资料查询、验证说明已交付。
- 已执行的检查：现有检查器定向调用、相对链接/锚点存在性、AST 定位、Graph JSON 对照、三个开发场景静态走查及差异检查。
- 收尾复核：14 个变更文件全部为 Markdown，现有检查器定向检查 0 错误；排除全局 CONTEXT/FEATURES 中的既有链接后，本期文档与项目记录共 154 个本地链接/标题锚点通过；任务清单无剩余未完成项，CI/代码差异为零。
- 产品测试：未运行，不计为通过；本期未改运行代码。
- 外部资料：通过官方 MCP 查询，不保证所有外部 URL 在所有网络环境中可达。
- 已知限制：部分案例 README 仍有早期叙述，导航已明确提示并直接链接当前源码/测试；未重写全部历史材料或解除任何生产门禁。
- **结论：** 本期文档范围 done；不代表原 CI 治理提案实施，也不代表新 Agent 或生产运行已验收。

## 追加范围 Phase：Task 5–6 全文审查与修订

- 实际范围：Runtime docs 45 篇（首轮新增指南后），案例 README 7 篇，共 52 篇；全部全文阅读，长文分段补读。
- 追加轮处置：45 篇修订、7 篇保留。逐篇结论、理由和核对依据见 [document-review.md](document-review.md)。
- 当前标准对照组合根、公共 MCP/预算/隐私/后台实现与后续专项；六篇案例直接纠偏，examples 的故意报表缺陷保留。
- 历史稿按篇说明有效设计和已取代的主张，在冲突章节加后续依据；撤下错误装配伪代码、修复路径和研究归属，不覆盖原始失败/延期/计数。
- 首次链接检查发现旧 07/09/17/21 文件、错误 Platform API 相对层级和迁移后的 chart schema；均已修复或明确缺失。新增清单迁移相对链接时的错误也在复核中修正，没有保留断链。
- 首轮 Final 中“案例 README 仍有历史描述”的限制由本次 Task 6 关闭；首轮结果不回写为当时已完成追加范围。

## 追加范围 Final：2026-11-08

- **结果：done（文档范围）。** Task 5–7 全部完成，未剩下可执行的本期文档任务；不代表产品、旧专项或生产部署整体通过。
- 临时 Python 标准库脚本逐项验证：60 个 Markdown 文件（52 篇审查对象 + 应用 README + 本项目 7 篇记录）；本地文件/标题链接全部通过，最终计数见下。检查没有扩展仓库 scripts/check_docs.py。
- 现有 scripts/check_docs.py 的 self_check() 与 check_file() 定向检查通过，0 错误；此检查器只负责本机绝对路径/退役 host，链接另查。
- AST 定位 18 个源码符号、10 个测试函数；当前规范/案例中 1 个 Python fenced snippet 语法解析通过。只证明符号/语法，不是运行测试。
- JSON 与 AST 核对正式 4 图、demo 6 图、两图入口包装、9 个 RuntimeContext 字段（无 tools）、Workflow 内存 saver/prepared_count；uv.lock 五项版本与文档一致。
- 审查清单 52 行与实际文件集完全覆盖，无遗漏；docs 下没有被排除的非 Markdown 文件。
- git diff --check 通过；整个本期共 58 个变更文件，全部 Markdown，未改 CI/源码/依赖/测试/运行配置。新增文件也纳入内容与链接检查。
- **未运行：** 产品单元/集成、真实模型/MCP、Docker、浏览器、生产部署；没有读取私人环境文件或启动服务。外部 URL 未逐个联网验证，历史外部研究未重新调研。
- **仍需识别的实现边界：** Workflow 教学 saver、Backend 教学全局 profile 不是新生产 Agent 模板；生产版本/权限/部署必须沿现行专项与目标环境证据，文档更新不替代验收。

最终链接计数：60 个文件中的 412 个本地链接及标题锚点，0 断链/错误锚点；外部 URL 未纳入可达性检查。

## 人工验收与交付收尾（2026-11-08）

- 用户明确人工验收通过，授权停止所属服务、标记完成、提交推送、合并主工作区、清理 Worktree 和所属测试数据库。
- 资源核验：本 Worktree 无 .local-stack/environment.json，公共登记无本路径条目；进程归属工具检查 Runtime API/Worker、Platform API/Web、Redis 均无所属 PID，lsof cwd 复核仅见检查命令自身。知识服务未登记，未调用会报环境缺失的 stop/destroy，也没有为清理反向初始化环境。
- PostgreSQL 仅只读查询数据库名称、owner 与归属注释；没有可归属本需求的测试数据库。本期未创建测试库，不删除其他专项或主环境库；数据库清理结果为“不适用（无所属资源）”。
- 合并前主工作区干净，main/origin/main 为 7bb848e4，比本需求起点 1f2283e6 多两个提交；其中业务源码、测试与项目交付均须保留。后续 Git 交付与清理结果如下。

- Git 实测：创建 docs/runtime-agent-development-guide-20261108，提交 5ea9ea8c 推送；将 main 合入分支，仅 CONTEXT.md 出现四处内容冲突，保留主干最新功能/服务状态及本需求记录。整合提交 2b434585 推送分支，主工作区使用 --ff-only 快进并推送 main。
- 远端复核：整合完成时，origin 的 main 与文档分支均为 2b4345852626b2cbf8e0a5fea6ce1e50a68bd922；没有强推、reset 或覆盖主工作区文件。
- 功能保留检查：主干两个新增提交涉及的 32 个文件中，CONTEXT/FEATURES 合并双方条目，其余 30 个文件逐一比较 Git blob 与原 main 7bb848e4 完全一致；HEAD 相对该主干 60 个差异全部为 Markdown，没有业务源码/测试/依赖/配置变化。
- 资源与目录收尾：本需求没有所属服务或测试数据库，清理不适用；git worktree remove（未使用 --force）成功，随后 Worktree 列表仅保留主工作区及原 retention-governance，f335 路径不存在，登记无本路径。
- 收尾静态复核：60 个文档文件中 413 个本地链接/锚点通过（比原 Final 多一条收尾导航）；既有检查器、AST/JSON/版本检查与 diff 空白检查通过。产品测试未重跑，用户本次验收不改写为自动化测试证据。
- 用户已批准的文档维护经验写入 ai-workflow 经验库，索引计数为 13；本需求状态为 done，人工验收和资源清理均已记录。以上收尾记录另以纯 docs 提交推送 main，提交结果以 Git 历史为准。
