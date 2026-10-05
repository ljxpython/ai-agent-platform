# Token 续期错误分类

## 改动
- refresh 端点明确 400/401 才清理会话。
- 网络、超时和 5xx 抛出 `auth_refresh_unavailable`，保留现有 Token 和工作区。
- REST 与 LangGraph Fetch 统一保留会话语义。

## 验证
- HTTP/LangGraph 单测通过；浏览器认证服务 503 故障注入通过。
