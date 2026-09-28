import { getApiBase, getToken, isDesktopShell } from './api/client'

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

/** 读取打包进桌面壳的应用版本（含 CI 写入的短 SHA，如 0.1.0+abcdef0） */
export async function getDesktopAppVersion(): Promise<string> {
  if (!isDesktopShell) return ''
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<string>('get_app_version')
}

/** 经工作台 API 下载最新 DMG 并用系统打开（需用户拖进 Applications） */
export async function downloadAndOpenDesktopDmg(downloadPath = '/system/desktop/dmg'): Promise<string> {
  if (!isDesktopShell) throw new Error('仅桌面端可下载客户端安装包')
  const base = (getApiBase() || window.location.origin).replace(/\/+$/, '')
  const path = downloadPath.startsWith('/') ? downloadPath : `/${downloadPath}`
  const url = `${base}/api/v1${path}`
  const token = getToken()
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<string>('download_and_open_dmg', {
    url,
    authorization: token ? `Bearer ${token}` : null,
  })
}
