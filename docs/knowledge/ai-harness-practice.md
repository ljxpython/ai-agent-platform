# AI Harness 实战：在 ai-agent-platform 中的六层落地

> 本文是[《AI Harness：让 AI 在你的项目里真正可靠工作》](ai-harness-theory.md)的配套实战篇。
> 理论篇讲了什么是六层 Harness、为什么这么设计；这篇讲我们在真实项目里是怎么做的、踩了哪些坑、前后对比是什么样的。

---

## 一、项目背景

**ai-agent-platform** 是一个 AI 智能体运行平台，包含四个核心服务：

```
platform-web          # 平台前端、管理页面
platform-api          # 鉴权、项目治理、审计、catalog
runtime-service       # graph 注册、工具装配、智能体执行
interaction-data-service  # 结果落库与查询
```

主链路：
```
platform-web → platform-api → runtime-service → interaction-data-service
```

这个项目有几个特点，让 Harness 设计变得尤为重要：

- **多服务并行开发**：四个服务之间有接口契约依赖，跨服务改动非常频繁
- **AI 深度参与**：开发过程中 AI 参与代码编写、文档维护、方案设计
- **改动影响范围难判断**：一个看起来很小的改动，有时会牵连多个服务的契约

没有 Harness 之前，我们的痛点是：AI 不知道改动会不会影响其他服务、每次新会话都要重新介绍项目背景、改完了不知道有没有按规范走、同样的错误反复出现。

---

## 二、我们用的 AI 工具

本项目使用 **Antigravity**（Google DeepMind 的 AI 编程助手）。

Antigravity 的 Harness 载体：

| 层 | 载体 | 位置 |
|---|---|---|
| 全局约束 | 用户全局规则 | `~/.gemini/config/` |
| 项目约束 | `AGENTS.md` | 项目根目录（自动加载） |
| 流程 SOP | `SKILL.md` | `.agents/skills/{skill-name}/` |
| MCP 工具 | MCP 配置 | `.agents/mcp_config.json` |

如果你用的是其他工具（Cursor、Claude Code、Copilot Workspace），载体名字不同，但设计思路完全一样：
- 约束层 → `CURSOR_RULES` / `CLAUDE.md` / `Copilot Instructions`
- 流程层 → 自定义指令文件 / workflows
- 记忆层 → 同样是文件系统

---

## 三、约束层：AGENTS.md 的设计

### 理论要求

规定改动边界、流程触发条件、不可逾越的禁令。

### 我们的实现

`AGENTS.md` 是整个 Harness 的核心入口文件，每次对话自动全量加载。

**最重要的设计决策：改动三级分类。**

我们用"影响范围"而不是"代码量"来分级：

```
单项目改动  →  单服务内部，不影响对外契约
              流程：直接实现 → 单测 → Commit

链路改动    →  跨服务，影响契约或数据模型
              流程：plan-project → 实现 → 链路测试 → verify-change

治理改动    →  架构/安全/生产/数据迁移
              流程：plan-project → 人工评审批准 → 实施 → 全面验证
```

**反模式列表（前后对比）：**

改之前，规则都是正向描述："AI 应该在开始实现前判断级别……"

改之后，核心禁令改为负向：

```markdown
## 严禁行为（已踩坑）
- ❌ 不得在未建 tasks.md 的情况下开始写跨服务改动的代码
- ❌ 不得把 Phase 验证记录写进 Final 验证区块，两者必须独立
- ❌ 不得将多专题模板的旧文档原地保留——升级必须加废弃标注
- ❌ 不得自己批准治理改动，人工评审是必须的
- ❌ 不得编造测试结果，验证记录必须是真实执行的产物
- ❌ 不得用 implementation/ 来判断项目进度，进度只看 tasks.md
```

效果立竿见影：禁令描述的是"不合法状态"，AI 的遵从率明显高于正向建议。

### 踩过的坑

**坑：AGENTS.md 越写越长，变成散文。**

