export const PULSE_ATTACHMENT_ACCEPT = '.md,.txt,.docx'
export const PULSE_ATTACHMENT_EXTS = ['.md', '.txt', '.docx'] as const
export const PULSE_MAX_ATTACHMENTS = 8
export const PULSE_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

export interface PulseAttachmentMeta {
  id: string
  name: string
  size: number
  chars: number
}

export interface RewindableTurn {
  id: number
  role: 'user' | 'assistant'
  completed?: boolean
}

export function attachmentSuffix(name: string): string {
  const base = name.replace(/\\/g, '/').split('/').pop() ?? name
  const dot = base.lastIndexOf('.')
  return dot >= 0 ? base.slice(dot).toLowerCase() : ''
}

export function isSupportedPulseAttachment(name: string): boolean {
  return (PULSE_ATTACHMENT_EXTS as readonly string[]).includes(attachmentSuffix(name))
}

export function defaultAttachmentPrompt(): string {
  return '请阅读附件。若没有其它要求，把它存进知识库。'
}

export function rewindCompletedExchanges(turns: RewindableTurn[], fromUserTurnId: number): number {
  let started = false
  let count = 0
  for (const turn of turns) {
    if (turn.id === fromUserTurnId) started = true
    if (!started) continue
    if (turn.role === 'assistant' && turn.completed) count += 1
  }
  return count
}

export function dropTurnsFrom<T extends { id: number }>(turns: T[], fromId: number): T[] {
  const index = turns.findIndex(item => item.id === fromId)
  return index < 0 ? turns : turns.slice(0, index)
}

export function findUserTurn<T extends { id: number; role: string }>(turns: T[], assistant: T): T | undefined {
  const index = turns.findIndex(item => item.id === assistant.id)
  if (index <= 0) return undefined
  return [...turns.slice(0, index)].reverse().find(item => item.role === 'user')
}

export function filesFromDataTransfer(data: DataTransfer | null | undefined): File[] {
  if (!data) return []
  const files = [...data.files]
  if (files.length) return files
  return [...data.items]
    .filter(item => item.kind === 'file')
    .map(item => item.getAsFile())
    .filter((file): file is File => Boolean(file))
}

export function namedPastedFile(file: File): File {
  if (isSupportedPulseAttachment(file.name)) return file
  const typeName = file.type === 'text/plain'
    ? '粘贴.txt'
    : file.type === 'text/markdown' || file.type === 'text/x-markdown'
      ? '粘贴.md'
      : file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ? '粘贴.docx'
        : ''
  return typeName
    ? new File([file], typeName, { type: file.type, lastModified: file.lastModified })
    : file
}

export function isPulseAttachmentMeta(value: unknown): value is PulseAttachmentMeta {
  if (!value || typeof value !== 'object') return false
  const item = value as PulseAttachmentMeta
  return typeof item.id === 'string' && typeof item.name === 'string'
    && typeof item.size === 'number' && typeof item.chars === 'number'
}
