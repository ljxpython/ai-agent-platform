# 01. AI 执行系统当前标准

本文是仓库里“按什么顺序接单、谁来定标准、什么时候必须升级”的**当前标准**。  
它是薄的、可执行的、可检查的；不是方法论文，也不是历史回顾。

如果你只需要背景原理，去读 `docs/development-paradigm.md` 和 `docs/knowledge/02-aitestlab-harness-blueprint.md`。  
如果你要做当前标准判断，先读本文。

---

## 0. 现行读路径

同一件事，按下面顺序读：

1. **leaf 本地文档**：先读最近的 app 文档，拿到本地事实
2. **本仓 current-standard**：再用本文做跨 leaf 的路由和升级判断
3. **知识文档**：只在需要背景、理由、历史折中时再读
4. **`.omx` helper surfaces**：只看运行态状态，不当成业务政策源

### 0.1 权威顺序

同一 locus 内，优先级是：

1. leaf 本地文档
2. 本仓 current-standard
3. 知识文档
4. `.omx` 状态 / 计划 / 便签 / trace / wiki

`.omx` 里可以有计划和状态，但不能反过来定义本仓当前标准。

### 0.2 root `AGENTS.md` 事实

当前版本化仓库树里**没有 root `AGENTS.md`**；现有的 `AGENTS.md` 只出现在 `.omx/` 的会话或备份路径里。  
所以这里不是“root AGENTS 统领一切”的模式，而是：

- 本文负责 current-standard 路由
- leaf 文档负责 leaf 本地事实
- `.omx` 负责运行态协作，不负责域政策

---

## 1. 必须先走的 intake 顺序

任何 AI 执行请求，必须按这个顺序判断：

1. **locus / layer**
2. **chain / ownership**
3. **standards resolution**
4. **execution band**
5. **artifacts / verification**

如果前一项没定，不能跳到后一项。

| 门 | 先回答什么 | 输出 |
| --- | --- | --- |
| locus / layer | 这是哪个 leaf、哪个层 | 具体目录 + 层级 |
| chain / ownership | 谁拥有这条链 | 本地 owner / 邻接 owner / formal owner |
| standards resolution | 哪份标准生效 | leaf 文档 / 本文 / 知识文档 |
| execution band | 该走 B1 / B2 / B3 | 允许的推进范围 |
| artifacts / verification | 需要哪些产物和证据 | 最小必需集合 |

---

## 2. B1 / B2 / B3：执行带宽

**B = execution band。**  
它不是 Harness Layers L1-L4，也不要拿它们互相替代。

| Band | 含义 | 适用范围 | 证据要求 |
| --- | --- | --- | --- |
| B1 | 本地最小执行 | 单一 leaf、单一 owner 链内可闭环 | 本地最小验证 |
| B2 | 最短相关链 | 需要相邻 leaf，但不需要全链路 | 最短链路验证 |
| B3 | formal chain | 触及正式标准、跨边界治理、或需要正式交付物 | formal artifacts + formal verification |

### 2.1 B1

B1 只做叶子内部闭环。  
典型情况：

- `platform-web-vue` 只改自己页面、自己的 payload 规范、自己的 service 适配
- `runtime-service` 只改自己的 runtime resolver、middleware、graph 装配

### 2.2 B2

B2 只走**最短相关链**，不扩散。

典型链：

- `platform-web-vue -> platform-api-v2`
- `platform-api-v2 -> runtime-service`
- `runtime-web -> runtime-service`

### 2.3 B3

B3 只在下面情况出现：

- 要改 current-standard 本身
- 要跨多个 leaf 的正式边界
- 要产出 PRD / test spec / 交付 runbook 这类 formal artifacts
- 本地或最短链无法证明结论

---

## 3. Hard escalation rules

以下任一条命中，必须升级，不准继续猜：

- 要改 **public / governed contract**
- 需要调研后才能做可信设计
- 影响 **正式平台相关**
- 影响 **运行时公开契约**
- 影响 **平台管理接口**
- 需要跨服务、跨权限、跨数据契约判断
- 本地验证无法覆盖结论

升级顺序：

1. 先升到 leaf owner / leaf doc
2. 再升到本文对应的 current-standard 规则
3. 最后才升到 formal chain

不允许直接跳过前两步去做“大而全”的 formal 处理。

---

## 4. canonical artifact grammar

