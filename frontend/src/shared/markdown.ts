import DOMPurify from 'dompurify'
import { marked, type Tokens } from 'marked'

const ESCAPE_MAP: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, ch => ESCAPE_MAP[ch] ?? ch)
}

function safeHttpUrl(href: string): string | null {
  try {
    const url = new URL(href, 'https://invalid.local')
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null
  } catch {
    return null
  }
}

const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'del', 'code', 'pre', 'a', 'ul', 'ol', 'li',
  'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'input',
]

const ALLOWED_ATTR = [
  'href', 'title', 'target', 'rel', 'class', 'align', 'colspan', 'rowspan',
  'type', 'disabled', 'checked',
]

marked.use({
  gfm: true,
  breaks: true,
  renderer: {
    html() {
      return ''
    },
    code({ text, lang }: Tokens.Code) {
      const cls = lang ? ` class="language-${escapeHtml(lang)}"` : ''
      return `<pre class="md-pre"><code${cls}>${escapeHtml(text)}</code></pre>\n`
    },
    link({ href, title, tokens }: Tokens.Link) {
      const url = safeHttpUrl(href)
      const label = this.parser.parseInline(tokens)
      if (!url) return label
      const extra = title ? ` title="${escapeHtml(title)}"` : ''
      return `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer"${extra}>${label}</a>`
    },
    image({ text }: Tokens.Image) {
      return escapeHtml(text)
    },
  },
})

/** 模型常写「1、」且后面不一定有空格；GFM 只认「1.」 */
function normalizeListMarkers(source: string): string {
  return source.replace(/^(\s*\d+)、\s*/gm, '$1. ')
}

function wrapTables(html: string): string {
  return html.replaceAll('<table>', '<div class="md-table-wrap"><table>').replaceAll('</table>', '</table></div>')
}

/** GFM Markdown → 消毒后的 HTML。表格、删除线、任务列表走 marked；原始 HTML 丢弃。 */
export function renderMarkdown(source: string): string {
  const dirty = marked.parse(normalizeListMarkers(source ?? ''), { async: false })
  const html = typeof dirty === 'string' ? dirty : ''
  // 包一层再消毒：部分 DOM 实现会丢掉作为根节点的 table/ol
  const clean = DOMPurify.sanitize(`<div data-md-root="1">${html}</div>`, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: [...ALLOWED_ATTR, 'data-md-root'],
  })
  return wrapTables(
    clean.replace(/^<div data-md-root="1">/, '').replace(/<\/div>$/, ''),
  )
}
