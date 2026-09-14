# 04 工作区、沙箱与文件产物

## 目标

解除 Showcase 耦合，让所有声明支持文件能力的 Agent 使用一致的授权、路径和产物契约；为 23 个 Skills 提供可复现、隔离、有预算且可恢复的执行环境。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P1 作用域／执行 Backend／TXT／产物；P3 子任务隔离；P4—P5 格式；P7 备份恢复联合验收。
- **必读前置：** [01 S4 与第一轮实施包](01-architecture-and-boundaries.md)、[08 C04／W03／F1](08-web-and-platform-contracts.md)；扩格式前读 [07 当前 K 卡片](07-skills-migration.md)。
- **输入 → 输出／对接：** 受信 graph/thread binding → Backend 与 HTTP 一致资源根、不可变产物引用、格式能力；同时交给 Runtime 工具、Platform 代理和前端预览。
- **当前切片／最近证据：** 2026-09-14 规划第二版；业务未实施，无实施验证记录；本文末尾只记录文档调研情况。
- **下一任务：** 04/W01—W03、W05 的 P1 最小切片；旧 Showcase 路径回归不可省。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 1. 现状、参考与目标

| 能力点 | 当前缺口／参考代码 | 拟实现位置 |
|---|---|---|
| 工作区解析 | `apps/runtime-service/src/runtime_service/workspace/scoped.py:get_showcase_workspace_root` 固定 Showcase 根；DeerFlow `backend/packages/harness/deerflow/config/paths.py` 提供虚拟映射 | 同目录改成由受信 graph／thread binding 决定的公共 `resolve_thread_workspace`；服务端声明支持范围 |
| 图片与文档入口 | `apps/runtime-service/src/runtime_service/http/images.py:_authorize_image_request` 固定 assistant_id；`http/documents.py` 也用 Showcase 根 | 两个现有路由复用相同 workspace resolver；不再根据客户端传来的 graph 名拼路径 |
| 执行 Backend | `services/demo/showcase_demo/backend.py:DockerWorkspaceBackend.execute` 每命令一个容器、禁网、最多 60 秒 | 公共拟新增 `apps/runtime-service/src/runtime_service/workspace/execution.py`；服务私有 `services/dearflow_agent/backend.py` 绑定资源；沿用官方 BackendProtocol／SandboxBackendProtocol |
| 文件输入 | 当前 `workspace/file_refs.py:MIME_EXT` 只有五种文档 | 扩充现有引用与校验，并新增明确的产物引用；输入和输出不混用“只能在 uploads 下”的校验 |
| 成果展示 | DeerFlow `backend/packages/harness/deerflow/tools/builtins/present_file_tool.py` 更新 artifacts | Runtime 工具返回经验证的 ArtifactRef，Web 按 08 渲染；不复制 DeerFlow 自定义 state reducer |
| 技能脚本挂载 | Showcase 的容器只见 `/workspace`，无法执行包内 Skills 脚本 | 只读挂载已启用的确定版本 Skills 到 `/skills/`，模型文件 Backend 与执行容器使用一致虚拟路径 |

### 1.1 需要消除的 Showcase 专属耦合

这里的“消除耦合”只针对产品身份、路径和编排分支；现有上传、下载、解析、授权、流式传输等通用组件应继续复用，不另起一套附件系统。

