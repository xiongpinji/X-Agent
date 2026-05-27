/**
 * Agent Store (Zustand)
 *
 * Global state management for agent execution, tasks, questions, and UI state.
 * Provides centralized state and actions for the agent workspace.
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { APIClient, AgentRun, Task, Question, FileMetadata } from './apiClient';
import { SSEClient, AnyStreamEvent } from './sseClient';

export interface AgentState {
  // API and SSE clients
  apiClient: APIClient;
  sseClient: SSEClient;

  // Current run
  currentRun: AgentRun | null;
  runId: string | null;

  // Collections
  tasks: Task[];
  messages: AnyStreamEvent[];
  pendingQuestions: Question[];
  selectedFiles: FileMetadata[];

  // UI state
  isRunning: boolean;
  isConnected: boolean;
  error: string | null;
  selectedTaskId: string | null;
  selectedQuestionId: string | null;
  selectedFilePath: string | null;

  // Actions
  startRun: (task: string, extraContext?: Record<string, any>) => Promise<void>;
  stopRun: () => Promise<void>;
  connectStream: (runId: string) => void;
  disconnectStream: () => void;
  addMessage: (message: AnyStreamEvent) => void;
  updateTask: (taskId: string, updates: Partial<Task>) => Promise<void>;
  fetchTasks: (runId?: string) => Promise<void>;
  fetchPendingQuestions: (runId: string) => Promise<void>;
  answerQuestion: (questionId: string, answer: any) => Promise<void>;
  cancelQuestion: (questionId: string) => Promise<void>;
  selectTask: (taskId: string | null) => void;
  selectQuestion: (questionId: string | null) => void;
  selectFile: (filePath: string | null) => void;
  clearMessages: () => void;
  clearError: () => void;
  setError: (error: string) => void;
}

const createAgentStore = () =>
  create<AgentState>()(
    devtools(
      persist(
        (set, get) => ({
          // Initial state
          apiClient: new APIClient(),
          sseClient: new SSEClient(),
          currentRun: null,
          runId: null,
          tasks: [],
          messages: [],
          pendingQuestions: [],
          selectedFiles: [],
          isRunning: false,
          isConnected: false,
          error: null,
          selectedTaskId: null,
          selectedQuestionId: null,
          selectedFilePath: null,

          // Start agent run
          startRun: async (task: string, extraContext?: Record<string, any>) => {
            try {
              set({ isRunning: true, error: null });
              const { apiClient } = get();

              const run = await apiClient.startAgentRun(task, extraContext);
              set({
                currentRun: run,
                runId: run.run_id,
                messages: [],
                tasks: [],
                pendingQuestions: [],
              });

              // Connect to stream
              get().connectStream(run.run_id);
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message, isRunning: false });
              throw error;
            }
          },

          // Stop agent run
          stopRun: async () => {
            try {
              const { apiClient, runId } = get();
              if (!runId) return;

              await apiClient.cancelAgentRun(runId);
              get().disconnectStream();
              set({ isRunning: false });
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message });
              throw error;
            }
          },

          // Connect to SSE stream
          connectStream: (runId: string) => {
            const { sseClient } = get();

            sseClient.connect(
              runId,
              (event) => {
                // Handle incoming events
                get().addMessage(event);

                // Update UI state based on event type
                if (event.event_type === 'completion') {
                  set({ isRunning: false, isConnected: false });
                }
              },
              (error) => {
                set({ error: error.message });
              },
              () => {
                set({ isConnected: false });
              }
            );

            set({ isConnected: true });
          },

          // Disconnect from stream
          disconnectStream: () => {
            const { sseClient } = get();
            sseClient.disconnect();
            set({ isConnected: false });
          },

          // Add message to stream
          addMessage: (message: AnyStreamEvent) => {
            set((state) => ({
              messages: [...state.messages, message].slice(-1000), // Keep last 1000 messages
            }));
          },

          // Update task
          updateTask: async (taskId: string, updates: Partial<Task>) => {
            try {
              const { apiClient } = get();
              const updated = await apiClient.updateTask(taskId, updates);

              set((state) => ({
                tasks: state.tasks.map((t) => (t.task_id === taskId ? updated : t)),
              }));
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message });
              throw error;
            }
          },

          // Fetch tasks
          fetchTasks: async (runId?: string) => {
            try {
              const { apiClient } = get();
              const data = await apiClient.getTasks(runId);
              set({ tasks: data.tasks });
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message });
              throw error;
            }
          },

          // Fetch pending questions
          fetchPendingQuestions: async (runId: string) => {
            try {
              const { apiClient } = get();
              const data = await apiClient.getPendingQuestions(runId);
              set({ pendingQuestions: data.questions });
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message });
              throw error;
            }
          },

          // Answer question
          answerQuestion: async (questionId: string, answer: any) => {
            try {
              const { apiClient } = get();
              await apiClient.answerQuestion(questionId, answer);

              set((state) => ({
                pendingQuestions: state.pendingQuestions.filter(
                  (q) => q.question_id !== questionId
                ),
              }));
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message });
              throw error;
            }
          },

          // Cancel question
          cancelQuestion: async (questionId: string) => {
            try {
              const { apiClient } = get();
              await apiClient.cancelQuestion(questionId);

              set((state) => ({
                pendingQuestions: state.pendingQuestions.filter(
                  (q) => q.question_id !== questionId
                ),
              }));
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              set({ error: message });
              throw error;
            }
          },

          // Select task
          selectTask: (taskId: string | null) => {
            set({ selectedTaskId: taskId });
          },

          // Select question
          selectQuestion: (questionId: string | null) => {
            set({ selectedQuestionId: questionId });
          },

          // Select file
          selectFile: (filePath: string | null) => {
            set({ selectedFilePath: filePath });
          },

          // Clear messages
          clearMessages: () => {
            set({ messages: [] });
          },

          // Clear error
          clearError: () => {
            set({ error: null });
          },

          // Set error
          setError: (error: string) => {
            set({ error });
          },
        }),
        {
          name: 'agent-store',
          partialize: (state) => ({
            // Only persist non-sensitive data
            currentRun: state.currentRun,
            runId: state.runId,
            selectedTaskId: state.selectedTaskId,
            selectedQuestionId: state.selectedQuestionId,
            selectedFilePath: state.selectedFilePath,
          }),
        }
      ),
      { name: 'AgentStore' }
    )
  );

export const useAgentStore = createAgentStore();

export default useAgentStore;
