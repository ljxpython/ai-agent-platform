# Runtime Agent 组合根脚手架重构与 DX 体验治理 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `test_harness_security_rejections()` - 验证非法 Token、篡改指纹与违规 Configurable 的拦截能力
- [ ] `test_harness_probe_mode()` - 验证目录扫描探测模式下的低资源虚假模型返回
- [ ] `test_harness_execution_mode()` - 验证正式执行模式下的真实模型与工作区初始化
- [ ] `test_create_test_config()` - 验证单测辅助工厂生成的配置是否具备合法数学签名

### 集成测试
- [ ] **场景 1：ReferenceAgent 最小闭环迁移验证**
  - 步骤：运行 `pytest apps/runtime-service/tests/services/reference_agent/`
  - 预期：完全兼容既有的单测与 Mock 模型注入

- [ ] **场景 2：WorkflowDemo 复杂工作流迁移验证**
  - 步骤：运行 `pytest apps/runtime-service/tests/services/workflow_demo/`
  - 预期：工作流分支与状态机保持严格一致

### 端到端测试
- [ ] **链路 1：DearFlowAgent 审批与文件写入回归**
  - 操作：运行 `pytest apps/runtime-service/tests/services/dearflow_agent/test_agent.py`
  - 验证点：`approve`, `edit`, `reject` 决策对沙箱文件的物理写入与中途拦截能力完好

- [ ] **链路 2：DearFlowAgent 动态技能与记忆中间件回归**
  - 操作：运行 `pytest apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py`
  - 验证点：租户级动态技能挂载与记忆隔离正常生效

### 性能与代码量指标
- [ ] **代码精简度**：`dearflow_agent/agent.py` 代码行数由 429 行降至 150 行以内（下降 > 60%）
- [ ] **构图初始化耗时**：`get_agent()` 耗时不得高于重构前基线（< 2ms）

---

## 验证记录

### 2026-09-30 初始规划登记
**执行人：** @laowang

- **当前状态：** 项目已立项并完成方案拆分，进入规划中状态。实际编码实施待方案评审批准后排期推进。
- **当前基线：** 现有全部单测均处于通过状态。
