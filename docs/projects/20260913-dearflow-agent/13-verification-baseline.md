# 重新盘点的验证基线与验收计划

## 目标

让“已有代码、已有历史测试、今天已验证、生产可交付”各有证据。关联 [11能力表](11-20260928-capability-reassessment.md)、[12接续任务](12-completion-plan.md)、[14机制与效果](14-effect-parity-and-reliability.md)。本轮运行了离线受控模型故障注入，没有运行真实供应商、浏览器全链路、迁移、生产发布或真实服务破坏实验。

## 方案设计：验收口径

每个K/A验收保存：平台/参考版本与关键文件摘要、执行配置（无密钥）、输入与期望、tenant/project/thread/run/request/trace关联、工具事实、产物hash及内容断言、页面结果、负例、实际命令/退出码、跳过原因。使用合成数据和隔离项目；涉及清理/数据库/停止服务的实验需在获批隔离环境执行，不碰现役业务数据。

**done**须满足该任务所有必需门禁；**partial**是部分实现/验证；**blocked**必须说明真实外部条件与尝试；**deferred**是明确延期。历史blocked不自动证明当前阻塞；未运行写未执行，不写通过。只在本期选择的范围全部验收后判定整体done，排除项须在交付说明明列。

### 验证矩阵

| ID / 关联任务 | 单元或确定性组合 | 服务集成/真实环境 | Dear浏览器验收与否决条件 |
|---|---|---|---|
| V01 / T01,T02 | schema无I/O、配置哈希、模式工具集 | 正确graph/assistant、真实Run/SSE与审计追踪 | 四模式可选且实际行为一致；假显示思考关闭而模型未支持不得宣称完全支持 |
| V02 / T02 | 七字段回答校验、混批guard、审批edit/reject | interrupt持久化、重启resume、撤权/重复回答 | 追问→回答→执行；刷新无僵尸审批；resume不覆盖原Context |
| V03 / T02 | 消息幂等、scope、不把ACK当消费 | 现役消息内部read委托、当前worker入队消费 | 执行中追加要求确实被后续模型采用；重连不重复提交 |
| V04 / T02 | 双子任务namespace隔离、父取消 | post37 state/checkpoint、子历史工具输入输出 | Dear内展开旧子任务，来源准确；不宣称单子任务取消；未知usage不可写0 |
| V05 / T04 | 每K固定数据内容断言、26图型schema、图片/PPTX校验 | K01—13逐项模型/供应商；K03配额、K05限流、K09双轴、K12多图单列 | 来源可打开，产物真实下载/预览/字节一致；UI测试与后端测试需对应同场景 |
| V06 / T05 | Skill ZIP边界、CAS、快照摘要、只读资源 | 上传/更新/启停/删除、准确commit导入、进程恢复 | 无Thread管理；409不丢草稿；旧Run恢复原版本、新Run读新内容；不恢复已取消发布流程 |
| V07 / T05 | candidate分类/quote/ID、epoch、队列作者、记忆降级 | PG CAS；真实Run提取→采纳→新会话召回；执行中分享 | 本人项目有效、他人/跨项目/共享不可读；删除后晚到提取不复活；浏览器记忆CRUD与导入导出 |
| V08 / T06 | 外部任务幂等/unknown、包digest、媒体头/大小 | 真实供应商、ACK丢失、重复通知、重启对账、Range206/416 | 视频/音频可播放拖动/下载；部署仅批准文件；unknown不得换key重购或伪称取消远端 |
| V09 / T03,T07 | 下调预算、graph重建、伪造完成、失败工具、空/截断响应、摘要后要求 | 长上下文、真实token用量、worker超时后恢复 | 不丢用户约束、来源与未完成项；不存在的产物/未运行测试不能报成功 |
| V10 / T08 | 显式Skill不存在/停用、schema可见与执行权限一致 | MCP可用/断连/重名/撤权、目录tokens比较 | 选中/实际使用/历史快照分明；无密钥回显；只有测出目录成本才加延迟检索 |
| V11 / T10 | scope/SSRF/路径/包/脱敏负例 | 两用户×两项目；Docker网络/CPU/内存/PID/磁盘、取消后资源回收；容量记录 | 无跨项目文件/Skills/记忆泄露；生产隔离不能由LocalShell成功替代；容量SLO评审后冻结 |
| V12 / T10 | 老线程/当前快照可读、开关关闭行为 | 备份恢复到隔离库、worker/DB故障、镜像回退与schema兼容 | 关闭新增能力不破坏通用Chat，恢复产物可读；数据库迁移不可逆时采用批准的恢复方案 |

媒体实现前必须固定支持格式、上传/下载上限和Range语义；性能先测当前基线，不临时编造QPS/延迟达标阈值。上游PII/注入防护不只按关键词做正例，要验证不会将真实用户内容误删，也不改变平台授权含义。

### 复用的测试入口

从 `apps/runtime-service` 执行（使用该服务独立虚拟环境；文档命令不含RTK前缀）：

```bash
.venv/bin/python -m pytest \
  "tests/services/dearflow_agent/test_agent.py" \
  "tests/services/dearflow_agent/test_modes.py" \
  "tests/services/dearflow_agent/test_context.py" \
  "tests/services/dearflow_agent/test_subagents.py" \
  "tests/services/dearflow_agent/test_limits_config.py" -q
```

其他已存在入口按切片运行：`test_research.py`、`test_p5_media.py`、`test_memory_contract.py`、`test_memory_access.py`、`test_p6_governance.py`、`test_skill_restart.py`、`test_mcp_tools.py`、`test_files.py`、`test_execution.py`。部分需要隔离PG/Docker或显式开关，先读用例前置，不把skip计入成功。

真实模型技能用例（后续在隔离环境、供应商预算及测试数据准备好后执行）：

