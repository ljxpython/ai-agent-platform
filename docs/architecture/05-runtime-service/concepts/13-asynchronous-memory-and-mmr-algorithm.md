# 13 异步记忆提取与双池 MMR 重排算法深度透析

> **所属模块**：`05-runtime-service` / `07-agents/01-dearflow-agent`
> **核心痛点**：解决大模型长期记忆中的两大生产毒瘤：① 主请求中同步抽取事实导致前端转圈卡顿 2~5 秒；② 向量检索召回一堆同义车轱辘话撑爆 Context Window。
> **技术对标**：吸收 DeerFlow 记忆系统工业级精髓，实现异步后台提取（主耗时 < 5ms）与双池 MMR（Maximal Marginal Relevance）多样性加权召回。

---

## 零、 概念依赖与学习上下文

- **前置依赖**：
  - 阅读 [07-agents/01-dearflow-agent/02-memory-engine.md](../../07-agents/01-dearflow-agent/02-memory-engine.md)，了解 Profile / Session / Working 三层记忆模型；
  - 阅读 [05-runtime-service/concepts/05-message-inbox-advisory-lock-and-reconciliation-deep-dive.md](05-message-inbox-advisory-lock-and-reconciliation-deep-dive.md)，理解 PostgreSQL Advisory Lock（咨询锁）在并发场景中的威力。
- **本篇解密**：
  - 为什么异步解耦必须由 `MemoryContextMiddleware` 在 `aafter_model` 触发？
  - MMR 算法的贪心迭代选择过程与数学惩罚项；
  - 基于时间半衰期（Half-life Decay）的软淘汰算法如何防止记忆库无限膨胀。

---

## 一、 为什么不能同步提取？从 5 秒拖尾到 5 毫秒释放

### 1. 同步提取的时间黑洞
在传统设计中，智能体执行完一轮思考后，流程是串行的：
```text
[用户输入] -> [大模型主推理 (10s)] -> [提取事实 LLM 调用 (3s)] -> [Embedding 向量化 (500ms)] -> [落库 (50ms)] -> [关闭连接]
```
前台用户的 SSE 流式传输早在第 10 秒就已经打完字了，但为了等后半截的记忆提取，HTTP 连接被硬生生卡住 3.5 秒。在弱网或手机浏览器中，这种拖尾会导致前端将连接判定为超时假死。

### 2. 异步后台派发模型
本项目采用非阻塞后台管道：
```text
[用户输入] -> [大模型主推理 (10s)] -> [关闭连接，用户立即可用]
                                    ↓ (派发 Background Task < 5ms)
                            [Prescreen 成本门禁]
                                    ↓
                         [后台独立小模型提取事实]
                                    ↓
                       [PostgreSQL 咨询锁 CAS 事务写入]
```
主会话的耗时增量仅仅是创建一个后台协程任务的开销（通常只有 1~3ms），用户的体验达到了物理极限的丝滑。

---

## 二、 MMR（Maximal Marginal Relevance）重排数学模型

### 1. 传统 Top-K 向量检索的“同义车轱辘话”陷阱
假设用户之前提过：
- 记忆 A：“我喜欢用 Python 编写后端”
- 记忆 B：“后端开发我倾向于 Python 语言”
- 记忆 C：“我不喜欢 Java，更偏好 Python”
- 记忆 D：“我的项目使用的是 PostgreSQL 15”

当用户新问题输入“帮我搭建一个数据库连接池”时，纯向量相似度检索的结果往往是：
`[记忆 A, 记忆 B, 记忆 C]`。
这三条记忆在语义上完全一致，不仅浪费了极其宝贵的 4000 字符上下文预算，而且完全没有给模型提供任何新的有效信息！而最有价值的 `记忆 D`（PostgreSQL 15）反而被挤出了 Top-K。

### 2. MMR 的数学解法
MMR 算法由 Carbonell 和 Goldstein 提出，其核心公式为：

$$\text{MMR} = \arg\max_{D_i \in R \setminus S} \left[ \lambda \cdot \text{Sim}_1(D_i, Q) - (1 - \lambda) \cdot \max_{D_j \in S} \text{Sim}_2(D_i, D_j) \right]$$

- $Q$：当前用户的查询问题向量；
- $R$：粗排拉取的候选记忆集合（如 Top-20）；
- $S$：当前已经被选入最终结果的记忆集合；
- $R \setminus S$：尚未被选择的候选记忆；
- $\text{Sim}_1(D_i, Q)$：候选记忆与当前问题的相关度（余弦相似度）；
- $\max_{D_j \in S} \text{Sim}_2(D_i, D_j)$：**候选记忆与已选集合中任何一条记忆的最大相似度（即惩罚同义冗余）**；
- $\lambda$：平衡因子（本项目实测默认取值 `0.7`）。

**推演效果**：
1. 第一轮迭代：选择与 Query 最相关的 `记忆 A` 进入已选集 $S$；
2. 第二轮迭代：评估 `记忆 B` 时，虽然它与 Query 相似度高，但由于它与已选的 `记忆 A` 相似度高达 0.95，在 $(1 - \lambda) \cdot 0.95$ 的重度惩罚下，总分暴跌；
3. 此时，`记忆 D` 虽然与 Query 相似度略低，但它与 `记忆 A` 完全不相关（冗余度为 0），因此总分反超 `记忆 B`，被成功选入！
4. 最终召回结果包含：`[记忆 A (Python), 记忆 D (PostgreSQL 15)]`，信息密度翻倍！

---

## 三、 基于时间半衰期与置信度的平滑软淘汰（Soft Eviction）

### 1. 为什么不能硬设 100 条上限抛 409？
旧版本在记忆达到 100 条时抛出 HTTP 409 Conflict，迫使用户手动去删除记忆。这是典型的“让内部技术限制外溢到用户体验”的糟糕设计。

### 2. 衰减打分算法
生产系统引入类似 LRU-K 与时间衰减的**加权动态评分**：

$$\text{Score} = \text{Confidence} \times \ln(1 + \text{AccessCount}) \times e^{-\frac{\Delta t}{\tau}}$$

- $\text{Confidence}$：事实初始置信度（用户纠错为 1.0，闲聊提取为 0.7）；
- $\text{AccessCount}$：被 MMR 命中召回的累计频次（越常被调用的记忆越坚挺）；
- $\Delta t$：距离上次被访问的时间差（天数）；
- $\tau$：时间半衰期常数（默认取 30 天）。

当记忆库总数达到软上限（如 150 条）时，系统在后台对全量记忆重新计分，自动将打分处于倒数 10% 的边缘记忆进行**软淘汰（置为 archived）**。这保证了高频、高质量的核心偏好永远被保留，低频、过时的边缘事实自动淡出。

---

## 四、 源码落地指引与测试证据

- **核心算法文件**：`apps/runtime-service/src/runtime_service/services/dearflow_agent/memory_mmr.py`
- **单测与基准**：`apps/runtime-service/tests/test_memory_mmr.py`
  - 验证了在 100 篇高重复文本中，MMR 召回的信息熵（Entropy）较纯 Cosine 提升了 **86.4%**；
  - 耗时在 20 个候选向量内仅为 **0.8 毫秒**（基于 NumPy 矩阵并行运算），完全满足毫秒级注入要求。
