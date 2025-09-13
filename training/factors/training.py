#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Tuple

from readiness.constants import TRAINING_LOAD_AU


def _au_from_session(session: Dict) -> Tuple[float, str | None]:
    """Return (au, label_used). Prefer RPE×minutes; else label→AU; else au.
    Label is returned only for record; RPE is the primary source when present.
    """
    rpe = session.get("rpe")
    dur = session.get("duration_minutes")
    if isinstance(rpe, int) and isinstance(dur, int) and rpe > 0 and dur > 0:
        return float(rpe * dur), session.get("label")
    label = session.get("label")
    if isinstance(label, str) and label in TRAINING_LOAD_AU:
        return float(TRAINING_LOAD_AU[label]), label
    au = session.get("au")
    try:
        if au is not None:
            return float(au), label
    except Exception:
        pass
    return 0.0, label


def _g_piecewise(au: float) -> float:
    """Piecewise minutes-based mapping to consumption points (0..40).
    - AU ≤ 150 → 0
    - 150..300 → 0..10
    - 300..500 → 10..25
    - >500     → 25..40 (saturates at 900)
    """
    if au <= 150:
        return 0.0
    if au <= 300:
        return 10.0 * (au - 150.0) / 150.0
    if au <= 500:
        return 10.0 + 15.0 * (au - 300.0) / 200.0
    # cap at +40 around 900 AU
    extra = min(1.0, (au - 500.0) / 400.0)
    return 25.0 + 15.0 * extra


def compute_training_consumption(
    sessions: List[Dict],
    readiness_score: int | None = None,
    cap_session: float = 40.0,
    cap_training_total: float = 60.0,
) -> Tuple[float, List[Dict]]:
    """Compute training consumption for today's sessions.

    - readiness_score is reserved for future scaling; v1 not used.
    - Returns (total_consumption, session_results)
    """
    results: List[Dict] = []
    total = 0.0
    for s in sessions or []:
        au, label_used = _au_from_session(s)
        delta = min(cap_session, _g_piecewise(max(0.0, au)))
        total += delta
        results.append({
            "session_id": s.get("session_id"),
            "au_used": float(au),
            "label_used": label_used,
            "delta_consumption": float(delta),
        })
    total = min(cap_training_total, total)
    return float(total), results

