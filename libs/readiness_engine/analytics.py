"""Retrospective analytics for Journal items and metrics.

This module provides simple helpers to compute naive effects of a boolean
journal item on a numeric metric (e.g., HRV) with an optional lag (e.g.,
"yesterday Alcohol=True" vs today's HRV).

Note: In production, it's recommended to pull data from your database into a
DataFrame and run more robust statistical analyses. These helpers are minimal
and operate on the in-memory JournalManager for demonstration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from readiness.engine import JournalManager


def _to_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def _date_add(s: str, days: int) -> str:
    return (_to_date(s) + timedelta(days=days)).strftime('%Y-%m-%d')


def effect_of_journal_on_metric(
    jm: JournalManager,
    user_id: str,
    item_key: str,
    metric_key: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lag_days: int = 1,
) -> Dict[str, Any]:
    """Compute naive effect: compare metric on days after item=True vs others.

    - item_key: e.g., 'Alcohol' (if you mapped WHOOP Journal to 'whoop_journal' dict)
    - metric_key: e.g., 'hrv_rmssd' or 'hrv_value' you stored under 'daily_metrics'
    - lag_days: typically 1 (yesterday's item -> today's metric)
    """
    data = jm.journal_database
    # Collect dates for this user
    entries = [(k.split('_', 1)[1], v) for k, v in data.items() if k.startswith(user_id + '_')]
    if not entries:
        return {'n_after': 0, 'n_other': 0, 'mean_after': None, 'mean_other': None, 'pct_diff': None}

    # Apply date filter
    if start_date:
        sdt = _to_date(start_date)
        entries = [(d, v) for d, v in entries if _to_date(d) >= sdt]
    if end_date:
        edt = _to_date(end_date)
        entries = [(d, v) for d, v in entries if _to_date(d) <= edt]

    # Build maps: item_by_date, metric_by_date
    item_by_date: Dict[str, bool] = {}
    metric_by_date: Dict[str, float] = {}
    for d, v in entries:
        item_val = bool(v.get('whoop_journal', {}).get(item_key, False))
        met = v.get('daily_metrics', {}).get(metric_key)
        if met is not None:
            try:
                metric_by_date[d] = float(met)
            except Exception:
                pass
        item_by_date[d] = item_val

    # Compare metric on day t given item on day t-lag
    after_vals: List[float] = []
    other_vals: List[float] = []
    for d in metric_by_date:
        prev = _date_add(d, -lag_days)
        flag = item_by_date.get(prev, False)
        (after_vals if flag else other_vals).append(metric_by_date[d])

    def _mean(xs: List[float]) -> Optional[float]:
        return sum(xs) / len(xs) if xs else None

    mean_after = _mean(after_vals)
    mean_other = _mean(other_vals)
    pct_diff = None
    if mean_after is not None and mean_other is not None and mean_other != 0:
        pct_diff = (mean_after - mean_other) / abs(mean_other) * 100.0

    return {
        'n_after': len(after_vals),
        'n_other': len(other_vals),
        'mean_after': mean_after,
        'mean_other': mean_other,
        'pct_diff': pct_diff,
    }


__all__ = ['effect_of_journal_on_metric']

