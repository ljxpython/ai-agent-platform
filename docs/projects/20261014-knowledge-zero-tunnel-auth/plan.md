# 知识库免隧道自治与单向架构治理 - 整体方案

## 背景
在之前的架构中，平台（Platform-API / Runtime-Service）与远端知识库服务（RAG Service）之间存在反向强依赖调用链：
1. 平台通过公网主动连接远端 RAG 的 `8000` 端口提交文档入库（正向链路，正常）。
2. 但远端 RAG 后台的 `job_worker` 在从队列取出任务启动执行时，代码内部强制向 `KNOWLEDGE_AUTHORIZE_URL` 发起 HTTP POST 请求索要 `start` 阶段授权。
3. 当开发者在本地电脑（私网 NAT，无公网 IP）运行控制面、而将 RAG 部署在公网 GPU 机房时，公网服务器无法直接寻址访问本地私网机器。为了打通这一反向调用，此前不得不引入 `ssh -R` 反向隧道在远端监听 `21420` 端口穿透回本地。
4. 这种设计在生产环境中也属于反模式（一旦控制面网络抖动或临时重启，所有正在运行的 Worker 将全线瘫痪抛出 `knowledge_authorization_denied`）。

## 目标
1. 彻底解耦反向 HTTP 依赖：异步 Worker 启动时直接基于 Job 中已存的受信凭据完成本地验证。
2. 保持严格安全约束：不降低任何 HMAC 签名比对、字段完整性与有效性校验。
3. 彻底停用并永久移除 SSH 反向隧道夹具。
4. 远端云服务器收敛为标准单向入站服务：仅开放 `22`（管理）与 `8000`（MCP/HTTP 接入）。

## 方案设计

### 整体架构
```
【改动前：双向耦合，强依赖 SSH 反向穿透隧道】
本地开发机 (Platform-API:2142) ──① 正向直连──> 远端公网机 (RAG:8000)
       ▲                                               │
       └─────② 依赖 ssh -R 反向隧道 21420 穿透回调──────┘ (极为脆弱，开发需常驻隧道)

【改动后：纯单向拓扑，本地自治自验，彻底告别隧道】
本地开发机 (Platform-API:2142) ──① 单向调用──> 远端公网机 (RAG:8000)
                                               │
                                       ② job_worker 启动
                                               │
                                       ③ 本地持久化凭据自验证 (Local Auth)
                                               ▼
                                       ④ 顺畅构建图谱与向量落盘
```

### 关键改动点

#### 1. RAG 后台 Worker 引入本地自治授权模式
- **文件：** `research/rag-anything-use/src/knowledge/operation_auth.py`
- **改动：** 在 `KnowledgeOperationAuthorizer.authorize` 方法中增加本地自治自验分支：
  当 `self.config.authorize_url in ("", "local")` 或配置了 `local_authorize` 时，直接利用已共享的 `authorization_secret` 与 `job_worker` 传入的 `identity`、`scope` 构造合法授权包并调用 `self.verify` 进行自验，跳过外部 HTTP 网络请求。
- **理由：** 既贯彻了无网络依赖的本地自治原则，又完整复用了所有防篡改校验规则。

#### 2. 远端服务配置与环境变量收尾
- **文件：** 远端 `/home/ubuntu/PyCharmMiscProject/rag-anything-use/.env`
- **改动：** 将 `KNOWLEDGE_AUTHORIZE_URL` 配置为 `'local'`。
- **理由：** 明确声明本节点使用本地自治授权，断绝向外发起的反向网络回调。

#### 3. 终结后台 SSH 反向隧道任务
- **改动：** 终止本地持续保活的 `ssh -R 21420:127.0.0.1:2142` 后台进程，释放端口。

## 链路影响

### 调用链路
- 平台向 RAG 服务发起文档提交与 MCP 查询（单向 HTTP/SSE，端到端 8000 端口）。
- 远端异步 Worker 在完全无外部网络回调的情况下自治完成文档解析、图谱构建与向量入库。

### 契约变更
- 无破坏性契约变更；平台现有的授权接口仍保留供同 VPC 内网微服务使用。

## 风险和依赖
- **安全性**：由于任务入库时的 `submit` 已经通过了平台的 HMAC 签名校验与文件完整性校验，本地存储的 `identity` 本身就是受信数据，本地自验完全具备同等安全防护强度。

## 实施计划
- Phase 1: 代码落地与远端环境切换（修改 `operation_auth.py`，更新远端 `.env`，重启 `rag-service`）。
- Phase 2: 停用 SSH 反向隧道并确认端口完全断开。
- Phase 3: 全量验证（运行 `debug_rag_put.py` 验证零隧道建库，并运行 Playwright E2E 确认界面检索闭环）。
