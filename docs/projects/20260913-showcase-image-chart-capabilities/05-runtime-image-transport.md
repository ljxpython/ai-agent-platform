# 05 Runtime：图片存储、HTTP 与消息接入

## 目标

基于第一阶段的 `ImageWorkspace`、`ImageToolsMiddleware` 和 Showcase workspace，补齐 HTTP 上传/读取、轻量引用解析和产物元信息。协议以 [04](04-platform-image-contract.md) 为准。

**状态：规划中，全部任务待实施。** 本文标为“新增”的路径/函数是拟建内容，不能作为当前已实现功能引用。

## 1. 文件与函数清单

下表 Runtime 相对路径均以 `apps/runtime-service/` 为根。

| 文件 | 现有/新增 | 函数/类及具体改动 |
| --- | --- | --- |
| `src/runtime_service/workspace/scoped.py` | 新增 | `hashed_thread_root(base_dir, tenant_id, project_id, thread_id)`：抽取现有 SHA-256 派生，纯路径计算，不创建资源 |
| `src/runtime_service/services/demo/showcase_demo/backend.py` | 修改 | `DockerWorkspaceBackend.__init__()` 使用该函数；不改变 id、现有路径或初始化语义 |
| `src/runtime_service/tools/images.py` | 修改 | `ImageWorkspace.put_upload(data, sha256)`、`describe(path)`、`read_asset(path)`；复用 `_directory/read/image_type` 的 dir_fd/O_NOFOLLOW 边界 |
| `src/runtime_service/workspace/image_refs.py` | 新增 | `ImageRef` 校验、`parse_image_reference_block()`、`build_image_reference_block()`、`normalize_image_messages()`；集中消息/HTTP/工具结果共用的字段规则 |
| `src/runtime_service/http/__init__.py`、`http/images.py` | 新增 | APIRouter；`upload_thread_image()`、`read_thread_image()`；签名主体来自 authenticate，输入 thread_id/hash/query |
| `src/runtime_service/webapp.py` | 修改 | `app.include_router()`；`EnqueueMessage.validate_content()` 接受受限 text.extras.runtime_image；入队前校验引用可读、真实总尺寸 |
| `src/runtime_service/runtime/auth.py` | 修改 | `_parse_scope()` 增加 image-upload/image-read operation 枚举，保留身份一致性检查 |
| `src/runtime_service/auth/platform.py` | 修改 | 原生 Server 资源事件中拒绝 image-* scope；不改变 authenticate 的 key 来源和旧 scope 规则 |
| `src/runtime_service/middlewares/images.py` | 修改 | ImageToolsMiddleware 增加消息引用规范化/模型请求投影；继承的 HITL 审批行为保留 |
| `src/runtime_service/services/demo/showcase_demo/agent.py` | 修改 | 明确 workspace 绑定、图片消息处理与 MessageQueueMiddleware 的执行顺序；schema 探测仍无 IO |
| `src/runtime_service/services/demo/showcase_demo/chart.py` | 修改 | `persist_image()` 在路径 content 之外保留图片 refs 到 structuredContent |
| `src/runtime_service/services/demo/showcase_demo/prompts.py` | 修改 | 主模型通过 analyze_image 处理附件路径；chart-agent 汇报必须带实际 charts 路径 |
| `src/runtime_service/services/demo/showcase_demo/README.md` | 修改 | 记录新引用格式、上传/读取边界、HTTP/worker 共享文件根、验证命令 |

不修改 `MessageInbox` 表结构，不提高 64 KiB 限额，不实现自定义 checkpointer、事件总线或工具 Registry。

## 2. 工作区算法与资源创建

必须逐字等价地保留当前派生：

```python
scope = (tenant_id, project_id, thread_id)
scope_hash = hashlib.sha256(json.dumps(scope).encode()).hexdigest()
thread_root = base_dir.resolve() / scope_hash
image_root = thread_root / "workspace"
```

不能改成 compact JSON、sort_keys、自定义连接符或另一个 workspace helper 的 tenant/project/thread 多层目录。已有 `workspace/deepagent.py:build_deepagent_workspace()` 使用不同目录布局，不能直接替换 Showcase。

HTTP 图片路由仅支持可信 scope.assistant_id 为 `showcase_demo`，用 `RUNTIME_SHOWCASE_WORKSPACE_ROOT` 计算根。图工厂和 HTTP handler 均使用同一个 pure helper。

