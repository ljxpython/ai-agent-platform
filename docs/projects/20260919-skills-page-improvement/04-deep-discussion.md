# 子专题04：深度问题讨论记录

> 实施更新：后端已完成，当前状态以 [README](README.md)、实际契约以 [07](07-frontend-handoff.md)、验证以 [08第9节](08-backend-development-and-validation.md#9-2026-09-19-实际验证记录) 为准。本文保留当时讨论与决策过程；历史“规划中/暂未实施/暂未决定”不作为当前实施状态。

> **Q1—Q7 补充决策：** 本文是历史核对记录，不再作为待定事项清单。用户已确认上传、启停/删除、公共全可见、扫描/工具方案、恢复原快照、不做存量技能兼容；技能归 runtime-service，不向 GraphHarbor 加业务能力。最新细节与官方来源见 [08](08-backend-development-and-validation.md)。

> **最新状态：** 用户已逐项批准 06 的 A—E；本篇保留核对和早期讨论，不再表示 A—E 尚未决定。具体开发与剩余未决事项见 [08](08-backend-development-and-validation.md)，前端只交接、不实施。

> 本文记录讨论、事实核对和未决事项。下方“本轮核对”是当前讨论依据；后面的 Q1—Q6 保留早期讨论背景，存在过度概括处，以本轮核对为准。

## 本轮核对与决策（2026-09-19）

### 1. 用户原意与状态

- **已决定：** 本次只规划讨论，所有已定与未定事项写入已有项目文档，不编写实现代码、不执行迁移。
- **已决定（条件性方向）：** 用户希望去掉参考项目没有的自定义版本治理，包括“治理上下文”UI。核对结果支持讨论去掉本项目额外的强制发布流程，不能解释为删除所有技能审查或自定义技能。
- **暂未决定：** 具体删除范围、保留能力、替代交互、接口契约、数据库工具和目录、旧数据与历史会话处理、是否独立立项及实施顺序。

### 2. 两份 SQL 的真实职责

| 文件/表 | 当前职责 | 与技能简化的关系 |
|---|---|---|
| `001_external_tasks.sql` / `dear_external_tasks` | 外部副作用请求的意图、幂等键、租约、结果与未知状态；媒体及部署工具使用 | 不是技能版本治理表，不因删除技能治理而自动删除 |
| `002_governance.sql` / `dear_memory` | tenant + project + user 下的记忆 JSON 文档 | 独立于技能发布，不能随技能表一起删 |
| 同文件 / `dear_skill_versions` | 包解析后的文本文件与版本状态 JSON；不是原始 ZIP 二进制存储 | 保留当前技能内容或换存储方式暂未决定 |
| 同文件 / `dear_skill_bindings` | scope + thread 的首次技能版本绑定 | 是否保留冻结、如何处理旧绑定暂未决定 |

`deadline_at` 的默认值是 24 小时，`claim()` 用它限制领取；不能据此声称存在“24 小时后自动改为 unknown”的后台任务。当前 `get()/claim()` 会处理已领取且租约过期的意图。也不能把这张表概括为已实现通用外部回调平台。

建表入口分别为 `external_task_storage.py::initialize()` 和 `governance_storage.py` 的模块入口。`scripts/local-stack.sh::migrate()` 已调用 `graphharbor migrate upgrade`，但没有接入这两个入口；消息收件箱还有独立 `messaging/__main__.py` 与 `MessageInbox.initialize()`。问题是服务自有表迁移分散，不能说整个 Runtime 没有迁移机制。

### 3. 技能到底按什么范围隔离

**已核实事实：** `SkillStorage.list/create/activate` 使用 `(tenant_id, project_id, user_id)`；`freeze` 额外使用 `thread_id`。同一用户同一项目的不同会话管理的是同一份版本库，不是各自一套技能。

`platform-api` 的 `RuntimeGatewayService.dear_governance()` 校验会话访问与 Dear Agent 类型并签发委托信息；Runtime 的 `authorize()` 校验委托 scope，返回 principal 的三维身份。不是简单从 thread metadata 提取用户然后查表。

冻结发生在 Agent 装配调用 `SkillStorage.freeze()` 时。新激活版本不替换旧绑定；但撤销旧版本会导致使用它的会话报 `thread_skill_revoked`，所以“历史会话永远不受撤销影响”是错误说法。

**暂未决定：** 后续继续用户私有技能还是增加项目共享；现有隔离事实不能当成新产品决策。建议本次简化保留现有三维隔离，不顺带扩大可见性。

### 4. 导入 ZIP：只能确认代码路径，不能宣布本地可用

已核对上传路径：页面 base64 编码 → platform-api 委托 → Runtime `change_skills()` → `inspect_package()` → `SkillStorage.create()`。本轮没有读取 `.env`、连接数据库或真实上传，因此此前“本地配置正确”“最可能是没建表”均不是本轮验证结论。

当前包要求：根 `SKILL.md`；YAML `name/description`；slug 格式；压缩包与累计解压内容各不超过 1 MiB；单文件不超过 256 KiB；ZIP 条目不超过 100；拒绝危险路径、软链接、隐藏文件、加密条目及不支持的扩展名，内容须为 UTF-8。扫描警告会阻止激活，候选仍可创建。

待排查项包括开关、连接、表是否存在、权限、包格式及无会话时按钮不可用。`dear_governance_disabled` 由功能开关检查产生，缺表通常是数据库异常，二者不要混写。是否安排真实排查 **暂未决定**。

### 5. DeerFlow 到底有没有这套治理

核对的是用户指定的本地源码，不推断其他版本。

| 能力 | DeerFlow 实际情况 | 本项目实际情况 |
|---|---|---|
| 自定义技能管理 | 上传安装、读取、编辑、删除、导出、历史、回滚 | 上传候选、列表、激活、撤销；无同等编辑历史 UI |
| 安全扫描 | 安装/编辑/回滚链路调用静态与 AI 扫描，行为受配置控制 | 包格式检查及正则 warnings |
| `review_skill_package` | **有**，只读包分析、报告与 CLI；审查不安装、不激活、不执行目标脚本 | **有**，依据已有 warnings 记录 `static_only` 审查，并返回受限内容 |
| 评估/实验能力 | review 可分析 eval 定义；skill-creator 承担实验，不等于没有任何评估能力 | `evaluate_skill_candidate` 执行 2–6 个纯文本模型用例 |
| 强制候选→审查→文本评估→发布门槛 | 检查的安装、管理路由与技能源码中未发现与本项目相同流程 | `activate()` 强制检查 warnings、review、evaluation 与 digest |
| 按会话永久冻结版本库快照 | 未发现与 `dear_skill_bindings` 等价的实现；有上下文/缓存机制，不能混同 | `SkillStorage.freeze()` 持久绑定 |
| 管理入口要求先选会话 | 技能 REST 路由按当前用户访问，不带 thread 参数 | 当前 API 委托和 UI 依赖会话 |
| 隔离 | 有 `get_effective_user_id()` 和用户技能目录 | tenant + project + user 三维 |

因此，之前“DeerFlow 没有审查”“双方都有同样的对话评估流程”“DeerFlow 仅单用户”“我们的会话选择因多租户而必要”的说法都不准确。

本项目的文本评估只是模型输出包含 expected、不包含 forbidden 的检查；没有执行包内脚本、浏览器或真实工具，不应描述为完整沙箱验收。

### 6. 去掉什么：建议及未决边界

**建议（暂未决定具体实施）：** 把页面从“自定义版本治理”改为普通“自定义技能管理”，取消用户必须先选会话、再通过对话完成评估才能使用的流程。保留导入、查看和清晰的可用状态；编辑、删除、开关、历史回滚是否本期加入，各自另行决定。

必须分别讨论：

1. **页面与流程：** 去掉整个自定义标签还是保留简化管理页；不能只藏按钮却仍让后端要求用户完成不可见的评估。
2. **后端：** 候选状态机、审查/评估工具、`publish_skill`、HTTP action、Agent 装配中哪些退役；是否将扫描保留为导入时检查。
3. **会话生效规则：** 保留冻结，还是每次新运行读取当前技能；正在运行与历史续聊各自怎么办。
4. **存储与历史：** 旧 candidate/active/inactive/revoked 和绑定如何处理；不自动删表、不丢记忆和外部任务数据。
5. **鉴权：** 页面若不再选会话，应让管理接口直接验证当前项目与用户权限并签发对应委托，不能靠偷偷挑“第一个会话”掩盖依赖，也不能直接移除 thread 检查后裸露接口。

以上均 **暂未决定**。减少发布步骤不意味着取消上传边界校验、租户隔离或必要安全扫描。

### 7. 代码证据与后续验收

本仓库证据（路径相对仓库根）：

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/{skill_governance.py,governance_storage.py,external_task_storage.py,agent.py,tools/skills.py,migrations/}`。
- `apps/runtime-service/src/runtime_service/http/dear_governance.py`。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py::dear_governance()`。
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.vue`、`apps/platform-web/src/services/dear-agent/skills.service.ts`。
- `scripts/local-stack.sh`、`apps/runtime-service/src/runtime_service/messaging/{__main__.py,inbox.py}`。

参考项目证据（相对 `/Users/lijiaxin/PyCharmMiscProject/research/deer-flow`）：

- `backend/app/gateway/routers/skills.py`：安装、内容、编辑、历史、回滚和开关路由。
- `backend/packages/harness/deerflow/tools/builtins/review_skill_package_tool.py`：真实存在的只读审查工具。
- `backend/packages/harness/deerflow/skills/{installer.py,security_scanner.py,security_static_scanner.py,review/,storage/user_scoped_skill_storage.py}`。

本轮只做源码核对与文档检查，无功能测试结果。后续方案应覆盖：无会话也能管理（若采用去会话化）、跨用户/项目拒绝访问、危险包拒绝、导入后的生效时机、旧会话行为及存量数据兼容；数据库验证见 05。

## 早期讨论记录（历史背景，冲突处以上文为准）

---

## Q1：migrations 目录里的两个 SQL 文件到底是干嘛的？

### 通俗解释

**简单说：这两个 SQL 文件是"建表脚本"，就是告诉 PostgreSQL 数据库"请帮我创建这几张表"。**

我们的 Dear Agent 功能需要把一些数据存到数据库里，这些表就是用来存这些数据的容器。

---

### 001_external_tasks.sql — 干什么用？

建了一张叫 `dear_external_tasks` 的表。

**这张表记录什么？**  
当 Dear Agent 在对话中需要调用外部服务（比如"帮我生成一张图片"、"帮我生成一个视频"），这类任务不是即时完成的，而是：
1. Agent 先把"我要生成图片"这个任务记下来（写入 `dear_external_tasks`）
2. 等外部服务（图片生成服务）处理完毕后回调
3. 整个过程中用这张表做**幂等控制**（同一个请求只提交一次，防止重复生成）

**关键字段含义：**
```
status: 'intent'(意图已登记) / 'succeeded'(完成) / 'unknown'(状态未知)
idem_key: 幂等键，防止重复提交
deadline_at: 24小时超时，超时自动标记为未知
lease_until: 工人租约，防止多个进程同时处理同一任务
```

---

### 002_governance.sql — 干什么用？

建了三张表，是技能治理体系的核心数据存储：

**`dear_memory`（记忆表）**
- 存储每个用户（tenant+project+user 三维隔离）的 Dear Agent **记忆**
- 就是 Dear Agent 的"长期记忆"，跨会话保留的用户信息/偏好
- 每个 tenant+project+user 只有一行（键值对形式的 JSON）

**`dear_skill_versions`（技能版本表）**
- 存储用户上传的**自定义技能版本**
- 每条记录是一个技能的一个版本，包含完整的压缩包内容（`document` JSONB 字段）
- 记录技能的状态机：`candidate → active / revoked / inactive`

**`dear_skill_bindings`（技能绑定表）**
- 存储每个会话（thread）**首次运行时冻结的技能快照**
- 记录"这个会话当时用了哪个版本的哪些技能"
- 作用：保证历史会话永远用同一套技能，不受后续版本激活/撤销影响

---

### 为什么要手动执行这两个 SQL？

目前没有自动化的迁移框架（如 Alembic）。新环境部署时需要手动执行：
```bash
# 建外部任务表
DATABASE_URI=postgresql://... python -m runtime_service.services.dearflow_agent.external_task_storage

# 建治理三张表（memory + skill_versions + skill_bindings）
DATABASE_URI=postgresql://... python -m runtime_service.services.dearflow_agent.governance_storage
```

本地开发环境目前的 `DATABASE_URI` 是 `postgresql://lijiaxin@127.0.0.1:5432/graphharbor_acceptance`，环境变量 `RUNTIME_DEAR_GOVERNANCE_ENABLED=1` 也已配置（在 `.env` 里）。

---

## Q2：自定义技能是项目维度还是会话维度？

### 结论：**用户维度（tenant + project + user）**，不是会话维度，也不是项目维度

**三张表的主键都是 `(tenant_id, project_id, user_id)`：**

```sql
-- dear_skill_versions 主键
PRIMARY KEY (tenant_id, project_id, user_id, slug, digest)

-- dear_skill_bindings 主键  
PRIMARY KEY (tenant_id, project_id, user_id, thread_id)

-- dear_memory 主键
PRIMARY KEY (tenant_id, project_id, user_id)
```

这意味着：
- **同一个项目，不同用户，技能版本彼此独立**（用户A上传的技能B看不到）
- **同一个用户，不同项目，技能版本也彼此独立**（项目A的技能与项目B完全隔离）
- **会话（thread）只是决定"这个会话冻结了哪些版本"**，不持有自己的技能版本

### 会话（thread）只参与"冻结"

`dear_skill_bindings` 表的作用是：
1. 会话**第一次运行**时，读取当前用户 scope 下所有 `status=active` 的技能版本
2. 把这个快照写入 `dear_skill_bindings(thread_id)`
3. 后续这个会话**永远使用这个快照**，不受之后的版本变更影响

所以：
- 你激活了一个新版本 → 新会话会用新版本，老会话不变
- 你撤销了一个版本 → 绑定了该版本的老会话无法继续运行

### 治理上下文 UI 里的"会话选择"是什么意思？

页面顶部的"治理上下文：[选择会话]"，是让你**指定你想查看哪个会话（thread）下的自定义技能列表**。

实际上 `GET /threads/{thread_id}/dear/skills` 这个接口，`thread_id` 只是用来提取 `scope=(tenant, project, user)`，真正查的是这个用户在这个项目下的全部技能版本——跟具体哪个 thread 没关系。

**所以这个 UI 设计存在歧义**：用户会以为"我在看这个会话的技能"，但实际上不管选哪个会话，看到的都是同一份数据（只要是同一个 user+project）。这是一个值得讨论的设计问题。

---

## Q3：导入候选 ZIP 功能有没有生效？

### 结论：功能代码完整、链路正确，但需要验证数据库表是否已建

**完整链路：**
```
前端：handleUploadCandidate() 
  → fileToBase64(file) 将 ZIP 转成 base64
  → uploadCandidateSkillPackage(projectId, threadId, base64)
    → POST /api/langgraph/threads/{threadId}/dear/skills
      { "action": "candidate", "package_base64": "..." }
    
platform-api：write_dear_governance()
  → service.dear_governance(..., payload={"action":"candidate", ...})
    → upstream.dear_governance(thread_id, "skills", payload=...)

runtime-service：change_skills()
  → base64.b64decode(command.package_base64)
  → SkillStorage().create(scope, raw, source="explicit-management")
    → inspect_package(raw)  ← 解析 ZIP，验证 SKILL.md frontmatter，安全检查
    → INSERT INTO dear_skill_versions ...
```

**前提条件：**
1. `RUNTIME_DEAR_GOVERNANCE_ENABLED=1` ← **本地已配置 ✅**
2. `DATABASE_URI` 指向的 PG 库里，`dear_skill_versions` 表已存在 ← **需要验证，需手动执行过 002_governance.sql**
3. 导入的 ZIP 必须满足格式要求：
   - 根目录有 `SKILL.md`
   - SKILL.md 有 YAML frontmatter（`name` + `description`）
   - `name` 必须是 slug 格式（小写字母+数字+连字符）
   - 总大小 ≤ 1MiB，文件数 ≤ 100
   - 无隐藏文件、无软链接、无跨目录路径

**可能的失败原因：**
- 数据库表未建 → 报 `"dear_governance_disabled"` 或 PG 报错
- ZIP 格式不合规 → 报 `"skill_frontmatter_required"` / `"unsafe_skill_package"` 等
- 缺少 Dear Agent 会话 → `hasThreads` 为 false，按钮 disabled

---

## Q4：自定义版本治理的具体用途是什么？

### 这是一套完整的"技能安全上线流程"，类似软件的 CI/CD

**设计理念**：不能让用户随便上传一个技能包就直接生效（安全风险太高），需要经过审查和评估才能正式启用。

### 完整流程图

```
用户上传 ZIP
    ↓
[候选状态 Candidate]
    ↓ 安全扫描（正则检查：prompt injection / api key 泄露等）
    如果有风险警告 → 直接禁止激活
    ↓
Dear Agent 对话中执行 review_skill_package() 工具
    ↓ 静态代码审查，读取文件内容，记录 review.passed
[代码审查通过 Review: passed=true]
    ↓
Dear Agent 对话中执行 evaluate_skill_candidate() 工具
    ↓ 用 AI 模型在隔离环境跑 2-6 个测试用例（prompt→output 验证）
[动态评估通过 Evaluation: passed=true]
    ↓
用户在治理页面点"启用版本" 或 Dear Agent 执行 publish_skill()
    ↓ 需要 review.passed=true AND evaluation.passed=true AND 无 warnings
[生效中 Active]
    ↓ 此后每个新会话首次运行时冻结当前 active 版本
```

### 用户的自定义技能在哪里管理？

1. **通过对话（推荐）**：在 Dear Agent 的对话工作台里，直接对话告诉 Agent "帮我上传这个技能包"，Agent 会调用 `create_skill_candidate` 工具，然后引导你完成 review → evaluate → publish 的流程

2. **通过治理页面（当前 UI）**：Skills 页面的"自定义版本治理"标签页
   - 上传 ZIP → 进入候选状态
   - 点"文件清单"看文件列表
   - 代码审查 & 动态评估目前只能通过**对话**触发（页面上无对应按钮）
   - 审查评估通过后，页面上的"启用版本"按钮才会激活可点击
   - 撤销（不可逆）直接可以点

### 核心约束

- **激活条件**：必须 `review.passed=true` AND `evaluation.passed=true` AND `warnings=[]`
- **版本冻结**：会话一旦运行过，它的技能版本就冻结了，后续变更不影响它
- **撤销不可逆**：被撤销的版本永远无法重新激活

---

## Q5：对比 DeerFlow，我们还缺哪些 Skills 功能？

### 功能对比表（完整版）

| 功能 | DeerFlow | 我们 | 差距 |
|------|---------|------|------|
| 公共 skill 列表动态从后端获取 | ✅ `GET /api/skills` | ❌ 前端硬编码 | **已决策补充：方案B** |
| 查看 SKILL.md 内容 | ✅ `GET /api/skills/custom/{name}` | ❌ 无 | **已决策：summary返回skill_md** |
| 文件树形展示 | ✅ 目录结构清晰 | ⚠️ 平铺路径列表 | 子专题02 |
| skill 启用/禁用开关 | ✅ PUT API + Toggle | ❌ 无（公共skill全量加载） | 未来功能 |
| skill 导出（打包下载） | ✅ `.skill` archive 下载 | ❌ 无 | 未来功能 |
| skill 安全扫描 | ✅ 静态扫描 + AI扫描（双层） | ⚠️ 只有正则扫描 | 需评估是否引入AI扫描 |
| skill 历史记录与回滚 | ✅ history + rollback | ❌ 无（我们有版本状态机但无rollback） | 设计不同，暂不对齐 |
| skill 代码审查入口（UI） | 无（通过Agent对话） | 无（通过Agent对话） | 两边相同 |
| skill 评估入口（UI） | 无（通过Agent对话） | 无（通过Agent对话） | 两边相同 |
| 治理上下文选择器（会话选择） | 无（单用户单tenant） | ✅ 有（多租户需要） | 我们独有，合理 |
| 版本状态机（candidate/active/revoked） | ❌ 无版本概念 | ✅ 严格状态机 | 我们更强 |
| 多租户 skill 隔离 | ❌ 无 | ✅ tenant+project+user 三维 | 我们更强 |
| 从 GitHub 直接导入 skill | 未见 | ✅ `import_skill` 工具支持 | 我们有 |
| music-generation | ✅ | ❌ | deferred |
| podcast-generation | ✅ | ❌ | deferred |
| video-generation | ✅ | ❌ | deferred |
| web-design-guidelines | ✅ | ✅ | 已有 |

### 本次可实施的缺失功能（已对应子专题）

1. **公共 skill 列表后端动态下发** → 子专题01（方案B，已决策）
2. **SKILL.md 内容展示** → 子专题02（summary 返回 skill_md）
3. **文件树形展示** → 子专题02（前端 UI 改进）
4. **7个未展示的公共 skill 补充** → 子专题01（补充到后端接口响应中）

### 本次不做的缺失功能

- skill 启用/禁用开关（需要治理层设计讨论）
- skill 导出（功能有价值，但不紧急）
- skill 代码审查/评估的 UI 入口（目前对话触发即可）
- music/podcast/video-generation（deferred）

---

## Q6：治理上下文 UI 设计问题——选会话到底有无意义？

### 结论：有轻微误导，建议改造

**现实情况**：`GET /threads/{thread_id}/dear/skills` 这个接口接收 `thread_id`，但内部只是从 thread metadata 里提取 `user_id`，真正查询的是 `(tenant_id, project_id, user_id)` 维度的全部技能版本。

**所以**：不管你在下拉框里选哪个 thread，只要是同一个用户在同一个项目下，看到的数据是完全一样的。

**为什么要传 thread_id？**  
platform-api 这一层需要通过 thread_id 来：
1. 验证这个 thread 确实属于当前用户的这个项目（权限校验）
2. 验证这个 thread 的 `graph_id` 是 `dearflow_agent`

所以 thread_id 是**权限验证用的**，不是"区分哪些技能"用的。

**UI 改造建议**：
- 把下拉标签从"治理上下文"改成更明确的说明（比如"选择 Dear Agent 工作区"或"验证 ID"）
- 或者完全隐藏这个 UI，后端自动选当前用户的第一个 dearflow_agent 会话
- 在"平台公共技能"标签页完全隐藏这个选择器（公共技能跟 thread 完全无关）
