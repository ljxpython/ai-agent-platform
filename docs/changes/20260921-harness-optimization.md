# 20260921 - Harness 优化：文档先行、任务结构、验证分阶段

## 背景

与用户共同评审 AGENTS.md 和三个本地 Skill（plan-project、implement-feature、verify-change）后，识别出以下问题并进行优化：
- 讨论结论易丢失，没有"落笔"动作
- tasks.md 任务结构粗糙，无法独立回答"改了什么、结果是什么、怎么验"
- 模板升级时新旧文档并存，读者不知道以哪个为纲领
- implementation/ 和 tasks.md 进度职责混乱
- verify-change 无分阶段验证，每改一小块就全量回归
- plan-project 指向外部参考路径，外部读者无法理解

## 改动内容

### AGENTS.md
- 场景0：新增"讨论有结论时主动落笔"机制，AI 在讨论达成明确结论时主动提议记录，不强制

### plan-project/SKILL.md
- 删除第43行外部路径引用（`apps/runtime-service/docs/knowledge/...`）
- 新增显式"独立子专题判断标准"（耦合性判断规则）
- 新增"标准模板 → 多专题模板升级操作规范"（4步原子操作）
- README.md 模板新增强制字段：`模板类型`
- tasks.md 模板改为四段式：改动内容 / 代码位置 / 预期结果 / 验证项 / 状态（含完成摘要行）

### implement-feature/SKILL.md
- 新增"两层分工原则"：tasks.md（进度层）vs implementation/（细节层）
- 步骤4（更新任务状态）明确要求在 tasks.md 留完成摘要行（含日期 + implementation 链接）
- 明确 implementation/ 是可选的细节档案，不是进度来源

### verify-change/SKILL.md
- 修复错别字：`## 注意事这里的。项` → `## 注意事项`
- 新增"两阶段验证原则"：Phase 验证（Task 完成后跑最小测试集）vs Final 验证（全部完成后全量回归）
- 验证记录模板拆为两个区块：`## Phase 验证记录` + `## Final 验证记录`

## 涉及文件
- `AGENTS.md`
- `.agents/skills/plan-project/SKILL.md`
- `.agents/skills/implement-feature/SKILL.md`
- `.agents/skills/verify-change/SKILL.md`

---

## Phase 2 补充：记忆层 / 可观测层 / 反馈层

### 背景

在完成 Phase 1 后，进一步讨论了 AI Harness 完整性，识别出三个缺失的层并设计补全：
- **记忆层**：AI 跨会话无项目现状感知
- **可观测层**：无法验证 AI 是否按流程执行
- **反馈层**：错误无法沉淀为经验，AI 会反复踩同一个坑

### 改动内容

#### AGENTS.md（新增3个章节）
- `## 会话初始化`：新会话开始前主动读 `docs/CONTEXT.md`，改完后更新
- `## 经验库读取规则`：按需读取 `docs/lessons/{domain}.md`，不全量加载
- `## 严禁行为（已踩坑）`：Tier1 经验始终加载，≤10 条普适性反模式

#### implement-feature/SKILL.md
- 步骤4 升级为 **Task Completion Card** 格式，含合规 checklist（代码/验证/状态/CONTEXT 四项）
- 合规 checklist 前三项必须勾选，CONTEXT.md 按需更新

#### verify-change/SKILL.md
- Final 验证前新增 **状态一致性检查**（前置步骤，不通过不得继续）：README/tasks/verification/CONTEXT 四处状态必须一致

### 新增文件
- `docs/CONTEXT.md`：项目状态快照，AI 每次会话同步入口
- `docs/lessons/index.md`：经验库索引
- `docs/lessons/ai-workflow.md`：AI 工作流领域经验（3条，来自今日 harness 优化）
