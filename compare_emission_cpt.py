#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys

CORE = [
    'hrv_trend',
    'sleep_performance',
    'restorative_sleep',
    'subjective_fatigue',
    'muscle_soreness',
    'subjective_stress',
    'subjective_sleep',
]

STATES = ['Peak','Well-adapted','FOR','Acute Fatigue','NFOR','OTS']

def avg_l1(a,b,vars_list):
    tot=0.0; cnt=0
    for var in vars_list:
        if var not in a or var not in b: continue
        cats = a[var].keys()
        for c in cats:
            for s in STATES:
                x = float(a[var][c].get(s,0.0))
                y = float(b[var][c].get(s,0.0))
                tot += abs(x-y); cnt += 1
    return (tot/cnt if cnt else 0.0, cnt)

def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_emission_cpt.py <old.json> <new.json>")
        sys.exit(1)
    old_path, new_path = sys.argv[1], sys.argv[2]
    with open(old_path,'r',encoding='utf-8') as f:
        old = json.load(f)
    with open(new_path,'r',encoding='utf-8') as f:
        new = json.load(f)
    avg, cnt = avg_l1(old, new, CORE)
    print(f'Average L1 diff over CORE vars ({cnt} cells): {avg:.6f}')
    for var in CORE:
        if var not in old or var not in new: continue
        tot=0.0; cnt=0
        for c in old[var].keys():
            for s in STATES:
                tot += abs(float(old[var][c].get(s,0.0)) - float(new[var][c].get(s,0.0)))
                cnt += 1
        print(f'  {var:20s}: {tot/cnt if cnt else 0.0:.6f}')

if __name__ == '__main__':
    main()

