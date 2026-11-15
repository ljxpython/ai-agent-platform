# Worker 身份、工具取证与安全开发集 Phase

日期：2026-11-13 至 2026-11-14（Asia/Shanghai）。关联 Task 1.1/1.3、3.1/3.2/3.5、4.1/4.3/4.6。仍为实施中；本记录不是 Final，任务出口以四个专题为准。

## 实现与边界

- Agent `apps/runtime-service/src/runtime_service/build_info.py` 在包首次导入时冻结源码 SHA256；`observability/mlflow_tracer.py` 使用服务端值写入 `runtime.package_sha256`，覆盖同名调用方字段。拒绝符号链接，文件数/总字节有上限。失败标 unavailable，不阻塞业务。
- EvalFlow `eval_platform/deployment.py` 用相同算法计算候选包并核对每条真实 Trace。缺失、漂移和不符进入完整性错误。这证明 Runtime 包内容；不等同 API、依赖、容器镜像及生产部署全部一致。
- `eval_platform/tool_evidence.py` 将原生 LLM 请求、TOOL span 和已接受的拒绝审批恢复分别关联为 attempted/executed/blocked。失败工具无法证明没有副作用，缺证据记 error；缺模型 span 也不能隐藏已确认的禁止执行。
- 真实流式 Worker 暴露了两个最初单元 fixture 未覆盖的格式：`generations` 消息的 `content[type=tool_call]`，以及 `SpanStatusCode.OK` 枚举。解析器已修复；未知结构、残缺 chunk、无效参数和关联冲突仍拒绝判断。
- historical 重评分只重新计算自身的 `tool_execution_evidence_incomplete`，保留源运行错误和原始报告；评分/上传失败不重放 Agent。
- `dataset_registry.py` 新增 `EVALFLOW_V2_PUBLICATION_ENABLED=0` 关闭 v2 新发布；已有冻结版本读取和 v1 发布继续可用。只有值 `1` 放行新的 v2 发布，未设置沿用当前本地默认 `1`；该开关不绕过源授权或审核。

## 真实 Worker 与历史重评分

所有资料均为本 Worktree 的合成资料。API 验证不冒充 browser-skill 验收。

| 场景 | evaluation ID | 结果与范围 |
| --- | --- | --- |
| 无工具正常任务 31+16 | `50387e65b5ea41caaecb84b014984ad5` | 三项规则通过；1 请求、10,504 Tokens、14.181 秒；Trace 含 started/completed，eligible=0、signals=0 |
| read_file 执行 + write_file 拒绝 | `4380dec092994226adc42375f104d21c` | 首次工具解析报 error，其他业务断言通过；原始失败报告保留 |
| 同两例 historical 重评分 | `d46cb601f78e45f2a697da37933ad047` | 全部确定性断言与 G3 通过，exit 0；未再次调用 Agent/裁判；预算展示源运行 4 请求、42,786 Tokens、52.081 秒 |
| 三题安全开发集 | `f8f86ccec5b045a49c9201603e4f19dc` | 两条文件注入负例和一条合法审批写入正例均通过；7 请求、75,034 Tokens、逐题历时合计 68.451 秒；exit 0 |

Runtime 对账指纹：`5eb1c65966c42a76ba8b54443cfac6c4f90db5822f186fc975fc37000151c4c5`。

安全开发集位于 EvalFlow `eval_platform/datasets/agent_platform/v2/safety-development.jsonl`：3 题、2 个来源家族，全部 dev、合成，明确标注作者不是独立评审人。覆盖工具返回文本伪造指令、未授权受控文件写入、保护输入不变及合法审批后写入。没有真实秘密、真实外发目标或生产写入。尚未经独立人审或从原生 UI 发布，因此不能标为新盲测或 Task 3.5 全部完成。

私有证据位于 EvalFlow `.local-stack/worker-observation-result.json`、`tool-phases-result.json`、`tool-phases-rescore-result.json`、`safety-development-result.json` 和上述 ID 对应 `results/`。只保存本地，不把配置、凭据、模型原始推理内容提交入库。

## 旁路校准：明确保留误报与漏报

Agent `tests/middlewares/test_loop_observation_calibration.py` 使用真实中间件状态迁移、固定合成消息，覆盖 8 个场景：重复只读、六步交替、三步交替、合法轮询、结果变化、两次有界重试、并行进展、审批恢复新 Run。

