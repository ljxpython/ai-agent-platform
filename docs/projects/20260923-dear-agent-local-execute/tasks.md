# 任务

## Phase 1: 实现

### Task 1.1: 统一执行后端选择
- **改动内容：** 用 `RUNTIME_BACKEND` 控制 Dear Agent、Showcase 和交互终端，并使提示与执行环境一致。
- **代码位置：** `apps/runtime-service/src/runtime_service/workspace/`、`apps/runtime-service/src/runtime_service/services/`
- **预期结果：** local 不调用 Docker，默认正式路径仍调用 Docker。
- **验证项：** Runtime 定向测试 34 passed、4 skipped（Docker 不可用）。
- **状态：** [x] 2026-09-23，见 [实现记录](implementation/01-unified-local-execute.md)。

### Task 1.2: 本地栈配置
- **改动内容：** local-stack 默认设置 `RUNTIME_BACKEND=local`，允许显式 docker 覆盖。
- **代码位置：** `scripts/local-stack.sh`
- **预期结果：** API/Worker 都继承一致的配置。
- **验证项：** 启动脚本定向测试 2 passed；API/Worker 使用同一个 `RUNTIME_BACKEND`。
- **状态：** [x] 2026-09-23，见 [实现记录](implementation/01-unified-local-execute.md)。

## Phase 2: 验证

### Task 2.1: 完成验证与记录
- **改动内容：** 执行单元、集成和本地执行链路测试，记录真实结果。
- **代码位置：** `verification.md`
- **预期结果：** 本地 execute 可运行且 Docker 模式不被误改。
- **验证项：** 见 `verification.md`；本地链路通过，Docker 实跑及浏览器手工验收待执行。
- **状态：** [x] 2026-09-23，Final 判定为 partial。
