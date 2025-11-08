from __future__ import annotations

from typing import Any, Dict, Optional


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def compute_sleep_metrics(data: Dict[str, Any], *, decimals: int = 4) -> Dict[str, Optional[float]]:
    """Return only two numeric values needed by your pipeline.

    Inputs (use minutes; only the following keys are needed):
      - total_sleep_minutes: total minutes actually asleep
      - in_bed_minutes (or time_in_bed_minutes): minutes in bed
      - deep_sleep_minutes: minutes of deep sleep
      - rem_sleep_minutes: minutes of REM sleep

    Output:
      - sleep_efficiency: fraction in [0,1]
      - sleep_efficiency_pct: percentage in [0,100]
      - restorative_ratio: (deep + rem) / total, fraction in [0,1]
    """
    t = _to_float(
        data.get('total_sleep_minutes')
        if data.get('total_sleep_minutes') is not None
        else data.get('sleep_minutes')
    )
    in_bed = _to_float(data.get('in_bed_minutes') or data.get('time_in_bed_minutes'))
    deep = _to_float(data.get('deep_sleep_minutes'))
    rem = _to_float(data.get('rem_sleep_minutes'))

    # sleep efficiency
    eff: Optional[float]
    if t is None or in_bed is None or in_bed <= 0:
        eff = None
    else:
        eff = max(0.0, min(1.0, t / in_bed))

    # restorative ratio
    rr: Optional[float]
    if t is None or t <= 0 or deep is None or rem is None:
        rr = None
    else:
        rr = max(0.0, min(1.0, (deep + rem) / t))

    def rnd(x: Optional[float]) -> Optional[float]:
        return round(x, decimals) if x is not None else None

    return {
        'sleep_efficiency': rnd(eff),
        'sleep_efficiency_pct': rnd(eff * 100.0) if eff is not None else None,
        'restorative_ratio': rnd(rr),
    }


__all__ = ['compute_sleep_metrics']

