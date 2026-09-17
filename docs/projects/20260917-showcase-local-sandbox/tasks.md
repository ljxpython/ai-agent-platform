# Showcase Demo 本地执行模式 - 任务拆分

## Phase 1: 后端实现

- [x] 新增 LocalShellBackend 并保留 DockerWorkspaceBackend ✅ 2026-09-17
- [x] 增加后端选择和非法配置校验 ✅ 2026-09-17
- [x] 补充本地后端单元测试 ✅ 2026-09-17

## Phase 2: 本地栈和文档

- [x] 在 `scripts/local-stack.sh` 增加模式切换 ✅ 2026-09-17
- [x] 更新 showcase_demo README 和功能总览 ✅ 2026-09-17

## Phase 3: 验证

- [x] 单元测试、编译检查、Ruff 检查 ✅ 2026-09-17
- [ ] Docker 模式回归（本机 Docker daemon 不可用）
- [x] 本地模式真实执行链路 ✅ 2026-09-17
- [x] 本地栈脚本语法检查 ✅ 2026-09-17
- [x] 本地栈配置优先级及 API/Worker 环境传递测试
- [x] 本地 Graph → 审批允许/拒绝 → 真实 Shell → 文件产物测试
- [ ] 完整部署 E2E 未执行；项目状态 partial
