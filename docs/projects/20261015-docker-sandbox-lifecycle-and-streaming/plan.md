# Docker 对话级沙箱生命周期管理与原生流式传输改造 - 整体方案

## 背景

在进行生产级实测时，针对 9.0MB 的 PPTX 工作区文件下载，发现了严重的性能瓶颈与稳定性缺陷：
1. **控制面与数据面混同**：底层远程沙箱在读取文件时，通过 `/v1/rpc` 将二进制文件 Base64 编码塞入 JSON（体积膨胀至 12.5MB），全内存序列化/反序列化，公网纯传输耗时高达 20.6 秒。
2. **超时踩钢丝与连环 502 踩踏**：网关 upstream timeout 与前端 axios 默认均为 30 秒，与 20.6 秒极为接近；且由于前端下载按钮缺乏 Loading 禁用态，用户多次点击，后端与沙箱底层的连接池限制为 `max_connections=1`，导致并发排队严重超时，引发成片 `502 Bad Gateway`。
3. **资源受限环境下的沙箱设计诉求**：生产环境为资源有限的单机/单节点 Docker 服务器（如 4核 3.6GB 内存），无法部署沉重的 Kubernetes，也无法承受预热池（Warm Pool）带来的常驻内存开销（若常驻 3 个容器，将蚕食 200MB~1GB 内存）。
4. **参考标杆设计借鉴**：参考开源项目 DeerFlow 2.0（`research/deer-flow`），其核心设计是**“临时容器计算 + 宿主机持久化卷挂载 + 网关/节点直接走操作系统 FileResponse/sendfile 流式输出”**，彻底规避大文件通过 RPC 内存搬运的问题。

## 目标

1. **轻量级对话级沙箱（Thread Sandbox）按需生命周期**：
   - 贯彻“**无状态瞬时容器 + 有状态宿主机卷（Stateless Container + Stateful Host Volume）**”原则；
   - 容器生命周期跟随对话交互：用户发消息触发 Agent 执行时秒级拉起容器，挂载宿主机工作区；
   - 会话空闲超过阈值（如 10 分钟无活动）后，守护进程自动 `docker stop` / `docker rm` 释放容器，**内存与 CPU 占用降为 0**；
   - 用户再次在该对话交互时，重新拉起容器并透明挂载同一宿主机目录，实现数据完全无缝恢复。
2. **下载与预览彻底旁路容器（Bypass Container Execution）**：
   - 宿主机磁盘上的工作区目录作为持久化真相来源；
   - 用户在 Web 端预览文本/图片、下载单文件或打包 Zip 时，**绝不拉起 Docker 容器**；
   - 由宿主机或 Sandbox Node 守护进程直接读取磁盘文件并以纯二进制流响应，毫秒级响应且 0 容器损耗。
3. **数据面流式下载与协议脱离**：
   - 废除文件下载走 `/v1/rpc` Base64 JSON 传输模式；
   - 在 Sandbox Node 开辟原生 HTTP 二进制流式端点（`GET /v1/files/stream`），支持 Chunked 传输；
   - 网关 `platform-api` 以流式生成器（`StreamingResponse`）透传，不在内存中缓存全量字节。
4. **流式超时分级与连接池扩容**：
   - 将流式下载从控制面 30s 整体超时中解耦，采用“首包连接超时 10s + 读流空闲超时 15s”的流式超时模型；
   - 扩容 HTTP 连接池（从 `max_connections=1` 提升至独立池 20+ 并发）。
5. **智能归档打包与前端防护**：
   - 工作区打包 Zip 对已压缩格式（`.pptx`, `.docx`, `.xlsx`, `.zip`, `.png`, `.jpg`, `.mp4`）强制走 `ZIP_STORED`，免除 CPU 压缩空转；
   - 前端按钮增加 `isDownloading` 状态锁定、Loading 视觉反馈及 `AbortController` 取消防护。

## 方案设计

### 整体架构图

