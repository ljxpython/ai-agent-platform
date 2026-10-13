# 本地部署与交接手册

## 归属与当前地址

此环境仅绑定平台Worktree `6394`，ID `wt_39abb85e02a2`。完整源码目录见README。知识工程使用自己的 `.venv`，平台两服务也各自独立；原生PostgreSQL、专属Redis、Runtime local，无Docker。知识资料/模型/日志都在平台本环境 `.local-stack/knowledge/`。

| 服务 | 当前地址 |
| --- | --- |
| Web | `http://127.0.0.1:25457` |
| Platform API | `http://127.0.0.1:24748` |
| Runtime API | `http://127.0.0.1:23512` |
| Redis | 本环境24741，秘密不公开 |
| 知识MCP | `http://127.0.0.1:63311/mcp` |
| Ollama Embedding | `http://127.0.0.1:65417`，nomic-embed-text768 |

Platform/Runtime数据库分别为 `wt_39abb85e02a2_platform` / `wt_39abb85e02a2_runtime`，已有本机PG保持运行。不要把端口/私有配置复制给另一个worktree。

## 配置与登记

- `.local-stack/platform.env`：`PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON`，可信tenant/project→resource；默认空，无知识token。
- `.local-stack/runtime.env`：`RUNTIME_MCP_CONNECTIONS_JSON`，resource→scope、URL、Bearer、allowed_tools；两主图实际装配。
- `.local-stack/knowledge/knowledge.env`：`KNOWLEDGE_MCP_TOKEN_SCOPES_JSON`、`KNOWLEDGE_ROOT_DIR`、模型/Embedding；权限600，不打印/提交。
- `.local-stack/knowledge/mcp-process.json` / `ollama-process.json`：源码归属、环境、配置路径、预备端口；不含Key。新启动PID以 `.local-stack/pids/knowledge-{mcp,embedding}.pid` 为准。
- `.local-stack/environment.json` 与Git公共目录的local-stacks登记含知识source/两端口。`knowledge-register`检查loopback、配置/目录、端口冲突和监听进程归属；`start/status/stop`包含已登记知识资源。
- `.local-stack/knowledge/projects.json`：本任务alpha/beta项目ID和知识URL；测试身份秘密在 `test-actors.json`，不交前端、不截图。

知识模型使用miaomiaoai `deepseek-v4.1-flash`。抽取/关键词任务需要正文，当前供应商配置 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`、本地 `LLM_MAX_TOKENS=8192`；首次版本样本未关闭thinking时返回空正文，失败索引不能发布，补参数后真实入库成功。此参数仅针对支持该设置的供应商，其他供应商用 `{}`。外部关键词LLM/Embedding费用不自动记入平台Usage。

本地实际映射：alpha→knowledge_alpha→alpha_v1；beta→knowledge_beta→beta_v1。tenant为既有 `__default`。三个进程scope必须同值，不使用用户输入scope作授权。

## 启停与检查

从平台Worktree根执行，命令不输出秘密：

```bash
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" knowledge-register
bash "scripts/local-stack.sh" knowledge-start
bash "scripts/local-stack.sh" knowledge-restart
bash "scripts/local-stack.sh" restart-one runtime-api
bash "scripts/local-stack.sh" restart-one runtime-worker
bash "scripts/local-stack.sh" restart-one platform-api
```

`knowledge-register`用于准备好本环境私有配置/source和预备进程记录后登记，重复执行不改变平台端口或库；不是通用远端部署命令。首次准备不同worktree时先按Worktree规范init/deps，再由维护者分配空闲知识端口、独立corpus/models和三份私有scope配置。禁止拷贝此环境秘密或复用安装目录。

```bash
bash "scripts/local-stack.sh" knowledge-stop
bash "scripts/local-stack.sh" stop
```

停止保留资料、checkpoint、Redis与数据库。仅管理登记端口及匹配源码目录/命令的所属进程；无归属不能强杀。knowledge只接受本机loopback。`destroy`有知识监听时拒绝删除，数据销毁仍需用户明确确认；本次没有执行destroy。

MCP监听并完成初始化后，用有scope的官方Client或平台新会话做discovery/query确认；普通端口连通不等于检索成功。私有日志 `.local-stack/knowledge/mcp.log` / `ollama.log`；禁止整份复制上游配置/日志到公开报告。

配置改动需重启对应进程。目录刷新沿现有 `POST /api/runtime/graphs/refresh` 和 `POST /api/runtime/tools/refresh`，使用平台会话身份和项目头。新Thread才获得知识绑定；旧Thread不自动迁移。只删API映射不能撤掉旧binding。

## 离线入库与发布

进入K根；`--project-id`在CLI中是namespace，网络工具没有该参数。使用本环境私有env的绝对路径，以下变量由维护者指向它：

```bash
uv sync --frozen --group dev
uv run --no-sync --frozen --env-file "$knowledge_env_file" python "main.py" ingest --project-id project_v2 --file "资料/规范.md"
uv run --no-sync --frozen --env-file "$knowledge_env_file" python "main.py" list-docs --project-id project_v2
uv run --no-sync --frozen --env-file "$knowledge_env_file" python "main.py" publish --project-id project_v2
```

CLI会输出管理员诊断，可能包含内部文件信息，勿直接交浏览器。资料目前只实测UTF-8 md/txt；PDF/Office先在兼容环境 `uv sync --frozen --extra documents --group dev`。Intel本机该步骤缺Torch wheel，不能声称PDF已验。

单文件顺序入库到未发布namespace；检查所有overall/index状态ready且质量通过，publish写模型/Embedding签名。失败索引保留failed且不能发布；服务读锁期间同namespace写入被拒，发布后冻结。不要手改manifest或一边查询一边CLI写。

## 版本更新和回退

1. 新namespace完整导入批准的资料，不修改旧已发布目录。
2. 使用新随机凭据/scope（必要时新resource），验证新版本事实/引用和旧版本仍可查。
3. 维护窗口先deny项目知识工具并处理在途Run；更新对应三份配置、重启，刷新目录。
4. 新resource/范围从新Thread接入；旧binding不静默变成别的scope。历史保留检索时快照。
5. 发布失败恢复旧私有配置/凭据和已发布namespace，重启；核验普通Chat及旧来源。保留两个目录，不删除数据、不downgrade数据库。

本轮真实新版本namespace、独立token、旧token401、旧scope保留和MCP/Embedding重启均通过；安全汇总见deployment-evidence.json。新版本和失败namespace均保留在私有corpus，未映射给正式alpha/beta。

正式停用：先用现有tool restriction deny `mcp_query_project_knowledge`，再撤知识token/移除映射并重启；历史读取仍走当前Thread ACL。撤成员/grant后新Run/state403已验，provider0；在途请求可能已提交远端，Stop保证不接受迟到ToolMessage，不能保证抹去已经计费的调用。

## 复验与剩余Block

平台Runtime目录执行：

```bash
KNOWLEDGE_PLATFORM_LIVE=1 uv run --no-sync --frozen pytest "tests/e2e/test_knowledge_platform.py" -q -s
```

测试使用环境登记而非固定主端口；创建本任务新Thread/测试项目、临时限制/撤权在finally恢复、重启本环境Worker；不在别的环境执行。依赖本任务已有无敏感语料和测试身份。先确认知识/平台服务及模型额度可用。

B01兼容PDF解析环境和B02代表性语料未提供，补齐后继续V1B。跨机HTTPS/生产发布、真实业务负载、多实例写入/扩容不在本次本地验收范围。
