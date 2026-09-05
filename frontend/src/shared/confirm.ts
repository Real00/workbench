import { reactive } from 'vue'

export interface ConfirmOptions {
  title: string
  message?: string
  confirmText?: string
  /** 默认按危险操作渲染（红键 + 警示图标） */
  danger?: boolean
}

const state = reactive({
  open: false,
  title: '',
  message: '',
  confirmText: '确认',
  danger: true,
})

let resolver: ((ok: boolean) => void) | null = null

/** 危险操作确认：await confirmDialog({ title, message }) 返回是否确认 */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  state.open = true
  state.title = options.title
  state.message = options.message ?? ''
  state.confirmText = options.confirmText ?? '确认'
  state.danger = options.danger ?? true
  return new Promise(resolve => {
    resolver = resolve
  })
}

export function confirmState() {
  return state
}

export function resolveConfirm(ok: boolean) {
  if (!state.open) return
  state.open = false
  resolver?.(ok)
  resolver = null
}
