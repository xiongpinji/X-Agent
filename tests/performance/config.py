"""
性能测试配置
"""
import os
from pathlib import Path

# 测试配置
class PerformanceTestConfig:
    """性能测试配置"""

    # 基准测试配置
    BENCHMARK_CONFIG = {
        'health_check': {
            'endpoint': '/api/v1/health',
            'num_requests': 1000,
            'concurrent': 50,
            'timeout': 30,
            'expected_avg_response_time': 0.1,  # 100ms
            'expected_p95_response_time': 0.2,  # 200ms
            'expected_throughput': 500,  # RPS
            'expected_error_rate': 0.01,  # 1%
        },
        'list_agents': {
            'endpoint': '/api/v1/agents',
            'num_requests': 500,
            'concurrent': 25,
            'timeout': 30,
            'expected_avg_response_time': 0.5,  # 500ms
            'expected_p95_response_time': 1.0,  # 1000ms
            'expected_throughput': 50,  # RPS
            'expected_error_rate': 0.05,  # 5%
        }
    }

    # 负载测试配置
    LOAD_TEST_CONFIG = {
        'normal_load': {
            'num_users': 100,
            'duration_seconds': 60,
            'expected_throughput': 500,  # RPS
            'expected_error_rate': 0.05,  # 5%
        },
        'high_load': {
            'num_users': 1000,
            'duration_seconds': 60,
            'expected_throughput': 400,  # RPS
            'expected_error_rate': 0.15,  # 15%
        },
        'peak_load': {
            'num_users': 5000,
            'duration_seconds': 30,
            'expected_throughput': 200,  # RPS
            'expected_error_rate': 0.30,  # 30%
        },
        'sustained_load': {
            'num_users': 500,
            'duration_seconds': 300,  # 5分钟
            'expected_throughput': 450,  # RPS
            'expected_error_rate': 0.10,  # 10%
        }
    }

    # 压力测试配置
    STRESS_TEST_CONFIG = {
        'breaking_point': {
            'initial_users': 100,
            'max_users': 10000,
            'step_size': 500,
            'duration_per_step': 20,
            'error_threshold': 50.0,  # 50%
        },
        'resource_exhaustion': {
            'num_users': 10000,
            'duration': 60,
            'expected_memory_increase': 300,  # MB
        },
        'large_data': {
            'data_size_mb': 10,
            'num_requests': 10,
            'expected_error_rate': 0.50,  # 50%
        }
    }

    # 稳定性测试配置
    STABILITY_TEST_CONFIG = {
        'long_duration': {
            'num_users': 100,
            'duration_hours': 0.083,  # 5分钟演示
            'requests_per_user_per_minute': 10,
            'expected_error_rate': 0.05,  # 5%
        },
        'memory_leak_detection': {
            'num_iterations': 1000,
            'expected_memory_growth': 500,  # MB
        },
        'resource_cleanup': {
            'num_cycles': 50,
            'expected_memory_stable': True,
        },
        'error_recovery': {
            'num_requests': 1000,
            'error_injection_rate': 0.1,  # 10%
            'expected_recovery_rate': 0.80,  # 80%
        }
    }

    # 瓶颈分析配置
    BOTTLENECK_CONFIG = {
        'cpu_threshold': 80,  # %
        'memory_threshold': 50,  # %
        'io_threshold': 100,  # MB/s
        'network_threshold': 5,  # seconds
        'database_threshold': 1,  # seconds
    }

    # 服务器配置
    SERVER_CONFIG = {
        'base_url': os.getenv('TEST_BASE_URL', 'http://localhost:8000'),
        'timeout': 30,
        'max_retries': 3,
        'retry_delay': 1,
    }

    # 数据库配置
    DATABASE_CONFIG = {
        'connection_string': os.getenv(
            'TEST_DATABASE_URL',
            'postgresql://user:password@localhost:5432/xagent_test'
        ),
        'pool_size': 20,
        'max_overflow': 10,
    }

    # 报告配置
    REPORT_CONFIG = {
        'output_dir': 'performance_reports',
        'formats': ['html', 'json', 'markdown'],
        'include_charts': True,
        'include_recommendations': True,
    }

    # 日志配置
    LOG_CONFIG = {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': 'performance_tests.log',
    }


# 性能目标
class PerformanceTargets:
    """性能目标"""

    # API响应时间目标 (毫秒)
    API_RESPONSE_TIME_TARGETS = {
        'health_check': {
            'avg': 50,
            'p95': 100,
            'p99': 150,
        },
        'list_agents': {
            'avg': 200,
            'p95': 500,
            'p99': 1000,
        },
        'create_agent': {
            'avg': 500,
            'p95': 1000,
            'p99': 2000,
        }
    }

    # 吞吐量目标 (RPS)
    THROUGHPUT_TARGETS = {
        'health_check': 500,
        'list_agents': 100,
        'create_agent': 50,
    }

    # 错误率目标 (%)
    ERROR_RATE_TARGETS = {
        'normal_load': 1.0,
        'high_load': 5.0,
        'peak_load': 10.0,
    }

    # 资源使用目标
    RESOURCE_TARGETS = {
        'memory_growth_per_hour': 50,  # MB
        'cpu_usage': 50,  # %
        'disk_usage': 80,  # %
    }

    # 可用性目标
    AVAILABILITY_TARGETS = {
        'uptime': 99.9,  # %
        'error_recovery_rate': 95.0,  # %
    }


# 性能等级
class PerformanceGrades:
    """性能等级"""

    GRADES = {
        'A': {
            'description': '优秀',
            'score_range': (90, 100),
            'color': '#4CAF50',  # 绿色
        },
        'B': {
            'description': '良好',
            'score_range': (80, 89),
            'color': '#8BC34A',  # 浅绿色
        },
        'C': {
            'description': '一般',
            'score_range': (70, 79),
            'color': '#FFC107',  # 黄色
        },
        'D': {
            'description': '差',
            'score_range': (60, 69),
            'color': '#FF9800',  # 橙色
        },
        'F': {
            'description': '极差',
            'score_range': (0, 59),
            'color': '#F44336',  # 红色
        }
    }

    @classmethod
    def get_grade(cls, score: float) -> str:
        """根据分数获取等级"""
        for grade, info in cls.GRADES.items():
            if info['score_range'][0] <= score <= info['score_range'][1]:
                return grade
        return 'F'

    @classmethod
    def get_description(cls, grade: str) -> str:
        """获取等级描述"""
        return cls.GRADES.get(grade, {}).get('description', '未知')

    @classmethod
    def get_color(cls, grade: str) -> str:
        """获取等级颜色"""
        return cls.GRADES.get(grade, {}).get('color', '#999999')


# 导出配置
__all__ = [
    'PerformanceTestConfig',
    'PerformanceTargets',
    'PerformanceGrades',
]
