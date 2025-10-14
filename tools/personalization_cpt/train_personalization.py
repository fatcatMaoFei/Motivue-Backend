#!/usr/bin/env python3
import sys, os, json
from copy import deepcopy
from typing import Any, Dict, List
import pandas as pd

# Add project root to path to use the existing readiness package
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from readiness import service as readiness_service
from readiness import mapping as readiness_mapping
from readiness import constants as readiness_constants

STATES: List[str] = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']

def _read_history(path: str) -> pd.DataFrame:
    na_vals = ["", "none", "null", "na", "nan", "None", "NULL", "NA", "NaN"]
    df = pd.read_csv(path, na_values=na_vals, keep_default_na=True)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.sort_values('date')
    return df

def learn_personalized_cpt(df: pd.DataFrame, user_id: str, shrink_k: float = 100.0) -> Dict[str, Any]:
    if len(df) < 30:
        return deepcopy(readiness_constants.EMISSION_CPT)

    evidence_counts: Dict[str, Dict[str, Dict[str, float]]] = {}
    state_totals: Dict[str, Dict[str, float]] = {}
    for ev, cats in readiness_constants.EMISSION_CPT.items():
        evidence_counts[ev] = {c: {s: 0.0 for s in STATES} for c in cats.keys()}
        state_totals[ev] = {s: 0.0 for s in STATES}

    prev_probs = None
    for _, row in df.iterrows():
        # Build daily payload (top-level fields accepted by service)
        date = row['date']
        if hasattr(date, 'strftime'):
            date = date.strftime('%Y-%m-%d')
        payload: Dict[str, Any] = {
            'user_id': user_id,
            'date': date,
            'gender': str(row.get('gender', '男性')),
            'previous_state_probs': prev_probs,
        }
        if pd.notna(row.get('training_load')):
            payload['training_load'] = str(row['training_load'])
        for k in ['apple_sleep_score','sleep_duration_hours','sleep_efficiency','restorative_ratio','hrv_trend',
                  'nutrition','gi_symptoms','fatigue_3day_state']:
            if k in row and pd.notna(row[k]):
                payload[k] = row[k]
        # hooper
        hooper = {}
        for h in ['fatigue','soreness','stress','sleep']:
            rk = f'{h}_hooper'
            if rk in row and pd.notna(row[rk]):
                hooper[h] = int(float(row[rk]))
        if hooper:
            payload['hooper'] = hooper

        result = readiness_service.compute_readiness_from_payload(payload)
        posterior = result.get('final_posterior_probs', result.get('posterior_probs', {}))

        mapped = readiness_mapping.map_inputs_to_states(payload)
        for ev, level in mapped.items():
            if ev not in evidence_counts:
                continue
            if level not in evidence_counts[ev]:
                continue
            for s in STATES:
                w = posterior.get(s, 0.0)
                evidence_counts[ev][level][s] += w
                state_totals[ev][s] += w
        prev_probs = posterior

    # M-step with shrinkage
    learned = deepcopy(readiness_constants.EMISSION_CPT)
    for ev, cats in learned.items():
        for state in STATES:
            n = state_totals.get(ev, {}).get(state, 0.0)
            alpha = n / (n + shrink_k) if (n + shrink_k) > 0 else 0.0
            # estimate
            est = {}
            total = sum(evidence_counts[ev][c][state] for c in cats.keys())
            for c in cats.keys():
                base = float(readiness_constants.EMISSION_CPT[ev][c][state])
                p = (evidence_counts[ev][c][state] / total) if total > 0 else base
                est[c] = max(1e-6, (1.0 - alpha) * base + alpha * p)
            # normalize per state
            ssum = sum(est.values())
            if ssum > 0:
                for c in est:
                    est[c] = est[c] / ssum
            for c, v in est.items():
                learned[ev][c][state] = float(v)
    return learned

def main():
    import argparse
    ap = argparse.ArgumentParser(description='Train personalized EMISSION_CPT from history CSV (either-or sleep logic).')
    ap.add_argument('--csv', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--shrink-k', type=float, default=100.0)
    args = ap.parse_args()

    df = _read_history(args.csv)
    cpt = learn_personalized_cpt(df, args.user, args.shrink_k)
    out = args.out or os.path.join(os.path.dirname(__file__), f'personalized_emission_cpt_{args.user}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(cpt, f, ensure_ascii=False, indent=2)
    print('Saved', out)

if __name__ == '__main__':
    main()
