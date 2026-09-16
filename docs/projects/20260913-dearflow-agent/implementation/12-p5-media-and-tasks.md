# P5：媒体生成与持久任务批次

## 最新续验：区分供应商响应与本地交付失败（2026-09-15）

用户确认供应商能够成功，要求补验此前缺口。此前503是当时真实HTTP响应，不代表供应商永久不可用；未保留上游请求ID／完整错误体，不能倒推为某个确定的供应商根因。当前直连与公共工具的地址、模型、n=1、1024x1024一致，均无自动重试；当前终端／dotenv未配置HTTP代理，不据此断言历史网络路径。

### 已完成与问题定位

- **K13完整AI三页链路 done**：project `c18ac09e-1e51-41ef-833d-2da7ad460117`，thread `c84a2565-6545-402f-82cd-09588858ead1`，最终Run `1d9e6202-019f-4593-a4cb-4e43f39f7e17`。三张AI图均succeeded，真实沙箱组装、PPTX/MD发布、平台下载、哈希/MIME/3页校验及v3 lifecycle回放全部通过。PPTX 327787 bytes，SHA256 `47b17c8f1d8fd997d60ac347b932afc2a8a22143e9365751c70a7b0215f8bb95`；MD SHA256 `6406e795f9b78b2e0a0c7726d42318e1d11211e259e9640cf8d7fa12784349a4`。可见184400 tokens，费用unknown。
- K12生成成功，编辑结果unknown（不是503）：project `a94b2edb-0d49-4762-91ea-35532f6287ba`，thread `8b9c5366-f187-4109-bf13-90185f849a60`；生成task `dcf6144d-af0d-4515-b628-c81382bcda78` succeeded，编辑task `837747d3-759e-43e6-bc43-d6233e785d1a` 为 `submission_or_delivery_unknown`。该旧回执缺少细分原因，不能单凭它认定供应商失败。
- 独立编辑定位：当前供应商44.91秒返回1个图片URL，域名 `v4-gateway-v2.shagentai.com`，而本地白名单只有 `multimodal.vibelearning.top`。使用既有 `download_image` 并允许新域名后，**同一响应图片下载／格式校验通过**：1116705 bytes，SHA256 `fd71ed5c988ac63cce050df623637a79d5e97406f399d9f22f0284a156cd1ed0`。证实当前配置缺少结果域名；未重发该编辑请求。结果 `/tmp/dear-edit-verified.png`，日志 `/tmp/dear-edit-direct.log`。包含返回URL的原始响应仅留本机，不提交。
- 本地配置修复：`apps/runtime-service/.env` 的 `RUNTIME_IMAGE_ASSET_HOSTS` 保留旧域名并追加上述新域名，worker在K13结束后加载配置。**没有关闭白名单或放开任意URL**；密钥不写文档。
- K12最后还出现独立发布错误：模型把图片传给仅接受 `/workspace/work/` 文档的发布工具，抛 `artifact_source_denied` 导致Run失败。这不属于供应商错误。最小修复位于 `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/artifacts.py:build_artifact_tool`，设置既有LangChain `handle_tool_error=True`，仅将受控ToolException反馈为error ToolMessage，权限／路径拒绝不变；其他程序错误继续抛出。
- 回归位于 `apps/runtime-service/tests/services/dearflow_agent/test_files.py:test_artifact_tool_returns_recoverable_error_then_publishes`：非法图片发布返回error后，正常MD仍可发布。该文件 **3 passed，44.06s**。已先核对官方LangChain文档及BaseTool API。没有增加中间件或修改GraphHarbor。
- 多参考图（主图＋3参考图）真实公共工具调用：28.97秒后 `image_provider_APIConnectionError_None`，无HTTP响应，**未通过**；没有自动重试。日志 `/tmp/dear-p5-multiref.log`、结果 `/tmp/dear-p5-multiref-result.json`。前两次探针在本地路径准备阶段被拒绝（uploads目的目录／macOS临时目录软链接），未调用供应商；改用generated及真实绝对路径后才进行上述一次调用。

### 批次证据