```mermaid
flowchart TD
    subgraph 客户端与接入层["1. 用户客户端 (platform-web)"]
        UI[WorkspacePreview / Panel]
        UI -->|防抖点击 + Loading 锁<br/>直接发起流式 GET| GW
    end

    subgraph 网关与流式透传层["2. 网关与调度层 (platform-api & runtime-service)"]
        GW[Platform-API 网关]
        GW -->|流式透传 StreamingResponse<br/>独立流式超时 / 连接池| NC[Node Client 专用流式池]
        NC -->|mTLS 原生 HTTP 流请求| SN_HTTP[Sandbox Node Stream Handler]
    end

    subgraph 远端Docker宿主机与沙箱层["3. 远端宿主机 (Docker Host / sshmy2)"]
        SN_HTTP -->|1. 下载/预览: 旁路容器<br/>直接读取宿主机磁盘 (sendfile)| Disk[(宿主机持久化目录<br/>/var/lib/.../workspaces/thread_id)]

        AgentExec[Agent 执行请求<br/>/v1/bash/exec] --> SC[Thread Sandbox Controller]
        SC -->|检查容器存活状态| D_API[Docker Engine API]
        D_API -->|未运行: 按需秒级拉起| Cont[Thread Docker 容器]
        Cont -->|Bind Mount 挂载| Disk

        Reaper[Reaper 空闲巡检器<br/>每分钟检查一次] -->|空闲超过 10 分钟| D_API
        Reaper -.->|docker stop / rm<br/>内存归零| Cont
    end
```

### 资源开销对比：预热池 vs 按需冷启动（算笔明白账）

以当前 `sshmy2`（4核、3.6 GiB 内存、40GB SSD）为例：

| 指标 | 预热池方案 (Warm Pool) | 按需冷启动 + 空闲自动销毁 (本方案) | 收益与结论 |
| :--- | :--- | :--- | :--- |
| **空闲时内存占用** | 3 个容器常驻：**约 300MB ~ 1.2GB** 内存 | 0 个活跃容器：**0 MB** 内存（守护进程仅占 ~15MB） | **节省 95% 以上常驻内存**，彻底消除小机 OOM 风险 |
| **单会话并发上限** | 内存易被占满，最多同时维持 3~5 个容器 | 按需回收，同一时间只有活跃操作的容器占用内存，并发承载力提升 3 倍 | 资源利用率最大化 |
| **冷启动延迟** | 毫秒级（但换来内存枯竭） | 首次交互拉起容器约 **0.8 ~ 1.5 秒**（Docker 本地镜像直接 run） | 仅在首轮对话产生轻微等待，后续交互全程热态复用 |
| **文件下载体验** | 若绑定在容器内，受容器状态制约 | **完全由宿主机磁盘直读**，即使容器已销毁也可 **0.01 秒极速下载** | 极致稳定，免除容器启停对文件查看的干扰 |
| **磁盘占用** | 镜像共享层（只占一次基础镜像空间） | 镜像共享层 + 各 Thread 独立工作区目录（仅存真实业务文件） | 磁盘占用完全相同，且无额外可写层膨胀 |

---

### 关键改动点

#### 1. 远端沙箱节点（Sandbox Node）：新增原生流式下载端点与无损打包
- **文件**：`apps/runtime-service/src/runtime_service/sandbox_node/`
- **改动**：
  - 新增 `GET /v1/files/stream` 路由：接收 `path`、`thread_id`，直接通过 `FileResponse` 或 aiofiles 生成器以 64KB 为分块吐出 raw octet-stream，设置标准响应头（`Content-Disposition`, `Content-Length`, `ETag`）。
  - 修改 `storage.py` 中的 `archive` 方法：
    遍历文件列表时，判断文件后缀名，若属于已压缩格式（`.pptx`, `.docx`, `.xlsx`, `.zip`, `.png`, `.jpg`, `.mp4` 等），使用 `zipfile.ZIP_STORED`，文本类型使用 `zipfile.ZIP_DEFLATED`；支持生成临时 zip 文件并由 `FileResponse` 流式发送，传输完毕后清理。

