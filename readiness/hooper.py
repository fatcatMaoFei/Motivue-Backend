#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from readiness.constants import EMISSION_CPT


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def _piecewise_weights(score: int) -> Dict[str, float]:
    """Piecewise-linear weights over 1..7 with within-band separation.

    Design (monotone, more distinct bins, but 1/2, 3/4/5, 6/7 still differ):
    - 1..2: near-low, but 2 slightly worse than 1
    - 3..5: medium band with fixed medium mass and linear low→high trade
    - 6..7: high band with medium mass shrinking, 7 worse than 6
    """
    s = max(1, min(7, int(score)))
    if s == 1:
        w = {'low': 1.0, 'medium': 0.0, 'high': 0.0}
    elif s == 2:
        w = {'low': 0.80, 'medium': 0.20, 'high': 0.0}
    elif s == 3:
        w = {'low': 0.20, 'medium': 0.80, 'high': 0.0}
    elif s == 4:
        w = {'low': 0.10, 'medium': 0.80, 'high': 0.10}
    elif s == 5:
        w = {'low': 0.0, 'medium': 0.80, 'high': 0.20}
    elif s == 6:
        w = {'low': 0.0, 'medium': 0.30, 'high': 0.70}
    else:  # s == 7
        w = {'low': 0.0, 'medium': 0.10, 'high': 0.90}

    # Normalize defensively
    total = sum(w.values())
    if total <= 0:
        return {'low': 1.0, 'medium': 0.0, 'high': 0.0}
    return {k: v / total for k, v in w.items()}


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
    """Map Hooper 1..7 to state-likelihood via piecewise-linear anchor blending.

    Assumptions: higher score = worse (for all Hooper components).
    var ∈ {'subjective_fatigue','muscle_soreness','subjective_stress','subjective_sleep'}.
    """
    w = _piecewise_weights(int(score))
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
