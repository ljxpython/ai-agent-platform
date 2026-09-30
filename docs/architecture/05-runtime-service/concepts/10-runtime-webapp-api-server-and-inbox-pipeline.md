# 运行时 Web 控制面、消息收件箱与对账引擎深度剖析 (Runtime WebApp, MessageInbox & Reconciliation Pipeline)

> **老王暴躁技术流寄语**：
> “很多菜鸟一听‘Agent 底座’，就以为只要起一个跑模型的死循环就完事了。我呸！在真实生产环境下，模型在后台跑一个长达数分钟的深度分析（Deep Research），用户在前端聊天框里突然发了一句‘等等，把时间范围改成最近三个月’，你怎么把这句话插队送进正在跑的模型嘴里？！
> 如果服务重启或者发生故障，那些排在半路上的消息怎么对账？停机的时候那些开在后台的 Docker 终端容器怎么彻底杀干净，不把宿主机占满变僵尸？！
> `apps/runtime-service/src/runtime_service/webapp.py` 就是整个 `runtime-service` 控制面 API Server 进程的核心组合根（Composition Root）！它守着大门、管着路由、捏着数据库咨询锁，是整个底座平稳运行的定海神针！”

---

## 一、30秒速通全景：`webapp.py` 五大核心机制速查表

在 `apps/runtime-service/langgraph.json` 中，控制面 HTTP 入口绑定了此文件：
```json
"http": {
    "app": "./src/runtime_service/webapp.py:app"
}
```

`webapp.py` 总共 289 行代码，集中体现了微服务控制面与计算核物理切分的设计哲学：

| 核心机制 | 核心代码 / 端点 | 物理职责 (大白话) | 解决的生产致命痛点 |
| :--- | :--- | :--- | :--- |
| **一、生命周期看门狗** | `lifespan(app)` | 负责系统启停资源治理：启动连接 Langfuse；停机时异步执行 `terminals.shutdown` 强杀清理所有活跃 PTY 终端容器。 | 杜绝 K8s 节点滚动发布或容器重启时，宿主机残留上百个后台僵尸 Docker 容器吃光句柄。 |
| **二、八大业务子路由汇聚** | `app.include_router(...)` | 将工作区、终端、文档安检、图片、动态技能、记忆、治理等 8 大子路由统一挂载对外暴露。 | 保持各功能模块高度内聚自治（高内聚低耦合），组合根只负责装配，不写业务死循环。 |
| **三、消息收件箱进港中枢** | `POST /internal/threads/{thread_id}/messages` | 接收上层用户在 Agent 运行期间的“插队”追加消息，执行 Delegation 验签、双向委托核对并申请 Postgres 咨询锁有序入库。 | 杜绝行锁在空表失效、杜绝消息乱序与掉电丢失，支持高并发长周期 Agent 执行中途实时交互。 |
| **四、消息终态对账自愈** | `GET /internal/threads/{thread_id}/messages` | 前端拉取消息时，自动扫描未结挂起 Run（`pending_runs`），触发 `reconcile_run` 收敛终态原因（`run_ended` / `run_cancelled`）。 | 杜绝由于网络超时、用户取消导致排队消息沦为永不被消费的“幽灵悬挂消息”。 |
| **五、平台能力反射字典** | `GET /internal/capabilities/tools`<br>`GET /internal/capabilities/graphs/{id}` | 向控制面（Platform-API）与资产目录声明底座当前的真实物理能力（可用工具、是否支持工作区、是否支持终端）。 | 控制面无需猜测执行面能力，动态探测与展示，杜绝因服务版本不一致导致的跨端硬编码。 |

---

## 二、架构全景拓扑：`webapp.py` 如何统领控制面进程

在双进程部署架构中，`webapp.py` 扮演着“迎宾大厅”与“调度总台”的角色：