初版 AGENTS.md 是一篇流水账，什么都往里写，结果 AI 解析时漏掉关键规则。

优化方法：结构化分节，每节独立回答一个问题，用列表和表格替代段落。规则越结构化，AI 遵从率越高。

---

## 四、流程层：三个 Skill 的设计

### 理论要求

把常见工作场景封装成 AI 按需读取的 SOP 手册。

### 我们的实现

三个本地 Skill，对应开发全流程：

**`plan-project`**：判断为链路/治理改动时触发，创建项目文档结构

```
docs/projects/{YYYYMMDD}-{项目名}/
├── README.md       # 项目概览（含模板类型字段）
├── plan.md         # 整体方案
├── tasks.md        # 任务拆分（四段式）
├── verification.md # 验证计划和记录
└── implementation/ # 实现细节（细节层，可选）
```

**`implement-feature`**：实现过程中记录改动，核心输出是 Task Completion Card

**`verify-change`**：两阶段验证（Phase 验证 + Final 验证）+ 状态一致性检查

### 最重要的设计决策：tasks.md 的四段式结构

旧版 tasks.md 的任务格式：

```markdown
### Task 1.1: 重构数据模型
- **文件：** src/models.py
- **改动：** 重构为 dataclass
- **状态：** 待开始
```

问题：看完不知道改完结果应该是什么，也不知道怎么验证。

新版四段式：

```markdown
### Task 1.1: 重构数据模型
- **改动内容：** 将 RuntimeConfig 重构为 dataclass 结构
- **代码位置：** `src/models.py` → `RuntimeConfig`
- **预期结果：** 支持新的 model_config 格式，向后兼容 v1
- **验证项：** `pytest tests/test_runtime_config.py` → 全部通过
- **状态：** `[ ]` 待开始
```

四个字段缺一不可：没有"预期结果"，不知道改完应该是什么样；没有"验证项"，任务完没完全靠感觉。

### 踩过的坑

**坑1：AGENTS.md 和 Skill 内容严重重复。**

比如"改动分级规则"同时出现在 AGENTS.md 和 `plan-project/SKILL.md` 里，两边稍有不同，产生矛盾。

现在的分工原则：AGENTS.md 只说"什么情况走什么流程"，Skill 只说"这个流程具体怎么走"。不许交叉。

**坑2：模板升级时新旧文档并存，不知道看哪个。**

大型项目会从"标准模板"（单一 tasks.md）升级为"多专题模板"（多个子专题文档）。升级时如果只建新文档不处理旧文档，读者打开项目目录一头雾水。

现在升级是原子操作，四步走：
1. 旧文档顶部加废弃标注
2. 内容迁移到新子专题文档
3. README.md 的"阅读顺序"列表成为唯一纲领
4. README.md 的"模板类型"字段更新为"多专题模板"

**坑3：验证没有分阶段，每改一小块就全量回归。**

改了一个函数，跑全量测试等了 10 分钟，效率极差。

现在分两阶段：
- **Phase 验证**：每个 Task 完成后，只跑这个 Task 直接相关的最小测试集
- **Final 验证**：所有 Task 完成后，全量回归 + 集成 + E2E

---

## 五、工具层：AI 的能力边界

### 我们的实现

**内置工具（Antigravity 提供）：**

```
读层：view_file / grep_search / find_by_name / list_dir
写层：write_to_file / replace_file_content
执行层：run_command（同步/后台）
扩展层：invoke_subagent / call_mcp_tool
```

**MCP 工具扩展：**

项目配置了两个 MCP 服务：
- `langchain-docs`：查询 LangGraph / LangChain 文档
- `langchain-reference`：查询 API 引用

在 AGENTS.md 里有对应规则："对于 LangGraph、LangChain 的 API 使用、示例问题，先查询 MCP，再提出实现代码"——这避免了 AI 凭记忆写出过时或错误的 LangChain API。

**危险操作守卫：**

在全局用户规则里定义了高风险操作列表（删除文件、git push、数据库变更等），触发前必须走确认流程：

