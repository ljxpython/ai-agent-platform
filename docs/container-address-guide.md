# 容器地址填写指南

文档类型：`Operational`

这份短文档只回答一个问题：

> 当服务跑在容器里时，外部依赖地址应该怎么填？

## 1. 先记住这条规则

从容器里看地址时：

- `127.0.0.1`
  - 指向容器自己
  - 不是宿主机
- `0.0.0.0`
  - 只能用于服务端监听
  - 不是客户端访问目标

所以：

- 不要把宿主机服务地址写成 `127.0.0.1:<port>`
- 不要把客户端目标地址写成 `0.0.0.0:<port>`

## 2. 三种常见场景

### 2.1 服务跑在宿主机

容器访问宿主机服务时，优先使用：

```text
http://host.docker.internal:<port>
```

当前已验证通过的例子：

- RAG HTTP：
  - `http://host.docker.internal:9621`
- MCP SSE：
  - `http://host.docker.internal:8621/sse`

### 2.2 服务跑在同一个 Docker 网络

直接用服务名：

```text
http://<service-name>:<port>
```

例如：

- `http://platform-api:2142`
- `http://interaction-data-service:8081`

### 2.3 服务跑在外网或其他可直连机器

直接填写真实 URL：

```text
https://rag.example.com
https://mcp.example.com/sse
```

如果是公司内网可直连地址，也按同样方式处理。

## 3. 这套仓库里对应填哪里

### 3.1 平台侧 RAG HTTP

填到：

- `deploy/.env.stack`

字段：

```env
PLATFORM_API_KNOWLEDGE_UPSTREAM_URL=...
PLATFORM_API_KNOWLEDGE_UPSTREAM_API_KEY=
```

### 3.2 runtime 私有 knowledge MCP

填到：

- `deploy/.env.stack`
- 或单应用验证时的 `apps/runtime-service/deploy/.env.runtime-service`

字段：

```env
TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED=true
TEST_CASE_V2_KNOWLEDGE_MCP_URL=...
TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS=30
TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS=300
```

## 4. 已验证结论

当前这套仓库里已经验证过：

- `http://host.docker.internal:9621`
  - 可被 `platform-api` 容器访问
- `http://host.docker.internal:8621/sse`
  - 可被 `runtime-service` 容器访问

也已经验证过下面两种写法**不可用**：

- `http://127.0.0.1:9621`
- `http://0.0.0.0:8621`

## 5. 最短建议

如果你不想思考太多：

- 宿主机服务：`host.docker.internal`
- 容器服务：`service-name`
- 公网/内网服务：真实 URL