| 位置／符号 | 当前耦合 | 处理方式 | 验收 |
|---|---|---|---|
| `runtime_service/workspace/scoped.py:get_showcase_workspace_root` | 工作区根目录由 Showcase 固定函数决定 | 提取公共 `resolve_thread_workspace(thread_binding)`；Showcase 仅提供旧 binding 适配 | Dear Agent、Showcase、不同项目路径互相隔离；旧线程仍可读 |
| `platform-api/.../application/service.py` 上传／读取分支中的 `reference_agent`、`showcase_demo` 白名单 | 是否能上传、读取、排队由 assistant/graph 名称判断 | 改为 graph capability／thread binding 判断；名称只用于展示 | 新增 Dear Agent 无需修改硬编码集合；未声明能力仍拒绝 |
| `runtime_service/http/images.py:_authorize_image_request`、`http/documents.py` | 用 `assistant_id` 和 Showcase 根拼接资源路径 | 统一调用 workspace resolver 和 capability 授权；客户端只提交 thread 与 FileRef | 伪造 assistant、跨项目路径和绝对路径均拒绝 |
| `platform-web/src/modules/chat/composables/useChatAttachments.ts` | `currentGraphId === "showcase_demo"` 才启用图片／附件分支 | 改为读取运行时返回的 attachment capability；保留 Chat 组件作为通用 UI | Dear Agent 与 Showcase 都能按能力声明上传；无能力时 UI 明确禁用 |
| `platform-web/src/modules/chat/composables/useChatSession.ts` | `supportsQueue` 通过 `reference_agent`／`showcase_demo` 名称推断 | 改为 session capability／协议字段；队列动作仍复用现有实现 | 新 Agent 不改前端白名单即可获得声明能力 |
| `runtime_service/application/service.py` 中 `assistant_id in {"reference_agent", "showcase_demo"}` 的附件／结果特殊分支 | 服务层把样例 Agent 当作资源权限边界 | 将分支下沉为通用 graph/thread binding；Showcase 只保留配置数据 | 删除名称判断后，通用路径测试覆盖两种 Agent |
| `services/demo/showcase_demo/backend.py:DockerWorkspaceBackend` | 通用执行能力藏在 Showcase demo service 下 | 抽取最小 Backend 协议实现到 `workspace/execution.py`；Dear Agent 通过服务目录装配，Showcase 保留薄适配 | 两种 Agent 使用同一资源限制和取消清理逻辑 |

以下代码属于通用能力，不能因为解耦而删除或复制：`runtime_client.py`／`runtime_gateway_upstream.py` 的上传端口、`workspace/file_refs.py` 与 `documents.py` 的校验和原子 I/O、`security/tokens.py` 的操作令牌、`http/presentation.py` 的审计映射、Chat 的 `ThreadFile.vue`／`ThreadImage.vue`／`ChatArtifactPanel.vue`。它们只需把输入从“Showcase 名称”改成受信 binding／capability。

禁止的“伪解耦”包括：新增 `dearflow_*_upload` 与旧路由并存、把 `showcase_demo` 再加入更多白名单、在 Dear Agent 中复制一套 workspace 根解析、让模型直接传宿主绝对路径，或把通用执行器重新放回 Showcase。

### 2. 路径与资源生命周期

业务模型统一看到：

```text
/skills/public/<skill>/       只读、随发布版本固定的资源
/skills/custom/<skill>/       只读、该授权域已发布的自定义版本
/workspace/uploads/          用户输入，只读给通用执行容器
/workspace/work/             可写中间文件，按任务目录进一步隔离
/workspace/outputs/          最终候选产物，验证后才对用户公开
```

现有 `/workspace/generated/`、`/workspace/charts/` 图片引用仍按已持久化路径读取；新产物统一 outputs，旧文件不批量搬家。文件 HTTP 使用线程的服务端资源绑定找到真实根，不能把增加另一个 graph ID 到硬编码列表当作解耦。

新工作区 scope 包含 tenant／project／graph／thread；多 worker 共享同一资源 binding。已有 Showcase 根由既有资源版本识别，保留原路径供旧线程访问；这是持久数据版本处理，不增加运行时兼容包装层。新 Graph 不复用 Showcase 数据根。

每次访问重新校验项目、Agent／线程归属和 capability。Thread 的 graph／workspace binding 建立后不可由普通消息或 resume 切换。所有服务只传虚拟路径或 artifact ID，不暴露宿主绝对路径。

并行子任务默认写入各自 `/workspace/work/<task-id>/`，输入快照只读；主 Agent 验证后发布结果。同路径写入有冲突检测；不允许两个子 Agent 共享任意可写根并靠提示词避免覆盖。

### 3. 输入／处理／输出／预览矩阵

