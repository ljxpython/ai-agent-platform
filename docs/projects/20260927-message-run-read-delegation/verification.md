# 消息内部 Run 回查委托修复验证

## 计划

- API：消息操作仅携带请求内已有的 `read` 委托，普通操作无额外头；两 token 的主体/项目/凭据一致。
- Runtime：合法配对通过自定义入口并由原生 Run GET 按现有 ACL 判断；缺头、过期、错主体/项目/凭据/Thread在业务查询前拒绝；消息 token 直接访问原生 Run 仍403。
- 集成：真实 PostgreSQL 消息队列与 Runtime HTTP 入口，验证入队202、待处理列表与终态对账；拒绝场景无新增队列行。
- 端到端：Platform API → Runtime消息入口 → GraphHarbor原生Run回查至少一条；没有现役部署条件时标“未验证”，不以mock代替。
- 质量：相关pytest、Ruff致命规则及新增代码完整检查、文档检查和本项目范围 `git diff --check`。

## Phase 验证记录

### M1 配对委托测试（2026-09-27）

- API：`uv run --no-sync pytest tests/test_runtime_delegation.py -q`，21 passed、106 subtests，退出码0。
- Runtime：`uv run --no-sync pytest tests/runtime/test_platform_auth.py tests/runtime/test_message_read_delegation.py -q`，42 passed，退出码0。原生授权白名单对`message-enqueue`和`message-read`仍返回403。
- PostgreSQL HTTP：`uv run --no-sync pytest tests/services/test_message_inbox_postgres.py -q -k receipt_http_reconciles_before_terminal_close`，1 passed、22 deselected，退出码0；错误配对时无内部GET、无入队。
- 结论：通过。测试使用真实v2签名与真实PostgreSQL；内部原生GET响应受控，不代表真实跨服务链路。

### M2 平台转发与Runtime校验（2026-09-27）

- API网关组合：`uv run --no-sync python -m pytest tests/test_runtime_gateway_http_matrix.py tests/test_runtime_gateway_memory_contract.py tests/test_runtime_delegation.py -q`，31 passed、395 subtests，退出码0。
- Runtime配对：`uv run --no-sync pytest tests/runtime/test_message_read_delegation.py -q`，9 passed，退出码0；包含平台实际未绑定Thread的read委托。
- `uvx --offline ruff check`对本次相关API/Runtime文件的`E4,E7,E9,F`通过；新增Runtime测试文件格式检查通过。`webapp.py`完整格式检查仍报既有行格式差异，未做无关格式化。
- 结论：通过。首轮直接`rtk pytest`与环境内`ruff`不可用，改用现有`uv`项目环境及离线`uvx`；API组合首轮直接`pytest`有`tests`包导入错误，改用`python -m pytest`后通过。

### M3 链路与交接（2026-09-27）

- API全量首轮：299 passed、15 skipped，但`test_runtime_delegation_contract.py`有2个消息子用例失败。原因是旧夹具仍只向新Runtime消息入口传消息token；补配对read委托后，契约定向26 passed、152 subtests，API全量重跑299 passed、15 skipped、606 subtests passed，退出码0。
- Runtime授权目录全量：109 passed，退出码0；PostgreSQL消息队列全套：22 passed、1 skipped，退出码0；最终改动后消息HTTP定向重跑1 passed，错误配对无内部GET/入队且响应不回显内部头值。
- SSE内部头脱敏定向：8 passed；相关Python编译、Ruff致命规则、本项目范围`git diff --check`及`python3 scripts/check_docs.py`通过。Ruff完整格式检查`webapp.py`仍有既有基线差异；未整理无关行。
- 真实Platform API→Runtime消息入口→GraphHarbor原生Run回查：**未验证**。当前现役进程并未按本轮授权部署新API与新Runtime；本机PostgreSQL HTTP测试的原生Run响应受控，不能代替该链路。
- 结论：M3的代码、自动化验证和交接记录已完成；现役链路验收仍缺部署条件。

## Final 验证记录

### 2026-09-27 Final

**完成度：`partial`。** 状态核对：README为“部分完成”，tasks.md的M1—M3均为`[x]`且M3卡片注明部分验证，Phase对应M1—M3三条，plan与CONTEXT均标现役链路未验证。

**单元与契约：** API全量299 passed、15 skipped、606 subtests passed；Runtime授权目录109 passed；跨进程双端契约定向26 passed、152 subtests。消息委托仍被原生白名单403拒绝，配对read委托通过身份/租户/项目/凭据/Thread校验；缺失、过期和错配拒绝。

**集成：** 真实PostgreSQL消息队列全套22 passed、1 skipped；HTTP正例完成入队202、列表、终态对账，内部GET收到read委托。拒绝用例没有内部GET、没有新队列行、响应没有委托原文。该测试对原生Run GET使用受控响应。

**端到端：** 现役Platform API→Runtime→GraphHarbor真实消息链路**未验证**。本轮未获部署授权，现役进程不代表本次源码；不能以受控响应或跨进程鉴权夹具标记通过。需要在后续部署新API与新Runtime后，用真实运行中Run执行消息入队、待处理列表和Thread ACL撤权拒绝验收。

**质量与边界：** 新增测试格式、相关文件Ruff `E4,E7,E9,F`、Python编译、文档检查及范围diff检查通过；`webapp.py`完整格式仍受既有基线影响。GraphHarbor、JWT v2、原生授权白名单、Thread ACL、数据库结构均未改；未执行迁移、部署、Git提交或分支操作。无独立性能目标；本轮无部署变更，回滚演练不适用。

**结论：** 代码与本机验证已完成，现役真实链路因部署另行安排而未验证；项目保持部分完成，不宣称403在现役环境已消除。
