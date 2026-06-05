"""Prompt Compiler — 把故事板字段编译成各模型的提示词。

核心价值：不同图片/视频/TTS 模型对提示词格式敏感；统一从故事板编译，
保证剧情/角色/镜头一致性；切换模型只改 adapter；失败重试可只重编译
单个镜头。
"""

from __future__ import annotations

from backend.app.core.creative_studio.storyboard import Shot, Storyboard


def compile_image_prompt(shot: Shot, storyboard: Storyboard) -> str:
    """把镜头编译成图片生成提示词。"""
    cam = shot.camera
    light = shot.lighting
    parts = [
        f"cinematic vertical short drama, {storyboard.style_profile}",
        f"genre: {storyboard.genre}",
        f"scene: {shot.scene}",
        f"shot size: {cam.shot_size}, angle: {cam.angle}, lens: {cam.lens}",
        f"composition: {cam.composition}",
        f"lighting: {light.style}, key light {light.key_light}, "
        f"contrast {light.contrast}, color temperature {light.color_temperature}",
        f"mood: {light.mood or shot.emotion}",
        f"action: {shot.action}" if shot.action else "",
        f"aspect ratio {storyboard.aspect_ratio.value}",
        "high quality, film grain, professional color grading",
    ]
    # 注入角色一致性参考
    if shot.continuity.character_ref:
        parts.append(f"character ref: {shot.continuity.character_ref}")
    if shot.continuity.scene_ref:
        parts.append(f"scene ref: {shot.continuity.scene_ref}")
    return ", ".join(p for p in parts if p)


def compile_video_prompt(shot: Shot, storyboard: Storyboard) -> str:
    """把镜头编译成视频生成提示词。"""
    cam = shot.camera
    parts = [
        f"{cam.movement} camera movement",
        f"subject action: {shot.action or shot.plot_purpose}",
        f"shot size {cam.shot_size}, {cam.angle}",
        f"duration {shot.duration_seconds}s",
        f"emotion: {shot.emotion}",
        "maintain character appearance and outfit, no drift, stable scene",
    ]
    if shot.continuity.character_ref:
        parts.append(f"consistent character {shot.continuity.character_ref}")
    return ", ".join(p for p in parts if p)


def compile_tts_text(shot: Shot) -> str:
    """提取镜头配音文本。"""
    return shot.dialogue or shot.subtitle or ""


def compile_storyboard_prompts(storyboard: Storyboard) -> Storyboard:
    """为故事板所有镜头编译 visual_prompt / video_prompt（就地回填）。"""
    for shot in storyboard.shots:
        if not shot.visual_prompt:
            shot.visual_prompt = compile_image_prompt(shot, storyboard)
        if not shot.video_prompt:
            shot.video_prompt = compile_video_prompt(shot, storyboard)
    storyboard.touch()
    return storyboard
