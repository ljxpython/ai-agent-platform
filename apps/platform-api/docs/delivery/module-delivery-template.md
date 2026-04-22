# Platform API 模块交付模板

新增模块或新增正式治理能力时，至少按这个模板补齐。

---

## 1. 模块边界

- 模块名：
- 所属平面：`control plane / runtime plane / result domain`
- 负责的资源：
- 不负责的资源：
- 上游依赖：
- 下游依赖：

---

## 2. HTTP 契约

- 读接口：
- 写接口：
- 分页口径：
- 搜索 / 筛选 / 排序口径：
- 成功响应 DTO：
- 错误码：

---

## 3. 权限与审计

- 平台级权限：
- 项目级权限：
- 审计 action：
- target_type：
- target_id 推导：
- 成功 / 失败 / 取消结果口径：

---

## 4. 后端落点

- `domain`：
- `application`：
- `infra`：
- `presentation`：
- adapter 是否涉及外部系统：
- 是否需要 `operations`：

---

## 5. 前端接入

- service 文件：
- page / route：
- 共享组件：
- state 依赖：
- 空态 / 错态 / loading：
- 成功反馈与风险确认：

---

## 6. 自动化测试

- 单测：
- repository / service 测试：
- API 集成测试：
- 前端 lint / typecheck / build：

---

## 7. 手动验收

- 启动命令：
- 登录账号：
- 页面路径：
- 关键操作：
- 预期审计：
- 预期权限失败：
- 回归点：
