# 知识文档上传使用说明

- Date: 2026-04-20
- Audience: `platform-web` `/knowledge/documents` 页面使用者
- Status: current usage guide
- Related:
  - `04-platform-web-knowledge-workspace-plan.md`
  - `03-platform-api-project-knowledge-design.md`
  - `.omx/plans/prd-knowledge-documents-upload-ux-20260420.md`

## 1. 这份文档解决什么问题

这份文档只回答一件事：

> 在 `/knowledge/documents` 上传文档时，`默认 tags`、`默认 layer`、逐文件覆盖、快速上传分别应该怎么用，什么场景下最合适。

它是**使用说明**，不是新的协议设计文档。

## 2. 先记住三个结论

1. **默认 tags / 默认 layer 只对当前这一次上传对话框生效**
   - 不是项目全局配置
   - 不是知识库永久默认值

2. **完整上传对话框是主路径**
   - 适合需要认真补 metadata 的上传
   - 支持批量默认值 + 逐文件覆盖

3. **快速上传是次路径**
   - 适合“先传进去再说”
   - 当前不提供逐文件 metadata 确认

## 3. 两条上传路径分别适合什么场景

### 3.1 上传文档（推荐默认路径）

适合：

- 你希望上传时就把 metadata 带好
- 你要控制后续检索范围
- 你这批文件大体属于同一类，但少数文件需要逐个修正
- 你希望失败文件留在对话框里继续重试

特点：

- 先选文件
- 再填批量默认值
- 再逐文件确认 / 覆盖
- 混合成功失败时，对话框不会直接关闭

### 3.2 快速上传（次路径）

适合：

- 临时导入
- 批量补历史文档但暂时顾不上 metadata
- 先验证文件是否能成功进入处理流水线

当前限制：

- 不走逐文件 metadata 编辑
- 不适合对检索质量要求高的正式入库场景

## 4. `tags` 和 `layer` 分别是什么

### 4.1 tags

`tags` 是**可多选主题标签**。

例如：

- `architecture`
- `network`
- `storage`
- `compute`
- `frontend`
- `runtime`
- `rag`
- `testcase`

输入方式：

- 在 UI 中按逗号分隔输入
- 前端会转成 `string[]`

例如：

```text
architecture, storage, network
```

会变成：

```json
["architecture", "storage", "network"]
```

### 4.2 layer

`layer` 是**单值的大层级分类**。

当前前端推荐值：

- `infrastructure`
- `application`
- `component`

建议理解为：

- `infrastructure`：底层架构、网络、存储、计算、调度
- `application`：应用层、页面、业务流程、功能说明
- `component`：基础组件、通用模块、SDK、公共封装

> 注意：
>
> 这些是 **AITestLab 当前推荐值**，用于帮助团队形成一致录入习惯；
> 它们不是 LightRAG 上游协议的固定保留字段集合。

## 5. 默认 tags / 默认 layer 现在到底怎么生效

它们是这次上传批次里的**默认 metadata**。

### 5.1 默认行为：所有文件先“继承默认值”

选中文件后，每个文件初始状态都是：

- tags：继承默认 tags
- layer：继承默认 layer

也就是说，如果你设置了：

- 默认 tags = `architecture`
- 默认 layer = `infrastructure`

那么所有未单独修改的文件，最终都会带上这两个值。

### 5.2 它是“实时继承”，不是“复制一份”

当前实现是 **live-computed**。

这意味着：

- 你先选了文件
- 后改了默认 tags / 默认 layer
- 只要某个文件还处于“继承默认值”状态，它就会跟着新的默认值一起变化

它不是：

- 选文件那一刻拷贝一份默认值
- 后面再也不动

### 5.3 单个文件可以切到“覆盖”

如果某个文件不想跟默认值走，可以对它单独切换：

- 覆盖 tags
- 覆盖 layer

这样它就只使用本文件自己的值，不再跟随批量默认值。

## 6. 什么叫“显式清空”

逐文件覆盖时，每个字段支持三种语义：

