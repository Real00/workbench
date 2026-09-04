import { describe, expect, it } from 'vitest'
import { clothingHex, deskHair, memberHasDeskWork, memberPixelUri } from './pixel-avatar'

function decodePixelSvg(uri: string) {
  const payload = uri.slice(uri.indexOf(',') + 1)
  if (uri.includes(';base64,')) return atob(payload)
  return decodeURIComponent(payload)
}

describe('member pixel desk', () => {
  it('把成员色收成 6 位 hex，非法值回退青', () => {
    expect(clothingHex('#36d9e9')).toBe('36d9e9')
    expect(clothingHex('not-a-color')).toBe('36d9e9')
  })

  it('有进行中任务才显示笔记本', () => {
    expect(memberHasDeskWork(2)).toBe(true)
    expect(memberHasDeskWork(0)).toBe(false)
  })

  it('用 DiceBear pixel-art 生成稳定 SVG', () => {
    const first = memberPixelUri('member-1', '#36d9e9')
    const again = memberPixelUri('member-1', '#36d9e9')
    expect(first).toBe(again)
    expect(first.startsWith('data:image/svg+xml')).toBe(true)
  })

  it('排除几乎没头发的短发款', () => {
    expect(deskHair).not.toContain('short23')
    expect(deskHair).not.toContain('short21')
    expect(deskHair).not.toContain('short07')
    expect(deskHair).not.toContain('short05')
    expect(deskHair).toContain('long01')
  })

  it('生成的形象不含稀疏短发路径', () => {
    for (const seed of ['member-1', 'a', 'b', 'c', 'idle', 'busy', 'alpha', 'beta']) {
      const svg = decodePixelSvg(memberPixelUri(seed, '#36d9e9'))
      expect(svg).not.toContain('d="M6 2h4v1H6z"')
      expect(svg).not.toContain('d="M7 1h2v2H7z"')
    }
  })
})
