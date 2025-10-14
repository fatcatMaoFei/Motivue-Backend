from __future__ import annotations

from statistics import mean
from typing import Any, Dict, Iterable, Optional, Sequence

from backend.utils.sleep_metrics import compute_sleep_metrics
from physio_age.css import compute_css

from readiness.constants import TRAINING_LOAD_AU
from weekly_report.state import ReadinessState


def _model_copy(model, updates: Dict[str, Any]):
    if not updates:
        return model
    return model.model_copy(update=updates)

_AU_OUTLIER_ABS_THRESHOLD = 2000.0  # AU values above this will be clipped for ACWR/metrics


def _clip_au_outliers(values: Sequence[float], *, abs_threshold: float) -> list[float]:
    """Clip extreme AU values to a reasonable absolute threshold to stabilize ACWR.

    - Negative values are floored at 0
    - Values greater than `abs_threshold` are clipped to `abs_threshold`
    """
    clipped: list[float] = []
    thr = float(abs_threshold)
    for v in values:
        try:
            f = float(v)
        except Exception:
            f = 0.0
        if f < 0:
            f = 0.0
        if f > thr:
            f = thr
        clipped.append(f)
    return clipped


def _labels_to_au(labels: Sequence[str]) -> list[float]:
    res: list[float] = []
    for lab in labels:
        if lab in TRAINING_LOAD_AU:
            res.append(float(TRAINING_LOAD_AU[lab]))
            continue
        if isinstance(lab, str):
            if "极高" in lab:
                res.append(float(TRAINING_LOAD_AU.get("极高", 700)))
            elif "高" in lab:
                res.append(float(TRAINING_LOAD_AU.get("高", 500)))
            elif "中" in lab:
                res.append(float(TRAINING_LOAD_AU.get("中", 350)))
            elif "低" in lab:
                res.append(float(TRAINING_LOAD_AU.get("低", 200)))
            elif "无" in lab:
                res.append(float(TRAINING_LOAD_AU.get("无", 0)))
            else:
                res.append(0.0)
        else:
            res.append(0.0)
    return res


def _ewma(values: Sequence[float], alpha: float) -> float:
    it = iter(values)
    try:
        acc = float(next(it))
    except StopIteration:
        return 0.0
    for v in it:
        acc = alpha * float(v) + (1.0 - alpha) * acc
    return acc


def _calc_acwr(
    recent_au: Sequence[float],
    acute_window: int = 7,
    chronic_window: int = 28,
    *,
    personalized_threshold: Optional[float] = None,
    use_ewma: bool = True,
) -> Dict[str, float | str | None]:
    # 保持与旧实现一致的缺数据防守：不足以计算急性窗口时不返回 ACWR
    if len(recent_au) < acute_window or len(recent_au) < 1:
        return {
            "acwr_value": None,
            "acwr_band": None,
            "acute_load": None,
            "chronic_load": None,
        }

    if use_ewma:
        # EWMA 实现：急性 7d，慢性 28d
        alpha_a = 2.0 / (acute_window + 1.0)
        alpha_c = 2.0 / (chronic_window + 1.0)
        acute = _ewma(recent_au[-acute_window:], alpha_a)
        chronic_slice = recent_au[-chronic_window:] if len(recent_au) >= chronic_window else recent_au
        chronic = _ewma(chronic_slice, alpha_c) if chronic_slice else 0.0
    else:
        acute_slice = recent_au[-acute_window:]
        chronic_slice = recent_au[-chronic_window:] if len(recent_au) >= chronic_window else recent_au
        chronic = mean(chronic_slice) if chronic_slice else 0.0
        acute = mean(acute_slice) if acute_slice else 0.0

    ratio = 0.0 if chronic <= 1e-9 else (acute / chronic)
    threshold = personalized_threshold or 1.3
    band: str
    if ratio >= threshold:
        band = "high"
    elif ratio <= 0.6:
        band = "low"
    else:
        band = "optimal"
    return {
        "acwr_value": round(ratio, 4),
        "acwr_band": band,
        "acute_load": round(acute, 2),
        "chronic_load": round(chronic, 2),
    }


