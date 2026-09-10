# 下一步操作指南

## 当前状态 ✅

两个关键问题已修复：

1. **Agent同步问题** ✅ 
   - `list_graphs()` 已改为从LangGraph API同步
   - 不再依赖静态文件

2. **showcase_demo工具权限问题** ✅
   - 按照文档19的设计原则修复
   - 工具不再在AgentDefaults中声明
   - context_hash格式正确

## 剩余问题 ⚠️

**模型配置缺失**：showcase_demo需要可用的模型才能响应消息。

## 验证步骤

### 方式1：配置真实模型（推荐）

1. 访问 http://127.0.0.1:3000

2. 进入项目设置 > 模型配置

3. 添加一个可用的模型（例如DeepSeek、OpenAI等）

4. 创建**新的** showcase_demo 对话（不要使用之前失败的对话）

5. 发送测试消息："你好"

6. 观察是否有回复

### 方式2：使用已配置的模型

如果项目中已经有配置好的模型（如workflow_demo使用的模型），可以：

1. 检查当前配置的模型：
   ```bash
   bash scripts/local-stack.sh logs platform-api 2>&1 | grep -i "model" | tail -20
   ```

2. 在Web界面创建showcase_demo对话时，手动选择一个已配置的模型

### 方式3：检查日志确认修复生效

即使没有配置模型，也可以通过日志确认工具权限问题已解决：

```bash
cd /Users/lijiaxin/PyCharmMiscProject/ai-agent-platform

# 创建新的showcase_demo对话并发送消息后，检查日志
bash scripts/local-stack.sh logs runtime-worker 2>&1 | grep "showcase_demo" | tail -20
```

**预期结果**：
- ✅ 不应该看到 `runtime.optional_tool.not_allowed`
- ✅ 不应该看到 `runtime.required_tool.not_allowed`  
- ⚠️  可能看到 `runtime.model.initialization_failed`（这是正常的，因为缺少API key）

## 确认修复的证据

运行本地测试脚本：

```bash
cd /Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service
source .venv/bin/activate
cd ../..
python test_showcase_demo.py
```

**成功的输出示例**：
```
🔧 Testing showcase_demo agent initialization...
❌ Agent creation failed:
   Error type: RuntimeResolutionError
   Error message: runtime.model.initialization_failed
```

注意：看到 `model.initialization_failed` 是正常的，说明已经通过了工具权限验证阶段。

## 如何设置模型API Key

如果要使用真实模型，需要：

### DeepSeek
```bash
# 在 apps/runtime-service/.env 中添加
DEEPSEEK_PROXY_API_KEY=sk-your-key-here
```

### OpenAI
```bash
# 在 apps/runtime-service/.env 中添加  
OPENAI_API_KEY=sk-your-key-here
```

然后重启服务：
```bash
bash scripts/local-stack.sh restart runtime-worker
```

## 快速验证命令

```bash
cd /Users/lijiaxin/PyCharmMiscProject/ai-agent-platform

# 1. 检查服务状态
bash scripts/local-stack.sh status

# 2. 检查最新的showcase_demo日志
bash scripts/local-stack.sh logs runtime-worker 2>&1 | grep "showcase_demo" | tail -10

# 3. 在浏览器访问
open http://127.0.0.1:3000

# 4. 创建新对话并测试
```

## 关键修改文件

如果需要回顾修改：

1. **Agent同步修复**
   - `apps/platform-api/app/modules/runtime_catalog/application/service.py` (line 605-637)

2. **showcase_demo工具修复**
   - `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` (line 42-82)

3. **验证和文档**
   - `VERIFICATION_REPORT.md` - 详细的修复报告
   - `FIXES_SUMMARY.md` - 修复总结
   - `test_showcase_demo.py` - 测试脚本

## 常见问题

### Q: 为什么showcase_demo的工具不需要在AgentDefaults中声明？

A: 根据文档19的设计，showcase_demo的工具是通过 `create_deep_agent(tools=[...])` 直接装配的，不是通过平台的工具目录管理。这类工具不应该在AgentDefaults中声明。

### Q: 如果还是看到工具权限错误怎么办？

A: 
1. 确认runtime-worker已重启并加载了新代码
2. 创建**新的**对话（不要使用旧的失败对话）
3. 检查文件确认修改生效：
   ```bash
   grep -A 2 "optional_tool_names" apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py
   ```
   应该看到 `optional_tool_names=(),  # 工具由DeepAgents直接管理`

### Q: Workflow Demo HITL 能工作，为什么showcase_demo不行？

A: Workflow Demo使用的是平台工具目录中注册的工具（如`read_reference`），而showcase_demo使用的是自定义工具。两者的装配方式不同，showcase_demo的工具通过DeepAgents框架直接管理，不需要在Policy中声明。

## 成功标志

当看到以下情况时，说明修复成功：

✅ 本地测试脚本只报模型错误，不报工具错误
✅ runtime-worker日志中showcase_demo不再有 `tool.not_allowed` 错误
✅ 在Web界面配置模型后，showcase_demo能正常响应消息
