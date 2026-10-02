# DearFlow Agent 接入 Jina Reader 网页深度提取 - 整体方案

## 背景
当前平台中的 DearFlow Agent 网络研究能力包含两个工具：`search_web`（搜索）和 `fetch_page`（抓取正文）。
目前两者均统一绑定在 Tavily 服务上。在实际工程与深度调研场景中存在两个痛点：
1. **Tavily 额度消耗大**：Tavily 免费每月仅 1,000 次调用，若 `search` 和 `extract` 全走 Tavily，单次多源调研需消耗 5~10 点，额度快速告罄；
2. **现代复杂网页抓取受限**：大量现代网站依赖客户端 JS 动态渲染（SPA/CSR），普通静态抽取拿不到完整有效内容，且常常夹带冗余的导航条、广告和弹窗噪音。

借鉴原版 Deer-Flow 的优秀工程实践，将 `Tavily Search` 与 `Jina Reader`（`https://r.jina.ai`）深度结合，实现“Tavily 搜源头 + Jina 读正文”的高效协同。

## 目标
1. 升级 `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py`，实现 `jina_reader` 高效客户端；
2. 在 `fetch_page` 中构建 Jina 首选 + Tavily 自动降级的双引擎架构；
3. 严格保留现有的 SHA256 证据链落盘与 `public_url` SSRF 安全防线；
4. 环境变量兼容 `JINA_API_KEY` 与 `JINA_KEY`，并完成本地环境配置注入；
5. 新增单测，覆盖 Jina 正常读取、Jina 异常时自动降级 Tavily、以及两家均失效时的标准异常抛出。

## 方案设计

### 整体架构
```
                [ fetch_page(url, runtime) ]
                             │
                             ▼
                 [ public_url(url) 安全校验 ]
                             │ (通过)
                             ▼
                 ┌───────────────────────────┐
                 │ 优先调用：Jina Reader      │
                 │ GET https://r.jina.ai/{url}│
                 │ Headers: X-Return-Format  │
                 └─────────────┬─────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │ (成功返回 Markdown)                  │ (超时 / 5xx / 无 Key)
            ▼                                     ▼
   [ 组装 page_text 数据 ]               ┌───────────────────────────┐
            │                            │ 降级调用：Tavily Extract   │
            │                            └─────────────┬─────────────┘
            │                                          │ (成功)
            │                                          ▼
            │                                 [ 组装 page_text 数据 ]
            │                                          │
            └──────────────────┬───────────────────────┘
                               │
                               ▼
           [ _evidence(workspace, runtime, records) ]
           • 计算 raw_content 的 SHA256
           • 原子硬链接写入 /workspace/sources/{sha256}.txt
           • 构造 ToolMessage.artifact 元数据
```

### 关键改动点

#### 1. 新增 Jina Reader 请求函数与控制协议
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py`
- **函数：** `async def jina_extract(url: str) -> dict`
- **配置与协议：**
  - 读取 `os.environ.get("JINA_API_KEY") or os.environ.get("JINA_KEY")`；
  - 请求 URL：`https://r.jina.ai/{url}`；
  - Headers:
    - `Authorization: Bearer <key>`（若有 key）；
    - `X-Return-Format: markdown`；
    - `X-Timeout: 20`；
    - `Accept: text/plain, text/markdown, application/json`；
  - 限制流式读取大小不超过 1MB。

#### 2. `fetch_page` 双通道平滑降级改造
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py`
- **逻辑：**
  - 首先尝试 `jina_extract(url)`；
  - 若 Jina 抛出异常（网络错误、服务端错误、解析失败）或未配置 Jina Key，捕获异常后记录日志并降级调用 `tavily("extract", ...)`；
  - 最终获取的文本交由现有的 `_evidence(workspace, runtime, records)` 进行统一证据链落盘。

#### 3. Agent 工具暴露策略对齐
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
- **逻辑：**
  - 只要配置了 `TAVILY_API_KEY` 或 `JINA_API_KEY`/`JINA_KEY` 其中之一，`fetch_page` 即可保持可用；
  - 仅在两者皆无时，才下架 `fetch_page`。

## 风险和依赖
- **依赖：** `~/.my_best/.env` 中的 `JINA_KEY`；
- **风险：** Jina Reader 海外网络偶发超时 → **应对：** 超时限制 20s，超时后瞬时降级 Tavily Extract，对外保持零感知。

## 实施计划
1. **Phase 1: 配置注入与 search.py Jina 实现**：
   - 从 `~/.my_best/.env` 导入配置到 `apps/runtime-service/.env`；
   - 在 `search.py` 中实现 `jina_extract` 与双通道降级逻辑；
2. **Phase 2: 单元测试覆盖与断言验证**：
   - 编写 Jina 提取、降级 Tavily、双失败异常的针对性测试用例；
3. **Phase 3: 真实网络调用端到端回归**：
   - 真实请求网页测试 Markdown 提取效果与工作区证据文件落盘。
