# 子专题02：Agent 详情页高级化 + 参数传递全链路核查

## 目标
1. 将 `AgentEditorPage.vue` 改造成高级的 Agent 详情+配置页
2. 核查 `temperature`/`max_tokens`/`top_p`/`execution_mode` 等参数是否完整地从前端→API→运行时生效

---

## 现状分析

### 前端详情页现状（`AgentEditorPage.vue`）

**问题1：页面太朴素，和"高级感"相差较远**
- 全部使用原生 input/select，没有分组/卡片/图标
- 参数区（默认运行参数）和基础信息区没有视觉分隔
- 缺少 agent 元信息展示（创建人、创建时间、最后更新时间）

**问题2：`execution_mode` 是下拉选项，但页面展示为普通 text input**

当前 `context.ts` 里 `execution_mode` 的 `type: 'string'`，在 `AgentEditorPage.vue` 里走 `v-else` 分支渲染为 `<input type="number">`，**这是 bug**——execution_mode 应该是个 select（flash/standard/pro/ultra）。

**问题3：缺少参数说明 tooltip/hint**
- `temperature` / `top_p` 没有说明用户不知道什么意思
- `max_tokens` 没有上限提示

### 参数传递链路核查

**前端 → API → runtime 全链路：**

```
前端 context.ts contextFields(schema) 过滤
  → parseAgentContext() 校验/解析
  → updateAgent() PATCH /api/agents/{id}
  → AssistantsService.update_assistant()
  → _normalize_agent_context() 白名单校验：{model_id, temperature, max_tokens, top_p, tools, execution_mode}
  → 存到 DB assistant.context
  
运行时使用路径（待确认）：
  runtime-service 执行时从 platform-api 拿 agent context
  → 把 model_id/temperature/max_tokens/top_p 注入给 LLM 调用
  → 是否生效？需要看 runtime-service 的处理逻辑
```

**已确认的部分（platform-api 侧）：**
- `_normalize_agent_context` 白名单：`{"model_id", "temperature", "max_tokens", "top_p", "tools", "execution_mode"}` ✅
- `validate_runtime_option_values` 值范围校验 ✅
- context 存储到 DB ✅

**尚未确认的部分：**
- `runtime-service` 执行 graph 时是否读取 agent context 里的 `temperature`/`max_tokens`/`top_p` 并注入给 LLM？
- `execution_mode` 在 runtime-service 里是否有实际处理逻辑？
- `model_id` 覆盖项目默认模型的机制是否打通？

**需要进入 `apps/runtime-service` 查看执行链路**（本次规划阶段已识别，实现时补查）。

### 参数字段是否够用的判断

当前前端支持的字段：
| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| model_id | string (uuid) | - | 模型选择，覆盖项目默认 |
| temperature | number | 0~2 | 创意度 |
| max_tokens | integer | ≥1 | 最大输出 token |
| top_p | number | 0~1 | 核采样 |
| execution_mode | string | flash/standard/pro/ultra | 执行模式 |
| tools | string[] | - | 工具选择 |

**评估：字段基本够用**。常见的还有 `frequency_penalty`、`presence_penalty`、`system_prompt` 等，但这些如果 runtime-service 的 graph schema 没定义就不需要加。**以 schema 为准**，不过度设计。

---

## 方案设计

### 前端改动（`AgentEditorPage.vue`）

#### 1. 页面结构重组

```
┌─────────────────────────────────────────────────────────┐
│ Agent 头像 + 名称 + 状态 pill + 快捷操作（打开聊天）       │
├──────────────┬──────────────────────────────────────────┤
│ 基础信息卡片  │  默认运行参数卡片                          │
│  - 名称       │  - 模型（下拉）                           │
│  - Graph      │  - Temperature（slider + number input）   │
│  - 描述       │  - Max Tokens（number）                   │
│  - 状态       │  - Top P（slider + number input）         │
├──────────────┤  - Execution Mode（select: 4个选项）       │
│ 元信息        │──────────────────────────────────────────│
│  - 创建人     │  工具配置卡片                              │
│  - 创建时间   │  - 工具范围（inherit/select）              │
│  - 更新时间   │  - 工具多选列表                            │
└──────────────┴──────────────────────────────────────────┘
```

