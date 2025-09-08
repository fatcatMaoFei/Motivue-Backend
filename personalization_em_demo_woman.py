#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personalization Demo (Women): learn menstrual-cycle effect parameters from daily data.

What it does
- Runs an approximate EM over days to estimate posterior P(state|evidence) using the current engine.
- Fits simple, smooth cycle parameters by grid-search to maximize ∑_t ∑_s γ_t(s) log P_cycle(day_t|state=s; params).

Inputs (CSV)
- date, training_load
- sleep_performance_state, restorative_sleep, hrv_trend
- fatigue_hooper, soreness_hooper, stress_hooper, sleep_hooper
- cycle_day, cycle_length (per-day)

Output
- Prints best parameters and saves JSON `personalized_cycle_params_<user>.json`.
- Shows how to apply at runtime (manual patch) until the API accepts per-user cycle params.
"""

from __future__ import annotations

import argparse
import json
from math import exp
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from readiness.engine import ReadinessEngine


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def _gauss(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return exp(-0.5 * z * z)


def cycle_like_params(day: int, L: int,
                      ov_frac: float, luteal_off: float, sig_scale: float) -> Dict[str, float]:
    # Base centers/sigmas from readiness.cycle; allow simple personalization
    L = max(20, min(40, int(L or 28)))
    d = max(1, min(L, int(day or 1)))
    ov = max(1.0, min(L*0.9, ov_frac * L))
    luteal_late = max(1.0, min(L*1.0, (L - 2) + luteal_off))
    menses_early = 2.0

    sig_peak = 2.2 * sig_scale
    sig_well = 3.2 * sig_scale
    sig_nfor = 2.5 * sig_scale
    sig_acute = 2.8 * sig_scale
    sig_for = 5.0 * sig_scale

    g_peak = _gauss(d, ov, sig_peak)
    g_well = _gauss(d, ov, sig_well)
    g_nfor = _gauss(d, luteal_late, sig_nfor)
    g_acute_late = _gauss(d, luteal_late - 2.0, sig_acute)
    g_acute_early = _gauss(d, menses_early, sig_acute)
    g_for = _gauss(d, 0.35 * L, sig_for) + _gauss(d, 0.65 * L, sig_for)

    raw = {
        'Peak': 0.85 * g_peak + 0.15 * g_well,
        'Well-adapted': 0.70 * g_well + 0.20 * g_peak + 0.10 * g_for,
        'FOR': 0.60 * g_for + 0.20 * g_well + 0.20 * g_acute_early,
        'Acute Fatigue': 0.55 * g_acute_late + 0.35 * g_acute_early + 0.10 * g_for,
        'NFOR': 0.70 * g_nfor + 0.25 * g_acute_late + 0.05 * g_for,
        'OTS': 1e-6,
    }
    eps = 1e-6
    s = sum(max(v, eps) for v in raw.values())
    return {k: max(v, eps) / s for k, v in raw.items()}


def e_step_posteriors(df: pd.DataFrame, user_id: str, gender: str) -> Tuple[List[Dict[str, float]], List[Tuple[int, int]]]:
    posteriors: List[Dict[str, float]] = []
    cycle_pairs: List[Tuple[int, int]] = []
    prev_probs: Optional[Dict[str, float]] = None
    for _, row in df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d') if 'date' in df.columns else str(row['date'])
        eng = ReadinessEngine(user_id=user_id, date=date_str, previous_state_probs=prev_probs, gender=gender)
        # prior
        causal = {}
        if pd.notna(row.get('training_load')):
            causal['training_load'] = str(row['training_load'])
        eng.calculate_today_prior(causal)
        # posterior updates
        ev = {}
        for k in ['sleep_performance_state', 'restorative_sleep', 'hrv_trend']:
            if k in row and pd.notna(row[k]):
                ev[k] = row[k]
        for k2, k1 in [('fatigue_hooper','fatigue_hooper'), ('soreness_hooper','soreness_hooper'), ('stress_hooper','stress_hooper'), ('sleep_hooper','sleep_hooper')]:
            if k1 in row and pd.notna(row[k1]):
                try:
                    ev[k2] = int(row[k1])
                except Exception:
                    pass
        # include current model cycle evidence to get baseline gamma
        if pd.notna(row.get('cycle_day')):
            cyc = {'day': int(row['cycle_day']), 'length': int(row.get('cycle_length', 28))}
            ev['cycle'] = cyc
            cycle_pairs.append((cyc['day'], cyc['length']))
        else:
            cycle_pairs.append((None, None))
        eng.add_evidence_and_update(ev)
        post = eng.get_daily_summary()['final_posterior_probs']
        posteriors.append(post)
        prev_probs = post
    return posteriors, cycle_pairs


def fit_cycle(df: pd.DataFrame, gamma: List[Dict[str, float]], cycles: List[Tuple[int, int]]):
    # Grid search simple params
    best = None
    best_ll = -1e18
    for ov_frac in [0.46, 0.48, 0.50, 0.52, 0.54]:
        for luteal_off in [-2.0, -1.0, 0.0, 1.0, 2.0]:
            for sig_scale in [0.9, 1.0, 1.1]:
                ll = 0.0
                valid_days = 0
                for (day, L), post in zip(cycles, gamma):
                    if not day or not L:
                        continue
                    like = cycle_like_params(day, L, ov_frac, luteal_off, sig_scale)
                    for s, p_s in post.items():
                        v = max(like.get(s, 1e-6), 1e-6)
                        ll += p_s * (0.0 if v <= 0 else float(pd.np.log(v)))
                    valid_days += 1
                if valid_days >= 10 and ll > best_ll:
                    best_ll = ll
                    best = {'ov_frac': ov_frac, 'luteal_off': luteal_off, 'sig_scale': sig_scale, 'days': valid_days}
    return best


def main():
    ap = argparse.ArgumentParser(description='Personalize menstrual cycle effect (women) by grid search')
    ap.add_argument('--csv', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--gender', default='女性')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

    gamma, cycles = e_step_posteriors(df, args.user, args.gender)
    best = fit_cycle(df, gamma, cycles)
    if not best:
        print('Insufficient cycle data to personalize (need >=10 days with cycle_day).')
        return

    out = args.out or f'personalized_cycle_params_{args.user}.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(best, f, ensure_ascii=False, indent=2)

    print('\nBest cycle params:')
    print(json.dumps(best, ensure_ascii=False, indent=2))
    print('\nHow to apply (manual until API accepts per-user cycle params):')
    print('  1) Load this JSON per user when starting the engine.')
    print('  2) Override readiness.cycle.cycle_likelihood_by_day to call cycle_like_params(day,L, ov_frac, luteal_off, sig_scale).')
    print('  3) Or add these params into payload (e.g., payload["cycle_params"]) and patch engine to read them.')


if __name__ == '__main__':
    main()

