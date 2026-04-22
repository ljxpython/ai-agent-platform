# Platform API 能力对账与收口清单

这份文档只解决一个问题：

> `apps/platform-api` 已经做出来的后端能力，哪些已经被 `apps/platform-web` 正式消费，哪些只是弱接入，哪些应该暂时收成 internal，哪些前端抽象应该继续清理。

这不是阶段纪要，而是控制面进入稳定期后的正式收口文档。

## 1. 当前结论

当前不是“后端做了很多废接口，前端根本没用上”。

真实情况是：

- 平台治理主链路已经基本接通
- Agent 运行工作台主链路已经接通
- `runtime_gateway` 的高级 API 面明显超前于当前前端产品面
- 前端权限体系和少数页面入口还没有完全跟上
- 前端还残留一批过渡期抽象和重复 service，需要继续收口

一句话总结：

> 主链路已经成立，但还没有完成“正式能力边界冻结”。

## 2. 已经被前端正式消费的能力

以下能力已经形成“后端模块 + 前端页面/工作台”的正式链路，应该保留并继续产品化。

### 2.1 身份与会话

- 登录
- 登出
- 刷新 token
- 当前用户资料
- 修改个人资料
- 修改密码

对应模块：

- `identity`

对应前端场景：

- 登录页
- 个人信息页
- 安全设置页
- 全局会话续期

### 2.2 平台治理主数据

- 用户管理
- 项目管理
- 项目成员管理
- 服务账号管理
- 公告管理
- 审计日志

对应模块：

- `users`
- `projects`
- `service_accounts`
- `announcements`
- `audit`

对应前端场景：

- 用户列表 / 详情 / 新建
- 项目列表 / 创建 / 详情 / 成员
- service account 列表、token 创建与吊销
- 公告中心与公告管理页
- 审计日志页

### 2.3 Agent 治理与运行目录

- assistant 列表、创建、详情、更新、删除
- assistant 参数 schema
- runtime models / tools / graphs 目录查询与刷新
- 项目级 runtime policies

对应模块：

- `assistants`
- `runtime_catalog`
- `runtime_policies`

对应前端场景：

- 助手管理
- 图谱列表
- Runtime 页面
- Runtime Policies 页面

### 2.4 运行工作台

- thread 列表
- thread 详情
- thread 历史
- thread 状态
- 新建 thread
- 发起 run stream
- 取消 run
- 更新 thread state
- 删除 thread
- Chat 页面
- SQL Agent 页面

对应模块：

- `runtime_gateway`
- LangGraph SDK 直连适配层

对应前端场景：

- `/workspace/chat`
- `/workspace/threads`
- `/workspace/sql-agent`

### 2.5 长任务与控制面运维

- operation 列表
- operation 详情
- operation 实时流
- operation 取消
- operation 批量取消 / 归档 / 恢复
- operation artifact 下载
- operation 过期产物清理
- system live / ready / health / metrics
- platform config / feature flags

对应模块：

- `operations`
- `_system`

对应前端场景：

- `/workspace/operations`
- `/workspace/system-governance`
- `/workspace/platform-config`
- `/workspace/control-plane`

### 2.6 Testcase 结果域控制面

- overview
- role
- batches
- documents 列表
- documents relations
- documents preview / download / export
- cases 列表 / 详情 / 新增 / 编辑 / 删除 / 导出
- batch detail

对应模块：

- `testcase`

对应前端场景：

- `/workspace/testcase/generate`
- `/workspace/testcase/documents`
- `/workspace/testcase/cases`

## 3. 已经接入，但仍然属于“弱接入”的地方

这些不是没接，而是接得还不够规范。

### 3.1 权限体系

后端已经有明确的权限和角色模型，但前端现在还没有统一的消费层。

现状：

- 路由层主要校验登录态
- 导航层没有按权限裁剪
- 页面层只有少量局部角色判断
- 工作台场景较多依赖后端 `403` 再展示提示

这意味着：