修正白名单后的 `K12_EDIT` **1 passed、14 deselected，915.88s**：project `75495118-3be4-4585-93e8-27a7dffc0192`，thread `976d0f7f-81c5-488f-8e0b-aa0ac726ba5a`，编辑task `738d2d0b-5377-4176-9484-597a14e19d7b` succeeded，最终Run `c34d8127-a009-4f78-9456-4d10e2c6cedb`。日志 `/tmp/dear-p5-edit-fixed.log`；平台实际图片下载与哈希、MD下载和v3 lifecycle回放通过，MD SHA256 `946aad26d9c815cab7647c208a9e77dfa43f0baa53c50dc3422f040e372a6e7a`。35332可见tokens、费用unknown；915.88秒是包含worker启动等待、模型、审批、生成、发布的测试总耗时，不是图片接口响应时间。复用测试模型在finally恢复disabled。

**本轮结论：K13后端done；K12文生图和单图编辑链路done，多参考图真实验收未通过，整体partial。** 前端交接done、页面deferred；K14/K15/K16及音视频大文件仍deferred。旧unknown任务没有自动重提。除本机域名配置和上述一行工具错误处理／回归测试外，没有改动供应商适配、Deep Agents编排或GraphHarbor；新错误处理源码经定向测试，运行中worker尚需下次重启加载，不能将本轮编辑成功归功于这行尚未加载的代码。

质量检查：`uvx ruff check .../tools/artifacts.py .../test_files.py --select E9,F63,F7,F82` 通过，`git diff --check`通过。未重复执行已通过的全量P4/P5测试，也未重建wheel；此前wheel不包含这次一行修复。

`DEAR_SKILL_E2E=1 .venv/bin/python -m pytest tests/e2e/test_dearflow_skills.py -k '(K12 or K13) and not EDIT and not UPLOAD' -q -s`：**1 passed、1 failed、13 deselected，667.32s**，日志 `/tmp/dear-p5-final-retest.log`。K13通过，K12失败如上；不得将整批标为全绿。此前直连和历史供应商记录继续保留，最新状态以本节及P5执行包为准。

## 最新定向验证：更换图片供应商（2026-09-15）

用户要求先独立排查生图，不启动整套服务、不继续 Agent/PPT 验收。已停止本轮 K12 pytest 和对应 Run；本次只直接调用图片 HTTP 接口，不改生产代码。

- 上一家 `xiaok.lol`：K12/K13 四次生成均 HTTP503；独立 K12_EDIT 也 HTTP503。日志 `/tmp/dear-p5-retest-20260915.log`（2 failed，248.36s）、`/tmp/dear-p5-edit-retest-20260915.log`（1 failed，94.71s）。旧 unknown 回执保留，不重提。
- 新配置从 `apps/runtime-service/.env` 读取；直接请求 `https://cn.cdn.flux-code.cc/images/generations`，模型 `gpt-image-2.5-flare`，参数 `n=1`、`size=1024x1024`，简单蓝色几何山景提示词。禁用自动重试，HTTP超时180秒，不输出密钥。
- **通过：HTTP200，46.47秒，返回1张图片**。base64解码及 Pillow `Image.verify()` 通过，950262 bytes，SHA256 `5ce38c98f72f7ea495c2c31980ddd26cda09bf9ae9384acfbcc3e909517e9564`。
- 本地图片 `/tmp/dear-image-direct-0.png`；脱敏结果 `/tmp/dear-image-direct-result.json`；日志 `/tmp/dear-image-direct.log`。临时文件只作本机排查，关键证据已抄录本节。
- 结论：新供应商**直接文生图 done**，当前 URL／模型／凭据组合至少成功一次；不能据此承诺稳定性。新供应商编辑、Dear工具完整链路和AI三页PPT仍未验证，K12/K13整体继续 partial。以下历史失败记录不覆盖本节最新直连结果。

## 范围与实施顺序

2026-09-15，用户批准实施 P5：集中写完本批代码、测试入口和交接，再统一验证；失败只定向复验。前端代码不实施，页面验收 deferred。延续原样复制优先、必要时最小适配的迁移原则。

本批涉及 09/B03—B06、07/K12—K16、04 媒体文件、08/F5。代码完成与真实供应商验收分别登记，不用可控服务代替真实视频验收。

## 开工事实

- 现有通用图片工具位于 `apps/runtime-service/src/runtime_service/tools/images.py`，Dear 尚未装配。
- 长 MCP 只有 `tests/services/dearflow_agent/mcp_task_probe.py` 协议试验，没有正式业务持久表；P4 回归中该试验超时，需定位，不能沿用旧通过结论。
- Runtime 当前配置存在图片服务配置；未发现 MiniMax/Gemini 配置，已询问现有配置文件路径，不索取明文密钥。
- P4 遗留 K03 GitHub 限流、K05 arXiv、K09 dual_axes 外部阻塞继续保留。

