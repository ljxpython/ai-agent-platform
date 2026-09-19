# Skills 前端交接：后端实际契约与前端实施细则

状态：**最高 / done（后端契约、前端规格与交互细化）**；前端代码与浏览器验收 **待实施**。本文件为前端实施的唯一事实标准（Single Source of Truth）。

---

## 1. 前端要改什么（改动总览）

| 文件位置 | 必须适配改动 | 关键注意事项 |
|---|---|---|
| `apps/platform-web/src/services/dear-agent/skills.service.ts` | 彻底删除 `OFFICIAL_PUBLIC_SKILLS` 硬编码、旧 `SkillVersion` 类型及 candidate/activate/revoke 方法；完整接入下述 7 类强类型 API 方法。 | 彻底移除所有 `threadId` 和 `action` 参数；统一走 `platformHttpClient` 附加 `x-project-id` 请求头。 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.vue` | 1. 移除会话与治理上下文依赖（不再调用 `useDearGovernanceContext` 的 threads，改为 `useWorkspaceProjectContext` 仅获取项目上下文）；<br>2. 移除公共技能 `category` 分类字段及相关筛选逻辑；<br>3. 列表项不再包含 `manifest`，新增右侧抽屉（`BaseDrawer`）查看文件树与正文；<br>4. 自定义技能卡片增加 Switch 启停、显式更新按钮、删除二次确认；<br>5. 导入弹窗遇到同名 409 时支持一键转更新。 | 严禁在列表项直接取 `skill.manifest`（列表已剥离，会报 undefined）；安全渲染 Markdown，禁止执行 HTML/JS。 |
| `apps/platform-web/src/services/dear-agent/skills.service.spec.ts` | 移除 8 项公共技能及带 `threadId` 的旧接口断言；测试新 7 类方法的请求路径、Query/Body 传参及返回结构。 | 重点验证 DELETE 传参 `expected_revision` 位于 params，PATCH 传递 strict boolean。 |
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.spec.ts` | 移除 `hasThreads`、`switchThread` 等会话 mock；验证无会话加载、动态公共目录、抽屉展开文件树、启停 CAS 传递、同名更新转接与只读模式展示。 | 模拟 409 revision conflict 与容量超限错误分支。 |

> [!IMPORTANT]
> **边界红线**：
> 1. 技能管理只依赖登录凭据和当前项目（`activeProjectId`），**严禁查找第一个会话充当上下文**，严禁调用 thread capabilities。
> 2. 记忆页面（`DearAgentMemoryPage.vue`）仍依赖既有 thread memory 接口，**切勿改动或误删 `useDearGovernanceContext` 的会话能力**。

---

## 2. 已实现的后端变化

1. **Runtime 存储与生命周期**：
   - 数据库表 `dear_skills` 采用 `(tenant_id, project_id, user_id, slug)` 联合主键，**同一技能仅维护一份当前内容**。
   - 上传默认 `enabled: true`；更新（PUT）**保留原 enabled 状态**；启停（PATCH）瞬时可逆；删除（DELETE）物理移除记录。
   - 取消“候选(candidate) → 审查(review) → 评估(evaluation) → 激活(activate) → 撤销(revoke)”复杂状态机，无强制审查与发布门槛。
2. **公共目录与分类变动**：
   - 后端动态枚举内置技能（`runtime_service/services/dearflow_agent/skills/*`），包含烟测与管理类。
   - 公共技能**只读**，不支持覆盖、启停或删除。
   - **重要数据结构变动**：公共技能**不再提供 `category` 分类字段**，仅包含 `backend_verified` 与 `recommendable`（仅作验收参考，不影响展示）。
3. **列表性能优化与 Manifest 剥离**：
   - `GET /api/langgraph/dear/skills` 返回的列表项中**故意剥离了 `manifest` 字段**以节约带宽。
   - 只有详情接口 `GET /api/langgraph/dear/skills/{source}/{slug}` 或新建/更新成功的响应中才携带 `manifest` 文件清单。
4. **执行快照机制**：
   - 任务启动时快照当前启用的技能；中断恢复沿用原快照；新任务读取当前最新启用集合。

---

## 3. 七类实际接口与数据契约

前端仅与 `platform-api` 交互，由网关统一注入授权委托并附加 `x-project-id: <projectId>`。

### 3.1 接口清单

