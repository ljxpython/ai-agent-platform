# 20260914 - 轨迹排障三合一控制器、微交互与工业级指标栏对齐

## 背景
根据用户比对原版 `deepseek-harness` 提出的前端效果差距与功能补齐要求：
1. **控制功能缺失**：缺少 `Duration`（真实耗时比例甘特图 vs 等宽模式切换）、`Turns`（批量折叠/展开轮次）、`Calls`（批量折叠/隐藏工具与子智能体调用）三大控制器；
2. **时间轴交互缺失**：时间轴色块缺少 hover 原版黑底白字微型气泡 Tooltip（大写类型标签、时间区间与持续时间），缺少原版双色两段式色块（浅紫 TTFT + 深紫 Decoding）；
3. **顶栏大字概览缺失**：轨迹顶栏缺少 `X 轮 · Y 步 · Z 工具` 大字统计；
4. **底部指标栏简陋**：原版呈现 LLM 耗时、首 token 平均延迟、生成速率（tok/s）、缓存命中率、紧凑格式输入输出 tokens；
5. **发送按钮微交互差距**：传统矩形按钮不够极简，原版为浅蓝紫色圆球向上白色箭头气泡（↑）；
6. **侧栏列表翻页体验**：绿色“加载更多会话”文本链接笨拙，且长列表滚动繁琐，需要极简高质感的紧凑微型分页器。

## 改动内容
1. **轨迹排障三大控制器联动（Duration、Turns、Calls）**：
   - `TrajectoryView.vue` 顶栏新增 `[Duration] [Turns] [Calls]` 紧凑控制按钮组；
   - `TrajectoryTimeline.vue`：支持 `actualDuration` prop，真实耗时模式按实际毫秒比例动态切片甘特图；
   - `TrajectoryLedger.vue`：支持 `allTurnsCollapsed` 与 `allCallsCollapsed`，支持独立 Turn Header 展开/折叠，Calls 折叠时自动收起/隐藏工具与子代理事件行。
2. **时间轴两段式双色甘特条与原版 Tooltip 深度对齐**：
   - `TrajectoryTimeline.vue`：ASSISTANT 色块展现浅紫（TTFT 首 token 等待）+ 深紫（Decoding 文本生成）原版双色段渐变，带蓝紫微光细边框；
   - Tooltip 对齐原版格式：首行大写类别（`ASSISTANT`）、次行时间跨度（`16:21:30.584 → 16:21:33.078`）、第三行细目（`Total 2,494 ms · TTFT 2,126 ms · Decoding 368 ms`）。
3. **顶栏大字概览**：
   - 增加原版同款 `X 轮 · Y 步 · Z 工具` 大字高亮展示，异常时追加标红 `· W 异常`。
4. **底部工业级指标栏（Metrics Strip）与全链路遥测打点**：
   - `apps/runtime-service` 的 `modeling.py`：为 `ChatOpenAI` 和 `ChatDeepSeek` 开启 `stream_usage=True`，让流式最后一个 chunk 完整回传官方 Token 统计；
   - `trajectory-adapter.ts` 与 `ChatSession.vue`：支持智能耗时与 Token 推导，彻底消灭历史记录中的 `Total 0 ms` 与“LLM 就绪”降级态，完整展示原版工业级指标：
     `X 轮 · Y 步 | LLM Xs | 首 token 平均 ... · ... tok/s | 缓存命中 ...% | 输入 ... tok · 输出 ... tok`。
5. **发送/停止按钮微交互升级**：
   - `ChatComposer.vue` 将发送按钮升级为原版浅蓝紫色圆球向上白色箭头（↑）微交互气泡，运行中平滑过渡为红色圆形停止按钮，内嵌 sr-only 保持语义无障碍与单测兼容。
6. **侧栏高质感微型分页器**：
   - `ChatThreadSidebar.vue` 彻底移除粗糙的绿色“加载更多会话”文本按钮，改为底部 32px 紧凑微型数字分页条（`第 1 页 (20 条)`、`‹` `1` `›`）；
   - `ChatPage.vue` 实现真正的 `handlePageChange` 单页切换，彻底告别列表滚动的繁重体验。

## 涉及文件
- `apps/runtime-service/src/runtime_service/runtime/modeling.py`
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/chat/trajectory/types.ts`
- `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts`
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryTimeline.vue`
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryLedger.vue`
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryView.vue`
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryView.spec.ts`

## 验证结果
- `runtime-service` pytest: 8 passed in 5.64s, 100% 绿灯
- `pnpm --filter platform-web run typecheck`: 0 error
- `pnpm --filter platform-web run lint`: 0 error, 0 warning
- `pnpm --filter platform-web test:run`: 47 passed, 143 passed, 100% 绿灯
- `pnpm --filter platform-web build`: 打包成功通过
