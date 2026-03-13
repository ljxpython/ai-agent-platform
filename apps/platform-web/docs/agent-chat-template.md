# Agent Chat Template 开发与使用说明

## 1. 目标

这份文档定义 `platform-web` 中“Agent 专属 Chat 页面”的推荐开发方式。

目标不是重写一套新的聊天基础设施，而是：

- 把当前已经成熟的 chat 页面沉淀为一个可复用的基础模板
- 让未来新 agent 可以快速获得自己的专属前端页面
- 保持当前默认 chat 功能稳定，不因为 agent 定制而被污染
- 为后续二次优化（专属面板、结果展示、动作按钮、图表等）留出清晰扩展点

## 2. 当前推荐路线

当前推荐采用：

- **基础模板 + Agent 页面薄包装**

也就是说：

1. 保留当前 chat 的 provider 体系与运行协议
2. 把当前 chat 页面沉淀为一个基础模板（Base Chat Template）
3. 每个 agent 页面只负责：
   - 固定 assistant / graph
   - 固定 apiUrl（如果需要）
   - 固定 targetType
   - 传入页面标题、说明、默认参数
4. 后续如需更强定制，再在模板层上增加扩展点

当前实现已经落地到：

- 默认 chat：`src/app/workspace/chat/page.tsx`
- 基础模板：`src/components/chat-template/base-chat-template.tsx`
- SQL Agent 示例页：`src/app/workspace/sql-agent/page.tsx`

## 3. 为什么这样做

这个方案的优点：

- 不破坏当前默认 chat
- 能最快支持第一个 agent 专属页面
- 不需要一上来设计过重的模板系统
- 可以逐步演进为真正的模板/插件架构

不推荐的做法：

- 直接在当前 `Thread` 里大量加 `if/else`
- 让 agent 专属 UI 直接侵入 `StreamProvider` / `ThreadProvider`
- 一开始就复制整套 chat 运行时与 provider 再自由改动

## 4. 当前 chat 的真实结构

当前 `/workspace/chat` 入口非常薄：

- `src/app/workspace/chat/page.tsx`

它只是组合：

- `ThreadProvider`
- `StreamProvider`
- `ArtifactProvider`
- `Thread`

这意味着：

- provider 层已经是稳定的运行时基础设施
- 真正需要被抽象成“模板”的，主要是 `Thread` 对应的 UI 壳层

## 5. 什么应该被视为模板核心

这些能力建议保留为核心基础设施，不让每个 agent 页面自己重造：

- `WorkspaceContext`
- `ThreadProvider`
- `StreamProvider`
- `ArtifactProvider`
- thread / stream / artifact 的协议
- URL query-state 约定

原因：

- 这些属于运行时与状态管理，不属于页面模板本身
- 如果每个 agent 页面都改这层，后续会很难维护

## 6. 什么应该被视为模板层

这些部分适合被抽象成可复用模板：

- 页面标题 / 描述
- 默认 assistant / graph / targetType / apiUrl
- header
- starter prompts
- history panel 是否显示
- artifact panel 是否显示
- run options 是否显示
- 空状态文案
- 页面布局（单栏 / 双栏 / 带右侧结果面板）

## 7. 当前推荐的实现心智模型

推荐把未来能力理解为：

- **Base Chat Template**：稳定的通用模板
- **Agent Wrapper Page**：薄包装页面

### 7.1 Base Chat Template 的职责

负责：

- 组合 provider
- 初始化默认参数
- 渲染通用 chat 骨架
- 决定用户是否还能修改 assistant / graph / apiUrl
- 保持与现有 `Thread` 能力兼容

### 7.2 Agent Wrapper Page 的职责

负责：

- 指定模板使用的 assistant / graph
- 指定标题与描述
- 指定默认 query 参数
- 指定该 agent 允许的功能开关

它应该尽量薄，不承载复杂运行逻辑。

## 8. 后续新 agent 的推荐开发方式

当后续新增一个 agent，需要一个专属 chat 页面时，建议流程是：

1. 明确它是否只需要“固定参数 + 复用默认 chat”
2. 如果是，优先基于 Base Chat Template 开一个包装页
3. 只在确实有 UI 差异时，才增加专属 slot / panel / renderer
4. 仍然尽量不碰 provider 协议

## 9. 团队开发约定：什么时候复用，什么时候复制

当前团队约定如下：

### 9.1 默认策略：先复用模板

后续新增 chat 型 agent 页面时，默认先：

1. 基于 `BaseChatTemplate` 新建页面
2. 固定 `assistantId / graphId / targetType / apiUrl`
3. 通过 feature flags 和少量 slot 完成页面差异化

### 9.2 允许复制，但只复制模板页面层

如果某个 agent 页面未来需要明显独立演化，可以复制一份“模板页面层”到自己的目录里继续开发。

这里允许复制的对象是：

- `BaseChatTemplate`
- 或者基于它包出来的页面壳层
- 与页面布局直接相关的局部 UI 组件

### 9.3 默认不要复制底层运行时

