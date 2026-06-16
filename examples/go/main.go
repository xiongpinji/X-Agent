package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

// XAgentClient wraps the X-Agent API
type XAgentClient struct {
	baseURL string
	apiKey  string
	client  *http.Client
}

// TaskRequest represents a task submission
type TaskRequest struct {
	Prompt  string                 `json:"prompt"`
	Context map[string]interface{} `json:"context,omitempty"`
	Tools   []string               `json:"tools,omitempty"`
	Timeout int                    `json:"timeout,omitempty"`
}

// RunResponse represents a task run response
type RunResponse struct {
	ID        string    `json:"id"`
	Status    string    `json:"status"`
	Output    string    `json:"output,omitempty"`
	Error     string    `json:"error,omitempty"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// TaskRun represents an active task run
type TaskRun struct {
	ID     string
	client *XAgentClient
}

// NewXAgentClient creates a new X-Agent client
func NewXAgentClient(baseURL, apiKey string) *XAgentClient {
	return &XAgentClient{
		baseURL: strings.TrimSuffix(baseURL, "/"),
		apiKey:  apiKey,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// SubmitTask submits a new task and returns a TaskRun
func (c *XAgentClient) SubmitTask(ctx context.Context, task TaskRequest) (*TaskRun, error) {
	body, err := json.Marshal(task)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(
		ctx,
		"POST",
		fmt.Sprintf("%s/api/v1/agent/run", c.baseURL),
		bytes.NewReader(body),
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", c.apiKey)

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("submit task: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error: %d - %s", resp.StatusCode, string(body))
	}

	var result RunResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &TaskRun{ID: result.ID, client: c}, nil
}

// Status gets the current status of a task
func (r *TaskRun) Status(ctx context.Context) (*RunResponse, error) {
	req, err := http.NewRequestWithContext(
		ctx,
		"GET",
		fmt.Sprintf("%s/api/v1/agent/run/%s", r.client.baseURL, r.ID),
		nil,
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("X-API-Key", r.client.apiKey)

	resp, err := r.client.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get status: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var result RunResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// Wait blocks until the task completes or times out
func (r *TaskRun) Wait(ctx context.Context, timeout time.Duration) (*RunResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		status, err := r.Status(ctx)
		if err != nil {
			return nil, err
		}

		if status.Status == "completed" || status.Status == "failed" {
			return status, nil
		}

		select {
		case <-ticker.C:
			// Poll again
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}
}

// GetRuns retrieves task history
func (c *XAgentClient) GetRuns(ctx context.Context, limit int, status string) ([]RunResponse, error) {
	req, err := http.NewRequestWithContext(
		ctx,
		"GET",
		fmt.Sprintf("%s/api/v1/agent/runs?limit=%d&status=%s", c.baseURL, limit, status),
		nil,
	)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	req.Header.Set("X-API-Key", c.apiKey)

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get runs: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API error: %d", resp.StatusCode)
	}

	var result struct {
		Runs []RunResponse `json:"runs"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return result.Runs, nil
}

// Example 1: Basic task submission
func exampleBasicTask(client *XAgentClient) {
	fmt.Println("Example 1: Basic Task Submission")
	fmt.Println(strings.Repeat("=", 50))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Submit task
	fmt.Println("Submitting task...")
	task := TaskRequest{
		Prompt: "Analyze this Python code for security issues",
		Context: map[string]interface{}{
			"language": "python",
			"code": `def login(user, pwd):
    query = f"SELECT * FROM users WHERE username='{user}'"
    return db.execute(query)`,
		},
	}

	run, err := client.SubmitTask(ctx, task)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}
	fmt.Printf("Task ID: %s\n", run.ID)

	// Wait for completion
	fmt.Println("Waiting for completion...")
	result, err := run.Wait(ctx, 5*time.Minute)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}

	fmt.Printf("\nStatus: %s\n", result.Status)
	if result.Status == "completed" {
		fmt.Printf("Output: %s\n", result.Output)
		fmt.Println("\n✓ Task completed successfully")
	} else {
		fmt.Printf("Error: %s\n", result.Error)
	}
	fmt.Println()
}

// Example 2: Polling task status
func examplePollingTask(client *XAgentClient) {
	fmt.Println("Example 2: Polling Task Status")
	fmt.Println(strings.Repeat("=", 50))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Submit task
	fmt.Println("Submitting task...")
	task := TaskRequest{
		Prompt: "Generate API documentation",
	}

	run, err := client.SubmitTask(ctx, task)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}
	fmt.Printf("Task ID: %s\n", run.ID)

	// Poll for status
	fmt.Println("Polling for status...")
	for {
		status, err := run.Status(ctx)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			return
		}

		fmt.Printf("Status: %s\n", status.Status)

		if status.Status == "completed" || status.Status == "failed" {
			break
		}

		time.Sleep(5 * time.Second)
	}
	fmt.Println()
}

// Example 3: Batch submit tasks
func exampleBatchTasks(client *XAgentClient) {
	fmt.Println("Example 3: Batch Submit Multiple Tasks")
	fmt.Println(strings.Repeat("=", 50))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	tasks := []TaskRequest{
		{Prompt: "Check code style"},
		{Prompt: "Analyze security"},
		{Prompt: "Generate tests"},
		{Prompt: "Create docs"},
	}

	// Submit all tasks
	fmt.Println("Submitting tasks...")
	var runs []*TaskRun
	for i, task := range tasks {
		run, err := client.SubmitTask(ctx, task)
		if err != nil {
			fmt.Printf("Error submitting task %d: %v\n", i, err)
			continue
		}
		fmt.Printf("  Task %d: %s\n", i+1, run.ID)
		runs = append(runs, run)
	}

	// Wait for all to complete
	fmt.Println("Waiting for completion...")
	for i, run := range runs {
		result, err := run.Wait(ctx, 5*time.Minute)
		if err != nil {
			fmt.Printf("Error waiting for task %d: %v\n", i, err)
			continue
		}
		status := "✓"
		if result.Status != "completed" {
			status = "✗"
		}
		fmt.Printf("  %s Task %d: %s\n", status, i+1, result.Status)
	}
	fmt.Println()
}

