# 可信契约与审计

## 目标

把用户选择转化为可授权、可撤销、可审计的服务端事实，避免浏览器伪造 `approval: never` 或恢复旧 run 时混用策略。

## 方案设计

### API 与数据流

```text
platform-web
  -> PATCH /api/langgraph/threads/{thread_id}/access-policy { policy }
platform-api
  -> 校验项目成员和 PROJECT_RUNTIME_WRITE
  -> 校验 graph 支持的档位并写入 thread.metadata.access_policy
  -> 记录审计事件（原值、新值、操作者、时间、原因）
  -> 新 run 的 RuntimeContext.access_policy + delegation context hash
runtime-service
  -> 校验签名和 hash 后解析档位
  -> 选择 interrupt_on
```

使用 GraphHarbor 线程 metadata 存储当前档位，第一期不引入新表。`LangGraphThreadsSdkAdapter` 已支持 `threads.update(metadata=...)`；Gateway 只开放专用接口而不开放任意 metadata 写入。HTTP 审计中间件记录策略变更请求，不依赖 metadata 覆盖后的最终值。

`RuntimeContext` 新增 `access_policy`，`RuntimeGatewayService` 的 context snapshot、允许字段、delegation payload 与 context hash 同步扩展。Platform API 从线程元数据覆盖或拒绝客户端声明的值，随后签发；Runtime 不从请求体或 `configurable` 读取它。

### 授权与兼容

- 设置接口建议要求 `PROJECT_RUNTIME_WRITE`，并验证线程属于当前 project；是否仅项目管理员可升级作为人工评审项。
- 新线程默认 `review`；历史线程缺失字段时视为 `review`。
- 只有 graph capabilities 显式声明支持时才允许 `workspace_write`。
- 非法值返回稳定的 `invalid_access_policy`；无权限返回既有的授权错误。

实现前须验证 GraphHarbor 是否提供受支持的 metadata 更新与并发条件写接口，不能假定现有 gateway 已有策略更新方法。策略字段禁止从通用线程创建/更新 metadata 注入；若无法保证服务端专属写入和切换/启动互斥，则改为 Platform API 专属持久化记录，不把普通 metadata 作为授权事实源。签名只保证传输完整性，不能替代签名前的权限判断。

策略读写使用 revision 条件更新；run.start、run.resume、队列后续启动、重试和 checkpoint 分支统一解析。新线程/复制分支默认 review，历史回放不得恢复旧高权限；幂等重试复用原 run 策略快照。两个浏览器同时切换或启动时，冲突返回 409。审计写入失败时升级不生效。

## 任务拆分

- [x] 在 `platform-api` 增加 `PATCH /api/langgraph/threads/{thread_id}/access-policy`，只接受 `{ "access_policy": "review" | "workspace_write" }`。
- [x] 线程创建强制写入 `metadata.access_policy=review`；历史线程缺失字段按 `review` 处理。
- [x] `RuntimeGatewayService` 在 `create_thread_run()` 与 Protocol v2 `send_thread_command(run.start)` 读取线程策略，覆盖浏览器提交值并纳入 context snapshot/hash。
- [x] 接入现有 HTTP audit metadata；路由矩阵、伪造覆盖及 adapter 测试已补齐。

## 验证要求与记录

### 验证要求
- [ ] 普通成员只能变更自己有写权限项目内线程。
- [ ] payload 中伪造的 `access_policy` 无法越过服务端线程状态。
- [ ] Runtime 收到的 hash 覆盖档位，篡改后拒绝执行。
- [ ] 每次变更生成可查询的审计记录。

### 验证记录

#### 2026-09-17 验证
- ✅ `python -m unittest tests/test_thread_access_policy.py tests/test_runtime_gateway_http_matrix.py tests/test_runtime_gateway_sdk_adapters.py tests/test_runtime_gateway_runtime_contract.py`：34 项通过。
- ✅ 覆盖专用 PATCH 路由、认证/跨项目边界、SDK `threads.update` 适配、浏览器伪造值被线程 metadata 覆盖，以及 v1/v3 Context hash 兼容。
- ⚠️ 浏览器端与真实 Runtime 的端到端链路：待 Platform Web 接入后执行。

## 状态

部分完成：后端已实现并通过定向测试，前端与端到端待接入。