```
+----------------------------------------------------------------------------------------------------+
|                                    Platform-API 控制面 / 前端网关                                   |
+----------------------------------------------------------------------------------------------------+
       │                                     │                                      │
 (1) 追加插队消息                       (2) 查看文件树/终端/技能               (3) 查询底座能力
       │                                     │                                      │
       ▼                                     ▼                                      ▼
+────────────────────────────────────────────────────────────────────────────────────────────────────+
|                     apps/runtime-service/src/runtime_service/webapp.py (API Server)                |
|                                                                                                    |
|  [海关验签与双向委托] ──> authenticate() + _verified_run_read_authorization()                      |
|                                                                                                    |
|  [生命周期看门狗 lifespan] ──> initialize_langfuse() ──> [停机排空] terminals.shutdown               |
|                                                                                                    |
|  [八大业务子路由汇聚]                                                                                |
|  ├── /images       (图片上传与校验)               ├── /workspace (文件树分页/安全预览/ZIP)           |
|  ├── /documents    (用户文档体检落盘)             ├── /terminal  (PTY 终端与 WebSocket)            |
|  ├── /skills       (动态技能管理)                 ├── /memory    (长期记忆检索与写入)               |
|  └── /governance   (模式与审批配置)               └── /titles    (会话标题与摘要生成)                |
|                                                                                                    |
|  [MessageInbox 消息进港端点]                                                                         |
|  POST /internal/threads/{id}/messages                                                              |
|  ├── 探测目标 Run 状态 (GET /threads/{id}/runs/{target_run_id})                                    |
|  └── MessageInbox.enqueue(): 申请 pg_advisory_xact_lock 咨询锁，分配单调递增 sequence 落库           |
|                                                                                                    |
|  [消息终态对账引擎]                                                                                 |
|  GET /internal/threads/{id}/messages                                                               |
|  └── 扫描 pending_runs ──> reconcile_run() 消除悬挂幽灵消息                                        |
+────────────────────────────────────────────────────────────────────────────────────────────────────+
       │                                                                            │
       │ (通过 PostgreSQL 数据库通信，零直接内存依赖)                                  │
       ▼                                                                            ▼
+────────────────────────────────────────+                +──────────────────────────────────────────+
|  运行时独立数据库 (Runtime Postgres DB)   |                |       独立后台 Worker 进程 (Worker)       |
|  - runtime_message_inbox (消息队列表)   |                |       - 无对外 HTTP 端口                  |
|  - checkpoints (LangGraph 图状态表)    | <───────────── |       - MessageQueueMiddleware 消费消息  |
+────────────────────────────────────────+                |       - 驱动 Pregel 图与 Docker 沙箱全速运行|
                                                          +──────────────────────────────────────────+
```

---

## 三、`http/` 模块全员挂载实证与八大子路由业务深度剖析

很多初学者看到 `apps/runtime-service/src/runtime_service/http/` 文件夹下散落着 8 个路由文件，脑子里直犯嘀咕：
“这些子路由到底有没有全部挂载到 `webapp.py`？它们分别由谁调用？在前端实际界面和整个平台链路中扮演什么角色？”

**艹，老王我用白纸黑字的代码告诉你：全部挂载！零遗漏！**

### 1. 挂载事实源代码实证

翻开 `apps/runtime-service/src/runtime_service/webapp.py` 第 47 行到第 54 行，挂载代码清清楚楚：

```python
# 对应 apps/runtime-service/src/runtime_service/webapp.py
app = FastAPI(lifespan=lifespan)

# 八大业务子路由 100% 全员挂载进组合根：
app.include_router(images_router)           # 1. 多模态图片资产通道
app.include_router(documents_router)        # 2. 会话文档安检与进出港
app.include_router(workspace_router)        # 3. 工作区文件树/制品/安全预览/ZIP打包/Fork
app.include_router(terminal_router)         # 4. 沙箱交互 PTY 伪终端会话
app.include_router(dear_governance_router)  # 5. 会话级 DearFlow 记忆纠偏与提取
app.include_router(dear_skills_router)      # 6. 自定义技能包动态热加载与治理
app.include_router(dear_memory_router)      # 7. 全局/项目级长期记忆偏好库
app.include_router(title_summary_router)    # 8. 会话标题轻量 LLM 自动摘要
```

`apps/runtime-service/src/runtime_service/http/` 目录下一共 8 个业务 Python 模块，**被 `webapp.py` 100% 毫无保留全部挂载**！每一个路由都有极强烈的生产业务价值，共同支撑起了前端 Web 交互界面的完整生命周期。

