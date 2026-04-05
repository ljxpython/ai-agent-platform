# Platform Web V2 迁移方案

更新时间：2026-04-01

## 1. 总体策略

本轮迁移不是“一次性替换旧前端”，而是：

- 在 `apps/platform-web-v2` 中先把新版 UI 基座搭好
- 按页面分批承接旧 `platform-web` 的能力
- 在迁移完成前，允许旧前端继续承担现有联调职责

这套方案的核心优点：

- 风险隔离
- 迁移路径清晰
- 可以持续展示阶段性成果

## 2. 迁移原则

1. 不先重构业务协议
2. 不先重写所有 provider
3. 不先追求 100% 页面覆盖
4. 先搭基座，后迁页面
5. 每迁完一页，都能单独验证

## 3. 保留与迁移边界

### 当前保留

- `platform-api` 现有管理接口
- 旧 `platform-web` 当前联调能力
- 旧前端已验证过的业务契约

### 当前迁移

- 工作台壳子
- 页面母版
- 标准管理页
- 登录页

### 延后迁移

- chat / threads / stream 等复杂工作区
- testcase 这类有更强业务特征的页面

## 4. 分阶段迁移

### Phase 0：方案固化

产出：

- 新 app 目录
- UI 基座方案文档
- 迁移策略文档

### Phase 1：UI Foundation

产出：

- `WorkspaceShellV2`
- `SidebarNav`
- `TopContextBar`
- `PlatformPage`
- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- 主题系统（默认 `Refine HR 系`，支持一键切换主题）

### Phase 2：首批页面迁移

产出：

- 登录页
- 项目页
- 用户页
- 助手页

### Phase 3：管理页扩展

产出：

- Graphs
- Audit
- Profile / Security
- Project detail / Members

### Phase 4：复杂工作区迁移

产出：

- Chat
- Threads
- SQL Agent
- Testcase

## 5. 迁移过程中的关键控制

### 控制 1：不做双向耦合

`platform-web-v2` 不要一边建新结构，一边再去反改旧 `platform-web`。

### 控制 2：优先复制，再抽象

对于旧页面逻辑，前期迁移允许先复制，再在新 app 内重构为统一母版。

### 控制 3：先保证视觉统一，再做局部高级交互

别一上来就在动画和花活上发疯。先把整体壳子打稳。

## 6. 当前推荐的第一步

真正开始写代码时，建议从下面顺序启动：

1. 初始化 `platform-web-v2`
2. 接入最小样式体系和 `shadcn/ui`
3. 完成新版工作台壳子
4. 完成主题 token 和主题切换
5. 先做登录页和项目页
6. 再迁移用户页和助手页
