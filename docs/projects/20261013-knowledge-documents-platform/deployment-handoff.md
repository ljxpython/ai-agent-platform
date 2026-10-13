# 联调恢复与正式接入

本轮只开发/验收本worktree隔离栈，没有正式合入主工作区或部署现役。RAG仓库源码未改，基线main `c30e2149`。本次临时Ubuntu服务、SSH通道在验收后停止，corpus/原件/冻结generation及调试证据保留；是否已停止以[清理证据](evidence/cleanup.json)为准。

2026-10-13已完成清理：Runtime/API恢复原私有备份，新上传关闭、来源1；所属Web/API/Runtime API/Worker/Redis/旧MCP/Ollama共7服务均停止。旧768库`knowledge.env`显式补`EMBEDDING_PROVIDER=ollama`，原文件备份在忽略证据目录。不能省略该项依赖源码`.env`默认值：当前源码新OpenAI配置会污染旧Ollama请求，曾向本地`/embeddings`调用404；固定后真实旧query2来源通过。新1024库独立，不原地改维度。

恢复旧配置时，四GET capability为`knowledge_not_configured`，legacy MCP query可用；恢复完整online连接后再验成员面板。仅关闭上传且保留online连接时四GET/query/job不受影响，已在真实configuration/queue-drain场景通过。

## 前端同事恢复真实环境

1. 在6394或自己的worktree读取 `docs/standards/worktree-development.md`，用 `scripts/local-stack.sh` 管理所属PG/Redis/API/Worker，模型使用miaomiaoai `deepseek-v4.1-flash`。禁止复用union依赖、主库或手工固定端口。
2. 由RAG负责人与平台协作人准备同版本的独立1024维多模态库、Docling模型缓存、授权回调和项目逻辑KB。继续使用原RAG服务与队列，不额外实现平台索引/解析服务。不允许把旧768文本库凭据直接改成1024。
3. API配置 `PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON` 与 `PLATFORM_API_KNOWLEDGE_CONNECTIONS_JSON`，Runtime配置 `RUNTIME_MCP_CONNECTIONS_JSON`；同resource及tenant/project固定scope，允许query/submit/job三工具。RAG token固定同scope/逻辑KB。全部私有token和专用HMAC secret只放所属私有配置，不复制进交接文档/fixture。
4. 上传名称与size/MIME网关已就绪。联调环境先显式启用 `RUNTIME_KNOWLEDGE_UPLOAD_ENABLED=1` 与 `PLATFORM_API_KNOWLEDGE_UPLOAD_ENABLED=true`，设置知识HMAC同key/secret，回调为本环境API。来源先默认1，前端v1/v2兼容完成后设置 `RUNTIME_KNOWLEDGE_SOURCES_VERSION=2`。三者配置变动后重启所属API、Runtime API/Worker，再用现有目录刷新入口更新catalog。平台新建Thread得到可信binding；旧Thread不自动迁移。
5. 真实前端验收按 [frontend-handoff.md](frontend-handoff.md)，不mock四GET/MCP。新建executor和reader两个成员账户，使用review策略，核对真实工具回执、job ready/searchable及另一成员查询。示例语料/真实协议已经留档，不必重复解析已ready资料来证明历史显示。

原本轮忽略目录 `.local-stack/evidence/knowledge-platform-documents/` 存在私有配置备份、资源归属和恢复runner；仅适用于本目录，不提交或复制给别的worktree。setup.py带拒绝覆盖备份保护，不要直接重跑覆盖。可读测试入口是 `apps/runtime-service/tests/e2e/test_knowledge_documents_platform.py`，只有显式 `KNOWLEDGE_DOCUMENTS_PLATFORM_LIVE=1` 执行真实模型；需先准备两项目、各Agent、resources与公开样本，不能在缺配置时回退主环境。

复跑API Final使用忽略目录的`final_api_runner.py`：只读本环境`PLATFORM_API_DATABASE_URL`，验证回环及wt_*_platform同名角色，迁移使用随机schema，completion使用显式`RUN_COMPLETION_TEST_DATABASE_URL`和`RUN_COMPLETION_PG_TEST=1`再各建随机schema，最终仅回收测试schema。它包含本阶段所有API相关集合，不能把DSN打印或将脚本配置复制到其他环境。Runtime回归的PG测试同样使用本环境`BACKGROUND_TEST_DSN`，不降级运行库。服务重启与pytest顺序执行，避免同目录进程归属扫描回收测试进程。

## 正式合入检查

保留主线Token/Usage、completion、background和精确acceptance回执，不能按RAG临时union补丁删除revision或替换主线auth。本worktree现有API head `20261011_0008` 和Runtime head `0004_merge_runtime_heads` 已含两分支；本次没有新增迁移。主工作区正式合入时重新检查heads与锁文件，已有同名merge只留正确主线版本；不要创建重复迁移来掩盖冲突。

上线顺序：后端安全DTO/图片信任链 → 前端动态能力/完整JSON/状态/locator → 目标环境真实浏览器验收 → 按部署开启submit/v2。默认新上传关闭/来源1；后端验收完成不自动开启现役。音视频、生产吞吐、真实业务题集质量另行评估，本次Orion小语料与两项目不能作为容量承诺。

## 回退与在途任务

仅回退新增提交：关闭Runtime/API上传开关并重启所属进程；新submit/upload拒绝，query/job/四GET保留，已受理start/activate沿当前权限继续。撤销成员/凭据或submit deny仍能阻止其排队启动/发布。

来源展示回退：服务请求改1并重启，旧v2历史继续读取显示，不能重写历史。

冻结版本回退：先关新提交并等待在途构建结束，再由RAG管理员用项目uploads=off及既有generation rollback操作回退经过验证的冻结generation。该RAG开关会暂停queued，不是平台“只停新提交”开关。后入库任务仍ready但当前searchable=false，前端据实显示。恢复最新完整generation并确认全部已发布资料可见后才能重新允许RAG上传，最后再按部署开启平台新submit。不要删除原件/资产/历史/冻结快照，不把两签名或不同Embedding维度混写。
