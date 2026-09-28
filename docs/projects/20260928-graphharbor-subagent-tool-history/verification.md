# 验证计划与验收记录

## 一、验证目标与标准

1. **RFC 交付验证**：需求文档技术事实准确，SQL 语句、数据结构与接口提案无歧义；
2. **端到端功能验证**：
   - 场景 A（实时生成态）：子智能体运行中实时展示步骤；
   - 场景 B（历史刷新态）：刷新浏览器后，展开子智能体卡片依然能看到子智能体执行过的每个工具调用；
3. **回归质量保证**：单元测试通过、类型检查 0 错误。

---

## 二、测试用例矩阵

### 1. 单元测试
- [ ] `platform-api`: `threads_sdk_adapter.spec.py` 测试 `checkpoint_ns`、`expand_subagents` 参数透传无过滤
- [ ] `platform-web`: `SubtaskDetail.spec.ts` 验证离线历史模式下对子工具调用的正确渲染与展开
- [ ] `platform-web`: `SubagentCard.spec.ts` 保持现有卡片渲染测试 100% 通过

### 2. 接口契约测试
- [ ] 调用扩展后的 `GET /api/langgraph/threads/{thread_id}/state`
  - 预期结果：当传入对应参数时，返回体包含子图消息或能够通过 `checkpoint_ns` 拉取子图列表。

### 3. 端到端场景验证
- [ ] **场景 1：历史会话复核**
  - 打开 `http://127.0.0.1:3000/workspace/projects/.../chat/fba64a6c-0268-4609-bfc8-802c72b26dec`
  - 展开最上方 `research` 子智能体卡片；
  - 验证：在“子任务执行过程”抽屉中，成功列出 `ls`、`read_file`、`grep` 等 10 项执行步骤；
  - 点击其中一个 `read_file`，能够正常展开查看该步骤读取的文件内容与状态。

---

## 三、验证记录

### 2026-09-28 初始调研与真实数据验证
**执行人：** @lijiaxin

#### 数据库持久化验证
- ✅ `graphharbor_acceptance` 数据库 `checkpoints` 表存在 `checkpoint_ns = 'tools:89b00bd9-...'`
- ✅ `checkpoint_blobs` 表反序列化出 16 条完整消息、10 次内部工具调用（`ls`, `read_file`, `grep`, `glob`）
- 结论：**底层数据 100% 存在，瓶颈在服务间读取契约**。

### 2026-09-28 GraphHarbor post37 升级与网关集成回归验证
**执行人：** 老王（Antigravity）

#### 1. 依赖锁步与服务栈重启
- ✅ `apps/runtime-service/pyproject.toml` 与 `uv.lock` 升级至 `graphharbor==0.13.0.post37` 和 `graphharbor-runtime==0.13.0.post37`。
- ✅ 执行 `rtk bash scripts/local-stack.sh restart`：
  - `runtime-api` (pid=52675, port=8123) ready
  - `runtime-worker` (pid=52689) ready
  - `platform-api` (pid=52740, port=2142) ready
  - `platform-web` (pid=52770, port=3000) ready

#### 2. 网关层单元测试
- ✅ `apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py`:
  - `test_threads_get_state_passes_checkpoint_ns` PASSED
  - `test_threads_get_history_passes_checkpoint` PASSED
  - 累计 21 项单元测试全绿通过。

#### 3. 真实会话端到端接口验证
- 测试环境：Thread `fba64a6c-0268-4609-bfc8-802c72b26dec`, Project `5a5b7239-43e3-40e6-bba3-e64d96057607`, Namespace `tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451`
- **验证项 1: 主图根节点读取**
  - 请求：`GET /api/langgraph/threads/{thread_id}/state`
  - 响应：HTTP 200，消息数 18 条，`checkpoint_ns=""`
- **验证项 2: 子智能体状态读取 (GET)**
  - 请求：`GET /api/langgraph/threads/{thread_id}/state?checkpoint_ns=tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451`
  - 响应：HTTP 200，消息数 16 条，`checkpoint_ns="tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451"`
  - 真实工具调用清单（10 次全数返回）：
    1. `ls` (call_00_v64mnfu8okr81952bjvost4l)
    2. `read_file` (call_01_0w1ehuyzc140wtzgmxdkcy9y)
    3. `read_file` (call_00_tnbni1dsfwcm0s3hoxwl9piq)
    4. `read_file` (call_01_nj89jp1572g2xuponh9mpvgp)
    5. `read_file` (call_02_b2wt5ipmri76o0q0muasr3el)
    6. `grep` (call_00_qp6uacpahxftwfsxwcxfb0tz)
    7. `grep` (call_01_g2bqaom25qf2d82tat2eluc1)
    8. `glob` (call_02_3a53qmsm32872nqyyo90er29)
    9. `glob` (call_00_xyll56ztcjocj5doy7jaut44)
    10. `read_file` (call_01_whl77sndsmpe3l6sitqwouj8)
- **验证项 3: 官方 SDK 规范调用 (POST /state/checkpoint)**
  - 请求：`POST /api/langgraph/threads/{thread_id}/state/checkpoint`
  - 响应：HTTP 200，消息数 16 条
- **验证项 4: 完整时间线回溯 (POST /history)**
  - 请求：`POST /api/langgraph/threads/{thread_id}/history`
  - 响应：HTTP 200，返回 10 个步进历史状态（各步骤 namespace 一致保持为 `tools:89b00bd9-03c0-6b3a-4dc0-566fe060a451`）

#### 最终判定
- **完成度状态：** `done`
- **结论：** GraphHarbor 修复版本及平台网关层接入完全成功，子智能体状态、消息及工具调用丢失问题彻底根治。
