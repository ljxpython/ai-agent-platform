# Python 格式基线清理 - 验证计划

## Phase 验证计划
- [ ] 基线统计可重复，记录 Ruff 版本、规则和各目录诊断数。
- [ ] 每批执行对应目录 `ruff check` 与 `ruff format --check`。
- [ ] 每批执行受影响服务的相关测试。

## Final 验证计划
- [ ] `ruff check apps/platform-api apps/runtime-service`
- [ ] `ruff format --check apps/platform-api apps/runtime-service`
- [ ] platform-api 与 runtime-service 测试通过。
- [ ] CI 全量 Python 门禁通过。

## 验证记录
尚未实施，未执行本专项测试。当前约 731 条 Ruff 诊断、297 个文件格式差异的统计来自代码规范自动化专项；实施前需重新采样并固定版本。

## 状态
规划中。必要任务、测试和 CI 证据齐全后才能标为 `done`。
