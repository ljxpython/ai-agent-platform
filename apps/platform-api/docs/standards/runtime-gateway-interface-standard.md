# Runtime网关标准

公开前缀为 `/api/langgraph`，入口见[router](../../src/platform_api/modules/runtime_gateway/presentation/http.py)。Platform负责身份/项目授权、参数决议、幂等记录和受控转发；GraphHarbor持有执行事实，Runtime负责图、模型与工具。GraphHarbor不实现平台业务JWT。

## 当前公开面

下列路径相对前缀；t表示 `{thread_id}`，r表示 `{run_id}`，实际请求必须替换为ID。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /info | Runtime信息 |
| POST | /graphs/search | Graph搜索 |
| POST | /graphs/count | Graph计数 |
| POST | /threads | 创建Thread |
| POST | /threads/search | 搜索Thread |
| POST | /threads/count | Thread计数 |
| GET | /threads/t | 读取Thread |
| DELETE | /threads/t | 删除Thread |
| GET | /threads/t/state | 读取state，支持subgraphs/checkpoint_id |
| POST | /threads/t/state | 更新state |
| POST | /threads/t/history | 读取checkpoint历史 |
| POST | /threads/t/runs | 创建或恢复Run |
| POST | /threads/t/runs/stream | 创建并订阅Run |
| POST | /threads/t/commands | Protocol命令 |
| POST | /threads/t/stream/events | Protocol事件订阅 |
| GET | /threads/t/runs/r | 读取Run |
| GET | /threads/t/runs | 列表，支持limit/offset/status/select |
| GET | /threads/t/runs/r/join | 等待Run |
| GET | /threads/t/runs/r/stream | 重连Run事件 |
| POST | /threads/t/runs/r/cancel | 显式取消 |

共20条，由[test_runtime_gateway_http_matrix.py](../../tests/test_runtime_gateway_http_matrix.py)与路由注册集合校验。未列出的上游能力不能因为SDK有方法就当作平台接口，完整LangGraph Server等价性另行验收。

## 身份与参数

请求携带平台认证与 `x-project-id`。Thread归属必须匹配项目；启动/恢复重新检查当前Agent、Graph、模型、工具与成员授权。委托scope.operation区分read和run-create。

产品Agent执行键为graph_id，标准SDK字段仍为assistant_id；平台不创建/同步上游Assistant。Graph/Tool刷新是有限超时HTTP，普通目录只读快照；schema从远端读取，不扫描宿主源码。

model_id使用平台模型记录UUID，不是provider:model或模型名称。默认值按项目→Agent→本次显式参数覆盖，仍受策略约束。Agent公开context为model_id、temperature、max_tokens、top_p、tools；不能从客户端注入身份或内部模型引用。

公开运行config只允许recursion_limit（1–1000，默认25）。内部委托与模型引用由服务端构造，模型凭据不进入浏览器、Run快照或普通日志。Runtime通过受信内部接口按当前权限兑换连接；master key只由Platform持有。

## 幂等与审批

新动作使用新的 `Idempotency-Key`，同动作重试保留原key。相同key和内容复用原Run，不同内容返回409；没有key的标准请求是独立动作。HTTP超时表示结果未知，先查询原Run，不用新key盲重发。

run_requests只保存请求摘要、授权/config快照和Run关联，不存消息或执行终态。并发执行首期使用reject，由Agent Server原子裁决，不在平台再造活跃运行锁。

标准恢复示例：

```json
{"assistant_id":"showcase_demo","command":{"resume":{"interrupt-id":{"decisions":[{"type":"approve"}]}}}}
```

从当前state读取真实interrupt ID与动作，decisions必须与动作对应，不能硬编码全批准。恢复不允许覆盖input/config/context；多个interrupt使用ID映射。Protocol `/commands` 的input.respond共用授权与恢复路径，id为整数，不是HTTP幂等键。恢复产生新Run ID，父Run关联保留；重复/过期/异项目审批拒绝。

## SSE、错误与取消

授权和上游状态校验在发送200前完成。JSON/SSE移除内部runtime_model_ref；SSE敏感键脱敏。网络chunk不等于完整事件，客户端使用SDK或正确SSE解析器。

join stream支持stream_mode、last_event_id和cancel_on_disconnect参数，但当前只允许cancel_on_disconnect=false，true被拒绝。订阅断开不取消Run，必须显式cancel。重连先读Run/state和interrupt，不自动重新发送消息或批准。

Protocol lifecycle可能规范化为completed；Run JSON保留上游状态，不能将两者机械替换。cancel成功ACK不等于终态确认，需继续读取Run。

401重新认证，403检查权限，404检查资源与项目，409检查幂等或并发，5xx/超时核实提交结果。不得在HTTP 200后伪装前置失败。

## 变更验证

新增路由更新20条显式清单，覆盖scope、授权拒绝、字段过滤与参数；业务语义由run_requests/SDK/事件测试以及[真实验收](../../../../docs/projects/20260910-platform-api-refactor/implementation/13-backend-acceptance-closeout.md)证明。router替身不能替代真实执行，前端适配见[交接](../../../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)。
