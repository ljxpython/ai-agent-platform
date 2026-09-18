# 契约与状态边界

## 目标
定义一个与 LangGraph 原生 thread/checkpoint 一致、且不会把原会话继续写坏的分叉契约。

## 方案设计
来源只能是已完成 assistant 回复对应的 checkpoint。Platform Web 从消息元数据取得该 checkpoint；Platform API 不相信浏览器声称的 state，只按来源 thread 的 checkpoint_id 向 LangGraph 读取快照。

`POST /api/langgraph/threads/{source_thread_id}/fork`

请求体只接受：`{"checkpoint_id":"...","title":"可选的新会话标题"}`。

调用链：`Platform Web -> Platform API validate -> LangGraph get_state(source checkpoint) -> create(target) -> update_state(target values) -> Platform Web opens new thread`。

不复制 `config`、`parent_checkpoint`、pending interrupt、Run、消息队列、文件/终端/上传对象。这些对象都绑定 source thread；目标状态写入生成新的 checkpoint，后续执行完全走目标 thread_id。

## 任务拆分
- [x] 确认现有 `checkpoint_id` 白名单和 `update_state` SDK 适配器可复用。
- [ ] 在 Platform API 实现受控 fork endpoint。
- [ ] 补充状态、跨项目拒绝和创建失败清理测试。

## 验证要求与记录
- [ ] 只允许同项目、有 write 权限的来源 thread。
- [ ] 目标 thread 具有新的 ID、继承 `values`、记录 provenance。
- [ ] 不允许客户端提交任意 `values`、`graph_id` 或项目 ID。

## 状态
进行中。
