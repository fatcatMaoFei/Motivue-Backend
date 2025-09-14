from __future__ import annotations

from typing import Any, Dict, List, Optional

from .utils import mean, pct_change, last_n, normalize_ratio, direction_flags


MetricKeyMap = {
    # canonical -> accepted aliases in payload
    'sleep_hours': ['sleep_hours', 'sleep_duration_hours'],
    'sleep_eff': ['sleep_eff', 'sleep_efficiency'],
    'rest_ratio': ['rest_ratio', 'restorative_ratio'],
    'hrv_rmssd': ['hrv', 'hrv_rmssd'],
    'training_au': ['training_au'],
}


def _get_series(payload: Dict[str, Any], key: str) -> Optional[List[float]]:
    aliases = MetricKeyMap.get(key, [key])
    for k in aliases:
        v = payload.get(k)
        if isinstance(v, list):
            # normalize entries
            out: List[float] = []
            for x in v:
                if x is None:
                    continue
                try:
                    out.append(float(x))
                except Exception:
                    continue
            return out if out else None
    return None


def _baseline_avg(series: List[float], window: int) -> Optional[float]:
    # exclude today (last value)
    if len(series) < window + 1:
        return None
    return mean(series[-(window+1):-1])


def compare_today_vs_baseline(
    payload: Dict[str, Any],
    *,
    windows: List[int] | None = None,
    tol_pct: float = 1.0,
    baseline_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Today vs N-day window baseline for key metrics.

    Inputs (lists of daily values; last element = today):
      - sleep_hours | sleep_duration_hours
      - sleep_eff | sleep_efficiency (0..1 or 0..100)
      - rest_ratio | restorative_ratio (0..1)
      - hrv_rmssd | hrv
      - training_au

    Returns a dict per metric with window comparisons under 'windows'. If
    baseline_overrides provided (e.g., from global baseline), an additional
    'override' entry is included with today vs override-baseline comparison.
    """
    wins = windows or [7, 28, 56]
    result: Dict[str, Any] = {}

    # collect series
    sh = _get_series(payload, 'sleep_hours')
    se = _get_series(payload, 'sleep_eff')
    rr = _get_series(payload, 'rest_ratio')
    hr = _get_series(payload, 'hrv_rmssd')
    au = _get_series(payload, 'training_au')

    # normalize ratio-like series
    if se:
        se = [normalize_ratio(x) for x in se]
    if rr:
        rr = [normalize_ratio(x) for x in rr]

    overrides = baseline_overrides or {}

    def _compare(series: Optional[List[float]], metric: str) -> Dict[str, Any]:
        out_windows: Dict[int, Any] = {}
        out: Dict[str, Any] = { 'windows': out_windows }
        if not series:
            return out
        today = series[-1]
        for w in wins:
            b = _baseline_avg(series, w)
            p = pct_change(today, b)
            out_windows[w] = {
                'today': today,
                'baseline_avg': b,
                'pct_change': p,
                **direction_flags(p, tol=tol_pct),
                'window': w,
            }
        if metric in overrides and overrides[metric] is not None:
            ov = float(overrides[metric])
            p2 = pct_change(today, ov)
            out['override'] = {
                'today': today,
                'baseline': ov,
                'pct_change': p2,
                **direction_flags(p2, tol=tol_pct),
            }
        return out

    if sh:
        result['sleep_hours'] = _compare(sh, 'sleep_hours')
    if se:
        result['sleep_eff'] = _compare(se, 'sleep_eff')
    if rr:
        result['rest_ratio'] = _compare(rr, 'rest_ratio')
    if hr:
        result['hrv_rmssd'] = _compare(hr, 'hrv_rmssd')
    if au:
        result['training_au'] = _compare(au, 'training_au')

    return result


__all__ = ['compare_today_vs_baseline']
