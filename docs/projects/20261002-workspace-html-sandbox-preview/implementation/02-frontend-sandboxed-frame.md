# 前端沙箱权限放通与文案更新

## 改动时间
2026-10-02

## 相关任务
- Task 2.1: 更新 SandboxedHtmlFrame 沙箱权限与徽章文案

## 改动文件
- `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue`
- `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.spec.ts`

## 具体改动

### 1. 放行 allow-scripts 权限并更新文案
**位置：** `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue:39, 61`

**改动内容：**
- 将 iframe 的 `sandbox=""` 改为 `sandbox="allow-scripts"`。在不提供 `allow-same-origin` 的前提下，浏览器将 iframe 的 Origin 强制锁定为 `null`，既允许 Tailwind CDN 等运行时脚本解析样式，又彻底剥离了跨域访问父页面 DOM、Cookie、LocalStorage 的能力。
- 顶部控制条的说明徽章从“禁用脚本与外链”更新为“独立脚本沙箱 (零同源凭据)”，准确向用户表达安全隔离状态。

### 2. 补充单元测试
**位置：** `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.spec.ts`

**改动内容：**
- 新增单元测试断言 iframe 属性包含 `sandbox="allow-scripts"` 和 `referrerpolicy="no-referrer"`，且徽章正常渲染。

## 验证
- [x] 单元测试通过 (`SandboxedHtmlFrame.spec.ts` 1 passed, `WorkspacePreview.spec.ts` 3 passed)
- [x] ESLint / TypeScript 检查通过
