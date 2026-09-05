/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 云端 API 地址，如 https://api.example.com；同源部署留空 */
  readonly VITE_API_BASE_URL?: string
}
