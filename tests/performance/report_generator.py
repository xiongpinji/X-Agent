"""
性能测试报告生成
生成详细的性能测试报告、分析和建议
"""
import json
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import asdict


class PerformanceReportGenerator:
    """性能测试报告生成器"""

    def __init__(self, project_name: str = "X-Agent"):
        self.project_name = project_name
        self.report_data = {
            'project_name': project_name,
            'generated_at': datetime.now().isoformat(),
            'sections': {}
        }

    def add_benchmark_results(self, results: Dict[str, Any]):
        """添加基准测试结果"""
        self.report_data['sections']['benchmarks'] = {
            'title': '性能基准测试',
            'description': '测试系统在标准条件下的性能指标',
            'results': results
        }

    def add_load_test_results(self, results: List[Dict[str, Any]]):
        """添加负载测试结果"""
        self.report_data['sections']['load_tests'] = {
            'title': '负载测试',
            'description': '测试系统在不同负载条件下的表现',
            'results': results
        }

    def add_stress_test_results(self, results: List[Dict[str, Any]]):
        """添加压力测试结果"""
        self.report_data['sections']['stress_tests'] = {
            'title': '压力测试',
            'description': '测试系统的极限和破裂点',
            'results': results
        }

    def add_stability_test_results(self, results: List[Dict[str, Any]]):
        """添加稳定性测试结果"""
        self.report_data['sections']['stability_tests'] = {
            'title': '稳定性测试',
            'description': '测试系统的长期稳定性和可靠性',
            'results': results
        }

    def add_bottleneck_analysis(self, results: List[Dict[str, Any]]):
        """添加瓶颈分析结果"""
        self.report_data['sections']['bottleneck_analysis'] = {
            'title': '性能瓶颈分析',
            'description': '识别系统中的性能瓶颈',
            'results': results
        }

    def add_recommendations(self, recommendations: List[Dict[str, Any]]):
        """添加优化建议"""
        self.report_data['sections']['recommendations'] = {
            'title': '优化建议',
            'description': '基于测试结果的性能优化建议',
            'items': recommendations
        }

    def add_capacity_planning(self, capacity_plan: Dict[str, Any]):
        """添加容量规划"""
        self.report_data['sections']['capacity_planning'] = {
            'title': '容量规划',
            'description': '基于性能测试的容量规划建议',
            'plan': capacity_plan
        }

    def generate_html_report(self, output_path: str):
        """生成HTML报告"""
        html_content = self._generate_html()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def generate_json_report(self, output_path: str):
        """生成JSON报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.report_data, f, indent=2, ensure_ascii=False)

    def generate_markdown_report(self, output_path: str):
        """生成Markdown报告"""
        markdown_content = self._generate_markdown()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

    def _generate_html(self) -> str:
        """生成HTML内容"""
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.project_name} 性能测试报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .section h2 {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        .section h3 {{
            color: #764ba2;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 1.3em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        table th {{
            background-color: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        table td {{
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f9f9f9;
        }}
        .metric {{
            display: inline-block;
            background: #f0f0f0;
            padding: 15px 20px;
            margin: 10px 10px 10px 0;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }}
        .recommendation {{
            background: #e8f4f8;
            border-left: 4px solid #0288d1;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .recommendation strong {{
            color: #0288d1;
        }}
        .critical {{
            color: #d32f2f;
            font-weight: bold;
        }}
        .high {{
            color: #f57c00;
            font-weight: bold;
        }}
        .medium {{
            color: #fbc02d;
            font-weight: bold;
        }}
        .low {{
            color: #388e3c;
            font-weight: bold;
        }}
        footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #ddd;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{self.project_name} 性能测试报告</h1>
            <p>生成时间: {self.report_data['generated_at']}</p>
        </header>

        {self._generate_html_sections()}

        <footer>
            <p>本报告由性能测试框架自动生成</p>
        </footer>
    </div>
</body>
</html>
"""
        return html

    def _generate_html_sections(self) -> str:
        """生成HTML部分"""
        html = ""

        for section_key, section_data in self.report_data['sections'].items():
            html += f"""
        <div class="section">
            <h2>{section_data.get('title', section_key)}</h2>
            <p>{section_data.get('description', '')}</p>
"""

            if 'results' in section_data:
                results = section_data['results']
                if isinstance(results, list) and results:
                    html += self._generate_html_table(results)
                elif isinstance(results, dict):
                    html += self._generate_html_metrics(results)

            if 'items' in section_data:
                for item in section_data['items']:
                    html += f"""
            <div class="recommendation">
                <strong>{item.get('title', '')}</strong>
                <p>{item.get('description', '')}</p>
            </div>
"""

            if 'plan' in section_data:
                plan = section_data['plan']
                html += self._generate_html_metrics(plan)

            html += """
        </div>
"""

        return html

    def _generate_html_table(self, data: List[Dict]) -> str:
        """生成HTML表格"""
        if not data:
            return ""

        html = "<table><thead><tr>"
        for key in data[0].keys():
            html += f"<th>{key}</th>"
        html += "</tr></thead><tbody>"

        for row in data:
            html += "<tr>"
            for value in row.values():
                if isinstance(value, float):
                    html += f"<td>{value:.2f}</td>"
                else:
                    html += f"<td>{value}</td>"
            html += "</tr>"

        html += "</tbody></table>"
        return html

    def _generate_html_metrics(self, metrics: Dict) -> str:
        """生成HTML指标"""
        html = ""
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                html += f"""
            <div class="metric">
                <div class="metric-label">{key}</div>
                <div class="metric-value">{value:.2f}</div>
            </div>
"""
        return html

    def _generate_markdown(self) -> str:
        """生成Markdown内容"""
        md = f"""# {self.project_name} 性能测试报告

**生成时间**: {self.report_data['generated_at']}

## 目录

"""

        for i, (section_key, section_data) in enumerate(self.report_data['sections'].items(), 1):
            md += f"- [{section_data.get('title', section_key)}](#{section_key})\n"

        md += "\n---\n\n"

        for section_key, section_data in self.report_data['sections'].items():
            md += f"## {section_data.get('title', section_key)}\n\n"
            md += f"{section_data.get('description', '')}\n\n"

            if 'results' in section_data:
                results = section_data['results']
                if isinstance(results, list) and results:
                    md += self._generate_markdown_table(results)
                elif isinstance(results, dict):
                    md += self._generate_markdown_metrics(results)

            if 'items' in section_data:
                for item in section_data['items']:
                    md += f"### {item.get('title', '')}\n\n"
                    md += f"{item.get('description', '')}\n\n"

            if 'plan' in section_data:
                plan = section_data['plan']
                md += self._generate_markdown_metrics(plan)

            md += "\n---\n\n"

        return md

    def _generate_markdown_table(self, data: List[Dict]) -> str:
        """生成Markdown表格"""
        if not data:
            return ""

        md = "| " + " | ".join(data[0].keys()) + " |\n"
        md += "| " + " | ".join(["---"] * len(data[0])) + " |\n"

        for row in data:
            values = []
            for value in row.values():
                if isinstance(value, float):
                    values.append(f"{value:.2f}")
                else:
                    values.append(str(value))
            md += "| " + " | ".join(values) + " |\n"

        md += "\n"
        return md

    def _generate_markdown_metrics(self, metrics: Dict) -> str:
        """生成Markdown指标"""
        md = ""
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                md += f"- **{key}**: {value:.2f}\n"
            else:
                md += f"- **{key}**: {value}\n"
        md += "\n"
        return md


