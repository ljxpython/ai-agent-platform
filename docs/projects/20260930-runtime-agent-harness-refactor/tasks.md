# Runtime Agent 组合根脚手架重构与 DX 体验治理 - 任务拆分

## Phase 1: 框架脚手架研发 (Harness Infrastructure)

### Task 1.1: 实现 `AgentBuildContext` 与核心解包逻辑
- **改动内容：** 抽取 Delegation 验签、指纹比对、模型与工作区初始化逻辑。
- **代码位置：** `apps/runtime-service/src/runtime_service/framework/harness.py` → `AgentBuildContext`, `extract_and_verify_facts()`
- **预期结果：** 具备纯粹的构建期上下文容器与标准安全抽取流程。
- **验证项：** 编写独立单元测试覆盖合法 Token、篡改 Token、指纹不匹配等分支。
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 1.2: 实现高阶包装器 `@runtime_agent`
- **改动内容：** 封装 LangGraph 探针模式与真实运行模式的装配分支。
- **代码位置：** `apps/runtime-service/src/runtime_service/framework/harness.py` → `runtime_agent()`
- **预期结果：** 支持装饰任意标准业务构建函数并输出标准 `Pregel` 入口。
- **验证项：** 编写测试用例验证元数据探测（`is_probe=True`）与正式执行模式。
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 1.3: 实现通用单测脚手架 `create_test_config()`
- **改动内容：** 提供开箱即用的测试用例配置生成器与 Mock 注入辅助类。
- **代码位置：** `apps/runtime-service/src/runtime_service/framework/testing.py` → `create_test_config()`
- **预期结果：** 测试人员可使用 1 行代码生成合法配置并注入 `FakeModel`。
- **验证项：** 替换部分测试文件验证可用性。
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

---

## Phase 2: 参考服务平滑迁移 (Reference Migration)

### Task 2.1: 迁移 `reference_agent`
- **改动内容：** 将参考实现迁移至 `@runtime_agent`，精简旧有的样板逻辑。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py`
- **预期结果：** 代码量减少 50%，逻辑清晰度显著提升。
- **验证项：** `pytest apps/runtime-service/tests/services/reference_agent/` 全部通过。
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 2.2: 迁移 `workflow_demo`
- **改动内容：** 将工作流演示智能体迁移至新 Harness。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py`
- **预期结果：** 消除私有的模型引用解析代码。
- **验证项：** `pytest apps/runtime-service/tests/services/workflow_demo/` 全部通过。
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

---

## Phase 3: 核心旗舰改造与全量回归 (DearFlow Migration & Verification)

### Task 3.1: 迁移旗舰 `dearflow_agent`
- **改动内容：** 将 `dearflow_agent` 改造为使用 `@runtime_agent`，剥离前 150 行胶水代码。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
- **预期结果：** 单文件代码量从 429 行精简至 150 行以内，保留全部中间件与多模态能力。
- **验证项：** 跑通 `tests/services/dearflow_agent/test_agent.py` 与 `test_execution.py`。
- **预计：** 1.5 天
- **状态：** `[ ]` 待开始

### Task 3.2: Final 全量回归与基线对齐
- **改动内容：** 运行 `runtime-service` 全量单元测试、集成测试与契约回归。
- **代码位置：** `apps/runtime-service/tests/`
- **预期结果：** 所有现有测试 100% 通过，无回归缺陷。
- **验证项：** `pytest apps/runtime-service/tests/`
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

---

## 进度追踪
- [ ] Phase 1 框架脚手架研发
- [ ] Phase 2 参考服务平滑迁移
- [ ] Phase 3 核心旗舰改造与全量回归
