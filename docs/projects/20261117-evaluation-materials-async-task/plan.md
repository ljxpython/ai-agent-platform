# 技术方案与决策（plan.md）

## 1. 现状剖析与反模式识别

### 1.1 现状实现（同步阻塞请求）
当前 `POST /api/evaluation/materials/send` 采用单一同步请求完成全部处理：
1. 校验请求与用户权限（`check_purpose`、`require_action`）；
2. 循环翻页拉取该 thread 的全部 checkpoint 历史（最多 20 页）；
3. 循环拉取所有 runs 的详细执行清单；
4. 对每个 run 抓取 execution evidence（HTTP 调用 runtime-service）；
5. 组装材料包并进行正则敏感信息（PII）脱敏；
6. 调用 EvalFlow 的 `/ajax-api/evalflow/internal/workbench/command` 创建评测工作项；
7. （若勾选 auto_generate）调用 EvalFlow 的 grant 与 generate 命令启动大模型草稿生成；
8. 组装 receipt 和 EvalFlow 前端跳转 URL 返回给客户端；
9. 前端调用 `window.location.assign(url)` 跳转。

### 1.2 现存反模式
- **同步长耗时与代理超时冲突**：大模型/多步工具调用的会话体积大，整个后端处理往往在 40~70 秒。前端 HTTP 默认超时（30s）与企业反向代理超时（Nginx 默认 60s）会直接掐断长连接；
- **前端状态机脆弱**：弹窗打开状态下如果网络中断或用户误关，重开弹窗重新生成 `request_id` 会导致后端重跑全部拉取与脱敏计算；
- **用户心智模型被绑架**：用户无法进行任何并发操作，必须干等。

---

## 2. 目标架构与设计决策

### 2.1 异步任务机制选择
- **方案 A（Celery / Redis Worker 独立任务队列）**：复杂度较高，需维护额外 worker 进程与序列化通道；对于单机 local-stack 和容器化集群运维偏重。
- **方案 B（FastAPI 原生 BackgroundTasks + 数据库任务/通知持久化，推荐）**：
  - 极简（KISS 原则）：无新增第三方守护进程依赖；
  - 接口收到请求后做轻量级前置参数与权限核对，在当前事务写入一条状态为 `pending` 的转换任务记录（或利用既有 audit/task 结构），立即返回 `202 Accepted`；
  - 后台线程池异步执行 `snapshot()`、脱敏与 EvalFlow 推送；
  - 执行完毕后，调用 `NotificationService.create_notification` 写入通知中心。
  - **决策**：选用方案 B。

### 2.2 接口契约演进（兼容性保障）
为了保证向后兼容与平滑过渡：
- `POST /api/evaluation/materials/send`：
  - 新增可选参数 `async_mode: bool = True`（默认 `True`，也可通过前端显式传入）；
  - 当 `async_mode == True` 时：
    - 返回 HTTP `202 Accepted`：
      ```json
      {
        "status": "accepted",
        "task_id": "item_id_uuid",
        "request_id": "request_id_uuid",
        "message": "评测集转换任务已提交后台处理，生成后将通过系统通知告知。"
      }
      ```
  - 当 `async_mode == False` 时：保持原有同步逻辑（兼容历史自动化测试脚本）。

### 2.3 状态通知与触达闭环
- **任务成功**：
  - 调用 `notification_service.create_notification`：
    - `title`: `评测集【{title}】已生成完毕`
    - `content`: `已成功将 {count} 段会话资料转换为评测用例草稿，AI 题目与评分标准已就绪。`
    - `category`: `NotificationCategory.SYSTEM`
    - `level`: `NotificationLevel.INFO`
    - `action_url`: `http://127.0.0.1:9128/#/authoring/{item_id}`
    - `recipient_user_id`: `actor.user_id`
    - `project_id`: `project_id`
- **任务失败**：
  - 写入 Warning 通知，说明具体失败原因（如源会话未关联 Agent、EvalFlow 服务未就绪等），并提示可重试。

### 2.4 前端交互与视觉规范
- **弹窗解耦**：
  - 点击“转换并查看 AI 建议”后，触发请求；
  - 收到 202 响应立即关闭弹窗，重置表单；
  - 触发全局 Toast（`useUiStore().showToast({ message: "评测集转换任务已在后台启动...", type: "info" })`）；
  - 顶栏通知中心（`NotificationCenterDropdown.vue`）轮询到新未读消息后红点亮起，卡片点击调用 `window.open(item.action_url, '_blank')`。

---

## 3. 风险与防范

1. **并发重跑保护**：同一个 `request_id` 或 `thread_id` 在后台尚未完成时被重复提交。
   - *防范*：在后台任务执行前做分布式/内存轻量锁或检查既有 item 状态，避免并发重复抓取。
2. **长耗时后台任务在服务重启时被中断**：
   - *防范*：后台任务记录其 `task_id` 与时间戳，若异常终止，通知中保留失败原因或允许重试。
