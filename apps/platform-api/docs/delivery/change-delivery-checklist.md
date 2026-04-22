# Platform API 变更交付清单

这份清单不是给人看着安心的摆设，而是后续所有结构性改动都要照着执行的正式流程。

---

## 1. 开工前

- [ ] 先确认改动属于 `platform-api`、`platform-web`、`runtime-service` 还是 `interaction-data-service`
- [ ] 先确认是否影响正式控制面链路
- [ ] 先确认 request / response 契约
- [ ] 先确认权限边界
- [ ] 先确认审计动作
- [ ] 先确认是否必须进入 `operations`

---

## 2. 编码时

- [ ] handler / router 只做协议层工作
- [ ] application 层负责编排
- [ ] adapter 负责外部系统映射
- [ ] 不直接跨模块拼 repository
- [ ] 不新增绕过 service 层的前端请求
- [ ] 不把旧 `platform-api` 兼容逻辑带回正式主链

---

## 3. 完成后必须补齐

- [ ] 代码
- [ ] 自动化测试
- [ ] 手动验收步骤
- [ ] 对应文档
- [ ] checklist 勾选
- [ ] 如涉及交付，补 runbook / release 模板影响说明

---

## 4. 提交前最小验证

- [ ] `platform-api`: `python3 -m compileall app`
- [ ] `platform-api`: `.venv/bin/python -m unittest discover -s tests`
- [ ] `platform-web`: `pnpm lint`
- [ ] `platform-web`: `pnpm typecheck`
- [ ] `platform-web`: `pnpm build`
- [ ] `bash "./scripts/check-health.sh"` 或等价健康检查

---

## 5. 提交说明必须覆盖

- [ ] 这次改了什么
- [ ] 为什么这么改
- [ ] 验证怎么做的
- [ ] 还有哪些风险或后续项

---

## 6. 明确禁止

- [ ] 只改代码不改文档
- [ ] 只改文档不做验证
- [ ] 为了赶进度跳过权限或审计
- [ ] 页面直接拼 URL 绕过 service
- [ ] 把旧链路 fallback 带回正式主链
