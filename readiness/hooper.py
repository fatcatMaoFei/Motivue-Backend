#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict

from readiness.constants import EMISSION_CPT


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def _band_and_alpha(score: int) -> (str, float):
    """Map score to a single anchor band and an exponent alpha to adjust strength.

    Policy per request:
    - 1..2 → 'low' anchor only; 1 slightly better than baseline-low, 2 slightly worse
    - 3..5 → 'medium' anchor only; 3 < 4 < 5 (强度逐步增加)
    - 6..7 → 'high' anchor only; 6 < 7（7 最差）
    """
    s = max(1, min(7, int(score)))
    if s <= 2:
        band = 'low'
        alpha = 1.20 if s == 1 else 0.95
    elif s <= 5:
        band = 'medium'
        alpha = {3: 0.95, 4: 1.00, 5: 1.08}[s]
    else:
        band = 'high'
        alpha = 1.06 if s == 6 else 1.20
    return band, alpha


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
    """Map Hooper 1..7 to state-likelihood via single-band + exponent shaping.

    不跨档混合：
    - 1..2 仅用 low 锚点；1 比 baseline-low 稍“更好”，2 稍“更弱”
    - 3..5 仅用 medium 锚点；3/4/5 依次增强
    - 6..7 仅用 high 锚点；7 最强（最差）
    通过对锚点分布按 alpha 做幂次缩放体现“证据力度”。
    """
    band, alpha = _band_and_alpha(int(score))
    anchors = _anchors_for_var(var)
    base = anchors['low'] if band == 'low' else anchors['medium'] if band == 'medium' else anchors['high']

    # Power-shape the anchor to modulate evidence strength within the band
    like: Dict[str, float] = {}
    for st in STATES:
        v = float(base.get(st, 1e-6))
        v = max(v, 1e-9) ** float(alpha)
        like[st] = v

    # Normalize
    total = sum(like.values())
    if total > 0:
        like = {st: v / total for st, v in like.items()}
    return like