## 首批历史状态（最新结果见文首续验）

**部分完成（partial）。** 本批代码已完成并统一验证；PPTX上传三图真实链路通过，K12真实编辑与完整三次AI生成链路仍受供应商unknown／HTTP524阻塞。前端交接done、页面deferred。K14/K15延期，K16异步视频及音视频大文件／Range后续实施（deferred）。

## 用户调整范围（2026-09-15）

用户先要求延期供应商接入，随后进一步明确最终范围：**K14播客、K15音乐deferred；K16异步视频、音视频大文件／Range后续实施（deferred）**。视频轮询、视频取消与交付验收一并后置，恢复K16开发时作为前置。完整长MCP／outbox仅在实际场景需要时恢复开发，没有保留未使用的供应商框架、ffmpeg或假成功工具。B03—B06不因图片回执实现而勾选完成。

## 代码位置与用途

| 需求 | 文件／函数 | 本批改动 | 验证状态 |
|---|---|---|---|
| K12 图片生成／编辑 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/media.py:build_media_tools` | 复用公共图片工具；官方 ToolRuntime 取受信身份；生成／编辑稳定幂等键，未知结果回传任务 ID；查询不能重购 | partial：组合测试与真实文生图下载通过；编辑HTTP524 blocked |
| 图片多参考图 | `apps/runtime-service/src/runtime_service/tools/images.py:build_image_tools` | 保留单图调用，额外最多 3 张参考图；仍由公共工具校验图片与下载白名单 | 参数／边界组合测试done；真实供应商编辑blocked |
| 图片付费回执 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/external_task_storage.py`、`migrations/001_external_tasks.sql` | PostgreSQL 意图／摘要／租约／fence；同 key 不同摘要冲突；过期意图 unknown，不自动重发；不存密钥、不写引擎表 | done（图片回执范围）：真实PostgreSQL及Run unknown证据 |
| 工具装配／权限 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`、`capabilities.py`、`prompts.py` | generate_image／edit_image 走写权限与官方 HITL；get_media_task 走读权限 | done：相关20项契约及真实HITL／scope证据 |
| K12／K13 资源迁移 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/image-generation/`、`skills/ppt-generation/` | 完整资源、LICENSE、provenance；图片网络脚本改为明确引导工具，PPT 原排版逻辑保留，仅加路径／页数／缺图／退出码约束 | done：9个资源及源码哈希、许可证、wheel核对 |
| PPTX 沙箱 | `apps/runtime-service/deploy/Dockerfile.agent-workspace`、`services/dearflow_agent/workspace/backend.py` | p5 镜像加入 Pillow 11.3.0、python-pptx 1.0.2；继续断网、只读根、256MiB、60秒、8MiB单文件限制 | done：Docker三页、尺寸／顺序／缺图验证 |
| PPTX 发布 | `apps/runtime-service/src/runtime_service/workspace/media.py:validate_media`、`workspace/artifact_refs.py`、`services/dearflow_agent/tools/artifacts.py` | 安全 ZIP／XML、页数1—20、拒绝宏与外部关系；不可变哈希引用；输出总大小20MiB且受既有 ZIP 解包限制 | done：负例、真实模型组装／平台下载通过 |
| 平台下载 | `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py:read_file` | 底层 MIME 白名单新增 PPTX；复用已有项目权限、文件scope、attachment、nosniff | done：14项适配器及真实PPTX下载哈希 |
| 测试入口 | `apps/runtime-service/tests/services/dearflow_agent/test_p5_media.py`、`tests/e2e/test_dearflow_skills.py`、`tests/services/dearflow_agent/skills/platform_batch.py`、`test_platform.py`；`apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py` | 真实 PostgreSQL 双并发／重启对象恢复、取消／重复购买、Docker三页、负例；增加K12／K13真实模型链路 | 已统一执行；供应商失败保持failed，详情见下 |
| 安装包 | `apps/runtime-service/pyproject.toml` | wheel显式包含私有SQL迁移 | done：SQL及全部生产Python与最终wheel一致 |

## 部署与回滚

