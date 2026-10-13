# 验证计划与记录

状态：本阶段非前端范围 `done`，T01–T06及Final已完成。RAG同事与临时union证据仅作参考；本轮结果独立记录，前端浏览器与生产部署后续接续。

## 验证计划

- 单元/集成：root可信namespace；授权/迁移；v1/v2与F04；图片网关、原名称收据/Fork；FileRef/ImageRef schema、安全投影、失ACK恢复。
- 真实链：普通成员通过平台Worker文档/图片→root审批→异步回执→RAG ready→另一成员查询；新旧知识同时可查。
- 安全/生命周期：跨项目、无收据/篡改/生成图/Plan/子图拒绝、撤权、Stop、重启/Fork、重复hash零新增模型用量。
- 回退：query默认v1/v2固定配置回退与历史v2保留、关闭submit保留读取；保留 Token/后台迁移。
- 性能：异步submit有界，不等待整份解析；大文件与排队限定测试规模，生产吞吐另评估。
- Final：全部相关API/Runtime测试、lint/type（适用），真实Worker与RAG；前端业务与浏览器展示由同事继续，不计入本轮完成范围。

## Phase 验证记录

### T01 2026-10-13
- Runtime root空/可信tools namespace通过，伪task、子图、namespace不一致、read委托拒绝；auth与后台回执回归通过。API authorization与单迁移head/既有revision通过。
- 执行：Runtime相关146项；API `test_knowledge_authorization.py/test_knowledge_mcp_bindings.py/test_runtime_gateway_images.py` 19项+3subtests通过。
- 首轮具名构造误用context_claim字段失败；修正为context_hash后通过。API测试独立加载循环导入，局部导入修正后通过。

### T02 2026-10-13
- v1/v2、非法页码/布尔/逆序/额外路径/未知版本、F04同值与固定版本/模型隐藏覆盖测试通过，含无hit/缺locator及provider版本不符。
- 证据：`.local-stack/evidence/knowledge-platform-documents/phase-runtime.xml`，146项通过，16.68秒。

### T03 2026-10-13
- API图片名称query转发与非法名拒绝、Runtime原MIME与私有收据、五字段不变、首次名称固定、Fork、收据符号链接通过；图/Thread隔离旧测试通过。
- 证据：同T01最小相关集；Ruff所改API文件通过，Runtime导入排序已修正。

### T04 2026-10-13
- PNG/JPEG原bytes经私有收据转换入库参数；缺收据/伪名称/字节篡改/跨Thread/生成图/WebP/收据symlink未发生网络传输。schema及失ACK、取消/撤权回归通过。
- 证据：同Runtime146项；后续MIME schema补收紧在Final回归覆盖。

### T05 2026-10-13
- 真实环境：6394原生PG/专属Redis、local Runtime API/Worker，Ubuntu独立1024 corpus，miaomiaoai deepseek-v4.1-flash；RAG main c30e2149。本轮不改RAG仓库，七类MIME能力实际读取。
- 六格式真实HTTP原件→executor Agent→review审批→submit→ready→editor查询通过；DearFlow上传PNG、Showcase上传MD/PDF/DOCX/PPTX/JPEG。PDF可信page，图片unknown；新旧资料同时检索，正文/artifact同值及预算通过。formats-live 1 passed，185.86秒（前期已ready的四文档复用实物，不重复花解析成本）；原始submit与ready证据均保留。
- 同PNG跨Thread/Run和Fork复用原job，usage/jobs均不变；Fork在首轮submit前checkpoint验证复制收据，API/Worker重启后审批仍可恢复。生命周期1 passed，116.38秒；跨项目job404、route/header不一致400/project_scope_mismatch、撤权GET/run.start403且新增入库事件0、Plan无提交。
- 20MiB双页边界PDF通过，Agent提交及回复25.677秒，初始queued；聊天Stop后后台ready。该文件验证字节上限，不代表20MiB复杂业务PDF的解析耗时保证。large-file测试在lifecycle-live内1 passed；原受理/Stop/ready见evidence/large-file-stop.json。
- 受控暂停隔离RAG所属builder使alpha真实parsing；另一Run复用samehash，同usage284/jobs9无增；beta同hash独立job排队，alpha旧资料检索和旧冻结文件仍正常。关闭Runtime/API新upload后释放builder，alpha/beta均ready；队列/drain 1 passed，173.14秒。实现修复写开关仅禁新upload，start/activate保留当前授权。
- v1配置回退＋关闭新写＋四GET＋v2历史完整保留1 passed，132.82秒；模型无版本参数，submit隐藏。冻结generation回退/恢复1 passed，134.92秒，旧版本只一份文档，新增job ready/false；恢复后八份资料，旧/新冻结文件与ingestion usage不变。RAG真实进程重启后同KB/端口query和ready回执保持。pending审批Stop 1 passed，27.28秒，no_active_run/confirmed_at/无迟到submit或新入库。
- RAG119 passed，29.03秒，本轮Ubuntu复跑，包括实际supervisor SIGKILL与子进程watchdog、候选失败/撤权/CAS/损坏拒绝与reader lease，不冒充生产故障保证。
- 修复：跨机约0.2秒时差造成iat未来，15次有效签名对照3次403、PNG start失败且0usage；增加固定5秒未来iat容差，过期仍拒绝。测试输入诊断保留（access_policy应在Thread、官方content是数组、模型看到成功历史不重复submit、重启测试须顺序、pending无运行Stop为no_active_run）；详见implementation/02与证据。

