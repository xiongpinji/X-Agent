import React, { useEffect, useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { apiClient, Task } from '@/services/api'
import { Plus, Trash2, Eye, CheckCircle, Clock, AlertCircle } from 'lucide-react'
import clsx from 'clsx'

export const TasksPage: React.FC = () => {
  const { theme, tasks, setTasks, isLoading, setLoading, setError } = useAppStore()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showModal, setShowModal] = useState(false)

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
    if (!confirm('Are you sure you want to delete this task?')) return

    try {
      await apiClient.deleteTask(id)
      setTasks(tasks.filter((t) => t.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete task')
    }
  }

  const getStatusIcon = (status: Task['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="text-green-500" />
      case 'running':
        return <Clock size={16} className="text-blue-500 animate-spin" />
      case 'failed':
        return <AlertCircle size={16} className="text-red-500" />
      default:
        return <Clock size={16} className="text-slate-500" />
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
              Tasks
            </h1>
            <p className={clsx(
              'text-sm',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              Manage and monitor your tasks
            </p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <Plus size={20} />
            New Task
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
              <p className="text-lg font-medium mb-2">No tasks yet</p>
              <p className="text-sm">Create a new task to get started</p>
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
                      Name
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      Status
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      Progress
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-left text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      Created
                    </th>
                    <th className={clsx(
                      'px-6 py-3 text-right text-sm font-semibold',
                      theme === 'dark' ? 'text-slate-300' : 'text-slate-900'
                    )}>
                      Actions
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
                            task.status === 'completed' ? 'text-green-600' :
                            task.status === 'running' ? 'text-blue-600' :
                            task.status === 'failed' ? 'text-red-600' :
                            'text-slate-600'
                          )}>
                            {task.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="w-32 bg-slate-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all"
                            style={{ width: `${task.progress}%` }}
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
                            title="View details"
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
                            title="Delete task"
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
    </div>
  )
}

interface TaskModalProps {
  task: Task
  onClose: () => void
}

const TaskModal: React.FC<TaskModalProps> = ({ task, onClose }) => {
  const { theme } = useAppStore()

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
          {task.name}
        </h2>

        <div className="space-y-4 mb-6">
          <div>
            <p className={clsx(
              'text-sm font-medium mb-1',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              Status
            </p>
            <p className={clsx(
              'text-lg font-semibold capitalize',
              task.status === 'completed' ? 'text-green-600' :
              task.status === 'running' ? 'text-blue-600' :
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
              Progress
            </p>
            <div className="w-full bg-slate-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${task.progress}%` }}
              />
            </div>
            <p className={clsx(
              'text-sm mt-1',
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            )}>
              {task.progress}%
            </p>
          </div>

          {task.error && (
            <div>
              <p className={clsx(
                'text-sm font-medium mb-1',
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              )}>
                Error
              </p>
              <p className="text-sm text-red-600">{task.error}</p>
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  )
}

export default TasksPage
