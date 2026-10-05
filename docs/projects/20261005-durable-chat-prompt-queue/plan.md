# Chat 持久消息队列 - 整体方案

> 2026-10-05 用户明确批准实施；下述为批准设计，实际完成情况见 tasks.md。

## 目标和产品边界
用户明确提交并收到服务端确认的消息，即使切换会话、离开聊天页、刷新、退出浏览器，也由后端继续执行。同会话逐轮串行，不同会话可并行；每条补充消息是独立下一轮，不改成向当前 Run 注入上下文。

未提交草稿不执行。浏览器退出不等同撤销任务；权限被明确收回、审批待处理、显式取消具有独立语义。网络故障不得伪装成撤权，也不得在无法确认授权时先执行工具。

## 已核对的事实
| 位置 | 当前行为与缺口 |
| --- | --- |
| `apps/platform-web/src/modules/chat/composables/usePromptQueue.ts` | 仅 localStorage；enqueue/dequeue/reorder 均本地操作 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | `drainNextQueuedItem()` 由页面 watch 驱动发送；卸载后无人发送 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | `launch_runtime_run()` 已持久化幂等请求并透传显式 multitask_strategy；默认 reject，并非完全不支持 enqueue |
| GraphHarbor `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/run_store.py` | `create()` 已支持 pending Run；`claim_next()` 排除 running/rollback，但没有 Thread interrupts 守卫；created_at + skip_locked 不能直接宣称多 Worker 严格 FIFO |
| GraphHarbor `libs/langhost/src/langhost/core_api.py` | `_cancel_row()` 允许取消 running；取消任意 pending 也会设 thread.status=idle，不能直接当“仅移除待执行项”接口 |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py` | 已支持带当前 Runtime HMAC 的延迟模型引用兑换；服务层仍复核当前身份、线程、Agent、模型权限，无需放宽现有引用或用户令牌过期检查 |
| `apps/runtime-service/src/runtime_service/messaging/inbox.py` | 当前 Run 内注入消息，与本次独立下一轮队列语义不同，不作为实现基础 |

## 方案

### 1. 提交和恢复
- 保留 `POST /threads/{thread_id}/runs`，排队显式传 `multitask_strategy=enqueue`，常规请求默认 reject 不改。
- 复用 `run-actions.ts` 的幂等约定：每个动作固定 message_id、key、body。输入、Agent、模型/config 在提交时冻结，不受后续页面选择影响。
- 收到 run_id 才显示“已排队”；请求尚未完成显示“提交中”，丢响应显示“结果待确认”。未知结果复用原 key/body 对账，禁止换 key 自动重发。
- 未确认动作的最小快照保存在本地，仅用于对账，不在本地安排下一轮执行。服务端 Run 才是排队状态事实源。
- Runs 查询恢复 pending、running、失败和审批状态，正确分页；前端不只选第一个 active 就丢掉其他 pending。后台不为每个排队项建立 SSE。
- 旧 `prompt_queue:*` 保留为明确标识的“未提交草稿”，用户可恢复后手动提交；不静默重发，也不删除用户内容。此前获准删除的是未知 Redis 流缓存，不适用于本地草稿。

### 2. 顺序、审批与恢复
- 复用 Run 表、Worker、Lease/Reaper；PostgreSQL 为事实源，Redis 只作唤醒/事件缓存。Redis 丢失唤醒不丢已提交任务。
- 同 Thread 的 claim/create/取消/调序统一锁顺序，避免当前 run→thread 与 thread→run 交叉造成死锁；领取队首前在锁内复核状态，不跳过正在重试或暂不可执行的队首。
- 保留现有上移/下移功能：为 Run 增加可空 `queue_position`，在 Thread 锁内分配和交换；旧 pending 以 created_at/run_id 确定顺序，迁移验证后填充。仅未领取项可调序，不修改 created_at、不取消再建 Run。
- Thread 存在未处理 interrupts 时普通 queued Run 停留 pending。合法 resume 仍需平台审批权限和准确 interrupt ID，允许越过普通等待项解除中断，不能被已有 pending 的 reject 检查挡死。
- Worker 重启复用原 Run/checkpoint，不创建重复消息。不能承诺外部工具副作用天然 exactly-once；本项目保证幂等入队和消息 ID 去重，副作用沿用现有工具幂等/恢复契约。
- 普通业务失败保留失败回执，随后独立消息可继续；授权服务暂不可用时使用有界退避，队首等待、不允许后面的消息抢跑。超出重试预算保留失败回执，不自动无限重试。

### 3. 取消、清空和恢复草稿
- 现有“停止当前生成”保持显式取消当前 Run；不暗中清空其他已确认消息，界面明确提示后续队列仍会继续。
- 待执行项的删除/恢复草稿使用服务端 pending 条件取消：锁内检查；若已领取则 409 并刷新状态，不能意外杀掉已经开始的 Run。
- 清空只取消请求时的待执行项，服务端事务内核对队列版本；并发入队/领取造成冲突时刷新后重试，不宣称全部清空成功。
- 恢复草稿必须先确认 pending 取消成功，再把内容放入输入框；取消未知不恢复为可再次发送的草稿。保留已存在的输入内容，避免覆盖丢失。
- 同 Thread 有其他 active 或 interrupts 时取消 pending 不得改写成 idle；真正停止 running 后，下一轮启动仍须等待执行租约/停止确认，防止两轮工具并发。

### 4. 权限与受信执行
- 入队、读队列、调序、删除分别复用现有 Thread 写/读/编辑权限及项目隔离；不能让浏览器注入 owner、内部授权引用或排序位置。
- 每轮开始前复核当前身份/Thread/Agent/工具策略，模型连接兑换沿用现有 HMAC + 当前权限校验。明确撤权的项不执行，返回可识别失败原因。
- 受信身份来自服务端保存的运行上下文，业务授权逻辑留在 platform-api/runtime-service；GraphHarbor 只承载通用调度/执行入口，不加入平台用户或模型概念。
- 不在每个 token 或页面切换重查全套权限；授权查询失败保留队列、暂停执行并有界重试，不伪造 403，也不使用过期授权快照启动新轮次。
- 无模型图和缓存模型路径同样需要执行前检查，不能只依赖“恰好首次兑换模型”。执行中 Run 的连续撤权策略不在本次扩展，沿用当前规范。

## 公开契约与标准同步
- 创建 Run 使用已有 enqueue 字段，ACK 仍是原 run_id，服务端入队成功不等于生成完成。
- 新增受控 `POST /threads/{thread_id}/runs/queue` 队列操作：`operation=cancel|reorder`，携带 expected_run_ids 和目标 IDs/顺序；校验同 Thread、仅 pending、版本一致，冲突 409。不增加独立队列存储。
- Runs 读接口需可恢复消息预览及 queue_position，沿用内部字段脱敏，不返回受信 token、模型引用或凭据。
- 更新 `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` 的接口清单、并发策略和取消语义；GraphHarbor 更新对应 Core 契约。现有“首期 reject”是本次拟扩展点，评审前不改生效标准。

## 范围、发布与回退
- 范围包括平台三服务、GraphHarbor 通用队列/审批修复、前端原有队列操作和真实端到端验收。
- 采用兼容性字段迁移，不删历史 Run；先在隔离库验证，再发布双包并升级本地 Runtime，最后启用前端入队。发布和数据库实施范围随本方案一并评审，远端生产部署另行明确环境。
- 回退先停止新 enqueue 提交；已接收 pending 由修复后的 Worker 排空或经明确操作取消，再回退 UI/API。存在 pending 时禁止直接回退旧 Worker，避免审批/FIFO 缺口重新出现。
- 不自动把已有会话全部重跑，不增加第二套调度服务，不全局提高 Worker 并发或 Redis 内存限额。

## 人工评审项
确认以上独立下一轮、审批阻塞、停止当前不清空后续、失败继续/临时鉴权故障等待、旧草稿不自动执行，以及 GraphHarbor 字段迁移/本地升级的方案。批准后实施；实际实现如发现新的安全契约冲突，再单独提出具体差异。