def _calc_consecutive_high_days(recent_au: Sequence[float], high_threshold: float) -> int:
    count = 0
    for value in reversed(recent_au):
        if value >= high_threshold:
            count += 1
        else:
            break
    return count


def populate_training_metrics(
    state: ReadinessState,
    *,
    recent_training_au: Optional[Sequence[float]] = None,
    recent_training_loads: Optional[Sequence[str]] = None,
    personalized_thresholds: Optional[Dict[str, float]] = None,
) -> None:
    loads = list(recent_training_au or [])
    if not loads and recent_training_loads:
        loads = _labels_to_au(recent_training_loads)
    # Clip extreme AU values to avoid ACWR distortion (e.g., accidental 10000 AU entries)
    if loads:
        abs_thr = (personalized_thresholds or {}).get("au_outlier_abs", _AU_OUTLIER_ABS_THRESHOLD)
        loads = _clip_au_outliers(loads, abs_threshold=abs_thr)
    training_updates: Dict[str, Any] = {}
    if loads:
        training_updates["daily_au_28d"] = list(loads[-28:])
        training_updates["daily_au_7d"] = list(loads[-7:])
        acwr = _calc_acwr(
            loads,
            personalized_threshold=(
                (personalized_thresholds or {}).get("acwr_high")
                if personalized_thresholds
                else None
            ),
        )
        training_updates.update(
            {
                "acwr_value": acwr["acwr_value"],
                "acwr_band": acwr["acwr_band"],
                "acute_load": acwr["acute_load"],
                "chronic_load": acwr["chronic_load"],
                "consecutive_high_days": _calc_consecutive_high_days(
                    loads, high_threshold=(personalized_thresholds or {}).get("au_high", 500.0)
                ),
            }
        )
    else:
        training_updates.update(
            {
                "daily_au_28d": None,
                "daily_au_7d": None,
                "acwr_value": None,
                "acwr_band": None,
                "acute_load": None,
                "chronic_load": None,
                "consecutive_high_days": None,
            }
        )

    today_sessions = state.raw_inputs.training_sessions
    if today_sessions:
        total_volume = 0.0
        total_au = 0.0
        for s in today_sessions:
            au = s.au
            if au is None and s.rpe and s.duration_minutes:
                au = s.rpe * s.duration_minutes
            if au is not None:
                total_au += au
            if s.duration_minutes is not None:
                total_volume += s.duration_minutes
        training_updates["training_intensity_index"] = (
            round(total_au / 60.0, 2) if total_au else None
        )
        training_updates["training_volume"] = round(total_volume, 2)
    else:
        training_updates.setdefault("training_intensity_index", None)
        training_updates.setdefault("training_volume", None)

    state.metrics.training_load = _model_copy(
        state.metrics.training_load, training_updates
    )


