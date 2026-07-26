import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Memory } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Search, Plus, Trash2, Edit2, Tag } from 'lucide-react'
import clsx from 'clsx'

export const MemoryPage: React.FC = () => {
  const { theme, memories, setMemories, isLoading: _isLoading, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [searchQuery, setSearchQuery] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null)
  const [filteredMemories, setFilteredMemories] = useState<Memory[]>([])

  useEffect(() => {
    loadMemories()
  }, [])

  useEffect(() => {
    filterMemories()
  }, [memories, searchQuery])

  const loadMemories = async () => {
    try {
      setLoading(true)
      const response = await apiClient.listMemories()
      setMemories(response.items)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load memories')
    } finally {
      setLoading(false)
    }
  }

  const filterMemories = async () => {
    if (!searchQuery.trim()) {
      setFilteredMemories(memories)
      return
    }

    try {
      const results = await apiClient.searchMemories(searchQuery)
      setFilteredMemories(results)
    } catch (error) {
      console.error('Search failed:', error)
      setFilteredMemories(memories)
    }
  }

  // PUT /api/v1/memory/{id} and DELETE /api/v1/memory/{id} exist in the
  // backend — edit and delete are fully wired.
  const handleEdit = (memory: Memory) => {
    setEditingMemory(memory)
    setShowModal(true)
  }

  const handleDelete = async (memory: Memory) => {
    if (!window.confirm(t('memory.confirmDelete', 'Delete this memory?'))) return
    try {
      setLoading(true)
      await apiClient.deleteMemory(memory.id)
      await loadMemories()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete memory')
    } finally {
      setLoading(false)
    }
  }

  const closeModal = () => {
    setShowModal(false)
    setEditingMemory(null)
  }

  return (
    <div className={clsx(
      'p-8',
      theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50'
    )}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx(
              'text-3xl font-bold mb-2',
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            )}>
              {t('memory.title', 'Memory Management')}
            </h1>
            <p className={clsx(
              'text-sm',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {t('memory.subtitle', 'Browse and manage your agent memories')}
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus size={20} />
            {t('memory.newMemory', 'New Memory')}
          </button>
        </div>

        {/* Search */}
        <div className="mb-6">
          <div className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-lg',
            theme === 'dark'
              ? 'bg-slate-900 border border-slate-700'
              : 'bg-white border border-slate-300'
          )}>
            <Search size={20} className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'} aria-hidden="true" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('memory.searchPlaceholder', 'Search memories...')}
              aria-label={t('memory.searchMemories', 'Search memories')}
              className={clsx(
                'flex-1 bg-transparent outline-none text-sm',
                theme === 'dark' ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
              )}
            />
          </div>
        </div>

        {/* Memories List */}
        <div className="space-y-4">
          {filteredMemories.length === 0 ? (
            <div className={clsx(
              'text-center py-12 rounded-lg',
              theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
            )}>
              <p className={clsx(
                'text-lg font-medium mb-2',
                theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
              )}>
                {searchQuery ? t('memory.noFound', 'No memories found') : t('memory.noYet', 'No memories yet')}
              </p>
              <p className={clsx(
                'text-sm',
                theme === 'dark' ? 'text-slate-500' : 'text-slate-600'
              )}>
                {searchQuery ? t('memory.tryDifferent', 'Try a different search query') : t('memory.createToStart', 'Create a new memory to get started')}
              </p>
            </div>
          ) : (
            filteredMemories.map((memory) => (
              <MemoryCard key={memory.id} memory={memory} onEdit={handleEdit} onDelete={handleDelete} />
            ))
          )}
        </div>
      </div>

      {/* Memory Modal (create / edit) */}
      {showModal && (
        <MemoryModal
          memory={editingMemory ?? undefined}
          onClose={closeModal}
          onSave={() => {
            loadMemories()
            closeModal()
          }}
        />
      )}
    </div>
  )
}

interface MemoryCardProps {
  memory: Memory
  onEdit: (memory: Memory) => void
  onDelete: (memory: Memory) => void
}

