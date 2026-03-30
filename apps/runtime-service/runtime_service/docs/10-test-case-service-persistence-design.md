# test_case_service 持久化设计

## 目标

为 `runtime_service/services/test_case_service` 增加一条最小但稳定的正式落库链路：

```text
多模态输入
  -> 需求分析 / 策略 / 用例设计 / 评审 / 格式化
  -> persist_test_case_results
  -> interaction-data-service HTTP API
  -> test_case_documents / test_cases
```

本设计明确不复用 `usecase_workflow_agent` 的 workflow / snapshot / review 编排模型。

## 设计原则

1. 只保留一个模型可见持久化工具：`persist_test_case_results`
2. 只保留两类远端资源：`documents` 和 `test-cases`
3. 共享 HTTP client 只抽传输层，不抽业务 payload
4. `project_id` 等受信参数由 `runtime.config / runtime.state / runtime.context` 读取
5. 当前尚未完全透传项目上下文时，允许使用默认项目 ID 兜底

## runtime-service 侧结构

### 1. 服务私有工具

新增：

- `runtime_service/services/test_case_service/tools.py`

职责：

- 解析 `ToolRuntime`
- 读取 `project_id / thread_id / run_id / batch_id`
- 从 `multimodal_attachments` 构造文档持久化 payload
- 从最终测试用例构造测试用例持久化 payload
- 调用共享 HTTP client

实现注意：

- `persist_test_case_results` 的 `runtime` 参数必须使用标准 `ToolRuntime[...]` 注入形式
- 不要把 `runtime` 写成可选参数
- 不要再为这个工具显式绑定 `args_schema`
- 该工具应由函数签名自动推导 schema，否则 LangGraph 可能无法正确注入 `runtime`

### 1.1 二期职责调整

二期后 `persist_test_case_results` 不再承担“首次写入 document”的职责。

它只负责：

- 读取运行态里已经持久化成功的 `document_id`
- 对缺失 `document_id` 的附件做补偿写入
- 写入最终正式 `test_cases`
- 建立 `source_document_ids` 关联

### 1.2 服务专属即时持久化层

二期新增：

- `runtime_service/services/test_case_service/document_persistence.py`
- `runtime_service/services/test_case_service/middleware.py`

职责：

- 在 `test_case_service` 作用域内即时持久化已解析附件
- 基于附件 fingerprint 做幂等
- 将 `persisted_document_id / persist_status / persisted_at / persist_error` 回填到附件状态

约束：

- 通用 `runtime_service/middlewares/multimodal/*` 不耦合 testcase 落库逻辑
- 即时持久化逻辑只允许出现在 `test_case_service` 私有层

### 2. 共享 HTTP client

新增：

- `runtime_service/integrations/interaction_data.py`

抽象边界：

- 负责 base_url / token / timeout / headers / HTTP JSON 请求
- 不理解任何具体业务字段
- 不替各服务组装 payload

这样其他服务后续也能复用同一个 client，但不会被 `test_case_service` 的数据结构绑死。

### 3. 默认项目 ID 策略

解析顺序：

1. `runtime.context.project_id`
2. `runtime.config.configurable.project_id`
3. `runtime.config.metadata.project_id`
4. `runtime.state.project_id`
5. `test_case_default_project_id`

当前默认值：

- `00000000-0000-0000-0000-000000000001`

这是过渡方案，后续接入真实项目上下文后应优先覆盖。

## interaction-data-service 侧结构

采用“每个服务一个专属接口前缀”的范式：

- `POST /api/test-case-service/documents`
- `GET /api/test-case-service/documents`
- `GET /api/test-case-service/documents/{document_id}`
- `POST /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases`
- `GET /api/test-case-service/test-cases/{test_case_id}`
- `PATCH /api/test-case-service/test-cases/{test_case_id}`
- `DELETE /api/test-case-service/test-cases/{test_case_id}`

旧的 `/api/usecase-generation/*` 已退役，不再作为主路径。

## 数据落点

### 1. `test_case_documents`

存附件解析结果：

- `project_id`
- `batch_id`
- `filename`
- `content_type`
- `source_kind`
- `parse_status`
- `summary_for_model`
- `parsed_text`
- `structured_data`
- `provenance`
- `confidence`
- `error`
- `idempotency_key`（二期用于上传即落库幂等）

