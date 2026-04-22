# AI 执行系统使用指南

文档类型：`Current Usage Guide`

这份文档回答的是一个非常实际的问题：

> 以后当我在这个仓库里给 AI 提需求、修 bug、做设计、做调研时，应该怎么用我们已经收敛好的 Harness Engineering 体系？

如果你只想知道：

- 这套体系的**理念**是什么
- 为什么要做成这样
- 如何在日常工作里真正使用它

先读这份。

如果你要看正式 current-standard，再读：

- `docs/standards/01-ai-execution-system.md`

如果你要看背景和理由，再读：

- `docs/knowledge/04-ai-execution-system-rationale.md`

---

## 1. 一句话先讲清楚

这套系统不是为了让大家多写文档，而是为了让 **人和 AI 在接任务时，先走对路，再做对事**。

核心原则只有一句：

> **先判定任务落点和边界，再决定流程深度，再决定产物和验证。**

不要一上来就让 AI 直接写代码。

---

## 2. Harness 哲学到底在这里意味着什么

在这个仓库里，Harness Engineering 不是一个抽象口号，而是下面这套工作方式：

1. **任务先找对 locus / layer**
   - 先判断这是 `platform-web`、`platform-api`、`runtime-service`、`runtime-web`、`interaction-data-service`，还是 repo 级问题

2. **标准先就近解析**
   - 优先读最窄的 app-local / leaf standard
   - 不要一开始就拿大而泛的总文档替代局部标准

3. **执行深度按边界决定**
   - 小改动走轻量带宽
   - 改契约 / 要调研 / 碰正式受管面就升级

4. **验证先本地，再最短链，再正式链**
   - 不默认把所有事情都抬成全链路大验收

5. **标准、知识、helper 三层分开**
   - `docs/standards/`：当前标准
   - `docs/knowledge/`：为什么这样设计
   - `.omx/`：helper 模板 / 运行态辅助，不是 canonical truth

---

## 3. 你以后提任务时，先给 AI 什么

最少给这 5 类信息：

### 3.1 Goal

你这次要解决什么问题？

例如：
- 修复某个页面滚动问题
- 新增一个受控管理接口
- 设计一个结果域切片

### 3.2 Scope

这次只做什么，不做什么？

例如：
- 只改前端页面，不动后端
- 先做调研，不直接实现
- 先出设计文档，再决定是否开发

### 3.3 现有事实 / 证据

把你已有的东西给 AI，而不是让它猜：

- 报错日志
- 截图
- 相关接口
- 相关文档
- 你已经确认的约束

### 3.4 真实输入依赖

如果后面一定需要你提供这些，应该先说清楚：

- API key
- 模型地址
- embedding 地址
- 账号
- 测试数据
- 环境参数

AI 可以提醒你缺什么，但**不能代替你决定真实密钥和真实参数**。

### 3.5 你期望的交付形态

你可以明确告诉 AI：

- 先修 bug
- 先调研
- 先规划
- 先做 PRD / Test Spec
- 先给我 TODO，再实现

---

## 4. AI 接到任务后，第一步必须产出什么

AI 第一反应不应该是“开始改代码”，而应该先回答这 5 件事：

1. **Locus / Layer**
2. **Chain Map**
3. **Standards Loaded**
4. **Execution Band**
5. **Verification Plan**

也就是先告诉你：

- 这件事属于哪一层
- 会影响哪条链
- 应该先读哪份标准
- 应该走 B1 / B2 / B3 哪一档
- 怎么证明完成

如果 AI 没先回答这 5 件事，就说明它还没真正按这套系统工作。

---

## 5. B1 / B2 / B3 怎么理解

### B1：轻量本地执行

适合：

- 小 bug
- 明确范围的小改动
- 单一 locus 内闭环
- 不改契约
- 不需要调研
- 不碰正式平台受管面

AI 在 B1 下应该：

- 简短澄清
- 输出紧凑 TODO/checklist
- 直接改
- 跑本地最小验证
- 做简短 retro/doc decision

**B1 不要求强行写完整 PRD。**

---

### B2：标准执行

适合：

- 单应用内中等需求
- 需要设计、拆解、TODO
- 需要最短链验证
- 还没碰到受管公开面

AI 在 B2 下应该：

- 先规划
- 再拆 TODO
- 再实现
- 再跑本地 + 最短链验证
- 最后同步文档/回顾

---

### B3：受管 / 调研 / 正式链执行

适合：

