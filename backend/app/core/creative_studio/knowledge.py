"""短剧专业知识包。

短剧智能体必须内置影视专业知识，不应完全依赖通用模型临场发挥。这些知识
被注入到子代理的 system prompt 中，并被 Prompt Compiler 用于把故事板字段
编译成高质量的图片/视频/TTS 提示词。
"""

from __future__ import annotations

# ===== 短剧类型 =====
DRAMA_GENRES: dict[str, str] = {
    "霸总": "强势男主 + 普通女主，权力差与情感拉扯，强反差与宠溺爽点",
    "甜宠": "轻冲突重甜度，日常互动、误会、和解，情绪柔和明亮",
    "复仇": "受害-隐忍-反击-翻盘，强压抑后强释放，节奏由暗转明",
    "逆袭": "底层主角被轻视，能力/身份揭露，打脸时刻是核心爽点",
    "豪门": "家族权谋、身世之谜、利益与情感冲突，冷暖光影对比强烈",
    "都市": "现实职场/情感，贴近生活的冲突与成长",
    "古风": "古装场景、含蓄情感、礼制冲突，暖色调与质感服化道",
    "赘婿": "身份隐藏-被轻视-真实实力揭露的强反转结构",
}

# ===== 剧本知识 =====
SCREENWRITING_KNOWLEDGE = {
    "structure": ["三幕式", "钩子", "冲突", "爽点", "悬念", "反转", "人设", "情绪递进", "结尾钩子"],
    "hook_rules": [
        "前 3 秒必须抛出冲突或悬念，不能铺垫",
        "第一句台词要制造信息差或身份反差",
        "结尾留钩子，引导完播或下一集",
    ],
    "pacing": "30 秒 3-5 镜，60 秒 5-8 镜，90 秒 8-12 镜；每镜单一叙事目的",
}

# ===== 镜头与运镜知识 =====
CAMERA_KNOWLEDGE = {
    "shot_sizes": ["远景", "全景", "中景", "中近景", "近景", "特写", "大特写", "过肩镜头", "双人镜头", "主观镜头"],
    "angles": ["平视", "俯拍", "仰拍", "鸟瞰", "低机位", "高机位", "侧面", "背面", "正反打"],
    "movements": ["推镜", "拉镜", "摇镜", "移镜", "跟拍", "环绕", "升降", "横移", "手持", "稳定器", "甩镜"],
    "emotion_mapping": {
        "压迫感": "低机位 + 慢推",
        "弱势感": "俯拍",
        "情绪爆点": "特写 / 大特写",
        "冲突": "正反打快切",
        "沉浸": "长镜头",
    },
    "composition": ["三分法", "中心构图", "对称构图", "框中框", "留白", "前景层次", "引导线"],
}

# ===== 光线与影调知识 =====
LIGHTING_KNOWLEDGE = {
    "basics": ["主光", "辅光", "轮廓光", "背景光", "眼神光", "实景光"],
    "quality": ["硬光", "软光", "漫反射", "聚光", "自然窗光", "霓虹光", "烛光", "手机屏幕光"],
    "position": ["顺光", "侧光", "逆光", "顶光", "底光", "侧逆光", "剪影"],
    "tone": ["高调", "低调", "高反差", "低反差", "明暗对比", "黑位控制"],
    "genre_style": {
        "悬疑": "低调光 + 高反差",
        "甜宠": "柔光 + 高调",
        "豪门": "冷暖对比",
        "复仇": "强侧光 + 低调",
        "古风": "暖烛光",
    },
    "consistency": "同一场景保持主光方向、色温、反差和环境光逻辑一致",
}

# ===== 图片提示词知识 =====
IMAGE_PROMPT_KNOWLEDGE = [
    "角色一致性", "固定服装", "表情", "光影", "主光方向", "色温", "影调",
    "构图", "景别", "机位", "景深", "电影感", "竖屏比例", "参考图约束", "negative prompt",
]

# ===== 视频提示词知识 =====
VIDEO_PROMPT_KNOWLEDGE = [
    "主体运动", "运镜方向", "景别变化", "焦点变化", "光线变化", "动作连续性",
    "镜头时长", "情绪变化", "场景稳定", "避免画面漂移", "避免角色外貌变化",
]

# ===== 剪辑知识 =====
EDIT_KNOWLEDGE = {
    "rhythm": ["3 秒钩子", "5-8 秒情绪点", "卡点字幕", "BGM 转折", "反转点", "转场节奏", "封面标题强化"],
}


def knowledge_pack_for(sub_agent_id: str) -> str:
    """按子代理角色返回拼接好的知识包文本，注入其 system prompt。"""
    import json

    packs: dict[str, object] = {
        "planner": SCREENWRITING_KNOWLEDGE,
        "screenwriter": {"genres": DRAMA_GENRES, "screenwriting": SCREENWRITING_KNOWLEDGE},
        "caption": SCREENWRITING_KNOWLEDGE["pacing"],
        "director": CAMERA_KNOWLEDGE,
        "cinematographer": LIGHTING_KNOWLEDGE,
        "art": {"image_prompt": IMAGE_PROMPT_KNOWLEDGE},
        "image": IMAGE_PROMPT_KNOWLEDGE,
        "video": VIDEO_PROMPT_KNOWLEDGE,
        "editor": EDIT_KNOWLEDGE,
    }
    pack = packs.get(sub_agent_id)
    if pack is None:
        return ""
    if isinstance(pack, str):
        return pack
    return json.dumps(pack, ensure_ascii=False, indent=2)
