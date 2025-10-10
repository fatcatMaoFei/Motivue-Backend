from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from readiness.state import (
    InsightAction,
    InsightEvidence,
    InsightItem,
    ReadinessState,
)


def _get_threshold(personalized: Optional[dict], key: str, default: float) -> float:
    if personalized and key in personalized:
        try:
            return float(personalized[key])
        except Exception:
            return default
    return default


def _make_insight_id(state: ReadinessState, suffix: str) -> str:
    base = state.raw_inputs.date or "today"
    user = state.raw_inputs.user_id or "user"
    return f"{user}_{base}_{suffix}"


def _create_insight(
    state: ReadinessState,
    *,
    suffix: str,
    trigger: str,
    summary: str,
    explanation: str,
    actions: Sequence[InsightAction],
    evidence: Sequence[InsightEvidence],
    confidence: float,
    tags: Optional[Sequence[str]] = None,
) -> InsightItem:
    return InsightItem(
        id=_make_insight_id(state, suffix),
        trigger=trigger,
        summary=summary,
        explanation=explanation,
        actions=list(actions),
        evidence=list(evidence),
        confidence=confidence,
        tags=list(tags) if tags else None,
    )


def _maybe_high_load_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    metrics = state.metrics.training_load
    thresholds = state.metrics.baselines.personalized_thresholds
    acwr = metrics.acwr_value
    if acwr is None:
        return
    high_thr = _get_threshold(thresholds, "acwr_high", 1.3)
    if acwr >= high_thr:
        fatigue_score = state.metrics.subjective.fatigue_score
        hooper_band = (state.metrics.subjective.hooper_bands or {}).get("fatigue")
        actions = [
            InsightAction(
                recommendation="未来 48 小时降低训练量 15-25%，避免高强度爆发训练。",
                category="training_adjustment",
                priority=1,
            ),
            InsightAction(
                recommendation="安排 30-45 分钟低强度恢复（例如轻度有氧、拉伸或呼吸练习）。",
                category="recovery",
                priority=2,
            ),
        ]
        ev = [
            InsightEvidence(
                key="acwr_value",
                value=acwr,
                description="ACWR 高于个性化阈值",
            )
        ]
        if hooper_band == "high":
            ev.append(
                InsightEvidence(
                    key="hooper_fatigue_band",
                    description="Hooper 疲劳处于高档",
                )
            )
        if fatigue_score is not None:
            ev.append(
                InsightEvidence(
                    key="fatigue_score",
                    value=fatigue_score,
                    description="综合疲劳指数升高",
                )
            )
        insight = _create_insight(
            state,
            suffix="acwr_high",
            trigger="acwr_high",
            summary="训练负荷偏高",
            explanation=(
                f"ACWR 达到 {acwr:.2f}，超过个性化阈值 {high_thr:.2f}。"
                " 建议及时安排恢复并降低短期训练量。"
            ),
            actions=actions,
            evidence=ev,
            confidence=0.75,
            tags=["training_load", "recovery"],
        )
        insights.append(insight)


def _maybe_low_load_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    metrics = state.metrics.training_load
    acwr = metrics.acwr_value
    if acwr is None:
        return
    low_thr = _get_threshold(
        state.metrics.baselines.personalized_thresholds, "acwr_low", 0.6
    )
    if acwr <= low_thr:
        actions = [
            InsightAction(
                recommendation="适度增加训练量或集中刺激关键项目，以避免去适应。",
                category="training_adjustment",
                priority=2,
            )
        ]
        ev = [
            InsightEvidence(
                key="acwr_value",
                value=acwr,
                description="ACWR 低于理想窗口",
            )
        ]
        insights.append(
            _create_insight(
                state,
                suffix="acwr_low",
                trigger="acwr_low",
                summary="训练负荷偏低",
                explanation=(
                    f"ACWR 仅为 {acwr:.2f}，低于推荐窗口 {low_thr:.2f}，"
                    "可能影响训练适应效果。"
                ),
                actions=actions,
                evidence=ev,
                confidence=0.6,
                tags=["training_load"],
            )
        )


