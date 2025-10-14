#!/usr/bin/env python3
import sys, os, json
import pandas as pd

# Use readiness library from this monorepo (proxy to libs/readiness-engine)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from readiness.personalization_cpt.train import learn_personalized_cpt  # type: ignore

def main():
    import argparse
    ap = argparse.ArgumentParser(description='Personalize EMISSION_CPT: CSV in -> CPT JSON out')
    ap.add_argument('--csv', required=True, help='History CSV path (standardized format)')
    ap.add_argument('--user', required=True, help='User ID')
    ap.add_argument('--out', required=True, help='Output JSON path')
    ap.add_argument('--shrink-k', type=float, default=50.0, help='Shrinkage strength (n/(n+k))')
    args = ap.parse_args()

    na_vals = ["", "none", "null", "na", "nan", "None", "NULL", "NA", "NaN"]
    df = pd.read_csv(args.csv, na_values=na_vals, keep_default_na=True)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.sort_values('date')

    cpt = learn_personalized_cpt(df, args.user, args.shrink_k)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(cpt, f, ensure_ascii=False, indent=2)
    print('Saved', args.out)

if __name__ == '__main__':
    main()