def populate_recovery_metrics(state: ReadinessState) -> None:
    sleep_payload = {
        "total_sleep_minutes": state.raw_inputs.sleep.total_sleep_minutes,
        "in_bed_minutes": state.raw_inputs.sleep.in_bed_minutes,
        "deep_sleep_minutes": state.raw_inputs.sleep.deep_sleep_minutes,
        "rem_sleep_minutes": state.raw_inputs.sleep.rem_sleep_minutes,
    }
    metrics = compute_sleep_metrics(sleep_payload)
    recovery_updates: Dict[str, Any] = {
        "sleep_efficiency": metrics.get("sleep_efficiency"),
        "sleep_restorative_ratio": metrics.get("restorative_ratio"),
    }
    if state.raw_inputs.sleep.total_sleep_minutes is not None:
        recovery_updates["sleep_duration_hours"] = round(
            state.raw_inputs.sleep.total_sleep_minutes / 60.0, 2
        )
    else:
        recovery_updates["sleep_duration_hours"] = None
    baseline_hours = state.metrics.baselines.sleep_baseline_hours
    sleep_duration_hours = recovery_updates.get("sleep_duration_hours")
    if baseline_hours is not None and sleep_duration_hours is not None:
        recovery_updates["sleep_duration_delta"] = round(
            sleep_duration_hours - baseline_hours, 2
        )
    else:
        recovery_updates["sleep_duration_delta"] = None
    css_input = {
        "total_sleep_minutes": state.raw_inputs.sleep.total_sleep_minutes,
        "in_bed_minutes": state.raw_inputs.sleep.in_bed_minutes,
        "deep_sleep_minutes": state.raw_inputs.sleep.deep_sleep_minutes,
        "rem_sleep_minutes": state.raw_inputs.sleep.rem_sleep_minutes,
        "sleep_duration_hours": recovery_updates.get("sleep_duration_hours"),
        "sleep_efficiency": recovery_updates.get("sleep_efficiency"),
        "restorative_ratio": recovery_updates.get("sleep_restorative_ratio"),
    }
    css_result = compute_css(css_input)
    if css_result.get("status") == "ok":
        recovery_updates["css_score"] = css_result.get("daily_CSS")
    else:
        recovery_updates["css_score"] = None

    state.metrics.recovery = _model_copy(state.metrics.recovery, recovery_updates)


def populate_physiology_metrics(
    state: ReadinessState,
    *,
    hrv_mu: Optional[float] = None,
    hrv_sigma: Optional[float] = None,
) -> None:
    baseline_updates: Dict[str, Any] = {}
    if hrv_mu is not None:
        baseline_updates["hrv_mu"] = hrv_mu
    if hrv_sigma is not None:
        baseline_updates["hrv_sigma"] = hrv_sigma
    if baseline_updates:
        state.metrics.baselines = _model_copy(state.metrics.baselines, baseline_updates)
    today = state.raw_inputs.hrv.hrv_rmssd_today
    mu = state.metrics.baselines.hrv_mu
    sigma = state.metrics.baselines.hrv_sigma
    physiology_updates: Dict[str, Any] = {
        "hrv_z_score": None,
        "hrv_trend": None,
        "hrv_state": None,
    }
    if today is not None and mu is not None and sigma and sigma > 1e-6:
        z = (today - mu) / sigma
        physiology_updates["hrv_z_score"] = round(z, 3)
        if z >= 0.5:
            physiology_updates["hrv_trend"] = "rising"
        elif z <= -1.5:
            physiology_updates["hrv_trend"] = "significant_decline"
        elif z <= -0.5:
            physiology_updates["hrv_trend"] = "slight_decline"
        else:
            physiology_updates["hrv_trend"] = "stable"
    physiology_updates["hrv_state"] = physiology_updates.get("hrv_trend")
    state.metrics.physiology = _model_copy(
        state.metrics.physiology, physiology_updates
    )


