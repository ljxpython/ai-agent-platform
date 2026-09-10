# Platform Dispatch Layer - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `test_prepare_run_config()` - 测试配置准备逻辑
  - 验证 `__event_streaming_v2` 被正确设置
  - 验证 `prepare_run_id` 生成
  - 验证 metadata 合并

- [ ] `test_is_loopback_webhook()` - 测试 loopback 检测
  - 验证相对路径被识别
  - 验证 localhost/127.0.0.1 被识别
  - 验证合法 https URL 通过

- [ ] `test_resolve_completion_webhook_url()` - 测试 webhook URL 解析
  - 验证无 secret 时返回 None
  - 验证 loopback URL 降级为 None
  - 验证正确拼接 token 参数

- [ ] `test_dispatch_agent_run()` - 测试完整 dispatch 流程
  - 验证调用参数正确传递
  - 验证默认配置应用
  - 验证 webhook 配置

### 集成测试

- [ ] **场景1：标准 run 创建**
  - 步骤：调用 dispatch_agent_run() 创建 run
  - 预期：run 成功创建，配置包含 Protocol v2 标记

- [ ] **场景2：带 webhook 的 run**
  - 步骤：配置环境变量，创建 run
  - 预期：run 包含 webhook URL

- [ ] **场景3：multitask_strategy="enqueue"**
  - 步骤：在活跃 thread 上以 enqueue 模式创建 run
  - 预期：新 run 排队而非中断

### 端到端测试

- [ ] **链路1：platform-web → platform-api → runtime-service**
  - 操作：从前端创建新的 agent run
  - 验证点：
    - run 成功创建
    - 前端能看到完整的事件流（tools, lifecycle, subagent）
    - run 状态正确显示

- [ ] **链路2：webhook 回调**
  - 操作：配置 webhook，等待 run 完成
  - 验证点：platform-api 收到回调通知

### 性能测试
- [ ] 并发 run 创建 - 目标：支持 100 QPS

## 验证记录

### {日期} 验证
**执行人：** @lijiaxin

#### 单元测试
- ⏭️ 待执行

#### 集成测试
- ⏭️ 待执行

#### 端到端测试
- ⏭️ 待执行

#### 问题和修复
_待记录_

#### 最终结论
⏭️ 待验证

## 回归测试检查清单

在实施 dispatch 层后，需要验证以下现有功能不受影响：

- [ ] 现有 run 创建流程正常
- [ ] 前端能正确观察 run 状态和进度
- [ ] run 中断和恢复功能正常
- [ ] durability="sync" 确保崩溃后能恢复
- [ ] subagent 事件正确显示在前端