### 2. `test_cases`

存最终正式测试用例：

- `project_id`
- `batch_id`
- `case_id`
- `title`
- `description`
- `status`
- `module_name`
- `priority`
- `source_document_ids`
- `content_json`

其中完整业务结果和运行时元数据全部收敛到 `content_json.meta`。

## 调试与验证要求

禁止 mock 持久化链路。

验证必须同时满足：

1. 使用真实 PDF 或真实业务需求文本
2. 使用真实模型
3. 调用真实 `interaction-data-service`
4. 最终通过远端查询接口确认文档和测试用例已写入
5. 抓取并分析：
   - 流式输出内容
   - 工具调用记录
   - 远端返回结果
   - 最终异常或成功状态

二期额外要求：

1. 在不调用 `persist_test_case_results` 的前提下，上传真实 PDF 后应立即能在 `test_case_documents` 中查到记录
2. 同一 PDF 同一项目重复重试时，document 不得重复插入
3. 后续正式保存 testcase 时，必须复用既有 `document_id`

推荐使用两个真实验证脚本：

```bash
cd apps/runtime-service
uv run python runtime_service/tests/services_test_case_service_document_live.py \
  --model-id deepseek_chat \
  --timeout 900 \
  --interaction-timeout 60

uv run python runtime_service/tests/services_test_case_service_persistence_live.py \
  --model-id deepseek_chat \
  --timeout 900
```

含义：

1. `services_test_case_service_document_live.py`
   - 真实上传 PDF
   - 不允许调用 `persist_test_case_results`
   - 验证 `TestCaseDocumentPersistenceMiddleware` 是否完成“上传即落库”
   - 同一 `batch_id` 连续跑两次，验证 document 幂等
2. `services_test_case_service_persistence_live.py`
   - 真实生成正式测试用例
   - 调用 `persist_test_case_results`
   - 验证 `test_cases` 写入以及 `source_document_ids` 关联

## 实现陷阱与修复点

### 1. middleware 阶段不能假设 `runtime.config` 一定存在

`persist_test_case_results` 工具里拿到的是 `ToolRuntime`，它有 `config/state`。

但 `wrap_model_call` 中间件里拿到的是 `langgraph.runtime.Runtime`，默认只有：

- `context`
- `store`
- `stream_writer`
- `previous`

没有 `config`。

因此 `test_case_service` 的文档即时持久化层必须这样取配置：

1. 优先读 `runtime.config`
2. 若不存在，则回退到 `langgraph.config.get_config()`

否则中间件阶段会拿不到：

- `interaction_data_service_url`
- `project_id`
- `batch_id`

最终表现为“即时落库没有真正发生”。

### 2. `wrap_model_call` 里的 `request.override(state=...)` 不等于 graph state 已更新

`wrap_model_call` 内改过的 `request.state` 只保证“本次模型调用能看到”。

如果希望后续工具节点也能读到这些状态，例如：

- `persisted_document_id`
- `persist_status`
- `persisted_at`

就必须额外返回：

- `ExtendedModelResponse`
- `Command(update=...)`

把附件状态显式写回 graph state。

否则会出现：

1. 文档即时落库已经成功
2. 但后续 `persist_test_case_results` 仍看不到 `persisted_document_id`
3. `source_document_ids` 为空
4. testcase 与 document 无法关联

当前修复方案：

1. `document_persistence.py` 在 middleware 阶段回退使用 `get_config()`
2. `TestCaseDocumentPersistenceMiddleware` 在 `wrap_model_call/awrap_model_call` 返回 `ExtendedModelResponse + Command(update=...)`
3. 工具阶段复用 graph state 中已回填的 `persisted_document_id`

## 已完成真实验证

已通过以下命令完成一轮真实落库验证：

```bash
cd apps/runtime-service
uv run python runtime_service/tests/services_test_case_service_persistence_live.py \
  --model-id deepseek_chat \
  --timeout 900
```

验证结果：

1. `persist_test_case_results` 已被真实调用
2. `interaction-data-service` 远端查询确认：
   - `documents_total = 1`
   - `test_cases_total = 4`
3. 退出码为 `0`

说明当前最小持久化架构已经可用。
