from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from weekly_report.analysis.models import (
    AnalysisBundle,
    DailyRootCause,
    LifestyleImpact,
    LoadImpactSummary,
    RecoveryResponseSummary,
    SleepImpactSummary,
    SubjectiveObjectiveConflictSummary,
    TrendStabilitySummary,
    OutlierSummary,
)
from weekly_report.models import WeeklyHistoryEntry
from weekly_report.state import ReadinessState


def _build_context(state: Optional[ReadinessState]) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        "sleep_baseline_hours": None,
        "sleep_eff_baseline": None,
        "rest_ratio_baseline": None,
        "hrv_mu": None,
        "hrv_sigma": None,
        "acwr_high": 1.3,
        "acwr_low": 0.6,
        "daily_au_high": 500.0,
        "daily_au_low": 150.0,
        "sleep_low_hours": None,
        "sleep_efficiency_low": None,
        "rest_ratio_floor": 0.25,
        "subjective_bands": {},
    }
    if state is None:
        return ctx

    baselines = state.metrics.baselines
    ctx["sleep_baseline_hours"] = baselines.sleep_baseline_hours
    ctx["sleep_eff_baseline"] = baselines.sleep_baseline_efficiency
    ctx["rest_ratio_baseline"] = baselines.rest_baseline_ratio
    ctx["hrv_mu"] = baselines.hrv_mu
    ctx["hrv_sigma"] = baselines.hrv_sigma

    thresholds = dict(baselines.personalized_thresholds or {})
    if "acwr_high" in thresholds:
        ctx["acwr_high"] = thresholds["acwr_high"]
    if "acwr_low" in thresholds:
        ctx["acwr_low"] = thresholds["acwr_low"]
    if "au_high" in thresholds:
        ctx["daily_au_high"] = thresholds["au_high"]
    if "au_low" in thresholds:
        ctx["daily_au_low"] = thresholds["au_low"]
    if "sleep_low_hours" in thresholds:
        ctx["sleep_low_hours"] = thresholds["sleep_low_hours"]
    if "sleep_efficiency_low" in thresholds:
        ctx["sleep_efficiency_low"] = thresholds["sleep_efficiency_low"]
    if "rest_ratio_floor" in thresholds:
        ctx["rest_ratio_floor"] = thresholds["rest_ratio_floor"]

    subjective = state.metrics.subjective
    if subjective.hooper_bands:
        ctx["subjective_bands"] = dict(subjective.hooper_bands)

    return ctx


def run_analysis(
    history: Sequence[WeeklyHistoryEntry],
    *,
    state: Optional[ReadinessState] = None,
) -> AnalysisBundle:
    entries = sorted(history, key=lambda x: x.date)
    context = _build_context(state)
    root_causes = _compute_root_causes(entries, context)
    load_summary = _compute_load_impacts(entries, context)
    sleep_summary = _compute_sleep_impacts(entries, context)
    lifestyle_summary = _compute_lifestyle_impacts(entries, context)
    conflicts = _compute_subjective_objective_conflicts(entries, context)
    recovery = _compute_recovery_response(entries, context)
    trend = _compute_trends(entries, context)
    outliers = _compute_outliers(entries, context)

    return AnalysisBundle(
        root_causes=root_causes,
        load_impact=load_summary,
        sleep_impact=sleep_summary,
        lifestyle_impacts=lifestyle_summary,
        subjective_objective_conflicts=conflicts,
        recovery_response=recovery,
        trend_stability=trend,
        outliers=outliers,
    )


