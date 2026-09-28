import { describe, expect, it } from 'vitest'
import { isImeKeyEvent } from './ime'

function keyEvent(partial: Partial<KeyboardEvent> & { key: string }): KeyboardEvent {
  return {
    isComposing: false,
    keyCode: 0,
    ...partial,
  } as KeyboardEvent
}

describe('isImeKeyEvent', () => {
  it('blocks while the browser reports composition', () => {
    expect(isImeKeyEvent(keyEvent({ key: 'Enter', isComposing: true }))).toBe(true)
  })

  it('blocks while a local composing flag is set', () => {
    expect(isImeKeyEvent(keyEvent({ key: 'Enter' }), true)).toBe(true)
  })

  it('blocks IME process keys used by some engines', () => {
    expect(isImeKeyEvent(keyEvent({ key: 'Enter', keyCode: 229 }))).toBe(true)
    expect(isImeKeyEvent(keyEvent({ key: 'Process' }))).toBe(true)
  })

  it('blocks Enter briefly after compositionend (macOS candidate confirm)', () => {
    expect(isImeKeyEvent(keyEvent({ key: 'Enter' }), false, 200, 150)).toBe(true)
    expect(isImeKeyEvent(keyEvent({ key: 'Enter' }), false, 200, 250)).toBe(false)
  })

  it('allows normal Enter when idle', () => {
    expect(isImeKeyEvent(keyEvent({ key: 'Enter' }), false, 0, 1000)).toBe(false)
  })
})
