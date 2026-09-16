# P4 K08—K11 集中迁移与验证

日期：2026-09-15。用户批准：四项先集中实现，统一运行相关验证；失败仅定向复验。前端只交接，页面验收后置。本文件是本批次实现与证据入口。

## 需求与进度

| 需求 | 代码实现 | 后端验证 | 前端交接 | 页面验收 |
| --- | --- | --- | --- | --- |
| K08 CSV/XLSX/XLS 多文件、schema、只读 SQL、统计、CSV/JSON/MD 导出 | 已实现 | done：Docker＋真实两表SQL与发布下载通过 | done：见frontend-handoff.md | deferred |
| K09 26 类图表与地图、审批外发数据、真实图片落盘与下载 | 已实现 | partial：25/26真实图型通过；代表性柱图＋地图平台链路done，双轴远端blocked | done：见frontend-handoff.md | deferred |
| K10 独立 HTML/CSS/JS、ZIP 交付 | 已实现 | done：真实生成＋既有产物只读下载复核通过 | done：见frontend-handoff.md | deferred：隔离预览不在本轮实现 |
| K11 规范版本获取、静态源码评审、file:line 报告 | 已实现 | done：组合＋真实平台链路通过 | done：见frontend-handoff.md | deferred：动态行为不冒充静态验证结果 |

## 代码导航与改动原因

以下路径均相对仓库根目录。

| 文件／函数 | 改动及原因 |
| --- | --- |
| apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/{data-analysis,chart-visualization,frontend-design,web-design-guidelines}/ | 复制完整上游资源，provenance.json 保存原始资源哈希、commit、适配文件清单；frontend-design/LICENSE.txt 原样保留 |
| apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/data-analysis/scripts/analyze.py：load_files、_load_excel、_load_csv、action_query、_export_results | 保留上游 schema／统计／格式化逻辑；去掉运行时 pip、spatial 扩展、全局缓存和任意 SQL。Excel 使用 openpyxl／xlrd；文件与 sheet 映射不互相覆盖；导入后关闭外部 IO 并锁定 DuckDB 配置，只允许单条 SELECT。参数导入、资源限制、导出路径校验与 CSV 公式注入保护 |
| apps/runtime-service/deploy/Dockerfile.agent-workspace | 构建时固定 duckdb 1.4.4、openpyxl 3.1.5、xlrd 2.0.2、defusedxml 0.7.1；运行时离线，无临时 pip。镜像 runtime-agent-workspace:p4 |
| apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py：aexecute | 默认使用 p4 镜像；复用原有 Docker 内存／超时／断网／只读挂载／取消机制 |
| apps/runtime-service/src/runtime_service/workspace/file_refs.py、documents.py | 补 XLS/XLSX、HTML/CSS/JS 上传格式；XLS 校验容器标识，XLSX 校验压缩包与必需文件并拒绝宏；完整 Excel 解析在受限执行进程内进行 |
| apps/runtime-service/src/runtime_service/workspace/artifact_refs.py：read、publish | 复用不可变哈希产物，增加 CSV/JSON/HTML/CSS/JS/ZIP；压缩包安全校验，不落解包目录 |
| apps/runtime-service/src/runtime_service/tools/documents.py：parse_document | 可静态读取已发布产物；Excel 返回沙箱分析指引，避免在 HTTP／工具宿主进程直接解析工作簿 |
| apps/runtime-service/src/runtime_service/tools/chart.py、chart-schemas.json | 从 Showcase 公共化原有 AntV MCP 工具及参数快照；默认保持 Showcase 旧选择，Dear 开启 spreadsheet；参数／大小／尺寸校验，真实图片下载后保存到线程空间，远端 URL 不等于交付成功 |
| apps/runtime-service/src/runtime_service/services/demo/showcase_demo/chart.py | 旧导入路径保留兼容再导出；Dear 不依赖 Showcase 的业务目录 |
| apps/runtime-service/src/runtime_service/http/images.py：_authorize_image_request | 去掉只允许 Showcase 与固定根路径的耦合；根据服务端验证的 graph_id 解析线程工作区，保持 project/thread/operation 校验 |
| apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/web_guidelines.py：fetch_web_guidelines | 固定公开来源获取规范；保存 SHA256、抓取时间、ETag，失败抛出明确错误，不静默伪造最新规范 |
| apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/research_http.py：get_public | 只额外放行一个规范 URL，沿用响应大小／超时／禁止重定向／无凭据约束 |
| apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py、capabilities.py、prompts.py、tools/artifacts.py | 注册 26 类工具与规范工具；图表权限 runtime.tool.write 且必须 HITL 审批，拒绝后不得外发；增加图片能力与格式声明，更新产物指引 |
| apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py；tests/test_runtime_gateway_sdk_adapters.py | 内部HTTP客户端统一trust_env=False，避免服务间文件请求经系统代理；13项适配契约通过 |
| apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py | 上传白名单同步新格式，不修改 GraphHarbor |
| apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py、apps/runtime-service/src/runtime_service/http/documents.py | 文件强制附件下载，nosniff 与 sandbox CSP；防止生成 HTML 在平台域执行 |
| apps/runtime-service/pyproject.toml、uv.lock | 公共图表 schema 纳入 wheel；显式声明现有 jsonschema 依赖 |

