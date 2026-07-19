"""
性能瓶颈分析
分析范围: CPU瓶颈、内存瓶颈、IO瓶颈、网络瓶颈、数据库瓶颈
"""
import pytest
import time
import psutil
import os
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
import json
import cProfile
import pstats
import io


@dataclass
class BottleneckAnalysisResult:
    """瓶颈分析结果"""
    test_name: str
    bottleneck_type: str  # CPU, Memory, IO, Network, Database
    severity: str  # Critical, High, Medium, Low
    description: str
    metrics: Dict[str, Any]
    recommendations: List[str]


class BottleneckAnalyzer:
    """瓶颈分析器"""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.results: List[BottleneckAnalysisResult] = []

    def analyze_cpu_bottleneck(
        self,
        function: Callable,
        *args,
        **kwargs
    ) -> BottleneckAnalysisResult:
        """分析CPU瓶颈"""
        profiler = cProfile.Profile()
        profiler.enable()

        start_time = time.time()
        start_cpu = self.process.cpu_percent(interval=0.1)

        function(*args, **kwargs)

        end_cpu = self.process.cpu_percent(interval=0.1)
        elapsed_time = time.time() - start_time

        profiler.disable()

        # 获取性能统计
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(10)
        profile_output = s.getvalue()

        # 分析结果
        cpu_usage = (start_cpu + end_cpu) / 2
        severity = 'Critical' if cpu_usage > 80 else 'High' if cpu_usage > 60 else 'Medium' if cpu_usage > 40 else 'Low'

        result = BottleneckAnalysisResult(
            test_name='cpu_bottleneck_analysis',
            bottleneck_type='CPU',
            severity=severity,
            description=f'CPU usage: {cpu_usage:.2f}%',
            metrics={
                'cpu_usage_percent': cpu_usage,
                'elapsed_time': elapsed_time,
                'profile_output': profile_output[:500]  # 只保存前500个字符
            },
            recommendations=[
                'Optimize hot functions identified in profiler output',
                'Consider using caching for expensive computations',
                'Profile with py-spy for production-like conditions',
                'Use vectorization or compiled extensions for CPU-intensive code'
            ]
        )

        self.results.append(result)
        return result

    def analyze_memory_bottleneck(
        self,
        function: Callable,
        *args,
        **kwargs
    ) -> BottleneckAnalysisResult:
        """分析内存瓶颈"""
        import tracemalloc

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        initial_memory = self.process.memory_info().rss / 1024 / 1024

        function(*args, **kwargs)

        snapshot_after = tracemalloc.take_snapshot()
        final_memory = self.process.memory_info().rss / 1024 / 1024

        top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')

        memory_growth = final_memory - initial_memory
        memory_percent = (memory_growth / initial_memory * 100) if initial_memory > 0 else 0

        severity = 'Critical' if memory_percent > 50 else 'High' if memory_percent > 30 else 'Medium' if memory_percent > 10 else 'Low'

        top_allocations = []
        for stat in top_stats[:5]:
            top_allocations.append({
                'file': str(stat.traceback[0]) if stat.traceback else 'unknown',
                'size_diff': stat.size_diff,
                'count_diff': stat.count_diff
            })

        result = BottleneckAnalysisResult(
            test_name='memory_bottleneck_analysis',
            bottleneck_type='Memory',
            severity=severity,
            description=f'Memory growth: {memory_growth:.2f} MB ({memory_percent:.2f}%)',
            metrics={
                'initial_memory_mb': initial_memory,
                'final_memory_mb': final_memory,
                'memory_growth_mb': memory_growth,
                'memory_growth_percent': memory_percent,
                'top_allocations': top_allocations
            },
            recommendations=[
                'Review top memory allocations for optimization',
                'Implement object pooling for frequently created objects',
                'Use generators instead of lists for large datasets',
                'Profile with memory_profiler for line-by-line analysis'
            ]
        )

        tracemalloc.stop()
        self.results.append(result)
        return result

    def analyze_io_bottleneck(
        self,
        function: Callable,
        *args,
        **kwargs
    ) -> BottleneckAnalysisResult:
        """分析IO瓶颈"""
        import io as io_module

        # 获取初始IO统计
        initial_io_counters = self.process.io_counters()

        start_time = time.time()
        function(*args, **kwargs)
        elapsed_time = time.time() - start_time

        # 获取最终IO统计
        final_io_counters = self.process.io_counters()

        read_bytes = final_io_counters.read_bytes - initial_io_counters.read_bytes
        write_bytes = final_io_counters.write_bytes - initial_io_counters.write_bytes
        read_count = final_io_counters.read_count - initial_io_counters.read_count
        write_count = final_io_counters.write_count - initial_io_counters.write_count

        # 计算IO速率
        read_rate = read_bytes / elapsed_time if elapsed_time > 0 else 0
        write_rate = write_bytes / elapsed_time if elapsed_time > 0 else 0

        severity = 'Critical' if read_rate > 100 * 1024 * 1024 else 'High' if read_rate > 50 * 1024 * 1024 else 'Medium' if read_rate > 10 * 1024 * 1024 else 'Low'

        result = BottleneckAnalysisResult(
            test_name='io_bottleneck_analysis',
            bottleneck_type='IO',
            severity=severity,
            description=f'IO rate: Read {read_rate / 1024 / 1024:.2f} MB/s, Write {write_rate / 1024 / 1024:.2f} MB/s',
            metrics={
                'read_bytes': read_bytes,
                'write_bytes': write_bytes,
                'read_count': read_count,
                'write_count': write_count,
                'read_rate_mbps': read_rate / 1024 / 1024,
                'write_rate_mbps': write_rate / 1024 / 1024,
                'elapsed_time': elapsed_time
            },
            recommendations=[
                'Implement caching to reduce IO operations',
                'Use batch operations instead of individual reads/writes',
                'Consider using memory-mapped files for large datasets',
                'Profile with iotop to identify specific IO bottlenecks'
            ]
        )

        self.results.append(result)
        return result

    async def analyze_network_bottleneck(
        self,
        endpoint: str,
        num_requests: int = 100,
        base_url: str = "http://localhost:8000"
    ) -> BottleneckAnalysisResult:
        """分析网络瓶颈"""
        import aiohttp

        url = f"{base_url}{endpoint}"
        response_times = []
        total_bytes_received = 0
        errors = 0

        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            for _ in range(num_requests):
                try:
                    req_start = time.time()
                    async with session.get(url, timeout=30) as resp:
                        data = await resp.text()
                        response_time = time.time() - req_start
                        response_times.append(response_time)
                        total_bytes_received += len(data.encode())
                except Exception:
                    errors += 1

        elapsed_time = time.time() - start_time

        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        throughput = total_bytes_received / elapsed_time if elapsed_time > 0 else 0

        severity = 'Critical' if avg_response_time > 5 else 'High' if avg_response_time > 2 else 'Medium' if avg_response_time > 1 else 'Low'

        result = BottleneckAnalysisResult(
            test_name='network_bottleneck_analysis',
            bottleneck_type='Network',
            severity=severity,
            description=f'Avg response time: {avg_response_time:.3f}s, Throughput: {throughput / 1024 / 1024:.2f} MB/s',
            metrics={
                'avg_response_time': avg_response_time,
                'total_bytes_received': total_bytes_received,
                'throughput_mbps': throughput / 1024 / 1024,
                'error_rate': (errors / num_requests * 100) if num_requests > 0 else 0,
                'num_requests': num_requests
            },
            recommendations=[
                'Enable HTTP compression (gzip) for responses',
                'Implement connection pooling',
                'Use CDN for static content',
                'Optimize payload size and consider pagination',
                'Monitor network latency with tools like mtr or ping'
            ]
        )

        self.results.append(result)
        return result

    async def analyze_database_bottleneck(
        self,
        query: str,
        num_iterations: int = 100,
        connection_string: str = None
    ) -> BottleneckAnalysisResult:
        """分析数据库瓶颈"""
        import asyncpg

        execution_times = []
        errors = 0

        try:
            conn = await asyncpg.connect(connection_string)

            start_time = time.time()

            for _ in range(num_iterations):
                try:
                    query_start = time.time()
                    await conn.fetch(query)
                    execution_time = time.time() - query_start
                    execution_times.append(execution_time)
                except Exception:
                    errors += 1

            await conn.close()

            elapsed_time = time.time() - start_time

            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
            throughput = len(execution_times) / elapsed_time if elapsed_time > 0 else 0

            severity = 'Critical' if avg_execution_time > 1 else 'High' if avg_execution_time > 0.5 else 'Medium' if avg_execution_time > 0.1 else 'Low'

            result = BottleneckAnalysisResult(
                test_name='database_bottleneck_analysis',
                bottleneck_type='Database',
                severity=severity,
                description=f'Avg query time: {avg_execution_time:.3f}s, Throughput: {throughput:.2f} queries/s',
                metrics={
                    'avg_execution_time': avg_execution_time,
                    'throughput_qps': throughput,
                    'error_rate': (errors / num_iterations * 100) if num_iterations > 0 else 0,
                    'num_iterations': num_iterations
                },
                recommendations=[
                    'Add indexes to frequently queried columns',
                    'Analyze query execution plans with EXPLAIN',
                    'Implement query result caching',
                    'Consider connection pooling',
                    'Optimize N+1 queries with joins or batch operations',
                    'Monitor slow query logs'
                ]
            )

        except Exception as e:
            result = BottleneckAnalysisResult(
                test_name='database_bottleneck_analysis',
                bottleneck_type='Database',
                severity='Critical',
                description=f'Database connection error: {str(e)}',
                metrics={'error': str(e)},
                recommendations=['Check database connection string and availability']
            )

        self.results.append(result)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """获取分析摘要"""
        if not self.results:
            return {}

        critical_count = sum(1 for r in self.results if r.severity == 'Critical')
        high_count = sum(1 for r in self.results if r.severity == 'High')

        return {
            'total_analyses': len(self.results),
            'critical_bottlenecks': critical_count,
            'high_bottlenecks': high_count,
            'bottlenecks': [
                {
                    'type': r.bottleneck_type,
                    'severity': r.severity,
                    'description': r.description,
                    'recommendations': r.recommendations
                }
                for r in self.results
            ]
        }