// Example 4: Get task history
func exampleTaskHistory(client *XAgentClient) {
	fmt.Println("Example 4: Get Task History")
	fmt.Println(strings.Repeat("=", 50))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	runs, err := client.GetRuns(ctx, 10, "completed")
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}

	fmt.Println("Recent completed tasks:")
	for i, run := range runs {
		fmt.Printf("  %d. %s (created: %s)\n", i+1, run.ID, run.CreatedAt.Format("2006-01-02 15:04:05"))
	}
	fmt.Println()
}

// Example 5: Error handling and retries
func exampleErrorHandling(client *XAgentClient) {
	fmt.Println("Example 5: Error Handling and Retries")
	fmt.Println(strings.Repeat("=", 50))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	task := TaskRequest{
		Prompt:  "Analyze codebase",
		Timeout: 60,
	}

	maxRetries := 3
	var result *RunResponse
	var err error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		fmt.Printf("Attempt %d/%d\n", attempt, maxRetries)

		run, err := client.SubmitTask(ctx, task)
		if err != nil {
			fmt.Printf("  Error: %v\n", err)
			if attempt < maxRetries {
				fmt.Println("  Retrying...")
				time.Sleep(time.Duration(attempt) * time.Second)
				continue
			}
			return
		}

		result, err = run.Wait(ctx, 5*time.Minute)
		if err != nil {
			fmt.Printf("  Error waiting: %v\n", err)
			if attempt < maxRetries {
				fmt.Println("  Retrying...")
				time.Sleep(time.Duration(attempt) * time.Second)
				continue
			}
			return
		}

		if result.Status == "completed" {
			fmt.Printf("Success on attempt %d\n", attempt)
			break
		}

		if attempt < maxRetries {
			fmt.Println("  Retrying...")
			time.Sleep(time.Duration(attempt) * time.Second)
		}
	}

	if result != nil && result.Status == "completed" {
		fmt.Println("✓ Task completed successfully")
	} else {
		fmt.Println("✗ Task failed")
	}
	fmt.Println()
}

// Example 6: Handle signals gracefully
func exampleSignalHandling(client *XAgentClient) {
	fmt.Println("Example 6: Signal Handling (Cancel Tasks)")
	fmt.Println(strings.Repeat("=", 50))

	// Create context that can be cancelled
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Setup signal handler
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		fmt.Printf("\nReceived signal: %v\n", sig)
		fmt.Println("Cancelling task...")
		cancel()
	}()

	// Submit task
	fmt.Println("Submitting long-running task (press Ctrl+C to cancel)...")
	task := TaskRequest{
		Prompt: "Deep analysis of large codebase",
	}

	run, err := client.SubmitTask(ctx, task)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}
	fmt.Printf("Task ID: %s\n", run.ID)

	// Wait with signal handling
	result, err := run.Wait(ctx, 10*time.Minute)
	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Println("Task cancelled by user")
		} else {
			fmt.Printf("Error: %v\n", err)
		}
		return
	}

	fmt.Printf("Task status: %s\n", result.Status)
	fmt.Println()
}

func main() {
	baseURL := flag.String("url", "http://localhost:8000", "X-Agent base URL")
	apiKey := flag.String("key", os.Getenv("XAGENT_API_KEY"), "API key (or set XAGENT_API_KEY env var)")
	example := flag.String("example", "basic", "Example to run (basic, polling, batch, history, errors, signals, all)")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, `X-Agent Go Integration Examples

Usage: %s [flags] -example <name>

Flags:
`, os.Args[0])
		flag.PrintDefaults()

		fmt.Fprintf(os.Stderr, `
Examples:
  basic     - Basic task submission and polling
  polling   - Poll task status manually
  batch     - Batch submit multiple tasks
  history   - Get task history
  errors    - Error handling and retries
  signals   - Handle OS signals gracefully
  all       - Run all examples

Example:
  %s -url http://localhost:8000 -key sk_xxx -example basic
`, os.Args[0])
	}

	flag.Parse()

	if *apiKey == "" {
		fmt.Fprintf(os.Stderr, "Error: API key required\n")
		flag.Usage()
		os.Exit(1)
	}

	client := NewXAgentClient(*baseURL, *apiKey)

	// Run selected example(s)
	switch *example {
	case "basic":
		exampleBasicTask(client)
	case "polling":
		examplePollingTask(client)
	case "batch":
		exampleBatchTasks(client)
	case "history":
		exampleTaskHistory(client)
	case "errors":
		exampleErrorHandling(client)
	case "signals":
		exampleSignalHandling(client)
	case "all":
		exampleBasicTask(client)
		examplePollingTask(client)
		exampleBatchTasks(client)
		exampleTaskHistory(client)
		exampleErrorHandling(client)
	default:
		fmt.Fprintf(os.Stderr, "Unknown example: %s\n", *example)
		flag.Usage()
		os.Exit(1)
	}
}