### T06 2026-10-13
- 前端逐文件F01–F06、HTTP/ToolMessage真实fixture、v1/v2/queued/ready/reused/failed/unknown、五六字段引用、权限/项目切换与前端真实浏览器断言交接完成；前端业务代码未改。
- 活Runtime知识标准、API配置与图片网关契约更新；写开关只禁新upload、iat容差、默认v1及上线顺序明确。
- Phase扩展：API107 passed+176subtests，87.86秒；Runtime355 passed/26 skipped，140.59秒。后续授权11 passed，11.82秒；真实PG后台/迁移21 passed/5 Docker skipped，47.42秒；API SQLite/PG迁移2 passed，5.74秒，既有行/acceptance回执及Token/后台revision保留。以上先记Phase，最终统一回归另记。
- 迁移测试原锁死head/origin_ref断言失败已修；Alembic URL百分号转义、merge降级节点处理后SQLite/PG通过，不降级运行库。

## Final 验证记录

### 2026-10-13 · `done`

T01–T06全部实施/Phase完成后独立执行。公开[最终摘要](evidence/final-results.json)、[默认回退smoke](evidence/default-smoke.json)及[资源清理](evidence/cleanup.json)保留在本专项；JUnit原件仅在所属忽略目录 `.local-stack/evidence/knowledge-platform-documents/`，不导出私有配置、Token/HMAC或模型Key。

| 检查 | 最终结果 | 证据与边界 |
|---|---|---|
| Platform API相关回归 | 223 passed、182 subtests passed，180.49秒，0 skip | `final-api-retry.xml`；知识权限/四GET/授权、文件/图片/SDK网关、delegation、Token/Usage、background、acceptance/completion/backfill和迁移。completion全组用当前worktree随机PG schema，8并发CAS已执行；migration SQLite/PG均通过，不降级运行库。 |
| Runtime相关回归 | 379 passed、5 skipped、17 warnings，229.02秒 | `final-runtime.xml`；knowledge/composition/上传信任链、auth/resource-binding、图片/Office/Workspace/Fork、completion、Token/Usage及PG后台/迁移；5项仅`BACKGROUND_DOCKER_TEST`受管daemon专项，按本阶段local要求跳过，不作通过。warnings为既有PyMuPDF/Pydantic，不外推全仓无warning。 |
| RAG相关回归 | 119 passed，29.03秒 | `rag-regression.xml`；Ubuntu本轮重跑，含candidate/CAS/撤权、受控SIGKILL/stdin-watchdog、腐坏拒绝、旧reader lease；本轮未改RAG源码。 |
| 本地栈脚本 | 5 passed，0.55秒 | `final-local-stack.xml`；登记、回调和隔离配置。 |
| 静态检查 | 通过 | 50个后端变更Python文件Ruff check/format、两个app compileall、local-stack shell syntax和`git diff --check`。使用当前worktree安装的静态工具，没有新增/升级依赖。 |
| 文档与公开fixture | 通过 | 20份专项/承接Markdown的98个本地链接有效；37份JSON可解析，API7份与Runtime9份fixture按实际DTO校验，3份ToolMessage text/artifact同值；私有配置值扫描无泄露，6个Task与6条Phase对应。 |
| 真实平台Worker/模型/RAG链 | 七类验收通过 | 六格式/两图/成员共享、生命周期与去重、20MiB/Stop、v1-v2/上传关闭、处理中去重/两项目排队/旧读/在途排空、冻结generation回退/恢复、pending审批Stop。原始报告/来源与限定规模见T05，Final不将Phase重复累加成独立测试数量。 |
| 默认配置与清理 | 通过 | 恢复前的upload=true/v2只用于验收；Runtime/API恢复原备份后上传关闭、来源1、catalog无submit，旧v1 query真实返回2来源、text/artifact同值，28.467秒。随后Ubuntu所属RAG/SSH及本worktree7服务全部停止，登记端口释放，PG/Workspace/原件/corpus/冻结版本保留。 |

首轮Final API：23 failed/199 passed/1 skipped；acceptance旧测试桩缺planning read返回和默认run-create operation，已修测试桩，32项独立复验通过后重跑上述全组。completion原限定旧专项数据库而skip，增加显式本机worktree测试URL，保留旧数据库安全护栏，仅操作随机测试schema后回收，最终0 skip。没有为测试放宽生产权限或运行受理逻辑。

默认配置smoke首轮：`knowledge_retrieval_failed`。旧768维Ollama配置缺`EMBEDDING_PROVIDER`，源码`.env`新openai缺省项被加载，向Ollama调用`/embeddings`返回404。仅在本隔离`knowledge.env`显式固定`ollama`，原配置600权限备份保留，未改模型/维度或重建旧索引；重启后旧query通过。恢复旧接口配置不等于部署在线HTTP管理能力：capability仍为`knowledge_not_configured/read_enabled=false`，legacy MCP query有独立连接且可用；此前“仅关闭上传保留四GET”在完整online配置下已经真实通过。

| 四态判定对象 | 状态 | 说明 |
|---|---|---|
| 本专项非前端实现/单元集成/真实链/安全回退/交接 | `done` | T01–T06及上述Final完成，无当前范围内可推进未完成项。 |
| 本轮前端业务与无mock浏览器 | `deferred` | 用户指定由前端同事继续，逐文件F01–F06/接口/真实fixture与验收已交。 |
| 正式合入/现役发布、音视频、生产容量 | `deferred` | 本阶段未授权发布，不用两项目/20MiB字节边界承诺复杂文件耗时或工业吞吐。 |
| 原知识专项代表性业务题集质量 | `blocked`（原专项） | 仍未提供10–20份业务资料/标注问题，本次Orion小语料不代替业务质量；PDF/Office环境阻塞已由Ubuntu真实验收解除。 |

跨库授权最长30秒租约边界仍存在；固定5秒未来iat容差不延长过期有效期。没有提交/push/合并/生产部署。业务质量和前端接续不改写为已通过，旧失败及模型波动继续保留。
