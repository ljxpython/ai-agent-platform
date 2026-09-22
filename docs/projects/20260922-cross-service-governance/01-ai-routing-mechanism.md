# 01 - AI 服务路由机制

## 目标

在 AGENTS.md 中建立服务规范索引，让 AI 在改动某个服务前自动读取对应的开发规范，解决"AI 用 FastAPI 思维改 Agent 代码"、"AI 不知道前端有 CSS token 约束"等问题。

## 方案设计

### 机制原理

**不新建任何文档**——各服务的规范文档已经存在，缺的是路由规则。

在 AGENTS.md 新增两个章节：

**`## 服务规范索引`**：明确告诉 AI 改哪个服务读哪份文档（表格形式）

**在会话初始化规则中加入服务感知**：改动涉及某个服务时，在读 CONTEXT.md 之后，再读对应服务的规范入口

### 各服务规范入口

| 服务 | 规范入口文件 | 开发范式关键词 |
|---|---|---|
| platform-web | `apps/platform-web/docs/frontend-development-playbook.md` + `control-plane-page-standard.md` + `frontend-visual-baseline-standard.md` | Vue 3 + TypeScript，5种页面 Archetype，4层架构，CSS token 体系 |
| platform-api | `apps/platform-api/docs/handbook/` 下所有文件 | Python FastAPI 同步栈，Session 线程边界，委托 JWT，`core.errors` |
| runtime-service | `apps/runtime-service/docs/standards/` 下所有文件 | LangGraph 组合根，1 Service = 1 Agent = 1 graph_id，信任边界校验 |
| interaction-data-service | `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md` | 结果域边界服务，不承载编排状态，幂等写入 |

### 跨服务改动额外读取

链路改动或治理改动（改动涉及两个以上服务）时，额外读取：
- `docs/standards/cross-service-contract.md`（本治理项目建立后存在）

### 优先级规则（写进 AGENTS.md）

```
跨服务规范（契约）优先于服务内部规范
当两者冲突时，以跨服务规范为准
```

## 任务拆分

### Task 1.1: 在 AGENTS.md 新增服务规范索引章节
- **改动内容：** 在 AGENTS.md 的"服务边界"章节后，新增 `## 服务规范索引` 章节，包含服务→规范入口的表格 + 跨服务读取规则 + 优先级声明
- **代码位置：** `AGENTS.md` → `## 服务边界` 章节之后
- **预期结果：** AI 开始改动某服务时，能自动识别需要读取哪些规范文档
- **验证项：** 手动测试：新开会话，要求 AI 修改 runtime-service 代码，检查 AI 是否主动读取 `apps/runtime-service/docs/standards/`
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 1.2: 在 AGENTS.md 会话初始化规则中补充服务感知说明
- **改动内容：** 会话初始化章节补充："当改动涉及特定服务时，在读 CONTEXT.md 后，读取该服务的规范入口文档"
- **代码位置：** `AGENTS.md` → `## 会话初始化` 章节
- **预期结果：** 会话初始化规则和服务规范索引形成完整闭环
- **验证项：** 规则表述清晰，无歧义
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

## 验证要求与记录

### 验证要求
- [ ] AGENTS.md 新章节内容清晰，格式正确
- [ ] 服务索引表格路径均可访问（文件存在）
- [ ] 新开会话测试：AI 改动 runtime-service 时主动读取其规范文档
- [ ] 新开会话测试：AI 处理跨服务改动时主动读取 cross-service-contract.md（待 02-05 建立后验证）

### 验证记录
<!-- 实施后填写 -->

## 状态

规划中