def _maybe_sleep_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    recovery = state.metrics.recovery
    sleep_eff = recovery.sleep_efficiency
    if sleep_eff is None:
        return
    baseline_eff = state.metrics.baselines.sleep_baseline_efficiency or 0.85
    threshold = baseline_eff - 0.05
    if sleep_eff < threshold:
        actions = [
            InsightAction(
                recommendation="睡前 60 分钟减少屏幕使用，建立固定作息与放松流程。",
                category="lifestyle",
                priority=2,
            ),
            InsightAction(
                recommendation="确保卧室环境安静、降噪与适宜温度。",
                category="lifestyle",
                priority=3,
            ),
        ]
        ev = [
            InsightEvidence(
                key="sleep_efficiency",
                value=sleep_eff,
                description="近期睡眠效率下降",
            )
        ]
        if state.raw_inputs.journal.screen_before_bed:
            ev.append(
                InsightEvidence(
                    key="screen_before_bed",
                    description="存在睡前屏幕使用记录",
                )
            )
        delta = recovery.sleep_duration_delta
        detail = (
            f"睡眠效率 {sleep_eff:.2f}，低于基线 {baseline_eff:.2f}。"
            if delta is None or abs(delta) < 1e-3
            else f"睡眠效率 {sleep_eff:.2f}，且时长较基线偏差 {delta:+.2f} 小时。"
        )
        insights.append(
            _create_insight(
                state,
                suffix="sleep_eff_drop",
                trigger="sleep_efficiency_drop",
                summary="睡眠效率下降影响恢复",
                explanation=detail,
                actions=actions,
                evidence=ev,
                confidence=0.65,
                tags=["sleep", "recovery"],
            )
        )


def _maybe_hrv_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    z = state.metrics.physiology.hrv_z_score
    if z is None:
        return
    severe_thr = _get_threshold(
        state.metrics.baselines.personalized_thresholds, "hrv_severe_decline", -1.5
    )
    mild_thr = _get_threshold(
        state.metrics.baselines.personalized_thresholds, "hrv_decline", -0.5
    )
    if z <= severe_thr:
        severity = "严重下降"
        confidence = 0.8
    elif z <= mild_thr:
        severity = "下降"
        confidence = 0.65
    else:
        return
    actions = [
        InsightAction(
            recommendation="增加恢复手段（充足睡眠、营养、主动恢复），短期内避免高强度模式。",
            category="recovery",
            priority=1,
        )
    ]
    ev = [
        InsightEvidence(
            key="hrv_z_score",
            value=z,
            description="HRV 相较基线出现下降",
        )
    ]
    insights.append(
        _create_insight(
            state,
            suffix="hrv_decline",
            trigger="hrv_decline",
            summary=f"HRV {severity}",
            explanation=f"HRV Z-score 为 {z:.2f}，低于个性化阈值，提示自律神经恢复不足。",
            actions=actions,
            evidence=ev,
            confidence=confidence,
            tags=["physiology", "recovery"],
        )
    )


def _maybe_subjective_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    bands = state.metrics.subjective.hooper_bands or {}
    mapping = {
        "fatigue": ("疲劳压力升高", "fatigue"),
        "soreness": ("肌肉酸痛偏高", "soreness"),
        "stress": ("心理压力偏高", "stress"),
        "sleep": ("主观睡眠质量偏低", "sleep"),
    }
    for key, (summary, tag) in mapping.items():
        if bands.get(key) != "high":
            continue
        explanations = {
            "fatigue": "主观疲劳评分为高档，需安排恢复或调整训练。",
            "soreness": "主观酸痛评分高，需要关注肌肉恢复与拉伸。",
            "stress": "主观压力高，注意心理恢复与压力管理。",
            "sleep": "主观睡眠质量差，建议优化睡眠习惯。",
        }
        actions = [
            InsightAction(
                recommendation="记录具体感受与诱因，安排主动恢复或减量训练。",
                category="recovery",
                priority=2,
            )
        ]
        evidence = [
            InsightEvidence(
                key=f"hooper_{key}",
                description="Hooper 指标处于高档",
            )
        ]
        insights.append(
            _create_insight(
                state,
                suffix=f"hooper_{key}",
                trigger=f"hooper_{key}_high",
                summary=summary,
                explanation=explanations.get(key, ""),
                actions=actions,
                evidence=evidence,
                confidence=0.55,
                tags=["subjective", tag],
            )
        )
    fatigue_score = state.metrics.subjective.fatigue_score
    if fatigue_score is not None and fatigue_score >= 7.0:
        insights.append(
            _create_insight(
                state,
                suffix="fatigue_score_high",
                trigger="fatigue_score_high",
                summary="综合疲劳指数偏高",
                explanation=(
                    f"综合疲劳指数达到 {fatigue_score:.1f}，"
                    "建议安排额外恢复并监测主观反馈。"
                ),
                actions=[
                    InsightAction(
                        recommendation="短期降低训练密度，安排主动恢复或高质量睡眠。",
                        category="recovery",
                        priority=1,
                    )
                ],
                evidence=[
                    InsightEvidence(
                        key="fatigue_score",
                        value=fatigue_score,
                        description="综合疲劳指数高",
                    )
                ],
                confidence=0.6,
                tags=["subjective", "fatigue"],
            )
        )


