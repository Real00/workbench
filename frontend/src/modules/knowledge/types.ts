export interface KnowledgeTag {
  id: string
  name: string
  explanation: string
  created_at?: string
  updated_at?: string
}

export type TagInput = Pick<KnowledgeTag, 'name' | 'explanation'>

export interface KnowledgeEntry {
  id: string
  key: string
  value: string
  tag_ids: string[]
  document_ids: string[]
  aliases: string[]
  created_at?: string
  updated_at?: string
}

export type EntryInput = Pick<KnowledgeEntry, 'key' | 'value' | 'tag_ids' | 'document_ids' | 'aliases'>

export interface KnowledgeDocument {
  id: string
  title: string
  body: string
  tag_ids: string[]
  entry_ids: string[]
  raw_filename: string | null
  raw_storage_key: string | null
  has_raw: boolean
  canvas_x: number
  canvas_y: number
  created_at?: string
  updated_at?: string
}

export type DocumentInput = Pick<KnowledgeDocument, 'title' | 'body' | 'tag_ids' | 'entry_ids'>
