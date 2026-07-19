"""
X-Agent 插件市场初始化脚本
用于在测试环境中初始化插件市场系统
"""

import json
import sys
from pathlib import Path
from datetime import datetime, UTC

# 示例插件数据
SAMPLE_PLUGINS = [
    {
        "id": "github-assistant-001",
        "manifest": {
            "name": "GitHub 助手",
            "version": "1.0.0",
            "author": "X-Agent Team",
            "description": "GitHub API integration for repository management",
            "description_zh": "GitHub API集成，用于仓库管理",
            "long_description": "A comprehensive GitHub assistant that helps you manage repositories, issues, and pull requests",
            "long_description_zh": "一个全面的GitHub助手，帮助你管理仓库、Issue和Pull Request",
            "homepage": "https://github.com/x-agent/github-plugin",
            "repository": "https://github.com/x-agent/github-plugin",
            "license": "MIT",
            "keywords": ["github", "git", "repository", "code"],
            "capabilities": ["repository", "issue", "pull-request", "workflow"],
            "dependencies": {"requests": ">=2.28.0"},
            "permissions": ["github:read", "github:write"],
            "entry_point": "github_plugin.main",
            "icon_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
            "screenshots": []
        },
        "category": "development",
        "status": "published",
        "risk_level": "low",
        "what_is_it": "这是一个GitHub助手插件，可以帮助你管理GitHub仓库、处理Issue和Pull Request。",
        "who_is_it_for": "适合程序员、开发团队和开源贡献者使用。",
        "how_to_use": "1. 安装插件\n2. 配置GitHub Token\n3. 选择要管理的仓库\n4. 执行相关操作（创建Issue、管理PR等）",
        "faq": [
            {
                "question": "如何配置GitHub Token？",
                "answer": "在插件设置中输入你的GitHub Personal Access Token，可以在GitHub设置页面生成。"
            },
            {
                "question": "支持哪些操作？",
                "answer": "支持创建/编辑Issue、管理Pull Request、查看仓库信息、管理Workflow等。"
            }
        ],
        "tutorial": "## GitHub助手使用教程\n\n### 快速开始\n1. 安装插件\n2. 配置Token\n3. 开始使用\n\n### 常见操作\n- 创建Issue\n- 管理Pull Request\n- 查看仓库统计",
        "downloads": 1250,
        "rating": 4.8,
        "rating_count": 156,
        "installed_count": 342,
        "is_installed": False,
        "is_enabled": False,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "published_at": datetime.now(UTC).isoformat()
    },
    {
        "id": "data-analyzer-001",
        "manifest": {
            "name": "数据分析工具",
            "version": "2.1.0",
            "author": "Data Team",
            "description": "Data analysis and visualization toolkit",
            "description_zh": "数据分析和可视化工具包",
            "long_description": "Comprehensive data analysis toolkit with visualization and statistical analysis",
            "long_description_zh": "包含可视化和统计分析的综合数据分析工具包",
            "homepage": "https://github.com/x-agent/data-analyzer",
            "repository": "https://github.com/x-agent/data-analyzer",
            "license": "MIT",
            "keywords": ["data", "analysis", "visualization", "chart"],
            "capabilities": ["data-cleaning", "visualization", "statistics", "export"],
            "dependencies": {"pandas": ">=1.5.0", "matplotlib": ">=3.6.0"},
            "permissions": ["file:read", "file:write"],
            "entry_point": "data_analyzer.main",
            "icon_url": "https://via.placeholder.com/128?text=Data",
            "screenshots": []
        },
        "category": "data",
        "status": "published",
        "risk_level": "low",
        "what_is_it": "这是一个强大的数据分析工具，支持数据清洗、统计分析和可视化。",
        "who_is_it_for": "适合数据分析师、商业分析师和研究人员使用。",
        "how_to_use": "1. 导入数据文件（CSV、Excel等）\n2. 选择分析类型\n3. 配置分析参数\n4. 生成报告和图表",
        "faq": [
            {
                "question": "支持哪些数据格式？",
                "answer": "支持CSV、Excel、JSON、Parquet等常见数据格式。"
            },
            {
                "question": "可以导出什么格式？",
                "answer": "可以导出为PDF、PNG、SVG等格式的报告和图表。"
            }
        ],
        "tutorial": "## 数据分析工具使用教程\n\n### 基本步骤\n1. 导入数据\n2. 数据清洗\n3. 分析和可视化\n4. 导出报告",
        "downloads": 890,
        "rating": 4.6,
        "rating_count": 124,
        "installed_count": 267,
        "is_installed": False,
        "is_enabled": False,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "published_at": datetime.now(UTC).isoformat()
    },
    {
        "id": "doc-generator-001",
        "manifest": {
            "name": "文档生成器",
            "version": "1.5.0",
            "author": "Doc Team",
            "description": "Automatic documentation generation from code",
            "description_zh": "从代码自动生成文档",
            "long_description": "Generate professional documentation from your source code automatically",
            "long_description_zh": "从源代码自动生成专业文档",
            "homepage": "https://github.com/x-agent/doc-generator",
            "repository": "https://github.com/x-agent/doc-generator",
            "license": "MIT",
            "keywords": ["documentation", "code", "markdown", "api-doc"],
            "capabilities": ["code-parsing", "doc-generation", "markdown", "pdf-export"],
            "dependencies": {"sphinx": ">=5.0.0"},
            "permissions": ["file:read", "file:write"],
            "entry_point": "doc_generator.main",
            "icon_url": "https://via.placeholder.com/128?text=Docs",
            "screenshots": []
        },
        "category": "development",
        "status": "published",
        "risk_level": "low",
        "what_is_it": "这是一个文档生成器，可以从代码自动生成API文档和使用说明。",
        "who_is_it_for": "适合开发者、技术写手和项目经理使用。",
        "how_to_use": "1. 选择代码目录\n2. 配置文档模板\n3. 生成文档\n4. 导出为Markdown或PDF",
        "faq": [
            {
                "question": "支持哪些编程语言？",
                "answer": "支持Python、JavaScript、Java、C++等主流编程语言。"
            },
            {
                "question": "如何自定义文档样式？",
                "answer": "可以使用内置模板或上传自定义CSS样式。"
            }
        ],
        "tutorial": "## 文档生成器使用教程\n\n### 快速开始\n1. 选择代码目录\n2. 配置生成选项\n3. 点击生成\n4. 预览和导出",
        "downloads": 756,
        "rating": 4.5,
        "rating_count": 98,
        "installed_count": 201,
        "is_installed": False,
        "is_enabled": False,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "published_at": datetime.now(UTC).isoformat()
    },
    {
        "id": "auto-test-framework-001",
        "manifest": {
            "name": "自动化测试框架",
            "version": "3.0.0",
            "author": "QA Team",
            "description": "Comprehensive automation testing framework",
            "description_zh": "综合自动化测试框架",
            "long_description": "Complete testing framework for unit, integration, and end-to-end testing",
            "long_description_zh": "用于单元测试、集成测试和端到端测试的完整框架",
            "homepage": "https://github.com/x-agent/auto-test",
            "repository": "https://github.com/x-agent/auto-test",
            "license": "MIT",
            "keywords": ["testing", "automation", "qa", "pytest"],
            "capabilities": ["unit-test", "integration-test", "e2e-test", "report-generation"],
            "dependencies": {"pytest": ">=7.0.0", "selenium": ">=4.0.0"},
            "permissions": ["file:read", "file:write"],
            "entry_point": "auto_test.main",
            "icon_url": "https://via.placeholder.com/128?text=Test",
            "screenshots": []
        },
        "category": "development",
        "status": "published",
        "risk_level": "medium",
        "what_is_it": "这是一个全面的自动化测试框架，支持单元测试、集成测试和端到端测试。",
        "who_is_it_for": "适合QA工程师、开发者和测试团队使用。",
        "how_to_use": "1. 安装框架\n2. 编写测试用例\n3. 配置测试环境\n4. 运行测试并生成报告",
        "faq": [
            {
                "question": "如何编写测试用例？",
                "answer": "使用pytest框架编写测试用例，支持多种断言和fixture。"
            },
            {
                "question": "支持哪些浏览器？",
                "answer": "支持Chrome、Firefox、Safari、Edge等主流浏览器。"
            }
        ],
        "tutorial": "## 自动化测试框架使用教程\n\n### 基础概念\n- 单元测试\n- 集成测试\n- 端到端测试\n\n### 编写测试\n1. 创建测试文件\n2. 编写测试函数\n3. 运行测试",
        "downloads": 1050,
        "rating": 4.7,
        "rating_count": 142,
        "installed_count": 298,
        "is_installed": False,
        "is_enabled": False,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "published_at": datetime.now(UTC).isoformat()
    },
    {
        "id": "perf-optimizer-001",
        "manifest": {
            "name": "性能优化工具",
            "version": "1.2.0",
            "author": "Performance Team",
            "description": "Application performance optimization and profiling",
            "description_zh": "应用性能优化和分析工具",
            "long_description": "Comprehensive performance profiling and optimization toolkit",
            "long_description_zh": "综合性能分析和优化工具包",
            "homepage": "https://github.com/x-agent/perf-optimizer",
            "repository": "https://github.com/x-agent/perf-optimizer",
            "license": "MIT",
            "keywords": ["performance", "optimization", "profiling", "monitoring"],
            "capabilities": ["profiling", "bottleneck-detection", "optimization-suggestions", "monitoring"],
            "dependencies": {"psutil": ">=5.9.0"},
            "permissions": ["system:read"],
            "entry_point": "perf_optimizer.main",
            "icon_url": "https://via.placeholder.com/128?text=Perf",
            "screenshots": []
        },
        "category": "system",
        "status": "published",
        "risk_level": "low",
        "what_is_it": "这是一个性能优化工具，可以帮助你识别性能瓶颈并提供优化建议。",
        "who_is_it_for": "适合系统管理员、DevOps工程师和性能优化专家使用。",
        "how_to_use": "1. 启动监控\n2. 运行应用\n3. 分析性能数据\n4. 查看优化建议",
        "faq": [
            {
                "question": "如何开始性能分析？",
                "answer": "点击\"开始监控\"按钮，然后运行你的应用程序。"
            },
            {
                "question": "支持哪些指标？",
                "answer": "支持CPU、内存、磁盘I/O、网络等系统指标。"
            }
        ],
        "tutorial": "## 性能优化工具使用教程\n\n### 监控步骤\n1. 启动监控\n2. 执行操作\n3. 停止监控\n4. 查看报告",
        "downloads": 623,
        "rating": 4.4,
        "rating_count": 87,
        "installed_count": 156,
        "is_installed": False,
        "is_enabled": False,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "published_at": datetime.now(UTC).isoformat()
    }
]


