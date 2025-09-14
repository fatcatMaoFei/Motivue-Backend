from __future__ import annotations

from typing import Any, Dict, List, Optional

from .utils import mean, last_n, pct_change, normalize_ratio, direction_flags


MetricKeyMap = {
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


def _recent_vs_previous(series: List[float], window: int) -> Dict[str, Optional[float]]:
    if not series:
        return {'last_avg': None, 'prev_avg': None, 'pct_change': None}
    last = last_n(series, window)
    prev = series[-2*window:-window] if len(series) >= 2*window else []
    last_avg = mean(last)
    prev_avg = mean(prev) if prev else None
    return {
        'last_avg': last_avg,
        'prev_avg': prev_avg,
        'pct_change': pct_change(last_avg, prev_avg),
    }


def compare_recent_vs_previous(
    payload: Dict[str, Any],
    *,
    windows: List[int] | None = None,
    tol_pct: float = 1.0,
    compare_window_map: Optional[Dict[int, int]] = None,
    baseline_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Recent N vs previous N for key metrics.

    Inputs: same as daily_vs_baseline; arrays ordered by day.
    Returns per-metric dict mapping window->result with direction flags.
    """
    wins = windows or [7, 28, 56]
    cmp_map = compare_window_map or {}
    overrides = baseline_overrides or {}
    result: Dict[str, Any] = {}

    sh = _get_series(payload, 'sleep_hours')
    se = _get_series(payload, 'sleep_eff')
    rr = _get_series(payload, 'rest_ratio')
    hr = _get_series(payload, 'hrv_rmssd')
    au = _get_series(payload, 'training_au')

    if se:
        se = [normalize_ratio(x) for x in se]
    if rr:
        rr = [normalize_ratio(x) for x in rr]

    def _cmp(series: Optional[List[float]], metric: str) -> Dict[str, Any]:
        out_windows: Dict[int, Any] = {}
        out: Dict[str, Any] = { 'windows': out_windows }
        if not series:
            return out
        for w in wins:
            cmp_w = int(cmp_map.get(w, w))
            if len(series) >= w + cmp_w:
                last = last_n(series, w)
                prev = series[-(w+cmp_w):-w]
                last_avg = mean(last)
                prev_avg = mean(prev)
                p = pct_change(last_avg, prev_avg)
            else:
                last_avg = mean(last_n(series, w))
                prev_avg = None
                p = None
            out_windows[w] = {
                'last_avg': last_avg,
                'prev_avg': prev_avg,
                'pct_change': p,
                **direction_flags(p, tol=tol_pct),
                'window': w,
                'compare_window': cmp_w,
            }
        # optional override vs last_avg
        if metric in overrides and overrides[metric] is not None:
            ov = float(overrides[metric])
            last_avg7 = mean(last_n(series, wins[0])) if series else None
            p2 = pct_change(last_avg7, ov)
            out['override'] = {
                'last_avg': last_avg7,
                'baseline': ov,
                'pct_change': p2,
                **direction_flags(p2, tol=tol_pct),
                'window': wins[0],
            }
        return out

    if sh:
        result['sleep_hours'] = _cmp(sh, 'sleep_hours')
    if se:
        result['sleep_eff'] = _cmp(se, 'sleep_eff')
    if rr:
        result['rest_ratio'] = _cmp(rr, 'rest_ratio')
    if hr:
        result['hrv_rmssd'] = _cmp(hr, 'hrv_rmssd')
    if au:
        result['training_au'] = _cmp(au, 'training_au')

    return result


__all__ = ['compare_recent_vs_previous']