本文认可的 canonical artifact grammar 必须覆盖下面这些字段：

```md
# <artifact title>

- Goal:
- Scope:
- Not-do list:
- Locus / Layer:
- Chain map:
- Responsibility boundary / ownership split:
- Standards loaded:
- I/O contract:
- Verification plan:
- Acceptance criteria:
- Retro / doc decision:
```

### 4.1 语义要求

- **Goal**：这次要证明什么结果成立
- **Scope**：这次只做什么
- **Not-do list**：明确不做什么
- **Locus / Layer**：具体到 leaf / 目录 / blueprint 层级
- **Chain map**：本次走的是本地链、最短链，还是 formal chain
- **Responsibility boundary / ownership split**：谁拥有这一步，哪些边界不能跨
- **Standards loaded**：明确写出读取了哪份 authoritative 文档
- **I/O contract**：涉及的输入、输出、默认值、禁止字段、失败语义
- **Verification plan**：用什么证据证明
- **Acceptance criteria**：什么条件全部成立才算完成
- **Retro / doc decision**：是否要更新 docs / runbook / handoff，或为什么不用

### 4.2 产物命名

正式产物尽量保持短、稳、能路由：

- current-standard：`docs/standards/<nn>-<slug>.md`
- leaf 本地标准：leaf 自己的 `docs/*`
- formal plan：`.omx/plans/prd-*.md`
- formal test spec：`.omx/plans/test-spec-*.md`

`.omx` 里的计划文件是 formal chain 产物，不是 current-standard 本身。

---

## 5. verification doctrine

验证顺序固定为：

1. **local/minimal**
2. **shortest relevant chain**
3. **formal chain only when required**

### 5.1 local/minimal

先证明 leaf 自己没坏。

例子：

- `platform-web-vue`：先看自己的 payload 归一化、endpoint 归一化、页面本地服务调用
- `runtime-service`：先看自己的 runtime context 解析、settings 解析、middleware 装配

### 5.2 shortest relevant chain

只有当本地证明不够，才走最短相关链。

例子：

- `platform-web-vue -> platform-api-v2`
- `platform-api-v2 -> runtime-service`

### 5.3 formal chain only when required

只有以下情况才上 formal chain：

- 要改标准
- 要改边界
- 要交 formal artifact
- 要给外部审核或发布门禁

不要因为“更稳妥”就默认升级到 formal chain。

---

## 6. leaf 本地 authority / resolver

leaf 先管 leaf 的事。

### 6.1 `platform-web-vue`

`platform-web-vue` 不能只按“前端规范”一个粗桶判断，必须按更窄的 leaf concern 解析：

#### Leaf A：页面 archetype / UI composition / template choice
- `docs/platform-web-sub2api-migration/14-frontend-development-playbook.md`
- 适用于：
  - 这是 list / detail / create / workspace / resource 哪类页面
  - 该复用哪组共享组件与页面骨架
  - 页面结构和视觉/交互模板怎么选

#### Leaf B：formal control-plane page behavior
- `apps/platform-web-vue/docs/control-plane-page-standard.md`
- 适用于：
  - 页面 service / state / permission / audit / page shell 规则
  - 正式控制面页面有哪些禁止项
  - formal page 行为如何遵守平台规则

#### `platform-web-vue` resolver rule
- 如果问题是 **“这是什么页面、应该用哪种页面骨架/组件组合？”**
  - 先读 **frontend playbook**
- 如果问题是 **“这个正式页面在 service/state/permission/audit 上必须怎么做？”**
  - 先读 **control-plane page standard**
- 如果两者都涉及：
  - 先用 playbook 选 page archetype
  - 再用 control-plane standard 收 formal page behavior

### 6.2 `runtime-service`

`runtime-service` 的本地 authority 主要在：

- `apps/runtime-service/runtime_service/docs/standards/*.md`
- `apps/runtime-service/runtime_service/tests/harness/*.py`

这里的 authoritative leaf 先是标准和 harness checks；具体代码实现只能作为**事实样本**，不能反过来升级成 current-standard 本身。

### 6.3 `platform-api-v2`

`platform-api-v2` 的 leaf authority 不能只收成“control-plane 后端”一个粗桶。