- GET 不创建目录、不调用 `prepare()`、不复制教学样例；不存在的图片返回 404，根配置错误/不可读返回 503。
- PUT 可以创建该线程 root/workspace/uploads，不创建 `.initialized`，后续 Agent 首次运行仍会正常初始化样例。
- schema-only get_agent() 不读 `.env` 文件、不 mkdir、不连接模型、不加载 npx。
- 服务启动配置保证 HTTP 与 worker root 一致；不通过请求传递 filesystem root。

## 3. 安全上传与读取算法

### `put_upload(data, sha256)`

1. 限制实际字节 ≤5 MiB；`image_type()` 验证 PNG/JPEG/WebP 与像素上限；核对实际 SHA-256。
2. 由真实类型确定 png/jpg/webp 扩展名，目标 `/workspace/uploads/<hash>.<ext>`。
3. 通过受信目录描述符逐层打开 scope/workspace/uploads；父目录和文件都拒绝符号链接、非普通文件、路径逃逸。
4. 先完整写入同目录的本次临时文件，flush/close 后用原子“不覆盖已有目标”的操作发布（例如 dir_fd 下 hard link 后 unlink 本次临时文件）；不能 O_EXCL 创建最终文件后边写边让并发 GET 读到半图。
5. 目标已存在时安全读取，检查真实字节 hash/type 一致再返回成功；若损坏/被覆盖则 409，不自动覆盖修复。
6. 所有异常只清理本次临时文件，保留已存在正式图片。取消协程也必须有 finally 清理，不执行广域删除。
7. 返回从真实字节计算的 ImageRef，不保存用户 filename 到路径，不额外建 metadata 数据库。

### `read_asset(path)` / `describe(path)`

1. 使用 04 的严格文件路径 grammar，图片 HTTP 面不复用“可以读任意 /workspace 文件”的宽泛权限。
2. 在同一文件描述符上 fstat、bounded read、检查真实图像；特殊文件、symlink、oversize 全拒绝。
3. uploads 校验 filename digest 与字节相符，损坏返回 409；generated/charts 使用现有 UUID 路径。
4. describe 返回 MIME/size/hash；工具生成时直接从已经持有的 bytes 计算，不重复下载模型产物。
5. 读取当前文件事实，不宣称 filesystem 随 checkpoint 回滚。已授权 shell 可以修改 workspace；前端收到强 ImageRef 时还需比较下载内容 hash，变化则显示“图片内容已变更”。旧历史纯路径只能展示当前文件版本。

### HTTP handler

复用现有 `webapp.py` 的 authenticate 模式，但图片 handler 必须验证精确 image operation、path.thread_id、scope.assistant_id、tenant/project 一致。hash/path/MIME/bytes 校验后调用上述方法。CPU/文件操作走 `asyncio.to_thread`，事件循环不阻塞。

错误返回固定 code，不把 OSError 的宿主路径、供应商 URL、traceback 放进客户端 detail。读图片不能触发生成或调用豆包。

## 4. 消息转换与执行顺序

### 新引用消息

`normalize_image_messages(messages, workspace)` 输入 LangChain messages；保持 message.id、role/type、tool_call_id、追加信息和普通文字，只转换/规范化图片引用块。

- 验证 `extras.runtime_image` 完整字段、限定路径、文件存在、hash/MIME/size 与实际一致。
- 根据真实数据重新构造 ref 文本，不执行原 filename/text 中指令；name 仅清洗后展示。
- 检查每条 human 消息的数量与实际总字节。Agent 运行前校验失败时停止对应输入，不把伪引用送给模型。
- 只处理 human 消息里的图片输入；不要把任意 tool/model 输出 extras 当成用户授权。
- `analyze_image` 本身继续在实际工具调用时校验/read 图片，初次校验不能替代工具边界校验。

### 普通启动和运行中补充消息

1. 首次 `abefore_agent`：先现有 RuntimeConfig/WorkspaceMiddleware 校验 scope 并准备 workspace，再检查当前输入/历史引用。
2. `MessageQueueMiddleware.abefore_model` 将已复核发送者权限的 HumanMessage 注入 State。
3. 图片规范化 `abefore_model` 在队列注入之后运行，处理新消息；不得只在 before_agent 处理一次而漏掉队列。
4. `awrap_model_call` 使用 request.override(messages=...) 创建发送给模型的副本；对 ref 块仅发送规范 text，去掉图片 UI extras，不改写审批工具调用消息。
5. 主模型看到 `/workspace/uploads/...`，自主调用 `analyze_image`；它不负责把 Base64 拼成工具参数。

