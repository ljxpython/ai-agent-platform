# Platform API V2 Phase D: Final Standard Freeze

这份文档对应 `phase-5` 里定义的：

> `Phase D: Final Standard Freeze`

这一阶段不再新增控制面能力，而是把正式入口、Harness、模板、验收与交付口径彻底冻结。

---

## 1. 目标

Phase D 要完成五件事：

- 冻结正式宿主与正式启动链路
- 冻结根 README、docs index 与本地部署事实源
- 冻结 AI / 人协作的交付 checklist
- 冻结新模块与新页面的复用模板
- 冻结前端控制面页面的 UI / 交互 / service / state / audit 范式

---

## 2. 本轮完成项

### P0 正式入口冻结

- [x] 正式前端宿主固定为 `apps/platform-web-vue`
- [x] 正式控制面固定为 `apps/platform-api-v2`
- [x] 根级 `scripts/dev-up.sh`
- [x] 根级 `scripts/check-health.sh`
- [x] 根级 `scripts/dev-down.sh`
- [x] 统一收口到 `platform-web-vue-demo-*` 正式脚本
- [x] 默认本地正式链路固定为：
  - `platform-web-vue -> platform-api-v2 -> runtime-service`

### P1 文档入口冻结

- [x] 根 `README.md` 已明确正式宿主、正式端口与正式启动方式
- [x] `docs/local-deployment-contract.yaml` 已切到 `platform-api-v2` 口径
- [x] `docs/local-dev.md` 已切到 `platform-api-v2` 口径
- [x] `docs/env-matrix.md` 已切到 `platform-api-v2` 口径
- [x] `docs/development-paradigm.md` 已切到正式控制面口径
- [x] `apps/platform-api-v2/docs/README.md` 已补最终阶段入口

### P2 协作与验收冻结

- [x] 新增 `delivery/change-delivery-checklist.md`
- [x] `handbook/development-playbook.md` 已补正式协作入口
- [x] 已明确“代码、测试、文档、验收、提交”五件套缺一不可

### P3 模板冻结

- [x] 新增 `delivery/module-delivery-template.md`
- [x] 新增 `apps/platform-web-vue/docs/control-plane-page-standard.md`
- [x] 后续新模块和新页面不再从旧实现里猜做法

---

## 3. 正式启动口径

### 3.1 正式一键启动

```bash
bash "./scripts/dev-up.sh"
```

### 3.2 正式健康检查

```bash
bash "./scripts/check-health.sh"
```

### 3.3 正式停止

```bash
bash "./scripts/dev-down.sh"
```

### 3.4 当前正式端口

- `interaction-data-service`: `8081`
- `runtime-service`: `8123`
- `platform-api-v2`: `2142`
- `platform-web-vue`: `3000`

可选调试入口：

- `runtime-web`: `3001`

---

## 4. 正式开发入口

后续继续开发，默认从这些入口开始：

1. 根 `README.md`
2. `docs/local-deployment-contract.yaml`
3. `docs/development-paradigm.md`
4. `apps/platform-api-v2/docs/README.md`
5. `apps/platform-api-v2/docs/handbook/project-handbook.md`
6. `apps/platform-api-v2/docs/delivery/change-delivery-checklist.md`
7. `apps/platform-api-v2/docs/delivery/module-delivery-template.md`
8. `apps/platform-web-vue/docs/control-plane-page-standard.md`

---

## 5. 验收标准

- 新人不需要先翻旧 `platform-api`
- AI 不需要再猜正式宿主和正式端口
- 根级脚本、README、contract、env matrix 口径一致
- 新模块能直接按模板和 checklist 落地
- 前端控制面页面有固定开发范式可复用

---

## 6. Phase D 结论

`Phase D: Final Standard Freeze` 到这里视为完成。

最终收口验证结果（2026-04-06）：

- [x] `bash "./scripts/check-health.sh"` 通过
- [x] `pnpm --dir apps/platform-web-vue check` 通过
- [x] `cd apps/platform-api-v2 && .venv/bin/python -m unittest discover -s tests` 通过
- [x] 浏览器 smoke 已验证：
  - `overview`
  - `control-plane`
  - `platform-config`
  - `service-accounts`
  - `system-governance`
- [x] `service-accounts` 页面已修复超限拉取导致的 `422`

从现在开始，后续新增能力默认遵守：

- 正式控制面只认 `apps/platform-api-v2`
- 正式前端只认 `apps/platform-web-vue`
- 正式本地启动只认根脚本和 `platform-web-vue-demo-*`
- 结构性改动必须同步文档、模板、测试和验收说明
