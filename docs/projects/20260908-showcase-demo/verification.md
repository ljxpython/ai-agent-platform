# Showcase Demo 验证

## 状态

`partial`。后端核心能力已有组合、Docker 和真实模型证据；远程持久化及完整 UI 链路尚未验收，不沿用旧版“全部完成”。

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
| 真实模型 | partial | 只读流式分析通过；未覆盖真实模型自主完成全部审批修复链路 |
| 远程持久化、重启恢复 | partial | 未取得本轮真实 Agent Server 部署证据 |
| 多个独立 interrupt ID 同时恢复 | partial | 已测单 payload 多动作及单个子 Agent interrupt，未测同时多个独立 interrupt |
| 完整平台 UI、子 Agent token、三栏 Sandbox、推理 token | deferred | 按用户先聚焦 runtime-service 的范围，留后续前端联调验收 |
| 项目整体 | partial | 不把本地后端通过等同全项目完成 |

工作区独立于 checkpoint，文件副作用不承诺 exactly-once 或回滚。Run 取消不保证立即停止官方线程适配中的 Docker 命令，命令仍受 60 秒上限；多副本/容器化执行需要部署者配置共享目录及 Docker 可见的挂载路径。未验证生产预演、全仓库回归或性能容量。

## 2026-09-10 提交前复核

用户授权提交并推送本轮后端与文档。将暂存内容通过 `git checkout-index` 导出到独立临时目录，使用该目录的 `src` 和已有虚拟环境运行上述非 e2e 回归命令：**150 passed, 1 deselected，151.57 秒**。本次未纳入工作区中其他模型解析修改及其测试，因此与上轮工作区的 151 项计数不同。暂存内容 `git diff --cached --check` 通过；远程和前端验收状态不变。
