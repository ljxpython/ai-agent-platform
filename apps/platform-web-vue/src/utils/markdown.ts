import MarkdownIt from 'markdown-it'
import type { RenderRule } from 'markdown-it/lib/renderer.mjs'

const markdownRenderer = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false
})

const defaultLinkOpen: RenderRule =
  markdownRenderer.renderer.rules.link_open ||
  ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))

markdownRenderer.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index]

  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noreferrer noopener')

  return defaultLinkOpen(tokens, index, options, env, self)
}

markdownRenderer.renderer.rules.table_open = () => '<div class="pw-markdown-table"><table>'
markdownRenderer.renderer.rules.table_close = () => '</table></div>'

markdownRenderer.renderer.rules.fence = ((tokens, index) => {
  const token = tokens[index]
  const info = typeof token.info === 'string' ? token.info.trim() : ''
  const language = info.split(/\s+/)[0]?.replace(/[^\w-]/g, '') || 'text'
  const escapedLanguage = markdownRenderer.utils.escapeHtml(language)
  const escapedCode = markdownRenderer.utils.escapeHtml(token.content.replace(/\n$/, ''))

  return [
    '<div class="pw-markdown-code">',
    '<div class="pw-markdown-code-header">',
    `<span>${escapedLanguage}</span>`,
    '<button type="button" class="pw-markdown-copy" data-copy-code>复制</button>',
    '</div>',
    `<pre><code class="language-${escapedLanguage}">${escapedCode}</code></pre>`,
    '</div>'
  ].join('')
}) satisfies RenderRule

export function renderMarkdown(source: string): string {
  return markdownRenderer.render(source || '')
}
