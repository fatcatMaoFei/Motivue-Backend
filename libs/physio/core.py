from __future__ import annotations

from typing import Any, Dict, List

from .css import compute_css


def _mean(xs: List[float]) -> float:
    return sum(xs) / max(1, len(xs))


def compute_physiological_age(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight physiological-age estimate from SDNN/RHR series + daily CSS.

    This implementation provides a minimal, self-contained computation so the
    physio-age feature can run without external reference tables. It uses:
      - SDNN (higher is better)
      - RHR (lower is better)
      - CSS (higher is better)

    Returns a dict with fields similar to the original API contract.
    """
    sdnn_series = payload.get("sdnn_series") or []
    rhr_series = payload.get("rhr_series") or []
    if not isinstance(sdnn_series, list) or not isinstance(rhr_series, list):
        return {"status": "error", "message": "invalid series"}
    if len(sdnn_series) < 30 or len(rhr_series) < 30:
        return {"status": "error", "message": "need >=30 samples for sdnn/rhr"}

    try:
        sdnn = [float(x) for x in sdnn_series if x is not None]
        rhr = [float(x) for x in rhr_series if x is not None]
    except Exception:
        return {"status": "error", "message": "non-numeric values in series"}

    sdnn_mean = _mean(sdnn)
    rhr_mean = _mean(rhr)

    # Daily CSS from sleep payload (if provided)
    css_payload_keys = [
        "sleep_duration_hours",
        "total_sleep_minutes",
        "in_bed_minutes",
        "deep_sleep_minutes",
        "rem_sleep_minutes",
        "sleep_efficiency",
        "restorative_ratio",
        "deep_sleep_ratio",
        "rem_sleep_ratio",
    ]
    css_input = {k: payload.get(k) for k in css_payload_keys if k in payload}
    css_res = compute_css(css_input) if css_input else {"status": "partial", "daily_CSS": None}
    css_value = css_res.get("daily_CSS")

    # Simple z-like normalisation around broadly typical values
    # These anchors are approximate and only to keep the output stable.
    sdnn_anchor, sdnn_scale = 50.0, 20.0
    rhr_anchor, rhr_scale = 60.0, 10.0

    sdnn_z = (sdnn_mean - sdnn_anchor) / sdnn_scale
    rhr_z = (rhr_anchor - rhr_mean) / rhr_scale  # lower RHR is better
    css_z = ((css_value or 70.0) - 70.0) / 15.0  # around 70 ± 15

    # Blend into an age estimate (18..80) where higher SDNN/CSS and lower RHR
    # drive younger physiological age.
    base_age = 35.0
    age_adjust = -8.0 * sdnn_z + -5.0 * css_z + -6.0 * rhr_z
    phys_age = max(18.0, min(80.0, base_age + age_adjust))

    # Soft weighting (soft-min like) with small temperature
    phys_age_weighted = max(18.0, min(80.0, 0.7 * phys_age + 0.3 * base_age))

    return {
        "status": "ok",
        "physiological_age": round(phys_age),
        "physiological_age_weighted": round(phys_age_weighted, 1),
        "css_details": css_res,
        "best_age_zscores": {
            "sdnn_z": round(sdnn_z, 2),
            "rhr_z": round(rhr_z, 2),
            "css_z": round(css_z, 2),
        },
        "window_days_used": max(len(sdnn), len(rhr)),
        "data_days_count": {"sdnn": len(sdnn), "rhr": len(rhr)},
    }


__all__ = ["compute_physiological_age"]