## 已知边界

- K08 无缓存，每次导入独立内存数据库；这直接消除跨任务缓存泄漏。单文件20MiB、最多10文件、Excel每sheet10万单元格／256列、SQL结果最多1万行，超出明确失败；Docker既有256MiB／60秒上限不放大。
- XLSX公式作为文本、不计算；XLS读取已保存值，不能声称重新计算了公式。CSV导出对公式前缀字符串加单引号。
- K09 上游26类全部保留。MCP另有waterfall，不自动扩大本次范围。上游脚本原样保留作参考，但实际执行使用公共MCP工具；地图中国POI名称契约不等于任意经纬度绘图。
- K10删除强制DeerFlow品牌业务提示，不删除许可证；只交付源码与下载，不新增平台前端、发布或浏览器工具。
- K11没有隐式“最新版”回退；获取失败必须说明。若使用会话中已保存规范，必须带旧SHA256与时间并标记非当前版本。

## 验证计划及证据

- [x] 一次集中（结果含1个旧MCP探针失败，见下文，不代表全绿）：Dear相关回归、文件/图片共享链路、Platform文件契约、定向lint。
- [x] 真实Docker：CSV／XLSX／XLS、同名sheet、联表精确结果、导出回读、公式不执行、恶意SQL拒绝。
- [x] 26类参数与落盘契约；真实AntV矩阵逐项保留返回结果和哈希，累计25／26通过，双轴远端失败未标done。
- [x] K08—K11代表性真实模型经Platform授权、工具审批、执行与文件下载；K10用已有成功运行只读收口。K09全图型仍保留双轴blocked，不等于26项全部完成。
- [x] 干净wheel资源及文档链接检查。

入口：apps/runtime-service/tests/services/dearflow_agent/skills/test_data_web_batch.py；sandbox_data_check.py；fixtures/legacy.xls；platform_batch.py；apps/runtime-service/tests/e2e/test_dearflow_skills.py。

## 集中验证发现与修复

- 首轮测试收集发现图表夹具括号错误，已修正；未将收集失败记为通过。
- 文件网关由inline改attachment后，旧契约断言同步更新；增加HTML主动脚本响应头与Excel白名单验证。6项通过，9.304秒。
- K08真实第二文件上传超时后客户端断开，Platform抛出ClientDisconnect；栈确认内部HTTP请求绕到系统HTTP代理。修复apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py所有6个HTTP客户端构造，trust_env=False，服务间直接使用配置的Runtime地址；不增加重试、不吞掉断开。相关SDK适配契约补充代理隔离断言，待定向结果。
- 批次组合7 passed、1 skipped（仅外部图表矩阵另跑）、92.55秒，包含真实Docker。镜像ID sha256:4cbad672b188b607c7f3789401c26513cd80a5e8ee5a77b6accb3c42d9c2fba8。
- 共享回归81 passed、19 skipped、1 failed，503.84秒；失败为旧MCP重启探针45秒超时，单项复测54.66秒仍在第三次初始化失败，未修改断言或扩大超时掩盖。