在 Runtime 的既有 DATABASE_URI 下显式执行 `python -m runtime_service.services.dearflow_agent.external_task_storage`。请求或 lifespan 不自动建表。部署镜像构建 `docker build -f deploy/Dockerfile.agent-workspace -t runtime-agent-workspace:p5 .`，生产固定最终镜像 digest。

回滚代码与执行镜像时保留 `dear_external_tasks`，不得删除未知付费回执。关闭平台 generate_image／edit_image 工具授权即可停止新提交；旧结果仍按原文件scope读取。P5 没有新增 GraphHarbor 业务代码，也没有新建后台 Agent executor。

## 已执行验证（持续回填）

命令均在对应 app 目录执行；只对失败／修改边界定向复验，没有每次小改都全量回归。

| 验证 | 命令／入口 | 真实结果 |
|---|---|---|
| Runtime批次 | `.venv/bin/python -m pytest tests/services/dearflow_agent/test_p5_media.py tests/services/showcase_demo/test_images_chart.py tests/services/showcase_demo/test_documents.py tests/test_image_http.py -q` | **23 passed，3 skipped，17.02s**；跳过不计通过 |
| 平台文件适配器 | `.venv/bin/python -m unittest discover -s tests -p test_runtime_gateway_sdk_adapters.py -q` | **14 passed，0.375s**；含PPTX白名单、流读取和trust_env契约 |
| Docker三页 | `DEAR_P5_DOCKER=1 .venv/bin/python -m pytest tests/services/dearflow_agent/test_p5_media.py -k real_three -q` | **1 passed，3 deselected，19.29s**；实际沙箱、重新用python-pptx解析、尺寸／颜色顺序、缺图拒绝 |
| PPTX关系补强后定向复验 | 同文件 `-k 'pptx or real_three'`，保留DEAR_P5_DOCKER=1 | **2 passed，2 deselected，21.58s**；验证幻灯片关系存在、目标在包内且不重复 |
| unknown提示／取消回执定向 | 同文件 `-k image_tools` | **1 passed，3 deselected，31.67s**；取消继续传播CancelledError，记录unknown；同key不二次调用供应商 |
| SQL部署 | 加载本地`.env`后调用`ExternalTaskStorage(DATABASE_URI).initialize()` | 显式新增本地`dear_external_tasks`，退出码0；API／worker已重启，既有回执保留 |
| 镜像 | `docker build -f deploy/Dockerfile.agent-workspace -t runtime-agent-workspace:p5 .` | image ID **sha256:204e7d14f49f818545026345355c675dec744ae12dfbb423d1c7403cd4d99d85** |
| 来源／wheel | 隔离复制pyproject、README、src后`uv build --wheel`；逐文件与源码及provenance比较 | **9个K12/K13资源相同、SQL在包内、无pyc、无后置三技能**；wheel SHA256 **db94deeb24ec272066c573b456f9c055a3a2496f641d38e2dda6caa7abe0655f**，`/tmp/dear-p5-dist/langgraph_open_teach-0.1.2-py3-none-any.whl` |

完整ruff检查新增生产文件和测试通过；既有修改文件执行E9/F63/F7/F82通过，`git diff --check`通过。初次全规则扫描在既有`tools/images.py`发现RUF059及BLE001历史告警，没有把历史代码全量格式化。首次在原目录构建wheel带入旧build缓存中的runtime-smoke pyc，检查真实失败；改为隔离目录构建后逐项通过，没有删除用户工作目录或掩盖问题。

## 实际模型／供应商失败与证据

