# Platform Dispatch Layer - 任务拆分

## Phase 1: 核心实现

### Task 1.1: 创建 dispatch 模块基础结构
- **文件：** `apps/platform-api/app/core/dispatch.py`
- **改动：** 
  - 创建模块文件
  - 定义常量 `EVENT_STREAMING_V2_CONFIG_KEY`, `V2_RUN_STREAM_MODES`
  - 实现 `_is_loopback_webhook()` 辅助函数
  - 实现 `_resolve_completion_webhook_url()` 辅助函数
- **预计：** 0.5天
- **状态：** 待开始

### Task 1.2: 实现 prepare_run_config()
- **文件：** `apps/platform-api/app/core/dispatch.py`
- **函数：** `prepare_run_config(config, metadata)`
- **改动：**
  - 合并 configurable，设置 `__event_streaming_v2=True`
  - 生成 `prepare_run_id`
  - 合并 metadata
- **预计：** 0.5天
- **状态：** 待开始

### Task 1.3: 实现 dispatch_agent_run()
- **文件：** `apps/platform-api/app/core/dispatch.py`
- **函数：** `dispatch_agent_run()`
- **改动：**
  - 接受参数：thread_id, assistant_id, input, config, metadata
  - 调用 prepare_run_config()
  - 构建 create_kwargs（stream_mode, stream_subgraphs, durability 等）
  - 处理 webhook URL
  - 调用 langgraph_sdk.runs.create()
  - 添加日志
- **预计：** 1天
- **状态：** 待开始

### Task 1.4: 添加单元测试
- **文件：** `apps/platform-api/tests/test_dispatch.py`
- **改动：**
  - `test_prepare_run_config()` - 测试配置准备
  - `test_is_loopback_webhook()` - 测试 webhook 验证
  - `test_resolve_completion_webhook_url()` - 测试 URL 解析
  - `test_dispatch_agent_run()` - 测试完整 dispatch 流程
- **预计：** 0.5天
- **状态：** 待开始

## Phase 2: 集成现有代码

### Task 2.1: 更新 runtime_gateway service
- **文件：** `apps/platform-api/app/modules/runtime_gateway/application/service.py`
- **改动：**
  - import dispatch_agent_run
  - 替换现有 runs.create() 调用
  - 简化配置逻辑（移到 dispatch 层）
- **预计：** 0.5天
- **状态：** 待开始

### Task 2.2: 更新其他 run 创建点
- **文件：** `apps/platform-api/app/adapters/langgraph/runs_sdk_adapter.py`
- **改动：** 评估是否需要使用 dispatch 层，或保持直接调用
- **预计：** 0.5天
- **状态：** 待开始

### Task 2.3: 添加集成测试
- **文件：** `apps/platform-api/tests/integration/test_dispatch_integration.py`
- **改动：**
  - 测试完整的 run 创建流程
  - 验证 Protocol v2 配置生效
- **预计：** 0.5天
- **状态：** 待开始

## Phase 3: 验证和文档

### Task 3.1: 本地环境验证
- **描述：** 启动 local-stack，创建 run，验证配置正确
- **预计：** 0.5天
- **状态：** 待开始

### Task 3.2: 端到端测试
- **描述：** 
  - 从 platform-web 触发 run
  - 验证前端能正确观察 run 状态
  - 验证 webhook 回调（如果配置）
- **预计：** 0.5天
- **状态：** 待开始

### Task 3.3: 更新文档
- **文件：** `apps/platform-api/README.md` 或新增 `docs/dispatch.md`
- **改动：**
  - 说明 dispatch 层的作用
  - 环境变量配置说明
  - 使用示例
- **预计：** 0.5天
- **状态：** 待开始

## 进度追踪
- [ ] Phase 1 完成（核心实现）
- [ ] Phase 2 完成（集成）
- [ ] Phase 3 完成（验证和文档）

## 总计工作量
- Phase 1: 2.5天
- Phase 2: 1.5天
- Phase 3: 1.5天
- **合计：** 5.5天（实际预估 1.5 人天为最小可用版本）