def populate_subjective_metrics(
    state: ReadinessState,
    *,
    doms_slider_key: str = "fatigue_slider",
    energy_slider_key: str = "mood_slider",
) -> None:
    hooper = state.raw_inputs.hooper
    bands = {}
    for key, val in [
        ("fatigue", hooper.fatigue),
        ("soreness", hooper.soreness),
        ("stress", hooper.stress),
        ("sleep", hooper.sleep),
    ]:
        if val is None:
            continue
        if val <= 2:
            bands[key] = "low"
        elif val <= 4:
            bands[key] = "medium"
        else:
            bands[key] = "high"
    subjective_updates: Dict[str, Any] = {}
    if bands:
        subjective_updates["hooper_bands"] = bands
    sliders = state.raw_inputs.journal.sliders or {}
    doms_score = sliders.get(doms_slider_key)
    energy_score = sliders.get(energy_slider_key)
    if doms_score is not None:
        subjective_updates["doms_score"] = doms_score
    if energy_score is not None:
        subjective_updates["energy_score"] = energy_score
    # 计算综合疲劳指标（沿用 readiness.engine 的简化版本）
    daily_au_7d = state.metrics.training_load.daily_au_7d or []
    if daily_au_7d:
        last3 = daily_au_7d[-3:]
        avg3 = mean(last3) if last3 else 0.0
    else:
        avg3 = 0.0
    au_norm = 2000.0
    if state.metrics.baselines.personalized_thresholds.get("au_norm"):
        au_norm = state.metrics.baselines.personalized_thresholds["au_norm"]
    normalized_load = max(0.0, min(10.0, (avg3 / max(au_norm, 1e-6)) * 10.0))
    doms_v = max(0.0, min(10.0, float(doms_score) if doms_score is not None else 0.0))
    energy_v = max(
        0.0, min(10.0, 10.0 - float(energy_score)) if energy_score is not None else 3.0
    )
    fatigue_score = 0.4 * normalized_load + 0.4 * doms_v + 0.2 * energy_v
    subjective_updates["fatigue_score"] = round(fatigue_score, 2)

    state.metrics.subjective = _model_copy(
        state.metrics.subjective, subjective_updates
    )


def populate_baseline_metrics(
    state: ReadinessState,
    *,
    sleep_baseline_hours: Optional[float] = None,
    sleep_baseline_eff: Optional[float] = None,
    rest_baseline_ratio: Optional[float] = None,
    hrv_mu: Optional[float] = None,
    hrv_sigma: Optional[float] = None,
    personalized_thresholds: Optional[Dict[str, float]] = None,
) -> None:
    baseline_updates: Dict[str, Any] = {}
    if sleep_baseline_hours is not None:
        baseline_updates["sleep_baseline_hours"] = sleep_baseline_hours
    if sleep_baseline_eff is not None:
        baseline_updates["sleep_baseline_efficiency"] = sleep_baseline_eff
    if rest_baseline_ratio is not None:
        baseline_updates["rest_baseline_ratio"] = rest_baseline_ratio
    if hrv_mu is not None:
        baseline_updates["hrv_mu"] = hrv_mu
    if hrv_sigma is not None:
        baseline_updates["hrv_sigma"] = hrv_sigma
    if personalized_thresholds:
        merged = dict(state.metrics.baselines.personalized_thresholds)
        merged.update(personalized_thresholds)
        baseline_updates["personalized_thresholds"] = merged
    if baseline_updates:
        state.metrics.baselines = _model_copy(state.metrics.baselines, baseline_updates)


def populate_metrics(
    state: ReadinessState,
    *,
    recent_training_au: Optional[Sequence[float]] = None,
    recent_training_loads: Optional[Sequence[str]] = None,
    baselines: Optional[Dict[str, float]] = None,
    personalized_thresholds: Optional[Dict[str, float]] = None,
) -> ReadinessState:
    """Populate deterministic metrics into the provided state.

    This function is pure and does not touch database or existing APIs.
    """
    populate_baseline_metrics(
        state,
        sleep_baseline_hours=(baselines or {}).get("sleep_baseline_hours"),
        sleep_baseline_eff=(baselines or {}).get("sleep_baseline_eff"),
        rest_baseline_ratio=(baselines or {}).get("rest_baseline_ratio"),
        hrv_mu=(baselines or {}).get("hrv_baseline_mu"),
        hrv_sigma=(baselines or {}).get("hrv_baseline_sd"),
        personalized_thresholds=personalized_thresholds,
    )
    populate_training_metrics(
        state,
        recent_training_au=recent_training_au,
        recent_training_loads=recent_training_loads,
        personalized_thresholds=personalized_thresholds,
    )
    populate_recovery_metrics(state)
    populate_physiology_metrics(
        state,
        hrv_mu=state.metrics.baselines.hrv_mu,
        hrv_sigma=state.metrics.baselines.hrv_sigma,
    )
    populate_subjective_metrics(state)
    return state


__all__ = ["populate_metrics"]