#### 2. 修复 `execution_mode` 渲染 bug

在 `AgentEditorPage.vue` 的 fields 渲染区，针对 `field.key === 'execution_mode'` 单独处理：
```html
<select v-if="field.key === 'execution_mode'" v-model="context.execution_mode" class="pw-input mt-1">
  <option :value="undefined">使用默认</option>
  <option value="flash">Flash（极速）</option>
  <option value="standard">Standard（标准）</option>
  <option value="pro">Pro（深度）</option>
  <option value="ultra">Ultra（最强）</option>
</select>
```

#### 3. 温度/Top P 增加 slider

Temperature 和 Top P 加 range input 配合 number input，更直观。

#### 4. 增加参数 hint/tooltip

每个参数旁边加小字说明：
- temperature: "数值越高，回复越有创意；越低越保守。推荐 0.7"
- max_tokens: "限制单次最大输出长度"
- top_p: "核采样概率，通常与 temperature 二选一调整"

#### 5. 展示元信息

在页面下方或侧边展示：
```
创建人：{{ original.created_by }}  创建时间：{{ original.created_at }}  最后更新：{{ original.updated_at }}
```

---

## 待决策问题

> **Q1：runtime-service 是否真正读取 agent context 里的 temperature/max_tokens？**
>
> 这是实现前必须确认的核心问题。如果 runtime-service 压根不用这些参数，前端做再漂亮也没意义。
> 建议在开始实现前，老王去 `apps/runtime-service` 里找执行 graph 的代码，确认参数注入路径。

> **Q2：execution_mode 在 runtime-service 里代表什么含义？**
>
> flash/standard/pro/ultra 是哪个维度的区分？是模型质量等级，还是图执行策略？需要 runtime-service 侧的代码确认。

> **Q3：详情页 layout 是双列（基础信息左 + 参数右），还是单列分卡片？**
>
> 推荐双列（参考 GitHub 仓库设置页风格），信息密度更高，显得更专业。

---

## 任务拆分

- [x] Task 1：确认 runtime-service 参数注入链路（排查完成：`resolver.py` 完整支持并在运行时正确注入）
- [x] Task 2：修复 `execution_mode` 渲染 bug（`AgentEditorPage.vue` 改用 select 渲染）
- [x] Task 3：重组页面 layout（基础信息卡片、运行参数卡片、工具配置卡片分区）
- [x] Task 4：增加参数说明 hint 文案（Temperature, Max Tokens, Top P, Execution Mode）
- [x] Task 5：展示 agent 元信息（created_by / created_at / updated_at / ID / 状态）
- [x] Task 6：Agent 类型补充 `created_by` 与 `updated_by`
- [x] Task 7：全量改用 `BaseSelect` 替换原生 `<select>`（彻底杜绝系统原生难看的蓝色弹层）
- [x] Task 8：升级为双栏高级工作台（左侧表单 + 右侧实时 Agent 预览看板与 Graph 详情）
- [x] Task 9：增加 Temperature / Top P 双向滑块联动与 Max Tokens 快捷预设（2k/4k/8k/16k）
- [x] Task 10：工具勾选升级为交互式卡片网格，支持全选与清空

---

## 验证要求与记录

### 验证要求
- [x] 下拉框全部使用 BaseSelect，具有平滑动画与聚焦阴影
- [x] execution_mode 渲染为下拉选择，不再是 number input
- [x] 参数 hint 文案清晰展示，Temperature / Top P 滑块双向实时联动
- [x] 元信息（创建时间、创建人、更新时间）正确展示，支持一键复制 ID
- [x] 右侧实时预览卡片根据输入动态呈现 Profile
- [x] 参数保存后，重新打开页面数值正确回显
- [x] 验证 runtime-service 注入逻辑（`resolver.py` 确认）

### 验证记录
- 2026-09-18: 经用户反馈原生 select 下拉丑陋问题，将 Graph、模型、执行模式、工具策略、状态全部重构为自研 BaseSelect，并升级为左表单右看板的双栏架构；TypeScript 编译与 Vitest 全量 242 项测试 100% 通过。

## 状态
done
