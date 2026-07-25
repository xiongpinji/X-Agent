import React, { useState, useCallback, useEffect } from 'react'
import { apiClient } from '@/services/api'
import { useI18n } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'
import clsx from 'clsx'

// Lightweight DAG editor without external dependencies (reactflow alternative)
interface WorkflowNode {
  id: string
  type: 'start' | 'task' | 'condition' | 'end'
  label: string
  x: number
  y: number
  config?: Record<string, any>
}

interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
}

interface Workflow {
  id: string
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  status?: string
}

const NODE_COLORS: Record<string, string> = {
  start: 'bg-green-500',
  task: 'bg-blue-500',
  condition: 'bg-amber-500',
  end: 'bg-red-500',
}

const WorkflowEditorPage: React.FC = () => {
  const { t } = useI18n()
  const { theme } = useAppStore()
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null)
  const [loading, setLoading] = useState(true)
  const [nodes, setNodes] = useState<WorkflowNode[]>([])
  const [edges, setEdges] = useState<WorkflowEdge[]>([])
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [dragNode, setDragNode] = useState<string | null>(null)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const [running, setRunning] = useState(false)
  const [runStatus, setRunStatus] = useState<string | null>(null)

  const isDark = theme === 'dark'

  useEffect(() => {
    fetchWorkflows()
  }, [])

  const fetchWorkflows = async () => {
    try {
      setLoading(true)
      const data = await apiClient.listWorkflows()
      setWorkflows(data.map((w: any) => ({
        id: w.id || w.workflow_id || '',
        name: w.name || w.title || 'Untitled',
        description: w.description || '',
        nodes: w.nodes || [],
        edges: w.edges || [],
        status: w.status,
      })))
    } catch (err) {
      console.error('Failed to load workflows:', err)
    } finally {
      setLoading(false)
    }
  }

  const openWorkflow = (wf: Workflow) => {
    setSelectedWorkflow(wf)
    setNodes(wf.nodes.length > 0 ? wf.nodes : [
      { id: 'start-1', type: 'start', label: 'Start', x: 100, y: 200 },
      { id: 'end-1', type: 'end', label: 'End', x: 500, y: 200 },
    ])
    setEdges(wf.edges.length > 0 ? wf.edges : [
      { id: 'e1', source: 'start-1', target: 'end-1' },
    ])
  }

  const addNode = (type: WorkflowNode['type']) => {
    const id = `${type}-${Date.now()}`
    const labels: Record<string, string> = { start: 'Start', task: 'Task', condition: 'Condition', end: 'End' }
    setNodes(prev => [...prev, {
      id,
      type,
      label: labels[type],
      x: 200 + Math.random() * 200,
      y: 100 + Math.random() * 200,
    }])
    setSelectedNode(id)
  }

  const removeNode = (id: string) => {
    setNodes(prev => prev.filter(n => n.id !== id))
    setEdges(prev => prev.filter(e => e.source !== id && e.target !== id))
    setSelectedNode(null)
  }

  const handleNodeMouseDown = (e: React.MouseEvent, nodeId: string) => {
    e.preventDefault()
    const node = nodes.find(n => n.id === nodeId)
    if (!node) return
    setDragNode(nodeId)
    setDragOffset({ x: e.clientX - node.x, y: e.clientY - node.y })
    setSelectedNode(nodeId)
  }

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragNode) return
    setNodes(prev => prev.map(n =>
      n.id === dragNode ? { ...n, x: e.clientX - dragOffset.x, y: e.clientY - dragOffset.y } : n
    ))
  }, [dragNode, dragOffset])

  const handleMouseUp = () => {
    setDragNode(null)
  }

  const runWorkflow = async () => {
    if (!selectedWorkflow) return
    setRunning(true)
    setRunStatus('running')
    try {
      await apiClient.runWorkflow(selectedWorkflow.id)
      setRunStatus('completed')
    } catch {
      setRunStatus('failed')
    } finally {
      setRunning(false)
      setTimeout(() => setRunStatus(null), 3000)
    }
  }

  const updateNodeLabel = (id: string, label: string) => {
    setNodes(prev => prev.map(n => n.id === id ? { ...n, label } : n))
  }

  // SVG edge rendering
  const renderEdges = () => {
    return edges.map(edge => {
      const source = nodes.find(n => n.id === edge.source)
      const target = nodes.find(n => n.id === edge.target)
      if (!source || !target) return null
      const x1 = source.x + 60
      const y1 = source.y + 20
      const x2 = target.x + 60
      const y2 = target.y + 20
      const midX = (x1 + x2) / 2
      return (
        <g key={edge.id}>
          <path
            d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
            fill="none"
            stroke={isDark ? '#64748b' : '#94a3b8'}
            strokeWidth={2}
            markerEnd="url(#arrowhead)"
          />
        </g>
      )
    })
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className={clsx(
        'flex items-center justify-between px-4 py-3 border-b',
        isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
      )}>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">{t('workflows.editor', 'Workflow Editor')}</h1>
          {selectedWorkflow && (
            <span className={clsx('text-sm px-2 py-0.5 rounded', isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600')}>
              {selectedWorkflow.name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => addNode('task')} className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            + Task
          </button>
          <button onClick={() => addNode('condition')} className="px-3 py-1.5 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700">
            + Condition
          </button>
          {selectedWorkflow && (
            <button
              onClick={runWorkflow}
              disabled={running}
              className="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {running ? '⏳ Running...' : '▶ Run'}
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Workflow List Sidebar */}
        <div className={clsx(
          'w-56 border-r overflow-y-auto p-3',
          isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-slate-50'
        )}>
          <h3 className="text-xs font-semibold uppercase tracking-wide mb-2 text-slate-500">Workflows</h3>
          {loading ? (
            <p className="text-xs text-slate-400">Loading...</p>
          ) : workflows.length === 0 ? (
            <p className="text-xs text-slate-400">No workflows yet</p>
          ) : (
            <div className="space-y-1">
              {workflows.map(wf => (
                <button
                  key={wf.id}
                  onClick={() => openWorkflow(wf)}
                  className={clsx(
                    'w-full text-left px-3 py-2 rounded-lg text-sm transition-colors',
                    selectedWorkflow?.id === wf.id
                      ? 'bg-blue-600 text-white'
                      : isDark ? 'hover:bg-slate-800 text-slate-300' : 'hover:bg-slate-200 text-slate-700'
                  )}
                >
                  {wf.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Canvas */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
        <div
          role="application"
          aria-label="Workflow canvas"
          className={clsx('flex-1 relative overflow-hidden', isDark ? 'bg-slate-950' : 'bg-slate-100')}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {!selectedWorkflow ? (
            <div className="flex items-center justify-center h-full">
              <p className={clsx('text-sm', isDark ? 'text-slate-500' : 'text-slate-400')}>
                Select a workflow to edit, or create a new one
              </p>
            </div>
          ) : (
            <>
              {/* SVG Edges */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                <defs>
                  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                    <polygon points="0 0, 10 3.5, 0 7" fill={isDark ? '#64748b' : '#94a3b8'} />
                  </marker>
                </defs>
                {renderEdges()}
              </svg>

              {/* Nodes */}
              {nodes.map(node => (
                <div
                  key={node.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`Node: ${node.label}`}
                  className={clsx(
                    'absolute w-[120px] cursor-move select-none rounded-lg border-2 shadow-sm transition-shadow',
                    selectedNode === node.id ? 'border-blue-500 shadow-md' : isDark ? 'border-slate-600' : 'border-slate-300',
                    isDark ? 'bg-slate-800' : 'bg-white'
                  )}
                  style={{ left: node.x, top: node.y }}
                  onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedNode(node.id); }}
                >
                  <div className={clsx('h-1.5 rounded-t-md', NODE_COLORS[node.type])} />
                  <div className="p-2">
                    <p className="text-xs font-medium truncate">{node.label}</p>
                    <p className={clsx('text-[10px]', isDark ? 'text-slate-500' : 'text-slate-400')}>{node.type}</p>
                  </div>
                  {selectedNode === node.id && node.type !== 'start' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); removeNode(node.id) }}
                      className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center hover:bg-red-600"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}

              {/* Run Status */}
              {runStatus && (
                <div className={clsx(
                  'absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm font-medium',
                  runStatus === 'completed' ? 'bg-green-500 text-white' :
                  runStatus === 'failed' ? 'bg-red-500 text-white' :
                  'bg-blue-500 text-white'
                )}>
                  {runStatus === 'completed' ? '✓ Workflow completed' :
                   runStatus === 'failed' ? '✗ Workflow failed' : '⏳ Running...'}
                </div>
              )}
            </>
          )}
        </div>

        {/* Properties Panel */}
        {selectedNode && (
          <div className={clsx(
            'w-64 border-l p-4 overflow-y-auto',
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          )}>
            <h3 className="text-sm font-semibold mb-3">Node Properties</h3>
            {(() => {
              const node = nodes.find(n => n.id === selectedNode)
              if (!node) return null
              return (
                <div className="space-y-3">
                  <div>
                    <label htmlFor="node-label" className="block text-xs font-medium mb-1">Label</label>
                    <input
                      id="node-label"
                      type="text"
                      value={node.label}
                      onChange={e => updateNodeLabel(node.id, e.target.value)}
                      className={clsx(
                        'w-full px-2 py-1.5 rounded border text-sm',
                        isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-slate-300'
                      )}
                    />
                  </div>
                  <div>
                    <span className="block text-xs font-medium mb-1">Type</span>
                    <p className={clsx('text-sm', isDark ? 'text-slate-400' : 'text-slate-500')}>{node.type}</p>
                  </div>
                  <div>
                    <span className="block text-xs font-medium mb-1">ID</span>
                    <p className={clsx('text-xs font-mono', isDark ? 'text-slate-500' : 'text-slate-400')}>{node.id}</p>
                  </div>
                </div>
              )
            })()}
          </div>
        )}
      </div>
    </div>
  )
}

export default WorkflowEditorPage
