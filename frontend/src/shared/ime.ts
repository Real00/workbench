/** macOS 输入法确认候选后，Enter 的 keydown 常在 compositionend 之后到达 */
export const IME_ENTER_GUARD_MS = 120

/** 组字中或刚结束组字：不应触发 Enter 发送 / 提交 */
export function isImeKeyEvent(
  event: KeyboardEvent,
  composing = false,
  guardUntil = 0,
  now = typeof performance !== 'undefined' ? performance.now() : 0,
): boolean {
  return event.isComposing
    || composing
    || event.keyCode === 229
    || event.key === 'Process'
    || now < guardUntil
}