# 测试用例
@pytest.mark.bottleneck_analysis
class TestCPUBottleneck:
    """CPU瓶颈分析"""

    def test_cpu_bottleneck_analysis(self):
        """CPU瓶颈分析"""
        analyzer = BottleneckAnalyzer()

        def cpu_intensive_function():
            """CPU密集型函数"""
            result = 0
            for i in range(10000000):
                result += i ** 2
            return result

        result = analyzer.analyze_cpu_bottleneck(cpu_intensive_function)

        print(f"\nCPU瓶颈分析结果:")
        print(f"  严重程度: {result.severity}")
        print(f"  描述: {result.description}")
        print(f"  建议: {result.recommendations}")


@pytest.mark.bottleneck_analysis
class TestMemoryBottleneck:
    """内存瓶颈分析"""

    def test_memory_bottleneck_analysis(self):
        """内存瓶颈分析"""
        analyzer = BottleneckAnalyzer()

        def memory_intensive_function():
            """内存密集型函数"""
            data = []
            for i in range(1000000):
                data.append({'id': i, 'value': i * 2})
            return data

        result = analyzer.analyze_memory_bottleneck(memory_intensive_function)

        print(f"\n内存瓶颈分析结果:")
        print(f"  严重程度: {result.severity}")
        print(f"  描述: {result.description}")
        print(f"  内存增长: {result.metrics['memory_growth_mb']:.2f} MB")