- 真正的安全仍由后端兜底
- 前端还没有完成“权限标准落地”

这部分必须继续补齐，但不影响当前后端模块本身的成立。

### 3.2 SQL Agent 页面

当前 SQL Agent 不是独立后端业务模块，而是：

- 复用通用 chat 基座
- 固定目标到 `graph: sql_agent`

这条设计是合理的，但要明确它的语义：

- 它是正式产品入口
- 但它不是新的后端领域模块

### 3.3 Control Plane 页面

当前 Control Plane 主要是聚合页，不是独立后端域。

它聚合了：

- platform config
- operations
- audit
- service accounts
- probes / health

这页应该保留，但要明确它的定位是“控制面首页”，不是新的控制面资源域。

## 4. 后端存在，但当前前端没有正式产品面的能力

这部分不应该继续伪装成“已经完成的正式前端能力”。

建议统一标记为：

> internal / reserved capability

### 4.1 项目删除

后端已有：

- `DELETE /api/projects/{project_id}`

当前状态：

- 前端没有正式入口
- 前端 service 也没有对等 delete 能力

建议：

- 如果近期需要项目治理闭环，就补正式删除入口
- 如果近期不做，就在文档中明确为“后端已具备，前端未开放”

### 4.2 Runtime Gateway 高级能力

当前 `runtime_gateway` 暴露出的高级能力明显多于前端产品面。

后端已具备但前端未正式产品化的能力包括：

