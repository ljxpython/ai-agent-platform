# 审计标准

审计记录HTTP行为与主体，不代替Runtime执行事实。入口为[audit模块](../../src/platform_api/modules/audit/)和[审计中间件](../../src/platform_api/entrypoints/http/middleware/audit_log.py)。

## 内容与动作

`audit_logs`保存request_id、plane、action、目标类型/ID、actor_user_id/subject、tenant_id/project_id、result、method/path、status_code、duration_ms、metadata_json及created_at。

plane为control_plane/runtime_gateway/system_internal；result为success/failed/cancelled。动作由http_resolution.py解析，例如identity.session.created、runtime.run.item.created、runtime.command.submitted。解析器中的历史分支不等于接口公开，公开面以注册router为准。

新增受治理接口时更新动作、目标/项目定位与测试。使用可信actor/scope，用户治理的action override只允许代码登记的动作。

## 写入与失败

数据库启用时，中间件在响应体消费结束后写独立短事务。HTTP状态低于400记success，否则failed；异常记500/failed，取消记499/cancelled。SSE审计时长包含订阅时间，不代表模型执行时长。

数据库写入交给线程池，用取消保护完成收尾。写入失败记录 `audit_write_failed`，不覆盖原业务响应。当前没有业务与审计原子提交、持久化重试或outbox，不能承诺审计绝不丢失。

未配置Session时不写数据库审计；API文档、OpenAPI及favicon等路径跳过，具体范围见中间件。

## 敏感数据

仅对有Content-Length且不超过64KiB的JSON响应临时捕获以提取目标ID，不持久化整份响应或SSE正文。metadata包含query、client_ip、user_agent、目标、结果及响应大小等，额外业务metadata仅允许reason。

query当前原样进入审计，禁止在URL携带token、密码或模型密钥。不得将Authorization、Cookie、原始请求体或模型凭据加入metadata。公开响应过滤不能代替日志和审计数据最小化。

## 查询与检查

平台审计读取受 `platform.audit.read` 控制，项目审计受 `project.audit.read` 和项目scope控制。cancel的成功ACK表示请求响应，不证明Run已终止，应读取Runtime状态。

复用test_audit_http_resolution.py和test_transaction_boundaries.py验证定位、线程和取消收尾；不为已退役平台Worker增加job生命周期事件。