---

### 2. 八大子路由业务职责与当前项目 UI 映射全景矩阵

| 序号 | 子模块名称 | 路由前缀 (Prefix) | 核心暴露端点 | 对应前端界面业务场景 | 核心设计哲学与安全护栏 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `workspace.py` | `/internal/threads/{thread_id}` | `GET /workspace/tree`<br>`GET /artifacts`<br>`GET /workspace/content`<br>`GET /workspace/zip`<br>`GET /workspace/preview`<br>`POST /workspace/fork` | **聊天界面右侧抽屉：工作区面板**<br>• 文件树层级浏览与分页滚动<br>• 不可变制品卡片展示<br>• 文件原样下载与代码查看<br>• 一键打包整包 ZIP 下载<br>• 网页内嵌安全沙箱预览 (HTML/SVG)<br>• 会话分支 (Fork) 继承上游工作区 | **防 Stored XSS 与路径穿越**：<br>预览时强制注入 `HTML_CSP` 超严沙箱头，禁用所有外部网络和脚本提升；下载加 `nosniff` 与 `sandbox; default-src 'none'`；Fork 复制忽略外部软链接防止逃逸出沙箱。 |
| **2** | `terminal.py` | `/internal/threads/{thread_id}/terminals` | `POST /`<br>`GET /`<br>`GET /{id}/output`<br>`POST /{id}/input`<br>`POST /{id}/resize`<br>`DELETE /{id}` | **聊天界面右侧抽屉：xterm.js 网页终端**<br>• 用户实时查看 Agent 在后台执行的 bash 过程<br>• 人工介入直接在容器沙箱里敲命令调试<br>• 动态调整终端窗口行列尺寸自适应 UI | **人工接管与调试，Never an Agent Tool**：<br>绝不暴露给 Agent 自身避免循环输入死锁；基于操作系统 PTY 与环形缓冲区，按 `sequence` 严格保序；进程退出在 Lifespan 中强制 `docker rm -f` 销毁容器。 |
| **3** | `documents.py` | `/internal/threads/{thread_id}/files` | `PUT /uploads/{sha256}`<br>`GET /content` | **聊天输入框附件上传 & 制品下载**<br>• 用户向会话上传 PDF 论文、代码文件、CSV 表格<br>• 用户在聊天流中点击下载 Agent 导出的报告文档 | **流式安检与 MIME 白名单**：<br>20MB 硬顶阈值；流式分块异步写入杜绝内存爆炸；下载强制带 `Content-Disposition: attachment` 防止浏览器直接解释执行恶意脚本。 |
| **4** | `images.py` | `/internal/threads/{thread_id}/images` | `PUT /uploads/{sha256}`<br>`GET /content` | **多模态图片输入与绘图回显**<br>• 用户上传截图、UI 设计稿供 Vision 模型分析<br>• Agent 调用 Python/Matplotlib/Graphviz 生成的图表在前端聊天气泡中渲染显示 | **强类型图片引用 (ImageRef)**：<br>严格限制 `image/jpeg`、`png`、`gif`、`webp`；生成不可变哈希路径，供 LangChain 多模态消息块与前端 `<img>` 标签无缝消费。 |
| **5** | `dear_skills.py` | `/internal/dear/skills` | `GET /`<br>`POST /custom`<br>`PUT /custom/{slug}`<br>`PATCH /custom/{slug}`<br>`DELETE /custom/{slug}`<br>`GET /{source}/{slug}`<br>`GET /{source}/{slug}/content` | **平台左侧控制台：技能治理大厅 (Skills Hub)**<br>• 浏览公共内置 23+ 技能列表<br>• 用户上传自定义私有技能 ZIP 压缩包<br>• 在线查看 `SKILL.md` 描述与代码<br>• 一键启用/禁用技能开关 | **租户私有资产与乐观锁并发控制**：<br>无 thread 依赖；上传 Base64 包执行 1MB 内存解压防炸弹校验；修改与开关状态带 `expected_revision` 乐观锁防多管理员同时覆盖；提供只读预览。 |
| **6** | `dear_memory.py` | `/internal/dear/memory` | `GET /`<br>`POST /` | **平台个人设置页：偏好与长期记忆中心**<br>• 查看自己的跨会话核心事实（Facts）<br>• 审核系统推荐的候选记忆（Candidates）<br>• 手工新增偏好（如“回答请使用中文，代码写单元测试”）或删除过时偏好 | **无会话依赖的项目级用户记忆资产**：<br>绑定 `(tenant_id, project_id, user_id)` 事实身份；统一返回包含配额（Limits）的 `envelope` 包装对象；单条限制 1000 字符，总条数上限 100 条。 |
| **7** | `dear_governance.py` | `/internal/threads/{thread_id}/dear` | `GET /memory`<br>`POST /memory` | **会话内侧边栏：当前对话记忆提取检查器**<br>• 实时查看大模型在本轮对话中萃取出的临时记忆<br>• 用户人工纠错或立即抹除某条不准确的对话上下文记忆 | **会话强绑定与显式管理审计**：<br>强制锁定当前 `thread_id`；写操作必须持有 `tool_access: manage_memory`，且在记忆表中强制盖戳 `source_id="explicit-management"` 以便后续审计。 |
| **8** | `title_summary.py` | `/internal/threads/{thread_id}/title` | `POST /summarize` | **左侧会话历史侧边栏：会话标题自动更名**<br>• 用户发起第一轮提问后，侧边栏从默认的“新对话”自动提炼更名为 10 个字以内的精炼概括标题 | **非阻塞异步轻量提炼与容错降级**：<br>上层网关在首轮推理完成后异步触发；调用轻量极速模型，遇超时或模型异常自动熔断并静默降级为“新对话”，绝对不卡死主会话。 |