- 首轮四项真实模型：4 failed／7 deselected，1055.33秒。K08第二文件上传受系统代理影响；K09地图imageUrl结构未兼容；K10轮询45秒超时（运行实际停在execute审批，未丢失状态）；K11合法规范中的HTML示例被错误过滤。这些不是成功记录，修正后仅复测本批次。
- K09真实矩阵首轮21／26成功，1395.29秒：district_map／pin_map／path_map需识别structuredContent.imageUrl，已修复；mind_map失败待定向复验；dual_axes远端HTTP200但success=false、AE0310000201、Cannot read properties of undefined (reading 'map')，需区分远端渲染失败，不伪造双轴结果。
- K11改按响应Content-Type拒绝HTML错误页，保留Markdown中的合法HTML代码示例；ToolException作为错误ToolMessage返回，允许Agent说明限制，避免工具失败导致整图无说明退出。
- Platform SDK适配契约13项通过，2.409秒，包含内部客户端trust_env=False断言。

## 26类图表参数与产物对照（首轮）

每行夹具完整参数见tests/services/dearflow_agent/skills/test_data_web_batch.py:chart_cases；下表哈希来自真实下载文件，不是Mock。MCP版本@antv/mcp-server-chart@0.9.10。失败项由后续定向记录覆盖，不重跑已通过项。

| 图型／上游references同名文件 | 参数形状 | 实际结果／SHA256 |
| --- | --- | --- |
| generate_area_chart | data | a54f78d46af0d24166933356d581d3cadbc099b14f591d32acd7c6c902517fa2 |
| generate_bar_chart | data | 3ea671e1219f6e2ac9938a6ab01a8077c9bc375e4284f2671acaa43572d64d20 |
| generate_boxplot_chart | data | dd63ec1389b04b4ca2d6c6465b5e72587227a20c2d83a4f96af33b596fd81309 |
| generate_column_chart | data | b254f8bad1d8063cde23227e1e26b625db3805893cc7e2971ee34a3468b4a84c |
| generate_district_map | title, data | 失败，待定向复验 |
| generate_dual_axes_chart | categories, series | 失败，待定向复验 |
| generate_fishbone_diagram | data | 518765e130e1a9ce302e20a1543f82bd71c274e9bac4acb3533ebc644d4c2646 |
| generate_flow_diagram | data | 15fafe26650f237c9aa96cb7121023b797348a510f534744d154685fae54a238 |
| generate_funnel_chart | data | bf307424bdd0adf1ce074387221cb37eef8800f1dee7cd7feeb9266c7ca0117f |
| generate_histogram_chart | data | 0e5e0424c97c95d23e195c273e9a0815d8ebf17e60b2fbe2be381e0a7f6882fd |
| generate_line_chart | data | c1bbcdd472d85089cc95e8d5b089737cfa05b5da9dffcb8e1c71933bc43aa813 |
| generate_liquid_chart | percent | d83efb438e3a0f5e8ae57ef757fbb7a148d5ac68270b65d1ac144aceabde3e16 |
| generate_mind_map | data | 失败，待定向复验 |
| generate_network_graph | data | d0b442be2541e0445a128fd39b9d63efa07d8dac00de6c9ddda440464212d6d7 |
| generate_organization_chart | data | 4c0545fed8da653b7014a96ad7a47bdc3848faa5bd94579495d1da0adb43e1d0 |
| generate_path_map | title, data | 失败，待定向复验 |
| generate_pie_chart | data | d76ec11b4857010a0a6f1770803e77be0efe54696e281119c328316ae41401d8 |
| generate_pin_map | title, data | 失败，待定向复验 |
| generate_radar_chart | data | be86eb1e9eb3b045a0c0254711fcc71aad5464e8a448c448811e60a3ab1a1341 |
| generate_sankey_chart | data | e2253a1f21c581623b9a7558eea363479e9bd8021f9118de539f49c8f80066ab |
| generate_scatter_chart | data | 741065fce995a0ef93ba8592ace03404e2c696f2b49be39f17cd58dce1740e88 |
| generate_spreadsheet | data | 7024f4f153ce9d941c57c691a9d83392bb927eed92c72c083b2f2850c53fef6b |
| generate_treemap_chart | data | 2cb4cde09d9478b72235880480be1ec81b8c481336798c571bd4108ea1c00383 |
| generate_venn_chart | data | 8299d4791828bc41369598666ad283508d47526cf724da360adccaa75dc986fa |
| generate_violin_chart | data | 9b9ba254d29a7d8f3afff752259b3d77259d320c15d314b1e37563b895671eb8 |
| generate_word_cloud_chart | data | bad228c98a8903c38531d8da8fd995d38af83658593c63f97f335b4fb2964b56 |

