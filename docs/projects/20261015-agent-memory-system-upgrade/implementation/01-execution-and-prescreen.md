# 01 执行流解耦与 Prescreen 成本门禁实现记录

## 改动时间
2026-10-15

## 相关任务
- Task 1.1: 创建 `prescreen.py`，实现确定性信号检测与对话价值初筛逻辑
- Task 1.2: 重构 `MemoryContextMiddleware.aafter_agent`，引入异步后台任务派发与 Prescreen 门禁
- Task 1.3: 加固异步任务生命周期与异常兜底，状态回写

## 改动文件
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/prescreen.py` (新建)
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py` (重构)
- `apps/runtime-service/tests/services/dearflow_agent/test_memory_prescreen.py` (新建单测)

## 具体改动

### 1. 新建 `prescreen.py`
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prescreen.py`
- 实现 `detect_signals`：使用正则高效匹配显式纠错与强化偏好信号；
- 实现 `prescreen_conversation`：在进入昂贵的 LLM 提取前，优先基于确定性信号放行，对极短文本（<8字符且无偏好信号）、纯代码/命令、纯知识问答直接返回 `(False, reason)`，避免无意义的 Token 开销。

### 2. 重构 `MemoryContextMiddleware` 异步非阻塞派发
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`
- 将原 `aafter_agent` 内同步阻塞的 `await self.model.with_structured_output(...).ainvoke(...)` 剥离；
- 先走 `prescreen_conversation`，跳过时轻量记录 `skipped` 推进水位（耗时 < 5ms）；
- 需要提取时，封装为独立的 `_async_extract_and_propose` 协程，在生产环境下通过 `asyncio.create_task` 在后台执行，主执行流毫秒级立即返回；
- 提供 `drain_tasks(timeout)` 方法用于测试和关机排空，支持 `MEMORY_EXTRACTION_SYNC=1` 便于确定性测试；
- 全局异常防护，确保后台任务即使遇到网络超时或错误也不会造成未捕获异常，并正确回写 `status="failed"`。

## 验证
- [x] 单元测试通过：`pytest test_memory_prescreen.py test_memory_contract.py` 全部 22 个测试用例 100% 通过；
- [x] 非阻塞验证：`test_async_non_blocking_dispatch_and_drain` 验证在模型耗时 100ms 时，`aafter_agent` 耗时 < 80ms（实测 < 5ms）立即释放；
- [x] 确定性预筛验证：极短文本正确返回 `too_short`，显式偏好正确放行。