- `inherit`：继承默认值
- `replace`：使用本文件自己的值
- `explicit clear`：明确不要继承，且值就是空

### 6.1 tags 的显式清空

例如：

- 默认 tags = `architecture, storage`
- 某个文件切到“覆盖 tags”
- 但输入框保持空

含义不是“没填”，而是：

> 这个文件明确不继承默认 tags，最终 tags 为空。

### 6.2 layer 的显式清空

例如：

- 默认 layer = `infrastructure`
- 某个文件切到“覆盖 layer”
- 选择“不设置”

含义是：

> 这个文件明确不继承默认 layer。

这个能力适合“多数文件属于同一类，但个别文件不应带这个分类”的场景。

## 7. 推荐使用姿势

### 场景 A：一批都是底层架构文档

例如：

- 网络设计
- 存储方案
- 计算节点说明

建议：

- 默认 layer：`infrastructure`
- 默认 tags：`architecture`

再对少量文件逐个补：

- `network`
- `storage`
- `compute`

### 场景 B：大多数文件属于同一层，少量例外

例如：

- 8 份底层文档
- 2 份应用侧接入说明

建议：

- 默认 layer 先设成多数派：`infrastructure`
- 那 2 份例外文件逐个覆盖成：`application`

这样比逐个填写更省事，也更不容易漏。

### 场景 C：单文件上传但想精确分类

即使只传 1 个文件，也推荐走完整上传对话框。

这时：

- 上方默认值区域可以当快捷填写区
- 下方逐文件确认就是最终确认区

适合正式入库。

### 场景 D：只是临时导入

如果你只是：

- 先把文件放进去
- 先验证流水线是否可跑
- 暂时不关心检索质量

可以走快速上传。

但要接受：

- 这批文件当前 metadata 不完整
- 后续按 tags/layer 检索的质量会更弱

## 8. 建议的录入习惯

推荐团队内把语义分工固定为：

- **layer = 大层级**
- **tags = 主题 / 模块 / 能力点**

推荐示例：

| 文档类型 | layer | 常见 tags |
| --- | --- | --- |
| 底层架构总览 | `infrastructure` | `architecture` |
| 网络相关设计 | `infrastructure` | `architecture`, `network` |
| 存储相关设计 | `infrastructure` | `architecture`, `storage` |
| 计算/调度设计 | `infrastructure` | `architecture`, `compute` |
| 前端页面说明 | `application` | `frontend` |
| 业务流程/API 接入 | `application` | `workflow`, `api` |
| 基础组件/SDK | `component` | `component`, `sdk`, `runtime` |

## 9. 这和后续检索有什么关系

上传时填的 metadata，不只是“存一下”。

后续检索时可以用它们做：

- 范围过滤
- 优先召回
- 结果解释

例如你想问：

> 解释当前项目的底层架构

更理想的检索范围会倾向于：

- `tags_any=["architecture"]`
- `attributes.layer=["infrastructure"]`

这样可以减少把应用层文档一起召回进来的情况。

## 10. 常见误解

### 误解 A：默认值是项目全局默认

不是。

它只属于当前这个上传对话框会话。

### 误解 B：默认值在选文件时就固定下来了

不是。

当前实现是实时继承，只要文件还在 `inherit` 状态，就会跟着默认值变化。

### 误解 C：快速上传也会带上这套 metadata

不是。

快速上传当前是 metadata-lite 的次路径。

### 误解 D：留空就是“没设置”

不完全是。

如果某个文件已经切到了“覆盖”模式，再留空，就表示：

- tags：显式清空
- layer：显式清空

## 11. 当前版本的边界

当前文档说明的是：

- 上传时如何录入 metadata
- UI 里如何继承 / 覆盖 / 清空
- 它如何帮助后续 retrieval scope 更干净

当前不承诺：

- 自动推荐 tags
- 自动识别 layer
- 项目级固定 taxonomy 配置中心
- 快速上传自动补 metadata

这些如果后续需要，再单独扩展。