### 图表失败项定向复验

5项定向复验323.03秒，4项通过、1项远端失败；累计25／26真实图片通过，不重复跑首轮21个成功项。

- generate_district_map: success；fafc364637cdebcc26441d2cef54de8aaa4838bddbc743a93d44eae8c907c889
- generate_mind_map: success；9a69ebcc55056b8a9d8fcaf2b1ff76d347b18975cd62b34612bee2e3213d10aa
- generate_pin_map: success；e837ec19d828b185b2559853affaaa4fa16aee5ddbfa94ff0ecd4816a9626442
- generate_path_map: success；709e4ad34cf50ea70d910558d6ef4903998865b539537ac25d72e2b0aaac9ec1
- generate_dual_axes_chart: error；远端AE0310000201，双轴渲染错误

最终数据脚本／规范／26类结果适配定向回归3 passed、5 deselected，164.82秒；包含CSV规范化列名碰撞、512MiB分配超出256MiB容器上限终止。
最终wheel资源验证40个文件逐字节相同，公共chart-schemas.json在包内，无pyc；SHA256=173ad8189881b866d29efd725ae8dbd63214a9972b05dbed071ff2f5e3eea399。构建目录/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/dear-k08-k11-final-_ljy6b7d/dist/。33篇文档相对链接无损坏。

K08复验已完成两文件上传、schema、联表总额30、CSV导出回读；Pro模型在后续报告输出阶段触发既有600秒run_timeout，尚未形成完整发布链路。后续小型固定夹具改用已支持Flash模式验证，保留相同工具／审批／SQL／下载断言，不扩大全局运行预算。K09/K10/K11亦采用Flash作有限输入验收；Pro模式超时事实单列，不以Flash通过声称所有模式稳定。

第二轮Pro真实模型：4 failed／7 deselected，1272.11秒。K08 run=4bc572c0-7df9-47d6-99f7-fb9e35a206ef与K09 run=99d7a753-0bf8-4a2d-94ce-43fcbbe19637触发600秒run_timeout；K10状态轮询45秒ReadTimeout；K11在catalog refresh前置请求45秒ReadTimeout，尚未执行新规范工具。不能将这些统一归因于业务实现或宣称已验证完成。

## 本地复现与排查顺序

1. 构建执行镜像：仓库根目录运行docker build -t runtime-agent-workspace:p4 -f apps/runtime-service/deploy/Dockerfile.agent-workspace apps/runtime-service/deploy。运行阶段不联网安装。
2. Runtime目录运行DEAR_DATA_DOCKER=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/skills/test_data_web_batch.py --tb=short。默认跳过真实AntV；Docker数据检查由开关启用。
3. 图表定向：设置DEAR_CHART_E2E=1；DEAR_CHART_TYPES可传逗号分隔的generate_*工具名，DEAR_CHART_EVIDENCE指定JSON输出路径。没有类型过滤时才跑26项，不要每次重跑全部。
4. 模型链路：DEAR_SKILL_E2E=1 .venv/bin/python -m pytest -q tests/e2e/test_dearflow_skills.py -k "K08 or K09 or K10 or K11" --tb=short -s。使用已有本地服务／测试账号／配置模型；四项串行，避免测试模型启停互相影响。
5. 先按thread/run定位模型或工具轨迹，再查本文对应函数；工具本体通过不代表报告已发布。平台／Runtime／Worker分别看本地栈日志，远端AE0310000201不要按本地SQL错误排查。

本轮无数据库迁移、无GraphHarbor业务修改、无平台前端代码、无git提交。生产发布前仍须固定镜像digest；回滚按本批次代码和wheel整体回退，保留线程上传／产物数据，旧版本不一定理解新增扩展名，不删除数据伪造回滚成功。

## Flash真实模型证据

首次Flash批次2 passed、2 failed、7 deselected，171.11秒：K09／K11通过；K08／K10受验证途中Docker daemon不可用影响（exit125），没有把模型手写CSV当SQL验证。已启动Docker准备仅补测两项。

### K09 后端链路通过

