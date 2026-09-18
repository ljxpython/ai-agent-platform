# AI Agent Platform 开发规范

这是项目的 AI 协作入口，定义了开发流程、分级标准和验证要求。

## 快速开始

**新人必读：**
1. 阅读 `README.md` - 了解项目架构
2. 阅读 `docs/quickstart/` - 快速上手

**改动分级不是一个要手动调用的步骤**，AI 在接到任何改动请求时，先按下面「改动分级」的标准自行判断落在哪一级，再决定要不要往下走文档化/验证流程——用户不需要先跑什么命令。判断结果偏"重"（链路/治理改动）但依据不充分时，AI 应该直接问一句，而不是自己拍板往轻处理。

纯讨论、探索性规划、"这个方案是否可行"之类的问题，不生成任何文档，直接对话给结论；只有用户明确要落地实现时，才按下面的分级流程进入文档化。

**Skills（AI 按场景自动调用，用户通常不需要手动触发）：**
- `plan-project` - 判断出链路改动/治理改动时，AI 自动在 `docs/projects/` 下创建项目文档
- `implement-feature` - 项目文档存在时，AI 实现任务过程中自动记录改动细节
- `verify-change` - 实现完成后，AI 自动执行验证并记录结果（含四态判定）

## 改动分级（单项目改动/链路改动/治理改动）

### 单项目改动
**范围：** 单服务内部，不影响对外契约

**流程：**
```
直接实现 → 单元测试 → Commit
```

**文档：** 不需要 `docs/projects/` 项目文档，但要看这个改动会不会改变"这个服务现在有哪些功能"这个答案：
- 会（新增/改变了一个能力，哪怕只在单服务内）→ 在 `apps/{app}/docs/changes/{YYYYMMDD}-{slug}.md` 留一份轻量记录（背景+改了什么+涉及文件，几行话，不套用项目文档模板），并同步更新 `docs/FEATURES.md` 里对应的一行
- 不会（纯 bug fix、内部重构、typo、加日志）→ commit message 即可，不建文档

**示例：**
- 重构内部函数、修复单服务内 bug、加日志 → 不建文档
- 给 runtime-service 加一个新的内部工具封装、给 platform-web 加一个新页面组件 → 留痕到 `apps/{app}/docs/changes/`

---

### 链路改动
**范围：** 跨服务改动，影响服务间契约或数据模型

**流程（AI 自动执行，无需手动触发）：**
```
plan-project → 实现 → 链路测试 → verify-change
```

**文档：** 需要在 `docs/projects/{YYYYMMDD}-{project-name}/` 下创建项目目录（日期为项目启动日）

**验证要求：**
- ✅ 单元测试
- ✅ 集成测试
- ✅ 端到端测试（至少一条完整链路）

**示例：**
- runtime-service 契约变更
- platform-api 新增接口
- 数据库表结构调整
- 跨服务功能开发

---

### 治理改动
**范围：** 影响架构、安全、生产环境、数据迁移

**流程（AI 自动执行到"批准"这一步，评审必须由人完成）：**
```
plan-project → 方案评审（人工） → 批准 → 实施 → 全面验证 → verify-change
```

**文档：** `docs/projects/{YYYYMMDD}-{project-name}/` 完整项目文档 + 评审记录

**验证要求：**
- ✅ 单元测试
- ✅ 集成测试
- ✅ 端到端测试（所有关键链路）
- ✅ 性能测试（如适用）
- ✅ 安全测试（如适用）
- ✅ 回滚方案验证

**示例：**
- 架构重构
- 数据库迁移
- 安全加固
- 生产发布流程
- 鉴权系统改造

## 服务边界

当前仓库包含 4 个核心服务：

### platform-web
**职责：** 正式平台前端、管理页面、平台聊天入口

