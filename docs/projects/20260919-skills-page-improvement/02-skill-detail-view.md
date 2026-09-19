# 子专题02：技能详情展示

> 实施更新：后端已完成，当前状态以 [README](README.md)、实际契约以 [07](07-frontend-handoff.md)、验证以 [08第9节](08-backend-development-and-validation.md#9-2026-09-19-实际验证记录) 为准。本文保留当时讨论与决策过程；历史“规划中/暂未实施/暂未决定”不作为当前实施状态。

> **最新批准：** 用户已同意 D，公共与自定义技能均提供文件树和按需文本读取（含辅助文本），不采用只列文件名或只扩展 summary 的最低方案。大小/格式/schema 细节仍待定。后端开发见 [08](08-backend-development-and-validation.md)，前端只交接到 07。

> **2026-09-19 核对：** 详情范围与契约 **暂未决定（历史记录冲突待核对）**：原 04 写 summary 返回 skill_md 已决策，本页仍待确认。只展示树不等于能查看每个文件内容；只加 SKILL.md 也不能满足“查看所有文件”。需分别明确公共/自定义技能的树、正文与辅助文件范围。即便复用列表接口增加字段，也需核对 platform-api 透传和前端类型，不能断言只改 Runtime 即完成。若自定义治理简化，需先确定内容存储与详情身份标识，再定路径。

## 目标
让用户能够在 Skills 页面查看技能的目录结构和文件内容（只读），不要求编辑能力。

## 问题分析

### 当前现状

**自定义技能**：
- 后端 `SkillStorage.summary()` 返回的 `manifest` 字段包含文件列表（`path` + `sha256`）
- 前端已实现"文件清单"展开面板，可以看到文件路径和 sha256 前缀
- **缺失：** 无法看到文件的实际内容

**公共技能**：
- 完全没有详情展示，只有卡片上的 `name`、`description`、`path` 字段
- 后端 skill 文件物理存储在 runtime-service 容器内，目前没有暴露读取接口

### 关键代码位置

`SkillStorage.summary()` 方法（[`skill_governance.py`](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py)）：
```python
@staticmethod
def summary(doc):
    return {**{k: v for k, v in doc.items() if k != "files"},
            "manifest": [{"path": k, "sha256": hashlib.sha256(v.encode()).hexdigest()} for k, v in doc["files"].items()]}
```
`files` 字段（文件名→内容的字典）在 `summary()` 里被故意去掉了，只保留了 `manifest`（文件名→sha256）。

## 方案设计

### 自定义技能的文件内容查看

#### 方案 A：新增后端接口返回单文件内容
- 在 runtime-service 新增 `GET /internal/threads/{thread_id}/dear/skills/{slug}/{digest}/files/{path}` 接口
- platform-api 同步新增路由透传
- 前端点击文件名后发请求查看内容
- **优点：** 安全，按需加载，不会一次传回所有文件内容
- **缺点：** 需要跨服务改动（链路改动）

#### 方案 B：列表接口直接返回部分文件内容（只返回 SKILL.md）
- `summary()` 增加一个可选参数，或新增单独接口，返回 `SKILL.md` 内容
- **优点：** 改动范围小，SKILL.md 是最重要的文件
- **缺点：** 其他文件仍然看不到

#### 方案 C（最简）：只展示文件树，不展示内容
- 现有的 `manifest` 已经有文件路径列表，只是前端展示得比较简单（单列平铺）
- 把文件列表改成树形展示（按目录层级分组），体验更清晰
- **优点：** 纯前端改动，零后端代价
- **缺点：** 看不到文件内容，只是 UI 改进

### 公共技能的详情查看

需要在 runtime-service 新增接口来读取内置 skill 文件。

#### 方案：新增公共技能文件树接口
- `GET /internal/skills/{slug}/files` 返回该 skill 的文件列表（含 SKILL.md 内容）
- platform-api 透传（或直接前端访问 runtime-service，但这不符合现有架构）
- **工程量：** 中等（需要跨服务改动）

### 老王的判断

整个这个需求需要分层考虑：

1. **最低成本的改进**（方案C + 公共技能仅展示 SKILL.md 摘要）：
   - 自定义技能：把平铺文件列表改成树形视图，体验好很多
   - 公共技能：在前端硬编码里把 SKILL.md 的 `description` 内容扩展得更详细，而不是真正读取文件
   
2. **中等成本**（方案B）：
   - 自定义技能 `summary` 接口额外返回 SKILL.md 内容（只需改 runtime-service 一个地方）
   - 公共技能继续前端硬编码描述

3. **完整方案**（方案A）：
   - 真正可以查看任意文件的内容
   - 但工程量大，且这页面本来就是治理页，不是文档查看器

**这里建议用最低成本方案**——树形文件列表 + 展示 SKILL.md 内容，这样已经满足"能看到目录结构和每个文件"的需求，不用上重型接口。

## 待确认问题
- [ ] **Q1**：需要看到的"文件内容"深度是什么？只看 `SKILL.md` 的主体内容，还是所有文件（包括 `.py`, `.json` 等辅助文件）？
- [ ] **Q2**：公共技能是否也需要展示文件内容？还是只要自定义技能能看就够了？
- [ ] **Q3**：可以接受"只看文件列表（树形），不看文件内容"的最小改动吗？

## 任务拆分（方案待定）

### 基于"最低成本"方案的任务
- [ ] Task 1：自定义技能 - 将平铺文件列表改为按目录层级的树形展示
  - **文件：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.vue`
  - **改动：** 将 manifest 文件列表按 `/` 分隔解析成树形结构并渲染
  - **状态：** 待开始

- [ ] Task 2（可选）：runtime-service `summary()` 额外返回 SKILL.md 内容
  - **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py`
  - **改动：** `summary()` 在 manifest 之外额外包含 `skill_md` 字段（`files["SKILL.md"]` 的内容）
  - **状态：** 待开始（取决于 Q1 的答案）

## 验证要求与记录
### 验证要求
- [ ] 自定义技能展开后可以看到文件树（按目录层级分组）
- [ ] SKILL.md 内容（如果实施 Task 2）可正确显示

### 验证记录
_待实施后填写_

## 状态
规划中（待用户确认需要展示内容的深度）
