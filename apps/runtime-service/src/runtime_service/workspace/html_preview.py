"""Static HTML preview: safe scripts/styles/fonts with zero-origin-trust isolation."""

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

HTML_CSP = (
    "default-src 'none'; "
    "img-src data: https: blob:; "
    "style-src 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
    "font-src https://fonts.gstatic.com data:; "
    "script-src 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
    "connect-src https:; "
    "frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
)

TAGS = {
    "html",
    "head",
    "body",
    "meta",
    "title",
    "link",
    "style",
    "script",
    "div",
    "span",
    "p",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "code",
    "blockquote",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "caption",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "small",
    "sub",
    "sup",
    "section",
    "article",
    "header",
    "footer",
    "main",
    "aside",
    "figure",
    "figcaption",
    "img",
    "svg",
    "g",
    "path",
    "circle",
    "rect",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "defs",
    "clippath",
    "use",
}

ATTRS = {
    "class",
    "id",
    "title",
    "style",
    "alt",
    "width",
    "height",
    "colspan",
    "rowspan",
    "rel",
    "href",
    "src",
    "crossorigin",
    "type",
    "integrity",
    "name",
    "content",
    "charset",
    "viewbox",
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "d",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "points",
    "transform",
    "opacity",
}

SELF_CLOSING = {"br", "hr", "img", "link", "meta"}


class _StaticHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = None
        self.raw_tag = None

    def handle_starttag(self, tag, attrs):
        if self.skip:
            return
        tag_lower = tag.lower()
        if tag_lower in {"base"}:
            return
        if tag_lower in {"iframe", "object", "embed", "form", "template"}:
            self.skip = tag_lower
            return
        if tag_lower not in TAGS:
            return

        # 检查是否为 meta refresh 跳转
        if tag_lower == "meta":
            attrs_dict = {k.lower(): (v or "") for k, v in attrs}
            if attrs_dict.get("http-equiv", "").lower() == "refresh":
                return

        safe = []
        for name, value in attrs:
            if value is None:
                continue
            name_lower = name.lower()
            if name_lower.startswith("on"):
                # 剔除所有内联事件处理函数 (onclick, onerror 等)
                continue
            if name_lower not in ATTRS:
                continue

            # 针对 URL 属性做协议白名单过滤
            if name_lower in {"href", "src"}:
                val_clean = value.strip()
                val_lower = val_clean.lower()
                if val_lower.startswith("javascript:") or val_lower.startswith(
                    "vbscript:"
                ):
                    continue
                if tag_lower == "img" and val_lower.startswith("data:image/"):
                    safe.append(f' {name}="{escape(value, quote=True)}"')
                    continue
                parsed = urlparse(val_clean)
                if parsed.scheme and parsed.scheme.lower() not in {"https", "http"}:
                    continue

            safe.append(f' {name}="{escape(value, quote=True)}"')

        if tag_lower in {"script", "style"}:
            self.raw_tag = tag_lower

        if tag_lower in SELF_CLOSING:
            self.parts.append("<" + tag_lower + "".join(safe) + " />")
        else:
            self.parts.append("<" + tag_lower + "".join(safe) + ">")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if self.skip:
            if tag_lower == self.skip:
                self.skip = None
            return
        if tag_lower in SELF_CLOSING:
            return
        if tag_lower in TAGS:
            if self.raw_tag == tag_lower:
                self.raw_tag = None
            self.parts.append("</" + tag_lower + ">")

    def handle_data(self, data):
        if self.skip:
            return
        if self.raw_tag in {"script", "style"}:
            # script 和 style 标签内部保持原始代码，避免破坏 JavaScript/CSS 语法
            self.parts.append(data)
        else:
            self.parts.append(escape(data))


def safe_html(source: str) -> str:
    parser = _StaticHTML()
    parser.feed(source)
    parser.close()
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="'
        + escape(HTML_CSP, quote=True)
        + '">'
        '<meta name="referrer" content="no-referrer"></head><body>'
        + "".join(parser.parts)
        + "</body></html>"
    )
