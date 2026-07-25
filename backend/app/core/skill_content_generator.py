"""技能中文化翻译引擎 - 自动翻译、生成小白友好的介绍"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChineseContent:
    """中文化内容"""
    what_is_it: str  # 这个技能是干什么的
    who_is_it_for: str  # 适合谁用
    how_to_use: str  # 怎么用（步骤化）
    use_cases: list[str]  # 使用场景
    faq: list[dict[str, str]]  # 常见问题
    tutorial: str  # 使用教程
    examples: list[dict[str, str]]  # 使用示例


class SkillTranslator:
    """技能翻译器 - 将英文技能翻译为中文"""

    # 技术术语翻译字典
    TECH_TERMS = {
        "code review": "代码审查",
        "debugging": "调试",
        "optimization": "优化",
        "performance": "性能",
        "security": "安全",
        "testing": "测试",
        "deployment": "部署",
        "automation": "自动化",
        "integration": "集成",
        "api": "接口",
        "database": "数据库",
        "cache": "缓存",
        "monitoring": "监控",
        "logging": "日志",
        "analytics": "分析",
        "visualization": "可视化",
        "machine learning": "机器学习",
        "artificial intelligence": "人工智能",
        "natural language processing": "自然语言处理",
        "computer vision": "计算机视觉",
        "deep learning": "深度学习",
        "neural network": "神经网络",
        "data cleaning": "数据清洗",
        "data mining": "数据挖掘",
        "web scraping": "网页爬虫",
        "web automation": "网页自动化",
        "desktop automation": "桌面自动化",
        "scheduled tasks": "定时任务",
        "workflow": "工作流",
        "pipeline": "流程",
        "template": "模板",
        "configuration": "配置",
        "plugin": "插件",
        "extension": "扩展",
        "framework": "框架",
        "library": "库",
        "package": "包",
        "dependency": "依赖",
        "version": "版本",
        "release": "发布",
        "update": "更新",
        "bug fix": "修复",
        "feature": "功能",
        "enhancement": "增强",
        "improvement": "改进",
    }

    @staticmethod
    def translate_text(text: str) -> str:
        """翻译文本"""
        if not text:
            return ""

        result = text.lower()

        # 应用术语翻译
        for en_term, zh_term in SkillTranslator.TECH_TERMS.items():
            result = result.replace(en_term, zh_term)

        return result

    @staticmethod
    def translate_description(description: str) -> str:
        """翻译描述"""
        if not description:
            return ""

        # 简单的翻译策略
        translated = SkillTranslator.translate_text(description)

        # 如果翻译后仍然是英文，返回原文
        if translated == description.lower():
            return description

        return translated


class SkillContentGenerator:
    """技能内容生成器 - 为小白用户生成友好的介绍"""

    # 技能分类的通用模板
    CATEGORY_TEMPLATES = {
        "office": {
            "what_is_it": "帮你处理文档、表格、演示文稿等办公工作，就像有个办公助手在帮你。",
            "who_is_it_for": [
                "上班族：快速完成日常办公任务",
                "学生：整理笔记和作业",
                "自由职业者：提高工作效率",
            ],
            "use_cases": [
                "快速生成报告",
                "整理数据表格",
                "制作演示文稿",
                "编辑文档",
            ],
        },
        "design": {
            "what_is_it": "帮你处理图片、设计海报、选择配色等设计工作，不需要专业设计软件。",
            "who_is_it_for": [
                "内容创作者：快速制作配图",
                "小企业主：设计营销物料",
                "学生：完成设计作业",
            ],
            "use_cases": [
                "制作社交媒体配图",
                "设计海报和传单",
                "修图和美化",
                "选择配色方案",
            ],
        },
        "development": {
            "what_is_it": "帮你写代码、找bug、审查代码，就像有个经验丰富的程序员在帮你。",
            "who_is_it_for": [
                "新手程序员：学习写出更好的代码",
                "团队leader：快速审查代码",
                "自学者：没人帮忙看代码时用",
            ],
            "use_cases": [
                "生成代码框架",
                "调试程序错误",
                "审查代码质量",
                "优化代码性能",
            ],
        },
        "data": {
            "what_is_it": "帮你分析数据、制作图表、生成报告，让数据说话。",
            "who_is_it_for": [
                "数据分析师：加快分析速度",
                "业务人员：理解数据含义",
                "学生：完成数据作业",
            ],
            "use_cases": [
                "清洗和整理数据",
                "生成数据可视化",
                "制作分析报告",
                "发现数据规律",
            ],
        },
        "automation": {
            "what_is_it": "帮你自动化重复工作，比如自动填表、定时任务等，节省时间。",
            "who_is_it_for": [
                "上班族：减少重复工作",
                "运维人员：自动化系统任务",
                "任何人：节省时间做更重要的事",
            ],
            "use_cases": [
                "自动填表和数据输入",
                "定时执行任务",
                "网页自动化操作",
                "批量处理文件",
            ],
        },
        "learning": {
            "what_is_it": "帮你整理笔记、总结知识、制定学习计划，让学习更高效。",
            "who_is_it_for": [
                "学生：提高学习效率",
                "职场人士：持续学习和提升",
                "自学者：系统化学习",
            ],
            "use_cases": [
                "整理课堂笔记",
                "总结学习内容",
                "制定学习计划",
                "复习和巩固知识",
            ],
        },
        "search": {
            "what_is_it": "帮你搜集信息、整理资料、发现有用的内容，就像有个研究员在帮你。",
            "who_is_it_for": [
                "记者和编辑：快速收集素材",
                "研究人员：整理研究资料",
                "任何人：找到需要的信息",
            ],
            "use_cases": [
                "搜集行业信息",
                "整理竞争对手资料",
                "收集用户反馈",
                "聚合相关内容",
            ],
        },
        "creativity": {
            "what_is_it": "帮你进行头脑风暴、生成创意想法、创作内容，激发你的创意。",
            "who_is_it_for": [
                "内容创作者：克服创意瓶颈",
                "营销人员：生成营销文案",
                "任何人：需要创意灵感时",
            ],
            "use_cases": [
                "头脑风暴新想法",
                "生成创意文案",
                "创作故事和剧本",
                "设计新产品概念",
            ],
        },
    }

    @staticmethod
    def generate_what_is_it(
        skill_name: str,
        description: str,
        category: str,
    ) -> str:
        """生成'这个技能是干什么的'"""
        # 如果有分类模板，使用模板
        if category in SkillContentGenerator.CATEGORY_TEMPLATES:
            template = SkillContentGenerator.CATEGORY_TEMPLATES[category]["what_is_it"]
            return f"{template}\n\n具体来说，{skill_name}可以帮你：{description}"

        # 否则生成通用介绍
        return f"{skill_name}是一个强大的工具，可以帮你：{description}"

    @staticmethod
    def generate_who_is_it_for(category: str) -> str:
        """生成'适合谁用'"""
        if category in SkillContentGenerator.CATEGORY_TEMPLATES:
            users = SkillContentGenerator.CATEGORY_TEMPLATES[category]["who_is_it_for"]
            formatted = "\n".join([f"- {user}" for user in users])
            return f"这个技能适合以下人群使用：\n{formatted}"

        return "这个技能适合任何需要提高工作效率的人使用。"

    @staticmethod
    def generate_how_to_use() -> str:
        """生成'怎么用'"""
        return """使用这个技能非常简单：

