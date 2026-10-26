# GitHub 调研工具与远程沙箱证据元组契约韧性治理 - 整体方案

## 背景
在排查 Thread `4905953e-5758-47fb-a487-78a86e32672e` 工具调用失败故障时，发现了双重连环问题：
1. **GitHub 匿名调用额度耗尽**：`github_query` 工具以无 Token 匿名方式请求 GitHub REST API，受 GitHub 针对出口公网 IP 每小时 60 次的硬限制，额度耗尽后返回 HTTP 403（`x-ratelimit-remaining: 0`），触发 `tool.upstream_unavailable` 降级。
2. **大模型自愈引发 Agent 崩溃**：模型收到降级提示后智能尝试调用 `search_web` 与 `fetch_page`。在当前启用的远端 Docker 沙箱模式（`RUNTIME_SANDBOX_TARGET=remote`）下，工具将证据存盘调用 `_evidence()`，经由 RPC（`RemoteWorkspace.call("research_evidence", ...)`）传输回本地后，原有的 Python `tuple` 在 JSON 序列化/反序列化中退化为 `list`。而 LangChain `@tool(response_format="content_and_artifact")` 严格强校验 `isinstance(response, tuple)`，拿到 `list` 直接抛出未被捕获的 `ValueError`，导致 LangGraph 节点崩溃，Worker 标记 Run 为 `business_error`，向前端抛出 `runtime.execution_failed`。

## 目标
1. 消除匿名 GitHub 调用的限流痛点，借鉴 `deer-flow` 的实践，支持配置 `GITHUB_TOKEN`，额度提升至 5,000 次/小时，且未配置时不影响原有优雅降级机制。
2. 修复远程沙箱证据保存的返回值契约，确保 `RemoteWorkspace.call("research_evidence", ...)` 返回的结果 100% 满足 LangChain `tuple` 契约，彻底杜绝 `ValueError` 导致 Agent 异常暴毙。
3. 补齐对应单元测试与契约回归测试，保障本地模式与远端沙箱模式行为完全一致。

## 方案设计

### 整体架构
```
[LLM Tool Execution]
       │
       ├── github_query ──> research_http.get_public()
       │                         │
       │                         ├── (如果有 GITHUB_TOKEN) ──> Authorization: Bearer <token> (5000/hr)
       │                         └── (若无 Token) ──> 匿名请求 (60/hr) -> 403 限流时转为优雅降级
       │
       └── search_web / fetch_page ──> _evidence()
                                            │
                                            ├── [本地沙箱] ──> (json_summaries, artifact_dict) -> tuple
                                            └── [远端沙箱 RPC] ──> RemoteWorkspace.call("research_evidence")
                                                                         │
                                                                   [防退化转换层] (list -> tuple)
                                                                         │
                                                                         ▼
                                                           满足 LangChain isinstance(resp, tuple)
                                                                         │
                                                                         ▼
                                                           Run 正常执行完成，杜绝 execution_failed
```

### 关键改动点

#### 1. GitHub 工具鉴权注入与代理适应
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/research_http.py`
- **改动：**
  - 读取可选环境变量 `os.environ.get("GITHUB_TOKEN")`。
  - 当目标主机为 `api.github.com` 且配置了 `GITHUB_TOKEN` 时，在请求头注入 `Authorization: Bearer <token>`。
  - （可选/可配置）在 HTTP 客户端请求中，允许遵从系统环境变量代理配置，防止受国内网络环境阻断。
- **理由：** 借鉴 `deer-flow`（`skills/public/github-deep-research/scripts/github_api.py`），通过个人访问令牌提升限流配额至 5,000 次/小时。

#### 2. 远程沙箱证据 RPC 返回值元组防御转换
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py`
- **改动：**
  在 `_evidence()` 函数中对 `RemoteWorkspace.call("research_evidence", ...)` 的返回值进行防御性校验与转换：
  ```python
  if isinstance(workspace.root, RemoteWorkspace):
      result = workspace.root.call(
          "research_evidence",
          records=records,
          tool_call_id=runtime.tool_call_id,
          thread_id=info.thread_id,
          run_id=info.run_id,
          namespace=info.checkpoint_ns,
      )
      if isinstance(result, (list, tuple)) and len(result) == 2:
          return (result[0], result[1])
      return result
  ```
- **理由：** JSON RPC 协议本身无法天然区分 Python 的 `list` 与 `tuple`。LangChain 内部 `response_format="content_and_artifact"` 的校验逻辑是硬编码 `isinstance(response, tuple)`。在边界处进行显式转换是最直接、影响面最小（KISS）、且绝不破坏远程沙箱服务协议的优雅修复。

#### 3. 环境变量与开发栈配置说明补齐
- **文件：** `apps/runtime-service/.env` 与环境配置模板
- **改动：** 增加 `GITHUB_TOKEN` 配置项注释与样例。

## 链路影响

### 受影响的调用链路
```
User Prompt → dearflow_agent → ToolNode (github_query / fetch_page / search_web)
  → _evidence → RemoteWorkspace RPC → Sandbox Node Storage → Tool Result → LLM Next Step
```

### 契约变更
- **无破坏性契约变更**：
  - `_evidence` 在本地模式与远程模式下统一输出标准二元组 `tuple[str, dict]`。
  - `research_http` 对外仍抛出标准的 `ToolException`，对内无缝支持 `GITHUB_TOKEN`。

## 风险和依赖
- **风险1：** 用户的 `GITHUB_TOKEN` 格式错误或权限过期。
  - **应对：** 若附带 Token 遇到 401 Unauthorized，应同样由 `research_http.py` 捕获转换为标准 `ToolException`，不产生未捕获异常。
- **依赖1：** 需要在本地或 CI 环境中回归 `test_tool_errors.py` 与 `test_research_batch.py`。

## 实施计划
1. **Phase 1: 契约修复与防御加固**
   - 实现 `search.py` 中 `_evidence` 远程 RPC 返回值防御转换为 `tuple`。
   - 编写单元测试验证 RemoteWorkspace 模式下返回 `list` 能够正确转为 `tuple`，且 LangChain 不再报错。
2. **Phase 2: GitHub 调研工具 Token 鉴权注入**
   - 在 `research_http.py` 中注入 `GITHUB_TOKEN` 支持与 401/403 优雅容错。
   - 增加单元测试验证带 Token 与不带 Token 的请求头装配逻辑。
3. **Phase 3: 全量验证与留痕**
   - 运行 Runtime 关联单测套件，确认 100% 绿灯。
   - 更新环境配置项与项目文档。
