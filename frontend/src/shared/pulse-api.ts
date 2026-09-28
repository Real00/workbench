import { streamSse, api } from './api/client'
import type { AiStreamEvent } from '../modules/progress/types'
import type { PulseAttachmentMeta } from './pulse-session'

export interface PulseMention {
  type: 'task' | 'member' | 'project' | 'document' | 'tool'
  id: string | null
  label: string
}

export interface PulseRunPayload {
  instruction: string
  context_task_id?: string
  context_document_id?: string
  session_id?: string | null
  mentions?: PulseMention[]
  attachment_ids?: string[]
  rewind_exchanges?: number
}

export const pulseApi = {
  run: async (
    payload: PulseRunPayload,
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal,
  ) => {
    await streamSse('/ai/run', payload, event => onEvent(event as AiStreamEvent), signal)
  },
  confirm: async (confirmation_token: string) => (
    await api.post('/ai/confirm', { confirmation_token })
  ).data,
  uploadAttachment: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return (await api.post<PulseAttachmentMeta>('/ai/attachments', form, {
      timeout: 60_000,
      transformRequest: [(data, headers) => {
        if (headers && 'delete' in headers) headers.delete('Content-Type')
        return data
      }],
    })).data
  },
}
