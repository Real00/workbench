/** @vitest-environment happy-dom */
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('keeps numbered list items as an ordered list', () => {
    const html = renderMarkdown(
      '目前共有 4 个项目：\n\n1. **3A-DevOps**\n2. **ARTHUB一站**\n3. **AgentStudio**\n4. **MYAI**\n\n需要查看某个项目下的任务详情吗？',
    )
    expect(html).toContain('<ol>')
    expect(html).toContain('<li><strong>3A-DevOps</strong></li>')
    expect(html).toContain('<li><strong>MYAI</strong></li>')
    expect(html).toContain('</ol>')
  })

  it('renders GFM tables', () => {
    const html = renderMarkdown('| 项目 | 状态 |\n| --- | --- |\n| MYAI | 进行中 |')
    expect(html).toContain('<table>')
    expect(html).toContain('<th>项目</th>')
    expect(html).toContain('<td>MYAI</td>')
    expect(html).toContain('md-table-wrap')
  })

  it('accepts Chinese numbered list markers', () => {
    const html = renderMarkdown('1、第一项\n2、第二项')
    expect(html).toContain('<ol>')
    expect(html).toContain('第一项')
  })

  it('strips raw HTML from the model', () => {
    const html = renderMarkdown('看这里 <script>alert(1)</script> **加粗**')
    expect(html).not.toContain('<script')
    expect(html).toContain('<strong>加粗</strong>')
  })
})
