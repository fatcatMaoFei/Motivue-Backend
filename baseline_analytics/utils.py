from __future__ import annotations

from typing import List, Optional


def mean(xs: List[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def pct_change(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old) * 100.0


def last_n(xs: List[float], n: int) -> List[float]:
    return xs[-n:] if xs and len(xs) >= n else (xs or [])


def normalize_ratio(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    v = float(x)
    if v > 1.0:
        v /= 100.0
    if v < 0.0:
        v = 0.0
    if v > 1.0:
        v = 1.0
    return v


def direction_flags(pct: Optional[float], tol: float = 1.0) -> dict:
    """Return direction flags and label based on % change and tolerance.

    - tol: absolute percent within which counts as 'flat'.
    """
    if pct is None:
        return {"is_up": None, "is_down": None, "is_flat": None, "direction": None}
    if abs(pct) < tol:
        return {"is_up": False, "is_down": False, "is_flat": True, "direction": "flat"}
    if pct > 0:
        return {"is_up": True, "is_down": False, "is_flat": False, "direction": "up"}
    return {"is_up": False, "is_down": True, "is_flat": False, "direction": "down"}