| # | 方法与平台路径 | 请求参数 / Body | 成功响应 | 说明 |
|---|---|---|---|---|
| 1 | `GET /api/langgraph/dear/skills` | 无 | `200 { items, capabilities, limits }` | 列表 items **不含** manifest |
| 2 | `GET /api/langgraph/dear/skills/{source}/{slug}` | path: `source` (public/custom), `slug` | `200 SkillDetail` | 包含 `manifest` 清单 |
| 3 | `GET /api/langgraph/dear/skills/{source}/{slug}/content` | query: `path` (string), `revision` (string) | `200 { path, content, revision }` | 正文为文本字符串；遇 409 自动刷新 |
| 4 | `POST /api/langgraph/dear/skills/custom` | JSON `{ package_base64 }` | `201 SkillDetail` | 新增技能，默认启用 |
| 5 | `PUT /api/langgraph/dear/skills/custom/{slug}` | JSON `{ package_base64, expected_revision }` | `200 SkillDetail` | 覆盖更新，保留原有启用状态 |
| 6 | `PATCH /api/langgraph/dear/skills/custom/{slug}` | JSON `{ enabled: boolean, expected_revision }` | `200 SkillDetail` | **注意：返回完整更新后的技能详情** |
| 7 | `DELETE /api/langgraph/dear/skills/custom/{slug}` | query: `expected_revision` (string) | `204 No Content` | 彻底删除当前技能记录 |

### 3.2 TypeScript 类型定义（`skills.service.ts`）

```typescript
export interface SkillManifestItem {
  path: string;
  size: number;
  readable: boolean;
  reason?: 'not_utf8_text' | 'file_too_large' | string;
}

export interface BaseSkillItem {
  source: 'public' | 'custom';
  slug: string;
  name: string;
  description: string;
  revision: string;
  updated_at: string | null;
}

export interface PublicSkillItem extends BaseSkillItem {
  source: 'public';
  updated_at: null;
  backend_verified: boolean;
  recommendable: boolean;
}

export interface CustomSkillItem extends BaseSkillItem {
  source: 'custom';
  enabled: boolean;
  digest: string;
  origin: string;
  warnings: string[];
  updated_at: string;
}

export type SkillItem = PublicSkillItem | CustomSkillItem;

export type SkillDetail = SkillItem & {
  manifest: SkillManifestItem[];
};

export interface SkillContentResponse {
  path: string;
  content: string;
  revision: string;
}

export interface DearSkillsCapabilities {
  can_read: boolean;
  can_write: boolean;
  custom_management_enabled: boolean;
}

export interface DearSkillsLimits {
  package_bytes: number;   // 1048576 (1 MiB)
  unpacked_bytes: number;  // 1048576 (1 MiB)
  file_bytes: number;      // 262144 (256 KiB)
  entries: number;         // 100
  custom_skills: number;   // 50
}

export interface DearSkillsListResponse {
  items: SkillItem[];
  capabilities: DearSkillsCapabilities;
  limits: DearSkillsLimits;
}
```

### 3.3 Service 方法签名要求

```typescript
// 获取技能列表（公共 + 自定义）
export async function getDearSkills(projectId: string, signal?: AbortSignal): Promise<DearSkillsListResponse>;

// 获取技能详情（含 manifest）
export async function getDearSkillDetail(projectId: string, source: 'public' | 'custom', slug: string, signal?: AbortSignal): Promise<SkillDetail>;

// 获取单个文件文本正文
export async function getDearSkillContent(projectId: string, source: 'public' | 'custom', slug: string, path: string, revision: string, signal?: AbortSignal): Promise<SkillContentResponse>;

// 上传新自定义技能
export async function createCustomSkill(projectId: string, packageBase64: string): Promise<SkillDetail>;

// 显式覆盖更新已有技能
export async function updateCustomSkill(projectId: string, slug: string, packageBase64: string, expectedRevision: string): Promise<SkillDetail>;

// 启停自定义技能
export async function toggleCustomSkill(projectId: string, slug: string, enabled: boolean, expectedRevision: string): Promise<SkillDetail>;

// 删除自定义技能（注意：expected_revision 走 params）
export async function deleteCustomSkill(projectId: string, slug: string, expectedRevision: string): Promise<void>;
```

---

## 4. UI 架构与交互设计规格

### 4.1 页面顶栏与上下文
1. **移除治理上下文下拉**：彻底删除 `<select>` 会话下拉及“治理上下文”字样。
2. **上下文展示**：左侧展示标题“Skills 技能管理”与当前所属项目名称；右侧操作区保留“刷新”按钮与“导入技能包 (ZIP)”主按钮。
3. **只读横幅**：当 `!capabilities.can_write` 或无项目写权限时，展示黄色警告条：“当前项目处于只读模式或自定义技能管理已关闭，不可进行导入、修改与删除。”

