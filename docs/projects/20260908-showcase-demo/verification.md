# Showcase Demo 验证

## 状态

`runtime-service: done`，`项目整体: partial`。本轮教学 Demo 后端验收完成，包含真实模型完整修复、审批暂停时 API/Worker 重启恢复、多个独立 interrupt；前端联调仍单独待验收，不代表生产切流或容量验收完成。

## 审查基线（2026-09-09）

- 执行 apps/runtime-service/.venv/bin/python -m pytest tests/demo/test_showcase_demo.py -q -p no:cacheprovider：9 passed。
- 补充本地检查确认：空工具 allowlist 仍执行；Context 哈希不匹配仍运行；write_todos 后无 todos；checkpoint skills_metadata=[]。
- 使用项目非敏感 pyproject.toml 验证 fetch_documentation 可通过 file:// 读取宿主机文件。
- execute_command 接收 exit 7 仍返回退出码 0。
- 上述结果证明旧测试没有覆盖相应行为。

## 本轮验收项

1. 合法身份可运行，缺身份、错误 Context、错误 scope、禁用工具均拒绝。
2. 真实 Todo 状态出现在 values，支持 pending/in_progress/completed。
3. Skills 可发现、可读取、写入被拒绝；安装后的包包含资源。
4. 文件工具读写结果一致，线程不能访问其他线程目录。
5. approve/reject/edit 验证真实副作用；批量动作和子 Agent interrupt 能恢复。
6. 实际调用子 Agent，返回非空 namespace 的事件。
7. Docker 执行返回真实输出/退出码，超时和依赖缺失不假成功。
8. 文档抓取拒绝 file://、非允许站点和重定向，限制读取量。
9. schema/state 探测不请求模型 catalog、不启动容器。
10. 真实远程持久化和前端链路独立记录，不用本地组合测试替代。

## 执行记录

2026-09-09，执行人：Codex。以下命令在 `apps/runtime-service` 执行。

```bash
.venv/bin/python -m pytest tests/services/showcase_demo tests/middlewares tests/runtime tests/test_r0_baseline.py tests/services/test_r4_capability_demos.py -q -m "not e2e" -p no:cacheprovider --tb=short
```

结果：**151 passed, 1 deselected，85.67 秒**。包含实际 Docker 执行，非只检查图节点：
- Todo 状态与 Skills metadata/读取内容；Skills 写保护。
- approve/reject/edit 对真实文件的作用、批量 decisions 数量校验、子 Agent interrupt 经父 Run 恢复。
- research 实际产生非空 namespace 事件，工具集不能写入。
- 空工具清单、错误 Context、跨租户工作区复用及审批 edit 偷换未授权工具被拒绝。
- 真实 Graph 审批修改 → 审批执行 → Docker 输出 43.50 和产物。
- Docker 真实非零退出、超时、只读根、输出上限、缺镜像失败；工作区初始化不覆盖用户文件。
- 文档抓取的协议/站点/响应边界及模型连接校验。

```bash
RUNTIME_SHOWCASE_LIVE_TEST=1 .venv/bin/python -m pytest tests/services/showcase_demo/test_agent.py -k live_model -q -p no:cacheprovider --tb=short
```

结果：**1 passed, 13 deselected，24.15 秒**。真实模型读取项目与 Skills，流式分析给出正确金额；这是进程内真实模型检查，不是远程 Agent Server 或浏览器端到端验收。

```bash
uvx ruff check src/runtime_service/services/demo/showcase_demo src/runtime_service/middlewares/runtime_config.py src/runtime_service/runtime/modeling.py tests/services/showcase_demo
uvx ruff format --check src/runtime_service/services/demo/showcase_demo tests/services/showcase_demo
```

结果：lint 通过，Demo 和测试的 13 个文件格式通过。扩大格式检查发现两个公共模块存在格式差异；未整体重排混有已有改动的公共文件，不宣称全应用 format 通过。

### 安装包验证

先将当前 `src`（排除缓存与 egg-info）、`pyproject.toml`、应用 README 复制到干净临时目录，执行：

