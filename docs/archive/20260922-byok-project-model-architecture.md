# ADR: 平台公共模型与项目私有模型 (BYOK) 双层架构决策

- **状态**：ACCEPTED（2026-09-22 用户批准架构设计）
- **日期**：2026-09-22
- **影响范围**：`apps/platform-api`, `apps/platform-web`, `apps/runtime-service`
- **关联项目**：`docs/projects/20260920-platform-access-governance/`

---

## 1. 背景与核心矛盾 (Context)

在早期的访问治理方案（`20260920-platform-access-governance`）中，为了防止项目间跨租户篡改模型连接（F03 问题），平台采取了中心化管控策略：
- 将所有模型连接和 API Key 的管理权收紧至平台运维角色（`platform.model.write`）。
- 项目只能在平台配置好的模型列表中进行“授权/选用”和设置“项目默认模型”。
- 后端为了脱敏，在项目接口中将 `credential_configured` 硬编码置为 `False`，导致前端误报“部分凭据未配置”，且 Chat 界面因无法识别凭据而拦截对话。

**业务痛点与不合理性**：
1. **开发者丧失模型自主权**：项目团队拥有独立的私有 API Key（如团队采购的 DeepSeek/Kimi Key）或本地私有模型（如局域网 Ollama/vLLM 实例），无法自主接入项目，必须依赖平台运维，协作链路冗长。
2. **凭据运维边界错位**：公共模型密钥由平台运维统一保障，项目成员无法也不应维护平台级 Key；而如果项目成员接入私有模型，则需要对自身项目的凭据负责。
3. **成本与账单不可分**：缺乏项目级 BYOK 机制，无法实现项目自主承担模型消耗与账单隔离。

---

## 2. 决策：采用平台公共模型 + 项目私有模型 (BYOK) 双层架构

平台支持并规范化 **BYOK（Bring Your Own Key）机制**，建立两层模型供给与治理体系：

| 维度 | 平台公共模型 (Platform Managed) | 项目私有模型 (Project BYOK) |
|---|---|---|
| **归属作用域** | 全局（`scope_type = "platform"`, `project_id = NULL`） | 项目级（`scope_type = "project"`, 绑定具体 `project_id`） |
| **管理主体** | 平台运维管理员（`platform_operator` / `platform_super_admin`） | 当前项目管理员或具备写权限的编辑（`project_admin` / `project_editor`） |
| **配置内容** | 平台公共端点、平台总 API Key、全局启停 | 项目私有端点、项目私有 API Key、协议与模型标识 |
| **可见与调用范围** | 平台已授权该模型的所有项目成员均可选用 | 仅属于当前项目的成员可见并调用；跨项目物理隔离 |
| **凭据展示规范** | 平台管理端显示真实凭据状态；项目端标记为“平台托管”，不暴露底层密钥 | 项目端显示“私有凭据已配置/缺失”，项目管理员可管理和更换 |
| **费用与额度** | 消耗平台集中账单 | 消耗项目方自有账户额度 |

---

## 3. 技术实现方案 (Technical Specifications)

### 3.1 数据存储模型扩展
在 `platform-api` 的模型持久化表（`runtime_catalog_models`）中扩展作用域字段：
- `scope_type`: `VARCHAR(16) NOT NULL DEFAULT 'platform'`（取值：`platform` / `project`）
- `project_id`: `UUID NULL`（外键关联 `projects.id`；当 `scope_type='project'` 时必须非空且必须存在对应项目）

索引优化：建立 `(scope_type, project_id)` 复合索引以加速项目可用模型联合查询。

### 3.2 权限判定与安全矩阵 (RBAC)

1. **读取查询 (`GET /api/runtime/models`)**：
   - 请求必须携带可信项目上下文（`x-project-id`）。
   - 返回集合 = **（已授权给本项目的平台公共模型） ∪ （归属于本项目的私有模型）**。
   - 脱敏策略：平台公共模型的私密端点与凭据密文由后端代理托管，返回 `credential_configured=True`（若平台已配）；私有模型对本项目管理员回显配置元数据，API Key 不明文回显。
2. **新增与更新 (`POST / PATCH /api/runtime/models`)**：
   - **公共模型**：要求主体具备 `platform.model.write`。
   - **私有模型**：要求主体具备 `project.runtime.write`（或细化为 `project.model.write`），且请求的 `project_id` 必须与目标资源完全一致。
   - **跨项目拦截**：严禁携带 A 项目凭证修改 B 项目的私有模型，违者立即返回 403 `ForbiddenError` 并记录安全审计。

### 3.3 运行时执行代理 (Runtime Gateway)
- Agent 执行模型推理时，`runtime-gateway` 依据 `model_id` 检索模型元数据：
  - 若为公共模型：解密平台主 Key，附带平台统一代理头发送请求。
  - 若为私有模型：解密属于当前项目的私有 Key，直接发往指定的 Base URL，保证项目间网络与凭据独立。

### 3.4 前端交互规范 (platform-web)
项目模型页面（`/workspace/projects/:projectId/models`）：
1. **清晰分组**：
   - 组一：**项目私有模型 (BYOK)** —— 展示由当前项目自建的模型，项目管理员可见“添加模型”、“编辑凭据”入口。
   - 组二：**平台公共模型** —— 展示平台下发的标准化大底座，项目管理员只进行“选用/撤销”与“设为默认”。
2. **彻底解决状态混淆**：
   - 平台模型显示“平台托管就绪”，不报伪故障；
   - 私有模型根据自身 Key 配置情况真实显示凭据指示器。

---

## 4. 后续落地演进路线
1. **Phase 1（前端体验收敛，已完成）**：修复 Chat/DearAgent 会话模型过滤逻辑，确保已授权公共模型正常工作；在项目视图隐藏运维脱敏凭据假警报。
2. **Phase 2（数据表与接口迁移）**：编写 Alembic 迁移脚本扩充 `scope_type` 与 `project_id` 字段；更新 `RuntimeCatalogService` 实现双层读写与鉴权。
3. **Phase 3（前端 BYOK 编辑与管理）**：在项目模型界面提供项目私有模型创建与凭据抽屉，完善分组 UI。
