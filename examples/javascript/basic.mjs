/**
 * X-Agent Node.js / Browser Integration Example
 * 
 * This example demonstrates how to integrate with X-Agent using JavaScript.
 * 
 * Installation:
 *   npm install xagent-sdk
 * 
 * Browser (CDN):
 *   <script src="https://unpkg.com/xagent-sdk/dist/browser.js"></script>
 * 
 * Basic usage:
 *   const agent = new XAgent({ 
 *     baseUrl: "http://localhost:8000",
 *     apiKey: "sk_your_key_here"
 *   });
 *   const result = await agent.submitTask("Analyze my code");
 */

// Node.js imports
// const { XAgent } = require('xagent-sdk');

// Browser: XAgent is available globally as window.XAgent


/**
 * Example 1: Basic task submission
 */
async function exampleBasicTask() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
  });

  try {
    // Submit a task
    console.log("Submitting task...");
    const run = await agent.submitTask(
      "Analyze this Python code for security vulnerabilities"
    );
    console.log(`Task ID: ${run.id}`);

    // Wait for completion
    console.log("Waiting for completion...");
    const result = await run.wait({ timeout: 300000 });

    console.log(`Status: ${result.status}`);
    console.log(`Output:\n${result.output}`);

    if (result.status === "completed") {
      console.log("\n✓ Task completed successfully");
      console.log(`Metrics: ${JSON.stringify(result.metrics)}`);
    } else {
      console.error(`\n✗ Task failed: ${result.error}`);
    }
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 2: Stream task output in real-time
 */
async function exampleStreamingTask() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
  });

  const taskPrompt = "Generate documentation for my API endpoints";

  console.log("Task output:");
  console.log("-".repeat(50));

  try {
    // Stream updates as they arrive
    for await (const update of agent.submitTaskStream(taskPrompt)) {
      switch (update.event) {
        case "output":
          process.stdout.write(update.data);
          break;
        case "status":
          console.log(`\n[${update.data}]`);
          break;
        case "error":
          console.error(`\n❌ Error: ${update.data}`);
          break;
        case "complete":
          console.log(`\n✓ Complete: ${update.data}`);
          break;
      }
    }
  } catch (error) {
    console.error("Stream error:", error.message);
  }

  console.log("-".repeat(50));
}


/**
 * Example 3: Batch submit multiple tasks
 */
async function exampleBatchTasks() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
  });

  const tasks = [
    "Check code style and formatting",
    "Analyze security vulnerabilities",
    "Generate unit test cases",
    "Create API documentation",
  ];

  try {
    // Submit all tasks
    const runs = [];
    for (const prompt of tasks) {
      const run = await agent.submitTask(prompt);
      runs.push(run);
      console.log(`Submitted: ${prompt} (ID: ${run.id})`);
    }

    // Wait for all to complete
    console.log("\nWaiting for all tasks...");
    const results = await Promise.allSettled(
      runs.map((run) => run.wait({ timeout: 600000 }))
    );

    // Process results
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        const isSuccess = result.value.status === "completed";
        const status = isSuccess ? "✓" : "✗";
        console.log(`${status} ${tasks[index]}: ${result.value.status}`);
      } else {
        console.error(`✗ ${tasks[index]}: ${result.reason}`);
      }
    });
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 4: Poll for task status
 */