def initialize_plugin_market():
    """初始化插件市场"""
    print("=" * 60)
    print("X-Agent 插件市场初始化")
    print("=" * 60)

    # 创建插件市场目录
    marketplace_dir = Path("./marketplace")
    marketplace_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建插件市场目录: {marketplace_dir}")

    # 保存插件注册表
    registry_file = marketplace_dir / "registry.json"
    registry_data = {
        "plugins": SAMPLE_PLUGINS,
        "version": "1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat()
    }

    with open(registry_file, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2, ensure_ascii=False)

    print(f"✅ 保存插件注册表: {registry_file}")
    print(f"   包含 {len(SAMPLE_PLUGINS)} 个示例插件")

    # 创建插件目录
    plugins_dir = marketplace_dir / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建插件目录: {plugins_dir}")

    # 创建已安装插件目录
    installed_dir = plugins_dir / "installed"
    installed_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建已安装插件目录: {installed_dir}")

    # 创建禁用插件目录
    disabled_dir = plugins_dir / "disabled"
    disabled_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建禁用插件目录: {disabled_dir}")

    # 创建缓存目录
    cache_dir = Path("./.plugin_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 创建缓存目录: {cache_dir}")

    # 生成初始化报告
    report = {
        "status": "success",
        "timestamp": datetime.now(UTC).isoformat(),
        "directories_created": [
            str(marketplace_dir),
            str(plugins_dir),
            str(installed_dir),
            str(disabled_dir),
            str(cache_dir)
        ],
        "plugins_initialized": len(SAMPLE_PLUGINS),
        "plugin_categories": {
            "development": 3,
            "data": 1,
            "system": 1
        },
        "total_downloads": sum(p.get("downloads", 0) for p in SAMPLE_PLUGINS),
        "average_rating": sum(p.get("rating", 0) for p in SAMPLE_PLUGINS) / len(SAMPLE_PLUGINS)
    }

    report_file = marketplace_dir / "init_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"✅ 生成初始化报告: {report_file}")

    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)
    print(f"\n插件市场统计:")
    print(f"  - 总插件数: {len(SAMPLE_PLUGINS)}")
    print(f"  - 开发工具: 3个")
    print(f"  - 数据分析: 1个")
    print(f"  - 系统工具: 1个")
    print(f"  - 总下载数: {report['total_downloads']}")
    print(f"  - 平均评分: {report['average_rating']:.1f}/5.0")

    print(f"\n插件列表:")
    for plugin in SAMPLE_PLUGINS:
        manifest = plugin.get("manifest", {})
        print(f"  - {manifest.get('name')} v{manifest.get('version')}")
        print(f"    分类: {plugin.get('category')}")
        print(f"    评分: {plugin.get('rating')}/5.0 ({plugin.get('rating_count')})")
        print(f"    下载: {plugin.get('downloads')} | 安装: {plugin.get('installed_count')}")

    return True


if __name__ == "__main__":
    try:
        success = initialize_plugin_market()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)
