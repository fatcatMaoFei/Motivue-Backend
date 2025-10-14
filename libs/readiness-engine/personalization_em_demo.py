#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Personalization Demo (Stage 1: Approximate EM on EMISSION CPT)

Purpose
- Batch-learn a per-user personalized EMISSION_CPT from daily data.
- E-step (approx): use the model's daily posterior P(state|evidence) as gamma_t.
- M-step: re-estimate P(evidence|state) by weighted counts across days.

What it updates
- Only EMISSION_CPT (P(Evidence | State)) variables present in dynamic_model.EMISSION_CPT.
- It does NOT update prior causal CPTs (e.g., alcohol) in this demo.

Inputs (CSV columns; minimal set, extras ignored):
- date: YYYY-MM-DD
- training_load: one of your model keys (e.g., '高', '中', '低', '极高' as applicable)

Objective/subjective evidence for posterior updates (use any available):
- sleep_performance_state: 'good'|'medium'|'poor'
- restorative_sleep: 'high'|'medium'|'low'
- hrv_trend: 'rising'|'stable'|'slight_decline'|'significant_decline'
- Hooper indices (integers 1..7): fatigue_hooper, soreness_hooper, stress_hooper, sleep_hooper
- Optional: nutrition, gi_symptoms, fatigue_3day_state (if your pipeline uses them)

Optional logs (used for prior; if present, interpreted as "yesterday short-term behaviors"):
- alcohol_consumed: True/False
- late_caffeine: True/False
- screen_before_bed: True/False
- late_meal: True/False

Optional persistent states:
- is_sick: True/False (today)
- is_injured: True/False (today)
- menstrual_phase: one of dynamic_model.MENSTRUAL_PHASE_CPT keys (only for gender='女性')

Output
- Saves a JSON with the personalized EMISSION_CPT: `personalized_emission_cpt_<user>.json`
- Prints a short before/after summary for a few variables.

Usage
  python personalization_em_demo.py --csv user_history.csv --user u001 --gender 男性
  # Then apply in-memory when running the model:
  #   from personalization_em_demo import load_personalized_cpt
  #   load_personalized_cpt('personalized_emission_cpt_u001.json')

Notes
- This is an approximate EM (filtering-style): we use daily posterior as gamma_t without full forward-backward smoothing.
- Works well as a Stage-1 cold-start personalization once you have ~30–90 days.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from . import constants
from . import service
from . import mapping


State = str
Var = str
Category = str


CORE_EMISSION_VARS = [
    # HRV + Sleep (2) + Hooper (4 mapped)
    'hrv_trend',
    'sleep_performance',
    'restorative_sleep',
    'subjective_fatigue',
    'muscle_soreness',
    'subjective_stress',
    'subjective_sleep',
]


def get_emission_domains(whitelist: Optional[List[str]] = None) -> Dict[Var, List[Category]]:
    """Return var->categories for EMISSION_CPT, filtered by whitelist if provided."""
    domains: Dict[Var, List[Category]] = {}
    for var, cats in constants.EMISSION_CPT.items():
        if whitelist is not None and var not in whitelist:
            continue
        domains[var] = list(cats.keys())
    return domains


def map_row_to_evidence(row: pd.Series) -> Dict[str, Any]:
    """Build a new_evidence dict for posterior updates from a CSV row."""
    ev: Dict[str, Any] = {}
    # Objective
    for key in ['sleep_performance_state', 'restorative_sleep', 'hrv_trend',
                'nutrition', 'gi_symptoms', 'fatigue_3day_state']:
        if key in row and pd.notna(row[key]):
            ev[key] = row[key]
    # Hooper
    for key in ['fatigue_hooper', 'soreness_hooper', 'stress_hooper', 'sleep_hooper']:
        if key in row and pd.notna(row[key]):
            try:
                ev[key] = int(row[key])
            except Exception:
                pass
    # Today journal (boolean) evidence
    for key in ['is_sick', 'is_injured', 'high_stress_event_today', 'meditation_done_today']:
        if key in row and pd.notna(row[key]):
            v = row[key]
            if isinstance(v, str):
                v2 = v.strip().lower()
                ev[key] = v2 in ['1', 'true', 'yes', 'y', 't']
            else:
                ev[key] = bool(v)
    return ev


def map_row_to_yesterday_logs(row: pd.Series) -> Dict[str, Any]:
    """Interpret as yesterday's short-term behaviors for today's prior."""
    logs: Dict[str, Any] = {}
    for key in ['alcohol_consumed', 'late_caffeine', 'screen_before_bed', 'late_meal']:
        if key in row and pd.notna(row[key]):
            v = row[key]
            if isinstance(v, str):
                v2 = v.strip().lower()
                logs[key] = v2 in ['1', 'true', 'yes', 'y', 't']
            else:
                logs[key] = bool(v)
    return logs


