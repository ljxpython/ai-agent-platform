# 子专题01：公共技能目录完整性修复

> 实施更新：后端已完成，当前状态以 [README](README.md)、实际契约以 [07](07-frontend-handoff.md)、验证以 [08第9节](08-backend-development-and-validation.md#9-2026-09-19-实际验证记录) 为准。本文保留当时讨论与决策过程；历史“规划中/暂未实施/暂未决定”不作为当前实施状态。

> **Q5 最新决定：全部公共技能可见。** 取消下面早期“隐藏 5 个、展示 15 个”的方案和验收数量；后端动态返回所有有效内置技能，前端不按用途/推荐状态过滤，目录增长自动跟随。公共文件仍只读，受身份和路径边界保护。具体工作以 [08](08-backend-development-and-validation.md) 为准。

> **最新批准：** 用户已同意 D，采用后端动态目录，共享 Runtime 枚举；早期 A/B 待选择记录不再有效。具体可见集合仍暂未决定；开发位置与验证以 [08](08-backend-development-and-validation.md) 为准，前端仅交接到 07。

> **2026-09-19 核对：** 方案选择 **暂未决定（历史记录冲突待核对）**：原 04 曾写 B 已决策，本页仍待确认。下述 15 个可见技能、隐藏 5 个管理/测试技能均为早期建议。`tools/skills.py::list_skills()` 已有公共目录枚举，只把 8 个标为已验收/可推荐；应先讨论目录存在、页面可见、已验收三个概念，不能补全时把剩余条目统一标成可用。动态下发可复用已有枚举与 frontmatter，未证明必须给所有 SKILL.md 新增字段。最终可见集合与元数据来源 **暂未决定**。

## 目标
解决前端 `OFFICIAL_PUBLIC_SKILLS` 硬编码 8 个 vs 后端实际部署 20 个 skill 的数量差距，让界面展示的公共技能与实际可用的保持同步。

## 问题分析

### 当前实现方式
前端在 [`skills.service.ts`](../../../apps/platform-web/src/services/dear-agent/skills.service.ts) 里手动维护一个静态数组 `OFFICIAL_PUBLIC_SKILLS`，包含 8 个条目，每次后端新增 skill 都需要手动同步前端代码，极易遗漏。

### 后端实际情况
`runtime-service/services/dearflow_agent/skills/` 目录下有 20 个 skill，其中：
- **面向用户的 skill（应在界面展示）**：`academic-paper-review`, `chart-visualization`, `code-documentation`, `consulting-analysis`, `data-analysis`, `deep-research`, `frontend-design`, `github-deep-research`, `image-generation`, `newsletter-generation`, `ppt-generation`, `surprise-me`, `systematic-literature-review`, `vercel-deploy-claimable`, `web-design-guidelines`（共 **15 个**）
- **内部工具 skill（不应对用户展示）**：`bootstrap`, `find-skills`, `runtime-smoke`, `skill-creator`, `skill-reviewer`（共 5 个）

### 目前缺失的 7 个（已有后端 skill 但前端未展示）
| slug | 名称 | 说明 |
|------|------|------|
| `chart-visualization` | 图表可视化 | 26 种图表类型，数据可视化 |
| `consulting-analysis` | 咨询分析报告 | 市场/行业分析，咨询级报告 |
| `github-deep-research` | GitHub 深度研究 | GitHub 仓库深度分析 |
| `image-generation` | 图像生成 | 生成、可视化图像内容 |
| `surprise-me` | 惊喜我 | 创意性地组合多个 skill |
| `systematic-literature-review` | 系统性文献综述 | 多篇论文综述，非单篇审查 |
| `vercel-deploy-claimable` | Vercel 部署 | 部署到 Vercel，获取预览链接 |

## 方案设计

### 方案 A（推荐）：继续前端硬编码，但补全 7 个缺失 skill

**优点：** 改动小，纯前端，不需要后端配合，可以为每个 skill 定制中文名称、分类、描述  
**缺点：** 以后新增 skill 仍需手动同步，维护成本存在  
**适用场景：** 公共 skill 不频繁变化，且需要精心维护描述文案

**改动范围：** 仅 `apps/platform-web/src/services/dear-agent/skills.service.ts`，在 `OFFICIAL_PUBLIC_SKILLS` 数组中补充 7 条记录

### 方案 B：后端新增接口动态下发公共 skill 列表

**优点：** 前后端自动同步，不会再有遗漏  
**缺点：** 需要在 runtime-service 新增接口，属于链路改动；还需要在每个 SKILL.md 里加 `backend_verified`/`recommendable`/`category` 字段（目前 SKILL.md 里没有这些）  
**适用场景：** skill 变化频繁，或希望彻底去掉前端硬编码

### 老王的判断
方案 A 是现在最合理的——skill 列表不是天天在变，补全 7 个条目花不了多少时间，方案 B 工程量更大且需要改 SKILL.md 格式，得不偿失。但选哪个需要用户拍板。

## 待确认问题
- [ ] **Q1**：选方案 A（补全前端硬编码）还是方案 B（后端动态下发）？
- [ ] **Q2**：`vercel-deploy-claimable` 这个 skill slug 名字有点奇怪，前端展示时用什么中文名比较好？
- [ ] **Q3**：`surprise-me` 是否适合对所有用户展示？它的描述是"动态发现并创意组合其他 skill"，属于娱乐性功能。

## 任务拆分（基于方案A）
- [ ] Task 1：在 `skills.service.ts` 的 `OFFICIAL_PUBLIC_SKILLS` 数组中补充 7 个 skill 条目，确认中文名称、分类、描述文案
  - **文件：** `apps/platform-web/src/services/dear-agent/skills.service.ts`
  - **状态：** 待开始（方案待确认）

## 验证要求与记录
### 验证要求
- [ ] 前端 Skills 页面"平台公共技能"区显示 15 个 skill 卡片
- [ ] 搜索功能对新增的 skill 有效
- [ ] 所有卡片的 `path` 字段指向存在的后端路径

### 验证记录
_待实施后填写_

## 状态
规划中（待用户确认方案选择）
