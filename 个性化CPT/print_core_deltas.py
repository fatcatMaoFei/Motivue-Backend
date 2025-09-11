#!/usr/bin/env python3
import json
from readiness.constants import EMISSION_CPT as G

STATES=['Peak','Well-adapted','FOR','Acute Fatigue','NFOR','OTS']
CORE=['apple_sleep_score','restorative_sleep','hrv_trend','sleep_performance','nutrition','gi_symptoms']

def avg(C, var):
    if var not in C or var not in G:
        return 0.0
    total=0.0; cnt=0
    for cat in C[var].keys():
        for s in STATES:
            a=float(G[var].get(cat,{}).get(s,0.0)); b=float(C[var].get(cat,{}).get(s,0.0))
            total+=abs(a-b); cnt+=1
    return total/cnt if cnt else 0.0

def main(path):
    with open(path,'r',encoding='utf-8') as f:
        C=json.load(f)
    for v in CORE:
        print(v, f"avg_L1={avg(C,v):.4f}")

if __name__=='__main__':
    import sys
    main(sys.argv[1])