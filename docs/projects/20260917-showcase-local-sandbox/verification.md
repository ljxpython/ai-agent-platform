# Showcase Demo 本地执行模式 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] DockerWorkspaceBackend 现有隔离测试继续通过
- [x] LocalShellBackend 工作区初始化、环境变量和退出码测试
- [x] 后端选择默认值、local、docker、非法值测试

### 集成测试
- [x] 本地模式执行脚本 → 读取产物；审批拒绝时不执行
- [ ] Docker 模式原有真实执行回归

### 端到端测试
- [ ] `scripts/local-stack.sh` 显式切换 local/docker 后 Runtime 健康检查和 Showcase 执行

## 验证记录

## 2026-09-17 验证

**执行人：** Codex

### 单元测试

- ✅ `uv run --frozen pytest tests/services/showcase_demo -m "not integration and not e2e" -q`：59 passed，5 deselected
- ✅ `python3 -m unittest discover -s scripts -p test_local_stack_backend.py -v`：1 passed（5 种配置组合）；隔离临时目录中验证默认 local、显式 docker、环境优先级、非法值拒绝、API/Worker 子进程环境，无服务启动副作用
- ✅ Python compileall、`scripts/local-stack.sh` bash 语法检查、`git diff --check` 通过
- ✅ `uvx ruff check src/runtime_service/services/demo/showcase_demo tests/services/showcase_demo/test_backend.py tests/services/showcase_demo/test_agent.py ../../scripts/test_local_stack_backend.py`；使用临时工具环境，无项目依赖变更

### 集成测试

- ✅ LocalShellBackend 真实执行 `report.py`，退出码、产物、超时和凭据不继承通过
- ✅ 确定性模型驱动实际 Graph/HITL/LocalShellBackend：审批前无产物；approve 后报表 27.00；reject 后无产物
- ⚠️ `uv run --frozen pytest tests/services/showcase_demo/test_backend.py -m integration -q -rs`：1 skipped，7 deselected，明确原因 `Docker daemon is unavailable`

### 端到端测试

- ⚠️ 未启动完整 local-stack；需要本地 PostgreSQL、Redis、模型配置和服务联调环境

### 最终结论

⚠️ `partial`：实现、本地模式回归、脚本行为测试与 lint 通过；Docker 集成和完整栈 E2E 待验。编译检查不等同于静态类型检查，本轮未执行独立类型检查器。
