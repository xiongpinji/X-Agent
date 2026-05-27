/**
 * Component Integration Tests
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import StreamingOutput from '../components/StreamingOutput';
import TaskList from '../components/TaskList';
import ProgressIndicator from '../components/ProgressIndicator';

describe('StreamingOutput Component', () => {
  beforeEach(() => {
    global.EventSource = jest.fn(() => ({
      addEventListener: jest.fn(),
      close: jest.fn(),
      readyState: EventSource.OPEN,
    })) as any;
  });

  test('should render streaming output', () => {
    render(<StreamingOutput runId="test-run-1" />);

    expect(screen.getByText(/Connected|Disconnected/)).toBeInTheDocument();
  });

  test('should display connection status', () => {
    render(<StreamingOutput runId="test-run-1" />);

    const statusElement = screen.getByText(/Connected|Disconnected/);
    expect(statusElement).toBeInTheDocument();
  });

  test('should show waiting message when no events', () => {
    render(<StreamingOutput runId="test-run-1" />);

    expect(screen.getByText(/Waiting for events/)).toBeInTheDocument();
  });

  test('should call onComplete callback', async () => {
    const onComplete = jest.fn();
    render(
      <StreamingOutput runId="test-run-1" onComplete={onComplete} />
    );

    // Simulate completion event
    const eventSource = (global.EventSource as jest.Mock).mock.results[0].value;
    const completionHandler = eventSource.addEventListener.mock.calls.find(
      (call: any) => call[0] === 'completion'
    )?.[1];

    completionHandler?.(
      new MessageEvent('completion', {
        data: JSON.stringify({
          event_type: 'completion',
          status: 'success',
          result: { answer: 'test' },
          summary: {},
          timestamp: new Date().toISOString(),
          run_id: 'test-run-1',
        }),
      })
    );

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalled();
    });
  });
});

describe('TaskList Component', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  test('should render task list', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tasks: [
          {
            task_id: 'task-1',
            title: 'Test Task',
            description: 'Test description',
            status: 'completed',
            priority: 'high',
            progress: 1,
            created_at: new Date().toISOString(),
            depends_on: [],
            blocks: [],
            tags: [],
            metadata: {},
          },
        ],
        total: 1,
        completed: 1,
        in_progress: 0,
        failed: 0,
        pending: 0,
      }),
    });

    render(<TaskList runId="test-run-1" />);

    await waitFor(() => {
      expect(screen.getByText('Test Task')).toBeInTheDocument();
    });
  });

  test('should display task stats', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tasks: [],
        total: 5,
        completed: 3,
        in_progress: 1,
        failed: 1,
        pending: 0,
      }),
    });

    render(<TaskList runId="test-run-1" />);

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument(); // Total
      expect(screen.getByText('3')).toBeInTheDocument(); // Completed
    });
  });

  test('should handle refresh', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        tasks: [],
        total: 0,
        completed: 0,
        in_progress: 0,
        failed: 0,
        pending: 0,
      }),
    });

    render(<TaskList runId="test-run-1" />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(2); // Initial + refresh
    });
  });

  test('should show empty state', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tasks: [],
        total: 0,
        completed: 0,
        in_progress: 0,
        failed: 0,
        pending: 0,
      }),
    });

    render(<TaskList runId="test-run-1" />);

    await waitFor(() => {
      expect(screen.getByText('No tasks found')).toBeInTheDocument();
    });
  });
});

describe('ProgressIndicator Component', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  test('should render progress indicator', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        events: [
          {
            event_type: 'progress',
            overall_progress: 0.5,
            current_step: 'Processing',
            total_steps: 10,
            completed_steps: 5,
            timestamp: new Date().toISOString(),
            run_id: 'test-run-1',
          },
        ],
      }),
    });

    render(<ProgressIndicator runId="test-run-1" />);

    await waitFor(() => {
      expect(screen.getByText('Processing')).toBeInTheDocument();
    });
  });

  test('should display progress percentage', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        events: [
          {
            event_type: 'progress',
            overall_progress: 0.75,
            current_step: 'Step 3',
            total_steps: 4,
            completed_steps: 3,
            timestamp: new Date().toISOString(),
            run_id: 'test-run-1',
          },
        ],
      }),
    });

    render(<ProgressIndicator runId="test-run-1" />);

    await waitFor(() => {
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  test('should show step breakdown', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        events: [
          {
            event_type: 'progress',
            overall_progress: 0.5,
            current_step: 'Step 2',
            total_steps: 4,
            completed_steps: 2,
            timestamp: new Date().toISOString(),
            run_id: 'test-run-1',
          },
        ],
      }),
    });

    render(<ProgressIndicator runId="test-run-1" />);

    await waitFor(() => {
      expect(screen.getByText('2 / 4')).toBeInTheDocument();
    });
  });
});

describe('Component Integration', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
    global.EventSource = jest.fn(() => ({
      addEventListener: jest.fn(),
      close: jest.fn(),
      readyState: EventSource.OPEN,
    })) as any;
  });

  test('should handle multiple components together', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        tasks: [],
        total: 0,
        completed: 0,
        in_progress: 0,
        failed: 0,
        pending: 0,
        events: [],
      }),
    });

    const { container } = render(
      <div>
        <StreamingOutput runId="test-run-1" />
        <TaskList runId="test-run-1" />
        <ProgressIndicator runId="test-run-1" />
      </div>
    );

    expect(container).toBeInTheDocument();
  });
});