- 改 public / governed contract
- 需要调研
- 影响正式平台相关
- 影响 runtime public contract
- 影响 platform management interface
- 跨多个 locus
- 需要真实 key / 参数 / 数据

AI 在 B3 下应该：

- 先澄清
- 再出 PRD / ADR / Test Spec
- 明确你要提供的真实输入
- 再按 approved plan 实施
- 最后做 formal verification 和文档闭环

---

## 6. 升级门禁：什么情况下不能继续轻量做

只要命中下面任一条，就不能继续按 B1 轻量流随手做：

- 要改契约
- 需要调研
- 影响正式平台相关
- 影响运行时公开契约
- 影响平台管理接口
- 跨服务 / 跨权限 / 跨数据边界
- 本地验证不够证明结论

---

## 7. 以后实际使用时，应该先读哪份文档

### 第一步：统一先读

- `docs/standards/01-ai-execution-system.md`

### 第二步：按 locus 读 leaf

#### `platform-web`
- 页面类型 / 骨架 / 组件组合  
  → `docs/platform-web-sub2api-migration/14-frontend-development-playbook.md`
- 正式控制面页面的 service/state/permission/audit  
  → `apps/platform-web/docs/control-plane-page-standard.md`

#### `platform-api`
- 模块归属 / 分层  
  → `apps/platform-api/docs/handbook/project-handbook.md`  
  → `apps/platform-api/docs/handbook/development-playbook.md`
- 权限 / 审计 / operation  
  → `apps/platform-api/docs/standards/permission-standard.md`  
  → `apps/platform-api/docs/standards/audit-standard.md`  
  → `apps/platform-api/docs/standards/operations-standard.md`
- runtime gateway / 正式管理接口  
  → `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`

#### `runtime-service`
- `apps/runtime-service/runtime_service/docs/standards/*.md`
- `apps/runtime-service/runtime_service/tests/harness/*.py`

#### `runtime-web`
- `apps/runtime-web/docs/standards/runtime-web-debug-standard.md`

#### `interaction-data-service`
- 当前 API / payload / resource truth  
  → `apps/interaction-data-service/docs/test-case-service-api-design.md`
- 结果域边界 / 正式访问链  
  → `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md`
- 背景设计 / 未来抽象  
  → `apps/interaction-data-service/docs/service-design.md`

---

## 8. helper 模板怎么用

这些模板是为了让 AI 少漏字段：

- `.omx/specs/ai-execution-system/locus-classification-schema.md`
- `.omx/specs/ai-execution-system/execution-band-artifact-skeletons.md`
- `.omx/specs/ai-execution-system/real-input-checklist.md`
- `.omx/specs/ai-execution-system/verification-evidence-template.md`

正确用法：

- 让 AI **参考它们来输出**
- 不要把它们当成标准真源

标准真源永远是：

- `docs/standards/*`
- 各 app 的 leaf standard

---

## 9. 以后你可以怎么对 AI 提任务

### 场景 A：小 bug

你可以这样说：

> 请先按 `docs/standards/01-ai-execution-system.md` 做 locus/layer 判定，判断是不是 B1。  
> 如果是 B1，不要写重规划文档，直接给我：  
> 1. 你的理解  
> 2. 影响范围  
> 3. 要改的点  
> 4. 验证方式  
> 然后再开始改。

### 场景 B：普通需求

你可以这样说：

> 请按 AI execution system 先做：  
> locus/layer → chain → standards loaded → B1/B2/B3 判定。  
> 如果不是 B1，不要直接实现，先给我规划和 TODO。

### 场景 C：重大需求 / 新方向

你可以这样说：

> 请按 B3 处理，先做调研 / 澄清 / PRD / Test Spec。  
> 先别实现，先把方案收敛清楚，并明确我需要提供哪些真实输入。

---

## 10. 最推荐的一句固定话术

以后你给 AI 提需求时，最稳的一句话是：

> **请先按 `docs/standards/01-ai-execution-system.md` 做 locus-first 判定，再决定走 B1/B2/B3；如果不是 B1，不要直接实现，先给我规划、TODO 和需要我提供的真实输入。**

这句话会显著提高 AI 跑在正确轨道上的概率。

---

## 11. 你真正要记住的不是所有细节，而是这 4 句

1. **先找对 locus**
2. **先读对 leaf standard**
3. **先定 B1/B2/B3**
4. **先定验证，再动手做**

只要这 4 句守住，这套 Harness 哲学就真的会变成日常工作方式，而不是仓库里的漂亮文档。
