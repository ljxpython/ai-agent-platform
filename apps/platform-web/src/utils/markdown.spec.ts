import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown", () => {
  it("应当保留安全的 http 和 https 链接及图片", () => {
    const md =
      "[Google](https://google.com) ![Logo](http://example.com/logo.png)";
    const html = renderMarkdown(md);
    expect(html).toContain('href="https://google.com"');
    expect(html).toContain('src="http://example.com/logo.png"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noreferrer noopener"');
  });

  it("应当支持并保留 blob: 对象 URL（用于工作区产物及图表预览）", () => {
    const blobUrl =
      "blob:http://127.0.0.1:3000/6fa2d2a4-7934-4b53-997e-d8e7c2e0b503";
    const md = `![趋势图表](${blobUrl})`;
    const html = renderMarkdown(md);
    expect(html).toContain(`src="${blobUrl}"`);
    expect(html).toContain('alt="趋势图表"');
  });

  it("应当保留站内相对路径与锚点", () => {
    const md = "[回到顶部](#top) ![内部图片](/workspace/charts/demo.png)";
    const html = renderMarkdown(md);
    expect(html).toContain('href="#top"');
    expect(html).toContain('src="/workspace/charts/demo.png"');
  });

  it("应当拦截 javascript: 与 data: 危险伪协议并降级为 #", () => {
    const attackMd =
      "[攻击链接](javascript:alert(1)) ![XSS](javascript:void(0)) ![DataXSS](data:image/png;base64,abc)";
    const html = renderMarkdown(attackMd);
    expect(html).not.toContain("javascript:alert(1)");
    expect(html).not.toContain("javascript:void(0)");
    expect(html).not.toContain("data:image/png;base64,abc");
    expect(html).toContain('href="#"');
    expect(html).toContain('src="#"');
  });

  it("应当正确渲染表格并包裹样式容器", () => {
    const md = "| A | B |\n|---|---|\n| 1 | 2 |";
    const html = renderMarkdown(md);
    expect(html).toContain('<div class="pw-markdown-table"><table>');
    expect(html).toContain("</table></div>");
  });

  it("应当转义代码块中的 HTML 字符防御 XSS", () => {
    const md = "```html\n<script>alert(1)</script>\n```";
    const html = renderMarkdown(md);
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
  });
});