---

### 3. 八大子路由在当前系统中的物理流转大动脉

前端用户的每一个点击，是如何通过 Platform-API 穿透并最终打在 `webapp.py` 挂载的对应路由上的？看下面这张清晰到令人发指的端到端调用大动脉：

```
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                                    Platform-Web 前端交互界面                                 |
+─────────────────────────────────────────────────────────────────────────────────────────────+
   │ 1. 聊天发首问    │ 2. 传图片/文档    │ 3. 打开终端      │ 4. 浏览工作区    │ 5. 记忆/技能管理
   ▼                  ▼                  ▼                  ▼                  ▼
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                                 Platform-API 控制面网关服务                                  |
|   - 校验用户登录态与 RBAC 权限                                                                |
|   - 根据请求类型，签发 60 秒短命 Delegation JWT（带有特定 operation 与 thread_id scope）      |
|   - 将请求安全代理透传给底层 runtime-service 端口                                             |
+─────────────────────────────────────────────────────────────────────────────────────────────+
   │                  │                  │                  │                  │
   ▼                  ▼                  ▼                  ▼                  ▼
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                       apps/runtime-service/src/runtime_service/webapp.py                    |
|                                                                                             |
|   [title_summary.py]   [images.py / documents.py]   [terminal.py]   [workspace.py]          |
|   POST .../title/sum   PUT .../uploads/{sha256}    POST/GET ...    GET .../tree /preview   |
|         │                        │                        │               │                 |
|         │                        │                        │               │                 |
|   [dear_governance.py] [dear_memory.py]        [dear_skills.py]    [MessageInbox]           |
|   GET/POST .../dear/mem GET/POST .../dear/mem  GET/POST .../skills POST .../messages        |
+─────────────────────────────────────────────────────────────────────────────────────────────+
          │                        │                        │               │
          ▼                        ▼                        ▼               ▼
+──────────────────+     +──────────────────+     +──────────────────+  +─────────────────────+
| 轻量 LLM 提炼引擎 |     | 宿主机安全工作区  |     |  Docker 伪终端   |  | 运行时数据库         |
| (10字精炼标题)   |     | (SHA256 哈希沙箱)|     | (PTY 交互式会话) |  | (Postgres 咨询锁)   |
+──────────────────+     +──────────────────+     +──────────────────+  +─────────────────────+
```

### 4. 关键设计哲学深潜：为什么必须由 `webapp.py` 统筹挂载？

很多架构新手会问：“老王，为什么不把这些 HTTP 接口直接分散写在各个子模块里自起 FastAPI，或者直接全堆在 Worker 里？”