### 4.2 专区标签页与检索
1. **Tab 切换**：保留“平台公共技能”与“自定义技能管理”两个专区切换。
2. **公共技能分类剥离**：
   - 移除原 `s.category` 分类标签与徽标。
   - 搜索框检索范围限定为：`name`、`slug`、`description`。
   - 公共技能卡片仅展示：标题、slug、描述、只读状态标记、以及“查看详情”按钮。
3. **自定义技能卡片**：
   - 状态展示：启用中（绿色徽标）/ 已停用（灰色徽标）。
   - 字段展示：slug、name、description、更新时间 `updated_at`、版本 `revision`。
   - 操作按钮组：
     - **启用/停用 Switch 开关**：直接触发 PATCH 操作，带卡片局部 loading 防抖。
     - **更新按钮**：直接打开更新弹窗，自动填入当前 slug 并绑定最新 revision。
     - **查看详情按钮**：打开右侧详情抽屉。
     - **删除按钮**：触发危险操作确认弹窗。

### 4.3 技能详情抽屉（`BaseDrawer`）
点击任意公共或自定义技能卡片上的“查看详情”，右侧弹出 `BaseDrawer`（宽度 `wide` 或 `full`）：
1. **加载逻辑**：
   - 打开抽屉时显示 Skeleton 或 Loading，调用 `getDearSkillDetail(projectId, source, slug)` 获取完整元信息与 `manifest`。
   - 默认自动选中并请求根目录下 `SKILL.md` 的正文内容（调用 `getDearSkillContent`）。
2. **左侧：文件树导航面板**：
   - 根据 `manifest` 数组按 `/` 层级构造目录树，或展示结构化文件列表。
   - 每一项展示：文件名、文件体积（格式化为 B/KiB）。
   - 文件状态识别：
     - `readable === true`：可点击，选中后右侧加载正文。
     - `readable === false`：显示灰色并带锁定/警告图标，鼠标 hover 显示不可读原因（`file_too_large` 提示“文件超过 256 KiB 限制”，`not_utf8_text` 提示“非 UTF-8 文本文件”）。点击时不发送 content 请求。
3. **右侧：正文预览面板**：
   - 顶部工具条：当前选中文件路径、文件大小、一键复制代码按钮。
   - 内容渲染分支：
     - **Markdown (`.md`)**：调用现有 `renderMarkdown()` 函数安全渲染。
     - **代码/配置文本 (`.py`, `.json`, `.yaml`, `.txt`, `.js`, `.html` 等)**：以等宽代码块展示，严格进行 HTML escape 实体编码，防止 XSS，支持横向滚动与行号。
     - **不可读文件**：展示空态占位卡片与明确的不可读原因。
4. **409 Content 竞态自动处理**：
   - 若用户点击文件时后端返回 409 `skill_revision_conflict`，前端静默自动调用 `getDearSkillDetail` 刷新当前抽屉的 `revision` 和 `manifest`，并以最新 revision 重新拉取该文件，无需弹出阻断性错误。

### 4.4 导入与更新的双入口交互流
1. **入口 A：卡片“更新”按钮（直达 PUT）**：
   - 点击自定义技能卡片上的“更新”按钮，打开“更新技能包 [slug]”弹窗。
   - 仅需选择新 ZIP 文件。
   - 提交时调用 `updateCustomSkill(projectId, targetSkill.slug, base64, targetSkill.revision)`。
   - 成功后自动更新列表项与抽屉详情，保留原启停状态。
2. **入口 B：顶部“导入技能包”弹窗（POST 遇冲突平滑转 PUT）**：
   - 用户选择 ZIP 包，点击“确认上传”调用 `createCustomSkill`。
   - **遇 409 `skill_name_conflict` 错误处理**：
     - 弹窗不强制关闭，展示友好提示：“检测到同名技能已存在。是否直接将其更新覆盖？”。
     - 用户点击“直接更新”后，前端自动获取该 slug 的当前最新 revision，转换为 `updateCustomSkill` 进行 PUT 更新。

### 4.5 启停与删除交互防抖
1. **启停切换（Toggle）**：
   - 切换 Switch 时，先置卡片为 `isToggling = true`，禁用重复点击。
   - 成功后，以 PATCH 返回的全新 `SkillDetail` 直接替换当前数组中的项（保持响应性）。
   - 若失败（如并发 409），将 Switch 拨回原值，并弹 Toast 提示“状态已被其他操作更新，正在刷新”。
