from __future__ import annotations

from typing import Any, Dict, List

from weekly_report.state import ReadinessState


def score_complexity(state: ReadinessState) -> Dict[str, Any]:
    """Compute a heuristic complexity score to decide whether to trigger advanced reasoning."""
    score = 0
    reasons: List[str] = []
    metrics = state.metrics
    training = metrics.training_load
    baselines = metrics.baselines.personalized_thresholds or {}

    # ACWR thresholds
    acwr = training.acwr_value
    if acwr is not None:
        high_thr = float(baselines.get("acwr_high", 1.3))
        low_thr = float(baselines.get("acwr_low", 0.6))
        if acwr >= high_thr:
            score += 2
            reasons.append(f"ACWR {acwr:.2f} ≥ {high_thr:.2f}")
        elif acwr <= low_thr:
            score += 1
            reasons.append(f"ACWR {acwr:.2f} ≤ {low_thr:.2f}")

    # Consecutive high load days
    if training.consecutive_high_days and training.consecutive_high_days >= 3:
        score += 1
        reasons.append(f"{training.consecutive_high_days} consecutive high-load days")

    # Chronic load extremes
    if training.chronic_load and training.chronic_load < 200:
        score += 1
        reasons.append("Low chronic load (<200 AU)")

    # HRV Z-score
    hrv_z = metrics.physiology.hrv_z_score
    if hrv_z is not None:
        if hrv_z <= -1.5:
            score += 2
            reasons.append(f"HRV Z-score {hrv_z:.2f} indicates severe drop")
        elif hrv_z <= -0.5:
            score += 1
            reasons.append(f"HRV Z-score {hrv_z:.2f} indicates moderate drop")

    # Sleep deltas
    sleep_delta = metrics.recovery.sleep_duration_delta
    if sleep_delta is not None and sleep_delta <= -0.5:
        score += 1
        reasons.append(f"Sleep duration delta {sleep_delta:.2f}h below baseline")

    sleep_eff = metrics.recovery.sleep_efficiency
    baseline_eff = metrics.baselines.sleep_baseline_efficiency
    if sleep_eff is not None and baseline_eff is not None:
        if sleep_eff <= max(0.0, baseline_eff - 0.05):
            score += 1
            reasons.append("Sleep efficiency markedly below baseline")

    # Subjective fatigue / Hooper
    hooper_bands = metrics.subjective.hooper_bands or {}
    high_bands = [k for k, v in hooper_bands.items() if v == "high"]
    if high_bands:
        score += 1
        reasons.append(f"Hooper high bands: {', '.join(high_bands)}")

    fatigue_score = metrics.subjective.fatigue_score
    if fatigue_score is not None and fatigue_score >= 7:
        score += 1
        reasons.append(f"Composite fatigue score {fatigue_score:.1f} ≥ 7")

    # Lifestyle events
    journal = state.raw_inputs.journal
    lifestyle_events = []
    if journal.alcohol_consumed:
        lifestyle_events.append("alcohol")
    if journal.late_caffeine:
        lifestyle_events.append("late_caffeine")
    if journal.screen_before_bed:
        lifestyle_events.append("screen_before_bed")
    if journal.late_meal:
        lifestyle_events.append("late_meal")
    tags = list(journal.lifestyle_tags or [])
    if lifestyle_events or tags:
        event_count = len(lifestyle_events) + len(tags)
        if event_count >= 2:
            score += 1
            reasons.append(f"Lifestyle events recorded: {', '.join(lifestyle_events + tags)}")

    # Data completeness
    missing_fields = []
    sleep = state.raw_inputs.sleep
    if sleep.total_sleep_minutes is None:
        missing_fields.append("total_sleep_minutes")
    if metrics.physiology.hrv_z_score is None and state.raw_inputs.hrv.hrv_rmssd_today is None:
        missing_fields.append("hrv")
    if not state.raw_inputs.training_sessions:
        missing_fields.append("training_sessions")
    if missing_fields:
        score += 1
        reasons.append(f"Missing critical inputs: {', '.join(missing_fields)}")

    label = "complex" if score >= 3 else "simple"
    return {"score": score, "label": label, "reasons": reasons}


__all__ = ["score_complexity"]