**艹，这是典型的分布式单体思维和玩具工程！老王我给你点出三大设计命脉：**

1. **组合根原则（Composition Root Pattern）**：
   `webapp.py` 是整个 API Server 的唯一总指挥。子模块（`http/workspace.py`、`http/terminal.py` 等）只管暴露纯粹的 `APIRouter`，自身不持有应用的生命周期，不负责数据库连接池的启停。组合根集中装配中间件、集中挂载异常处理器（`auth_exceptions.HTTPException`），实现了代码的高度整洁与模块插拔能力。
2. **读写分离与动静隔离**：
   - 静态/轻量读操作（如 `GET /workspace/tree`、`GET /artifacts`、`GET /terminal/output`）：毫秒级返回，由 API Server 轻松支撑几千高并发 QPS，绝不打扰后院正在跑图的 Worker 进程！
   - 大计算量写操作（Agent 状态机推理）：由 Worker 后台慢条斯理地跑。
   如果把文件浏览和终端交互塞到 Worker 里，模型一跑满，前端看个文件树都要转圈卡死！
3. **安全纵深防御（Defense-in-Depth）**：
   所有 8 个路由文件在进入具体逻辑前，**第一行代码无一例外都是 `authenticate(authorization)` 验签**，并严格检查 `scope["operation"]`、`scope["thread_id"]` 和 `require_tool_access(facts, ...)`。就算上层网关不小心漏放了一个非法请求，底座控制面在进入业务逻辑前就直接 `403 Forbidden` 把攻击者踹出门外！

---

## 四、生命周期看门狗与消息进港/对账核心机制深度剖析

### 机制一：生命周期看门狗与资源强杀排空 (`lifespan`)

在容器化或本地开发环境中，最怕进程被 `SIGTERM` 或 `SIGINT` 杀掉后，遗留了一堆子进程和 Docker 容器在后台狂转。

```python
# 核心源码截取：webapp.py
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_langfuse()
    try:
        yield
    finally:
        from runtime_service.workspace.terminal import terminals

        # 核心防泄漏设计：停机时强制排空并强杀所有处于活跃状态的 Docker 终端容器
        await asyncio.to_thread(terminals.shutdown)
        close_langfuse(timeout_seconds=5.0)

app = FastAPI(lifespan=lifespan)
```
- **老王点评**：
  “看到 `finally` 里面的 `await asyncio.to_thread(terminals.shutdown)` 没有？`terminals` 在内部不仅会关闭 Python 侧的 PTY master/slave 描述符，还会顺藤摸瓜找到对应的 Docker 容器名，执行 `docker rm -f <container_id>` 并通过 `os.killpg` 杀光子进程组！很多搞玩具 Agent 的把停机当儿戏，容器一重启，宿主机 `docker ps` 一看，几百个旧容器在那挂着，把文件句柄和内网 IP 全占死了，老王我最恨这种拉完屎不擦屁股的代码！”

---

### 机制二：MessageInbox 异步消息进港四重防线 (`enqueue_message`)

当智能体在跑图时，外部系统调用 `POST /internal/threads/{thread_id}/messages` 追加消息。这个端点是全系统并发与安全要求最高的地方：

#### 1. 严格防伪与多租户隔离
```python
# webapp.py: enqueue_message()
facts = await authenticate(authorization)
scope = facts.get("runtime_scope", {})
if (
    scope.get("operation") != "message-enqueue"
    or scope.get("thread_id") != thread_id
    or scope.get("project_id") is None
    or scope.get("assistant_id") not in {"reference_agent", "showcase_demo", "dearflow_agent"}
):
    raise HTTPException(403, "thread scope denied")
```
- **绝不相信客户端声明**：网关传过来的 Delegation Token 必须白纸黑字写明 `operation == "message-enqueue"`，且路径中的 `thread_id` 必须和 Token 签发的 `thread_id` 丝毫不差，彻底杜绝越权串号。

