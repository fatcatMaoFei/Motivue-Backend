from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from pydantic import ValidationError

from weekly_report.state import (
    ReadinessState,
    TrainingSessionInput,
)
from weekly_report.state_utils import create_state, state_to_json
from weekly_report.metrics_extractors import populate_metrics
from weekly_report.insights import populate_insights


def _get(payload: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _copy_update(model, updates: Dict[str, Any]):
    if not updates:
        return model
    return model.model_copy(update=updates)


def hydrate_sleep(state: ReadinessState, payload: Dict[str, Any]) -> None:
    sleep_updates = {
        "total_sleep_minutes": _get(payload, "total_sleep_minutes", "sleep_minutes"),
        "in_bed_minutes": _get(payload, "in_bed_minutes", "time_in_bed_minutes"),
        "deep_sleep_minutes": payload.get("deep_sleep_minutes"),
        "rem_sleep_minutes": payload.get("rem_sleep_minutes"),
        "core_sleep_minutes": payload.get("core_sleep_minutes"),
        "sleep_efficiency_score": payload.get("apple_sleep_score"),
    }
    state.raw_inputs.sleep = _copy_update(state.raw_inputs.sleep, sleep_updates)


def hydrate_hrv(state: ReadinessState, payload: Dict[str, Any]) -> None:
    hrv_updates = {
        "hrv_rmssd_today": payload.get("hrv_rmssd_today"),
        "hrv_rmssd_3day_avg": payload.get("hrv_rmssd_3day_avg"),
        "hrv_rmssd_7day_avg": payload.get("hrv_rmssd_7day_avg"),
        "hrv_rmssd_28day_avg": payload.get("hrv_rmssd_28day_avg"),
        "hrv_rmssd_28day_sd": payload.get("hrv_rmssd_28day_sd"),
        "device": payload.get("hrv_device"),
    }
    state.raw_inputs.hrv = _copy_update(state.raw_inputs.hrv, hrv_updates)


def hydrate_training_sessions(
    state: ReadinessState, sessions: Optional[Iterable[Dict[str, Any]]]
) -> None:
    if not sessions:
        return
    parsed: List[TrainingSessionInput] = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        try:
            parsed.append(
                TrainingSessionInput.model_validate(
                    {
                        "label": s.get("label"),
                        "rpe": s.get("rpe"),
                        "duration_minutes": s.get("duration_minutes"),
                        "au": s.get("au"),
                        "start_time": s.get("start_time"),
                        "notes": s.get("notes"),
                    }
                )
            )
        except ValidationError:
            continue
    if parsed:
        state.raw_inputs.training_sessions = parsed


def hydrate_hooper(state: ReadinessState, payload: Dict[str, Any]) -> None:
    hooper_payload = payload.get("hooper") or {}
    hooper_updates = {
        "fatigue": hooper_payload.get("fatigue"),
        "soreness": hooper_payload.get("soreness"),
        "stress": hooper_payload.get("stress"),
        "sleep": hooper_payload.get("sleep"),
    }
    state.raw_inputs.hooper = _copy_update(state.raw_inputs.hooper, hooper_updates)


def hydrate_journal(state: ReadinessState, payload: Dict[str, Any]) -> None:
    journal_payload = payload.get("journal") or {}
    journal_updates = {
        "alcohol_consumed": journal_payload.get("alcohol_consumed"),
        "late_caffeine": journal_payload.get("late_caffeine"),
        "screen_before_bed": journal_payload.get("screen_before_bed"),
        "late_meal": journal_payload.get("late_meal"),
        "is_sick": journal_payload.get("is_sick"),
        "is_injured": journal_payload.get("is_injured"),
    }
    if isinstance(journal_payload.get("lifestyle_tags"), (list, tuple)):
        journal_updates["lifestyle_tags"] = list(journal_payload["lifestyle_tags"])
    if isinstance(journal_payload.get("sliders"), dict):
        journal_updates["sliders"] = dict(journal_payload["sliders"])
    state.raw_inputs.journal = _copy_update(state.raw_inputs.journal, journal_updates)


def hydrate_body_metrics(state: ReadinessState, payload: Dict[str, Any]) -> None:
    bm_updates = {
        "bodyweight_kg": payload.get("bodyweight_kg") or payload.get("bodyweight"),
        "bodyfat_pct": payload.get("bodyfat_pct"),
        "resting_hr": payload.get("resting_hr"),
    }
    state.raw_inputs.body_metrics = _copy_update(state.raw_inputs.body_metrics, bm_updates)


def hydrate_raw_inputs(
    state: ReadinessState,
    payload: Dict[str, Any],
    training_sessions: Optional[Iterable[Dict[str, Any]]] = None,
) -> None:
    """Populate raw_inputs on the provided state (ingestion stage)."""
    hydrate_sleep(state, payload)
    hydrate_hrv(state, payload)
    hydrate_training_sessions(
        state,
        training_sessions or payload.get("training_sessions"),
    )
    hydrate_hooper(state, payload)
    hydrate_journal(state, payload)
    hydrate_body_metrics(state, payload)
    if isinstance(payload.get("external_events"), (list, tuple)):
        state.raw_inputs.external_events = list(payload["external_events"])
    if payload.get("report_notes") is not None:
        state.raw_inputs.report_notes = str(payload["report_notes"])


def build_state_from_payload(
    payload: Dict[str, Any],
    *,
    baselines: Optional[Dict[str, float]] = None,
    personalized_thresholds: Optional[Dict[str, float]] = None,
    recent_training_au: Optional[Sequence[float]] = None,
    recent_training_loads: Optional[Sequence[str]] = None,
    training_sessions: Optional[Iterable[Dict[str, Any]]] = None,
    auto_generate_insights: bool = True,
) -> ReadinessState:
    """Build a ReadinessState from an existing readiness payload.

    This helper does not mutate database or change API behaviour: it merely
    organizes the data into the new unified structure.
    """
    state = create_state(
        user_id=payload.get("user_id"),
        date=payload.get("date"),
        gender=payload.get("gender"),
    )

    # Raw inputs
    hydrate_raw_inputs(state, payload, training_sessions)

    # Deterministic metrics
    populate_metrics(
        state,
        recent_training_au=recent_training_au or payload.get("recent_training_au"),
        recent_training_loads=recent_training_loads
        or payload.get("recent_training_loads"),
        baselines=baselines
        or {
            "sleep_baseline_hours": payload.get("sleep_baseline_hours"),
            "sleep_baseline_eff": payload.get("sleep_baseline_eff"),
            "rest_baseline_ratio": payload.get("rest_baseline_ratio"),
            "hrv_baseline_mu": payload.get("hrv_baseline_mu"),
            "hrv_baseline_sd": payload.get("hrv_baseline_sd"),
        },
        personalized_thresholds=personalized_thresholds
        or payload.get("personalized_thresholds"),
    )

    if auto_generate_insights:
        populate_insights(state)

    return state


def build_state_json(
    payload: Dict[str, Any],
    **kwargs: Any,
) -> str:
    """Convenience wrapper to directly obtain JSON from payload."""
    state = build_state_from_payload(payload, **kwargs)
    return state_to_json(state, indent=2)


__all__ = [
    "build_state_from_payload",
    "build_state_json",
    "hydrate_raw_inputs",
    "hydrate_sleep",
    "hydrate_hrv",
    "hydrate_training_sessions",
    "hydrate_hooper",
    "hydrate_journal",
    "hydrate_body_metrics",
]