1. `DEAR_SKILL_E2E=1 ...pytest tests/e2e/test_dearflow_skills.py -k 'K12 or K13' -q -s` 首轮 **2 failed，11 deselected，48.78s**。原因是验收脚本审批白名单遗漏图片动作；此时未提交图片购买。已补白名单，并新增`complete_batch_case`续接原Run，不重复创建付费任务。日志`/tmp/dear-p5-platform.log`。
2. 原线程续接：K12 project `b72b5564-b6a2-4b3a-a6ef-715ef9f5d38d`，thread `a84c4737-9dc2-4efa-89be-40b4dc4a56c7`，任务 `78239b80-349e-4528-9fb3-0d328dc03dc4`；实际提交后未拿到可交付图片，回执unknown。模型查询同一回执并发布缺失说明，未重新购买。最终Run `0ebab70b-8ce8-400c-8c37-c168044fd028`；说明文件SHA256 `cdeaba86b8e42db57d7ab4aadb69395ad044e5bb98035bb46eb79812811ebb02`。这是失败处理证据，不算图片生成成功。
3. K13 project `169dce48-d390-445a-ad4b-3f2fc8f707ac`，thread `472e8ee5-c5aa-4768-b303-456d87f451d8`：任务 `3d9352c3-3a8f-4716-8f71-c398a161b915` 实际生成PNG（912792 bytes），SHA256 `b93e69707fa712e5e2fee97d85f33b695ef7b3f5badc4d846f0210e283eb42b9`，路径 `/workspace/generated/4298aa19e2c844c287578b1912097b96.png`。第二任务 `b3edafc4-cf89-4995-ae24-9c4ac10aea61` unknown；没有重新购买，未生成第三页。模型反复本地查询后触发Flash既有12次thread预算，Run `e5809e08-8225-470a-b40b-54bbfadc1bdc` error（`ModelCallLimitExceededError`）。不增加预算掩盖失败；回执增加明确“无后台恢复，停止轮询，报告缺失”的notice。日志`/tmp/dear-p5-resume.log`。
4. 只读供应商`models.list()`成功且包含配置的图片模型，说明配置可用，但不证明每次生成稳定。上述unknown发生时未保存细粒度错误，不能武断称为HTTP502；已给公共图片异常补脱敏类型／HTTP状态码，持久到`error_code`，不保存provider正文或密钥。
5. 后续只定向验证 `K12_EDIT`（上传图一次编辑）和 `K13_UPLOAD`（真实模型使用三张明确标为测试上传图组装PPTX），没有重试unknown生成订单。它们是分段验证，不替代“三次AI生成均成功”的证据。日志`/tmp/dear-p5-targeted.log`，结果 **1 passed、1 failed、13 deselected，352.75s**：K13_UPLOAD通过，K12_EDIT因供应商524失败。

## 前端／运维交接

F5交接已写入 [frontend-handoff.md](../frontend-handoff.md)：嵌套`result.runtime_images`、图片回执三态、官方审批、PPTX普通文件下载、图片型说明、未知结果不重购，以及K14/K15延期、K16和音视频大文件／Range后续实施（deferred）。**交接done、页面deferred**。

图片任务表只保存intent/succeeded/unknown、归属、请求摘要／必要提示词、model、origin_run_id和审批tool_call_id；没有provider密钥。`get_media_task`按当前受信Run的tenant/project/user/thread授权查询；没有新的REST任务面。供应商未知结果需运营侧凭账户记录核对，首批不承诺通用exactly-once或自动恢复付费响应。暂不支持后台任务取消、租约接管重提、outbox通知；这些仅在K14/K15或实际长MCP明确需要时恢复；视频相关部分随K16后续实施。

## 补充证据

- Agent／文件／P2契约定向：`.venv/bin/python -m pytest tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_files.py tests/services/dearflow_agent/test_p2_contracts.py -q`，**20 passed，69.46s**。
- 移除本轮不再需要的大文件读取参数后，只复验文件边界：`...pytest tests/services/dearflow_agent/test_files.py -q`，**2 passed，19.76s**。
- 最终隔离wheel逐一比较**全部生产Python和SQL**与当前源码，均相同，无pyc；34份项目文档本地链接检查无缺失。
- Docker样例PPTX：38393 bytes，SHA256 `06151a9ae301f2a50012b0d2cb221210ce7acd92f35f428ff132d12f3a956228`；完整临时工作区及三个输入图引用见`/tmp/dear-p5-pptx.json`。
- K12_EDIT真实上传图编辑：project `877872c7-22a1-4cf2-927d-c2f8825c8b72`，thread `5759e0ca-6d05-4fa3-b74d-adf5f70cf1c5`，任务 `9f5c5a84-6671-421a-9fe8-11ba29a514cb`；供应商返回 **HTTP524**，error_code=`image_provider_InternalServerError_524`，状态unknown，无可信编辑后图片，无重试。根Run完成仅说明失败报告交付，不表示图片成功。

## 首批上传图PPTX交付与历史四态结论