```bash
DEAR_SKILL_E2E=1 .venv/bin/python -m pytest \
  "tests/e2e/test_dearflow_skills.py" -m e2e -k K03 -v
```

该入口使用当前 `test_platform.py`，会创建测试资源并调用真实服务，不是浏览器E2E；必须审查清理逻辑和实际测试环境再运行。K22目前未参数化，需新增批准后的静态部署场景。K14—16/K23若纳入，另补正式场景，不能只复制Skill然后加参数名。

Platform侧复用 `apps/platform-api/tests/test_runtime_gateway_{skills,memory,memory_contract,files,images,workspace}.py`、`test_runtime_thread_authorization.py`、`test_tool_restrictions.py`、`test_runtime_delegation_contract.py` 以及相关SDK adapter测试。花括号是文件组说明，执行时列出实际路径。

Web侧复用 `apps/platform-web/src/modules/dear-agent/pages/*.spec.ts`、`src/services/dear-agent/*.spec.ts`、Chat会话/审批/子任务测试；在 `apps/platform-web/e2e/` **新增拟定** `dear-agent-capabilities.spec.ts`，参考 `support/platform.ts`，必须真实登录→Dear入口→Run→工具/审批→产物/恢复。现有通用E2E可以复用基础步骤，但不能把mock render fixture当真实模型完整链路。

## 任务拆分

- [x] 记录本轮静态审视与核心确定性抽测。
- [x] 定义V01—V12以及逐Skill验收规则。
- [ ] 按T01冻结部署态和隔离验证条件。
- [ ] 按T02—T08实际执行各Phase测试并保存证据。
- [ ] T10执行Final联合回归；Final区块保持独立。

## 验证要求与记录

### Phase：2026-09-28盘点与核心抽测

实际执行了上方五文件pytest命令，退出码0：**28 passed, 1 skipped, 13 warnings in 30.92s**。

- 通过覆盖：文件审批/拒绝/编辑、受保护路径、schema探测、模式签名/工具拒绝、连续澄清、撤权恢复、摘要后记忆来源/队列回执/历史保存、预算跨graph重建、父取消和并行子上下文隔离。
- 跳过：`test_live_subagent_trace` 缺 `DEAR_SUBAGENT_TRACE_THREAD`；不能据此证明本轮真实Langfuse追踪通过。
- 警告：PyMuPDF SWIG弃用、Pydantic RuntimeContext序列化类型告警、LangGraph v3实验协议提示；未修，列后续定位，不包装成零告警。
- 限额测试只证明helper与默认值；本轮静态确认 `max(mode.limit, env_limit)`，未改变预算策略，T03需组合根低上限断言。
- 本轮未执行全量pytest/lint/typecheck/浏览器/供应商/生产测试；只修改规划文档，抽测用于识别现有基线，不是功能完成证明。
- 官方资料已查询langchain-docs与langchain-reference：`create_deep_agent`、内置摘要/外置、Skills及SubAgent继承。线上文档可能领先锁版本，实施以0.7.8实际行为和测试为准，不直接套最新版签名。
- 文档检查：`python3 "scripts/check_docs.py"`退出码0，`Documentation checks passed.`；`git diff --check`退出码0。一次性定向校验3份新文档的本地链接、显式本仓库路径、尾随空白、连续38个A/23个K/10个T编号全部通过；实盘目录对照为上游23、迁入19，差集恰为podcast/music/video/claude-to-deerflow。未新增检查框架。

资料入口：[DeepAgents定制](https://docs.langchain.com/oss/python/deepagents/customization)、[上下文工程](https://docs.langchain.com/oss/python/deepagents/context-engineering)、[create_deep_agent参考](https://reference.langchain.com/python/deepagents/graph/create_deep_agent)。

### Phase：2026-09-28 机制与效果复核

- 真实Dear组合根离线探针7个场景全部命中缺口断言，exit0：length/content_filter调用经审批后执行、工具后空回答、失败读取后声称成功、6次同调用无短路、env限1仍3次模型调用、Todo未完成仍声称完成。命令、源码与逐项边界见14/E01—E07。
- 此脚本是现状特征实验，绿色表示复现缺口，不能算验收通过。未调用真实模型/供应商、未绕过审批、未修改业务代码。
- 参考5文件测试实际104 passed in 7.19s，exit0；使用受控模型，子执行器在conftest中有mock，不能宣称完整业务链路通过；也不能与本地28项数量直接比较。
- 当前RuntimeConfig历史工具消息清理、官方PatchToolCalls/摘要/输出外置确实存在；它们不能自动替代finish_reason保护、结果验收或停滞检测。
- 新探针出现vercel-deploy名称/目录不一致告警，T05接续。供应商兼容、大输出原文、摘要业务连续性与真实质量A/B仍未验证。
- T03/T07优先级已调整；同条件故障配对、真实模型多次盲评与产品链路验收按14执行。此前“未做故障注入”的描述仅适用于前一核心抽测阶段。
- 文档检查与`git diff --check`通过；诊断脚本Ruff check/format check通过。Runtime虚拟环境未安装Ruff，使用参考项目已有Ruff可执行文件在当前仓库检查，未安装/更新依赖。文档检查首次发现本地绝对路径，改为相对参考根后通过。

### Final：整体迁移验收

**未执行。** 原专项07/10及后续记忆/Skills/SSE/JWT/业务边界仍有未验项。历史阶段记录不得复制到此区当作当前版本Final。全部纳入范围及V01—V12通过后再记录结论，未达到done不将JWT/SSE草案改active。

## 状态

本轮规划验证完成；业务验收partial（仅有部分当前抽测和历史证据）。下一步先评审12的范围与预算/权限语义，再按任务收尾。
