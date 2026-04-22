# Platform API 循环导入治理清单

这份清单只服务一件事：

> 把 `platform-api` 当前已经暴露出来的循环导入问题彻底收掉，并冻结成后续不得回退的模块规则。

当前不是“顺手优化”，而是明确的结构性重构任务。

---

## 1. 触发背景

在执行：

- `uv run --project apps/platform-api pytest apps/platform-api/tests/test_phase6_normalization_regressions.py -q`

时，测试收集阶段触发循环导入，错误核心为：

- `projects.infra.sqlalchemy.repository`
- `identity.__init__`
- `identity.application.service`

相互咬住，最终报：

- `ImportError: cannot import name 'SqlAlchemyProjectsRepository' from partially initialized module ...`

---

## 2. 当前根因

当前循环链条本质上有两层问题叠加：

1. `identity` 反向依赖 `projects` 的 infra repository
   - `IdentityService` 为了补 `project_roles`，直接导入 `SqlAlchemyProjectsRepository`
2. 包级 `__init__.py` 做了过重的 eager re-export
   - 只想导入 `identity.infra.sqlalchemy.models`
   - Python 也会先执行 `identity/__init__.py`
   - `identity/__init__.py` 又把 `IdentityService` 整包拉起
   - 结果把 `projects` repo 再反向拉回来

一句话：

- 这是模块边界问题，不是单测偶发问题
- 服务能启动只是碰巧绕开了导入时序，不代表结构没问题

---

## 3. 本次重构目标

- 打断 `identity <-> projects` 的循环依赖
- 取消包级 `__init__.py` 对 service 的激进 re-export
- 让 `RuntimeGatewayService` 相关回归测试可以稳定收集并执行
- 冻结新的模块导入规则，后续不允许再长回去

---

## 4. 明确范围

本轮只治理循环导入，不顺手扩散业务改造。

范围内：

- `app/modules/identity`
- `app/modules/projects`
- `app/modules/runtime_gateway`
- 相关测试与文档

范围外：

- 不改前端
- 不改 `runtime-service`
- 不改业务权限语义
- 不顺手做 PostgreSQL / Redis / operation 其他收口

---

## 5. 执行清单

### P0 先止血

- [x] 复现实验固定化：
  - [x] 用单独命令稳定复现当前循环导入
  - [x] 记录完整导入链和触发点
- [x] 在文档中冻结当前根因，不允许后续“感觉像修好了”但没有根因说明

### P1 打断循环

- [x] 去掉 `identity` 对 `projects` infra repository 的直接依赖
- [x] 为“查询用户 project roles”补独立 query port / query service / query adapter
- [x] `IdentityService` 改为依赖抽象能力，而不是直接依赖 `SqlAlchemyProjectsRepository`
- [x] 检查 `projects` repo 是否还有其他反向依赖 `identity.application` / `identity` 包级入口

### P2 收包级导出

- [x] 收敛 `app/modules/*/__init__.py`
- [x] 收敛 `application/__init__.py`
- [x] 收敛 `infra/__init__.py`
- [x] 禁止在包级 `__init__.py` 中 eager import `Service`
- [x] 禁止通过包级入口间接触发整个模块树初始化

### P3 回归与冻结

- [x] 修复 `tests/test_phase6_normalization_regressions.py` 的收集问题
- [x] 补最少一条“冷启动导入”回归测试
- [x] 补一条“RuntimeGatewayService 可独立导入”的回归测试
- [ ] 跑通：
  - [x] `python -m compileall app`
  - [x] 相关单测
  - [ ] 至少一轮 smoke

---

## 6. 验收口径

完成这条任务，必须满足：

- [x] `RuntimeGatewayService` 被测试直接导入时，不再触发循环导入
- [x] `IdentityService` 不再直接依赖 `Projects` infra repository
- [x] `projects` / `identity` 的包级 `__init__.py` 不再承担 service 聚合入口职责
- [x] pytest 收集阶段稳定通过
- [x] 文档已经更新到正式入口

---

## 7. 重构后的正式规则

这条任务完成后，`platform-api` 必须遵守下面的冻结规则：

1. 跨模块协作优先走 application port / query port，不直接咬对方 infra repository
2. 包级 `__init__.py` 只做轻量导出，不做 service eager import
3. 任何新模块都必须能被“冷启动导入 + 单测收集”稳定加载
4. 如果一个 service 只是需要只读查询，不要直接反向引用别的模块 repository，先抽 query

---

## 8. 交付物

这条任务交付时，至少要包含：

- [x] 代码改造
- [x] 回归测试
- [x] 导入链说明
- [x] 手动验证命令
- [x] 文档更新

---

## 9. 手动验证命令

- `uv run --project apps/platform-api pytest apps/platform-api/tests/test_phase6_normalization_regressions.py -q`
- `uv run --project apps/platform-api python -m compileall app`

如果上面两条都通过，说明当前这轮“冷启动导入 + RuntimeGatewayService 独立导入”已经被稳定收住。

---

## 10. 一句话收口

这不是在修一个 pytest 小毛病，而是在修 `platform-api` 当前模块边界不稳的问题。
