# W4 阶段实现记录：真记忆与真技能治理管理页 (T4.1 ~ T4.4)

## 1. 概述与目标
本阶段紧扣官方 DearFlow 治理规范与 PostgreSQL 权威存储契约，彻底重构了原有的误导性假占位页面，全面交付了生产级真记忆与真技能版本治理系统：
1. **T4.1 治理上下文自动降级与绑定 (`useDearGovernanceContext.ts`)**：
   - 自动拉取当前激活项目下 `graph_id === "dearflow_agent"` 的真实会话列表，智能优先绑定最新活跃会话或根据 URL 参数 `?threadId=...` 精确对齐；
   - 消除用户在 UI 上反复手动挑选会话的繁琐体验；
   - 当项目下没有任何 Dear 会话时，提供友好的自动降级空态与一键创建会话按钮（`createInitialThread`），创建成功后自动设置并绑定为治理上下文。
2. **T4.2 记忆真治理管理页 (`DearAgentMemoryPage.vue` & `memory.service.ts`)**：
   - 严格对接后端 `/api/langgraph/threads/{thread_id}/dear/memory` 契约；
   - 双 Tab 视图架构：“生效事实库 (Facts)”与“推断候选库 (Candidates)”；
   - 支持关键词过滤与即时检索；
   - 支持自动推断候选开关（`automatic_candidates`，明确标注默认关闭且开启不等于自动记住）；
   - 支持单条记忆事实的新增、编辑、删除（带 CAS `expected_revision` 防并发覆盖机制）；
   - 遇到 409 `memory_revision_conflict` 时自动拉取最新数据且保留用户表单草稿，避免反复录入；
   - 支持一键清空事实库（带严厉警告模态框确认，自增 epoch 防复活机制）；
   - 支持候选条目的采纳（转为正式事实）与拒绝（记录指纹防再次推断）；
   - 支持 JSON 批量追加恢复（最多 100 条，明确为追加导入非全量覆盖）。
3. **T4.3 技能真治理管理页 (`DearAgentSkillsPage.vue` & `skills.service.ts`)**：
   - 严格对接后端 `/api/langgraph/threads/{thread_id}/dear/skills` 契约；
   - 双专区视图：“平台公共技能专区”与“自定义技能版本治理专区”；
   - **平台公共技能**：展示 8 大官方沙箱内置技能（`deep-research`, `academic-paper-review`, `code-documentation`, `newsletter-generation`, `data-analysis`, `frontend-design`, `web-design-guidelines`, `ppt-generation`），全量标注 `backend_verified`（后端验证通过）与 `recommendable`（允许推荐）徽标；
   - **自定义技能版本**：获取该项目下全部不可变版本包，展示 slug、描述、前 12 位指纹摘要、修订号、安全 warnings 告警、代码审查结果 (Review) 与动态评估结果 (Evaluation)；
   - 支持展开查看技能包完整的 Manifest 清单（包含内部文件相对路径与 SHA256）；
   - **导入候选 ZIP**：前端校验文件格式必须为 `.zip`，大小 ≤ 1MiB (1,048,576 字节)，转换为 Base64 提交为 candidate 候选版本；
   - **版本启用与回退**：仅当 review 与 evaluation 均 passed 且无 warnings 风险时允许点击，弹出确认模态框，同名技能的历史版本自动转为 inactive；
   - **版本永久撤销**：弹出警告模态框，撤销后该版本永久失效且不可重新激活；若旧会话绑定了该版本将无法恢复，明确引导新建会话；
   - 清晰提示 DearFlow 线程首次装配时的版本冻结规则。
4. **T4.4 批次验证与状态签署**：
   - 完成服务层与页面层全量单测，13 套测试套件 50 个测试用例 100% 绿灯；
   - `vue-tsc --noEmit` 0 报错通过；
   - 原通用 Chat 模块 24 套测试套件 76 个测试用例全部通过，保持 0 破坏。

---

## 2. 涉及改动文件清单