def _compute_root_causes(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> List[DailyRootCause]:
    scored = [
        entry
        for entry in entries
        if entry.readiness_score is not None
    ]
    scored.sort(key=lambda e: e.readiness_score)  # ascending readiness
    drivers: List[DailyRootCause] = []
    if not scored:
        return drivers

    readiness_mean = mean([e.readiness_score for e in scored])
    sleep_mean = (
        mean([e.sleep_duration_hours for e in scored if e.sleep_duration_hours is not None])
        if any(e.sleep_duration_hours is not None for e in scored)
        else None
    )
    hrv_mean = (
        mean([e.hrv_rmssd for e in scored if e.hrv_rmssd is not None])
        if any(e.hrv_rmssd is not None for e in scored)
        else None
    )

    acwr_high = context.get("acwr_high", 1.3)
    load_high = context.get("daily_au_high", 500.0)
    sleep_baseline = context.get("sleep_baseline_hours")
    sleep_low_hours = context.get("sleep_low_hours")
    sleep_eff_floor = context.get("sleep_efficiency_low")
    rest_ratio_baseline = context.get("rest_ratio_baseline")
    rest_ratio_floor = context.get("rest_ratio_floor", 0.25)
    hrv_mu = context.get("hrv_mu")
    hrv_sigma = context.get("hrv_sigma")

    for entry in scored[:3]:  # focus on worst 3 days if available
        reasons: List[str] = []
        if entry.acwr is not None and acwr_high is not None and entry.acwr >= acwr_high:
            reasons.append(f"ACWR 偏高（{entry.acwr:.2f}≥{acwr_high:.2f}）")
        if entry.daily_au is not None and entry.daily_au >= load_high:
            reasons.append(f"训练量高（{entry.daily_au:.0f} AU）")

        hrv_z = entry.hrv_z_score
        if hrv_z is None and entry.hrv_rmssd is not None and hrv_mu is not None and hrv_sigma:
            if hrv_sigma > 1e-6:
                hrv_z = (entry.hrv_rmssd - hrv_mu) / hrv_sigma

        if hrv_z is not None and hrv_z <= -0.5:
            reasons.append(f"HRV 下滑（Z={hrv_z:.2f}）")
        elif entry.hrv_rmssd is not None and hrv_mean is not None and entry.hrv_rmssd < hrv_mean - 5:
            reasons.append("HRV 低于周均水平")

        sleep_threshold: Optional[float] = None
        if sleep_low_hours is not None:
            sleep_threshold = sleep_low_hours
        elif sleep_baseline is not None:
            sleep_threshold = sleep_baseline - 0.5
        elif sleep_mean is not None:
            sleep_threshold = sleep_mean - 0.5

        if (
            entry.sleep_duration_hours is not None
            and sleep_threshold is not None
            and entry.sleep_duration_hours < sleep_threshold
        ):
            if sleep_baseline is not None:
                reasons.append(
                    f"睡眠不足（{entry.sleep_duration_hours:.1f}h < 基线 {sleep_baseline:.1f}h）"
                )
            else:
                reasons.append("睡眠不足")

        if (
            entry.sleep_total_minutes is not None
            and entry.sleep_deep_minutes is not None
            and entry.sleep_rem_minutes is not None
        ):
            restorative_ratio = (entry.sleep_deep_minutes + entry.sleep_rem_minutes) / max(
                entry.sleep_total_minutes, 1
            )
            target_ratio = rest_ratio_baseline - 0.05 if rest_ratio_baseline else rest_ratio_floor
            if (
                target_ratio is not None
                and restorative_ratio < target_ratio
                and "恢复性睡眠偏低" not in reasons
            ):
                reasons.append("恢复性睡眠偏低")
            if (
                sleep_eff_floor is not None
                and restorative_ratio < sleep_eff_floor
                and "睡眠效率下降" not in reasons
            ):
                reasons.append("睡眠效率下降")

        if entry.hooper:
            fatigue = entry.hooper.get("fatigue")
            stress = entry.hooper.get("stress")
            if fatigue is not None and fatigue >= 6:
                reasons.append("主观疲劳高")
            if stress is not None and stress >= 6:
                reasons.append("主观压力高")
        if entry.lifestyle_events:
            reasons.extend([f"生活方式: {evt}" for evt in entry.lifestyle_events])

        if not reasons and entry.readiness_score < readiness_mean - 5:
            reasons.append("准备度显著低于周均")

        drivers.append(
            DailyRootCause(
                date=entry.date,
                readiness_score=entry.readiness_score,
                readiness_band=entry.readiness_band,
                drivers=reasons,
            )
        )
    return drivers


def _compute_load_impacts(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> LoadImpactSummary:
    high_thr = context.get("acwr_high", 1.3) or 1.3
    low_thr = context.get("acwr_low", 0.6) or 0.6
    high_acwr_indices = [
        idx for idx, entry in enumerate(entries)
        if entry.acwr is not None and entry.acwr >= high_thr
    ]
    low_acwr_days = len(
        [
            entry
            for entry in entries
            if entry.acwr is not None and entry.acwr <= low_thr
        ]
    )
    total_acwr_days = len([entry for entry in entries if entry.acwr is not None])
    next_day_readiness_deltas: List[float] = []
    next_day_hrv_deltas: List[float] = []
    streak_readiness_deltas: List[float] = []
    streak_hrv_deltas: List[float] = []
    streak = 0
    consecutive_runs = 0

    readiness_values = [entry.readiness_score for entry in entries]
    hrv_values = [entry.hrv_rmssd for entry in entries]
    load_values = [entry.daily_au for entry in entries]

    for idx in high_acwr_indices:
        if idx + 1 < len(entries):
            today = entries[idx]
            tomorrow = entries[idx + 1]
            if today.readiness_score is not None and tomorrow.readiness_score is not None:
                next_day_readiness_deltas.append(tomorrow.readiness_score - today.readiness_score)
            if today.hrv_rmssd is not None and tomorrow.hrv_rmssd is not None:
                next_day_hrv_deltas.append(tomorrow.hrv_rmssd - today.hrv_rmssd)

    for idx, entry in enumerate(entries):
        if entry.acwr is not None and entry.acwr >= high_thr:
            streak += 1
            if streak == 2:
                consecutive_runs += 1
            if idx + 1 < len(entries):
                tomorrow = entries[idx + 1]
                if (
                    entry.readiness_score is not None
                    and tomorrow.readiness_score is not None
                ):
                    streak_readiness_deltas.append(
                        tomorrow.readiness_score - entry.readiness_score
                    )
                if entry.hrv_rmssd is not None and tomorrow.hrv_rmssd is not None:
                    streak_hrv_deltas.append(tomorrow.hrv_rmssd - entry.hrv_rmssd)
        else:
            streak = 0

    readiness_corr = _pearson_corr(load_values, readiness_values)
    hrv_corr = _pearson_corr(load_values, hrv_values)

    return LoadImpactSummary(
        high_acwr_days=len(high_acwr_indices),
        high_acwr_ratio=round(len(high_acwr_indices) / total_acwr_days, 3)
        if total_acwr_days
        else None,
        low_acwr_days=low_acwr_days,
        consecutive_high_runs=consecutive_runs,
        avg_next_day_readiness_delta=_safe_mean(next_day_readiness_deltas),
        avg_next_day_hrv_delta=_safe_mean(next_day_hrv_deltas),
        avg_readiness_drop_after_streak=_safe_mean(streak_readiness_deltas),
        avg_hrv_drop_after_streak=_safe_mean(streak_hrv_deltas),
        correlation_readiness=readiness_corr,
        correlation_hrv=hrv_corr,
    )


def _compute_sleep_impacts(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> SleepImpactSummary:
    sleep_hours = [entry.sleep_duration_hours for entry in entries]
    readiness_scores = [entry.readiness_score for entry in entries]
    hrv_values = [entry.hrv_rmssd for entry in entries]
    restorative_ratios = [
        (
            (entry.sleep_deep_minutes or 0) + (entry.sleep_rem_minutes or 0)
        ) / max(entry.sleep_total_minutes or 0, 1)
        if entry.sleep_total_minutes is not None
        and entry.sleep_deep_minutes is not None
        and entry.sleep_rem_minutes is not None
        else None
        for entry in entries
    ]

    corr_readiness = _pearson_corr(sleep_hours, readiness_scores)
    corr_hrv = _pearson_corr(sleep_hours, hrv_values)
    corr_rest_readiness = _pearson_corr(restorative_ratios, readiness_scores)
    corr_rest_hrv = _pearson_corr(restorative_ratios, hrv_values)

    low_sleep_deltas_readiness: List[float] = []
    low_sleep_deltas_hrv: List[float] = []
    sleep_mean = _safe_mean([v for v in sleep_hours if v is not None])
    sleep_baseline = context.get("sleep_baseline_hours")
    sleep_low_hours = context.get("sleep_low_hours")
    rest_ratio_baseline = context.get("rest_ratio_baseline")
    rest_ratio_floor = context.get("rest_ratio_floor", 0.25)

    low_sleep_days = 0
    low_restorative_days = 0
    rest_readiness_deltas: List[float] = []
    rest_hrv_deltas: List[float] = []

    for idx, entry in enumerate(entries):
        threshold = None
        if sleep_low_hours is not None:
            threshold = sleep_low_hours
        elif sleep_baseline is not None:
            threshold = sleep_baseline - 0.5
        elif sleep_mean is not None:
            threshold = sleep_mean - 0.5

        if (
            threshold is not None
            and entry.sleep_duration_hours is not None
            and entry.sleep_duration_hours < threshold
        ):
            low_sleep_days += 1
            if idx + 1 < len(entries):
                tomorrow = entries[idx + 1]
                if (
                    entry.readiness_score is not None
                    and tomorrow.readiness_score is not None
                ):
                    low_sleep_deltas_readiness.append(
                        tomorrow.readiness_score - entry.readiness_score
                    )
                if entry.hrv_rmssd is not None and tomorrow.hrv_rmssd is not None:
                    low_sleep_deltas_hrv.append(
                        tomorrow.hrv_rmssd - entry.hrv_rmssd
                    )

        rest_threshold = (
            rest_ratio_baseline - 0.05 if rest_ratio_baseline is not None else rest_ratio_floor
        )
        current_rest_ratio = restorative_ratios[idx]
        if (
            rest_threshold is not None
            and current_rest_ratio is not None
            and current_rest_ratio < rest_threshold
        ):
            low_restorative_days += 1
            if idx + 1 < len(entries):
                tomorrow = entries[idx + 1]
                if (
                    entry.readiness_score is not None
                    and tomorrow.readiness_score is not None
                ):
                    rest_readiness_deltas.append(
                        tomorrow.readiness_score - entry.readiness_score
                    )
                if entry.hrv_rmssd is not None and tomorrow.hrv_rmssd is not None:
                    rest_hrv_deltas.append(tomorrow.hrv_rmssd - entry.hrv_rmssd)

    return SleepImpactSummary(
        correlation_readiness=corr_readiness,
        correlation_hrv=corr_hrv,
        restorative_correlation_readiness=corr_rest_readiness,
        restorative_correlation_hrv=corr_rest_hrv,
        low_sleep_days=low_sleep_days,
        avg_readiness_drop=_safe_mean(low_sleep_deltas_readiness),
        avg_hrv_drop=_safe_mean(low_sleep_deltas_hrv),
        low_restorative_days=low_restorative_days,
        avg_readiness_drop_after_low_rest=_safe_mean(rest_readiness_deltas),
        avg_hrv_drop_after_low_rest=_safe_mean(rest_hrv_deltas),
    )


def _compute_lifestyle_impacts(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> List[LifestyleImpact]:
    if not any(entry.lifestyle_events for entry in entries):
        return []
    impacts: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)

    for idx, entry in enumerate(entries):
        if not entry.lifestyle_events:
            continue
        next_entry = entries[idx + 1] if idx + 1 < len(entries) else None
        for event in entry.lifestyle_events:
            readiness_delta = None
            hrv_delta = None
            sleep_delta = None
            if next_entry:
                if entry.readiness_score is not None and next_entry.readiness_score is not None:
                    readiness_delta = next_entry.readiness_score - entry.readiness_score
                if entry.hrv_rmssd is not None and next_entry.hrv_rmssd is not None:
                    hrv_delta = next_entry.hrv_rmssd - entry.hrv_rmssd
                if entry.sleep_duration_hours is not None and next_entry.sleep_duration_hours is not None:
                    sleep_delta = next_entry.sleep_duration_hours - entry.sleep_duration_hours
            impacts[event].append(
                (
                    readiness_delta if readiness_delta is not None else 0.0,
                    hrv_delta if hrv_delta is not None else 0.0,
                    sleep_delta if sleep_delta is not None else 0.0,
                )
            )

    lifestyle_impacts: List[LifestyleImpact] = []
    for event, deltas in impacts.items():
        if not deltas:
            continue
        readiness_changes = [d[0] for d in deltas]
        hrv_changes = [d[1] for d in deltas]
        sleep_changes = [d[2] for d in deltas]
        readiness_avg = _safe_mean(readiness_changes)
        hrv_avg = _safe_mean(hrv_changes)
        sleep_avg = _safe_mean(sleep_changes)
        note_parts: List[str] = []
        if readiness_avg is not None and abs(readiness_avg) >= 0.5:
            note_parts.append(f"准备度{readiness_avg:+.1f}")
        if hrv_avg is not None and abs(hrv_avg) >= 0.5:
            note_parts.append(f"HRV{hrv_avg:+.1f}")
        if sleep_avg is not None and abs(sleep_avg) >= 0.3:
            note_parts.append(f"睡眠时长{sleep_avg:+.1f}h")
            if sleep_avg < 0 and context.get("sleep_baseline_hours") is not None:
                note_parts.append("低于睡眠基线")
        notes = "；".join(note_parts) if note_parts else None
        lifestyle_impacts.append(
            LifestyleImpact(
                event=event,
                occurrences=len(deltas),
                avg_readiness_delta=readiness_avg,
                avg_hrv_delta=hrv_avg,
                avg_sleep_delta=sleep_avg,
                notes=notes,
            )
        )
    return lifestyle_impacts


def _compute_subjective_objective_conflicts(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> SubjectiveObjectiveConflictSummary:
    subjective_high_objective_stable = 0
    subjective_low_objective_low = 0
    stress_conflicts = 0
    sleep_quality_conflicts = 0
    details: Dict[str, List[date]] = defaultdict(list)
    sleep_baseline = context.get("sleep_baseline_hours")
    sleep_ok_threshold = sleep_baseline - 0.5 if sleep_baseline else 6.5
    sleep_low_threshold = context.get("sleep_low_hours") or 6.0
    hrv_mu = context.get("hrv_mu")
    hrv_sigma = context.get("hrv_sigma")

    for entry in entries:
        if not entry.hooper:
            continue
        fatigue = entry.hooper.get("fatigue")
        stress = entry.hooper.get("stress")
        sleep_quality = entry.hooper.get("sleep")
        hrv_z = entry.hrv_z_score
        if hrv_z is None and entry.hrv_rmssd is not None and hrv_mu is not None and hrv_sigma:
            if hrv_sigma > 1e-6:
                hrv_z = (entry.hrv_rmssd - hrv_mu) / hrv_sigma
        objective_ok = (hrv_z is None or hrv_z > -0.3) and (
            entry.sleep_duration_hours is None or entry.sleep_duration_hours >= sleep_ok_threshold
        )
        objective_low = (hrv_z is not None and hrv_z <= -0.5) or (
            entry.sleep_duration_hours is not None and entry.sleep_duration_hours <= sleep_low_threshold
        )

        if fatigue is not None and fatigue >= 6 and objective_ok:
            subjective_high_objective_stable += 1
            details["subjective_high_objective_stable"].append(entry.date)
        if fatigue is not None and fatigue <= 3 and objective_low:
            subjective_low_objective_low += 1
            details["subjective_low_objective_low"].append(entry.date)
        if stress is not None and stress >= 6 and objective_ok:
            stress_conflicts += 1
            details["subjective_stress_conflict"].append(entry.date)
        if (
            sleep_quality is not None
            and sleep_quality <= 3
            and entry.sleep_duration_hours is not None
            and entry.sleep_duration_hours >= sleep_ok_threshold
        ):
            sleep_quality_conflicts += 1
            details["subjective_sleep_quality_conflict"].append(entry.date)

    return SubjectiveObjectiveConflictSummary(
        subjective_high_objective_stable=subjective_high_objective_stable,
        subjective_low_objective_low=subjective_low_objective_low,
        stress_conflicts=stress_conflicts,
        sleep_quality_conflicts=sleep_quality_conflicts,
        details=details,
    )


def _compute_recovery_response(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> RecoveryResponseSummary:
    recovery_ratios: List[float] = []
    slow_cases = 0
    slow_case_dates: List[date] = []
    readiness_rebounds: List[float] = []
    sleep_rebounds: List[float] = []
    sleep_vs_baseline: List[float] = []

    low_load_threshold = context.get("daily_au_low", 300.0) or 300.0
    baseline_sleep = context.get("sleep_baseline_hours")
    hrv_mu = context.get("hrv_mu")
    hrv_sigma = context.get("hrv_sigma")

    for idx in range(len(entries) - 2):
        day0 = entries[idx]
        day1 = entries[idx + 1]
        day2 = entries[idx + 2]

        def _hrv_z(entry: WeeklyHistoryEntry) -> Optional[float]:
            z = entry.hrv_z_score
            if z is None and entry.hrv_rmssd is not None and hrv_mu is not None and hrv_sigma:
                if hrv_sigma > 1e-6:
                    z = (entry.hrv_rmssd - hrv_mu) / hrv_sigma
            return z

        z0 = _hrv_z(day0)
        z1 = _hrv_z(day1)
        z2 = _hrv_z(day2)

        if z0 is None or z1 is None or z2 is None:
            continue
        if z0 <= -0.5 and z1 <= -0.5:
            if day1.daily_au is None or day1.daily_au <= low_load_threshold:
                delta = z2 - z1
                recovery_ratios.append(delta)
                if delta <= 0.1:
                    slow_cases += 1
                    slow_case_dates.append(day2.date)
                if (
                    day1.readiness_score is not None
                    and day2.readiness_score is not None
                ):
                    readiness_rebounds.append(
                        day2.readiness_score - day1.readiness_score
                    )
                if (
                    day1.sleep_duration_hours is not None
                    and day2.sleep_duration_hours is not None
                ):
                    sleep_rebounds.append(
                        day2.sleep_duration_hours - day1.sleep_duration_hours
                    )
                    if baseline_sleep is not None:
                        sleep_vs_baseline.append(day2.sleep_duration_hours - baseline_sleep)

    notes = None
    if slow_case_dates:
        last_case = slow_case_dates[-1].isoformat()
        notes = f"最近恢复不足发生在 {last_case}"

    return RecoveryResponseSummary(
        average_recovery_ratio=_safe_mean(recovery_ratios),
        slow_recovery_cases=slow_cases,
        avg_readiness_rebound=_safe_mean(readiness_rebounds),
        avg_sleep_rebound=_safe_mean(sleep_rebounds),
        avg_sleep_rebound_vs_baseline=_safe_mean(sleep_vs_baseline),
        notes=notes,
    )


def _compute_trends(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> TrendStabilitySummary:
    readiness_scores = [e.readiness_score for e in entries]
    hrv_values = [e.hrv_rmssd for e in entries]
    sleep_hours = [e.sleep_duration_hours for e in entries]

    readiness_slope = _simple_slope(readiness_scores)
    hrv_slope = _simple_slope(hrv_values)
    sleep_slope = _simple_slope(sleep_hours)

    readiness_vol = _safe_pstdev(readiness_scores)
    hrv_vol = _safe_pstdev(hrv_values)
    sleep_vol = _safe_pstdev(sleep_hours)

    def _first_last(values: Sequence[Optional[float]]) -> Tuple[Optional[float], Optional[float]]:
        first = next((v for v in values if v is not None), None)
        last = next((v for v in reversed(values) if v is not None), None)
        return first, last

    readiness_first, readiness_last = _first_last(readiness_scores)
    readiness_change = (
        round(readiness_last - readiness_first, 3)
        if readiness_first is not None and readiness_last is not None
        else None
    )
    _, hrv_last = _first_last(hrv_values)
    _, sleep_last = _first_last(sleep_hours)

    hrv_mu = context.get("hrv_mu")
    hrv_vs_baseline = (
        round((hrv_last or 0) - hrv_mu, 3) if hrv_mu is not None and hrv_last is not None else None
    )
    sleep_baseline = context.get("sleep_baseline_hours")
    sleep_vs_baseline = (
        round((sleep_last or 0) - sleep_baseline, 3)
        if sleep_baseline is not None and sleep_last is not None
        else None
    )

    return TrendStabilitySummary(
        readiness_slope=readiness_slope,
        hrv_slope=hrv_slope,
        sleep_slope=sleep_slope,
        readiness_volatility=readiness_vol,
        hrv_volatility=hrv_vol,
        sleep_volatility=sleep_vol,
        readiness_change=readiness_change,
        hrv_vs_baseline=hrv_vs_baseline,
        sleep_vs_baseline=sleep_vs_baseline,
    )


def _compute_outliers(
    entries: Sequence[WeeklyHistoryEntry],
    context: Dict[str, Any],
) -> Optional[OutlierSummary]:
    # Absolute AU threshold for plausibility
    ABS_THR = 2000.0
    au_outliers: list[tuple[date, float]] = []
    for e in entries:
        if e.daily_au is not None:
            try:
                au = float(e.daily_au)
            except Exception:
                continue
            if au > ABS_THR:
                au_outliers.append((e.date, au))
    if not au_outliers:
        return None
    # Build summary
    notes = (
        f"检测到 {len(au_outliers)} 天训练量 AU 超过阈值 {ABS_THR:.0f}，建议核查数据录入是否异常。"
    )
    return OutlierSummary(au_threshold_abs=ABS_THR, au_outliers=au_outliers, notes=notes)


def _pearson_corr(xs: Sequence[Optional[float]], ys: Sequence[Optional[float]]) -> Optional[float]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xs_clean = [p[0] for p in pairs]
    ys_clean = [p[1] for p in pairs]
    mean_x = mean(xs_clean)
    mean_y = mean(ys_clean)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator_x = sum((x - mean_x) ** 2 for x in xs_clean)
    denominator_y = sum((y - mean_y) ** 2 for y in ys_clean)
    if denominator_x <= 0 or denominator_y <= 0:
        return None
    return numerator / (denominator_x ** 0.5 * denominator_y ** 0.5)


def _safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return round(mean(cleaned), 3)


def _safe_pstdev(values: Sequence[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if len(cleaned) < 2:
        return None
    return round(pstdev(cleaned), 3)


def _simple_slope(values: Sequence[Optional[float]]) -> Optional[float]:
    cleaned = [(idx, v) for idx, v in enumerate(values) if v is not None]
    if len(cleaned) < 2:
        return None
    xs = [c[0] for c in cleaned]
    ys = [c[1] for c in cleaned]
    mean_x = mean(xs)
    mean_y = mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator <= 0:
        return None
    slope = numerator / denominator
    return round(slope, 3)