async function examplePollingTask() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
  });

  try {
    const taskPrompt = "Refactor my legacy module";
    const run = await agent.submitTask(taskPrompt);
    console.log(`Task submitted: ${run.id}`);

    // Poll for status
    let completed = false;
    while (!completed) {
      const status = await run.status();
      console.log(`Status: ${status.status} - Progress: ${status.progress}%`);

      if (["completed", "failed"].includes(status.status)) {
        completed = true;
      } else {
        // Wait 5 seconds before next poll
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }

    // Get final result
    const result = await run.result();
    console.log(`\nFinal result:\n${result}`);
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 5: Task with specific tools
 */
async function exampleWithTools() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
  });

  try {
    const run = await agent.submitTask({
      prompt: "Clone and analyze the repository",
      tools: ["git", "code_analyzer", "file_reader"],
      context: {
        repoUrl: "https://github.com/example/repo",
      },
    });

    const result = await run.wait();
    console.log(`Result: ${result.output}`);
    console.log(`Tools used: ${JSON.stringify(result.toolsUsed)}`);
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 6: Error handling and retries
 */
async function exampleErrorHandling() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
    timeout: 30000,
    maxRetries: 3,
  });

  try {
    const run = await agent.submitTask({
      prompt: "Analyze the codebase",
      timeout: 60000,
    });

    let result = await run.wait();

    if (result.status === "failed") {
      console.error(`Task failed: ${result.error}`);
      console.error(`Error code: ${result.errorCode}`);

      // Optionally retry
      if (result.errorCode === "timeout") {
        console.log("Retrying with longer timeout...");
        const retryRun = await agent.submitTask(
          "Analyze the codebase",
          { timeout: 120000 }
        );
        result = await retryRun.wait();
      }
    }

    console.log(`Final status: ${result.status}`);
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 7: Get task history and details
 */
async function exampleGetRunHistory() {
  const agent = new XAgent({
    baseUrl: "http://localhost:8000",
    apiKey: "sk_your_api_key_here",
  });

  try {
    // Get recent completed runs
    const runs = await agent.getRuns({ limit: 10, status: "completed" });

    console.log("Recent completed tasks:");
    for (const run of runs) {
      console.log(`- ${run.id}: ${run.name} (${run.createdAt})`);
    }

    // Get details of first run
    if (runs.length > 0) {
      const details = await agent.getRun(runs[0].id);
      console.log(`\nDetails of ${runs[0].id}:`);
      console.log(`  Status: ${details.status}`);
      console.log(`  Output: ${details.output.substring(0, 200)}...`);
    }
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 8: Browser usage (Fetch API)
 */
async function exampleBrowserUsage() {
  const baseUrl = "http://localhost:8000";
  const apiKey = "sk_your_api_key_here";

  try {
    // Submit task via fetch
    const response = await fetch(`${baseUrl}/api/v1/agent/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({
        prompt: "Analyze my code for issues",
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const runId = data.run_id;
    console.log(`Task submitted: ${runId}`);

    // Poll for completion
    let completed = false;
    while (!completed) {
      const statusResponse = await fetch(
        `${baseUrl}/api/v1/agent/run/${runId}`,
        {
          headers: {
            "X-API-Key": apiKey,
          },
        }
      );

      const status = await statusResponse.json();
      console.log(`Status: ${status.status}`);

      if (["completed", "failed"].includes(status.status)) {
        completed = true;
        console.log(`Result: ${JSON.stringify(status.result)}`);
      } else {
        // Wait 5 seconds
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }
  } catch (error) {
    console.error("Error:", error.message);
  }
}


/**
 * Example 9: WebSocket streaming in browser
 */
async function exampleWebSocketStreaming() {
  const baseUrl = "ws://localhost:8000";
  const apiKey = "sk_your_api_key_here";

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(
      `${baseUrl}/api/v1/stream?api_key=${apiKey}`
    );

    ws.onopen = () => {
      console.log("Connected to stream");
      ws.send(
        JSON.stringify({
          type: "submit_task",
          prompt: "Analyze the codebase",
        })
      );
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log(`[${data.event}] ${data.data}`);

      if (data.event === "complete") {
        ws.close();
        resolve(data.data);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      reject(error);
    };
  });
}


// Export for Node.js / ES modules
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    exampleBasicTask,
    exampleStreamingTask,
    exampleBatchTasks,
    examplePollingTask,
    exampleWithTools,
    exampleErrorHandling,
    exampleGetRunHistory,
    exampleBrowserUsage,
    exampleWebSocketStreaming,
  };
}


// CLI entrypoint for Node.js
if (require.main === module) {
  const examples = {
    basic: exampleBasicTask,
    streaming: exampleStreamingTask,
    batch: exampleBatchTasks,
    polling: examplePollingTask,
    tools: exampleWithTools,
    errors: exampleErrorHandling,
    history: exampleGetRunHistory,
    browser: exampleBrowserUsage,
    websocket: exampleWebSocketStreaming,
  };

  const exampleName = process.argv[2] || "basic";

  if (exampleName in examples) {
    console.log(`\nRunning: ${exampleName}\n`);
    examples[exampleName]().catch(console.error);
  } else {
    console.log("X-Agent JavaScript Integration Examples");
    console.log("=".repeat(50));
    console.log("\nUsage: node basic.mjs <example>");
    console.log("\nAvailable examples:");
    Object.keys(examples).forEach((name) => {
      console.log(`  ${name.padEnd(15)} - ${examples[name].toString().split('\n')[1]}`);
    });
    console.log("\nExample:");
    console.log("  node basic.mjs basic");
  }
}