def _maybe_lifestyle_insight(
    state: ReadinessState, insights: List[InsightItem]
) -> None:
    journal = state.raw_inputs.journal
    events: List[str] = []
    if journal.alcohol_consumed:
        events.append("当日记录饮酒")
    if journal.late_caffeine:
        events.append("晚间摄入咖啡因")
    if journal.screen_before_bed:
        events.append("睡前使用屏幕")
    if journal.lifestyle_tags:
        events.extend(journal.lifestyle_tags)
    if not events:
        return
    evidence = [
        InsightEvidence(
            key="lifestyle_events",
            description=", ".join(events),
        )
    ]
    insights.append(
        _create_insight(
            state,
            suffix="lifestyle_events",
            trigger="lifestyle_events",
            summary="生活方式事件提示",
            explanation="检测到影响恢复的生活方式事件，建议关注睡眠与恢复质量。",
            actions=[
                InsightAction(
                    recommendation="记录事件及其影响，必要时调整晚间习惯或生活节奏。",
                    category="lifestyle",
                    priority=3,
                )
            ],
            evidence=evidence,
            confidence=0.45,
            tags=["lifestyle"],
        )
    )


def _maybe_data_quality_insight(
    state: ReadinessState, insights: List[InsightItem]
) -> None:
    missing = []
    if state.raw_inputs.sleep.total_sleep_minutes is None:
        missing.append("睡眠时长")
    if state.raw_inputs.hrv.hrv_rmssd_today is None:
        missing.append("HRV")
    if not state.raw_inputs.training_sessions:
        missing.append("训练记录")
    if not missing:
        return
    insights.append(
        _create_insight(
            state,
            suffix="data_quality",
            trigger="data_quality_warning",
            summary="数据质量不足",
            explanation=f"缺少以下关键数据：{', '.join(missing)}，可能影响模型判断准确性。",
            actions=[
                InsightAction(
                    recommendation="补全相关数据或确认设备同步情况。",
                    category="data_quality",
                    priority=1,
                )
            ],
            evidence=[
                InsightEvidence(
                    key="missing_fields",
                    description=", ".join(missing),
                )
            ],
            confidence=0.4,
            tags=["data_quality"],
        )
    )


def _maybe_recovery_matrix_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    """Combine HRV 与神经肌肉指标，识别双重疲劳情形。"""
    hrv_z = state.metrics.physiology.hrv_z_score
    velocity_loss = state.metrics.strength.velocity_loss_pct
    if hrv_z is None or velocity_loss is None:
        return
    if hrv_z <= -0.5 and velocity_loss >= 15.0:
        actions = [
            InsightAction(
                recommendation="降低爆发/速度型训练量，加入神经肌肉恢复（如低幅度跳跃或轻度力量激活）。",
                category="training_adjustment",
                priority=1,
            ),
            InsightAction(
                recommendation="安排呼吸练习与放松训练，帮助自主神经恢复。",
                category="recovery",
                priority=2,
            ),
        ]
        evidence = [
            InsightEvidence(
                key="hrv_z_score",
                value=hrv_z,
                description="HRV 较基线下降，提示自主神经压力。",
            ),
            InsightEvidence(
                key="velocity_loss_pct",
                value=velocity_loss,
                description="速度损失超过 15%，提示神经肌肉疲劳。",
            ),
        ]
        insights.append(
            _create_insight(
                state,
                suffix="recovery_dual_strain",
                trigger="hrv_central_fatigue_matrix",
                summary="自主神经与神经肌肉均呈疲劳",
                explanation="HRV Z-score 与速度损失双双恶化，说明训练和生活压力同时作用，需要同步调整训练与恢复。",
                actions=actions,
                evidence=evidence,
                confidence=0.7,
                tags=["recovery", "training_load"],
            )
        )