| 格式 | 输入与处理 | 输出／Web 行为 | 依赖与约束 |
|---|---|---|---|
| TXT／MD／JSON／CSV | 保留并强化现有解析 | 文本、Markdown、表格及下载 | 编码、单元格／行数、CSV 公式导出策略；大文件分页而非全量入 Prompt |
| PDF | 复用现有 PyMuPDF；按页读取／提取 | PDF 下载与受限预览 | 加密／损坏明确报错；扫描 PDF 无 OCR 时提示不具备文本，不虚构解析成功 |
| XLSX | 多 sheet、类型、公式缓存、统计 | 有界表格预览、XLSX 下载 | 执行镜像固定 openpyxl；zip bomb、外链、宏、安全公式边界；不执行公式 |
| XLS | 真实旧格式解析 | 表格预览、下载或转换后的 XLSX | 单独锁定支持旧格式的解析器（候选 xlrd）；不能以 openpyxl 宣称支持 XLS；损坏／加密测试 |
| DOCX | 段落／表格提取和生成 | 下载、文本提取预览 | 需要时锁定 python-docx；属于格式补全，不默认引入 Office 全套服务 |
| PPTX | 文本与页信息读取；PPT Skill 输出 | 下载＋生成时随附的页图预览 | python-pptx、Pillow；保留上游图片型幻灯片，暂不声称所有元素可编辑 |
| PNG／JPEG／WebP | 复用图片上传、识图及生成 | 图片预览、下载 | 魔数、像素总数、大小；GIF 明确拒绝直传并可提供显式转换，不偷偷截第一帧 |
| MP3／WAV | 上传为资源；不自动承诺转录 | 原生 audio、Range 下载、转写稿文本 | 生成及混音时 ffmpeg／ffprobe；有界时长和解码资源 |
| MP4 | 上传为资源；不自动承诺视频理解 | 原生 video、Range 下载 | 视频 provider 输出与 ffprobe 验证；不读取远程任意 URL 播放 |
| HTML／CSS／JS | 代码资源或生成项目 | 下载；需要互动预览时独立 sandbox iframe | 禁止同源任意 JS；CSP、无平台 cookie、无 top navigation、默认禁外网 |
| ZIP／TGZ／.skill | 项目／技能包的显式导入 | 下载／安装候选包 | 单独受控解包：拒绝穿越、软链接、设备文件、过量条目及膨胀；不因上传而执行 |

“支持上传”不等于“支持理解／预览／执行”。能力接口必须区分四列；音视频内容识别不是本次隐含需求。补充格式在对应 Skill 前验收；Word 等没有当前消费者的生成工具不提前造一套框架。

### 4. 引用契约与下载

保留现有输入 FileRef／ImageRef 的受控读取。拟新增 `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:ArtifactRef`：`version, artifact_id, path, file_name, mime_type, size_bytes, sha256, kind`；租户和真实存储地址由服务端绑定，不能由模型提供。

拟新增 `apps/runtime-service/src/runtime_service/http/artifacts.py` 只做 HTTP 参数／授权与流式传输，公共 I/O 在 workspace；发布业务校验由服务工具执行。

- `present_artifacts` 先检查文件存在、普通文件类型、scope、MIME、字节数、hash，再返回引用；发布后文件以内容 hash 固定，覆盖产生新引用。
- 预览／下载经 Platform 重新授权；支持 Range、Content-Disposition、nosniff；大文件流式传输，不 base64 整体放进 JSON／messages。
- 文件删除与 Thread 删除有明确生命周期，活跃运行／引用不能被后台清理截断。下载授权变化及时生效。
- 参考 `apps/runtime-service/src/runtime_service/workspace/documents.py:DocumentWorkspace.put` 的原子写与描述符 I/O；抽取通用部分后图片和文档都复用，避免多个不一致的路径检查器。

### 5. 执行环境生产基线

拟新增 `apps/runtime-service/deploy/Dockerfile.agent-workspace`：固定 Python／Node／分析依赖、PPT、音频工具与必要字体；按依赖实际引入，构建锁定版本和镜像 digest。Runtime 服务镜像和任务镜像分开。