`K13_UPLOAD`：project `5001374f-635c-4df1-97c7-dafdff6de667`，thread `8f3e0ff2-14f7-4212-b0a2-6a8d7c594a63`。
初始Run `4eea198e-9506-4caa-ba8f-e810abfc4155`，最终Run `e12152a0-9e75-4af0-96d9-d8f58a43faa9` success。
模型读取技能、使用三张明确标记的上传测试图片、经官方审批执行脚本、发布PPTX／MD；平台下载哈希与MIME核对通过，实际包内3张幻灯片。
PPTX 38723 bytes，SHA256 `6081e8593087a66ac8f51ac3e079988f1aa0059077e00afa9cdd8886bb7ec33c`；
MD SHA256 `224f52a06af3063d086bbaa53b9bff0e6a5ee640f15c8864c653e3a49de9cb9c`。
模型DeepSeek-V4-Flash，model_id `9c276f29-a5cf-48a3-8cfb-86ab09f57537`；可见用量110366 tokens，实际费用unknown，不能当作全量计费账单。
样例使用上传图片，**不冒称三次AI生成完整通过**。

真实生成的第一张PNG经平台图片下载HTTP200，SHA256仍为 `b93e69707fa712e5e2fee97d85f33b695ef7b3f5badc4d846f0210e283eb42b9`；切到另一测试项目同一URL返回404。证据 `/tmp/dear-p5-image-download.json`。未重复调用供应商。

| 项目 | 最终状态 | 仍缺什么 |
|---|---|---|
| 图片回执、scope、去重、unknown、取消传播 | done（本批同步图片范围） | 不包含远端自动恢复／后台worker |
| K12图片生成／编辑整体 | partial；供应商blocked | 文生图真实下载通过，编辑HTTP524；多参考图实际供应商未通过 |
| K13上传图组装／PPTX发布下载 | done | 页面预览由前端后置 |
| K13三次AI生成→完整演示 | partial；供应商blocked | 第二张unknown，保留第一张，没有重新购买 |
| K14／K15 | deferred | 用户决定延迟开发 |
| K16异步视频、音视频大文件／Range | **deferred：保留需求，后续实施** | 保留后续实施／验收条件，本批不算功能done |
| 正式长MCP、outbox、自动续接 | deferred | 仅实际需求恢复时实施；旧B02超时仍未解决 |
| F5交接／页面 | done／deferred | 本次没有platform-web代码修改 |

下一次只针对供应商恢复后的编辑／生成验收缺口继续；不要重跑所有P4/P5用例，更不能用新key盲目重试unknown订单。源码与文档已保留；本轮未commit、push或操作GraphHarbor。


## 范围澄清与图片验收解释

用户再次澄清：K16异步视频、音视频大文件／Range是**后续实施（deferred）**，并未取消。已恢复迁移卡片、后续任务和验收要求，本批仍不实现。

现有图片接入沿用Runtime配置的OpenAI兼容服务：base URL `https://wawapii.com/v1`，配置模型名 `gpt-image-2.5-flare`。文生图调用 `POST /images/generations`，参考图编辑调用 `POST /images/edits`；配置来自 `IMAGE_25_URL/IMAGE_25_MODEL/IMAGE_25_KEY`。这是本项目当前配置的第三方兼容端点，不能只依据模型名认定其底层为OpenAI官方直连。没有为本批新增MiniMax/Gemini图片接入。

K12_EDIT验收把一张320×180蓝色测试图片上传至线程工作区，请服务“添加一个小橙色圆形”。返回HTTP524，没有可校验的编辑后图片；已记录unknown。524是网关超时类响应，当前证据不足以断言底层模型未执行、已取消或未计费。

“AI三页生成”是K13验收样例：DeepSeek-V4-Flash负责读技能、规划与调工具；图片服务依次生成“蓝色山脉、绿色丘陵、橙色日落”三张页图；Pillow/python-pptx在隔离沙箱中将每张图片放入一页16:9幻灯片，最后发布PPTX和说明。这是图片型PPT，不是原生可编辑文字／图表。三页是测试规模，当前实现上限为20页并受文件／沙箱资源限制。

结果：第一张AI页图生成及授权下载成功；第二张提交未得到可交付结果，记录unknown；第三张没有继续生成，完整三页链路未通过。另用三张明确标为测试上传的图片，真实模型组装、发布、平台下载PPTX的链路已通过，证明该段功能可用，不替代三次图片生成成功的证据。

“未重复购买”应准确理解为**未自动再次提交可能计费的请求**，不是确认已经购买／退款。真实供应商费用仍unknown；超时后换新key或直接重发可能产生第二次费用，因此保留原任务ID和回执用于核对。
