// @vitest-environment happy-dom
import { afterEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import ConfirmDialog from './ConfirmDialog.vue'
import { confirmDialog, resolveConfirm } from './confirm'

let app: App | undefined
let host: HTMLDivElement | undefined

afterEach(() => {
  resolveConfirm(false)
  app?.unmount()
  host?.remove()
  document.body.innerHTML = ''
})

async function open() {
  host = document.createElement('div')
  document.body.append(host)
  app = createApp(ConfirmDialog)
  app.mount(host)
  const result = confirmDialog({ title: '更新测试', confirmText: '开始更新' })
  await nextTick()
  await nextTick()
  return { result }
}

describe('确认框的按钮与自动关闭顺序', () => {
  it('点击确认返回 true，不被组件的关闭事件抢先取消', async () => {
    const { result } = await open()
    const button = document.querySelector<HTMLButtonElement>('[data-slot="alert-dialog-action"]')
    expect(button).not.toBeNull()
    button!.click()
    expect(await result).toBe(true)
  })

  it('点击取消返回 false', async () => {
    const { result } = await open()
    document.querySelector<HTMLButtonElement>('[data-slot="alert-dialog-cancel"]')!.click()
    expect(await result).toBe(false)
  })
})
