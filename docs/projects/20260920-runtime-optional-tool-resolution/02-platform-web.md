# 02 — 前端：工具展示与交互收口

## 目标

Catalog 页面展示 Runtime 声明；另提供管理员“工具禁用例外”管理，Agent 编辑和聊天不再承担工具选择/授权求值。身份入口、模型设置、审批交互继续正常工作。

## 方案设计

| 文件（相对 apps/platform-web/src） | 当前行为 | 开发内容 |
|---|---|---|
| modules/runtime/pages/RuntimeModelsPage.vue | listRuntimeToolPolicies + updateRuntimeToolPolicy，项目工具开关 | 改为只读目录；移除旧逐工具启用开关，保留模型配置及目录刷新；管理员可打开单独的禁用例外面板 |
| modules/agents/pages/AgentEditorPage.vue | toolMode/selectedTools 与 context.tools 持久化 | 删除工具选择 UI 和提交字段；按 graph 展示声明工具，只读且不阻塞 Agent 保存 |
| services/runtime-policies/runtime-policies.service.ts | 工具策略 GET/PUT | 删除 listRuntimeToolPolicies/updateRuntimeToolPolicy 及导出；保留 model/graph 策略 |
| types/management.ts | RuntimeToolPolicy* 类型 | 删除旧策略类型，调整 RuntimeToolItem 的 graph_ids/description/availability 展示字段 |
| services/runtime/runtime.service.ts | 目录 GET/refresh | 保留目录接口，更新新响应类型；刷新失败保持旧展示并提示 |
| services/agents/types.ts、context.ts | 接受 tools | 删除 tools 字段/解析，旧草稿提交应提示重建，不做运行期迁移 |
| services/runtime/runtime-contract.ts | 多入口移除/搬移旧业务字段 | 统一新契约，去掉针对 tools 的兼容归一分支，绝不依赖静默 strip 保障后端安全 |
| modules/chat/composables/useChatSession.ts、modules/dear-agent/composables/useDearAgentSession.ts | 提交 Run/继续/审批 | 验证全路径不产生工具授权字段，正确显示终态及规则拒绝 |

新增 `modules/runtime/components/ToolRestrictionsPanel.vue`（拟）与 `services/runtime/tool-restrictions.service.ts`（拟）：选择当前项目的 graph、全员或指定成员、工具名称，添加/删除拒绝例外，显示来源及“删除用户例外不解除项目禁用”。使用既有成员查询能力；后端复核范围。没有可授权的 true 开关。保留管理员命令反馈与审计关联，不在客户端合成 tool_overrides 或决定有效权限。管理权限使用后端的项目治理权限，普通使用者不可编辑。

Catalog 的“已声明”与“当前用户可执行”不能混同。第一版不提供用户级授权查询接口，页面说明实际能力由 Runtime 决定。目录缺失展示空态或过期提示，不能禁用聊天按钮。若 graph_ids 缺失应由新响应校验暴露，不能维护旧响应适配。

Skill 管理、工作区上传、Terminal 的入口可依据已有平台访问权展示；Runtime 拒绝具体动作后，前端提供清晰提示，不自行计算工具 false 规则。审批同意后仍可能因规则变化被拒绝，这是服务端结论。

## 任务拆分

- [x] W1：目录展示替换项目工具策略，移除开关与保存动作。
- [x] W2：Agent 编辑去除选择/继承工具 UI，改只读 Agent 能力列表。
- [x] W3：清除服务、类型、Context 及新请求中的旧字段；检索所有引用，不顺带删除模型/graph 能力。
- [x] W4：处理历史草稿、版本过期客户端与服务端拒绝提示；加载已有 Agent 时主动脱敏剔除旧 tools/enable_tools。
- [x] W5：新增管理员禁用例外面板（ToolRestrictionsPanel.vue）、服务类型与命令交互；目录刷新与权限管理分离。
- [x] W6：补定向组件/服务测试（ToolRestrictionsPanel.spec.ts、runtime-policies.service.spec.ts、context.spec.ts 等），跑通 lint/typecheck。

## 验证要求与记录

- [x] 目录不调用旧工具策略 API；管理员只调用新 restriction CRUD；Agent 创建/更新/聊天请求均无 tools/enable_tools/tool_overrides/自造权限字段。
- [x] 管理员可配置用户和项目禁用；普通成员拒绝写入；删除用户禁用后若项目仍禁用，界面不提示“已获授权”。
- [x] 目录为空、刷新失败、Runtime 不可达时展示准确；已有聊天能力不被目录状态禁用。
- [x] 模型选择、Agent CRUD、普通聊天、Dear Agent、审批、Terminal、Skills 正负向流程。
- [x] 类型检查、lint、定向测试：services/agents/context.spec.ts、services/agents/agents.service.spec.ts、services/runtime/runtime-contract.spec.ts、services/runtime-policies/runtime-policies.service.spec.ts、modules/runtime/components/ToolRestrictionsPanel.spec.ts 全部通过。

记录：前端实施与自动化验证完成，组件与服务单测全部通过，类型检查 0 错误。

## 状态

done：前端实现完成，工具目录只读化、管理员禁用规则管理面板、Agent 能力只读化及存量脏数据清洗均已落地并通过定向单测与类型检查。

## 本次访问控制边界

工具权限管理入口、独立路由（若采用）或面板入口按现有项目治理权限控制；无权用户不能通过直接 URL 或请求接口读取管理数据/修改规则，后端必须独立校验。工具目录保留项目成员的正常展示入口。对应前后端正负向验证属于本次交付，不后置。

全平台菜单、页面与角色权限梳理见[后置专项](../20260920-platform-access-governance/README.md)，不在本次扩展角色模型、重构全部菜单或新增通用权限配置平台。
