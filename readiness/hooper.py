#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from readiness.constants import EMISSION_CPT


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def _bernstein_w(t: float) -> Dict[str, float]:
    """Quadratic Bernstein (Bezier) weights for low/medium/high anchors.
    - t in [0,1], 0=best(closer to low anchor), 1=worst(closer to high anchor).
    """
    t = max(0.0, min(1.0, float(t)))
    w_low = (1.0 - t) ** 2
    w_med = 2.0 * t * (1.0 - t)
    w_high = t ** 2
    return {'low': w_low, 'medium': w_med, 'high': w_high}


def _anchors_for_var(var: str) -> Dict[str, Dict[str, float]]:
    """Return anchor distributions for a given Hooper variable mapping.
    For subjective_sleep, anchors are good/medium/poor; map to low/medium/high semantics.
    """
    if var == 'subjective_sleep':
        # Map low->good, medium->medium, high->poor
        return {
            'low': EMISSION_CPT['subjective_sleep']['good'],
            'medium': EMISSION_CPT['subjective_sleep']['medium'],
            'high': EMISSION_CPT['subjective_sleep']['poor'],
        }
    # Other vars use low/medium/high directly
    return {
        'low': EMISSION_CPT[var]['low'],
        'medium': EMISSION_CPT[var]['medium'],
        'high': EMISSION_CPT[var]['high'],
    }


def hooper_to_state_likelihood(var: str, score: int) -> Dict[str, float]:
    """Map Hooper score 1..7 to a continuous state-likelihood vector via Bezier blending.

    Assumptions: higher score = worse (for all Hooper components).
    var is one of: 'subjective_fatigue', 'muscle_soreness', 'subjective_stress', 'subjective_sleep'.
    """
    s = max(1, min(7, int(score)))
    t = (s - 1) / 6.0  # 1->0, 7->1 (higher=worse)
    w = _bernstein_w(t)
    anchors = _anchors_for_var(var)

    # Weighted blend across anchors for each state
    like: Dict[str, float] = {}
    for st in STATES:
        v = (
            w['low'] * float(anchors['low'].get(st, 0.0)) +
            w['medium'] * float(anchors['medium'].get(st, 0.0)) +
            w['high'] * float(anchors['high'].get(st, 0.0))
        )
        like[st] = max(v, 1e-6)

    # Normalize
    total = sum(like.values())
    if total > 0:
        like = {st: v / total for st, v in like.items()}
    return like