- 禁止 Skill 脚本运行时 `pip install`／全局 `npx skills add -g`；DuckDB 的 `INSTALL spatial` 等运行时下载改成镜像内固定依赖或用 CSV／Excel 读取替代。
- Shell 使用非 root、cap-drop、只读系统盘、独立 tmpfs、CPU／内存／PID／输出限制；不挂宿主仓库、凭据目录或 Docker socket 给任务容器。
- 生产执行 worker 位于独立执行信任域；接触 Docker daemon 的管理权限是运维边界，不能因为任务容器没 socket 就宣称 Runtime 宿主安全。固定部署在专用执行主机，评审其攻击面。
- 默认 Shell 无网络；搜索、下载、付费 provider 与部署走受控工具。若技能需要真实联网构建，依赖预装或显式出网策略，不整体开放网络。
- 文件解析／压缩／ffmpeg 在受限进程或任务容器，限制解析时间与膨胀量，不能堵塞 API 事件循环。
- 普通命令拟定 120 秒、硬上限 300 秒；长时间外部生成转入 09 的任务机制。默认内存拟定 1 GiB、CPU 1、PID 128，P0 实测后冻结。
- 取消必须终止所属执行进程／容器并有界清理，不能只取消 await；清理失败保留资源 ID 与告警，后台回收需核实无活跃 owner。

### 6. 存储、配额与恢复

拟定每线程工作区 1 GiB；普通输入 20 MiB、图片沿现有 5 MiB Web 上传上限、媒体 100 MiB，解析后最大膨胀 200 MiB／5000 条目。以上是容量初值，前后端、代理和执行环境一起冻结，不能只改前端提示。

工作区独立于 checkpoint，时间旅行不会自动回滚真实文件。历史产物以不可变内容版本引用；分叉默认只拷贝选定输入与已经固定的产物，不把后续工作目录带入历史分支。若不提供工作区快照，Web 明确显示这一限制。

生产先验收专用执行主机＋持久卷。多副本需要共享资源可见性、scope 一致、并行写冲突和清理 owner fence 测试；没有测试的拓扑不列为支持。备份必须覆盖数据库与产物引用对应的文件版本，恢复后重新校验 hash。

## 任务拆分

- [ ] W01：按 §1.1 清除名称白名单和固定根目录耦合，建立公共 workspace resolver／capability；修改 `workspace/scoped.py`、`http/images.py`、`http/documents.py`、Platform 上传与 session capability 分支；补旧 Showcase 与 Dear Agent 回归。
- [ ] W02：提取共享执行资源实现并新增服务 `backend.py`，保持 Showcase 只做原样例装配；测试 `apps/runtime-service/tests/services/dearflow_agent/test_backend.py`。
- [ ] W03：增加 ArtifactRef、发布工具及下载／预览路由；测试 `apps/runtime-service/tests/test_artifact_http.py`（拟新增）。
- [ ] W04：XLSX／XLS／PPTX／媒体／项目包按矩阵补全，测试 `apps/runtime-service/tests/services/dearflow_agent/test_formats.py`。
- [ ] W05：锁定任务镜像、只读 Skills 挂载和资源预算；测试容器取消、清理、并发与配额。
- [ ] W06：版本化 workspace binding、升级旧路径、备份恢复、Thread 清理与分叉语义，形成可运行运维验收。

## 验证要求与记录

- [ ] DearFlow 和 Showcase 相同 thread 字面值的资源仍正确隔离；跨租户／项目、伪造 artifact_id、符号链接／路径穿越拒绝。
- [ ] 所有矩阵格式分别验证输入、处理、输出、预览；旧 XLS、压缩炸弹、超大图片、加密／损坏文档有真实样本。
- [ ] 容器内 Skill 脚本可读但不可修改；上传原件不可覆盖，输出真实且可下载。
- [ ] 取消后 10 秒内正常清理（拟定门槛）；超时／worker 崩溃后可定位并回收，不能删除他人活跃资源。
- [ ] HTML 不得读取平台 cookie 或顶层页面；大媒体下载 Range 正确，内存有界。
- [ ] 备份／恢复后引用不悬空；磁盘耗尽明确失败，无半文件成功回执。
- 2026-09-13：仅完成设计，生产隔离、性能及格式测试未执行。

## 状态

规划中，P1 基础必需；格式按 Skill 顺序补齐，生产发布受 10 门禁约束。