def _l1_diff_emission(a: Dict[str, Any], b: Dict[str, Any], vars_subset: Optional[List[str]] = None) -> float:
    total = 0.0
    count = 0
    for var, cats in a.items():
        if vars_subset is not None and var not in vars_subset:
            continue
        for cat, sd in cats.items():
            for state, pa in sd.items():
                pb = float(b[var][cat][state])
                total += abs(float(pa) - pb)
                count += 1
    return total / max(count, 1)


def _normalize_state_cats(state_cats: Dict[Category, float], eps: float = 1e-6) -> Dict[Category, float]:
    clipped = {c: max(v, eps) for c, v in state_cats.items()}
    s = sum(clipped.values())
    return {c: v / s for c, v in clipped.items()} if s > 0 else clipped


def run_batch_personalization(
    df: pd.DataFrame,
    user_id: str,
    gender: str = '男性',
    only_core_vars: bool = True,
    shrink_k: float = 100.0,
    max_iter: int = 3,
    tol: float = 1e-3,
) -> Dict[str, Any]:
    """
    Approximate EM with core-var whitelist, shrinkage, and multi-iteration convergence.
      - E-step: per-day posterior P(state|evidence) using current EMISSION_CPT
      - M-step: re-estimate EMISSION_CPT via weighted counts (whitelisted vars only)
      - Shrinkage: new = (1-λ)*global + λ*learned, λ = n/(n+shrink_k) per (var,state)
      - Iterate until L1 change < tol or max_iter reached
    """
    df = df.copy()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
    else:
        df = df.reset_index(drop=True)

    states: List[State] = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']
    whitelist = CORE_EMISSION_VARS if only_core_vars else None
    domains = get_emission_domains(whitelist)

    # Keep a snapshot of the global baseline for shrinkage target
    global_baseline = deepcopy(constants.EMISSION_CPT)
    working = deepcopy(global_baseline)

    def one_e_step_counts(current_emission: Dict[str, Any]) -> Tuple[
        Dict[Var, Dict[State, Dict[Category, float]]],
        Dict[Var, Dict[State, float]],
    ]:
        # set runtime emission
        constants.EMISSION_CPT = deepcopy(current_emission)

        counts: Dict[Var, Dict[State, Dict[Category, float]]] = {
            var: {s: {c: 0.0 for c in cats} for s in states}
            for var, cats in domains.items()
        }
        state_totals: Dict[Var, Dict[State, float]] = {var: {s: 0.0 for s in states} for var in domains}

        prev_probs: Optional[Dict[str, float]] = None
        for idx, row in df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d') if 'date' in df.columns else f'day_{idx+1:02d}'
            mgr = dm.DailyReadinessManager(
                user_id=user_id,
                date=date_str,
                previous_state_probs=prev_probs,
                gender=gender,
            )

            # Yesterday logs -> prior (optional)
            y_logs = map_row_to_yesterday_logs(row)
            if y_logs:
                y_date = (datetime.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                mgr.journal_manager.add_journal_entry(user_id, y_date, 'short_term_behaviors', y_logs)

            # Optional today's persistent
            today_persistent: Dict[str, Any] = {}
            for key in ['is_sick', 'is_injured', 'menstrual_phase']:
                if key in row and pd.notna(row[key]):
                    today_persistent[key] = row[key]
            if today_persistent:
                mgr.journal_manager.add_journal_entry(user_id, date_str, 'persistent_status', today_persistent)

            # Prior
            causal_inputs = {}
            if 'training_load' in row and pd.notna(row['training_load']):
                causal_inputs['training_load'] = str(row['training_load'])
            mgr.calculate_today_prior(causal_inputs)

            # Posterior
            new_ev = map_row_to_evidence(row)
            update = mgr.add_evidence_and_update(new_ev)
            posterior = update['posterior_probs']

            # Map and filter to whitelist
            mapped = dm.map_inputs_to_states(new_ev)
            for var, val in mapped.items():
                if var not in domains:
                    continue
                if val not in domains[var]:
                    continue
                pv = posterior
                for s in states:
                    w = pv.get(s, 0.0)
                    counts[var][s][val] += w
                    state_totals[var][s] += w

            prev_probs = posterior

        return counts, state_totals

    def m_step_with_shrink(counts, state_totals, prior_emission, baseline_global):
        # Learned from counts
        learned = deepcopy(prior_emission)
        for var, cats in domains.items():
            for s in states:
                total = sum(counts[var][s].values())
                if total > 0:
                    for c in cats:
                        learned[var][c][s] = counts[var][s][c] / total
                # else keep prior_emission value

        # Shrink to global baseline per (var,state)
        new_emission = deepcopy(prior_emission)
        for var, cats in domains.items():
            for s in states:
                n = float(state_totals[var][s])
                lam = n / (n + float(shrink_k)) if (n + float(shrink_k)) > 0 else 0.0
                # mix each category and renormalize per state
                mixed_state = {}
                for c in cats:
                    base = float(baseline_global[var][c][s])
                    est = float(learned[var][c][s])
                    mixed_state[c] = (1.0 - lam) * base + lam * est
                mixed_state = _normalize_state_cats(mixed_state)
                for c, v in mixed_state.items():
                    new_emission[var][c][s] = v
        return new_emission

    history: List[Dict[str, Any]] = []
    for it in range(max_iter):
        counts, state_totals = one_e_step_counts(working)
        updated = m_step_with_shrink(counts, state_totals, working, global_baseline)
        delta = _l1_diff_emission(working, updated, vars_subset=list(domains.keys()))
        history.append({'iter': it + 1, 'l1_delta': delta})
        working = updated
        if delta < tol:
            break

    return {
        'personalized_emission_cpt': working,
        'counts': counts,
        'state_totals': state_totals,
        'history': history,
        'used_vars': list(domains.keys()),
        'shrink_k': shrink_k,
    }


def save_personalized_cpt(payload: Dict[str, Any], out_path: str) -> None:
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload['personalized_emission_cpt'], f, ensure_ascii=False, indent=2)


