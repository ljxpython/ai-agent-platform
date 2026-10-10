# F07 任务与进度

> R1-R5 已批准，推进范围为后端、Runtime、引擎源码配套与前端交接。`[x]` 只表示该任务已完成；前端及正式发布单独标注。

## Phase 0：本轮规划交付

- [x] P00 源码对照：当前平台/open-swe/DeerFlow 调用链、标题事实源、自动入口与历史决定已核对，见 `comparison.md`。
- [x] P01 取舍与范围：P1 现有接口补齐、P2 自动体验、CAS 前置、三层归属和排除项已列明，见 `plan.md`。
- [x] P02 任务、验收与独立前端交接已完成，见本文件、`verification.md`、`frontend-handoff.md`。
- [x] P03 既有标题定向测试已真实执行：Runtime 13、API 6、Web 36 项通过，见 `verification.md`。
- [x] P04 人工治理评审：2026-10-09 用户明确“我已经评审完成，可以开始实施了”，批准 R1-R5 与引擎配套源码范围。前端交给同事，外部正式发布不在本轮授权内。

## Phase 1：现有标题链路补齐（后端/Runtime，建议优先）

### [x] T01 冻结标题契约与精确委托

- **改动内容：** 现有 summarize URI 增严格有界 DTO 与固定 outcome；两端新增精确 `title-generate`。mandatory auth、tenant/project/thread/assistant/hash 绑定；read/write 分别委托。兼容现有手动空请求/文本请求；非法字段 fail-closed。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` → `summarize_thread_title()` / delegation factory；`application/service.py` → `summarize_thread_title()`；`core/security/tokens.py`；`apps/runtime-service/src/runtime_service/http/title_summary.py`；`runtime/auth.py`、`auth/platform.py`。
- **预期结果：** 无 token/错误 operation/跨项目与 Thread 被拒绝；标题 token 无原生资源访问；授权失败不调用模型、不修改标题。
- **验证项：** 两端 scope 集合测试、真实 HTTP 拒绝矩阵、现有 route matrix 与文本调用兼容；不依赖固定 operation 数量或索引。
- **状态：** 已完成 2026-10-09；见 [实施记录](implementation/01-title-safety.md)。API 38 项定向（含跨 Runtime 委托、HTTP route matrix）通过；Runtime signed HTTP 拒绝矩阵通过，完整网络链路继续记 T07。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] T02 把同一个生成器接入受管模型

- **改动内容：** API 使用项目默认/允许模型、短时 model reference（comment action）；要求 comment+edit。Runtime 复用 resolver/modeling；新增有实质编排职责的 `services/thread_titles.py`，保留 utils 中的文本 helper，移除独立 dotenv/proxy 和微型 create_agent wrapper。一次直接无工具调用、8s 总 deadline，取消/授权错误继续传播。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → 现有 `_inject_project_default_model()`、`_validate_run_options()`、`_attach_runtime_model_reference()`；`adapters/langgraph/runtime_gateway_upstream.py` / `application/ports.py`；`apps/runtime-service/src/runtime_service/services/thread_titles.py`（新增） / `utils/title_summarizer.py`。
- **预期结果：** 主运行与标题不再使用两套凭据入口；未配置模型/超时/provider 失败保留安全规则标题；invalid policy/hash 不降级成成功。
- **验证项：** 受管模型替身、项目模型禁用/BYOK 隔离、超时与取消、max_retries=0、无工具/无 native Run；正式主模型真实 one-shot 至少一次。
- **状态：** 已完成2026-10-09。Runtime受管服务6项通过（含阻塞构造deadline）；真实百炼qwen-plus经平台创建项目受管模型、主Run、一次title调用与CAS刷新通过。标题HTTP耗时1.293s；DeepSeek真实超时记录保留。
- **合规检查：** [x]实现；[x]Phase验证；[x]任务状态；[x]CONTEXT；[x]FEATURES；[x]CHANGELOG。

### [x] T03 输入、附件与输出归一化

- **改动内容：** 只取可证明来源的 user/final assistant 正文；处理 role/type alias、多文本块、提醒、think/reasoning；不用块对象 `str()` 或 reasoning fallback。内部可选附件材料从已提交 `runtime_file` 引用取得，沿现有文件校验/归属检查；单附件无文本本地命名、多附件计数，不发文件内容/路径到模型。
- **代码位置：** `apps/runtime-service/src/runtime_service/utils/title_summarizer.py` → `_format_messages_for_agent()`、`clean_generated_title()`、`_fallback_extract_title()`；`http/title_summary.py` request DTO；`services/thread_titles.py`（新增）；复用 `workspace/file_refs.py::validate_file_ref()`。API `summarize_thread_title()` 的 state 材料提取。
- **预期结果：** 标题只有正文纯文本；模型异常保留初始标题；附件不调用 LLM；文件必须存在于当前 Thread 的受信工作区且 hash/mime/size 匹配。原 filename 沿已提交引用，当前存储不保存原 filename，不能宣称名称不可伪造。
- **验证项：** thinking-only、工具调用 AI、Unicode/控制字符、多个文本块、超长输入、合法/伪造附件、图片无文件名、首轮材料缺失。
- **状态：** 已完成 2026-10-09；见 [实施记录](implementation/01-title-safety.md)。正文/角色/提醒定向与真实隔离工作区附件归属校验通过；Runtime 服务 5 项通过。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## Phase 2：自动标题增量（P2，已批准）

### [x] T04 引擎通用条件更新源码与候选接入

- **改动内容：** 已批准的通用metadata CAS、普通PATCH原子merge、独立条件URI与授权filter同SQL。候选双包构建/安装和实际平台transport接入；正式发布独立拆到B01，不修改引擎表或现役site-packages。
- **代码位置：** 外部 `graphharbor/libs/langgraph-runtime-pg/src/langgraph_runtime_pg/thread_metadata.py` → `patch_thread_metadata()`、`ops.py::Threads.patch()`；`libs/langhost/src/langhost/core_api.py::threads_metadata_cas()` / `server.py` route与OpenAPI。平台 `application/ports.py`、`adapters/langgraph/runtime_gateway_upstream.py::compare_thread_metadata()`。
- **预期结果：** 同 Thread 多 API 实例下，手动先提交则自动不覆盖；自动先提交则随后手动覆盖；不回写已消费 seed；条件失败可确定对账。
- **验证项：** 真实PG多session并发屏障、两种提交顺序/同名改回、无关键merge、null/filter/HTTP/ttl/minimal；冻结依赖候选cold install与使用方HTTP提交丢响应对账。
- **状态：** 已完成2026-10-09；4项PG/HTTP通过（36.35s），v2四产物/冻结依赖独立cold install来源核对及实际平台CAS链路通过。PyPI正式post43实查无CAS，正式发布/正式源接入单列B01。
- **合规检查：** [x]实现；[x]Phase验证；[x]任务状态；[x]CONTEXT；[x]FEATURES；[x]CHANGELOG。

### [x] T05 自动资格、首轮校验与安全落库

- **改动内容：** 新普通 Thread opt-in 与内部 seed；rename/manual success 清 seed，preview-only 不清；auto 模式从 native read 确认成功 Run、Thread/Graph 归属和根图已提交消息。生成前后查当前权限/开关/seed，CAS 写入；公开 pending 布尔投影，客户端不能注入标记，fork/旧数据不回填。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `create_thread()`、`update_thread()`、`summarize_thread_title()`、`fork_thread()` 与私有字段出口；`presentation/http.py` DTO；`config.py` → `title_auto_enabled`（新增，默认 false）。
- **预期结果：** 初始标题非空仍可升级；用户手动标题优先；重复自动请求只有一个最终结果；success 与最终材料未同时确认时等待下一有效机会而非猜测完成。
- **验证项：** 首轮/多轮、成功/工具中间态/interrupt/error/timeout/stop、同名 rename、双标签页、跨项目、撤权、开关中途关闭、fork/导入/旧 Thread、条件冲突/上游写结果未知。
- **状态：** 已完成2026-10-09；API auto/manual/fork27项通过（8.035s，含preview迟到返回不覆盖新title）；真实候选HTTP/Worker成功、同名改名、provider降级、双请求CAS、gate/model撤销与未知提交GET对账通过。ACL单元拒绝矩阵通过，最新真实平台撤权扩验见T07A。
- **合规检查：** [x]实现；[x]Phase验证；[x]任务状态；[x]CONTEXT；[x]FEATURES；[x]CHANGELOG。

### [ ] T06 前端同事接线

- **改动内容：** 按 `frontend-handoff.md`，双聊天入口共用辅助 composable；新会话 opt-in，已有 SDK Run success 与最终正文双条件；独立 HTTP 单飞与身份/项目/Thread/Run epoch，后台可见补偿；真实落库返回更新 metadata，手动动作继续可用。
- **代码位置：** `apps/platform-web/src/services/threads/session.service.ts`；`src/modules/chat/composables/useAutomaticThreadTitle.ts`（新增）；`ChatSession.vue` 与两处 Page 的 title 更新 handler。`useDearAgentSession.ts` 现有共享出口保持复用。
- **预期结果：** 标题可升级但不阻塞对话；迟到结果不覆盖改名/新项目/新 Thread；页面关闭不承诺后台生成；无新 SSE/运行状态机。
- **验证项：** composable/service/Page 最小定向测试、vue-tsc/lint/build；1440/768/390 的长标题和改名交互；F01-F10 交接验收。
- **依赖/状态：** T05契约冻结；同事可在隔离环境开启gate开发，正式开启依赖B01与F01-F10。待同事实施，本轮交付已冻结交接文档。

## Phase 3：联合验证与发布前收尾

### [x] T07A 非前端验证、回退边界与文档交接

- **改动内容：** API/Runtime/GraphHarbor真实HTTP/Worker/PG/Redis与受管模型、权限/竞态/流隔离/手动回归和关闭auto验证；记录正式来源和匹配发布/回退边界，同步活规范及冻结前端交接。全项目Final由T07B补齐。
- **代码位置：** 测试位置/命令见 `verification.md`；`docs/standards/delegation-jwt.md` / `README.md`、`apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`、Runtime/Web 对应活规范。
- **预期结果：** 非前端实现与候选证据齐全，剩T06/T07B前端及B01正式发布；不报现役可用或全项目done。
- **验证项：** 定向单元/委托/HTTP/真实PG与受管模型，ACL/gate/model中途撤销、未知写对账、静态/文档校验；通过与既有基线失败如实记录为Phase。
- **状态：** 已完成2026-10-09。9场景fixture通过（79.28s），真实qwen-plus链路通过，Runtime76项（排除1项HEAD既有fixture失败）、跨解释器委托新增title operation5项通过；静态/文档定向与差异校验见verification.md。交接已冻结，前端/正式发布独立。
- **合规检查：** [x]实现；[x]Phase验证；[x]任务状态；[x]CONTEXT；[x]FEATURES；[x]CHANGELOG。

### [ ] T07B 前端联合Final（同事完成）

- **改动内容：** T06实施后补两聊天入口F01-F10、三个视口Playwright真实模型/刷新/改名，执行独立联合Final。
- **代码位置：** `frontend-handoff.md`中的service/composable/Page测试与浏览器链路。
- **预期结果：** 前端接线和后端契约一致，真实UI不阻塞send/Stop/HITL，无幽灵消息、跨作用域或改名回滚。
- **验证项：** Web定向/类型/lint/build、1440/768/390真实浏览器、三服务模型E2E；B01正式接入核对后才启auto。
- **状态：** 待前端同事，与T06一起交接；本轮不写Final通过。

## Block

- [ ] B01 正式CAS双包发布与使用方正式源锁接入：**blocked**。2026-10-09实查PyPI官方post43无CAS，候选同版本有CAS但哈希/来源不同。须新的唯一双包版本，四产物发布、正式源cold install/锁更新和匹配API/Runtime回归。发布不在本轮授权内，不覆盖post43、不改现役。手动/自动AI新版同样依赖CAS，不能只关闭auto后单独发布API。

## 进度汇总

| 阶段 | 状态 |
|---|---|
| 本轮规划交付 P00-P03 | 已完成 |
| 人工评审 P04 | 已批准 |
| P1 现有链路补齐 T01-T03 | 已完成 |
| P2 后端/引擎 T04-T05 | 源码与候选已完成，正式发布单列B01 |
| 前端 T06/T07B | 同事待实施与联合Final |
| 非前端收尾 T07A | 已完成，定向/真实HTTP/真实模型证据与交接齐全 |
| 正式发布 B01 | blocked；需要唯一新版本与正式源接入 |

实施细节见 `implementation/`；进度以本文件的任务状态为准。
