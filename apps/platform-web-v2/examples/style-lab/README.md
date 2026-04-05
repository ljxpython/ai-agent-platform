# Platform Web V2 Style Lab

这个目录用于保存 `platform-web-v2` 的视觉样板，作为后续页面迁移和 UI 评审时的固定参考。

它不是正式业务代码，也不直接参与构建。

## 当前内容

- `index.html`：样板入口
- `styles.css`：3 套整体风格样式
- `styles.js`：风格切换脚本

## 使用方式

直接用浏览器打开 `index.html` 即可预览。

当前提供三套方向：

- `A. Refine HR 系`
- `B. Workspace Neutral`
- `C. Soft Admin`

三套都采用相同的信息架构：

- 左侧主导航
- 顶部上下文条
- 主内容区

当前已支持：

- 一键切换主题
- 主题选择持久化到浏览器本地存储
- 页面刷新后保持上次选择的风格

当前主推荐方向：

- `A. Refine HR 系`

这套样式明确参考了 `https://hr.refine.dev/overview` 的企业后台气质：

- 克制
- 轻量
- 中性色为主
- 少量强调色
- 不带 AI 演示风

后续 `platform-web-v2` 的正式页面开发，应优先参考这里的布局节奏、信息密度和色彩方向。