def load_personalized_cpt(in_path: str) -> None:
    """Load a personalized EMISSION_CPT JSON into the running dynamic_model module."""
    with open(in_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
    dm.EMISSION_CPT = loaded  # override in-memory
    print(f"Loaded personalized EMISSION_CPT from: {in_path}")


def preview_changes(old: Dict[str, Any], new: Dict[str, Any], vars_to_show: Optional[List[str]] = None, top_k: int = 3) -> None:
    if vars_to_show is None:
        vars_to_show = ['hrv_trend', 'restorative_sleep', 'sleep_performance', 'subjective_fatigue']
    states = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']
    for var in vars_to_show:
        if var not in old or var not in new:
            continue
        print(f"\n== {var} ==")
        for s in states:
            # compute L1 diff over categories
            cats = new[var].keys()
            diffs = []
            for c in cats:
                o = float(old[var][c].get(s, 0.0))
                n = float(new[var][c].get(s, 0.0))
                diffs.append((c, o, n, n - o))
            diffs.sort(key=lambda x: abs(x[3]), reverse=True)
            print(f"  State={s} (top-{top_k} changes):")
            for c, o, n, d in diffs[:top_k]:
                print(f"    {c:>18}: {o:6.3f} -> {n:6.3f} (Δ {d:+.3f})")


def main():
    ap = argparse.ArgumentParser(description="Personalize EMISSION_CPT from daily CSV (approx EM with whitelist+shrink+iterations)")
    ap.add_argument('--csv', required=True, help='Path to user daily CSV')
    ap.add_argument('--user', required=True, help='User ID')
    ap.add_argument('--gender', default='男性', choices=['男性', '女性'])
    ap.add_argument('--out', default=None, help='Output JSON path (defaults to personalized_emission_cpt_<user>.json)')
    ap.add_argument('--no-core-only', action='store_true', help='If set, do NOT restrict to core vars (HRV/Sleep/Hooper)')
    ap.add_argument('--shrink-k', type=float, default=100.0, help='Shrinkage strength k (λ=n/(n+k), higher k = stronger shrink to global)')
    ap.add_argument('--max-iter', type=int, default=3, help='Max EM iterations')
    ap.add_argument('--tol', type=float, default=1e-3, help='Convergence tolerance on avg L1 change')
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    result = run_batch_personalization(
        df,
        user_id=args.user,
        gender=args.gender,
        only_core_vars=(not args.no_core_only),
        shrink_k=args.shrink_k,
        max_iter=args.max_iter,
        tol=args.tol,
    )
    new_emission = result['personalized_emission_cpt']

    out_path = args.out or f'personalized_emission_cpt_{args.user}.json'
    save_personalized_cpt(result, out_path)
    print(f"\nSaved personalized EMISSION_CPT to: {out_path}")

    # Preview key changes vs current model
    print("\nEM iteration history:")
    for h in result.get('history', []):
        print(f"  iter={h['iter']}, avg_L1_delta={h['l1_delta']:.6f}")

    print("\nUsed variables:", ", ".join(result.get('used_vars', [])))
    preview_changes(dm.EMISSION_CPT, new_emission)


if __name__ == '__main__':
    main()
