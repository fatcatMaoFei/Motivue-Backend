#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch personalize on 60/100/200 days by repeating a base CSV, then compare
personalized CPTs against default readiness.constants.EMISSION_CPT.

Usage:
  python tools/personalization_cpt/batch_personalize_and_compare.py \
    --base samples/data/personalization/history_gui_log_clean.csv --user user_001
"""

from __future__ import annotations
import os
import sys
import json
from datetime import timedelta
from typing import Dict, Any, List, Tuple

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from readiness.constants import EMISSION_CPT as GLOBAL_CPT
from readiness.personalization_cpt.train import learn_personalized_cpt  # type: ignore


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def augment_days(df: pd.DataFrame, target_days: int) -> pd.DataFrame:
    base = df.copy()
    base['date'] = pd.to_datetime(base['date'], errors='coerce')
    out = base.copy()
    shift = 1
    while len(out) < target_days:
        b = base.copy()
        b['date'] = b['date'] + timedelta(days=shift * len(base))
        out = pd.concat([out, b], ignore_index=True)
        shift += 1
    out = out.iloc[:target_days].copy()
    out['date'] = out['date'].dt.strftime('%Y-%m-%d')
    return out


def avg_l1_var(global_cpt: Dict[str, Any], new_cpt: Dict[str, Any], var: str) -> float:
    if var not in global_cpt or var not in new_cpt:
        return 0.0
    total = 0.0
    cnt = 0
    for cat in new_cpt[var].keys():
        go = global_cpt[var].get(cat, {})
        gn = new_cpt[var].get(cat, {})
        for s in STATES:
            a = float(go.get(s, 0.0))
            b = float(gn.get(s, 0.0))
            total += abs(a - b)
            cnt += 1
    return (total / cnt) if cnt else 0.0


def compare_and_print(tag: str, cpt: Dict[str, Any], top_k: int = 5) -> None:
    # Compute avg L1 per variable
    rows: List[Tuple[str, float]] = []
    for var in cpt.keys():
        if var in GLOBAL_CPT:
            rows.append((var, avg_l1_var(GLOBAL_CPT, cpt, var)))
    rows.sort(key=lambda x: x[1], reverse=True)
    print(f"\n=== {tag} personalization deltas (avg L1 per variable, Top {top_k}) ===")
    for var, score in rows[:top_k]:
        print(f"  {var:22s}  avg_L1_delta={score:.4f}")
    if not rows:
        print("  No comparable variables (empty or invalid CPT)")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='Base CSV (>=1 day)')
    ap.add_argument('--user', required=True)
    args = ap.parse_args()

    df0 = pd.read_csv(args.base)
    targets = [60, 100, 200]
    out_dir = os.path.join(ROOT, 'samples', 'data', 'personalization')
    os.makedirs(out_dir, exist_ok=True)

    for days in targets:
        dfx = augment_days(df0, days)
        csv_path = os.path.join(out_dir, f'history_{args.user}_{days}d.csv')
        dfx.to_csv(csv_path, index=False, encoding='utf-8')
        cpt = learn_personalized_cpt(dfx, user_id=args.user, shrink_k=100.0)
        cpt_path = os.path.join(out_dir, f'personalized_emission_cpt_{args.user}_{days}d.json')
        with open(cpt_path, 'w', encoding='utf-8') as f:
            json.dump(cpt, f, ensure_ascii=False, indent=2)
        alpha = days / (days + 100.0)
        print(f"\n[{days}天] shrink-k=100 → 近似 α={alpha:.3f}")
        compare_and_print(f"{days}天", cpt)


if __name__ == '__main__':
    main()