# 示例使用
def generate_sample_report():
    """生成示例报告"""
    generator = PerformanceReportGenerator("X-Agent")

    # 添加基准测试结果
    generator.add_benchmark_results({
        'health_check': {
            'avg_response_time': 0.05,
            'p95_response_time': 0.08,
            'p99_response_time': 0.12,
            'throughput': 500
        },
        'list_agents': {
            'avg_response_time': 0.15,
            'p95_response_time': 0.25,
            'p99_response_time': 0.35,
            'throughput': 200
        }
    })

    # 添加负载测试结果
    generator.add_load_test_results([
        {
            'test_name': 'normal_load_100_users',
            'num_users': 100,
            'throughput': 450,
            'error_rate': 0.5,
            'avg_response_time': 0.06
        },
        {
            'test_name': 'high_load_1000_users',
            'num_users': 1000,
            'throughput': 400,
            'error_rate': 2.0,
            'avg_response_time': 0.08
        }
    ])

    # 添加压力测试结果
    generator.add_stress_test_results([
        {
            'test_name': 'breaking_point',
            'breaking_point': 5000,
            'max_throughput': 350,
            'error_rate_at_breaking': 50.0
        }
    ])

    # 添加稳定性测试结果
    generator.add_stability_test_results([
        {
            'test_name': 'stability_24h',
            'duration_hours': 24,
            'error_rate': 0.1,
            'memory_growth_mb': 50,
            'memory_stable': True
        }
    ])

    # 添加瓶颈分析
    generator.add_bottleneck_analysis([
        {
            'type': 'CPU',
            'severity': 'Low',
            'description': 'CPU usage is normal'
        },
        {
            'type': 'Memory',
            'severity': 'Medium',
            'description': 'Memory usage shows slight growth over time'
        }
    ])

    # 添加优化建议
    generator.add_recommendations([
        {
            'title': '数据库查询优化',
            'description': '添加索引到频繁查询的列，减少查询时间'
        },
        {
            'title': '缓存策略',
            'description': '实现Redis缓存层，减少数据库负载'
        },
        {
            'title': '连接池优化',
            'description': '调整数据库连接池大小以适应高并发'
        }
    ])

    # 添加容量规划
    generator.add_capacity_planning({
        'current_capacity': 5000,
        'recommended_capacity': 10000,
        'scaling_strategy': 'Horizontal scaling with load balancer',
        'estimated_cost_increase': '30%'
    })

    return generator


if __name__ == '__main__':
    generator = generate_sample_report()
    generator.generate_html_report('performance_report.html')
    generator.generate_json_report('performance_report.json')
    generator.generate_markdown_report('performance_report.md')
    print("Reports generated successfully!")