const MemoryCard: React.FC<MemoryCardProps> = ({ memory, onEdit, onDelete }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()

  return (
    <div className={clsx(
      'rounded-lg p-6 transition-all',
      theme === 'dark'
        ? 'bg-slate-900 border border-slate-700 hover:border-slate-600'
        : 'bg-white border border-slate-200 hover:border-slate-300'
    )}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className={clsx(
            'text-sm font-medium mb-2',
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          )}>
            {t('memory.layer', 'Layer')} {memory.layer}
          </p>
          <p className={clsx(
            'text-sm line-clamp-2',
            theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
          )}>
            {memory.content}
          </p>
        </div>
        <div className="flex items-center gap-2 ml-4">
          <button
            onClick={() => onEdit(memory)}
            className={clsx(
              'p-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                : 'text-slate-600 hover:bg-slate-100'
            )}
            title={t('memory.editMemory', 'Edit')}
            aria-label={t('memory.editMemory', 'Edit')}
          >
            <Edit2 size={16} />
          </button>
          <button
            onClick={() => onDelete(memory)}
            className={clsx(
              'p-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'text-red-400 hover:bg-slate-800'
                : 'text-red-600 hover:bg-red-50'
            )}
            title={t('memory.deleteMemory', 'Delete')}
            aria-label={t('memory.deleteMemory', 'Delete')}
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Tags */}
      {memory.tags && memory.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {memory.tags.map((tag) => (
            <span
              key={tag}
              className={clsx(
                'inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium',
                theme === 'dark'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'bg-blue-100 text-blue-700'
              )}
            >
              <Tag size={12} aria-hidden="true" />
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Metadata */}
      <div className={clsx(
        'mt-4 pt-4 border-t text-xs',
        theme === 'dark' ? 'border-slate-700 text-slate-500' : 'border-slate-200 text-slate-600'
      )}>
        <p>{t('memory.createdAt', 'Created')}: {new Date(memory.createdAt).toLocaleString()}</p>
        {memory.relevance !== undefined && (
          <p>Relevance: {(memory.relevance * 100).toFixed(0)}%</p>
        )}
      </div>
    </div>
  )
}

interface MemoryModalProps {
  memory?: Memory
  onClose: () => void
  onSave: () => void
}

const MemoryModal: React.FC<MemoryModalProps> = ({ memory, onClose, onSave }) => {
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const isEdit = !!memory
  const [content, setContent] = useState(memory?.content ?? '')
  const [importance, setImportance] = useState(memory?.importance ?? 0.5)
  const [tags, setTags] = useState(memory?.tags?.join(', ') ?? '')

  const handleSave = async () => {
    try {
      setLoading(true)
      const payload = {
        content,
        importance,
        tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      }
      if (isEdit && memory) {
        await apiClient.updateMemory(memory.id, payload)
      } else {
        await apiClient.createMemory(payload)
      }

      onSave()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to save memory')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-label={t('memory.newMemory', 'New Memory')}
    >
      <div className={clsx(
        'rounded-lg p-6 max-w-md w-full mx-4',
        theme === 'dark' ? 'bg-slate-900' : 'bg-white'
      )}>
        <h2 className={clsx(
          'text-2xl font-bold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          {isEdit ? t('memory.editMemory', 'Edit Memory') : t('memory.newMemory', 'New Memory')}
        </h2>

        <div className="space-y-4 mb-6">
          <div>
            <label
              htmlFor="memory-content"
              className={clsx(
                'block text-sm font-medium mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
            >
              {t('memory.content', 'Content')}
            </label>
            <textarea
              id="memory-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
              rows={6}
              placeholder={t('memory.contentPlaceholder', 'Enter memory content...')}
            />
          </div>

          <div>
            <label
              htmlFor="memory-importance"
              className={clsx(
                'block text-sm font-medium mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
            >
              {t('memory.importance', 'Importance')} ({importance.toFixed(2)})
            </label>
            <input
              id="memory-importance"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={importance}
              onChange={(e) => setImportance(Number(e.target.value))}
              className="w-full"
            />
          </div>

          <div>
            <label
              htmlFor="memory-tags"
              className={clsx(
                'block text-sm font-medium mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
            >
              {t('memory.tags', 'Tags')}
            </label>
            <input
              id="memory-tags"
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
              placeholder="tag1, tag2, tag3"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={onClose}
            className={clsx(
              'flex-1 px-4 py-2 rounded-lg font-medium transition-colors',
              theme === 'dark'
                ? 'bg-slate-700 hover:bg-slate-600 text-white'
                : 'bg-slate-200 hover:bg-slate-300 text-slate-900'
            )}
          >
            {t('common.cancel', 'Cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading || !content.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? t('common.loading', 'Saving...') : t('common.save', 'Save')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default MemoryPage
