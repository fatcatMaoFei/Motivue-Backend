#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sweep Hooper scores (1..7) to test model sensitivity/robustness.

For each Hooper component (fatigue/soreness/stress/sleep), runs 7 payloads with
the score fixed at 1..7 while holding other factors constant. Also tests a
"combined" scenario where all four Hooper components equal the same score.

Outputs a CSV with per-score readiness and diagnosis, plus prints monotonicity
checks (expect readiness decreases as Hooper score increases).

Run:
  python -m readiness.exp_hooper_sweep --out readiness/examples/hooper_sweep
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

from readiness.service import compute_readiness_from_payload
from readiness.constants import READINESS_WEIGHTS


HOOPER_VARS = ['fatigue', 'soreness', 'stress', 'sleep']


def fixed_prev() -> Dict[str, float]:
    return {'Peak': 0.10, 'Well-adapted': 0.50, 'FOR': 0.30, 'Acute Fatigue': 0.10, 'NFOR': 0.0, 'OTS': 0.0}


def run_case(var: str, score: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'user_id': 'hooper_sweep_user',
        'date': '2025-09-15',
        'gender': '男',
        'previous_state_probs': fixed_prev(),
        'training_load': '低',
        'recent_training_loads': [],
        # Keep objective evidence neutral to reduce overshadowing
        'objective': {
            'sleep_performance_state': 'medium',
            'restorative_sleep': 'medium',
            'hrv_trend': 'stable',
        },
        'journal': {},
        'hooper': {var: int(score)},
    }
    return compute_readiness_from_payload(payload)


def run_combined(score: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'user_id': 'hooper_sweep_user',
        'date': '2025-09-15',
        'gender': '男',
        'previous_state_probs': fixed_prev(),
        'training_load': '低',
        'recent_training_loads': [],
        'objective': {
            'sleep_performance_state': 'medium',
            'restorative_sleep': 'medium',
            'hrv_trend': 'stable',
        },
        'journal': {},
        'hooper': {k: int(score) for k in HOOPER_VARS},
    }
    return compute_readiness_from_payload(payload)


def monotone_non_increasing(xs: List[float]) -> bool:
    return all(xs[i] >= xs[i+1] for i in range(len(xs)-1))


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=str, default='readiness/examples/hooper_sweep', help='Output CSV path prefix (no extension)')
    args = ap.parse_args(argv)

    out_prefix = Path(args.out)
    out_csv = out_prefix.with_suffix('.csv')
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    rows: List[str] = []
    header = 'group,var,score,readiness,readiness_float,diagnosis'
    rows.append(header)

    # Per-variable sweeps
    summary: List[Tuple[str, List[float]]] = []
    for var in HOOPER_VARS:
        scores: List[float] = []
        for s in range(1, 8):
            res = run_case(var, s)
            # Compute non-rounded readiness for sensitivity visibility
            rfloat = 0.0
            post = res.get('final_posterior_probs') or {}
            for st, w in READINESS_WEIGHTS.items():
                rfloat += float(post.get(st, 0.0)) * float(w)
            rows.append(','.join([
                'single', var, str(s),
                str(res['final_readiness_score']), f"{rfloat:.3f}",
                str(res['final_diagnosis']),
            ]))
            scores.append(float(res['final_readiness_score']))
        summary.append((var, scores))

    # Combined sweep
    combo_scores: List[float] = []
    for s in range(1, 8):
        res = run_combined(s)
        rfloat = 0.0
        post = res.get('final_posterior_probs') or {}
        for st, w in READINESS_WEIGHTS.items():
            rfloat += float(post.get(st, 0.0)) * float(w)
        rows.append(','.join([
            'combined', 'all', str(s),
            str(res['final_readiness_score']), f"{rfloat:.3f}",
            str(res['final_diagnosis']),
        ]))
        combo_scores.append(float(res['final_readiness_score']))

    out_csv.write_text('\n'.join(rows), encoding='utf-8')

    # Console summary
    print(f'Wrote {out_csv}')
    for var, scores in summary:
        ok = monotone_non_increasing(scores)
        print(f'{var:9s}: scores={scores}  monotone_non_increasing={ok}')
    ok_combo = monotone_non_increasing(combo_scores)
    print(f'combined : scores={combo_scores}  monotone_non_increasing={ok_combo}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
