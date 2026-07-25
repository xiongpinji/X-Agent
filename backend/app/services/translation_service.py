"""中文化翻译引擎 - 自动翻译和生成小白友好的中文内容"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChineseContent:
    """中文化内容"""
    what_is_it: str  # 这个插件是干什么的
    who_is_it_for: str  # 适合谁用
    how_to_use: str  # 怎么用（步骤化）
    faq: list[dict[str, str]]  # 常见问题
    tutorial: str  # 使用教程


class TranslationEngine:
    """翻译引擎 - 将英文内容翻译为中文"""

    # 技术术语翻译字典
    TECH_TERMS = {
        "repository": "仓库",
        "commit": "提交",
        "pull request": "拉取请求",
        "issue": "问题",
        "branch": "分支",
        "merge": "合并",
        "fork": "分叉",
        "clone": "克隆",
        "push": "推送",
        "pull": "拉取",
        "api": "接口",
        "database": "数据库",
        "cache": "缓存",
        "authentication": "认证",
        "authorization": "授权",
        "encryption": "加密",
        "deployment": "部署",
        "configuration": "配置",
        "integration": "集成",
        "automation": "自动化",
        "workflow": "工作流",
        "pipeline": "管道",
        "container": "容器",
        "kubernetes": "库伯内特斯",
        "microservice": "微服务",
        "rest": "REST",
        "graphql": "GraphQL",
        "websocket": "网络套接字",
        "json": "JSON",
        "xml": "XML",
        "yaml": "YAML",
        "markdown": "Markdown",
        "regex": "正则表达式",
        "algorithm": "算法",
        "data structure": "数据结构",
        "performance": "性能",
        "scalability": "可扩展性",
        "reliability": "可靠性",
        "security": "安全性",
        "monitoring": "监控",
        "logging": "日志",
        "debugging": "调试",
        "testing": "测试",
        "ci/cd": "持续集成/持续部署",
        "devops": "开发运维",
        "agile": "敏捷",
        "scrum": "Scrum",
        "kanban": "看板",
    }

    @staticmethod
    def translate_text(text: str, source_lang: str = "en", target_lang: str = "zh") -> str:
        """翻译文本"""
        if not text:
            return ""

        # 这里应该使用真实的翻译API（如Google Translate、OpenAI等）
        # 为了演示，我们使用简单的术语替换
        translated = text

        # 替换技术术语
        for en_term, zh_term in TranslationEngine.TECH_TERMS.items():
            # 大小写不敏感的替换
            translated = translated.replace(en_term, zh_term)
            translated = translated.replace(en_term.capitalize(), zh_term)
            translated = translated.replace(en_term.upper(), zh_term)

        return translated

    @staticmethod
    def simplify_for_beginners(text: str) -> str:
        """简化文本以适应小白用户"""
        # 移除过于技术性的术语
        simplified = text

        # 替换复杂的表述
        replacements = {
            "utilize": "使用",
            "leverage": "利用",
            "facilitate": "促进",
            "implement": "实现",
            "configure": "配置",
            "execute": "执行",
            "initialize": "初始化",
            "terminate": "终止",
            "synchronize": "同步",
            "authenticate": "认证",
            "authorize": "授权",
            "validate": "验证",
            "optimize": "优化",
            "monitor": "监控",
            "troubleshoot": "排查问题",
        }

        for complex_word, simple_word in replacements.items():
            simplified = simplified.replace(complex_word, simple_word)
            simplified = simplified.replace(complex_word.capitalize(), simple_word)

        return simplified


class ContentGenerator:
    """内容生成器 - 生成小白友好的中文介绍"""

    @staticmethod
    def generate_what_is_it(
        name: str,
        description: str,
        description_zh: str,
        capabilities: list[str],
    ) -> str:
        """生成 这个插件是干什么的 的说明。"""
        if description_zh:
            return description_zh

        # 如果没有中文描述，从英文生成
        translated = TranslationEngine.translate_text(description)
        simplified = TranslationEngine.simplify_for_beginners(translated)

        # 添加能力列表
        if capabilities:
            caps_text = "、".join(capabilities[:3])
            return f"{simplified}\n\n主要功能：{caps_text}"

        return simplified

    @staticmethod
    def generate_who_is_it_for(
        name: str,
        description: str,
        capabilities: list[str],
        category: str,
    ) -> str:
        """生成"适合谁用\""""
        # 基于分类和能力生成目标用户
        user_groups = {
            "office": ["办公人员", "文案编辑", "数据分析师"],
            "design": ["设计师", "视频编辑", "内容创作者"],
            "development": ["程序员", "开发工程师", "技术爱好者"],
            "data": ["数据分析师", "商业分析师", "研究人员"],
            "automation": ["运维工程师", "系统管理员", "自动化爱好者"],
            "network": ["网络工程师", "爬虫开发者", "API测试人员"],
            "system": ["系统管理员", "运维工程师", "性能优化师"],
            "learning": ["学生", "知识工作者", "终身学习者"],
        }

        groups = user_groups.get(category, ["所有用户"])

        result = "适合以下人群使用：\n"
        for _i, group in enumerate(groups, 1):
            result += f"✓ {group}\n"

        return result.strip()

    @staticmethod
    def generate_how_to_use(
        name: str,
        entry_point: str,
        capabilities: list[str],
    ) -> str:
        """生成"怎么用"（步骤化）"""
        steps = [
            "1. 点击\"一键安装\"按钮",
            "2. 等待安装完成",
            "3. 在聊天框中输入相关命令",
            "4. 查看结果",
        ]

        # 根据能力添加具体步骤
        if "github" in str(capabilities).lower():
            steps.insert(2, "2.5. 输入你的GitHub账号授权")
        elif "api" in str(capabilities).lower():
            steps.insert(2, "2.5. 配置API密钥")

        result = "使用步骤：\n"
        for step in steps:
            result += f"{step}\n"

        return result.strip()

    @staticmethod
    def generate_faq(
        name: str,
        description: str,
        capabilities: list[str],
    ) -> list[dict[str, str]]:
        """生成常见问题"""
        faqs = [
            {
                "question": "这个插件安全吗？",
                "answer": "是的，所有插件都经过安全审查，运行在隔离的沙箱环境中。",
            },
            {
                "question": "如何卸载这个插件？",
                "answer": "在已安装插件列表中找到该插件，点击\"卸载\"按钮即可。",
            },
            {
                "question": "插件需要付费吗？",
                "answer": "大多数插件都是免费的，部分高级功能可能需要付费。",
            },
            {
                "question": "如何获得技术支持？",
                "answer": "你可以在插件详情页面找到作者的联系方式或提交问题。",
            },
        ]

        # 添加特定于插件的FAQ
        if "github" in str(capabilities).lower():
            faqs.append({
                "question": "如何授权GitHub账号？",
                "answer": "点击授权按钮，按照提示登录GitHub并授予权限即可。",
            })

        if "api" in str(capabilities).lower():
            faqs.append({
                "question": "如何获取API密钥？",
                "answer": "访问服务提供商的官方网站，在账户设置中生成API密钥。",
            })

        return faqs

    @staticmethod
    def generate_tutorial(
        name: str,
        description: str,
        capabilities: list[str],
        category: str,
    ) -> str:
        """生成使用教程"""
        tutorial = f"# {name} 使用教程\n\n"

        tutorial += "## 快速开始\n"
        tutorial += "1. 安装插件\n"
        tutorial += "2. 启用插件\n"
        tutorial += "3. 开始使用\n\n"

        tutorial += "## 主要功能\n"
        for i, cap in enumerate(capabilities[:5], 1):
            tutorial += f"{i}. {cap}\n"

        tutorial += "\n## 常见用法\n"
        tutorial += "- 在聊天框中输入相关命令\n"
        tutorial += "- 按照提示完成操作\n"
        tutorial += "- 查看结果\n\n"

        tutorial += "## 提示和技巧\n"
        tutorial += "- 定期检查插件更新\n"
        tutorial += "- 根据需要调整插件设置\n"
        tutorial += "- 遇到问题时查看FAQ\n\n"

        tutorial += "## 获取帮助\n"
        tutorial += "如有问题，请访问插件官方网站或联系作者。\n"

        return tutorial

    @staticmethod
    def generate_chinese_content(
        name: str,
        description: str,
        description_zh: str,
        capabilities: list[str],
        category: str,
        entry_point: str = "",
    ) -> ChineseContent:
        """生成完整的中文化内容"""
        return ChineseContent(
            what_is_it=ContentGenerator.generate_what_is_it(
                name, description, description_zh, capabilities
            ),
            who_is_it_for=ContentGenerator.generate_who_is_it_for(
                name, description, capabilities, category
            ),
            how_to_use=ContentGenerator.generate_how_to_use(
                name, entry_point, capabilities
            ),
            faq=ContentGenerator.generate_faq(name, description, capabilities),
            tutorial=ContentGenerator.generate_tutorial(
                name, description, capabilities, category
            ),
        )


class PluginLocalizer:
    """插件本地化器 - 完整的中文化处理"""

    @staticmethod
    def localize_plugin(
        name: str,
        description: str,
        description_zh: str,
        long_description: str,
        long_description_zh: str,
        capabilities: list[str],
        category: str,
        entry_point: str = "",
    ) -> dict:
        """本地化插件"""
        # 生成中文内容
        chinese_content = ContentGenerator.generate_chinese_content(
            name=name,
            description=description,
            description_zh=description_zh,
            capabilities=capabilities,
            category=category,
            entry_point=entry_point,
        )

        # 翻译长描述
        translated_long_desc = (
            long_description_zh
            or TranslationEngine.translate_text(long_description)
        )

        return {
            "name": name,
            "description_zh": chinese_content.what_is_it,
            "long_description_zh": translated_long_desc,
            "who_is_it_for": chinese_content.who_is_it_for,
            "how_to_use": chinese_content.how_to_use,
            "faq": chinese_content.faq,
            "tutorial": chinese_content.tutorial,
            "capabilities_zh": [
                TranslationEngine.translate_text(cap) for cap in capabilities
            ],
        }