- thread：0e556a1e-2faa-45ee-a11d-6f52c2709695
- runs：858ce624-cf8d-44fb-805e-028bbaa87b3b, 03059736-9f13-4315-b0a9-5860857c27b8, 618c759f-3f5d-4d28-a549-0b2da7a96bf6, 7d76e76d-6c9f-4bc4-9af5-1b918a195c04
- model：9c276f29-a5cf-48a3-8cfb-86ab09f57537；revision：dear-k09-v1；可见tokens：41924；费用未知。
- 产物：text/markdown，1346字节，SHA256=902b82e856fd762ae083dada84a1615afabade7c970f7c39f67631285cacebd6
### K11 后端链路通过

- thread：ad57193f-2e52-4724-b2ce-bd77fcee19f9
- runs：ede97277-01b4-49de-9cfe-3746f82fdbdf, 43fde4c8-d568-4a27-b2c4-02e36b2e9272, 4d8feda3-a1b1-449e-85c7-80daac3bd96c
- model：9c276f29-a5cf-48a3-8cfb-86ab09f57537；revision：dear-k11-v1；可见tokens：28802；费用未知。
- 产物：text/markdown，3021字节，SHA256=086dc9e7a5bf9863e770178fb5247e2d2551c7f14868c64cc95c659db5c9414f

### K08 Docker恢复后链路通过

- thread：529fbc69-f04b-4ad4-a25b-f92217461af1
- runs：54de3f81-d600-4670-815d-3d3b1fe4b4f9, f3a64591-1505-4b65-a204-756e8a1034ab, d3ee4c7b-b41a-4d50-863f-54fbaa7fd633, 0956e46e-0773-4403-b3a2-8c5a193afe5b, 52d9dde1-a5e0-4ffe-b319-2aa40d57ed56
- model：9c276f29-a5cf-48a3-8cfb-86ab09f57537；revision：dear-k08-v1；可见tokens：58771；费用未知。
- 产物：text/csv，40字节，SHA256=c71005bdb759e294fff2eb3b7052ba1465e1a756102c58943c638039fac9d9fd
- 产物：text/markdown，1336字节，SHA256=162109b850fcc50915f92d3c0a74f5cac9e0365ff3716c74086b7fa5152036d4

### K10 下载适配修复与只读收口

原真实运行已success，但平台adapters/langgraph/runtime_client.py:read_file遗漏HTML/ZIP等MIME，返回runtime_invalid_file_response 502。补齐与输入／产物契约一致的白名单（含此前BibTeX），新增底层适配器MockTransport测试；14项通过，0.265秒。没有重跑模型：对原thread/run进行只读复核，验证HTML／ZIP／MD的下载、SHA256、attachment／nosniff／sandbox头、ZIP内相对资源、label、execute exit_code=0及v3生命周期重放。

测试夹具同时修正：允许ZIP中的site/index.html和相邻CSS/JS构成单一项目根目录；不能把合法的顶层项目目录误判成缺文件。仍要求唯一index.html、CSS/JS存在、资源引用有效、输入有label，不弱化交付断言。
- thread：976f78a0-5605-4418-aeee-ea9e1212a6ec；末run：41734fdb-cccb-4a2a-a3c1-4f66b3fe4b03；可见tokens：84825；费用未知；复核方法：readonly-recheck-existing-run。
- application/zip：5802字节，SHA256=d612d7bbf6a4e7d3a0eb66880e709f7c78bbc66c3bd3bd30e01c335683c24f13
- text/markdown：1815字节，SHA256=dc61fc6bec5d65ef4f8ca31b8f2b35f89ed7afd57be3b04aaf8da6f8361b475d
- text/html：6003字节，SHA256=0102efc69821a6c5e908e7e01a8a6d293c49c398282ab4ed5421efbd51827228

## 本批次最终结论

- done：K08表格分析、K10网页源码产物、K11静态规范评审的约定后端范围；四项前端交接全部done。
- partial：K09，26类代码／参数契约已迁入，25类真实图片通过，柱图＋地图真实模型／审批／线程下载通过。双轴远端AE0310000201为blocked，未删类型或用其他图替代。
- deferred：全部平台前端实现和浏览器页面验收，按用户明确决定后置；不声称HTML已隔离预览。
- 未通过的既有回归：MCP重启探针45秒总预算在第三次初始化超时，重复复测仍失败（最后65.04秒）；未改原测试、未改GraphHarbor或放宽断言。后续单独定位，当前不能声称全回归全绿。
- Pro模式真实样本超时、Docker途中不可用、首轮下载502与测试夹具误报全部在上文保留。Flash成功与只读复核不抹去失败历史，也不代表所有模型／模式／生产场景已稳定。
