import React, { useEffect, useState } from 'react'
import clsx from 'clsx'
import { useAppStore } from '@/store/appStore'
import { apiClient } from '@/services/api'
import { Button, Card, CardBody, DataTable, EmptyState, LoadingState } from '@/components/ui'
import { Plus, Eye, Trash2, CheckCircle, Clock, AlertCircle } from 'lucide-react'

export const OptimizedTasksPage: React.FC = () => {
  const { theme, tasks, setTasks, isLoading, setLoading, setError } = useAppStore()
  const [selectedTask, setSelectedTask] = useState<any>(null)

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
    if (!confirm('Are you sure?')) return
    try {
      await apiClient.deleteTask(id)
      setTasks(tasks.filter((t) => t.id !== id))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete task')
    }
  }

  const getStatusIcon = (status: string) => {
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

  const columns = [
    {
      key: 'name',
      label: 'Task Name',
      render: (value: string) => <span className="font-medium">{value}</span>,
    },
    {
      key: 'status',
      label: 'Status',
      render: (value: string) => (
        <div className="flex items-center gap-2">
          {getStatusIcon(value)}
          <span className="capitalize text-sm">{value}</span>
        </div>
      ),
    },
    {
      key: 'progress',
      label: 'Progress',
      render: (value: number) => (
        <div className="w-32 bg-slate-200 dark:bg-slate-700 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${value}%` }}
          />
        </div>
      ),
    },
    {
      key: 'createdAt',
      label: 'Created',
      render: (value: string) => new Date(value).toLocaleDateString(),
    },
  ]

  return (
    <div className={clsx('p-8', theme === 'dark' ? 'bg-slate-950' : 'bg-slate-50')}>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className={clsx('text-3xl font-bold mb-2', theme === 'dark' ? 'text-white' : 'text-slate-900')}>
              Tasks
            </h1>
            <p className={clsx('text-sm', theme === 'dark' ? 'text-slate-400' : 'text-slate-600')}>
              Manage and monitor your tasks
            </p>
          </div>
          <Button variant="primary" icon={<Plus size={20} />}>
            New Task
          </Button>
        </div>

        {/* Content */}
        {isLoading ? (
          <LoadingState message="Loading tasks..." />
        ) : tasks.length === 0 ? (
          <Card>
            <CardBody>
              <EmptyState
                title="No tasks yet"
                description="Create a new task to get started"
                action={<Button variant="primary">Create Task</Button>}
              />
            </CardBody>
          </Card>
        ) : (
          <Card>
            <CardBody>
              <DataTable columns={columns} data={tasks} onRowClick={setSelectedTask} />
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  )
}

export default OptimizedTasksPage