| 文件路径 | 改动性质 | 核心职责 |
|---|---|---|
| `apps/platform-web/src/services/dear-agent/memory.service.ts` | 新建服务 | 长期记忆与偏好治理 HTTP 契约封装（read、save、delete、clear、accept、reject、settings、restore） |
| `apps/platform-web/src/services/dear-agent/memory.service.spec.ts` | 新建单测 | 覆盖记忆治理 7 个核心服务方法的请求参数与响应验证 |
| `apps/platform-web/src/services/dear-agent/skills.service.ts` | 新建服务 | 技能版本治理 HTTP 契约封装（公共技能列表、自定义版本读取、ZIP 导入、激活/回退、撤销） |
| `apps/platform-web/src/services/dear-agent/skills.service.spec.ts` | 新建单测 | 覆盖技能治理 5 个核心服务方法的请求参数与状态流转验证 |
| `apps/platform-web/src/modules/dear-agent/composables/useDearGovernanceContext.ts` | 新建组合函数 | Dear 治理会话上下文自动感知、URL 参数同步、无会话降级与一键创建会话 |
| `apps/platform-web/src/modules/dear-agent/composables/useDearGovernanceContext.spec.ts` | 新建单测 | 覆盖治理上下文自动绑定、会话切换、空态一键创建等 4 个关键场景 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue` | 彻底重构 | 长期记忆与偏好治理管理页面：事实与候选分栏、CRUD、CAS 冲突防护、清空确认、JSON 追加导入 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.spec.ts` | 新建单测 | 覆盖记忆管理页渲染、Tab 切换、候选采纳、空态引导等交互 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.vue` | 彻底重构 | 技能版本治理管理页面：公共技能与自定义版本双专区、ZIP 导入、Manifest 清单展开、审查状态判定、启用与撤销确认 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.spec.ts` | 新建单测 | 覆盖公共技能展示、自定义专区切换、Manifest 展开、审查通过启用等核心流程 |

---

## 3. 验证结果

### 3.1 单元测试执行
```bash
rtk npm test -- src/modules/dear-agent/ src/services/dear-agent/ --run
```
- `src/modules/dear-agent/human-input.spec.ts`: 5 passed
- `src/services/dear-agent/memory.service.spec.ts`: 7 passed
- `src/modules/dear-agent/approvals.spec.ts`: 5 passed
- `src/modules/dear-agent/trajectory/trajectory-adapter.spec.ts`: 7 passed
- `src/modules/dear-agent/pages/DearAgentMemoryPage.spec.ts`: 3 passed
- `src/services/dear-agent/skills.service.spec.ts`: 5 passed
- `src/modules/dear-agent/pages/DearAgentSkillsPage.spec.ts`: 3 passed
- `src/modules/dear-agent/pages/DearAgentArtifactsPage.spec.ts`: 1 passed
- `src/modules/dear-agent/composables/useDearGovernanceContext.spec.ts`: 4 passed
- `src/modules/dear-agent/components/trajectory/TrajectoryView.spec.ts`: 3 passed
- `src/modules/dear-agent/components/ClarificationCard.spec.ts`: 3 passed
- `src/modules/dear-agent/components/trajectory/TrajectoryTimeline.spec.ts`: 2 passed
- `src/modules/dear-agent/pages/DearAgentPage.spec.ts`: 2 passed
- **合计**：13 套测试套件，50 个测试用例全部 100% 通过（0 failed）。

### 3.2 通用 Chat 零破坏回归测试
```bash
rtk npm test -- src/modules/chat/ --run
```
- **检查状态**：24 套测试套件，76 个测试用例全部通过，确认平台通用 Chat 模块无任何功能回归或破坏。

### 3.3 静态类型检查
```bash
rtk npm run typecheck (vue-tsc --noEmit)
```
- **检查状态**：全部通过，退出码 0，无任何 TypeScript 报错。

---

## 4. 签署与后续交接
- **阶段状态**：W4 阶段完成（`[x]`）。
- **进入下一阶段**：W5 阶段（全系统健壮性联调与回归）。
