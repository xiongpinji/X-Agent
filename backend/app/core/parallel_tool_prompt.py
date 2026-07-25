"""LLM prompts for parallel tool calling."""

from __future__ import annotations


class ParallelToolPrompt:
    """Generates prompts to teach LLM about parallel tool calling."""

    @staticmethod
    def system_prompt() -> str:
        """Generate system prompt for parallel tool calling support."""
        return """You have the ability to call multiple tools in parallel when they are independent.

## Parallel Tool Calling

When you need to execute multiple independent operations, you can call them all at once instead of sequentially.

### Format for Parallel Calls

Use the following format to call multiple tools in parallel:

```
<parallel_calls>
<call id="call_1">
  <tool>tool_name_1</tool>
  <arguments>{"arg1": "value1", "arg2": "value2"}</arguments>
</call>
<call id="call_2">
  <tool>tool_name_2</tool>
  <arguments>{"arg1": "value1"}</arguments>
</call>
</parallel_calls>
```

### Format for Dependent Calls

When one call depends on the output of another, use variable references:

```
<parallel_calls>
<call id="read_config">
  <tool>read_file</tool>
  <arguments>{"path": "config.json"}</arguments>
</call>
<call id="read_data">
  <tool>read_file</tool>
  <arguments>{"path": "data.json"}</arguments>
</call>
<call id="process">
  <tool>process_data</tool>
  <arguments>{"config": "${read_config.output}", "data": "${read_data.output}"}</arguments>
</call>
</parallel_calls>
```

The system will automatically:
1. Detect dependencies between calls
2. Execute independent calls in parallel
3. Wait for dependencies before executing dependent calls
4. Return all results

### Benefits

- **Speed**: Independent operations complete faster
- **Efficiency**: Better resource utilization
- **Clarity**: Explicit about what can run in parallel

### When to Use Parallel Calls

Use parallel calls when:
- Multiple independent file reads
- Multiple independent API calls
- Multiple independent searches
- Multiple independent analyses

Don't use parallel calls when:
- One operation depends on another's output
- Operations modify shared state
- Order matters for correctness

### Examples

**Example 1: Reading Multiple Files**
```
<parallel_calls>
<call id="read_a">
  <tool>read_file</tool>
  <arguments>{"path": "file_a.txt"}</arguments>
</call>
<call id="read_b">
  <tool>read_file</tool>
  <arguments>{"path": "file_b.txt"}</arguments>
</call>
<call id="read_c">
  <tool>read_file</tool>
  <arguments>{"path": "file_c.txt"}</arguments>
</call>
</parallel_calls>
```

**Example 2: Dependent Operations**
```
<parallel_calls>
<call id="list_files">
  <tool>list_files</tool>
  <arguments>{"root": ".", "pattern": "*.py"}</arguments>
</call>
<call id="analyze_deps">
  <tool>analyze_dependencies</tool>
  <arguments>{"root": "."}</arguments>
</call>
<call id="search_imports">
  <tool>search_text</tool>
  <arguments>{"root": ".", "query": "import asyncio"}</arguments>
</call>
</parallel_calls>
```

**Example 3: Chained Dependencies**
```
<parallel_calls>
<call id="step1">
  <tool>read_file</tool>
  <arguments>{"path": "input.txt"}</arguments>
</call>
<call id="step2">
  <tool>process_text</tool>
  <arguments>{"text": "${step1.output}"}</arguments>
</call>
<call id="step3">
  <tool>write_file</tool>
  <arguments>{"path": "output.txt", "content": "${step2.output}"}</arguments>
</call>
</parallel_calls>
```

### Performance Expectations

- 3 independent file reads: ~1.1x faster than sequential
- 10 independent searches: ~5-8x faster than sequential
- Dependent operations: Minimal overhead, automatic optimization
"""

    @staticmethod
    def batch_execution_example() -> str:
        """Generate example of batch execution."""
        return """## Batch Tool Execution Example

### Scenario: Analyze a Python Project

Task: Analyze a Python project to understand its structure and dependencies.

### Sequential Approach (Slow)
```
1. List files (1s)
2. Analyze entrypoints (1s)
3. Analyze dependencies (1s)
4. Search for imports (1s)
Total: 4 seconds
```

### Parallel Approach (Fast)
```
<parallel_calls>
<call id="list">
  <tool>list_files</tool>
  <arguments>{"root": ".", "limit": 100}</arguments>
</call>
<call id="entrypoints">
  <tool>analyze_entrypoints</tool>
  <arguments>{"root": "."}</arguments>
</call>
<call id="deps">
  <tool>analyze_dependencies</tool>
  <arguments>{"root": "."}</arguments>
</call>
<call id="search">
  <tool>search_text</tool>
  <arguments>{"root": ".", "query": "async def"}</arguments>
</call>
</parallel_calls>
```
Total: ~1.2 seconds (3-4x faster)

### Results
All four operations complete in parallel, with results available immediately.
"""

    @staticmethod
    def dependency_reference_guide() -> str:
        """Generate guide for using dependency references."""
        return """## Dependency Reference Guide

### Variable Reference Syntax

Use `${call_id.attribute}` to reference outputs from other calls.

### Supported Attributes

- `${call_id.output}` - The output of the call (if successful)
- `${call_id.error}` - The error message (if failed)
- `${call_id.success}` - Boolean indicating success

### Examples

**Reference successful output:**
```
<call id="process">
  <tool>process_data</tool>
  <arguments>{"data": "${read.output}"}</arguments>
</call>
```

**Reference with fallback:**
```
<call id="save">
  <tool>write_file</tool>
  <arguments>{"path": "output.txt", "content": "${process.output}"}</arguments>
</call>
```

**Chain multiple dependencies:**
```
<parallel_calls>
<call id="step1">
  <tool>read_file</tool>
  <arguments>{"path": "input.txt"}</arguments>
</call>
<call id="step2">
  <tool>transform</tool>
  <arguments>{"data": "${step1.output}"}</arguments>
</call>
<call id="step3">
  <tool>validate</tool>
  <arguments>{"data": "${step2.output}"}</arguments>
</call>
<call id="step4">
  <tool>write_file</tool>
  <arguments>{"path": "output.txt", "content": "${step3.output}"}</arguments>
</call>
</parallel_calls>
```

### Execution Order

The system automatically determines execution order:
1. Calls with no dependencies execute first (Layer 1)
2. Calls depending on Layer 1 execute next (Layer 2)
3. And so on...

All calls in the same layer execute in parallel.
"""

    @staticmethod
    def best_practices() -> str:
        """Generate best practices guide."""
        return """## Best Practices for Parallel Tool Calling

### 1. Identify Independent Operations
Before using parallel calls, identify which operations are truly independent:
- ✓ Reading different files
- ✓ Searching in different directories
- ✓ Analyzing different code sections
- ✗ Operations that modify shared state
- ✗ Operations with implicit ordering requirements

### 2. Use Meaningful Call IDs
```
Good:
<call id="read_config">
<call id="read_data">
<call id="analyze_results">

Bad:
<call id="call1">
<call id="call2">
<call id="call3">
```

### 3. Handle Failures Gracefully
```
<parallel_calls>
<call id="primary">
  <tool>read_file</tool>
  <arguments>{"path": "primary.txt"}</arguments>
</call>
<call id="backup">
  <tool>read_file</tool>
  <arguments>{"path": "backup.txt"}</arguments>
</call>
<call id="process">
  <tool>process_data</tool>
  <arguments>{"data": "${primary.output}"}</arguments>
</call>
</parallel_calls>
```

### 4. Optimize Batch Size
- Small batches (2-5 calls): Good for simple operations
- Medium batches (5-20 calls): Good for mixed operations
- Large batches (20+ calls): Consider splitting into smaller batches

### 5. Monitor Performance
- Track execution time for parallel vs sequential
- Adjust batch sizes based on performance
- Use caching for repeated operations

### 6. Document Dependencies
When using complex dependency chains, add comments:
```
<!-- Read config and data in parallel -->
<call id="config">...</call>
<call id="data">...</call>

<!-- Process depends on both config and data -->
<call id="process">
  <arguments>{"config": "${config.output}", "data": "${data.output}"}</arguments>
</call>
```

### 7. Error Handling
```
<parallel_calls>
<call id="op1">
  <tool>operation1</tool>
  <arguments>{...}</arguments>
</call>
<call id="op2">
  <tool>operation2</tool>
  <arguments>{...}</arguments>
</call>
</parallel_calls>

If op1 fails, op2 still completes.
Check results individually for success/failure.
```
"""

    @staticmethod
    def performance_tips() -> str:
        """Generate performance optimization tips."""
        return """## Performance Optimization Tips

### 1. Caching
The system automatically caches tool results. Identical calls return cached results instantly.

```
<!-- First call: executes and caches (1s) -->
<call id="read1">
  <tool>read_file</tool>
  <arguments>{"path": "config.json"}</arguments>
</call>

<!-- Second call: returns from cache (<1ms) -->
<call id="read2">
  <tool>read_file</tool>
  <arguments>{"path": "config.json"}</arguments>
</call>
```

### 2. Batch Similar Operations
Group similar operations together for better optimization:

```
<!-- Good: All reads together -->
<parallel_calls>
<call id="read1"><tool>read_file</tool>...</call>
<call id="read2"><tool>read_file</tool>...</call>
<call id="read3"><tool>read_file</tool>...</call>
</parallel_calls>

<!-- Less optimal: Mixed operations -->
<parallel_calls>
<call id="read1"><tool>read_file</tool>...</call>
<call id="write1"><tool>write_file</tool>...</call>
<call id="read2"><tool>read_file</tool>...</call>
</parallel_calls>
```

### 3. Limit Concurrent Operations
The system limits concurrent operations to prevent resource exhaustion.
Typical limits:
- File operations: 10 concurrent
- Network operations: 5 concurrent
- CPU-intensive: 2-4 concurrent

### 4. Use Appropriate Timeouts
```
<call id="long_operation">
  <tool>analyze_large_codebase</tool>
  <arguments>{"root": ".", "timeout": 60}</arguments>
</call>
```

### 5. Monitor Cache Hit Rate
The system tracks cache statistics:
- Hit rate: Percentage of cached results
- Miss rate: Percentage of cache misses
- Evictions: Number of entries removed due to size limits

Higher hit rates indicate better performance.

### 6. Optimize Argument Passing
```
<!-- Good: Minimal arguments -->
<call id="read">
  <tool>read_file</tool>
  <arguments>{"path": "file.txt"}</arguments>
</call>

<!-- Less optimal: Unnecessary arguments -->
<call id="read">
  <tool>read_file</tool>
  <arguments>{"path": "file.txt", "encoding": "utf-8", "errors": "ignore", "limit": 4000}</arguments>
</call>
```

### 7. Dependency Chain Optimization
```
<!-- Good: Parallel where possible -->
<parallel_calls>
<call id="read_a"><tool>read_file</tool><arguments>{"path": "a.txt"}</arguments></call>
<call id="read_b"><tool>read_file</tool><arguments>{"path": "b.txt"}</arguments></call>
<call id="process"><tool>process</tool><arguments>{"a": "${read_a.output}", "b": "${read_b.output}"}</arguments></call>
</parallel_calls>

<!-- Less optimal: Sequential -->
<parallel_calls>
<call id="read_a"><tool>read_file</tool><arguments>{"path": "a.txt"}</arguments></call>
<call id="read_b"><tool>read_file</tool><arguments>{"path": "b.txt", "depends_on": "${read_a.output}"}</arguments></call>
</parallel_calls>
```
"""
