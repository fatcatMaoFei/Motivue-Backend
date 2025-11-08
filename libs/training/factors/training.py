#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Tuple

from readiness.constants import TRAINING_LOAD_AU


def _au_from_session(session: Dict) -> Tuple[float, str | None]:
    """Return (au, label_used). Prefer RPE脳minutes; else label鈫扐U; else au.
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
    杞昏礋鑽蜂篃鏈夊皬棰濇墸鍒嗭紝鏁翠綋鍧″害娓╁拰锛?    - 0..150   鈫?0..5
    - 150..300 鈫?5..12
    - 300..500 鈫?12..25
    - >500     鈫?25..40锛堢害鍦?900 楗卞拰锛?    """
    if au <= 0:
        return 0.0
    if au <= 150:
        return 5.0 * (au / 150.0)
    if au <= 300:
        return 5.0 + 7.0 * ((au - 150.0) / 150.0)
    if au <= 500:
        return 12.0 + 13.0 * ((au - 300.0) / 200.0)
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
