import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Task } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { Plus, Trash2, Eye, CheckCircle, Clock, AlertCircle } from 'lucide-react'
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

  const getStatusIcon = (status: Task['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="text-green-500" />
      case 'in_progress':
        return <Clock size={16} className="text-blue-500 animate-spin" />
      case 'failed':
        return <AlertCircle size={16} className="text-red-500" />
      default:
        return <Clock size={16} className="text-slate-500" />
    }
  }

  const statusColor = (status: Task['status']) =>
    status === 'completed' ? 'text-green-600' :
    status === 'in_progress' ? 'text-blue-600' :
    status === 'failed' ? 'text-red-600' :
    'text-slate-600'

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
              {t('tasks.title', 'Tasks')}
            </h1>
            <p className={clsx(
              'text-sm',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {t('tasks.allTasks', 'Manage and monitor your tasks')}
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus size={20} />
            {t('tasks.newTask', 'New Task')}
          </button>
        </div>

        {/* Tasks Table */}
        <div className={clsx(
          'rounded-lg overflow-hidden',
          theme === 'dark' ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-slate-200'
        )}>
          {tasks.length === 0 ? (
            <div className={clsx(
              'p-8 text-center',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
            )}>
              <p className="text-lg font-medium mb-2">{t('tasks.noTasks', 'No tasks yet')}</p>
              <p className="text-sm">{t('tasks.createToStart', 'Create a new task to get started')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className={clsx(
                  'border-b',
                  theme === 'dark' ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                )}>
                  <tr>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      {t('tasks.taskName', 'Name')}
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      {t('tasks.status', 'Status')}
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      {t('workflows.progress', 'Progress')}
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      {t('tasks.createdAt', 'Created')}
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-right text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      {t('common.actions', 'Actions')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr
                      key={task.id}
                      className={clsx(
                        'border-b transition-colors',
                        theme === 'dark'
                          ? 'border-slate-700 hover:bg-slate-800'
                          : 'border-slate-200 hover:bg-slate-50'
                      )}
                    >
                      <td className={clsx(
                        'px-6 py-4 text-sm font-medium',
                        theme === 'dark' ? 'text-white' : 'text-slate-900'
                      )}>
                        {task.name}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(task.status)}
                          <span className={clsx(
                            'text-sm font-medium capitalize',
                            statusColor(task.status)
                          )}>
                            {task.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div
                          className="w-32 bg-slate-200 rounded-full h-2"
                          role="progressbar"
                          aria-valuenow={Math.round(task.progress * 100)}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${task.name} ${t('workflows.progress', 'Progress')}`}
                        >
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all"
                            style={{ width: `${Math.round(task.progress * 100)}%` }}
                          />
                        </div>
                      </td>
                      <td className={clsx(
                        'px-6 py-4 text-sm',
                        theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                      )}>
                        {new Date(task.createdAt).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => {
                              setSelectedTask(task)
                              setShowModal(true)
                            }}
                            className={clsx(
                              'p-2 rounded-lg transition-colors',
                              theme === 'dark'
                                ? 'hover:bg-slate-700 text-slate-400'
                                : 'hover:bg-slate-200 text-slate-600'
                            )}
                            title={t('tasks.viewDetails', 'View details')}
                            aria-label={t('tasks.viewDetails', 'View details')}
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            onClick={() => handleDeleteTask(task.id)}
                            className={clsx(
                              'p-2 rounded-lg transition-colors',
                              theme === 'dark'
                                ? 'hover:bg-red-900/20 text-red-400'
                                : 'hover:bg-red-100 text-red-600'
                            )}
                            title={t('tasks.deleteTask', 'Delete task')}
                            aria-label={t('tasks.deleteTask', 'Delete task')}
                          >
                            <Trash2 size={16} />
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
