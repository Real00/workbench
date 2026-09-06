import { isDesktopShell } from './api/client'

/**
 * 桌面壳专用联动：监听 Rust 侧全局快捷键/托盘发出的 quick-capture 事件，
 * 打开应用内已有的快速记录对话框。仅桌面壳动态加载 Tauri API，网页端零开销。
 */
export function setupDesktopBridge(handlers: { quickCapture: () => void }): () => void {
  if (!isDesktopShell) return () => {}
  let unlisten: (() => void) | undefined
  void (async () => {
    try {
      const { listen } = await import('@tauri-apps/api/event')
      unlisten = await listen('quick-capture', () => handlers.quickCapture())
    } catch (error) {
      console.warn('桌面桥接初始化失败', error)
    }
  })()
  return () => unlisten?.()
}
