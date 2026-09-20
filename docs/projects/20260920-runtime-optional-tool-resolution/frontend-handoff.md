# 前端接入交接

本次只实现 Platform API 和 Runtime；前端由用户开发。全平台菜单/角色治理另见[后置专项](../20260920-platform-access-governance/README.md)。本页是当前工具治理接口契约。

## 页面范围

1. 工具目录仅展示名称、说明、graph 归属、同步状态；删除工具启用开关和旧项目工具策略 PUT。
2. Agent 编辑、普通聊天、Run/恢复请求移除 tools、enable_tools。不要从 Catalog 计算能否对话，也不要提交 tool_overrides/tool_policy_version。
3. 项目中增加“工具禁用规则”管理面板：按 graph、工具、项目全员或指定用户创建拒绝记录；通过删除记录解除该条来源。展示并集语义：删除用户规则不会解除项目全员禁用。
4. 管理面板入口和路由使用已有项目 access 权限判断；后端仍会独立检查权限。

## 认证与权限

沿用平台认证及 x-project-id。路径 project_id 必须是当前项目。
`GET /api/projects/{project_id}/access` 的 permissions 包含 `project.runtime.write` 才能读写禁用管理接口。
当前 IAM 中项目 admin/editor 具有该治理权限，executor 无此权限；不要在前端另造角色授权表。
服务账号仅适用项目全员禁用，不作为指定用户规则目标。
成员候选复用 `GET /api/projects/{project_id}/members`，提交真实 user_id。

## 管理接口

共同前缀：`/api/projects/{project_id}/runtime-policies/tool-restrictions`。

| 方法 | 路径 | 请求 / 响应 |
|---|---|---|
| GET | 前缀 | 200：`{"items":[记录],"total":1}`；当前无分页参数 |
| POST | 前缀 | 下列 body；201 返回完整记录 |
| DELETE | 前缀 + `/{restriction_id}` | 无 body；204 无响应体 |

```json
{
  "graph_id": "dearflow_agent",
  "subject_type": "user",
  "subject_id": "目标用户 UUID",
  "tool_name": "execute",
  "reason": "该用户无需运行终端命令"
}
```

项目全员规则使用 subject_type=`project`，subject_id 必须等于路径 project_id。
记录响应在上述字段之外包含 id、project_id、created_by、created_at。
graph_id/tool_name 最长 128，仅字母、数字、下划线、点、冒号、连字符；reason 长度 1–1000；额外字段拒绝。
不提供 PUT/PATCH 或 is_enabled/allow 布尔开关；修改规则用删除、重新创建。

新增时后端实时读取 Runtime 声明校验工具与 graph 的对应关系，不依赖平台缓存；Runtime 不可达时创建失败。已有规则查询、删除及运行时求值不依赖工具目录。

| 错误 | 前端处理 |
|---|---|
| 401 | 重新认证 |
| 403 | 无治理权限，隐藏/禁用管理入口，并显示拒绝信息 |
| 400 `invalid_restriction_subject` | 目标不属于当前项目或不是有效成员 |
| 400 `tool_not_declared` | 工具不属于该 graph；刷新目录后重新选择 |
| 409 `tool_restriction_exists` | 同一项目/graph/主体/工具已存在，刷新列表 |
| 404 `tool_restriction_not_found` | 记录已删除或不属于项目 |
| 422 | 字段格式或额外字段不合法 |
| 503 | Runtime 声明读取/数据库等服务不可用；不要显示保存成功 |

错误使用平台统一错误体；UI 优先使用服务端 message/code，不把异常吞成空规则。

## 只读目录

沿用 `GET /api/runtime/tools`、`POST /api/runtime/tools/refresh`，携带当前项目 header。
列表响应 `{count, tools, last_synced_at}`，工具项包含 id、runtime_id、tool_key、name、description、source、graph_ids、sync_status、last_seen_at、last_synced_at。
禁用记录使用 tool_key/name；不要提交 Catalog 数据库 id。graph_ids 供选择器按 Agent 过滤展示。
目录为空、过期、刷新失败均不能阻止普通聊天；目录不是用户有效授权列表。

## 生效与边界

规则从下一次新 Run、审批恢复或直接 HTTP 操作生效。活跃 Run 使用已签名快照，界面不要承诺即时撤销；紧急停止使用已有取消 Run/关闭终端功能。execute 被禁用后关闭已有终端仍允许，不能再输入或创建。
默认启用仅指 Agent 已声明且当前环境可用的工具；平台不能授予 Runtime 没有声明的工具。全部 optional 禁用仍允许普通对话；required 禁用会使运行失败。
禁用 write_file 不等价于禁止所有文件写入：execute/MCP 等替代路径仍受沙箱/存储边界约束。

## 联调验收

- 管理员创建项目禁用，普通执行用户无法绕过；同用户换项目不串规则。
- 项目和用户同时禁用同工具，删除其中一条仍然禁用。
- ordinary Run 不携带任何工具授权字段，目录空也可提交。
- disabled 工具不出现在模型可见工具中，伪造调用及批准旧待执行动作均不产生副作用。
- 管理接口失败不乐观显示成功；刷新坏响应不覆盖已有目录。

上线必须配套新版 Platform 与 Runtime，执行新 schema 更新并停止旧 Worker。旧工具接口、Context.tools、旧 JWT/快照不兼容；旧项目不做转换。当前实现不包含生产部署。
