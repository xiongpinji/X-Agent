"""短剧子代理团队定义。

ShortDramaProducerAgent 调度以下子代理。每个子代理是一个"角色 + 知识包 +
职责"的声明式定义；它们共享同一份故事板契约，按 storyboard-first 顺序协作。

子代理不是独立进程，而是制作人在不同阶段以不同 system prompt 调用 LLM
路由的"角色面具"。这样既复用现有 LLMRouter / 记忆 / 审计，又保持清晰分工。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.core.creative_studio.knowledge import knowledge_pack_for


@dataclass(frozen=True)
class SubAgentRole:
    """子代理角色声明。"""

    id: str
    name: str
    name_en: str
    responsibility: str
    model_class: str  # 多模型路由用的能力类别
    system_prompt: str

    def full_system_prompt(self) -> str:
        """system prompt + 注入的专业知识包。"""
        knowledge = knowledge_pack_for(self.id)
        if not knowledge:
            return self.system_prompt
        return f"{self.system_prompt}\n\n[专业知识包]\n{knowledge}"


SUB_AGENT_TEAM: list[SubAgentRole] = [
    SubAgentRole(
        id="planner",
        name="选题策划",
        name_en="TopicPlanner",
        responsibility="爆款方向、目标受众、平台风格、标题、前3秒钩子",
        model_class="strong_reasoning_text",
        system_prompt=(
            "你是短剧选题策划专家。给定一句话需求，你要确定爆款方向、目标受众、"
            "平台调性、有冲突力的标题，以及前 3 秒钩子。输出要简洁、可执行。"
        ),
    ),
    SubAgentRole(
        id="screenwriter",
        name="编剧",
        name_en="Screenwriter",
        responsibility="剧情结构、人物关系、冲突、反转、台词、结尾钩子",
        model_class="strong_reasoning_text",
        system_prompt=(
            "你是短剧编剧。基于选题与类型，产出三幕式结构、人物关系、核心冲突、"
            "反转点、关键台词和结尾钩子。台词口语化、有张力，适配竖屏短剧节奏。"
        ),
    ),
    SubAgentRole(
        id="caption",
        name="断句字幕",
        name_en="CaptionSplitter",
        responsibility="口播节奏、断句、停顿、字幕 SRT、情绪标记",
        model_class="fast_text",
        system_prompt=(
            "你是字幕与口播节奏专家。把台词切成适合竖屏阅读的短句，标注停顿与情绪，"
            "保证字幕与配音时间轴可对齐。"
        ),
    ),
    SubAgentRole(
        id="director",
        name="分镜导演",
        name_en="StoryboardDirector",
        responsibility="镜头表、景别、运镜、镜头时长、镜头衔接、画面构图",
        model_class="strong_reasoning_text",
        system_prompt=(
            "你是分镜导演。把剧本拆成镜头级故事板：每个镜头给出景别、机位、运镜、"
            "时长、画面构图、叙事目的与衔接关系。镜头数量匹配目标时长。"
        ),
    ),
    SubAgentRole(
        id="cinematographer",
        name="摄影灯光",
        name_en="Cinematographer",
        responsibility="镜头语言、机位、焦段、构图、光线、影调、色温、氛围",
        model_class="strong_reasoning_text",
        system_prompt=(
            "你是摄影指导与灯光师。为每个镜头确定光线风格、主辅轮廓光、影调、色温、"
            "氛围，保证同场景内光线逻辑一致，并强化情绪表达。"
        ),
    ),
    SubAgentRole(
        id="art",
        name="角色与美术",
        name_en="ArtDirector",
        responsibility="角色卡、服装、妆造、场景卡、画面风格、封面视觉",
        model_class="strong_reasoning_text",
        system_prompt=(
            "你是角色设定与美术指导。产出角色卡(固定外貌与服装)、场景卡、整体画面"
            "风格与封面视觉方案，保证跨镜头一致性。"
        ),
    ),
    SubAgentRole(
        id="image",
        name="图片生成",
        name_en="ImageGenerator",
        responsibility="角色图、场景图、关键帧、封面图",
        model_class="image_generation",
        system_prompt=(
            "你是图片生成提示词工程师。把故事板镜头编译成高质量图片生成提示词，强调"
            "角色一致性、固定服装、光影、构图、景别、竖屏比例与 negative prompt。"
        ),
    ),
    SubAgentRole(
        id="video",
        name="视频生成",
        name_en="VideoGenerator",
        responsibility="文生视频 / 图生视频镜头片段",
        model_class="video_generation",
        system_prompt=(
            "你是视频生成提示词工程师。把镜头编译成视频生成提示词，强调主体运动、"
            "运镜方向、动作连续性、镜头时长，避免画面漂移与角色外貌变化。"
        ),
    ),
    SubAgentRole(
        id="tts",
        name="配音",
        name_en="VoiceActor",
        responsibility="旁白、角色台词、音频文件",
        model_class="tts",
        system_prompt=(
            "你是配音导演。根据台词与情绪标记选择音色、语速、停顿，生成自然贴合"
            "短剧节奏的配音。"
        ),
    ),
    SubAgentRole(
        id="editor",
        name="剪辑合成",
        name_en="Editor",
        responsibility="合成镜头、配音、字幕、BGM、转场",
        model_class="render_engine",
        system_prompt=(
            "你是剪辑师。按剪辑计划合成镜头、配音、字幕、BGM 与转场，保证 3 秒钩子、"
            "卡点字幕与反转节奏，输出竖屏成片。"
        ),
    ),
    SubAgentRole(
        id="qc",
        name="质检",
        name_en="QualityControl",
        responsibility="剧情连贯性、角色一致性、字幕错字、时长、违规风险、缺失素材",
        model_class="fast_text",
        system_prompt=(
            "你是质检员。检查剧情连贯性、角色与场景一致性、字幕错字、总时长偏差、"
            "缺失素材与违规风险，给出可重试的具体问题清单。"
        ),
    ),
]

_TEAM_INDEX = {role.id: role for role in SUB_AGENT_TEAM}


def sub_agent_by_id(role_id: str) -> SubAgentRole | None:
    """按 id 取子代理角色。"""
    return _TEAM_INDEX.get(role_id)
