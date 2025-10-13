#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monthly batch personalization runner.

- Scans an input directory for per-user CSV files (standard columns)
- Uses the last --since-days window (default 90) for training
- Outputs CPT JSONs into 个性化CPT/artifacts/YYYYMM/ and a summary CSV

Usage:
  python 个性化CPT/monthly_update.py --input-dir 个性化CPT/artifacts \
    --since-days 90 --k 50 --user-col user_id

Note: Replace input-dir with your DB export drop (one CSV per user).
"""

from __future__ import annotations
import os
import sys
import json
from datetime import datetime, timedelta
from typing import List

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from 个性化CPT.train_personalization import learn_personalized_cpt


def list_csvs(input_dir: str) -> List[str]:
    return [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith('.csv')]


def infer_user_id(df: pd.DataFrame, path: str, user_col: str|None) -> str:
    if user_col and user_col in df.columns and df[user_col].notna().any():
        return str(df[user_col].dropna().iloc[0])
    # fallback to filename stem
    return os.path.splitext(os.path.basename(path))[0]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--since-days', type=int, default=90)
    ap.add_argument('--k', type=float, default=50.0)
    ap.add_argument('--user-col', default='user_id')
    args = ap.parse_args()

    in_dir = os.path.abspath(args.input_dir)
    csvs = list_csvs(in_dir)
    if not csvs:
        print('No CSV files found in', in_dir)
        return

    ts = datetime.now()
    ym = ts.strftime('%Y%m')
    out_dir = os.path.join(ROOT, '个性化CPT', 'artifacts', ym)
    os.makedirs(out_dir, exist_ok=True)
    summary_rows = []

    for p in csvs:
        try:
            df = pd.read_csv(p)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                cutoff = ts - timedelta(days=args.since_days)
                df = df[df['date'] >= cutoff].copy()
                df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            user_id = infer_user_id(df, p, args.user_col)
            days = len(df)
            if days < 30:
                print(f'Skip {user_id}: only {days} days < 30')
                continue
            cpt = learn_personalized_cpt(df, user_id=user_id, shrink_k=args.k)
            out_path = os.path.join(out_dir, f'personalized_emission_cpt_{user_id}.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(cpt, f, ensure_ascii=False, indent=2)
            summary_rows.append({'user_id': user_id, 'days_used': days, 'k': args.k, 'json': out_path})
            print('OK', user_id, 'days', days, '->', out_path)
        except Exception as e:
            print('ERR', p, e)

    if summary_rows:
        sm = pd.DataFrame(summary_rows)
        sm_path = os.path.join(out_dir, 'monthly_summary.csv')
        sm.to_csv(sm_path, index=False, encoding='utf-8')
        print('Summary saved:', sm_path)

if __name__ == '__main__':
    main()
