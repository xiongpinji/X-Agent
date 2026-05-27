# X-Agent Performance Benchmarks

Comprehensive performance benchmarking suite for X-Agent v2 architecture.

## Overview

This benchmarking suite provides:

- **Unit Benchmarks:** Low-level performance testing of individual components
- **Integration Benchmarks:** End-to-end performance testing of complete workflows
- **Performance Reports:** Detailed analysis with recommendations
- **Comparison Analysis:** V2 vs V1 architecture comparison

## Quick Start

### Run All Benchmarks

```bash
python benchmarks/run_benchmarks.py
```

### Run Specific Benchmark

```bash
# Unit benchmarks only
python -m benchmarks.agent_v2_benchmark

# Integration benchmarks only
python -m benchmarks.agent_v2_integration_benchmark
```

## Benchmark Scenarios

### Simple Task
- 1-2 tool calls
- Minimal processing
- Tests baseline performance

### Medium Task
- 5-10 tool calls
- Moderate processing
- Tests typical workload

### Complex Task
- 20+ tool calls
- Intensive processing
- Tests scalability

### Error Recovery
- Error handling
- Recovery mechanisms
- Tests resilience

### Memory Intensive
- Large data processing
- Memory management
- Tests memory efficiency

### Concurrent Operations
- Parallel execution
- Async operations
- Tests concurrency

## Metrics Collected

### Timing Metrics
- Initialization time
- Planning time
- Execution time
- Recovery time
- Completion time
- Total execution time

### Memory Metrics
- Initial memory usage
- Peak memory usage
- Final memory usage
- Memory delta

### CPU Metrics
- Average CPU usage
- Maximum CPU usage
- CPU sample count

## Output Files

### Results
- `unit_benchmark_results.json` - Unit benchmark results
- `integration_benchmark_results.json` - Integration benchmark results

### Reports
- `PERFORMANCE_BENCHMARK_REPORT.md` - Comprehensive markdown report
- `BENCHMARK_COMPARISON.txt` - Text-based comparison table

### Logs
- `benchmark.log` - Detailed execution log

## Architecture

### AgentV2Benchmark
Low-level performance testing with detailed metrics collection.

```python
from benchmarks.agent_v2_benchmark import AgentV2Benchmark

benchmark = AgentV2Benchmark()
results = await benchmark.run_all_benchmarks()
benchmark.save_results()
```

### AgentV2IntegrationBenchmark
Integration-level testing of complete workflows.

```python
from benchmarks.agent_v2_integration_benchmark import AgentV2IntegrationBenchmark

benchmark = AgentV2IntegrationBenchmark()
results = await benchmark.run_all_benchmarks()
benchmark.save_results()
```

### PerformanceBenchmarkReportGenerator
Report generation and analysis.

```python
from benchmarks.report_generator import PerformanceBenchmarkReportGenerator

generator = PerformanceBenchmarkReportGenerator()
report_path = generator.generate_markdown_report(results)
```

## Performance Targets

### Execution Time
- Simple task: < 0.2s
- Medium task: < 0.5s
- Complex task: < 2.0s

### Memory Usage
- Baseline: < 100 MB
- Peak: < 500 MB
- Delta: < 200 MB

### CPU Usage
- Average: < 50%
- Peak: < 80%

## Optimization Recommendations

### Short-term
1. Implement caching for plan generation
2. Parallelize independent tool calls
3. Optimize memory allocation

### Medium-term
1. Add phase result streaming
2. Implement incremental planning
3. Optimize state transitions

### Long-term
1. Implement predictive caching
2. Add ML-based optimization
3. Implement distributed execution

## Comparison with V1

The v2 architecture provides:

- **Better Modularity:** Phase-based design vs monolithic AgentLoop
- **Improved Testability:** Isolated phase testing
- **Enhanced Maintainability:** Clear separation of concerns
- **Better Performance:** Optimized state management and execution

## Dependencies

- Python 3.11+
- asyncio (standard library)
- psutil (for system metrics)
- json (standard library)

## Contributing

When adding new benchmarks:

1. Create benchmark method in appropriate class
2. Follow naming convention: `benchmark_<scenario_name>`
3. Collect timing, memory, and CPU metrics
4. Document expected performance targets
5. Add scenario to `run_all_benchmarks()`

## References

- X-Agent v2 Architecture: `backend/app/core/agent_v2/`
- Legacy AgentLoop: `backend/app/core/agent.py`
- Phase Implementations: `backend/app/core/agent_v2/phases/`

## License

Part of X-Agent project.
