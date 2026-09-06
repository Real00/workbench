import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiError } from '../../shared/api/client'
import { knowledgeApi } from './api'
import type { DocumentInput, EntryInput, KnowledgeDocument, KnowledgeEntry, KnowledgeTag, TagInput } from './types'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const tags = ref<KnowledgeTag[]>([])
  const entries = ref<KnowledgeEntry[]>([])
  const documents = ref<KnowledgeDocument[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const initialized = ref(false)
  const documentEditorOpen = ref(false)
  const editingDocument = ref<KnowledgeDocument | null>(null)
  const entryEditorOpen = ref(false)
  const editingEntry = ref<KnowledgeEntry | null>(null)
  const tagEditorOpen = ref(false)
  const editingTag = ref<KnowledgeTag | null>(null)
  const tagMap = computed(() => new Map(tags.value.map(tag => [tag.id, tag])))
  const entryMap = computed(() => new Map(entries.value.map(entry => [entry.id, entry])))

  async function initialize() {
    loading.value = true
    error.value = ''
    try {
      const [tagData, entryData, documentData] = await Promise.all([
        knowledgeApi.getTags(),
        knowledgeApi.getEntries(),
        knowledgeApi.getDocuments(),
      ])
      tags.value = tagData
      entries.value = entryData
      documents.value = documentData
      initialized.value = true
    } catch (cause) {
      error.value = apiError(cause)
    } finally {
      loading.value = false
    }
  }

  /** 静默刷新：不触发 loading，用于事件总线推送与子菜单切换的后台同步 */
  async function refresh() {
    try {
      const [tagData, entryData, documentData] = await Promise.all([
        knowledgeApi.getTags(),
        knowledgeApi.getEntries(),
        knowledgeApi.getDocuments(),
      ])
      tags.value = tagData
      entries.value = entryData
      documents.value = documentData
    } catch {
      /* 后台刷新失败不打扰用户，下次事件或切换菜单会再试 */
    }
  }

  async function runSave(action: () => Promise<void>) {
    saving.value = true
    error.value = ''
    try {
      await action()
      return true
    } catch (cause) {
      error.value = apiError(cause)
      return false
    } finally {
      saving.value = false
    }
  }

  function openDocument(document?: KnowledgeDocument) {
    editingDocument.value = document ?? null
    documentEditorOpen.value = true
  }

  function openEntry(entry?: KnowledgeEntry) {
    editingEntry.value = entry ?? null
    entryEditorOpen.value = true
  }

  function openTag(tag?: KnowledgeTag) {
    editingTag.value = tag ?? null
    tagEditorOpen.value = true
  }

  async function saveDocument(payload: DocumentInput, file?: File | null) {
    return runSave(async () => {
      const saved = editingDocument.value
        ? await knowledgeApi.updateDocument(editingDocument.value.id, payload)
        : await knowledgeApi.createDocument(payload)
      if (file) await knowledgeApi.importDocument(saved.id, file, false)
      documentEditorOpen.value = false
      await initialize()
    })
  }

  async function saveEntry(payload: EntryInput) {
    return runSave(async () => {
      if (editingEntry.value) await knowledgeApi.updateEntry(editingEntry.value.id, payload)
      else await knowledgeApi.createEntry(payload)
      entryEditorOpen.value = false
      await initialize()
    })
  }

  async function saveTag(payload: TagInput) {
    return runSave(async () => {
      if (editingTag.value) await knowledgeApi.updateTag(editingTag.value.id, payload)
      else await knowledgeApi.createTag(payload)
      tagEditorOpen.value = false
      await initialize()
    })
  }

  async function deleteDocument(id: string) {
    return runSave(async () => {
      await knowledgeApi.deleteDocument(id)
      documentEditorOpen.value = false
      await initialize()
    })
  }

  async function deleteEntry(id: string) {
    return runSave(async () => {
      await knowledgeApi.deleteEntry(id)
      entryEditorOpen.value = false
      await initialize()
    })
  }

  async function deleteTag(id: string) {
    return runSave(async () => {
      await knowledgeApi.deleteTag(id)
      tagEditorOpen.value = false
      await initialize()
    })
  }

  async function moveDocument(id: string, canvas_x: number, canvas_y: number) {
    const updated = await knowledgeApi.moveDocument(id, canvas_x, canvas_y)
    documents.value = documents.value.map(item => item.id === id ? updated : item)
  }

  return {
    tags, entries, documents, tagMap, entryMap, loading, saving, error, initialized,
    documentEditorOpen, editingDocument, entryEditorOpen, editingEntry, tagEditorOpen, editingTag,
    initialize, refresh, openDocument, openEntry, openTag, saveDocument, saveEntry, saveTag,
    deleteDocument, deleteEntry, deleteTag, moveDocument,
  }
})
