# Platform Dispatch Layer - 整体方案

## 背景

当前 platform-api 中创建 LangGraph run 的代码分散在多个模块，没有统一的配置标准：
- stream_mode、stream_subgraphs 配置不一致
- durability、multitask_strategy 需要每次手动指定
- 缺少统一的 webhook 回调机制
- Protocol v2 标记（`__event_streaming_v2`）容易遗漏

参考 open-swe 项目的 `agent/dispatch.py`，实现统一的 dispatch 层。

## 目标

1. 提供统一的 `dispatch_agent_run()` 函数，作为所有 run 创建的入口
2. 标准化 Protocol v2 配置，确保前端能正确观察 run 状态
3. 默认使用 durability="sync" 和 multitask_strategy="interrupt"
4. 支持 webhook 回调，确保 run 完成后能通知 platform-api

## 方案设计

### 整体架构

```
platform-api 各模块
    ↓
dispatch_agent_run()  ← 统一入口
    ↓
prepare_run_config()  ← 标准化配置
    ↓
langgraph_sdk.runs.create()
```

### 关键改动点

#### 1. 创建 dispatch 模块

**文件：** `apps/platform-api/app/core/dispatch.py`

**功能**：
- `prepare_run_config()` - 准备标准 run 配置
  - 设置 `__event_streaming_v2=True`
  - 设置 stream_mode 为 Protocol v2 标准
  - 合并 metadata
  
- `dispatch_agent_run()` - 统一 run 创建入口
  - 接受 thread_id, assistant_id, input, config
  - 自动应用标准配置
  - 支持 webhook、multitask_strategy、durability 参数

**常量**：
```python
EVENT_STREAMING_V2_CONFIG_KEY = "__event_streaming_v2"
V2_RUN_STREAM_MODES = (
    "values",
    "updates", 
    "messages",
    "custom",
    "tasks",
    "checkpoints",
)
```

#### 2. 更新现有 run 创建点

**文件：** `apps/platform-api/app/modules/runtime_gateway/application/service.py`

**改动：** 将现有的 `runs.create()` 调用替换为 `dispatch_agent_run()`

**理由：** 统一配置，减少重复代码

### 技术选型

**选型1：函数式 API vs 类封装**
- 选择：函数式 API（`dispatch_agent_run`）
- 理由：简单直接，参考 open-swe 的实现，易于测试

**选型2：webhook 配置方式**
- 选择：通过环境变量配置 `COMPLETION_WEBHOOK_URL` 和 `RUN_COMPLETE_WEBHOOK_SECRET`
- 理由：与 open-swe 保持一致，便于部署配置

**选型3：默认参数**
- 选择：durability="sync", multitask_strategy="interrupt", stream_resumable=True
- 理由：确保 run 持久化、支持中断恢复、前端能重新连接

## 链路影响

### 受影响的调用链路
```
platform-web → platform-api → runtime-service
                    ↓
            dispatch_agent_run()
                    ↓
            langgraph_sdk.runs.create()
```

### 契约变更
- **无破坏性变更** - dispatch 层只是封装，不改变 API 契约
- **增强点** - 所有 run 自动获得 Protocol v2 支持

## 风险和依赖

**风险1：** webhook URL 配置错误导致回调失败
- **应对：** 实现 URL 验证逻辑，拒绝 localhost/相对路径

**依赖1：** 需要环境变量 `COMPLETION_WEBHOOK_URL` 和 `RUN_COMPLETE_WEBHOOK_SECRET`
- **应对：** 在文档中说明，webhook 为可选功能

## 实施计划

### Phase 1: 核心实现
1. 创建 `dispatch.py` 模块
2. 实现 `prepare_run_config()` 和 `dispatch_agent_run()`
3. 添加单元测试

### Phase 2: 集成
1. 更新 runtime_gateway service
2. 更新其他 run 创建点
3. 添加集成测试

### Phase 3: 验证
1. 本地环境验证
2. 端到端测试
3. 文档更新
