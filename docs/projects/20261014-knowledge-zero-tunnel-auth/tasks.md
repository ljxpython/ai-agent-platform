# 知识库免隧道自治与单向架构治理 - 任务拆分

## Phase 1: 核心机制实现与配置对齐

### Task 1.1: 在 RAG 授权模块实装本地自治自验逻辑
- **改动内容：** 在 `KnowledgeOperationAuthorizer.authorize` 中支持 `authorize_url in ("", "local")` 分支，当处于本地自治模式时，直接利用受信的 `identity` 与共享密钥生成签名包并自验，不再发起任何外部网络 HTTP 请求。
- **代码位置：** `research/rag-anything-use/src/knowledge/operation_auth.py` → `KnowledgeOperationAuthorizer.authorize()`
- **预期结果：** 当 `authorize_url="local"` 时，`authorize()` 立即在本地成功自验返回合法的 envelope，无需外部网络连接。
- **验证项：** 编写单元测试校验 `authorize()` 在 `authorize_url="local"` 下的直接闭环自验通过。
- **状态：** `[x]` 已完成

### Task 1.2: 同步代码并更新远端服务器配置
- **改动内容：** 将加固后的 `operation_auth.py` 同步到远端服务器 `sshmy2`；在远端 `.env` 中设置 `KNOWLEDGE_AUTHORIZE_URL='local'`；重启 `rag-service` 服务。
- **代码位置：** 远端 `/home/<user>/PyCharmMiscProject/rag-anything-use/src/knowledge/operation_auth.py` & `.env`
- **预期结果：** 远端服务以本地自治模式正常运行，状态为 active。
- **验证项：** 检查 `systemctl status rag-service`，验证日志中无初始化异常。
- **状态：** `[x]` 已完成

## Phase 2: 停用并永久移除 SSH 反向隧道

### Task 2.1: 终止本地后台 SSH 反向隧道
- **改动内容：** 使用 `manage_task` 彻底终止本地常驻后台任务 `task-2857`（`ssh -R 21420...`），验证远端 `21420` 端口彻底关闭不可达。
- **预期结果：** 远端 `curl http://127.0.0.1:21420` 彻底 Connection Refused，证明完全没有隧道存活。
- **验证项：** 在远端执行端口检查，确认无任何反向监听或隧道进程。
- **状态：** `[x]` 已完成

## Phase 3: 全链路闭环验证

### Task 3.1: 零隧道状态下全链路入库测试
- **改动内容：** 在无隧道环境下，重新运行文档上传入库脚本，触发后台 Worker 处理。
- **预期结果：** 异步 Worker 在零网络隧道环境下顺利完成 `start` 授权，成功走完解析、抽图与向量存储，状态达到 `ready`。
- **验证项：** 查询远端 sqlite3 确认 job 状态为 `ready`，`builder.log` 中无任何授权失败异常。
- **状态：** `[x]` 已完成

### Task 3.2: 真实浏览器 Playwright 端到端验收
- **改动内容：** 运行 `scratch/e2e_test_runner.py` 自动化端到端测试，验证在零隧道真实环境下知识库检索完全通畅。
- **预期结果：** Playwright 自动化测试绿色通过（Exit Code 0），全套截图正常生成。
- **验证项：** 断言 `SUCCESS: Knowledge base retrieval & document status verified in UI!`，确认无报错。
- **状态：** `[x]` 已完成

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全链路闭环验证通过
