from __future__ import annotations

from typing import Any, Dict, Optional

try:
    # Prefer backend implementation to keep one source of truth
    from backend.utils.sleep_metrics import compute_sleep_metrics as _backend_sleep_metrics  # type: ignore
except Exception:  # pragma: no cover
    _backend_sleep_metrics = None  # fallback to local logic


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _efficiency(payload: Dict[str, Any]) -> Optional[float]:
    # First try backend sleep_metrics for consistency across services
    if _backend_sleep_metrics is not None:
        try:
            m = _backend_sleep_metrics(payload)
            eff = m.get('sleep_efficiency')
            if eff is not None:
                return _clamp01(float(eff))
        except Exception:
            pass
    eff = _to_float(payload.get('sleep_efficiency'))
    if eff is not None:
        if eff > 1.0:
            eff /= 100.0
        return _clamp01(eff)
    # compute from minutes if available
    total = _to_float(payload.get('total_sleep_minutes'))
    in_bed = _to_float(payload.get('in_bed_minutes') or payload.get('time_in_bed_minutes'))
    if total is None or in_bed is None or in_bed <= 0:
        return None
    return _clamp01(total / in_bed)


def _duration_hours(payload: Dict[str, Any]) -> Optional[float]:
    dur_h = _to_float(payload.get('sleep_duration_hours'))
    if dur_h is not None:
        return dur_h
    total = _to_float(payload.get('total_sleep_minutes'))
    if total is not None:
        return total / 60.0
    return None


def _restorative_ratio(payload: Dict[str, Any]) -> Optional[float]:
    # First try backend sleep_metrics for consistency across services
    if _backend_sleep_metrics is not None:
        try:
            m = _backend_sleep_metrics(payload)
            rr = m.get('restorative_ratio')
            if rr is not None:
                return _clamp01(float(rr))
        except Exception:
            pass
    rr = _to_float(payload.get('restorative_ratio'))
    if rr is not None:
        return _clamp01(rr)
    deep_r = _to_float(payload.get('deep_sleep_ratio'))
    rem_r = _to_float(payload.get('rem_sleep_ratio'))
    if deep_r is not None and rem_r is not None:
        return _clamp01(deep_r + rem_r)
    # minutes fallback
    deep_m = _to_float(payload.get('deep_sleep_minutes'))
    rem_m = _to_float(payload.get('rem_sleep_minutes'))
    total_m = _to_float(payload.get('total_sleep_minutes'))
    if deep_m is not None and rem_m is not None and total_m and total_m > 0:
        return _clamp01((deep_m + rem_m) / total_m)
    return None


def _duration_score(hours: float) -> float:
    if hours < 4.0:
        return 0.0
    if hours < 7.0:
        return ((hours - 4.0) / 3.0) * 100.0
    if hours <= 9.0:
        return 100.0
    if hours <= 11.0:
        return 100.0 - ((hours - 9.0) / 2.0) * 50.0
    return 50.0


def _efficiency_score(eff: float) -> float:
    # eff in 0..1
    if eff < 0.75:
        return 0.0
    if eff < 0.85:
        return ((eff - 0.75) / 0.10) * 80.0
    if eff <= 0.95:
        return 80.0 + ((eff - 0.85) / 0.10) * 20.0
    return 100.0


def _restorative_score(ratio: float) -> float:
    if ratio < 0.20:
        return 0.0
    if ratio < 0.35:
        return ((ratio - 0.20) / 0.15) * 100.0
    if ratio <= 0.55:
        return 100.0
    # Above 0.55: decrease from 100 toward 80, floor at 80
    val = 100.0 - ((ratio - 0.55) / 0.10) * 20.0
    return max(80.0, val)


def compute_css(payload: Dict[str, Any], *, weights: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Compute a composite sleep score (CSS) from daily sleep signals.

    Inputs (same naming as other modules):
      - sleep_duration_hours OR total_sleep_minutes
      - sleep_efficiency (0..1 or 0..100) OR total_sleep_minutes + in_bed_minutes
      - restorative_ratio (0..1) OR deep_sleep_ratio+rem_sleep_ratio OR minutes fallback

    Scoring:
      - restorative_ratio: 0.25..0.35 → 0..100
      - sleep_efficiency:  0.75..0.85 → 0..100
      - sleep_duration_h:  6.0..8.0  → 0..100
      - CSS = 0.50*rest + 0.30*eff + 0.20*dur
    """
    # Default weights per updated spec: duration 0.4, efficiency 0.3, restorative 0.3
    wd = 0.40
    we = 0.30
    wr = 0.30
    if isinstance(weights, dict):
        wd = float(weights.get('duration', wd))
        we = float(weights.get('efficiency', we))
        wr = float(weights.get('restorative', wr))
        s = wr + we + wd
        if s > 0:
            wr, we, wd = wr / s, we / s, wd / s

    rr = _restorative_ratio(payload)
    ef = _efficiency(payload)
    dh = _duration_hours(payload)

    # Component scores
    rr_score = _restorative_score(rr) if rr is not None else None
    ef_score = _efficiency_score(ef) if ef is not None else None
    dh_score = _duration_score(dh) if dh is not None else None

    # CSS requires all three; if missing, return partial info
    if rr_score is None or ef_score is None or dh_score is None:
        return {
            'status': 'partial',
            'components': {
                'restorative_score': rr_score,
                'efficiency_score': ef_score,
                'duration_score': dh_score,
            },
            'daily_CSS': None,
        }

    css = wd * dh_score + we * ef_score + wr * rr_score
    return {
        'status': 'ok',
        'daily_CSS': round(css, 1),
        'components': {
            'restorative_score': round(rr_score, 1),
            'efficiency_score': round(ef_score, 1),
            'duration_score': round(dh_score, 1),
        },
        'weights_used': {'restorative': wr, 'efficiency': we, 'duration': wd},
    }


__all__ = ['compute_css']