默认不要复制这些层：

- `StreamProvider`
- `ThreadProvider`
- `ArtifactProvider`
- thread / stream / artifact 协议逻辑

除非未来明确决定让某个 agent 页面彻底脱离当前 chat 运行时体系。

### 9.4 什么时候可以正式分叉

出现以下情况时，可以考虑从模板分叉：

- 页面布局明显不同于当前 chat
- 聊天不再是页面主体，结果区/工作台成为主体
- 页面需要大量 agent 专属状态和控制逻辑
- 模板里开始出现太多该 agent 的专属判断
- 该页面确认会长期独立演化

一句话规则：

> 默认先复用模板；当某个 agent 页面明显超出模板边界时，允许复制模板页面层并独立演化。

## 10. 参数建议

基础模板建议支持以下输入：

- `title`
- `description`
- `assistantId`
- `graphId`
- `targetType`
- `apiUrl`
- `projectId`
- `allowAssistantSwitch`
- `allowApiUrlEdit`
- `allowRunOptions`
- `showHistory`
- `showArtifacts`

其中：

- 对大多数 agent 页面，`assistantId` / `graphId` / `targetType` / `apiUrl` 可以固定
- 这样用户进入页面后，不需要再手工输入这些信息

## 11. 推荐的第一阶段接口草案

第一阶段不追求完整插件系统，只定义一个“够用、稳定”的基础模板接口。

### 11.1 目标绑定

```ts
type ChatTargetType = "assistant" | "graph";

type ChatTargetConfig = {
  targetType: ChatTargetType;
  assistantId?: string;
  graphId?: string;
  apiUrl?: string;
  projectId?: string;
};
```

说明：

- `targetType=assistant` 时优先使用 `assistantId`
- `targetType=graph` 时优先使用 `graphId`
- `apiUrl` 可以固定，也可以继续沿用现有默认解析逻辑

### 11.2 展示配置

```ts
type BaseChatTemplateDisplayConfig = {
  title: string;
  description?: string;
  emptyTitle?: string;
  emptyDescription?: string;
};
```

### 11.3 功能开关

```ts
type BaseChatTemplateFeatureFlags = {
  allowAssistantSwitch?: boolean;
  allowApiUrlEdit?: boolean;
  allowRunOptions?: boolean;
  showHistory?: boolean;
  showArtifacts?: boolean;
  showContextBar?: boolean;
};
```

### 11.4 扩展插槽

```ts
type BaseChatTemplateSlots = {
  headerSlot?: ReactNode;
  emptyStateSlot?: ReactNode;
  rightPanelSlot?: ReactNode;
};
```

### 11.5 总 props

```ts
type BaseChatTemplateProps = {
  target: ChatTargetConfig;
  display: BaseChatTemplateDisplayConfig;
  features?: BaseChatTemplateFeatureFlags;
  slots?: BaseChatTemplateSlots;
};
```

## 12. 什么是第一阶段必须实现的

第一阶段建议优先支持：

- 固定 `assistantId / graphId / targetType / apiUrl`
- 页面标题 / 描述
- `showHistory`
- `showArtifacts`
- `allowRunOptions`
- `headerSlot`
- `emptyStateSlot`
- `rightPanelSlot`

这已经足够支撑第一个 agent 专属页面。

## 13. 哪些能力以后再做

第一阶段不建议一上来实现：

- 完整模板注册中心
- 大而全的插件系统
- 任意 message renderer DSL
- 任意 artifact renderer DSL

这些能力可以在后续出现更多 agent 页面后再补。

## 14. 第二阶段演进方向

当平台里出现多个 agent 专属页面后，再考虑演进为：

- 模板注册表
- 模板 slot
- message renderer 扩展点
- artifact renderer 扩展点
- action bar 扩展点

这时基础模板就能升级为真正的“Agent Chat Template Kit”。

## 15. 当前开发约定

后续 agent 开发请遵循以下约定：

1. 默认 chat 页面始终保持可用，不因新 agent 定制被破坏
2. 新 agent 页面优先做“薄包装 + 固定参数”
3. provider 层默认不做 agent-specific 分叉
4. UI 差异优先在模板层解决，不在底层 runtime 层解决
5. 需要专属体验时，先复用模板，再逐步增加扩展点
6. 如果页面长期独立演化，优先复制模板页面层，不要直接复制底层 provider

## 16. 新 agent 页面推荐开发流程

1. 新建 `src/app/workspace/<agent-page>/page.tsx`
2. 引入 `BaseChatTemplate`
3. 固定该 agent 需要的 `assistantId / graphId / targetType / apiUrl`
4. 按需设置 `showHistory / showArtifacts / allowRunOptions`
5. 如果需要专属说明或结果面板，再传 slot
6. 如果后续发现该页面已经明显超出模板边界，再评估是否复制模板页面层独立维护

## 17. 一句话原则

> 先复用 `BaseChatTemplate` 快速生成 agent 页面；只有当某个页面明显超出模板边界时，才复制模板页面层并独立演化。