#### 2. 双向委托凭证核对 (`_verified_run_read_authorization`)
```python
# webapp.py: 校验跨端委托一致性
async def _verified_run_read_authorization(facts: dict, authorization: str | None, thread_id: str) -> str:
    if authorization is None:
        raise HTTPException(401, "Unauthorized")
    read_facts = await authenticate(authorization)
    read_scope = read_facts.get("runtime_scope", {})
    if (
        read_scope.get("operation") != "read"
        or read_scope.get("thread_id") not in {None, thread_id}
        or any(read_facts.get(key) != facts.get(key)
               for key in ("identity", "tenant_id", "project_id", "runtime_credential_id"))
    ):
        raise HTTPException(403, "run read delegation mismatch")
    return authorization
```
- **核心黑科技**：入队请求必须同时提供两个 Token——一个用于入队写操作，另一个附带用于回查目标 Run 状态的读凭证（`x-runtime-run-read-authorization`）。服务端对这两个 Token 进行交叉比对，四项核心事实（`identity`、`tenant_id`、`project_id`、`runtime_credential_id`）必须完全相等，彻底封杀中途掉包攻击！

#### 3. 目标 Run 状态探测与幂等保护
在真正写入数据库前，它通过内部 HTTP 客户端向自身探查目标 Run 状态：
```python
async with httpx.AsyncClient(base_url=os.getenv("RUNTIME_SELF_URL", "..."), ...) as client:
    response = await client.get(f"/threads/{thread_id}/runs/{payload.target_run_id}")
    response.raise_for_status()
    if response.json().get("status") != "running":
        # 如果 Run 已经结束或取消，检查这是否是之前已经成功写入过的重试请求
        existing = await asyncio.to_thread(MessageInbox(dsn).has_message, ...)
        if not existing:
            raise HTTPException(409, "run_changed")
```
- 如果大模型已经跑完了或者被用户取消了，新的插队消息直接被 `409 Conflict` 挡回去，绝不浪费算力和存储！

#### 4. PostgreSQL 咨询锁原子入库
```python
receipt = await asyncio.to_thread(
    MessageInbox(dsn).enqueue,
    thread_id=thread_id,
    target_run_id=str(payload.target_run_id),
    sender_id=str(facts.get("identity", "")),
    client_message_id=str(payload.client_message_id),
    idempotency_key=payload.idempotency_key,
    content=payload.content,
    authorization_ref=payload.authorization_ref,
)
```
- 底层在 `MessageInbox.enqueue` 中通过 `SELECT pg_advisory_xact_lock(...)` 锁定当前线程，获取连续单调递增的序号，保证即使一瞬间涌入 100 条并发追加消息，在数据库层面也绝对严格保序！

---

### 机制三：消息终态自愈对账引擎 (`list_messages`)

很多分布式系统最怕“悬挂孤儿”：如果一个 Run 在运行途中因为宿主机断电、网络超时或者被管理员在控制台强行 Cancelled，之前排在队列里的未消费消息该怎么办？

在 `GET /internal/threads/{thread_id}/messages` 中，`webapp.py` 实施了一套极其优雅的**主动对账机制（Active Reconciliation）**：

```python
# 扫描当前线程下所有未决的 Run
pending_runs = await asyncio.to_thread(
    inbox.pending_runs, thread_id=thread_id, sender_id=str(facts["identity"])
)
for run_id in pending_runs:
    response = await client.get(f"/threads/{thread_id}/runs/{run_id}")
    status = response.json()["status"]
    # 只要 Run 已经到达终态 (success/error/timeout/cancelled/interrupted)
    if status in {"success", "error", "timeout", "cancelled", "interrupted"}:
        reason = "run_cancelled" if status == "cancelled" else "run_ended"
        # 立即触发对账收敛，将未被消费的消息打上终态原因，释放队列
        await reconcile_run(
            inbox,
            get_checkpointer(),
            thread_id=thread_id,
            run_id=run_id,
            terminal_reason=reason,
        )
```
- **核心价值**：对账不依赖复杂的定时扫描定时器，而是在客户端每一次拉取消息时就近触发。保证了查询结果的**强最终一致性**，彻底消灭队列中的幽灵消息！

---

### 机制四：富媒体多模态输入校验网关 (`EnqueueMessage`)

在 `EnqueueMessage` Pydantic 模型中，`content` 支持字符串与结构化多模态数据块（文本、图片、文件），每一块都经过了极严苛的格式消杀：

