import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Agent, Task, Memory, Tool, ChatMessage } from '@/services/api'

export interface AppState {
  // User state
  user: { id: string; name: string; email: string } | null
  isAuthenticated: boolean
  setUser: (user: AppState['user']) => void
  logout: () => void

  // UI state
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  toggleTheme: () => void
  toggleSidebar: () => void

  // Agents
  agents: Agent[]
  currentAgent: Agent | null
  setAgents: (agents: Agent[]) => void
  setCurrentAgent: (agent: Agent | null) => void
  addAgent: (agent: Agent) => void
  removeAgent: (id: string) => void

  // Tasks
  tasks: Task[]
  currentTask: Task | null
  setTasks: (tasks: Task[]) => void
  setCurrentTask: (task: Task | null) => void
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  removeTask: (id: string) => void

  // Memory
  memories: Memory[]
  setMemories: (memories: Memory[]) => void
  addMemory: (memory: Memory) => void
  updateMemory: (id: string, updates: Partial<Memory>) => void
  removeMemory: (id: string) => void

  // Tools
  tools: Tool[]
  setTools: (tools: Tool[]) => void
  updateTool: (id: string, updates: Partial<Tool>) => void

  // Chat
  messages: ChatMessage[]
  addMessage: (message: ChatMessage) => void
  clearMessages: () => void

  // Connection state
  isConnected: boolean
  setConnected: (connected: boolean) => void

  // Loading state
  isLoading: boolean
  setLoading: (loading: boolean) => void

  // Error state
  error: string | null
  setError: (error: string | null) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // User state
      user: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      logout: () => set({ user: null, isAuthenticated: false }),

      // UI state
      theme: 'light',
      sidebarOpen: true,
      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'light' ? 'dark' : 'light',
        })),
      toggleSidebar: () =>
        set((state) => ({
          sidebarOpen: !state.sidebarOpen,
        })),

      // Agents
      agents: [],
      currentAgent: null,
      setAgents: (agents) => set({ agents }),
      setCurrentAgent: (currentAgent) => set({ currentAgent }),
      addAgent: (agent) =>
        set((state) => ({
          agents: [...state.agents, agent],
        })),
      removeAgent: (id) =>
        set((state) => ({
          agents: state.agents.filter((a) => a.id !== id),
        })),

      // Tasks
      tasks: [],
      currentTask: null,
      setTasks: (tasks) => set({ tasks }),
      setCurrentTask: (currentTask) => set({ currentTask }),
      addTask: (task) =>
        set((state) => ({
          tasks: [...state.tasks, task],
        })),
      updateTask: (id, updates) =>
        set((state) => ({
          tasks: state.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
        })),
      removeTask: (id) =>
        set((state) => ({
          tasks: state.tasks.filter((t) => t.id !== id),
        })),

      // Memory
      memories: [],
      setMemories: (memories) => set({ memories }),
      addMemory: (memory) =>
        set((state) => ({
          memories: [...state.memories, memory],
        })),
      updateMemory: (id, updates) =>
        set((state) => ({
          memories: state.memories.map((m) => (m.id === id ? { ...m, ...updates } : m)),
        })),
      removeMemory: (id) =>
        set((state) => ({
          memories: state.memories.filter((m) => m.id !== id),
        })),

      // Tools
      tools: [],
      setTools: (tools) => set({ tools }),
      updateTool: (id, updates) =>
        set((state) => ({
          tools: state.tools.map((t) => (t.id === id ? { ...t, ...updates } : t)),
        })),

      // Chat
      messages: [],
      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
        })),
      clearMessages: () => set({ messages: [] }),

      // Connection state
      isConnected: false,
      setConnected: (isConnected) => set({ isConnected }),

      // Loading state
      isLoading: false,
      setLoading: (isLoading) => set({ isLoading }),

      // Error state
      error: null,
      setError: (error) => set({ error }),
    }),
    {
      name: 'x-agent-store',
      partialize: (state) => ({
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
        user: state.user,
        isAuthenticated: !!state.user,
      }),
    }
  )
)

export default useAppStore
