# W1 阶段实现记录：会话与交互底座闭环 (T1.1 ~ T1.5)

## 1. 概述与目标
本阶段针对 DearFlow 前端会话底座进行工程加固与契约对齐，全面达成以下 5 项任务目标：
1. **T1.1 四模式切换与配置透传**：支持 `flash`/`standard`/`pro`/`ultra` 模式，前端选择联动有界 100 步预算（`recursion_limit=100`），会话运行中与待审批状态下锁定模式切换。
2. **T1.2 七字段官方澄清卡片完善**：卡片完整渲染并校验 7 类字段（`text`/`textarea`/`number`/`select`/`multi_select`/`checkbox`/`date`），`false` 判定为合法布尔回答，类型自动规范化。
3. **T1.3 工具审批面板与参数编辑**：消费官方 `action_requests` 协议，支持 `approve`/`edit`/`reject`，参数修改进行深度结构与类型安全校验，阻止审批期间普通消息穿透。
4. **T1.4 基础附件与原字节下载**：放行 `/workspace/outputs/` 和 `/workspace/uploads/` 两类沙箱路径，扩展 ZIP/XLSX/HTML/CSS/JS 等文件类型，二进制文件拦截文本乱码直接安全下载。
5. **T1.5 测试与类型安全闭环**：通过所有相关前端单测与 `vue-tsc --noEmit` 全量静态检查。

---

## 2. 涉及改动文件清单

| 文件路径 | 改动性质 | 核心职责 |
|---|---|---|
| `apps/platform-web/src/services/agents/types.ts` | 契约更新 | `AgentContext` 扩展 `execution_mode?: 'flash' \| 'standard' \| 'pro' \| 'ultra'` |
| `apps/platform-web/src/services/agents/context.ts` | 解析更新 | `parseAgentContext` 增加 `execution_mode` 白名单校验与透传 |
| `apps/platform-web/src/services/agents/context.spec.ts` | 单元测试 | 验证 `execution_mode` 解析、默认回退与非法值过滤 |
| `apps/platform-web/src/modules/dear-agent/components/ChatRunOptionsDialog.vue` | UI 增强 | 增加四运行模式选择卡片、模式介绍、有界步数提示与锁定保护 |
| `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue` | 状态与交互 | 增加顶部执行模式状态胶囊、运行时参数联动（pro/ultra 强制 `recursion_limit=100`）、对话框属性绑定 |
| `apps/platform-web/src/modules/dear-agent/human-input.ts` | 核心逻辑 | 完善七字段验证、布尔值边界防御、类型规范化 `normalizeClarificationValues`，兼容 `type/kind` 澄清中断 |
| `apps/platform-web/src/modules/dear-agent/human-input.spec.ts` | 单元测试 | 覆盖全部 7 类字段、布尔合法值、日期格式、数字转换测试 |
| `apps/platform-web/src/modules/dear-agent/components/ClarificationCard.vue` | UI 组件 | 支持 7 类字段模板渲染，修复 `v-model` 类型安全问题 |
| `apps/platform-web/src/modules/dear-agent/approvals.ts` | 协议解析 | 完善工具审核决策生成 `buildReviewResponses` 与多层参数修改校验 |
| `apps/platform-web/src/modules/dear-agent/approvals.spec.ts` | 新增单测 | 覆盖审批、参数编辑防注入、拒绝附带原因及非法中断过滤 5 项测试 |
| `apps/platform-web/src/utils/chat-content.ts` | 工具函数 | 扩充支持 ZIP、XLSX、XLS、HTML、CSS、JS 等文件 MIME 识别 |
| `apps/platform-web/src/services/threads/files.service.ts` | 接口服务 | 放行 `/workspace/outputs/`，对二进制文件拦截文本预览并走原字节下载 |
| `apps/platform-web/src/modules/dear-agent/components/ThreadFile.vue` | UI 组件 | 二进制文件隐藏不可用的纯文本预览按钮，仅展示下载操作 |

---

## 3. 验证结果

### 3.1 单元测试执行结果
```bash
rtk npm test -- src/modules/dear-agent/human-input.spec.ts src/services/agents/context.spec.ts src/modules/dear-agent/approvals.spec.ts --run
```
- `src/services/agents/context.spec.ts`: 1 passed
- `src/modules/dear-agent/human-input.spec.ts`: 5 passed
- `src/modules/dear-agent/approvals.spec.ts`: 5 passed
- **合计**：3 文件，11 测试，全部 100% 通过（0 failed）。

### 3.2 类型安全检查
```bash
rtk npm run typecheck (vue-tsc --noEmit)
```
- **检查状态**：全部通过，退出码 0，无任何 TypeScript 报错。

---

## 4. 结论与下一步
W1 阶段所有任务（T1.1 ~ T1.5）均已圆满交付并达标闭环。
后续可按排期推进 **W2：研究轨迹与子任务观测（T2.1 ~ T2.4）**。