#### Leaf A：control-plane module / ownership / code-shape
- `apps/platform-api-v2/docs/handbook/project-handbook.md`
- `apps/platform-api-v2/docs/handbook/development-playbook.md`
- 适用于：
  - 这个能力应落在哪个模块
  - handler / use case / repository / adapter 如何分工
  - 哪层拥有该行为

#### Leaf B：permission / audit / operation governance
- `apps/platform-api-v2/docs/standards/permission-standard.md`
- `apps/platform-api-v2/docs/standards/audit-standard.md`
- `apps/platform-api-v2/docs/standards/operations-standard.md`
- 适用于：
  - 谁能做
  - 如何追责
  - 长任务是否必须进入 operation

#### Leaf C：runtime gateway / formal management interface
- `apps/platform-api-v2/docs/standards/runtime-gateway-interface-standard.md`
- 适用于：
  - 正式平台接口如何暴露 runtime 能力
  - 项目边界与 runtime gateway 的治理边界
  - 平台管理接口与 runtime public contract 的受管面判断

#### `platform-api-v2` resolver rule
- 如果问题是 **“这个能力应该落在哪个模块、怎么分层？”**
  - 先读 **Leaf A**
- 如果问题是 **“谁能做、怎么记审计、是否必须走 operation？”**
  - 先读 **Leaf B**
- 如果问题是 **“这个正式管理接口 / runtime gateway 对外该怎么表现？”**
  - 先读 **Leaf C**

### 6.4 `runtime-web`

`runtime-web` 的 current-standard 先收成 debug shell，而不是正式平台页。

#### Leaf A：debug-shell role / UI boundary
- `apps/runtime-web/docs/standards/runtime-web-debug-standard.md`
- 适用于：
  - `runtime-web` 应不应该承接这个交互
  - 它是不是会漂移成正式平台入口
  - run context / debug mode / artifact context 这类调试壳边界

#### Leaf B：runtime behavior truth
- `apps/runtime-service/runtime_service/docs/standards/*.md`
- `apps/runtime-service/runtime_service/tests/harness/*.py`
- 适用于：
  - 真正的 runtime contract / graph / tool / middleware 行为

#### `runtime-web` resolver rule
- 如果问题是 **“这个能力该不该放在调试壳？”**
  - 先读 **Leaf A**
- 如果问题是 **“runtime 真正的 contract 行为是什么？”**
  - 转到 **Leaf B**
- 如果问题已经变成正式平台页：
  - 转回 `platform-web-vue` 的 leaf resolver

### 6.5 `interaction-data-service`

`interaction-data-service` 的 leaf authority 要把 **当前 API 真相** 和 **结果域边界** 分开看。

#### Leaf A：current API / resource / payload truth
- `apps/interaction-data-service/docs/test-case-service-api-design.md`
- 适用于：
  - 当前资源
  - 当前 payload / route / field / table 语义

#### Leaf B：result-domain ownership / formal access chain
- `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md`
- `apps/interaction-data-service/README.md`
- `apps/interaction-data-service/docs/README.md`
- 适用于：
  - 结果域边界
  - 平台访问是否必须经由 `platform-api-v2`
  - runtime 写入和平台读取的正式关系

#### Leaf C：background design / future abstraction
- `apps/interaction-data-service/docs/service-design.md`
- 适用于：
  - 为什么结果域应该独立存在
  - 未来如何继续抽象
  - 不直接作为当前实现真相

#### `interaction-data-service` resolver rule
- 如果问题是 **“当前接口/资源/字段到底是什么？”**
  - 先读 **Leaf A**
- 如果问题是 **“这东西应不应该归结果域拥有、平台怎么访问它？”**
  - 先读 **Leaf B**
- 如果问题是 **“未来还能怎么继续抽象？”**
  - 再读 **Leaf C**

### 6.6 leaf 之间怎么对齐

leaf 之间只在最短相关链里对齐。  
不要把一个 leaf 的本地代码实现直接写成另一个 leaf 的默认标准。  
本文负责 **resolver 路由**，不是把代码文件抬成标准文档。

---

## 7. 什么时候读 broad 文档

只有在下面情况才回到 broad 文档：

- 想知道为什么仓库是这种分层
- 想看 L1-L4 Harness 解释
- 想补背景，不是要做当前标准判断

对应文档：

- `docs/development-paradigm.md`
- `docs/knowledge/02-aitestlab-harness-blueprint.md`

如果你要的是“现在到底怎么判”，停在本文即可。
