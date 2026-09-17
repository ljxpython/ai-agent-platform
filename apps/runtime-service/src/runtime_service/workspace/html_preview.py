"""Static HTML preview: no scripts, navigation, forms or external resources."""

from html import escape
from html.parser import HTMLParser

HTML_CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
TAGS = {
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
    "style",
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
}


class _StaticHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = None

    def handle_starttag(self, tag, attrs):
        if self.skip:
            return
        if tag in {"script", "iframe", "object", "svg", "math", "template"}:
            self.skip = tag
            return
        if tag not in TAGS:
            return
        safe = []
        for name, value in attrs:
            if value is not None and (
                name in ATTRS
                or tag == "img"
                and name == "src"
                and value.startswith(
                    (
                        "data:image/png;base64,",
                        "data:image/jpeg;base64,",
                        "data:image/webp;base64,",
                    )
                )
            ):
                safe.append(f' {name}="{escape(value, quote=True)}"')
        self.parts.append("<" + tag + "".join(safe) + ">")

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip:
                self.skip = None
            return
        if tag in TAGS:
            self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.skip:
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