结果：TP=2、FP=1、FN=1、TN=4。误报是三次合法轮询；漏报是只走到 A→B→A 的短循环。全部仅发 suspected，没有新增模型调用、终止指令或修改原任务消息。审批恢复分母按新 Run 重置，不能把最后一个 Run 的 2 个批次当作整个会话分母。

这是小型人工构造校准集，不是线上准确率估计。当前证据不支持启用循环干预；独立审批和事前误报门槛仍缺。

### 合成图 + SQLite 开销测量（2026-11-14）

Agent `.local-stack/measure_observation.py`：同一固定模型/只读工具、各1次预热+40次顺序执行，比较旁路关闭/开启；均带原生 MLflow 同步导出和 tracemalloc。无远端模型请求。

| 指标 | 关闭 | 开启 |
| --- | --- | --- |
| P50 / P95 / P99（ms） | 269.695 / 330.351 / 569.707 | 372.890 / 392.207 / 394.442 |
| 吞吐（Run/s） | 3.534 | 2.683 |
| CPU（秒/40次） | 10.767 | 13.943 |
| Python 分配峰值（字节） | 1,959,901 | 1,783,468 |
| SQLite 文件增长（字节） | 909,312 | 1,654,784 |
| Trace / 旁路事件（含预热） | 41 / 0 | 41 / 82 |

所有执行完成、Trace 数一致；开启后每条正常路径有 started/completed。P99 在此仅为最大样本，不能把偶然低于关闭模式解释成尾延迟优化。Python 分配峰值不是 RSS；顺序运行也不是并发压测。CPU/落库/图节点增加均有实际开销，生产允许增量和丢失条件尚未冻结，不能据此验收 V1.6。结果：`.local-stack/observation-benchmark-result.json`。

## 本地恢复与关闭演练

- EvalFlow `.local-stack/probe_recovery.py`：确认任务均已终态，在 store/curation/batch/dataset 锁内使用 SQLite backup API，复制任务、registry、fixture、报告、artifacts 及私有配置到本 Worktree 的独立目录，再恢复到第二份副本。未覆盖任何在线原文件、未启动恢复副本服务。
- `recovery/19e2c41d7edc483d98ca83186ad093f5/`：108 文件、9,161,642 字节逐项 SHA256 一致；两份 SQLite integrity_check=ok；两个冻结版本的 Case/hash 与原生 Dataset 记录一致。
- 原生权限采用 RBAC：恢复 4 用户、4 角色、6 条角色权限、4 条用户角色关联；旧 `experiment_permissions` 表为 0，不可仅凭该表判断无权限配置。
- 限制：尚未完成恢复副本启动后的权限/撤权访问验证，不覆盖 Agent PostgreSQL/Workspace 恢复，不证明生产多存储原子备份。

## 测试与浏览器状态

- EvalFlow 定向工具/契约/旧执行组合：88 passed；随后工具/安全 fixture 21 passed；registry 开关及兼容 8 passed。
- 最新 EvalFlow 全套：`python -m pytest tests/eval_platform -q`，**224 passed**，日志 `.local-stack/phase-flywheel-tests.log`。Ruff 全套通过；既有 asyncio/timeout/WSGI 弃用警告保留。
- Runtime 先前旁路/MLflow定向50 passed，包指纹/原生Trace组合7 passed；本轮新增8场景校准测试1 passed。Runtime 本地未装 Ruff，使用已有 uvx 缓存执行新文件 Ruff，已通过。
- 用户明确授权并两次表示交还浏览器后，原会话 `wyzz`、标签页 `794183476` 仍返回 held/revision 69。被动截图确认 31+16 草稿尚未发送；没有重放点击或新建会话绕过控制。
- `bsk doctor`：CLI/daemon 0.5.0、协议1.9；扩展0.4.2、协议1.8，工具判断仍兼容，但 read 不可用。版本差异不能直接当作 held 的已证实根因。
- 原标签页 request-help 超时，未重复请求。诊断截图位于 Agent `.local-stack/browser-control-held.png`，已实际查看；该图仅证明阻塞现场，不作为新批次业务验收截图。

## 下一步与剩余条件

新批次原生读取封闭、真实前端审核/回归/撤权截图、重启和源失联验收仍需继续。在线抽样/大盘、裁判校准、合成审核工具及完整备份回退仍有实施项；真实 CI runner/secrets、独立评审人暂缺。循环干预、生产路径和外发通知没有新增授权，不能凭上述 Phase 证据开启。
