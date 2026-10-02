# 工作区 HTML 现代化沙箱渲染支持

## 项目概述
- **时间：** 2026-10-02 至 2026-10-02
- **目标：** 解决工作区 HTML 预览中 Tailwind CSS、Google Fonts 及常见现代化前端 CDN 样式完全丢失退化为无样式纯文本的问题，在杜绝同源凭据窃取与内网穿透的前提下提供高保真安全预览能力。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** done

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`, `runtime-service`
- **改动级别：** 链路改动
- **预计工作量：** 0.5 人天

## 关键决策
1. **精准沙箱原则（Precision Sandboxing）：** 前端 iframe 仅放权 `sandbox="allow-scripts"`，坚决不加 `allow-same-origin`。利用浏览器底层将 Origin 强制降级为 `null` 的安全机制，彻底阻断对宿主 DOM、Cookie、LocalStorage/SessionStorage 的跨域越权和伪造请求。
2. **CSP 外部静态白名单与内网阻断（CSP Perimeter）：** 后端配置强化版 CSP，放行常用公认安全 CDN（Tailwind CSS 官方 CDN、Google Fonts、cdnjs、jsdelivr、unpkg），但将 `connect-src` 严格限定为公网 `https:`，杜绝针对 `127.0.0.1` / `localhost` 本地控制面与服务的 SSRF 嗅探攻击。
3. **标签白名单适度扩充与危险协议封杀：** 后端 HTMLParser 白名单放行 `<link>`、`<script>`、`<svg>` 及合法属性，但对 `href`、`src` 进行协议校验，严禁 `javascript:` 伪协议、内联事件属性（如 `onclick`）及 `iframe` 嵌套。
