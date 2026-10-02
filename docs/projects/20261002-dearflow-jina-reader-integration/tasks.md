# DearFlow Agent 接入 Jina Reader 网页深度提取 - 任务拆分

## Phase 1: 配置与核心实现

### Task 1.1: 环境变量同步与多命名兼容
- **改动内容：** 从 `~/.my_best/.env` 读取 `JINA_KEY` 并写入 `apps/runtime-service/.env`（命名为 `JINA_API_KEY` 与 `JINA_KEY`），代码层兼容双键读取。
- **代码位置：** `apps/runtime-service/.env`, `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py`
- **预期结果：** runtime-service 启动环境具备有效 Jina 密钥。
- **验证项：** python 脚本读取确认环境变量存在且非空。
- **预计：** 0.1天
- **状态：** `[x]` 已完成

### Task 1.2: 实现 jina_extract 与 fetch_page 双通道降级逻辑
- **改动内容：** 在 `search.py` 中新增 `jina_extract`，改造 `fetch_page` 优先 Jina、失败降级 Tavily；保持 `public_url` 与 `_evidence` 证据落盘不变。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py`
- **预期结果：** `fetch_page` 优先返回 Jina 清洗的 Markdown 正文，遇异常自动回退 Tavily。
- **验证项：** 单元测试与 mock 测试。
- **预计：** 0.1天
- **状态：** `[x]` 已完成

### Task 1.3: 对齐 agent.py 工具可用性判定
- **改动内容：** 优化 `agent.py` 里的工具判定：只要存在 Jina Key 或 Tavily Key，`fetch_page` 保持可用；`search_web` 依赖 Tavily Key。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
- **预期结果：** 工具可用性判定更灵活，不会因缺少某一个 key 导致全部网络工具被误剔除。
- **验证项：** pytest 相关用例通过。
- **预计：** 0.1天
- **状态：** `[x]` 已完成

## Phase 2: 测试与验证

### Task 2.1: 补充 Jina Reader 与 Fallback 单元测试
- **改动内容：** 在 `apps/runtime-service/tests/services/dearflow_agent/test_research.py` 中新增 Jina 成功提取、Jina 报错自动回退 Tavily、两家均失败报错的测试用例。
- **代码位置：** `apps/runtime-service/tests/services/dearflow_agent/test_research.py`
- **预期结果：** 覆盖全部降级分支与异常处理。
- **验证项：** `pytest tests/services/dearflow_agent/test_research.py` 全绿通过。
- **预计：** 0.1天
- **状态：** `[x]` 已完成

## Phase 3: 全链路验收

### Task 3.1: 真实网络请求与工作区证据落盘验证
- **改动内容：** 执行真实 URL 提取测试，检查 `/workspace/sources/{hash}.txt` 生成的 Markdown 正文完整性。
- **预期结果：** 成功提取结构化 Markdown，无多余噪音，SHA256 证据落盘完备。
- **验证项：** 真实 HTTP 提取与证据文件哈希校验。
- **预计：** 0.1天
- **状态：** `[x]` 已完成

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全链路验收通过
