# Agent 全链路可观测与 Run Explorer - 验证计划和记录

## 验证计划

### 单元测试
- [ ] 关联 ID 生成、传播和缺失/非法 header 处理。
- [ ] 事件序号单调递增、分页和去重。
- [ ] Langfuse/OTel exporter 故障不改变 Run 结果。
- [ ] 事件摘要脱敏、字段 allowlist 和响应大小限制。
- [ ] API 项目/租户权限过滤。
- [ ] 前端时间线按 `sequence` 合并并恢复游标。

### 集成测试
- [ ] platform-api → runtime-service 的 `traceparent` 和关联 ID 贯通。
  - **预期：** OTel Trace、Run、Langfuse Trace 可互相定位。
- [ ] Run 失败、取消、重试和中断事件查询。
  - **预期：** 状态以 Durable Run 为准，事件无重复。
- [ ] Collector、Langfuse 不可用。
  - **预期：** Agent 运行成功/失败语义不变，产生降级诊断。
- [ ] 越权查询其他项目 Run。
  - **预期：** 返回 403 或等价的不可见结果，不泄露元数据。

### 端到端测试
- [ ] platform-web 发起一次 Agent 对话，完整验证 platform-api → runtime-service → Model/Tool → interaction-data-service。
  - **验证点：** 前端能看到 Run 时间线、工具/子 Agent 节点、错误详情、SSE 断线恢复、Langfuse 外链和审计关联。

### 性能测试
- [ ] Run 列表和详情 P95 在目标数据量下满足平台 API SLO。
- [ ] 事件写入和 SSE 重放不阻塞 Agent 执行。
- [ ] Collector 队列达到上限时丢弃观测数据，不拖慢业务请求。

### 安全测试
- [ ] Prompt、响应、工具参数中的 secret/PII 脱敏。
- [ ] 项目、租户、管理员角色隔离。
- [ ] Langfuse 外链不暴露长期密钥或未授权 Trace。

## 验证记录

暂无。实现完成后由 `verify-change` 补充执行证据和四态结论。