必须用组合测试记录真实 hook 顺序：身份校验→workspace→队列注入→引用规范化→模型。Deep Agents 可能自动装配摘要 Middleware，实施时检验摘要输入也没有 Base64；必要时将规范化放到原生摘要前的钩子，不依据列表位置猜执行顺序。

### 旧 Base64 历史

对已存在、符合旧 `type:image/mimeType/data` 的 human 块：在最早模型前钩子按5 MiB输入限制严格解码、幂等物化到 uploads，以同 message.id 更新为 ref。重复运行不会多写文件；不离线遍历数据库。失败产生明确错误，不悄悄把错误图片当纯文字。

旧 GIF/PDF 在 Showcase 下报告“不支持此附件，请使用 PNG/JPEG/WebP”；其他 Agent 不挂载这项转换，保留现状。新 `/messages` 请求带旧 Base64 且超过队列限制仍拒绝，并指导新版前端先上传。

### 队列入口

`EnqueueMessage.validate_content()` 不再笼统放行任意 text extras；普通 text 仍维持字段白名单。只额外允许 04 格式。对含图片引用的请求，enqueue handler 在保存回执之前使用该线程 workspace 校验，校验失败不插入队列记录。
消费时再次检查，可发现队列等待期间图片被清理/改写。消费失败不得标 consumed；沿用现有运行失败/回执 reconciliation 机制，不伪造已识图成功。

## 5. 产物输出

- `generate_image` 改为 `(path_text, {runtime_images:[ref]})`，tool 配置 `content_and_artifact`；输入参数和强制审批不变。
- `chart.persist_image` 为下载并写入成功的图片构造 ref，附到 `structuredContent.runtime_images`；保留 path 文本，适配器管理 ToolMessage 包装。
- 不能返回 Base64 或供应商临时 URL 作为聊天持久化产物。原 MCP 非图片文本照常处理，电子表格仍不启用。
- chart-agent 最终汇报必须包含确切产物路径，父 Agent 原样引用，不编造 URL。用于刷新后父 task 的最小兼容展示，不另写跨子图结果状态聚合器。

## 6. 任务拆分

| ID | 任务 | 依赖 | 完成条件 |
| --- | --- | --- | --- |
| R1 | 提取 hashed_thread_root，增加 ImageRef 类型/严格校验 | G0 | 历史 scope-hash 不变；所有反例拒绝 |
| R2 | 实现 put_upload/read_asset/describe | R1 | 幂等并发上传、原子可见、损坏冲突、symlink/越界/特殊文件测试通过 |
| R3 | image operation 枚举和原生 Auth 事件拒绝 | 评审、R1 | image 凭证只能用于精确图片路由，旧 scope 用例不回归 |
| R4 | 新增两个 FastAPI handler 并挂载 | R2、R3 | raw PUT/GET 与所有 status/code/headers 满足04；GET无资源初始化副作用 |
| R5 | 新引用、旧Base64和队列消息规范化 | R1、R2 | hook顺序、身份隔离、重放和65,536字节边界通过 |
| R6 | 文生图/MCP artifact 与提示词 | R1 | 保留路径、真实ref、错误无成功artifact；审批次数不变 |
| R7 | 更新 Runtime 文档和部署说明 | R1—R6 | 路径/权限/配置与代码一致；不把未验收链路记done |

- [ ] R1
- [ ] R2
- [ ] R3
- [ ] R4
- [ ] R5
- [ ] R6
- [ ] R7

## 7. 验证要求与记录

新增 `tests/test_image_http.py`、`tests/services/showcase_demo/test_image_attachments.py`；扩展现有 `test_images_chart.py`、`tests/runtime/test_auth.py`、`test_platform_auth.py`。具体矩阵和命令见08。

必须覆盖：同hash并发PUT、无Content-Length超限、伪MIME/炸弹图、无效JWT/错线程、image token调用原生Server被拒绝、普通GET不mkdir、正常工具读图/生成/审批回归、模型看不到Base64、消费队列时权限仍检查。

验证记录：仅完成代码调研与本地 `HumanMessage` extras 序列化实验；上述新增接口/测试尚不存在，没有实现通过证据。
