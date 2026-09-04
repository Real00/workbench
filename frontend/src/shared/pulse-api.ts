import { streamSse, api } from './api/client'
import type { AiStreamEvent } from '../modules/progress/types'

export interface PulseMention {
  type: 'task' | 'member' | 'project' | 'document' | 'tool'
  id: string | null
  label: string
}

export const pulseApi = {
  run: async (
    payload: { instruction: string; context_task_id?: string; context_document_id?: string; session_id?: string | null; mentions?: PulseMention[] },
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    await streamSse('/ai/run', payload, event => onEvent(event as AiStreamEvent), signal)
  },
  confirm: async (confirmation_token: string) => (
    await api.post('/ai/confirm', { confirmation_token })
  ).data,
}