**标准文档：**
- `apps/platform-web/docs/frontend-development-playbook.md`
- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-web/docs/frontend-visual-baseline-standard.md`

### platform-api
**职责：** 鉴权、项目治理、审计、catalog、运行时网关

**标准文档：**
- `apps/platform-api/docs/handbook/*.md`
- `apps/platform-api/docs/standards/*.md`

### runtime-service
**职责：** graph 注册、模型参数解析、工具装配、MCP、智能体执行

**标准文档：**
- `apps/runtime-service/docs/standards/*.md`
- `apps/runtime-service/tests/*.py`（可执行契约）

### interaction-data-service
**职责：** 结果域落库与查询

**标准文档：**
- `apps/interaction-data-service/docs/test-case-service-api-design.md`
- `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md`

## 主要链路

```
platform-web → platform-api → runtime-service → interaction-data-service
```

## 开发流程

以下流程都是 AI 自行判断级别后自动执行的，用户不需要手动触发每一步；用户只需要提出需求，AI 在过程中该记录、该验证的地方自己调用对应 Skill。

### 场景0：纯讨论/探索性规划

用户问"这个方案是否可行"、"要不要这样设计"、"帮我分析一下 xxx"这类问题时，不生成任何文档，不调用任何 Skill，直接对话给出分析和结论。只有当讨论收敛到"确定要做"，才转入下面的分级流程；此时才可能触发 `plan-project`。

### 场景1：单项目改动

```bash
# 1. 直接实现
# 编辑代码...

# 2. 单元测试
pytest apps/xxx/tests/

# 3.（仅当改动新增/改变了一个功能时）留痕
#   apps/{app}/docs/changes/{YYYYMMDD}-{slug}.md，同步更新 docs/FEATURES.md 对应行

# 4. 提交
git commit -m "fix: 修复 xxx 问题"
```

不触发任何 Skill；是否需要 `changes/` 记录看改动是否改变了"这个服务有哪些功能"这个答案（纯 bug fix/重构不需要）。

### 场景2：链路改动

```text
1. AI 判断为链路改动，自动调用 plan-project
   在 docs/projects/{YYYYMMDD}-{项目名}/ 下创建 README.md / plan.md / tasks.md / verification.md

2. AI 实现功能
   调用 implement-feature，记录改动到 implementation/

3. AI 验证
   调用 verify-change，执行测试并记录到 verification.md（含四态判定）

4. 提交
   git commit -m "refactor(runtime): 重构数据建模

   详见 docs/projects/20260908-runtime-modeling-refactor/"
```

### 场景3：治理改动

```text
1. AI 判断为治理改动，自动调用 plan-project 生成完整项目文档

2. 方案评审（这一步必须由人完成，AI 不能自己批准自己的方案）
   团队评审 plan.md，批准后在 README.md 记录评审结果

3. 分阶段实施
   Phase 1... Phase 2...（AI 按 implement-feature 记录每阶段）

4. 全面验证
   调用 verify-change，执行所有级别的测试

5. 生产部署（如适用）
   按部署流程执行

6. 归档
# 项目完成后精简文档，保留关键决策
```

## archive/ 的定义

`archive/` 只存放**已被取代、已被否决、不再是事实来源**的内容。

判断标准：这份文档现在还会被拿来对照检查代码、指导实现，还是决策吗？
- 会 → 不进 `archive/`，哪怕对应的开发阶段已经跑完（比如某阶段的设计文档，只要代码仍需要按它来验收，就还是有效事实源）
- 不会 → 进 `archive/`（比如被新方案替换的旧设计、废弃的旧架构说明、过时的排期计划）

反例：不要因为"这个阶段做完了"就把设计文档丢进 `archive/`——阶段完成不等于文档作废，完成状态应该写在项目文档（`docs/projects/{YYYYMMDD}-{项目名}/README.md` 或 `tasks.md`）里，不要靠挪目录来表达。

## 项目进度标注（替代复杂的 archive 流程）

不需要单独的归档审批流程。项目进度直接在项目文档里如实标注：

- 在 `tasks.md` 的任务前用 `[x]`/`[ ]` 标注完成状态
- 在 `README.md` 的"状态"字段写清楚：规划中 / 进行中 / 已完成 / 部分完成（并说明哪部分未完成）
- 未完成或明确推迟的部分，直接在文档里写清楚原因（阻塞、后置、超出本阶段范围），不要略过不提
- 项目全部完成后，文档保留在 `docs/projects/` 下即可，不强制搬到 `archive/`；只有当项目被后续方案整体取代、文档不再指导任何当前实现时才移入 `archive/`

## 文档组织

改动留痕分三个桶，按"改动影响范围"选择落地位置，不要混放：

| 改动类型 | 落地位置 |
|---|---|
| 单服务内改动（需要留痕的） | `apps/{app}/docs/changes/{YYYYMMDD}-{slug}.md` |
| 跨服务链路/治理改动 | `docs/projects/{YYYYMMDD}-{project-name}/` |
| 不属于任何 app 的仓库级/工具链改动（脚本、CI、根级配置、`AGENTS.md` 本身） | `docs/changes/{YYYYMMDD}-{slug}.md` |

`docs/FEATURES.md` 是全仓库"功能现状总览"，按服务/模块分组，一个功能一行（功能、状态、关联文档链接）。上面任何一个桶落一笔新记录时，同步更新这里对应的一行；不需要每次改动都重写整份文档。

```
docs/
├── README.md                   # 文档导航
├── FEATURES.md                 # 功能现状总览（全仓库，按服务分组）
├── changes/                    # 仓库级/工具链级单项目改动记录
│   └── {YYYYMMDD}-{slug}.md
├── quickstart/                 # 快速开始（新人必读）
│   ├── architecture.md
│   ├── local-dev.md
│   └── deployment.md
├── guides/                     # 开发指南
│   ├── development-workflow.md
│   ├── coding-standards.md
│   └── configuration.md
├── projects/                   # 项目文档（链路/治理改动），两档模板，见下
│   └── {YYYYMMDD}-{project-name}/
├── decisions/                  # 仓库级/跨服务技术决策（ADR）
└── archive/                    # 归档文档
```

`docs/projects/{YYYYMMDD}-{project-name}/` 内部有两档模板，由 `plan-project` 按规模自动选择（判断标准和模板细节见该 Skill）：

- **标准模板**（默认）：`README.md` / `plan.md` / `tasks.md` / `verification.md` / `implementation/`
- **多专题模板**（大型治理改动，或方案自然拆成 3 个以上独立子专题）：`README.md`（导航+总体状态）+ `01-{子专题}.md`/`02-{子专题}.md`/...（每篇自带目标/方案/任务/验证/状态）+ `implementation/`，不再维护全局 `plan.md`/`tasks.md`/`verification.md`

### app 级 `docs/` 约定

每个 `apps/{app}/docs/` 建议对齐这套分类（`platform-api` 已经自发长成这样）：

- `README.md` —— 入口导航
- `standards/` 或 `handbook/` —— 当前生效的架构/规范/playbook，活文档，改了直接改这里，不留旧版本
- `decisions/` —— 该服务内部的 ADR，记录"为什么选 A 不选 B"，一次一份，写完不再改
- `changes/` —— 单服务改动的轻量记录（见上表），一次改动一份，日期前缀，内容就是背景+改了什么+涉及文件，不套用项目文档模板
- `archive/` —— 被取代、不再指导实现的旧文档

单项目改动不需要把"需求"和"变更记录"拆成两份文件——一份 `changes/{日期}-{slug}.md` 开头写背景/需求，后面写改了什么即可。

## 验证标准

### 单项目改动
- ✅ 单元测试通过
- ✅ 代码质量检查通过（lint、类型检查）

### 链路改动
- ✅ 单元测试通过
- ✅ 集成测试通过
- ✅ 端到端测试通过（至少一条完整链路）

### 治理改动
- ✅ 单元测试通过
- ✅ 集成测试通过
- ✅ 端到端测试通过（所有关键链路）
- ✅ 性能测试通过（如适用）
- ✅ 安全测试通过（如适用）
- ✅ 回滚方案验证（如适用）

## LangChain 生态系统文档

对于 LangGraph、LangChain、DeepAgents 的 API 使用、示例、错误、迁移或最佳实践问题，
先查询 `langchain-docs` 和 `langchain-reference` MCP，再提出实现代码。

## 最佳实践

1. **改动前先判断级别**
   - AI 自行按「改动分级」标准判断，不等用户下命令
   - 判断结果有歧义时先问，不要自己拍板往轻处理

2. **文档写清楚**
   - 文件路径要完整
   - 函数名要准确
   - 改动理由要说明

3. **验证要真实**
   - 不编造测试结果
   - 发现问题如实记录
   - 保留验证证据

4. **定期清理**
   - 完成的项目在 `README.md`/`tasks.md` 里如实标注进度，不强制搬目录
   - 只有被取代、不再是事实源的内容才移入 `archive/`（见"archive/ 的定义"）
   - 保持文档数量可控

## 注意事项

- 判断级别看影响范围，不看代码量
- 治理改动必须有评审批准
- 验证通过才能合并代码
- 文档是给其他人看的，要清晰易懂
