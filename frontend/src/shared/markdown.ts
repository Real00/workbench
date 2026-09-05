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

function renderInline(raw: string): string {
  const codeSpans: string[] = []
  let text = raw.replace(/`([^`]+)`/g, (_, code: string) => {
    codeSpans.push(`<code>${escapeHtml(code)}</code>`)
    return `\u0000${codeSpans.length - 1}\u0000`
  })
  text = escapeHtml(text)
  text = text.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_match, label: string, url: string) =>
      `<a href="${url}" target="_blank" rel="noreferrer">${label}</a>`,
  )
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  text = text.replace(/\u0000(\d+)\u0000/g, (_, index: string) => codeSpans[Number(index)] ?? '')
  return text
}

/** 免依赖的轻量 Markdown 渲染：先转义全部 HTML 再按行组装，安全输出。
 *  支持标题、列表、引用、围栏代码、加粗/斜体/行内代码/链接、分段与换行。 */
export function renderMarkdown(source: string): string {
  const lines = (source ?? '').replace(/\r\n?/g, '\n').split('\n')
  const html: string[] = []
  let paragraph: string[] = []
  let list: 'ul' | 'ol' | null = null
  let quote = false
  let inFence = false
  let fenceBuffer: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) {
      html.push(`<p>${paragraph.map(renderInline).join('<br>')}</p>`)
      paragraph = []
    }
  }
  const closeList = () => {
    if (list) {
      html.push(`</${list}>`)
      list = null
    }
  }
  const closeQuote = () => {
    if (quote) {
      html.push('</blockquote>')
      quote = false
    }
  }

  for (const line of lines) {
    const fence = line.match(/^```\w*\s*$/)
    if (fence) {
      flushParagraph()
      closeList()
      closeQuote()
      if (!inFence) {
        inFence = true
        fenceBuffer = []
      } else {
        html.push(`<pre class="md-pre"><code>${escapeHtml(fenceBuffer.join('\n'))}</code></pre>`)
        inFence = false
      }
      continue
    }
    if (inFence) {
      fenceBuffer.push(line)
      continue
    }
    if (!line.trim()) {
      flushParagraph()
      closeList()
      closeQuote()
      continue
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/)
    if (heading) {
      flushParagraph()
      closeList()
      closeQuote()
      const level = heading[1].length + 1
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      continue
    }
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) {
      flushParagraph()
      closeList()
      closeQuote()
      html.push('<hr>')
      continue
    }
    const quoteLine = line.match(/^>\s?(.*)$/)
    if (quoteLine) {
      flushParagraph()
      closeList()
      if (!quote) {
        html.push('<blockquote>')
        quote = true
      }
      html.push(`<p>${renderInline(quoteLine[1])}</p>`)
      continue
    }
    closeQuote()
    const ulLine = line.match(/^\s*[-*+]\s+(.*)$/)
    const olLine = line.match(/^\s*\d+[.、]\s+(.*)$/)
    if (ulLine || olLine) {
      flushParagraph()
      const kind = ulLine ? 'ul' : 'ol'
      if (list !== kind) {
        closeList()
        html.push(`<${kind}>`)
        list = kind
      }
      html.push(`<li>${renderInline((ulLine ?? olLine)![1])}</li>`)
      continue
    }
    if (list) closeList()
    paragraph.push(line)
  }
  if (inFence) html.push(`<pre class="md-pre"><code>${escapeHtml(fenceBuffer.join('\n'))}</code></pre>`)
  flushParagraph()
  closeList()
  closeQuote()
  return html.join('\n')
}