```bash
uv build --wheel --out-dir /tmp/showcase-teaching-wheel-20260909
uv pip install --python <应用虚拟环境的 Python> --no-deps --target /tmp/showcase-installed-20260909 /tmp/showcase-teaching-wheel-20260909/langgraph_open_teach-0.1.2-py3-none-any.whl
```

结果：构建与安装成功。在 `/tmp` 运行应用 Python，将安装目标置于 sys.path 首位；断言 runtime_service 实际来自安装目标、README/Skills/report.py/sales.csv 可读，`get_agent({})` 的输入输出 schema 可取得，未创建 `.runtime/showcase`。检查通过。
原应用 `build/lib` 有旧残留，首次直接构建的包不能作干净证据；未清理用户构建目录，以上证据采用临时干净构建。

## 完成度与未覆盖边界

| 范围 | 状态 | 证据或缺口 |
| --- | --- | --- |
| 官方工具、Todo、Skills、子 Agent、HITL、授权契约 | done | 上述行为测试及公共模块回归 |
| 本地线程文件与真实 Docker 执行 | done | 真实 Graph 审批执行、产物、退出码和隔离检查 |
| 可移植包资源与探测 | done | 干净 wheel 安装后验证 |
| 真实模型 | done | 已通过真实服务修复 → 审批 → 执行与独立产物复核；见 2026-09-10 记录 |
| 远程持久化、重启恢复 | done | 正式鉴权、PostgreSQL/Redis，审批暂停期间重启独立 API/Worker 后恢复 |
| 多个独立 interrupt ID 同时恢复 | done | 实际并行子 Agent 产生两个 ID，批准一个、拒绝一个并验证文件副作用 |
| 完整平台 UI、子 Agent token、三栏 Sandbox、推理 token | deferred | 按用户先聚焦 runtime-service 的范围，留后续前端联调验收 |
| 项目整体 | partial | 后端教学范围 done，完整前端链路仍待后续验收 |

工作区独立于 checkpoint，文件副作用不承诺 exactly-once 或回滚。Run 取消不保证立即停止官方线程适配中的 Docker 命令，命令仍受 60 秒上限；多副本/容器化执行需要部署者配置共享目录及 Docker 可见的挂载路径。未验证生产预演、全仓库回归或性能容量。

## 2026-09-10 提交前复核

用户授权提交并推送本轮后端与文档。将暂存内容通过 `git checkout-index` 导出到独立临时目录，使用该目录的 `src` 和已有虚拟环境运行上述非 e2e 回归命令：**150 passed, 1 deselected，151.57 秒**。本次未纳入工作区中其他模型解析修改及其测试，因此与上轮工作区的 151 项计数不同。暂存内容 `git diff --cached --check` 通过；远程和前端验收状态不变。

## 2026-09-10 后端验收与配套发布

### 发现并修复的依赖缺陷

真实 Agent Server 首次执行被 `runtime.auth.context_hash_mismatch` 拒绝。原因是 GraphHarbor `post20` Worker 把 Context 放入 config，却未通过官方 `context=` 参数传给 LangGraph。修复位于框架执行适配层，Demo 的鉴权不变。

继续验收发现状态接口直接读取底层 checkpoint，丢失增量存储的 messages；改用官方 `aget_state/aget_state_history`，同时由 Worker 记录实际执行的 graph ID，普通创建的 Thread 也可还原状态。当前状态、历史 checkpoint、待执行节点、interrupt 均有回归覆盖。

### 确定性和框架回归

