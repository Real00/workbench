export type ContentFormat = 'markdown' | 'html'
export type SourceStatus = 'idle' | 'ok' | 'error' | 'running'

export interface SubscriptionPlugin {
  id: string
  name: string
  description: string
  script: string
  builtin: boolean
  created_at: string
  updated_at: string
}

export interface SubscriptionSource {
  id: string
  name: string
  url: string
  plugin_id: string
  config: Record<string, unknown>
  enabled: boolean
  interval_minutes: number
  last_fetched_at: string | null
  last_status: SourceStatus
  last_error: string
  created_at: string
  updated_at: string
}

export interface SubscriptionArticle {
  id: string
  source_id: string
  external_id: string
  title: string
  content: string
  content_format: ContentFormat
  published_at: string | null
  author: string
  cover_url: string | null
  url: string | null
  fetched_at: string
}

export interface PluginInput {
  name: string
  description?: string
  script: string
}

export interface SourceInput {
  name: string
  url: string
  plugin_id: string
  config?: Record<string, unknown>
  enabled?: boolean
  interval_minutes?: number
}