def _maybe_sleep_lifestyle_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    """睡眠指标与生活方式事件联动提示。"""
    recovery = state.metrics.recovery
    sleep_delta = recovery.sleep_duration_delta or 0.0
    sleep_eff = recovery.sleep_efficiency
    lifestyle_flags = []
    journal = state.raw_inputs.journal
    if journal.alcohol_consumed:
        lifestyle_flags.append("饮酒")
    if journal.late_caffeine:
        lifestyle_flags.append("晚间咖啡因")
    if journal.screen_before_bed:
        lifestyle_flags.append("睡前屏幕")
    if journal.late_meal:
        lifestyle_flags.append("晚餐偏晚")
    if not lifestyle_flags:
        return
    baseline_eff = state.metrics.baselines.sleep_baseline_efficiency or 0.85
    eff_threshold = baseline_eff - 0.05
    if (sleep_delta <= -0.5) or (sleep_eff is not None and sleep_eff < eff_threshold):
        evidence = [
            InsightEvidence(
                key="sleep_duration_delta",
                value=sleep_delta,
                description="睡眠时长低于基线",
            )
        ]
        if sleep_eff is not None:
            evidence.append(
                InsightEvidence(
                    key="sleep_efficiency",
                    value=sleep_eff,
                    description="睡眠效率下降",
                )
            )
        evidence.append(
            InsightEvidence(
                key="lifestyle_events",
                description="、".join(lifestyle_flags),
            )
        )
        insights.append(
            _create_insight(
                state,
                suffix="sleep_lifestyle_combo",
                trigger="sleep_lifestyle_events",
                summary="生活方式事件影响睡眠恢复",
                explanation="近期生活方式事件（{flags}）与睡眠下降同时出现，建议优化晚间习惯。".format(
                    flags="、".join(lifestyle_flags)
                ),
                actions=[
                    InsightAction(
                        recommendation="限制晚间刺激（咖啡因、酒精、屏幕光），提前结束进食时间。",
                        category="lifestyle",
                        priority=1,
                    )
                ],
                evidence=evidence,
                confidence=0.65,
                tags=["sleep", "lifestyle"],
            )
        )


def _maybe_subjective_priority_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    """主观指标先行但客观尚未恶化时提醒关注。"""
    hooper = state.metrics.subjective.hooper_bands or {}
    fatigue_band = hooper.get("fatigue")
    stress_band = hooper.get("stress")
    if fatigue_band != "high" and stress_band != "high":
        return
    hrv_z = state.metrics.physiology.hrv_z_score or 0.0
    sleep_delta = state.metrics.recovery.sleep_duration_delta or 0.0
    if hrv_z <= -0.5 or sleep_delta <= -0.5:
        return  # 客观已提示，避免重复
    evidence = [
        InsightEvidence(
            key="hooper_fatigue_band" if fatigue_band == "high" else "hooper_stress_band",
            description="Hooper 主观{item}显著升高".format(
                item="疲劳" if fatigue_band == "high" else "压力"
            ),
        ),
        InsightEvidence(
            key="hrv_z_score",
            value=hrv_z,
            description="HRV 尚未出现明显异常",
        ),
        InsightEvidence(
            key="sleep_duration_delta",
            value=sleep_delta,
            description="睡眠与基线差异有限",
        ),
    ]
    insights.append(
        _create_insight(
            state,
            suffix="subjective_priority_alert",
            trigger="subjective_priority",
            summary="主观反馈先行预警",
            explanation="尽管客观指标尚无显著恶化，但主观疲劳/压力已升高，应提前调整恢复与训练节奏。",
            actions=[
                InsightAction(
                    recommendation="记录具体诱因，与教练沟通调整训练与恢复计划。",
                    category="recovery",
                    priority=1,
                )
            ],
            evidence=evidence,
            confidence=0.55,
            tags=["subjective", "monitoring"],
        )
    )


def _maybe_lifestyle_trend_insight(state: ReadinessState, insights: List[InsightItem]) -> None:
    """生活方式标签与趋势指标结合的提醒。"""
    tags = list(state.raw_inputs.journal.lifestyle_tags or [])
    if not tags:
        return
    hrv_z = state.metrics.physiology.hrv_z_score
    sleep_delta = state.metrics.recovery.sleep_duration_delta
    if hrv_z is None and sleep_delta is None:
        return
    if (hrv_z is not None and hrv_z <= -0.5) or (sleep_delta is not None and sleep_delta <= -0.5):
        evidence = []
        if hrv_z is not None:
            evidence.append(
                InsightEvidence(
                    key="hrv_z_score",
                    value=hrv_z,
                    description="HRV 下降，提示恢复压力",
                )
            )
        if sleep_delta is not None:
            evidence.append(
                InsightEvidence(
                    key="sleep_duration_delta",
                    value=sleep_delta,
                    description="睡眠时长低于基线",
                )
            )
        evidence.append(
            InsightEvidence(
                key="lifestyle_tags",
                description="、".join(tags),
            )
        )
        insights.append(
            _create_insight(
                state,
                suffix="lifestyle_trend_watch",
                trigger="lifestyle_trend_overlap",
                summary="生活方式事件与恢复下降同时出现",
                explanation="生活方式标签（{tags}）与恢复指标下滑重叠，建议关注旅行/工作等因素对恢复的影响。".format(
                    tags="、".join(tags)
                ),
                actions=[
                    InsightAction(
                        recommendation="提前规划行程恢复窗口，保持睡眠作息稳定。",
                        category="lifestyle",
                        priority=2,
                    )
                ],
                evidence=evidence,
                confidence=0.6,
                tags=["lifestyle", "recovery"],
            )
        )