1. **点击"一键使用"按钮** - 打开技能界面
2. **输入你的需求** - 根据提示填写必要信息
3. **等待处理** - 技能会自动处理你的请求
4. **查看结果** - 获得处理结果，可以复制或下载
5. **保存或分享** - 保存结果或分享给他人

如果遇到问题，可以查看下面的常见问题或教程。"""

    @staticmethod
    def generate_use_cases(category: str) -> list[str]:
        """生成使用场景"""
        if category in SkillContentGenerator.CATEGORY_TEMPLATES:
            return SkillContentGenerator.CATEGORY_TEMPLATES[category]["use_cases"]

        return [
            "日常工作中使用",
            "提高工作效率",
            "解决实际问题",
            "学习和提升",
        ]

    @staticmethod
    def generate_faq() -> list[dict[str, str]]:
        """生成常见问题"""
        return [
            {
                "question": "这个技能完全免费吗？",
                "answer": "是的，这个技能完全免费使用。我们致力于为所有用户提供高质量的工具。"
            },
            {
                "question": "我的数据会被保存吗？",
                "answer": "你的数据只在处理时使用，不会被保存或用于其他目的。我们重视你的隐私。"
            },
            {
                "question": "如果技能出错了怎么办？",
                "answer": "如果遇到问题，请尝试重新运行或检查输入数据。如果问题持续，请联系我们的支持团队。"
            },
            {
                "question": "可以离线使用吗？",
                "answer": "大多数技能需要网络连接。具体情况请查看技能的详细说明。"
            },
            {
                "question": "支持哪些文件格式？",
                "answer": "支持的文件格式取决于具体的技能。请查看技能的详细说明了解更多信息。"
            },
        ]

    @staticmethod
    def generate_tutorial(skill_name: str, category: str) -> str:
        """生成使用教程"""
        return f"""# {skill_name} 使用教程

## 第一步：打开技能
在技能市场中找到{skill_name}，点击"一键使用"按钮。

## 第二步：准备输入
根据技能的要求准备你的输入数据。这可能是：
- 文本内容
- 文件上传
- 参数设置
- 其他配置

## 第三步：执行技能
点击"执行"或"开始"按钮，技能开始处理你的请求。

## 第四步：查看结果
等待处理完成，查看结果。你可以：
- 复制结果
- 下载结果
- 分享结果
- 继续编辑

## 常见技巧
- 如果结果不满意，可以调整参数重新运行
- 保存常用的配置以便下次快速使用
- 查看使用示例了解更多用法

## 获取帮助
如果遇到问题，请查看常见问题或联系支持团队。"""

    @staticmethod
    def generate_examples(skill_name: str, category: str) -> list[dict[str, str]]:
        """生成使用示例"""
        examples = [
            {
                "title": "基础示例",
                "description": f"最简单的{skill_name}使用方式",
                "input": "示例输入",
                "output": "示例输出",
            },
            {
                "title": "进阶示例",
                "description": f"展示{skill_name}的更多功能",
                "input": "更复杂的输入",
                "output": "更详细的输出",
            },
        ]
        return examples

    @staticmethod
    def generate_chinese_content(
        skill_name: str,
        description: str,
        category: str,
    ) -> ChineseContent:
        """生成完整的中文化内容"""
        return ChineseContent(
            what_is_it=SkillContentGenerator.generate_what_is_it(skill_name, description, category),
            who_is_it_for=SkillContentGenerator.generate_who_is_it_for(category),
            how_to_use=SkillContentGenerator.generate_how_to_use(),
            use_cases=SkillContentGenerator.generate_use_cases(category),
            faq=SkillContentGenerator.generate_faq(),
            tutorial=SkillContentGenerator.generate_tutorial(skill_name, category),
            examples=SkillContentGenerator.generate_examples(skill_name, category),
        )
