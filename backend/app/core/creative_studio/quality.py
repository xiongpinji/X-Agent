"""质量门：故事板与成片的可验证检查。

对齐 05 文档"质量控制"章节。每个门返回 QualityGate(name, passed, detail)，
失败镜头可被定位并单独重试。
"""

from __future__ import annotations

from backend.app.core.creative_studio.storyboard import QualityGate, Storyboard


def gate_storyboard_fields(sb: Storyboard) -> QualityGate:
    """故事板字段完整性：每镜须有目的、景别、台词或动作。"""
    bad: list[str] = []
    for shot in sb.shots:
        if not shot.plot_purpose:
            bad.append(f"{shot.shot_id}:缺plot_purpose")
        if not shot.camera.shot_size:
            bad.append(f"{shot.shot_id}:缺景别")
        if not (shot.dialogue or shot.action):
            bad.append(f"{shot.shot_id}:缺台词/动作")
    return QualityGate(
        name="storyboard_fields",
        passed=not bad,
        detail="; ".join(bad) if bad else "所有镜头字段完整",
    )


def gate_shot_count(sb: Storyboard) -> QualityGate:
    """镜头数量：3-12 个之间合理。"""
    n = len(sb.shots)
    ok = 3 <= n <= 12
    return QualityGate(
        name="shot_count",
        passed=ok,
        detail=f"镜头数 {n}" + ("" if ok else "（应在 3-12）"),
    )


def gate_duration(sb: Storyboard) -> QualityGate:
    """总时长偏差不超过目标的 15%。"""
    total = sb.total_shot_duration()
    target = sb.target_duration_seconds or 1
    deviation = abs(total - target) / target
    ok = deviation <= 0.15
    return QualityGate(
        name="duration",
        passed=ok,
        detail=f"总时长 {total}s / 目标 {target}s，偏差 {deviation*100:.0f}%",
    )


def gate_subtitle_consistency(sb: Storyboard) -> QualityGate:
    """字幕与台词一致：有台词的镜头应有字幕。"""
    bad = [s.shot_id for s in sb.shots if s.dialogue and not s.subtitle]
    return QualityGate(
        name="subtitle_consistency",
        passed=not bad,
        detail="; ".join(bad) if bad else "字幕与台词一致",
    )


def gate_character_consistency(sb: Storyboard) -> QualityGate:
    """角色一致性：镜头引用的角色须在角色卡中定义。"""
    defined = {c.ref_id for c in sb.character_cards} | {c.name for c in sb.character_cards}
    bad: list[str] = []
    for shot in sb.shots:
        for ch in shot.characters:
            if defined and ch not in defined:
                bad.append(f"{shot.shot_id}:{ch}未定义角色卡")
    return QualityGate(
        name="character_consistency",
        passed=not bad,
        detail="; ".join(bad) if bad else "角色引用一致",
    )


def gate_missing_assets(sb: Storyboard) -> QualityGate:
    """缺失素材检查（合成前）：每镜须有图片或视频。"""
    bad = [s.shot_id for s in sb.shots if not (s.image_path or s.video_path)]
    return QualityGate(
        name="missing_assets",
        passed=not bad,
        detail="; ".join(bad) if bad else "素材齐全",
    )


# 故事板阶段质量门（合成前，不含素材检查）
STORYBOARD_GATES = [
    gate_storyboard_fields,
    gate_shot_count,
    gate_duration,
    gate_subtitle_consistency,
    gate_character_consistency,
]

# 合成前完整质量门（含素材检查）
PRE_COMPOSE_GATES = [*STORYBOARD_GATES, gate_missing_assets]


def run_gates(sb: Storyboard, gates=None) -> list[QualityGate]:
    """运行一组质量门并把结果写回故事板。"""
    gates = gates or STORYBOARD_GATES
    results = [gate(sb) for gate in gates]
    sb.quality_gates = results
    sb.touch()
    return results


def all_passed(results: list[QualityGate]) -> bool:
    return all(r.passed for r in results)
