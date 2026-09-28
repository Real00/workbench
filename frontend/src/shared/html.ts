import DOMPurify from 'dompurify'

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

const HTML_ALLOWED_TAGS = [
  'p', 'br', 'strong', 'b', 'em', 'i', 'del', 's', 'u', 'code', 'pre', 'a',
  'ul', 'ol', 'li', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'span', 'figure', 'figcaption',
  'img', 'section', 'article', 'header', 'footer', 'main',
]

const HTML_ALLOWED_ATTR = [
  'href', 'title', 'target', 'rel', 'class', 'align', 'colspan', 'rowspan',
  'src', 'alt', 'width', 'height', 'loading',
]

/** 先去掉脚本/样式等危险标签，再走 DOMPurify 白名单。 */
function stripDangerous(source: string): string {
  return source
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<iframe\b[^>]*>[\s\S]*?<\/iframe>/gi, '')
    .replace(/<object\b[^>]*>[\s\S]*?<\/object>/gi, '')
    .replace(/<embed\b[^>]*>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
}

/** 订阅文章 HTML → 消毒后的安全 HTML（允许常见阅读标签与 http(s) 图片）。 */
export function sanitizeHtml(source: string): string {
  const dirty = stripDangerous(source ?? '')
  const clean = DOMPurify.sanitize(`<div data-html-root="1">${dirty}</div>`, {
    ALLOWED_TAGS: HTML_ALLOWED_TAGS,
    ALLOWED_ATTR: [...HTML_ALLOWED_ATTR, 'data-html-root'],
    ALLOW_DATA_ATTR: false,
    ADD_ATTR: ['target'],
  })
  let html = clean.replace(/^<div data-html-root="1">/, '').replace(/<\/div>$/, '')
  html = html.replace(/<a\b([^>]*)>/gi, (_match, attrs: string) => {
    const hrefMatch = attrs.match(/\bhref=["']([^"']*)["']/i)
    const href = hrefMatch ? safeHttpUrl(hrefMatch[1]) : null
    if (!href) return '<a>'
    return `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">`
  })
  html = html.replace(/<img\b([^>]*)>/gi, (_match, attrs: string) => {
    const srcMatch = attrs.match(/\bsrc=["']([^"']*)["']/i)
    const src = srcMatch ? safeHttpUrl(srcMatch[1]) : null
    if (!src) return ''
    const altMatch = attrs.match(/\balt=["']([^"']*)["']/i)
    const alt = altMatch ? escapeHtml(altMatch[1]) : ''
    return `<img src="${escapeHtml(src)}" alt="${alt}" loading="lazy">`
  })
  return html.replaceAll('<table>', '<div class="md-table-wrap"><table>').replaceAll('</table>', '</table></div>')
}
