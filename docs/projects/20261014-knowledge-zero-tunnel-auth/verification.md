# 知识库免隧道自治与单向架构治理 - 验证计划和记录

## 验证计划

### 单元与机制测试
- [x] `test_local_authorize()` - 验证 `operation_auth.py` 在 `authorize_url="local"` 时的本地闭环构造与签名自验。

### 网络拓扑隔离验证
- [x] **反向端口彻底断开验证：**
  - 操作：杀掉本地 `ssh -R` 隧道后台任务后，在远端执行 `curl -s -I http://127.0.0.1:21420`。
  - 预期：连接被直接拒绝（Connection refused），证明完全没有任何隧道存活。

### 业务链路与端到端测试
- [x] **零隧道入库处理：**
  - 操作：在无隧道环境下提交文档任务，远端异步 Worker 处理。
  - 预期：Worker 在完全无反向 HTTP 请求的情况下本地自验通过，Job 流转为 `ready`。
- [x] **真实浏览器 Playwright 端到端闭环：**
  - 操作：运行 `scratch/e2e_test_runner.py`。
  - 预期：在无头浏览器中自动完成全流程，验证命中知识库小萝卜手机号/院校，测试绿灯（Exit code 0）。

## 验证记录

### 2026-10-14 验证
**执行人：** 老王（laowang-engineer）

#### 单元与机制测试
- **测试用例：** `test_local_authorize()`
- **执行命令：** `pytest tests/test_knowledge_generations.py`
- **执行结果：** 6 passed in 5.34s，`authorize_url="local"` 成功直接生成受信 envelope 并完成 HMAC-SHA256 自验。

#### 网络拓扑隔离验证
- **反向端口断开验证：**
  - 在杀掉本地 SSH 隧道后台任务后，远端执行 `curl -s -I http://127.0.0.1:21420`。
  - 结果：curl 返回退出码 7（Failed to connect to host; Connection refused）。
  - 本地检查：`ps aux | grep 'ssh.*21420'` 结果为空，确认没有任何存活的隧道进程与监听端口。
  - 远端对外开放端口收敛至仅需 `22` (SSH) 与 `8000` (FastMCP/HTTP)。

#### 业务链路与端到端测试
- **零隧道入库构建落盘（Task 3.1）：**
  - 触发任务：`kj_59d7ebf265d84f989246e68a326f5f29`（`10.docx`）
  - 过程流转：`queued` → `parsing`（Docling 抽取文本与多模态资产） → `indexing`（LLM 实体抽取、关系提炼与百炼 embedding 向量化） → `ready`
  - 数据库状态：
    - `jobs.status`: `ready`，`error_code`: `NULL`
    - `projects.active_namespace`: `kg_dd161ddb04944c22893e590f5709d7ec`，`revision`: `1`
    - `documents.published_at`: `2026-10-14T14:44:17.026846Z`
  - 产物校验：`graph_chunk_entity_relation.graphml` (12KB)、`vdb_chunks.json` (12KB)、`vdb_entities.json` (118KB)、`vdb_relationships.json` (93KB) 均完整生成并通过 snapshot 密封校验。

- **Playwright + Chromium 端到端自动化验收（Task 3.2）：**
  - 执行脚本：`scratch/e2e_test_runner.py`
  - 执行结果：
    ```text
    === Starting Playwright End-to-End Test ===
    Chat page loaded: http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/chat/221a75ac-9577-48c3-b759-781131c0ff65?agentId=cec2267a-d96d-47e0-8363-71b083fd7d1f
    Step 2: Uploading attachment 10.docx...
    Attachment uploaded and preview rendered.
    Step 3: Checking '共享至项目知识库'...
    Checking '共享至项目知识库' checkbox...
    Step 5: Sending message...
    Step 6: Waiting for agent response and tool execution...
    Agent finished generating in 21s.
    Checking UI newly generated response content...
    Verification details: has_phone=True, has_school=True, has_error=False
    SUCCESS: Knowledge base retrieval & document status verified in UI!
    === Test Finished ===
    Final Success: True
    ```
  - 状态：Exit code 0 绿灯通过。
  - 截图证据链存档：
    - 登录界面：[`e2e_01_login_page.png`](file:///Users/lijiaxin/.gemini/antigravity/brain/ac2f2ace-73d4-4dc0-93b4-f07463308ea7/e2e_01_login_page.png)
    - 附件上传：[`e2e_04_attachment_uploaded.png`](file:///Users/lijiaxin/.gemini/antigravity/brain/ac2f2ace-73d4-4dc0-93b4-f07463308ea7/e2e_04_attachment_uploaded.png)
    - 知识库勾选：[`e2e_05_kb_checked.png`](file:///Users/lijiaxin/.gemini/antigravity/brain/ac2f2ace-73d4-4dc0-93b4-f07463308ea7/e2e_05_kb_checked.png)
    - 消息发送：[`e2e_07_message_sent.png`](file:///Users/lijiaxin/.gemini/antigravity/brain/ac2f2ace-73d4-4dc0-93b4-f07463308ea7/e2e_07_message_sent.png)
    - 最终结果：[`e2e_10_final_result.png`](file:///Users/lijiaxin/.gemini/antigravity/brain/ac2f2ace-73d4-4dc0-93b4-f07463308ea7/e2e_10_final_result.png)（清晰展示召回小萝卜手机号 `13688888888` 与 `吉林大学`）

#### 完成度判定
- **当前状态：** `done`
- **判定依据：** 全链路需求 100% 达成，单元测试、拓扑隔离验证、业务入库构建与 Playwright 端到端浏览器测试全量通过且留痕完备。零隧道架构稳定运行。
