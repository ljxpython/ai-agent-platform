# F17 前端交接

## 现在的交接结论

**当前无前端开发任务。** 用户已确认 F17 本期不开发自建知识库；当前没有知识服务/知识 API，后续优先作为外部 MCP 工具接入。本次只交接范围和未来条件，不交接可立即开发的接口。

不要创建“项目设置 → 知识库”Tab、独立菜单、上传/解析进度页、Embedding 设置、选库控件或新的知识 service；不要恢复退役的 knowledge/testcase 路由；也不需要 mock 页面占位。

这个结论适用于普通 Chat 和 Dear Agent；不是要求同事为两个入口分别写组件。

## 后续有 MCP 时先验证现有页面

| 当前入口 | 可以复用什么 | 何时才需要修改 |
| --- | --- | --- |
| `apps/platform-web/src/modules/chat/transcript.ts` | tool artifact 与调用关联 | 实际 Adapter 的来源结构无法正确投影到 ToolResult 时 |
| `apps/platform-web/src/modules/chat/components/ToolResult.vue` | `evidenceSources`、文本/错误/工具详情展示 | 真来源已经由后端安全投影，但现有 UI 无法展示来源名或片段时 |
| `apps/platform-web/src/modules/chat/components/ToolResult.spec.ts` / `transcript.test.ts` | 格式与历史回放测试 | 上面两处出现行为改动时补真实返回 fixture |
| `apps/platform-web/src/components/platform/MarkdownContent.vue`、`src/utils/markdown.ts` | 当前 Markdown 安全渲染 | 只有实际来源交互需要扩展且现有组件能力不足时；不预建引用协议 |
| `apps/platform-web/src/modules/dear-agent/` | 当前共享 Chat 的会话入口 | 只验证共用改动能生效，不复制第二份 ToolResult 或运行状态机 |

首期后续方向是固定授权项目资源、模型调用一个查询工具。默认不加每消息选库/选文档、不加 Agent 默认绑定编辑、不加专用知识管理页；这些都需另有需求与评审。

## 后端可以发起前端实施的条件

1. M01 已确定真实知识 MCP、项目可访问范围和生产接线，且用户批准实际范围。
2. 后端提供当前发布依赖下的真实 tool 文本/artifact、无命中、失败、来源缺字段、历史回放样例；明确哪些元信息可以公开。
3. 已证明现有工具卡存在具体展示缺口，并提供准确字段/版本/错误语义。示例不得虚构 `knowledge_sources`、`source_url` 或知识 CRUD endpoint。
4. 若增加任何平台公开查询接口，先给 OpenAPI/DTO、权限、错误与真实测试结果；前端不自己猜接口。

这些条件未达到前，维持零代码交接；MCP 即可展示的情况下，也可以零前端改动完成后续接入。

## 若确需展示适配

- 资料、文件名、URL 和检索片段按不可信内容处理，复用当前 Markdown 清洗与来源链接规则；不执行原始 HTML，不打开 `javascript:`/`data:` 或猜测私有下载地址。
- 展示“检索片段”和真实文档名；页码仅在返回时出现。score 不展示为“答案置信度”，空命中不是技术失败。
- 缺失来源记录显示不可用，不能把模型生成的文件名升级为已验证来源；新查询不覆写旧消息的片段。
- 工具 API Key、供应商内部 URL、授权令牌、内部 binding 不进入 DOM、localStorage 或可见错误。只有已批准的安全来源元信息能展示。
- 如有新请求，统一走 `src/services/` 和 platform-api；项目/身份/Thread 切换丢弃迟到结果，权限暂不可确认与明确撤权分开处理。
- 继续由官方 SDK 持有 Run/消息状态；不新增知识轮询、独立 SSE 或第二来源状态库。

## 验收和交接产物

- [ ] 真实成功/无命中/错误/缺来源四种 fixture 与文字反馈。
- [ ] 刷新、历史切换、同一回答多次检索的片段对应正确。
- [ ] 两项目、两个身份切换无旧片段串入，局部拒绝不误清全局权限。
- [ ] 恶意 Markdown/URL/超长文件名不产生 XSS 或布局溢出。
- [ ] 相关 Vitest、类型检查、lint、build 通过；无代码改动则记录现有页面验收即可。
- [ ] 真实浏览器 platform-web → platform-api → runtime-service → 知识 MCP 完整链，1440/768/390 宽度、双主题、键盘可访问；真实来源回放通过。

以上都是未来门禁，当前未执行、没有前端待办排期。实施记录和截图按 [tasks.md](tasks.md) M04/M05 回填，不将本期规划交接勾为前端功能已完成。

## 必读规范

- `apps/platform-web/docs/frontend-development-playbook.md`
- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-web/docs/frontend-visual-baseline-standard.md`
- `docs/standards/error-envelope.md`
- `docs/standards/worktree-development.md`

完整取舍和代码事实见 [plan.md](plan.md)，当前任务状态只看 [tasks.md](tasks.md)。
