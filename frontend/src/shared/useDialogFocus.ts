import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const dialogs: symbol[] = []
const selector = 'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex="-1"])'

export function useDialogFocus(element: Ref<HTMLElement | null>, isOpen: () => boolean, close: () => void) {
  const id = Symbol('dialog')
  let previous: HTMLElement | null = null
  let active = false
  const focusable = () => Array.from(element.value?.querySelectorAll<HTMLElement>(selector) ?? []).filter(node => node.getClientRects().length > 0)
  function keydown(event: KeyboardEvent) {
    if (dialogs.at(-1) !== id || event.defaultPrevented) return
    if (event.key === 'Escape') {
      event.preventDefault()
      close()
    } else if (event.key === 'Tab') {
      const nodes = focusable()
      const first = nodes[0]
      const last = nodes.at(-1)
      if (!first) { event.preventDefault(); element.value?.focus(); return }
      if (event.shiftKey && (document.activeElement === first || !element.value?.contains(document.activeElement))) {
        event.preventDefault(); last?.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !element.value?.contains(document.activeElement))) {
        event.preventDefault(); first.focus()
      }
    }
  }
  function deactivate() {
    if (!active) return
    const wasTop = dialogs.at(-1) === id
    dialogs.splice(dialogs.indexOf(id), 1)
    document.removeEventListener('keydown', keydown)
    active = false
    if (wasTop && previous?.isConnected) previous.focus({ preventScroll: true })
  }
  watch(isOpen, async open => {
    if (!open) { deactivate(); return }
    previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    if (!isOpen() || !element.value) return
    if (!active) { dialogs.push(id); active = true; document.addEventListener('keydown', keydown) }
    const initial = element.value.querySelector<HTMLElement>('[autofocus]') ?? focusable()[0] ?? element.value
    initial.focus({ preventScroll: true })
  }, { immediate: true })
  onBeforeUnmount(deactivate)
}
