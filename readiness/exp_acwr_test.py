#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import statistics as stats
from typing import Any, Dict, List

from readiness.service import compute_readiness_from_payload


def _payload_base() -> Dict[str, Any]:
    return {
        'user_id': 'acwr_test',
        'date': '2025-09-20',
        'gender': '鐢?,
        'objective': {
            'sleep_performance_state': 'medium',
            'restorative_sleep': 'medium',
            'hrv_trend': 'stable',
        },
        'hooper': {  # 涓€т富瑙傦紝閬垮厤鍠у澶轰富
            'fatigue': 3,
            'soreness': 3,
            'stress': 3,
            'sleep': 3,
        },
    }


def run_case(name: str, recent_au: List[float] | None = None,
             doms: int | None = None, energy: int | None = None,
             au_norm_ref: float | None = 2000.0) -> Dict[str, Any]:
    p = _payload_base()
    if recent_au is not None:
        p['recent_training_au'] = recent_au
    if doms is not None:
        p['doms_nrs'] = doms
    if energy is not None:
        p['energy_nrs'] = energy
    if au_norm_ref is not None:
        p['au_norm_ref'] = au_norm_ref
    res = compute_readiness_from_payload(p)
    out = {
        'name': name,
        'score': res['final_readiness_score'],
        'dx': res['final_diagnosis'],
    }
    return out


def summarize(title: str, out: Dict[str, Any]) -> None:
    print(f"[{title}] -> score={out['score']} dx={out['dx']}")


def main() -> int:
    # Baseline: no ACWR inputs 鈫?reference
    base = run_case('baseline_none')
    summarize('Baseline (no ACWR)', base)

    # Reward path: R鈮?.85 (A7 < C28), small +1 鍒嗗乏鍙?    au_reward = [350]*21 + [300]*7  # C28鈮?36, A7鈮?00 鈫?R鈮?.89
    reward = run_case('reward_R<0.9', au_reward)
    summarize('Reward (R<=0.9)', reward)

    # Penalty path (low chronic + high acute): C28鈮?0, A7鈮?00 鈫?R>>1
    au_pen_low = [0]*21 + [700]*7
    pen_low = run_case('penalty_lowC_highA', au_pen_low)
    summarize('Penalty (low chronic, high acute)', pen_low)

    # Penalty but with high chronic protection: use large daily AU to cross band-high thresholds
    au_pen_high = [2000]*21 + [2800]*7  # C28鈮?286, A7鈮?800 鈫?R鈮?.22, band=high
    pen_high = run_case('penalty_highC_highA', au_pen_high)
    summarize('Penalty (high chronic, high acute)', pen_high)

    # Very low side slight deconditioning: R<=0.6 & chronic low
    au_very_low = [200]*21 + [100]*7  # C28鈮?71, A7鈮?00 鈫?R鈮?.58
    very_low = run_case('very_low_R', au_very_low)
    summarize('Very low side (slight deconditioning)', very_low)

    # 3-day fatigue: high DOMS(8) + low Energy(3) + A3 moderate
    au_fatigue = [300]*25 + [500, 500, 500]
    fatigue = run_case('fatigue3_high', au_fatigue, doms=8, energy=3, au_norm_ref=2000)
    summarize('Fatigue_3day high (DOMS+low energy)', fatigue)

    # Small stability check: two close series
    au_a = [350]*28
    au_b = [350]*27 + [500]
    a = run_case('stability_a', au_a)
    b = run_case('stability_b', au_b)
    print(f"[Stability] a={a['score']} -> b={b['score']} (螖={b['score']-a['score']})")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

