import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Memory } from '@/services/api'
import { Search, Plus, Trash2, Edit2, Tag } from 'lucide-react'
import clsx from 'clsx'

export const MemoryPage: React.FC = () => {
  const { theme, memories, setMemories, isLoading, setLoading, setError } = useAppStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null)
  const [showModal, setShowModal] = useState(false)
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

  const handleDeleteMemory = async (id: string) => {
    if (!confirm('Are you sure you want to delete this memory?')) return

    try {
      await apiClient.deleteMemory(id)
      setMemories(memories.filter((m) => m.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete memory')
    }
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
              Memory Management
            </h1>
            <p className={clsx(
              'text-sm',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              Browse and manage your agent memories
            </p>
          </div>
          <button
            onClick={() => {
              setSelectedMemory(null)
              setShowModal(true)
            }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus size={20} />
            New Memory
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
            <Search size={20} className={theme === 'dark' ? 'text-slate-400' : 'text-slate-600'} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search memories..."
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
                {searchQuery ? 'No memories found' : 'No memories yet'}
              </p>
              <p className={clsx(
                'text-sm',
                theme === 'dark' ? 'text-slate-500' : 'text-slate-600'
              )}>
                {searchQuery ? 'Try a different search query' : 'Create a new memory to get started'}
              </p>
            </div>
          ) : (
            filteredMemories.map((memory) => (
              <MemoryCard
                key={memory.id}
                memory={memory}
                onEdit={() => {
                  setSelectedMemory(memory)
                  setShowModal(true)
                }}
                onDelete={() => handleDeleteMemory(memory.id)}
              />
            ))
          )}
        </div>
      </div>

      {/* Memory Modal */}
      {showModal && (
        <MemoryModal
          memory={selectedMemory}
          onClose={() => {
            setShowModal(false)
            setSelectedMemory(null)
          }}
          onSave={() => {
            loadMemories()
            setShowModal(false)
            setSelectedMemory(null)
          }}
        />
      )}
    </div>
  )
}

interface MemoryCardProps {
  memory: Memory
  onEdit: () => void
  onDelete: () => void
}

const MemoryCard: React.FC<MemoryCardProps> = ({ memory, onEdit, onDelete }) => {
  const { theme } = useAppStore()

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
            {memory.type}
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
            onClick={onEdit}
            className={clsx(
              'p-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'hover:bg-slate-800 text-slate-400'
                : 'hover:bg-slate-200 text-slate-600'
            )}
            title="Edit"
          >
            <Edit2 size={16} />
          </button>
          <button
            onClick={onDelete}
            className={clsx(
              'p-2 rounded-lg transition-colors',
              theme === 'dark'
                ? 'hover:bg-red-900/20 text-red-400'
                : 'hover:bg-red-100 text-red-600'
            )}
            title="Delete"
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
              <Tag size={12} />
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
        <p>Created: {new Date(memory.createdAt).toLocaleString()}</p>
        {memory.relevance !== undefined && (
          <p>Relevance: {(memory.relevance * 100).toFixed(0)}%</p>
        )}
      </div>
    </div>
  )
}

interface MemoryModalProps {
  memory: Memory | null
  onClose: () => void
  onSave: () => void
}

const MemoryModal: React.FC<MemoryModalProps> = ({ memory, onClose, onSave }) => {
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const [content, setContent] = useState(memory?.content || '')
  const [type, setType] = useState(memory?.type || 'note')
  const [tags, setTags] = useState(memory?.tags?.join(', ') || '')

  const handleSave = async () => {
    try {
      setLoading(true)
      const data = {
        content,
        type,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      }

      if (memory) {
        await apiClient.updateMemory(memory.id, data)
      } else {
        await apiClient.createMemory(data)
      }

      onSave()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to save memory')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className={clsx(
        'rounded-lg p-6 max-w-md w-full mx-4',
        theme === 'dark' ? 'bg-slate-900' : 'bg-white'
      )}>
        <h2 className={clsx(
          'text-2xl font-bold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          {memory ? 'Edit Memory' : 'New Memory'}
        </h2>

        <div className="space-y-4 mb-6">
          <div>
            <label className={clsx(
              'block text-sm font-medium mb-2',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}>
              Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
            >
              <option value="note">Note</option>
              <option value="context">Context</option>
              <option value="insight">Insight</option>
              <option value="reference">Reference</option>
            </select>
          </div>

          <div>
            <label className={clsx(
              'block text-sm font-medium mb-2',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}>
              Content
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
              rows={6}
              placeholder="Enter memory content..."
            />
          </div>

          <div>
            <label className={clsx(
              'block text-sm font-medium mb-2',
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            )}>
              Tags (comma-separated)
            </label>
            <input
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
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading || !content.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default MemoryPage
