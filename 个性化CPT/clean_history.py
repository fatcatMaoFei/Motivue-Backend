#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick cleaner for GUI-exported or Excel-edited CSVs to our standard format.

Usage:
  python 个性化CPT/clean_history.py --in "C:/Users/Lenovo/Desktop/2025-09-11T08-07_export.csv" --out 个性化CPT/history_gui_log_clean.csv
"""

import argparse
import pandas as pd

REQ_COLS = [
    'date','user_id','gender','training_load','apple_sleep_score','sleep_performance_state','restorative_sleep',
    'hrv_trend','fatigue_hooper','soreness_hooper','stress_hooper','sleep_hooper','nutrition','gi_symptoms',
    'alcohol_consumed','late_caffeine','screen_before_bed','late_meal','is_sick','is_injured',
    'rpe','duration_minutes','rpe_au','label_au','training_conflict','final_readiness_score','final_diagnosis'
]

TRAINING = {'极高','高','中','低','休息'}
TRAINING_AU = {
    '休息': 0,
    '低': 200,
    '中': 350,
    '高': 500,
    '极高': 700,
}

def detect_gender(x: str) -> str:
    s = str(x)
    if '女' in s:
        return '女性'
    if '男' in s:
        return '男性'
    return '男性'

def norm_bool(x):
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in ('1','true','yes','y')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--out', dest='out', required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    # Drop unnamed index columns
    drop_cols = [c for c in df.columns if c == '' or str(c).startswith('Unnamed:')]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # Ensure required columns exist
    for c in REQ_COLS:
        if c not in df.columns:
            df[c] = None

    # Normalize types
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['gender'] = df['gender'].apply(detect_gender)
    def _fix_tl(row):
        val = row.get('training_load')
        if str(val) in TRAINING:
            return str(val)
        try:
            la = float(row.get('label_au') or 0)
        except Exception:
            la = 0.0
        if la <= 0:
            return None
        # choose nearest label by AU
        best_label, best_dist = None, None
        for lbl, au in TRAINING_AU.items():
            d = abs(float(au) - la)
            if best_dist is None or d < best_dist:
                best_label, best_dist = lbl, d
        return best_label

    df['training_load'] = df.apply(_fix_tl, axis=1)
    # Booleans
    for k in ['alcohol_consumed','late_caffeine','screen_before_bed','late_meal','is_sick','is_injured']:
        df[k] = df[k].apply(norm_bool)

    # Reorder
    df = df[REQ_COLS]
    df.to_csv(args.out, index=False, encoding='utf-8')
    print('Wrote cleaned CSV to', args.out)

if __name__ == '__main__':
    main()