2. **删除确认（Delete）**：
   - 点击“删除”弹出 `ConfirmDialog`，设置 `danger = true`。
   - 文案明确：“删除后将彻底移除该自定义技能，不提供历史恢复；已在执行中的任务仍将沿用历史快照。确定要删除吗？”。
   - 确认后调用 `deleteCustomSkill(projectId, slug, revision)`，成功后清空抽屉并从列表移除该项。

---

## 5. 错误码分支与容错矩阵

| HTTP | 错误码 (`error.code`) | 场景说明 | 前端统一处理方案 |
|---|---|---|---|
| 400 | `invalid_skill_package` | ZIP 损坏或 Base64 解码失败 | 提示文件损坏，要求重新打包 |
| 400 | `unsafe_skill_package` | 包含软链接、绝对路径、隐藏文件或非常规后缀 | 标红展示安全拦截原因 |
| 400 | `skill_frontmatter_required` | `SKILL.md` 缺少 YAML frontmatter | 提示“根目录 SKILL.md 必须包含 name 与 description” |
| 400 | `skill_name_mismatch` | 更新包内 name 与当前 URL slug 不一致 | 提示“压缩包内技能名与目标技能不一致，禁止更新” |
| 400 | `reserved_public_skill_name` | 自定义技能名与公共技能同名 | 提示“该名称已被平台内置技能占用，请更换” |
| 400 | `skill_security_blocked` | 触发静态正则高危阻断（如 curl bash、明文凭据等） | 严重警告：“检测到代码包含高危敏感指令，禁止上传” |
| 403 | `dear_skills_scope_denied` | 无权限访问当前项目技能 | 提示权限不足，锁定写操作 |
| 404 | `skill_not_found` | 技能已被删除或不存在 | 刷新列表，关闭详情抽屉 |
| 409 | `skill_name_conflict` | POST 创建遇到重名技能 | 弹窗内引导转为显式覆盖更新（PUT） |
| 409 | `skill_revision_conflict` | 写操作（PUT/PATCH/DELETE）版本并发冲突 | 提示“技能已被他人更新，已自动刷新最新状态”并重拉列表 |
| 409 | `skill_capacity` | 自定义技能数量超过 50 个上限 | 提示“自定义技能数量已达 50 个上限，请先删除无用技能” |
| 409 | `dear_skills_disabled` | 后端治理总开关未开启 | 顶部展示横幅，禁用所有管理操作 |
| 413 | `skill_package_size` | 压缩包或展开体积超过 1 MiB | 提示“技能包体积超过 1 MiB 上限” |
| 413 | `file_too_large` | 读取单个文件超过 256 KiB | 详情树节点显示为不可读，禁用请求 |

---

## 6. 测试与交付验收清单

前端开发完成后，必须按此清单逐项在浏览器中完成实测验证：

- [ ] **T01 无会话管理验证**：清空所有对话/新项目进入 Skills 页面，页面正常加载，无任何 400/404 报错，不发送 threads 请求。
- [ ] **T02 公共目录动态枚举**：公共专区正确渲染所有内置技能，无 `category` 报错，搜索过滤流畅，只读无写控件。
- [ ] **T03 详情抽屉与正文预览**：点击公共/自定义技能卡片，右侧抽屉滑出，文件树层级正确；默认展示 `SKILL.md`；Markdown 正常排版，非 Markdown 代码高亮且 XSS 转义安全；不可读文件禁用并展示原因。
- [ ] **T04 导入自定义技能**：上传合法标准 ZIP，上传成功后列表出现该技能，默认启用，抽屉可查看新文件树。
- [ ] **T05 显式更新技能**：点击卡片“更新”按钮上传新 ZIP，PUT 成功后文件树与正文更新，原启用/停用状态保持不变。
- [ ] **T06 同名导入冲突转接**：导入弹窗上传同名包触发 409，弹窗提示转为更新，确认后成功 PUT 更新。
- [ ] **T07 启用与停用切换**：切换 Switch 开关，状态即时更新，卡片有 loading 防抖；在途中连续点击受控。
- [ ] **T08 删除与二次确认**：点击删除，弹出危险确认框；确认后成功删除并清空选中详情，列表无残留。
- [ ] **T09 权限与项目切换**：无写权限时写操作锁定；切换项目时清理旧数据并取消在途请求，重新拉取新项目技能。
- [ ] **T10 记忆页回归**：切换至 Memory 页面，验证会话选择与记忆读取/更新功能完好，不受技能去会话化影响。
- [ ] **T11 单元测试全部通过**：`pnpm test:run skills.service.spec.ts` 与 `DearAgentSkillsPage.spec.ts` 0 failures。
