# 20260927 AI 服务路由机制与跨服务规范目录

## 背景

跨服务规范治理项目（20260922）完成后，需要将 AI Harness 接入这套规范体系：
1. AI 在改动某个服务前，应自动读取对应的规范文档
2. 跨服务契约文档需要有统一的存放位置和置信度管理

## 改动内容

### AGENTS.md

1. **会话初始化章节**：新增一条——"改动涉及具体服务时，额外读取该服务规范入口"
2. **服务边界章节**：新增 `### 服务规范读取规则` 小节，含服务→规范入口的对照表，以及跨服务改动读取 `docs/standards/README.md` 的规则
3. **新增 `## 跨服务规范` 章节**：定义 `docs/standards/` 目录用途、置信度三档规则（high/medium/low）、代码与文档冲突处理规则（代码是事实源，文档是设计意图，冲突时 AI 标记不自裁）、改动触发文档审查规则
4. **文档结构图**：加入 `docs/standards/` 及其四个标准文件

### 新建 docs/standards/

| 文件 | 状态 | 内容 |
|---|---|---|
| `README.md` | — | 规范健康表，含置信度说明和各规范状态一览 |
| `error-envelope.md` | active | 错误响应 Envelope 结构、上游映射、422 规则、响应头规则 |
| `trace-propagation.md` | active | request_id/trace_id 生成规则、审计查询参数、SSE 追踪事件 |
| `delegation-jwt.md` | draft | JWT payload 完整字段、23 项 operation 枚举、生命周期规则 |
| `sse-event.md` | draft | 网关帧安全、SDK 重试、会话池、410 降级、双入口约定 |

## 关键决策

- **D1（规范读取粒度）**：读入口导航页，AI 按任务判断是否深读具体条目
- **D2（契约存放位置）**：`docs/standards/` 为统一存放位置；已 done 的专项状态为 active，partial/blocked 为 draft
- **D3（冲突处理）**：代码 = 当前事实源；文档 = 已批准设计意图；`confidence: low` 文档视为过期不作约束；安全/契约类冲突 AI 必须停止等待人工

## 涉及文件

- `AGENTS.md`（4处改动）
- `docs/standards/README.md`（新建）
- `docs/standards/error-envelope.md`（新建）
- `docs/standards/trace-propagation.md`（新建）
- `docs/standards/delegation-jwt.md`（新建）
- `docs/standards/sse-event.md`（新建）

## 关联项目

- [跨服务规范治理](../projects/20260922-cross-service-governance/README.md)
- [AI 服务路由专项](../projects/20260926-ai-service-routing/README.md)