- 新增 `test_parallel_subagent_interrupts_resume_by_id`：两个实际子 Agent 同时中断，反向组装 ID 映射，一项批准、一项拒绝，验证真实文件副作用；1 passed。
- GraphHarbor Context 普通/流式执行及恢复：9 项定向检查通过。
- GraphHarbor 增量 State/历史/审批还原：新增实际 Graph 测试通过。
- 隔离发布源码完整 `pytest libs -q -p no:cacheprovider --tb=short -o timeout=60`：**145 passed, 15 skipped，217.71 秒**。跳过项依赖未准备的上游对照服务/fixture，不计作通过。
- 完整回归首轮因隔离目录缺少 acceptance 依赖/比较脚本，以及一次 5 秒 lifespan 启动超时失败；补齐后相关 27 项与完整回归均通过，没有修改产品超时掩盖失败。
- 框架 `uv lock --check`、版本脚本、Ruff lint/format、mypy（36 个源文件）、两个 wheel 与 sdist 构建通过。
- runtime-service 从 PyPI 安装 `post21` 后执行本文件前述非 e2e 回归命令：**152 passed, 1 deselected，203.98 秒**。包含 Docker 和新增并行审批测试；工作区保留其他已有模型测试，计数不等于上一提交的独立快照。
- Demo、验收脚本及测试定向 lint/format 通过；两个仓库 `git diff --check` 通过。

### 真实模型、持久化与重启

运行 `scripts/showcase_acceptance.py`，API/Worker 使用实际发布 wheel、正式 JWT 认证、独立 PostgreSQL/Redis 和真实模型。脚本驱动审批仅用于隔离验收，正式服务没有自动批准开关。

1. 创建普通 Thread，让模型自行读取并修复 CSV 报表，生成回归检查。
2. 修改审批暂停时，停止 API 和 Worker，再启动新进程；断言完整 messages 与原 interrupt ID 保持一致。
3. 按 ID 批准后继续执行；验证最终没有待执行节点或审批。
4. 独立在 Docker 内执行模型生成的检查和报表，验证 `result.txt`。

最终 wheel 验证：**通过**。Thread `061d5e0e-53d8-4b15-9618-f39eae2e3440`，7 个 Run 最终以 success 完成，独立执行 **3 项检查通过，报表 43.50，退出码 0**。见 [结构化证据](evidence/20260910-post21-wheel.json)。审批轮数由真实模型行为决定，不固定为演示脚本的步骤数。

### 包发布及安装

- `graphharbor-runtime==0.13.0.post21` 与 `graphharbor==0.13.0.post21` 已按顺序发布到 PyPI；用户明确提供并授权使用本地发布凭据，凭据未进入代码或记录。
- 发布以 PyPI post20 源码包为基线，只加入本轮执行/状态/graph 关联修复及测试。其他未提交框架架构修改未纳入。
- 首次上传前本地校验发现继承的 PKG-INFO 重复；清除临时构建目录内旧元数据后重建，两个 wheel 哈希不变。修正后四个文件才成功上传，未覆盖已发布文件。
- PyPI 四份产物哈希与本地一致，见 [SHA-256](evidence/20260910-post21-sha256.json)。runtime-service 的 pyproject.toml/uv.lock 已更新，并通过 `uv sync --frozen` 从索引安装；后续刷新锁文件补齐索引刚发布时尚未缓存的 runtime wheel。
- 独立 worker 需有 Docker CLI、预拉取镜像和持久化工作区。现有运行中的业务服务没有被本次验收重启；采用新依赖的部署应正常更新 API 与 Worker。

本轮不覆盖前端验收、生产切流、容量压测，或 shell 副作用 exactly-once/回滚。Run 取消仍不保证正在执行的 Docker 命令立即停止，保留已文档化的 60 秒命令上限。

### 发布后最终复验

清除临时框架覆盖路径，使用 runtime-service `.venv` 中从 PyPI 安装的 post21，再运行同一真实验收脚本：**通过**。Thread `bf964ad4-bc31-4097-8c9b-33d9d9989d5a`，最终 Run `738809aa-6d08-4909-89f7-e8114dba765e` 为 success；API/Worker 重启后原 interrupt ID 和完整 messages 一致，独立运行模型生成的检查及报表均成功，输出 **43.50、退出码 0**。见 [索引安装版本证据](evidence/20260910-post21-published.json)。

验证脚本已停止自己启动的 API/Worker；本轮专用 PostgreSQL/Redis 容器停止，数据与本地证据保留，原有业务服务不受影响。后端教学范围验收完成；前端、生产切流与容量验收保持独立状态。
