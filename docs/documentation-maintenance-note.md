# Documentation Maintenance Note

文档类型：`Maintenance Note`

这份说明用于约束今后仓库再次重构时，哪些文档应该先更新、哪些文档只能保留为历史或设计说明，以及如何避免“代码已重构、文档还在讲旧架构”的漂移。

## 1. 更新顺序

当正式链路、正式宿主、端口、默认入口、主资源路径发生变化时，按下面顺序更新：

1. 代码与 contract
2. Canonical docs
3. App current docs / app README
4. Local design docs
5. Knowledge docs
6. Diagram source + export

## 2. 文档分类规则

### Canonical

典型文件：

- `docs/local-deployment-contract.yaml`
- `README.md`
- `README.en.md`
- `docs/local-dev.md`
- `docs/deployment-guide.md`
- `docs/env-matrix.md`

用途：

- 定义当前正式本地链路
- 定义当前正式宿主、端口、默认入口和默认 bring-up 方式

要求：

- 一旦正式链路变化，优先更新
- 不保留模糊历史口径
- 不把历史实现当成当前推荐入口

### Current App Docs

典型文件：

- 当前 app README
- 当前 app docs/README
- 当前 handbook / current API design docs

用途：

- 说明 app 在仓库 harness 中的当前角色
- 说明 app 当前真实资源、接口、职责边界和本地范式

要求：

- 必须与代码和 canonical docs 对齐
- 如需引用历史方案，必须明确当前差异和当前事实源

### Local Design

典型文件：

- 设计稿
- 局部抽象方案
- 未来方向说明

用途：

- 保留设计 rationale
- 解释为什么当前架构这样拆
- 记录未来可能继续抽象的方向

要求：

- 不得伪装成当前 API / 当前默认链路真相源
- 必须显式说明当前实现与本文的差异

### Historical-in-place

典型文件：

- 旧业务方案
- 旧工作区一期设计
- 退役接口说明

用途：

- 保留历史演进过程
- 给后续回溯和迁移对照提供上下文

要求：

- 必须显式标明历史身份
- 必须指出当前应该改读哪份文档
- 不得用现在时误导读者以为仍是当前实现

### Knowledge

典型文件：

- `docs/knowledge/**`

用途：

- 解释仓库总哲学、harness 方法论、操作模型

要求：

- 解释原则，不直接充当部署事实源
- 如果主链变化，需要确认叙事仍和当前正式主链一致

## 3. 哪些变化必须触发文档更新

下面任一变化发生时，都应触发一次文档排查：

- 正式宿主变化，例如 `platform-api` -> `platform-api`
- 正式前端入口变化，例如 `platform-web` -> `platform-web`
- 默认端口变化
- 默认启动顺序变化
- 默认接口前缀变化
- 结果域资源模型变化
- runtime 上下文注入规则变化
- diagram 与实际架构不再一致

## 4. Diagram 规则

涉及正式架构图或正式启动流程图时：

- `drawio` 与 `svg` 必须同一波更新
- 更新后必须 grep 扫描旧宿主名、旧端口和旧链路词
- 特别注意 SVG fallback 文本和 draw.io XML 里的截断标签

## 5. 最小排查清单

每次重构后，至少检查：

- 当前正式链路是否仍在 root docs 中一致
- 当前正式宿主是否仍在 app README / handbook 中一致
- 是否还有历史文档在用现在时描述旧实现
- diagrams 是否仍与当前主链一致
- supporting docs 是否仍把 canonical docs 作为默认事实源

## 6. 一句话原则

先更新 code/contract，再更新 canonical docs；保留历史，但必须把“历史”和“当前”写清楚。