```
⚠️ 检测到危险操作！
操作类型：[具体操作]
影响范围：[详细说明]
你真要这么干？[需要明确确认]
```

---

## 六、记忆层：文件系统就是记忆

### 理论要求

补偿 AI 没有跨会话持久记忆的缺陷，让 AI 每次新会话能快速同步项目现状。

### 我们的实现

**三类项目记忆文件：**

```
docs/FEATURES.md           # 语义记忆：全仓库功能现状总览
docs/projects/{date}-{}/   # 情节记忆：项目历史和决策背景
.agents/skills/            # 程序记忆：遇到 X 场景该怎么做
```

**`docs/CONTEXT.md`：会话同步快照（核心）**

```markdown
# 项目当前状态 - AI 上下文

## 最后更新
2026-09-21 | Harness 优化完成

## 各服务状态
| 服务 | 最后改动 | 关键约束 |
|---|---|---|
| runtime-service | 2026-09-18 | 新 API 需向后兼容 v1 |
| platform-api | 2026-09-10 | 鉴权逻辑不得绕过 |

## 近期关键决策
- 2026-09-21: 引入两阶段验证机制
```

**维护规则：只保留"当前有效"的信息。** 过期内容删掉，不要堆历史。这个文件应该越短越好——它是给 AI 读的，不是给人看的。

### 加这层之前 vs 之后

**之前：** 每次新会话开头花 5-10 分钟向 AI 介绍"我们项目有四个服务，主链路是这样的，最近在做这个……"

**之后：** AI 读 `CONTEXT.md`，30 秒同步完毕，直接进入正题。

---

## 七、可观测层：让合规性看得见

### 我们的实现

**Task Completion Card（每个任务完成时）：**

```markdown
### Task 1.1: 重构 RuntimeConfig ✅ 2026-09-21
- **改动内容：** 重构为 dataclass 结构
- **代码位置：** `src/models.py` → `RuntimeConfig`
- **预期结果：** 支持新格式，向后兼容 v1
- **验证项：** `pytest tests/test_runtime_config.py` → ✅ 12/12 通过
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（此任务未涉及服务状态变化，跳过）
```

**硬规则：没有完成卡 = 任务没完成。**

**状态一致性检查（项目收尾前置步骤）：**

```
对照四处，状态必须一致：
- README.md 的"状态"字段
- tasks.md 的进度追踪
- verification.md 的 Phase 验证记录条数 == 已完成 Task 数
- CONTEXT.md 的活跃项目状态行
```

**人工 5 分钟抽查法：**
1. tasks.md 的合规 checklist 全打勾了吗
2. verification.md 的 Phase 验证记录数 == 已完成 Task 数
3. CONTEXT.md 在改动后更新了吗

---

## 八、反馈层：错误沉淀为经验

### 我们的实现

**三层经验库：**

```
Tier 1  AGENTS.md 严禁行为    ← 始终加载，≤10 条
Tier 2  docs/lessons/{}.md   ← 按需加载，每条 ≤4 行
Tier 3  git log + ADR        ← 永不主动加载，人工深挖时查阅
```

**当前 ai-workflow.md 里的三条真实教训：**

```markdown
## [坑] 模板升级时旧文档未加废弃标注
- **场景：** 标准模板升级为多专题模板时
- **错误：** 只建了新文档，旧文档原地保留，不知道该看哪个
- **正确：** 旧文档加废弃标注 → 内容迁移 → README 成为唯一纲领
- **日期：** 2026-09-21

## [坑] implementation/ 被误用为进度来源
- **场景：** 链路/治理改动实现过程中
- **错误：** 把查 implementation/ 当了解进度的方式，tasks.md 不更新
- **正确：** tasks.md 是进度唯一来源，implementation/ 只是细节档案
- **日期：** 2026-09-21

## [坑] Skill 用外部路径作为参考实例
- **场景：** SKILL.md 里写 "参考实例: apps/xxx/..."
- **错误：** 外部读者和新会话的 AI 不知道那个目录是什么
- **正确：** 把判断标准直接写进 SKILL.md，不依赖外部路径
- **日期：** 2026-09-21
```

