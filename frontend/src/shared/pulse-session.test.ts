import { describe, expect, it } from 'vitest'
import {
  defaultAttachmentPrompt,
  dropTurnsFrom,
  findUserTurn,
  isSupportedPulseAttachment,
  namedPastedFile,
  rewindCompletedExchanges,
} from './pulse-session'

describe('pulse-session', () => {
  it('accepts markdown, text and word attachments', () => {
    expect(isSupportedPulseAttachment('纪要.md')).toBe(true)
    expect(isSupportedPulseAttachment('notes.TXT')).toBe(true)
    expect(isSupportedPulseAttachment('brief.docx')).toBe(true)
    expect(isSupportedPulseAttachment('slides.pdf')).toBe(false)
    expect(isSupportedPulseAttachment('image.png')).toBe(false)
  })

  it('names untitled pasted text as a supported file', () => {
    const named = namedPastedFile(new File(['hello'], 'blob', { type: 'text/plain' }))
    expect(named.name).toBe('粘贴.txt')
    expect(isSupportedPulseAttachment(named.name)).toBe(true)
  })

  it('counts only completed exchanges when rewinding for edit', () => {
    const turns = [
      { id: 1, role: 'user' as const },
      { id: 2, role: 'assistant' as const, completed: true },
      { id: 3, role: 'user' as const },
      { id: 4, role: 'assistant' as const, completed: true },
      { id: 5, role: 'user' as const },
      { id: 6, role: 'assistant' as const, completed: false },
    ]
    expect(rewindCompletedExchanges(turns, 3)).toBe(1)
    expect(rewindCompletedExchanges(turns, 5)).toBe(0)
    expect(rewindCompletedExchanges(turns, 1)).toBe(2)
  })

  it('drops the edited turn and everything after it', () => {
    const turns = [{ id: 1 }, { id: 2 }, { id: 3 }]
    expect(dropTurnsFrom(turns, 2).map(item => item.id)).toEqual([1])
    expect(dropTurnsFrom(turns, 9)).toEqual(turns)
  })

  it('finds the user turn that produced an assistant reply', () => {
    const turns = [
      { id: 1, role: 'user' },
      { id: 2, role: 'assistant' },
      { id: 3, role: 'user' },
      { id: 4, role: 'assistant' },
    ]
    expect(findUserTurn(turns, turns[3]!)?.id).toBe(3)
    expect(findUserTurn(turns, turns[0]!)).toBeUndefined()
  })

  it('uses a knowledge-save fallback when only files are sent', () => {
    expect(defaultAttachmentPrompt()).toMatch(/知识库/)
  })
})
