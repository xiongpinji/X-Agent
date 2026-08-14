import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Task } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Plus, Trash2, Eye } from 'lucide-react'
import clsx from 'clsx'

export const TasksPage: React.FC = () => {
  const { theme, tasks, setTasks, isLoading: _isLoading, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)

  useEffect(() => {
    loadTasks()
  }, [])

  const loadTasks = async () => {
    try {
      setLoading(true)
      const response = await apiClient.listTasks()
      setTasks(response.items)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteTask = async (id: string) => {
    if (!confirm(t('tasks.deleteTask', 'Delete this task?'))) return

    try {
      await apiClient.deleteTask(id)
      setTasks(tasks.filter((task) => task.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete task')
    }
  }

  const statusBadge = (status: Task['status']) =>
    status === 'completed' ? 'badge-success' :
    status === 'in_progress' ? 'badge-warning' :
    status === 'failed' ? 'badge-danger' :
    'badge-muted'

  return (
    <div className={clsx(
      'min-h-full px-8 py-10',
      theme === 'dark' ? 'bg-slate-950 text-slate-200' : 'bg-[#fafafa] text-[#333333]'
    )}>
      <div className="max-w-6xl">
        {/* Header — Dashboard-style: 2px rule + 32px/500 title + 50% subtitle */}
        <header className="mb-8">
          <div
            className={clsx(
              'w-12 border-t-2 mb-5',
              theme === 'dark' ? 'border-slate-200' : 'border-[#333333]'
            )}
            aria-hidden="true"
          />
          <div className="flex items-end justify-between gap-4">
            <div>
              <h1 className="page-title">{t('tasks.title', 'Tasks')}</h1>
              <p className="page-subtitle">{t('tasks.allTasks', 'Manage and monitor your tasks')}</p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Plus size={16} />
              {t('tasks.newTask', 'New Task')}
            </button>
          </div>
        </header>

        {/* Tasks Table — dense, hairline dividers */}
        {tasks.length === 0 ? (
          <p className="empty-state">
            {t('tasks.noTasks', 'No tasks yet')} · {t('tasks.createToStart', 'Create a new task to get started')}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-dense">
              <thead>
                <tr>
                  <th>{t('tasks.taskName', 'Name')}</th>
                  <th>{t('tasks.status', 'Status')}</th>
                  <th>{t('workflows.progress', 'Progress')}</th>
                  <th>{t('tasks.createdAt', 'Created')}</th>
                  <th className="ta-right">{t('common.actions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td className="font-medium">{task.name}</td>
                    <td>
                      <span className={clsx('badge-status', statusBadge(task.status))}>
                        {task.status}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div
                          className="w-24 h-[3px]"
                          style={{ backgroundColor: 'rgba(163,169,177,.25)' }}
                          role="progressbar"
                          aria-valuenow={Math.round(task.progress * 100)}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${task.name} ${t('workflows.progress', 'Progress')}`}
                        >
                          <div
                            className={clsx('h-[3px] transition-all', theme === 'dark' ? 'bg-slate-300' : 'bg-[#333333]')}
                            style={{ width: `${Math.round(task.progress * 100)}%` }}
                          />
                        </div>
                        <span className="cell-data opacity-60">{Math.round(task.progress * 100)}%</span>
                      </div>
                    </td>
                    <td className="cell-data opacity-70">
                      {new Date(task.createdAt).toLocaleDateString()}
                    </td>
                    <td className="ta-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => {
                            setSelectedTask(task)
                            setShowModal(true)
                          }}
                          className="p-1.5 opacity-50 hover:opacity-100 transition-opacity"
                          title={t('tasks.viewDetails', 'View details')}
                          aria-label={t('tasks.viewDetails', 'View details')}
                        >
                          <Eye size={15} />
                        </button>
                        <button
                          onClick={() => handleDeleteTask(task.id)}
                          className="p-1.5 text-[#dc2626] opacity-50 hover:opacity-100 transition-opacity"
                          title={t('tasks.deleteTask', 'Delete task')}
                          aria-label={t('tasks.deleteTask', 'Delete task')}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Task Detail Modal */}
      {showModal && selectedTask && (
        <TaskModal
          task={selectedTask}
          onClose={() => {
            setShowModal(false)
            setSelectedTask(null)
          }}
        />
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <CreateTaskModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false)
            loadTasks()
          }}
        />
      )}
    </div>
  )
}

interface TaskModalProps {
  task: Task
  onClose: () => void
}

const TaskModal: React.FC<TaskModalProps> = ({ task, onClose }) => {
  const { theme } = useAppStore()
  const { t } = useI18n()
  const percent = Math.round(task.progress * 100)

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-label={task.name}
    >
      <div className={clsx(
        'rounded-lg p-6 max-w-md w-full mx-4',
        theme === 'dark' ? 'bg-slate-900' : 'bg-white'
      )}>
        <h2 className={clsx(
          'text-2xl font-bold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          {task.name}
        </h2>

        <div className="space-y-4 mb-6">
          <div>
            <p className={clsx(
              'text-sm font-medium mb-1',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {t('tasks.status', 'Status')}
            </p>
            <p className={clsx(
              'text-lg font-semibold capitalize',
              task.status === 'completed' ? 'text-green-600' :
              task.status === 'in_progress' ? 'text-blue-600' :
              task.status === 'failed' ? 'text-red-600' :
              'text-slate-600'
            )}>
              {task.status}
            </p>
          </div>

          <div>
            <p className={clsx(
              'text-sm font-medium mb-1',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {t('workflows.progress', 'Progress')}
            </p>
            <div
              className="w-full bg-slate-200 rounded-full h-2"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${percent}%` }}
              />
            </div>
            <p className={clsx(
              'text-sm mt-1',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {percent}%
            </p>
          </div>

          {task.error && (
            <div>
              <p className={clsx(
                'text-sm font-medium mb-1',
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              )}>
                {t('common.error', 'Error')}
              </p>
              <p className="text-sm text-red-600">{task.error}</p>
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
        >
          {t('common.close', 'Close')}
        </button>
      </div>
    </div>
  )
}

interface CreateTaskModalProps {
  onClose: () => void
  onCreated: () => void
}

const CreateTaskModal: React.FC<CreateTaskModalProps> = ({ onClose, onCreated }) => {
  const { theme, isLoading, setLoading, setError } = useAppStore()
  const { t } = useI18n()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')

  const handleCreate = async () => {
    try {
      setLoading(true)
      await apiClient.createTask({ title, description })
      onCreated()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create task')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-label={t('tasks.newTask', 'New Task')}
    >
      <div className={clsx(
        'rounded-lg p-6 max-w-md w-full mx-4',
        theme === 'dark' ? 'bg-slate-900' : 'bg-white'
      )}>
        <h2 className={clsx(
          'text-2xl font-bold mb-4',
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        )}>
          {t('tasks.newTask', 'New Task')}
        </h2>

        <div className="space-y-4 mb-6">
          <div>
            <label
              htmlFor="task-title"
              className={clsx(
                'block text-sm font-medium mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
            >
              {t('tasks.taskName', 'Task name')}
            </label>
            <input
              id="task-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
            />
          </div>

          <div>
            <label
              htmlFor="task-description"
              className={clsx(
                'block text-sm font-medium mb-2',
                theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
              )}
            >
              {t('tasks.description', 'Description')}
            </label>
            <textarea
              id="task-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={clsx(
                'w-full px-3 py-2 rounded-lg text-sm',
                theme === 'dark'
                  ? 'bg-slate-800 text-white border border-slate-700'
                  : 'bg-slate-50 text-slate-900 border border-slate-300'
              )}
              rows={4}
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
            onClick={handleCreate}
            disabled={isLoading || !title.trim()}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? t('common.loading', 'Loading...') : t('common.create', 'Create')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default TasksPage
