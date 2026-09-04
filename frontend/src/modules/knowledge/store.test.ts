import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { knowledgeApi } from './api'
import { useKnowledgeStore } from './store'
import type { KnowledgeDocument, KnowledgeEntry, KnowledgeTag } from './types'

const tag: KnowledgeTag = {
  id: 'tag-1',
  name: '平台',
  explanation: '工作台约定',
}

const entry: KnowledgeEntry = {
  id: 'entry-1',
  key: 'Pulse',
  value: '工作台 AI 对话框',
  tag_ids: [tag.id],
  document_ids: ['doc-1'],
  aliases: ['助手'],
}

const document: KnowledgeDocument = {
  id: 'doc-1',
  title: '检索约定',
  body: '明文 Markdown 按行 grep',
  tag_ids: [tag.id],
  entry_ids: [entry.id],
  raw_filename: null,
  raw_storage_key: null,
  has_raw: false,
  canvas_x: 80,
  canvas_y: 80,
}

function mockReads() {
  vi.spyOn(knowledgeApi, 'getTags').mockResolvedValue([tag])
  vi.spyOn(knowledgeApi, 'getEntries').mockResolvedValue([entry])
  vi.spyOn(knowledgeApi, 'getDocuments').mockResolvedValue([document])
}

describe('knowledge store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('并行加载标签、条目和文档', async () => {
    mockReads()
    const store = useKnowledgeStore()
    await store.initialize()
    expect(store.documents).toEqual([document])
    expect(store.tagMap.get(tag.id)?.explanation).toBe('工作台约定')
    expect(store.entryMap.get(entry.id)?.key).toBe('Pulse')
  })

  it('保存文档后刷新列表并关闭编辑器', async () => {
    mockReads()
    const create = vi.spyOn(knowledgeApi, 'createDocument').mockResolvedValue(document)
    const store = useKnowledgeStore()
    store.openDocument()
    expect(await store.saveDocument({
      title: document.title,
      body: document.body,
      tag_ids: [],
      entry_ids: [],
    })).toBe(true)
    expect(create).toHaveBeenCalled()
    expect(store.documentEditorOpen).toBe(false)
    expect(store.documents).toEqual([document])
  })

  it('拖拽后写回画布坐标', async () => {
    mockReads()
    const moved = { ...document, canvas_x: 160, canvas_y: 90 }
    vi.spyOn(knowledgeApi, 'moveDocument').mockResolvedValue(moved)
    const store = useKnowledgeStore()
    await store.initialize()
    await store.moveDocument(document.id, 160, 90)
    expect(store.documents[0]?.canvas_x).toBe(160)
    expect(store.documents[0]?.canvas_y).toBe(90)
  })
})
