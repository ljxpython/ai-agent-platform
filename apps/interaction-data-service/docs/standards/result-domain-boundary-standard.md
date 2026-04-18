# Interaction Data Service 结果域边界标准

文档类型：`Current Standard`

这份文档定义 `interaction-data-service` 的 **结果域边界与 leaf resolver 标准**。

它回答的是：

> 当一个需求落在结果域服务时，AI 应该先按哪份权威事实判断“当前接口是什么”“结果域拥有权在哪里”“平台应如何访问它”？

---

## 1. 适用范围

命中下面情况，优先读本文：

- 新增或修改结果域资源
- 判断某个数据是否应属于结果域服务
- 判断平台访问结果域时是否应经过 control plane
- 判断 runtime 写入结果域时的边界责任
- 判断 `docs/README.md`、`test-case-service-api-design.md`、`service-design.md` 哪份是当前真相源

### 1.1 当前主线与通用 pattern

本文同时覆盖两层语义：

1. **当前主线实例**
   - 当前已正式落地的结果域切片：`/api/test-case-service`
2. **通用结果域 pattern**
   - 未来新增结果域切片时，应该继续遵守的边界

因此：

- 当前接口/字段/资源判断，以 testcase 这条主线为事实样本
- 通用 pattern 只负责约束以后怎么继续长，不把 testcase 现状误写成唯一固定业务语义

---

## 2. 核心边界

### 2.1 这是结果域服务，不是控制面后端

它负责：

- 结果域资源的 HTTP API
- 结果域表与资产路径
- 结果域自己的资源语义

它不负责：

- 平台权限 / 项目成员 / 治理主数据
- runtime graph 执行
- 平台工作区聚合与权限校验

### 2.2 平台正式读取继续走 control plane

正式平台链路固定为：

```text
platform-web-vue -> platform-api-v2 -> interaction-data-service
```

因此：

- `platform-web-vue` 不应把正式页面直接接到本服务
- `platform-api-v2` 负责治理、聚合、下载/预览代理与协议整形

### 2.3 runtime 通过稳定 HTTP 契约写入结果域

`runtime-service` 可以直接写入本服务，但只限于：

- 稳定的结果域 HTTP 契约
- 明确的业务切片前缀
- 明确的资源所有权

`interaction-data-service` 不接管 runtime 编排逻辑。

### 2.4 当前主线优先切片资源，不回退成万能入口

当前正式主线是：

- 一个 runtime 业务服务一个专属结果域前缀
- 当前真实前缀：`/api/test-case-service`

不要为了抽象而回退到大一统 records 入口。

对未来新切片同样成立：

- 优先保持专属资源语义
- 先讲清资源所有权、接口契约和访问链路
- 再考虑是否存在可复用的结果域 pattern

---

## 3. leaf resolver rule

### Leaf A：current API / resource / payload truth

先读：

- `docs/test-case-service-api-design.md`

适用于：

- 当前资源
- 当前 payload / route / field / table 语义

### Leaf B：result-domain ownership / formal access chain

先读：

- `README.md`
- `docs/README.md`
- 本文

适用于：

- 结果域边界
- 平台访问是否必须经由 `platform-api-v2`
- runtime 写入和平台读取的正式关系

### Leaf C：background design / future abstraction

先读：

- `docs/service-design.md`

适用于：

- 为什么结果域应该独立存在
- 未来如何继续抽象
- 不直接作为当前实现真相

### 组合规则

- 如果问题是 **“当前接口/资源/字段到底是什么？”**
  - 先读 **Leaf A**
- 如果问题是 **“这东西应不应该归结果域拥有、平台怎么访问它？”**
  - 先读 **Leaf B**
- 如果问题是 **“未来还能怎么继续抽象？”**
  - 再读 **Leaf C**

---

## 4. 验证规则

对 `interaction-data-service` 的验证顺序固定为：

1. 先验证本服务自己的 API / 表 / 资源行为
2. 再验证最短相关链
   - `runtime-service -> interaction-data-service`
   - 或 `platform-api-v2 -> interaction-data-service`
3. 只有当正式平台读取行为本身被改动时，才要求完整平台链路验证

不要默认把结果域验证抬升成全平台链路验证。