@pytest.mark.bottleneck_analysis
class TestIOBottleneck:
    """IO瓶颈分析"""

    def test_io_bottleneck_analysis(self):
        """IO瓶颈分析"""
        analyzer = BottleneckAnalyzer()

        def io_intensive_function():
            """IO密集型函数"""
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                for i in range(100000):
                    f.write(f"Line {i}\n")
                temp_file = f.name

            with open(temp_file, 'r') as f:
                lines = f.readlines()

            os.unlink(temp_file)
            return len(lines)

        result = analyzer.analyze_io_bottleneck(io_intensive_function)

        print(f"\nIO瓶颈分析结果:")
        print(f"  严重程度: {result.severity}")
        print(f"  描述: {result.description}")
        print(f"  读取速率: {result.metrics['read_rate_mbps']:.2f} MB/s")


@pytest.mark.bottleneck_analysis
class TestNetworkBottleneck:
    """网络瓶颈分析"""

    @pytest.mark.asyncio
    async def test_network_bottleneck_analysis(self):
        """网络瓶颈分析"""
        analyzer = BottleneckAnalyzer()
        result = await analyzer.analyze_network_bottleneck(
            endpoint='/api/v1/health',
            num_requests=100
        )

        print(f"\n网络瓶颈分析结果:")
        print(f"  严重程度: {result.severity}")
        print(f"  描述: {result.description}")
        print(f"  平均响应时间: {result.metrics['avg_response_time']:.3f}s")
