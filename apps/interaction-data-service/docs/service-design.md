# interaction-data-service 设计稿

状态：`Local Design`

这篇文档保留的是 `interaction-data-service` 更泛化的结果域设计思路，用于解释“为什么结果域要独立存在、未来如果继续抽象会往哪走”。

它不是当前 API 真相源。

## 当前实现与本文的差异

当前代码已经明确采用：

- 每个 runtime 业务服务一个专属接口前缀
- 当前真实前缀是 `/api/test-case-service`
- 当前真实资源是 `documents / test-cases / overview / batches`
- 当前真实表是 `test_case_documents / test_cases`
- 旧的 `/api/usecase-generation/*` 已退役
- 早期设想中的 `/api/records*` 并未成为当前正式主线

当前实现真相源请优先看：

- `app/api/test_case_service/**`
- `app/db/models.py`
- `README.md`
- `docs/README.md`
- `docs/test-case-service-api-design.md`

## 为什么还保留这篇文档

虽然当前实现先沿 testcase 业务切片落地，但下面这些设计判断仍然有价值：

1. `interaction-data-service` 应该是结果域，不是平台控制面后端
2. 平台治理、runtime 执行、结果域持久化应继续分层
3. 平台读取结果时仍应优先经由 `platform-api-v2`
4. 新结果域切片应先讲清接口契约、资源模型和表所有权，再扩展页面与 tool

换句话说，这篇文档保留的是“抽象方向”和“边界哲学”，不是“当前 REST 路由清单”。

## 当前正式边界

当前正式架构里：

```text
platform-web-vue
  -> platform-api-v2
    -> interaction-data-service

runtime-service
  -> interaction-data-service
```

因此本服务：

### 负责

- 结果域资源的落库与查询
- 结果域资源自己的接口契约
- 结果域资源自己的数据表与资产路径

### 不负责

- 用户鉴权、RBAC、项目成员治理
- runtime graph 执行
- 平台工作区聚合与项目权限校验
- 把所有业务结果强压成一个万能统一入口

## 这篇 Local Design 想表达的核心方向

### 1. 结果域应该独立存在

`interaction-data-service` 不是新的平台主后端，也不是通用数据库代理，而是：

> 为 runtime 结果与平台结果视图之间提供稳定结果域边界的独立服务。

### 2. 抽象可以存在，但不能先污染当前主线

本文保留一个更泛化的未来方向：如果后续结果域切片增多，可以考虑进一步抽象公共元数据、公共查询能力和类型注册机制。

但在当前阶段，不应该为了“抽象得更统一”而回退当前已经清晰落地的 `test-case-service` 专属资源设计。

### 3. 平台访问结果域时仍走控制面

当前正式平台前端是 `platform-web-vue`，正式控制面是 `platform-api-v2`。

因此正式读取链路应继续是：

```text
platform-web-vue
  -> platform-api-v2
    -> interaction-data-service
```

而不是让正式前端绕开治理层直连结果域。

## 如果未来继续抽象，哪些判断仍然成立

下面这些设计约束仍可视为未来扩展结果域时的参考：

### 1. 新结果域切片仍应保持专属资源语义

即便未来需要更多业务切片，也应优先保持：

- 一个业务切片一组清晰资源
- 一组资源对应自己拥有的数据表
- 平台层通过治理接口做聚合，而不是把所有业务资源揉平

### 2. 可考虑抽公共元数据，但不应牺牲业务可读性

未来如果切片增多，可以考虑抽象：

- 公共项目维度
- 公共批次维度
- 公共来源追踪元数据
- 公共聚合视图

但不应为了追求“抽象统一”而牺牲业务资源的可读性与可操作性。

### 3. 通信仍优先稳定 HTTP 契约

对当前仓库来说，结果域服务更适合作为稳定 HTTP 服务，而不是额外再包装成新的公共 MCP 主入口。

## 当前不再采用的旧方向

以下内容现在不应再被理解成当前实现：

- `/api/records` 作为正式统一外部入口
- `record_type` 作为当前外部资源设计主轴
- `/api/usecase-generation/*` 作为正式业务接口
- `platform-web -> platform-api -> interaction-data-service` 作为当前正式平台链路

这些内容只保留为历史设计思路或抽象方向参考。

## 推荐怎么使用这篇文档

- 想看当前接口怎么调：看 `docs/README.md` 和 `docs/test-case-service-api-design.md`
- 想看当前代码真相源：看 `app/api/test_case_service/**` 与 `app/db/models.py`
- 想理解“为什么结果域应该独立存在、后面还能怎么继续抽象”：看本文