```python
# webapp.py: EnqueueMessage.validate_content()
for block in content:
    if block.get("type") == "text":
        extras = block.get("extras", {})
        if "runtime_file" in extras:
            validate_file_ref(extras["runtime_file"]) # 强校验上传文件 SHA256 与路径
        if "runtime_image" in extras:
            validate_image_ref(extras["runtime_image"]) # 强校验图片格式
    elif block.get("type") in {"image", "file"}:
        # 严格限制 MIME 类型白名单，并校验 Base64 数据合法性
        allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"} if block["type"] == "image" else {"application/pdf"}
        if block.get("mimeType") not in allowed:
            raise ValueError("unsupported_message_block")
        base64.b64decode(block["data"], validate=True)
```
- 客户端休想塞入任何畸形数据或非法扩展名，在入口 Pydantic 校验阶段就全部就地正法！

---

## 五、切斯特顿栅栏：Naive vs Production 架构攻防对比

| 场景 / 攻击面 | Naive 粗暴做法 (玩具设计) | Production 生产做法 (`webapp.py` 严苛体系) | 栅栏背后的血泪教训 (为什么必须这么做) |
| :--- | :--- | :--- | :--- |
| **子路由架构拓扑** | 各子功能自起独立 HTTP 端口或堆在 Worker 进程里 | 统一由 `webapp.py` 组合根挂载 `http/` 全部 8 大路由，集中管理 Lifespan 与鉴权异常 | 分散起服务增加几十个网络端点导致运维灾难；塞在 Worker 导致模型推理打满 CPU 时前端文件树与终端彻底卡死！ |
| **服务优雅停机** | 进程收到信号直接 `sys.exit()` | `lifespan` 钩子调用 `terminals.shutdown` + Langfuse 5秒刷盘超时 | 简单退出会导致正在交互的 PTY 终端在宿主机残留僵尸 Docker 容器，积累成百上千个直到宿主机崩溃！ |
| **消息并发追加** | 直接往内存队列 `asyncio.Queue` 塞消息 | 严格 Delegation 验签 + 目标 Run 状态校验 + `pg_advisory_xact_lock` 咨询锁入库 | 内存队列进程一挂全丢；无锁并发导致序号冲突；Run 已结束后追加的消息会永远挂在内存里无法释放！ |
| **跨会话越权** | 只要携带了 Token 就允许发消息 | 强校验 `thread_id` + 双向委托 Token 事实一致性比对 | 黑客可能用自己的合法 Token 去修改别人的 `thread_id`，偷梁换柱向受害者会话注入恶意提示词！ |
| **多模态消息上传** | 客户端传什么 Base64 就原样接收 | 严格白名单过滤 MIME 类型，严格验证 Base64 编码合法性与文件元数据 | 攻击者上传畸形二进制或超大文件直接把下游大模型解析器搞到 OOM 崩溃！ |
| **异常消息悬挂** | 不管结束状态，消息就留在表里 | `list_messages` 时主动探查 Run 状态并触发 `reconcile_run` 对账终态 | 缺少对账机制，客户端界面会永远显示“消息发送中...”，造成前端状态彻底卡死！ |

---

## 六、老王架构不变量与避坑清单

1. **API Server 绝不执行耗时图计算**：`webapp.py` 作为控制面进程，其核心职责是 I/O 网关、路由转发与消息持久化，严禁在此进程内直接启动模型推理计算。
2. **退出必须排空宿主机资源**：`lifespan` 必须在 `finally` 中显式清退所有 PTY 伪终端会话与 Docker 容器，不准留任何僵尸资源。
3. **入队必须双重校验身份与目标 Run 存活性**：入队前必须核实目标 Run 处于 `running` 状态，严禁向已完成或已取消的 Run 追加新消息。
4. **消息状态必须最终自愈收敛**：通过 `reconcile_run` 确保未消费的消息能够正确标记为 `run_ended` 或 `run_cancelled`，杜绝幽灵消息。
5. **子路由纯粹化不变量**：`http/` 下所有子路由文件严禁自建 FastAPI 实例或持有独立数据库连接池，必须作为纯粹的 `APIRouter` 由 `webapp.py` 统筹挂载与装配。