- `GET /api/langgraph/info`
- `POST /api/langgraph/graphs/search`
- `POST /api/langgraph/graphs/count`
- `POST /api/langgraph/threads/prune`
- `PATCH /api/langgraph/threads/{thread_id}`
- `POST /api/langgraph/threads/{thread_id}/copy`
- `GET /api/langgraph/threads/{thread_id}/state/{checkpoint_id}`
- `POST /api/langgraph/runs`
- `POST /api/langgraph/runs/stream`
- `POST /api/langgraph/runs/wait`
- `POST /api/langgraph/runs/batch`
- `POST /api/langgraph/runs/cancel`
- `POST /api/langgraph/runs/crons`
- `POST /api/langgraph/runs/crons/search`
- `POST /api/langgraph/runs/crons/count`
- `PATCH /api/langgraph/runs/crons/{cron_id}`
- `DELETE /api/langgraph/runs/crons/{cron_id}`
- `POST /api/langgraph/threads/{thread_id}/runs`
- `POST /api/langgraph/threads/{thread_id}/runs/stream`
- `POST /api/langgraph/threads/{thread_id}/runs/wait`
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}`
- `GET /api/langgraph/threads/{thread_id}/runs`
- `DELETE /api/langgraph/threads/{thread_id}/runs/{run_id}`
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/join`
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/stream`
- `POST /api/langgraph/threads/{thread_id}/runs/crons`
- `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`

这些能力不是错误设计。

问题在于：

- 现在没有对应的正式前端页面
- 没有明确的产品语义
- 没有冻结哪些是 public，哪些是 internal

正式收口建议：

1. 当前工作台必需能力继续保留为正式 public 能力
2. 其余高级能力先标记为 internal
3. 后续只有在出现明确产品页面时，才升级成正式 public 模块能力

### 4.3 Testcase Document Detail

后端与前端 service 都已经支持：

- `GET /documents/{document_id}`

但当前页面主要使用的是：

- 列表
- relations
- preview
- download

是否保留这条 detail 能力，应该二选一：

- 补一个正式文档详情抽屉
- 或删除前端未使用 service，避免假能力

## 5. 前端应该继续补齐的能力

这些不是“后端没做好”，而是前端产品面还需要继续完成。

### 5.1 统一权限消费层

必须补：

- 权限 store
- `can()` 或等价能力判断入口
- route meta 权限配置
- 侧边栏导航裁剪
- 页面级 action gate

目标是把后端的权限标准，真正变成前端可执行的统一规则。

### 5.2 项目删除入口

如果项目治理页要完整闭环，就应该补：

- 项目删除动作
- 删除前确认
- 删除后的重定向和上下文重置
- 审计与错误提示联动

### 5.3 项目角色命名统一

前端当前仍残留旧命名：

- `admin`
- `editor`
- `executor`

后续应与 V2 最终标准保持一致，避免前后端词汇体系分裂。

### 5.4 文档详情是否产品化

Testcase 文档当前已有：

- 预览
- 下载
- 关联关系

但没有完整详情页语义。

需要明确：

- 是否需要单独的文档详情能力
- 如果不需要，就不要继续保留未消费的死 service

## 6. 前端需要继续清理的抽象和技术债

### 6.1 重复的 identity service

当前 `users.service.ts` 中仍保留了：

- `getMe`
- `updateMe`

但正式个人资料链路已经走：

- `identity.service.ts`

这类重复 service 会误导后续开发者，应该收敛成一套正式入口。

### 6.2 过时的 `legacy | runtime` 兼容壳

多个 service 还保留：

- `mode: 'legacy' | 'runtime'`

但大多数地方已经不再真的分流。

这些过渡期参数如果长期保留，会导致：

- 新人误以为还有双后端切换逻辑
- 页面继续写兼容分支
- service 语义越来越虚

建议：

- 对已经完成切换的模块，逐步删除这类兼容壳

### 6.3 过度包装的 runtime project context

当前前端有一套：

- `runtimeProjectId`
- `runtimeScopedProject`
- `runtimeProjects`

但在多数场景下，本质仍然是当前项目上下文的别名。

后续要么：

- 真正做独立 runtime scope

要么：

- 把抽象收敛回统一项目上下文

不要长期停留在“看起来很高级，实际上只是别名”的状态。

### 6.4 权限字段压扁

当前前端把后端的 `platform_roles` 压成：

- `is_super_admin`

这会直接削弱 V2 权限模型。

建议：

- 前端保留完整角色集合
- 页面通过统一权限能力层消费
- `is_super_admin` 只能作为派生展示字段，不能继续充当权限主模型

## 7. 正式收口原则

后续所有控制面能力都按下面三类管理：

### 7.1 正式产品能力

满足以下条件才算正式：

- 有稳定后端契约
- 有前端正式页面或工作台入口
- 有明确权限语义
- 有审计语义
- 不是临时演示壳

### 7.2 Internal 能力

满足任一条件就先归 internal：

- 当前没有正式前端产品面
- 仍然用于调试或底层编排
- 暂时只服务于内部链路
- 契约还没准备冻结

### 7.3 待删除或待收敛能力

满足任一条件就进入清理列表：

- 前端 service 存在但没有页面消费
- 新旧 service 重复
- 仍保留历史兼容参数但已无实际意义
- 抽象复杂度明显高于业务收益

## 8. 推荐执行顺序

建议按下面顺序继续收口：

1. 冻结“正式 public 能力 / internal 能力”边界
2. 清理前端重复 service 与无效兼容参数
3. 补统一权限消费层
4. 决定项目删除和 testcase document detail 是否产品化
5. 再决定 `runtime_gateway` 哪些高级能力值得继续上前端页面

## 9. 后续新功能的判断规则

以后新增控制面能力时，先问 4 个问题：

1. 这是不是正式产品能力，还是 internal 能力？
2. 它有没有明确前端入口和产品语义？
3. 它的权限和审计语义有没有定清楚？
4. 它是不是只是为了“以后可能会用”而提前暴露？

只要第 4 条回答是“是”，就先别把它包装成正式能力。

## 10. 最终判断

当前 `platform-api` 的主链路设计是成立的。

接下来不该再做“大拆大改”，而应该做：

- 能力边界冻结
- 前端消费层补齐
- internal 与 public 分层
- 过渡期抽象清理

这样后续无论接 PostgreSQL、Redis、对象存储，还是继续把旧服务能力迁进来，都不会再把控制面重新搞成一锅粥。