#### 2. 对话沙箱生命周期控制器（Thread Sandbox Controller & Reaper）
- **文件**：`apps/runtime-service/src/runtime_service/sandbox_node/controller.py`
- **改动**：
  - 维护容器状态表：记录 `thread_id -> {container_id, status, last_active_at}`。
  - **按需拉起（Ensure Active）**：
    当接收到 Agent 的执行指令（Bash/Python/Tool）时，先检查容器：
    - 若 `docker inspect` 状态为 running，刷新 `last_active_at`，直接执行；
    - 若容器不存在或已退出，调用 Docker Engine API 创建容器：
      `docker run -d --name sandbox_{thread_id} -v {host_workspace}:/workspace:rw --cpus 2.0 --memory 4g ...`
  - **空闲回收（Reaper Daemon）**：
    后台轻量定时任务（每 60 秒检查一次）：
    遍历当前活跃容器，若 `now - last_active_at > IDLE_TIMEOUT_SECONDS`（默认 600 秒，即 10 分钟），且当前无正在执行的命令，执行 `docker stop` 并 `docker rm`，更新状态为 `stopped`。

#### 3. 运行时与网关：流式透传与连接池隔离
- **文件**：
  - `apps/runtime-service/src/runtime_service/workspace/node_client.py`
  - `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py`
- **改动**：
  - 在 `node_client.py` 中开辟专用的流式客户端 `_stream_transport_client`，配置 `limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)`，独立于控制面锁 `_clients_lock`。
  - 在 `read_file` 逻辑中，废弃获取全部字节再返回的逻辑，直接通过 `response.aiter_bytes()` 包装为异步生成器返回给网关。
  - 引入流式超时：`httpx.Timeout(connect=10.0, read=20.0, write=20.0, pool=10.0)`，只要网络数据流持续传输，就不受 30s 业务总超时中断。

#### 4. 前端交互加固（防狂点、防雪崩）
- **文件**：
  - `apps/platform-web/src/components/workspace/WorkspacePreview.vue`
  - `apps/platform-web/src/composables/useThreadWorkspace.ts`
- **改动**：
  - 在 `useThreadWorkspace` 中声明 `downloadingFiles = ref<Set<string>>(new Set())`。
  - “直接下载原文件”与“打包下载”按钮均绑定对应 loading 态，并在下载进行中设置 `:disabled="true"` 禁用点击，鼠标指针呈现 `cursor-not-allowed`。
  - 点击后触发全局 Toast 提示：“正在准备文件传输，请稍候...”。
  - 绑定 `AbortController`，当组件卸载或用户切换预览文件时，自动取消上一次未完成的下载请求，释放后端网络信道。

---

## 链路影响

### 受影响的调用链路
1. **Agent 代码/命令执行链路**：
   - 增加沙箱按需拉起检查逻辑（冷启动时增加约 0.8~1.2 秒容器启动时间，命中热态时无感知）。
2. **工作区单文件下载链路**：
   - 原链路：`Web -> API -> Runtime -> Node RPC (Base64 JSON 全量内存) -> 20.6s -> 容易超时 502`
   - 新链路：`Web -> API 流式代理 -> Node 原生 HTTP 流 (宿主机裸读 64KB chunk) -> 毫秒级首包响应 -> 带宽跑满下载`
3. **工作区打包 Zip 链路**：
   - 移除在内存中对已压缩大文件二次压缩的逻辑，打包耗时从 21.5s 降至 1s 内。

### 降级与容灾
- **Docker 守护进程异常**：若宿主机 Docker daemon 异常，执行命令抛出清晰的 `sandbox_engine_unavailable`（503），但**文件预览和下载依然可用**（因为下载直接读宿主机磁盘，完全不依赖 Docker daemon）。
- **容器无法拉起**：若系统资源紧张导致容器创建失败，触发重试一次；若依旧失败，释放陈旧孤儿容器后再试。
