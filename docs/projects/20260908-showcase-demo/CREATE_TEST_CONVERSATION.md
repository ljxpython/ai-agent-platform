# 测试步骤

## 1. 在浏览器打开
http://127.0.0.1:3000

## 2. 创建新的showcase_demo对话
- 点击 "New Chat" 或类似按钮
- 选择 Assistant: showcase_demo
- 创建对话

## 3. 发送测试消息
发送：你好

## 4. 立即检查日志
在终端运行：
```bash
# 在 ai-agent-platform 仓库根目录执行
bash scripts/local-stack.sh logs runtime-worker 2>&1 | grep -A 100 "showcase_demo" | tail -150
```

## 5. 检查关键信息
日志中应该看到：
- ✅ 没有 `runtime.tool.not_allowed` 错误（工具权限问题已解决）
- ⚠️ 可能有模型相关的错误
- 检查是否调用了 `_catalog_connection()`
- 检查 `connection` 是否为 `None`

## 6. 检查平台API是否配置了可用模型
访问：http://127.0.0.1:3000/workspace/models

确认：
- 是否有已配置的模型
- 模型是否已启用（enabled）
- API key是否已配置
