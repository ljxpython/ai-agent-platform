# DearFlow Agent 接入 Jina Reader 网页深度提取 - 验证计划和记录

## 验证计划
- [x] `test_fetch_page_jina_success` - 验证 Jina Reader 正常提取并生成 Markdown 证据
- [x] `test_fetch_page_fallback_to_tavily` - 验证 Jina 报错时自动平滑回退 Tavily Extract
- [x] `test_fetch_page_both_fail` - 验证两者均失效时标准报错 `research_extract_failed`
- [x] `tests/services/dearflow_agent/test_research.py` 现有测试全绿通过

### 集成与链路测试
- [x] **场景 1：真实 URL 提取与 Jina 报文解析**
  - 测试：对公开网页调用 `fetch_page`
  - 预期：获得由 Jina 洗出的结构化 Markdown，无 HTML 垃圾标签
- [x] **场景 2：证据落盘与 SHA256 校验**
  - 测试：检查 `/workspace/sources/{hash}.txt`
  - 预期：文件内容与返回的 `content` 一致，哈希值与文件名完全匹配

---

## Phase 验证记录

### Phase 1 & 2: 单元测试回归
- **测试命令：** `uv run pytest tests/services/dearflow_agent/test_research.py -v`
- **执行结果：**
  ```text
  tests/services/dearflow_agent/test_research.py::test_source_records_are_scoped_and_read_only PASSED [  6%]
  tests/services/dearflow_agent/test_research.py::test_private_or_credential_urls_rejected[...] PASSED [ 43%]
  tests/services/dearflow_agent/test_research.py::test_modes_enforce_planning_and_delegation PASSED [ 50%]
  tests/services/dearflow_agent/test_research.py::test_provider_errors_and_large_results PASSED [ 81%]
  tests/services/dearflow_agent/test_research.py::test_jina_extract_direct PASSED [ 87%]
  tests/services/dearflow_agent/test_research.py::test_fetch_page_dual_channel_fallback PASSED [ 93%]
  tests/services/dearflow_agent/test_research.py::test_agent_available_tools_with_jina_only PASSED [100%]
  ================= 15 passed, 1 skipped, 11 warnings in 19.19s ==================
  ```
- **Agent 回归测试：** `uv run pytest tests/services/dearflow_agent/test_agent.py`
  - 18 passed in 21.67s（无任何回归与副作用）。

---

## Final 验证记录

### 真实网络调用端到端验收
- **测试命令：** `DEAR_RESEARCH_LIVE_TEST=1 uv run pytest tests/services/dearflow_agent/test_research.py -k test_live_search_and_extract`
- **执行结果：** 1 passed, 15 deselected in 16.69s。
- **沙箱证据落盘抽查（`https://example.com`）：**
  ```json
  {
    "source_url": "https://example.com/",
    "requested_url": "https://example.com",
    "title": "Example Domain",
    "kind": "page_text",
    "content_hash": "55c19993de36151e2a4f04afcbae2ee42e6ca9f17c4799d801b989b4712a2866",
    "path": "/workspace/sources/55c19993de36151e2a4f04afcbae2ee42e6ca9f17c4799d801b989b4712a2866.txt"
  }
  ```
  - 落盘正文为规范 Markdown，含链接语法 `[Learn more](https://iana.org/help/example-domains)`，SHA256 完全吻合，无任何 HTML 杂质。

### 结论
- **完成状态：** `done`
- **四态判定：** 全部功能已实现，单测、降级容灾、真实网络交互与沙箱证据链均通过验证。