def _maybe_conflict_detection_insight(
    state: ReadinessState, insights: List[InsightItem]
) -> None:
    """当客观与主观信号冲突时发出提示。"""
    hrv_z = state.metrics.physiology.hrv_z_score
    sleep_delta = state.metrics.recovery.sleep_duration_delta
    hooper = state.metrics.subjective.hooper_bands or {}
    fatigue_band = hooper.get("fatigue")
    stress_band = hooper.get("stress")
    if hrv_z is None and sleep_delta is None:
        return

    objective_good = (hrv_z is None or hrv_z > -0.5) and (sleep_delta is None or sleep_delta > -0.3)
    objective_poor = (hrv_z is not None and hrv_z <= -0.5) or (sleep_delta is not None and sleep_delta <= -0.5)
    subjective_high = fatigue_band == "high" or stress_band == "high"
    subjective_low = fatigue_band == "low" and stress_band == "low"

    if objective_good and subjective_high:
        evidence = [
            InsightEvidence(
                key="hrv_z_score",
                value=hrv_z,
                description="HRV 未显著下降",
            ),
            InsightEvidence(
                key="sleep_duration_delta",
                value=sleep_delta,
                description="睡眠与基线差距不大",
            ),
            InsightEvidence(
                key="hooper_bands",
                description="主观疲劳/压力偏高",
            ),
        ]
        insights.append(
            _create_insight(
                state,
                suffix="subjective_objective_gap",
                trigger="subjective_over_objective",
                summary="主观疲劳升高但客观指标尚平稳",
                explanation="主观信号已提前预警，虽客观数据尚稳定，仍需安排恢复或关注非训练压力。",
                actions=[
                    InsightAction(
                        recommendation="记录主观感受与生活事件，必要时主动减量或调整训练内容。",
                        category="recovery",
                        priority=1,
                    )
                ],
                evidence=evidence,
                confidence=0.55,
                tags=["subjective", "monitoring"],
            )
        )
    elif objective_poor and subjective_low:
        evidence = [
            InsightEvidence(
                key="hrv_z_score",
                value=hrv_z,
                description="HRV 下降显著",
            ),
            InsightEvidence(
                key="sleep_duration_delta",
                value=sleep_delta,
                description="睡眠时间/效率不足",
            ),
            InsightEvidence(
                key="hooper_bands",
                description="主观疲劳/压力评分较低",
            ),
        ]
        insights.append(
            _create_insight(
                state,
                suffix="objective_hidden_risk",
                trigger="objective_vs_subjective_conflict",
                summary="客观疲劳信号明显但主观感觉良好",
                explanation="客观指标已展示疲劳迹象，尽管主观感觉良好，也需谨慎评估训练负荷。",
                actions=[
                    InsightAction(
                        recommendation="安排一次主动恢复日或睡眠优化，确认身体反应后再恢复高强度训练。",
                        category="training_adjustment",
                        priority=2,
                    )
                ],
                evidence=evidence,
                confidence=0.6,
                tags=["recovery", "monitoring"],
            )
        )

def generate_insights(state: ReadinessState) -> List[InsightItem]:
    """Generate structured insights based on computed metrics."""
    insights: List[InsightItem] = []
    _maybe_high_load_insight(state, insights)
    _maybe_low_load_insight(state, insights)
    _maybe_sleep_insight(state, insights)
    _maybe_hrv_insight(state, insights)
    _maybe_subjective_insight(state, insights)
    _maybe_lifestyle_insight(state, insights)
    _maybe_data_quality_insight(state, insights)
    _maybe_recovery_matrix_insight(state, insights)
    _maybe_sleep_lifestyle_insight(state, insights)
    _maybe_subjective_priority_insight(state, insights)
    _maybe_lifestyle_trend_insight(state, insights)
    _maybe_conflict_detection_insight(state, insights)
    return insights


def populate_insights(state: ReadinessState) -> ReadinessState:
    """Populate the state's insights list in-place and return the state."""
    state.insights = generate_insights(state)
    return state


__all__ = ["generate_insights", "populate_insights"]