**新坑沉淀流程：**

```
AI 犯错 → 你纠正 → 蒸馏成 ≤4 行
    ↓
任何场景都会犯 → Tier1（AGENTS.md，≤10条上限）
特定领域才会犯 → Tier2（docs/lessons/{domain}.md）
    ↓
更新 lessons/index.md 条数
```

---

## 九、三轮迭代过程

这套 Harness 不是一次设计好的，被真实痛点驱动，迭代了三轮。

**第一轮：只有基础约束**

`AGENTS.md` 里有项目简介、服务说明、一些模糊的规范要求。

痛点：AI 行为不一致，文档该建不建，格式五花八门。

**第二轮：加了三个 Skill**

建立了 plan-project / implement-feature / verify-change 三段式流程。

暴露的新痛点：

| 痛点 | 具体表现 |
|---|---|
| AGENTS.md 和 Skill 内容重复 | 两边稍有不同时产生矛盾，AI 行为混乱 |
| tasks.md 粒度太粗 | 不知道改没改完，不知道结果该是什么 |
| 模板升级混乱 | 新旧文档并存，不知道以哪个为准 |
| 没有项目状态感知 | 每次新会话重新介绍项目背景 |
| 无法验证 AI 合规性 | 只能相信 AI 说"做完了" |
| 同样的错反复犯 | 没有经验沉淀机制 |
| 每改一小块就全量测试 | 效率极差 |

**第三轮：补全记忆/可观测/反馈三层**

| 痛点 | 解法 |
|---|---|
| 每次重建上下文 | CONTEXT.md + 会话初始化规则 |
| 模板升级混乱 | 升级原子操作规范 + 模板类型字段 |
| tasks.md 看不出完成度 | 四段式结构 + Task Completion Card |
| 不知道 AI 是否合规 | 合规 checklist + 状态一致性检查 |
| 同样的错反复犯 | 三层经验库 + 蒸馏沉淀流程 |
| 全量回归效率差 | Phase 验证 + Final 验证两阶段 |

---

## 十、当前局限性（诚实说）

**局限1：Skill 是被动触发的，没有自动 hook。**

AI 需要主动判断"现在该读这个 Skill 了"——如果判断错了，Skill 就被跳过了。应对：触发条件写得尽量清晰，AGENTS.md 里加兜底禁令。

**局限2：记忆层还是纯文件系统，没有语义检索。**

历史决策靠 `docs/projects/` 和 `docs/decisions/` 存放，但 AI 不会主动语义检索历史——需要人主动指定去看哪个文档。

**局限3：可观测层还依赖 AI 的自我汇报。**

合规 checklist 是 AI 自己填的，不是系统自动生成的。只能靠人工抽查来发现问题。

**局限4：领域经验还很薄。**

`docs/lessons/` 目前只有 `ai-workflow.md` 的 3 条，服务级别的经验需要在实际开发中逐步积累。

---

## 附录：当前 Harness 文件结构

```
项目根目录/
├── AGENTS.md                          # 约束层：项目规则入口
├── .agents/
│   └── skills/
│       ├── plan-project/SKILL.md      # 流程层：规划 SOP
│       ├── implement-feature/SKILL.md # 流程层：实现 SOP
│       └── verify-change/SKILL.md     # 流程层：验证 SOP
└── docs/
    ├── CONTEXT.md                     # 记忆层：AI 会话快照
    ├── FEATURES.md                    # 记忆层：功能现状总览
    ├── lessons/
    │   ├── index.md                   # 反馈层：经验索引
    │   └── ai-workflow.md             # 反馈层：AI 工作流经验
    ├── projects/                      # 记忆层：项目历史文档
    ├── changes/                       # 记忆层：改动留痕记录
    └── knowledge/
        ├── ai-harness-theory.md       # 理论篇
        └── ai-harness-practice.md    # 实战篇（本文）
```
