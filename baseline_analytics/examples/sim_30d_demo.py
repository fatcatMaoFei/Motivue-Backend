from __future__ import annotations

import json
from pathlib import Path
from pprint import pprint

from baseline_analytics import compare_today_vs_baseline, compare_recent_vs_previous


def main() -> None:
    here = Path(__file__).parent
    payload_path = here / 'sim_30d_payload.json'
    payload = json.loads(payload_path.read_text(encoding='utf-8'))

    # Today (Day 30) vs previous windows (7, 28)
    res_today = compare_today_vs_baseline(payload, windows=[7, 28])

    # Recent 7-day vs previous 7-day
    res_period = compare_recent_vs_previous(payload, windows=[7])

    print('--- Today vs Baseline (Day 30 vs prev 7/28) ---')
    for k in ['sleep_hours', 'sleep_eff', 'rest_ratio', 'hrv_rmssd', 'training_au']:
        v = res_today.get(k)
        if not v:
            continue
        w = v.get('windows', v)
        print(f'[{k}]')
        for win in [7, 28]:
            if win in w and w[win]['baseline_avg'] is not None:
                m = w[win]
                pct = m['pct_change']
                pct_s = f"{pct:.2f}%" if pct is not None else 'NA'
                print(f"  win={win}: today={m['today']} baseline_avg={m['baseline_avg']} pct_change={pct_s} dir={m['direction']}")

    print('\n--- Recent vs Previous (last 7 vs prev 7) ---')
    for k in ['sleep_hours', 'sleep_eff', 'rest_ratio', 'hrv_rmssd', 'training_au']:
        v = res_period.get(k)
        if not v:
            continue
        w = v.get('windows', v)
        m = w.get(7)
        if m:
            pct = m['pct_change']
            pct_s = f"{pct:.2f}%" if pct is not None else 'NA'
            print(f"[{k}] last_avg={m['last_avg']} prev_avg={m['prev_avg']} pct_change={pct_s} dir={m['direction']}")


if __name__ == '__main__':
    main()

