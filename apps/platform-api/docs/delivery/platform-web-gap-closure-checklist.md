# Platform Web 对齐与收口清单

这份清单用于收口 `apps/platform-api` 和 `apps/platform-web` 之间的正式能力边界，并修正当前前端中不合理、重复或过渡期残留的实现。

目标不是继续“堆功能”，而是把当前已经成立的控制面和正式前端宿主收成一套可以长期演进的标准范式。

## 1. 执行目标

- 冻结 `platform-api` 的正式 public 能力和 internal 能力边界
- 让 `apps/platform-web` 与当前后端正式能力一一对齐
- 清理前端中的重复 service、无效兼容参数和伪独立上下文抽象
- 把权限、导航、页面动作、工作台入口统一收进同一套前端范式
- 后续所有前端改动继续遵循既定的页面基座、组件封装和视觉规则

## 2. 范围说明

本清单只处理两类事情：

- `platform-api` 已存在能力的边界冻结与前端消费对齐
- `platform-web` 中与当前正式范式不一致的实现收口

本清单不处理：

- 新开一个新的正式前端宿主
- 回退到旧 `platform-api`
- 重新设计一套新的视觉系统
- 为了“未来可能会用”而继续扩口子

## 3. P0 能力边界冻结

- [x] 冻结 `platform-api` 的正式 public 能力范围：
  - `identity`
  - `users`
  - `projects`
  - `members`
  - `service_accounts`
  - `announcements`
  - `audit`
  - `assistants`
  - `runtime_catalog`
  - `runtime_policies`
  - `testcase`
  - `operations`
  - `_system`
  - `runtime_gateway` 的工作台必需子集
- [x] 冻结 `runtime_gateway` 的正式 public 子集：
  - thread 列表
  - thread 详情
  - thread 历史
  - thread 状态
  - 新建 thread
  - run stream
  - cancel run
  - update thread state
  - delete thread
- [x] 将 `runtime_gateway` 的高级能力统一标记为 internal：
  - `info`
  - `graphs search / count`
  - `threads prune / copy / patch / state@checkpoint`
  - 全局 `runs*`
  - `crons*`
  - 线程级 `run detail / list / delete / join / join-stream`
- [x] 明确 `project delete` 的产品命运：
  - 要么补前端正式入口
  - 要么明确“后端已具备，前端未开放”
- [x] 明确 `testcase document detail` 的产品命运：
  - 要么补正式详情能力
  - 要么清掉未消费的前端死 service

## 4. P0 前端架构收口

- [x] 补统一权限消费层：
  - 权限 store
  - `can()` 或等价能力判断
  - 路由 `meta` 权限配置
  - 侧边栏导航裁剪
  - 页面按钮级 action gate
- [x] 前端保留完整 `platform_roles` 与项目级角色能力，不再只靠 `is_super_admin`
- [x] 用户创建页 / 用户详情页支持显式平台角色绑定，不再只能靠 bootstrap admin 或旧 `is_super_admin`
- [x] 将前端项目角色命名对齐 V2 最终标准，不再长期保留旧口径
- [x] 收敛重复 identity 能力：
  - `users.service.ts` 中的 `getMe / updateMe`
  - `identity.service.ts`
  - 最终保留一套正式入口
- [x] 清理无实际分流意义的 `legacy | runtime` 过渡参数
- [x] 收敛 `runtimeProjectId / runtimeScopedProject / runtimeProjects` 这类伪独立上下文抽象
- [x] 保证所有页面只能通过统一 service/client 层访问 `platform-api`

## 5. P1 前端产品缺口补齐

- [x] 补项目删除的正式前端流程：
  - 删除入口
  - 二次确认
  - 删除成功后的上下文重置
  - 错误提示
  - 审计联动
- [x] 统一“无权限”体验：
  - 导航隐藏
  - 按钮禁用
  - 空态提示
  - `403` 文案
- [x] 评估并落地 `testcase document detail`，让文档域语义完整
- [x] 检查长任务是否统一走 `operations`
- [x] 检查 chat / sql-agent / threads 是否继续复用同一套通用 chat 基座

## 6. P1 前端范式约束

- [x] `apps/platform-web` 继续作为唯一正式前端宿主
- [x] 页面继续复用既有平台基座：
  - `PageHeader`
  - `TablePageLayout`
  - `FilterToolbar`
  - `DataTable`
  - `PaginationBar`
  - `BaseDialog`
  - `StateBanner`
  - `EmptyState`
- [x] 新功能优先复用现有平台组件，不允许为了单页再手搓一套壳子
- [x] 页面视觉继续跟当前正式风格保持一致，不允许重新引入新的模板感样式
- [x] 页面不直接判断底层服务地址或自行拼控制面 URL
- [x] Agent 工作台相关页面继续复用通用 chat 基座，不再维护第二套聊天页
- [x] 示例和资源库只能演示当前正式范式，不再保留过渡期写法

## 7. P2 文档与标准同步

- [x] 将 public / internal 边界同步回正式手册
- [x] 在前端开发范式文档中补权限接入规范
- [x] 在前端开发范式文档中补 service 层收敛规范
- [x] 将这份清单作为后续前端收口工作的唯一执行单

## 8. 验收标准

- [ ] 前后端权限语义一致，前端不再出现页面各自发挥的权限逻辑
- [ ] 主要治理页、工作台页、测试页全部跑在统一 service 结构上
- [ ] `public / internal` 能力边界在文档中明确，后续新功能不再随意扩口子
- [ ] 前端代码结构不再保留明显重复 service、无效兼容参数和伪独立上下文抽象
- [ ] 页面视觉、交互壳、表格壳、弹窗壳继续维持当前正式风格

## 9. 推荐执行顺序

1. 先完成 `P0 能力边界冻结`
2. 再完成 `P0 前端架构收口`
3. 然后完成 `P1 前端产品缺口补齐`
4. 最后完成 `P2 文档与标准同步`

## 10. 参考文档

- `../decisions/platform-capability-reconciliation.md`
- `../handbook/project-handbook.md`
- `../handbook/development-playbook.md`
- `./platform-web-capability-coverage.md`
- `./runtime-contract-three-wave-checklist.md`
- `./runtime-contract-manual-integration-checklist.md`

## 11. 当前执行单

- [x] 已建立文件级三波次执行清单：`./runtime-contract-three-wave-checklist.md`
- [x] 已建立手工联调清单：`./runtime-contract-manual-integration-checklist.md`
