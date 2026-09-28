/** @vitest-environment happy-dom */
import { describe, expect, it } from 'vitest'
import { sanitizeHtml } from './html'

describe('sanitizeHtml', () => {
  it('keeps safe markup and http images', () => {
    const html = sanitizeHtml('<p>hi <strong>there</strong></p><img src="https://cdn.example/a.png" alt="a">')
    expect(html).toContain('<p>')
    expect(html).toContain('<strong>')
    expect(html).toContain('https://cdn.example/a.png')
    expect(html).toContain('loading="lazy"')
  })

  it('strips scripts and javascript urls', () => {
    const html = sanitizeHtml('<p>x</p><script>alert(1)</script><a href="javascript:alert(1)">x</a><img src="javascript:alert(1)">')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('javascript:')
  })

  it('forces noreferrer on links', () => {
    const html = sanitizeHtml('<a href="https://example.com">link</a>')
    expect(html).toContain('rel="noreferrer"')
    expect(html).toContain('target="_blank"')
  })
})
