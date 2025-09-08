#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from readiness.service import compute_readiness_from_payload


def run_5_days():
    user_id = 'sim_user'
    gender = '男性'
    start = datetime.strptime('2025-09-01', '%Y-%m-%d')

    # Day plan (today's training; affects next day's prior). For each morning we also set
    # whether there was drinking last night (affects today's prior via journal_yesterday).
    # D1: train=高 (to affect D2), D2: train=高 + drank_last_night=True (affect D3 and D2 prior),
    # D3: train=高, D4: 低 (rest), D5: 中
    plan = [
        {'train': '高', 'drank_last_night': False},
        {'train': '高', 'drank_last_night': True},
        {'train': '高', 'drank_last_night': False},
        {'train': '低', 'drank_last_night': False},
        {'train': '中', 'drank_last_night': False},
    ]

    # Initial previous_state_probs for Day 1 (Peak, Well, FOR, Acute, NFOR, OTS)
    prev_probs: Optional[Dict[str, float]] = {
        'Peak': 0.10,
        'Well-adapted': 0.50,
        'FOR': 0.30,
        'Acute Fatigue': 0.10,
        'NFOR': 0.0,
        'OTS': 0.0,
    }

    def derive_objective(prev_training: str, drank: bool) -> Dict[str, Any]:
        # Map yesterday's training + drinking to today's morning objective states
        if prev_training in ['高', '极高']:
            return {
                'sleep_performance_state': 'poor' if drank else 'medium',
                'restorative_sleep': 'low' if drank else 'medium',
                'hrv_trend': 'significant_decline' if drank else 'slight_decline',
            }
        if prev_training == '中':
            return {
                'sleep_performance_state': 'medium',
                'restorative_sleep': 'medium',
                'hrv_trend': 'stable',
            }
        # 低/无 → 恢复较好
        return {
            'sleep_performance_state': 'good' if prev_training == '低' else 'medium',
            'restorative_sleep': 'high' if prev_training == '低' else 'medium',
            'hrv_trend': 'rising' if prev_training == '低' else 'stable',
        }

    def clamp(v: int) -> int:
        return max(1, min(7, int(v)))

    def derive_hooper(prev_training: str, drank: bool) -> Dict[str, Any]:
        if prev_training in ['高', '极高']:
            fatigue = 5
            soreness = 5
            stress = 3
            sleep = 3
            if drank:
                fatigue += 1; sleep += 1; stress += 1
        elif prev_training == '中':
            fatigue = 4; soreness = 4; stress = 3; sleep = 3
        elif prev_training == '低':
            fatigue = 2; soreness = 2; stress = 2; sleep = 2
        else:  # 无
            fatigue = 3; soreness = 2; stress = 2; sleep = 3
        return {'fatigue': clamp(fatigue), 'soreness': clamp(soreness), 'stress': clamp(stress), 'sleep': clamp(sleep)}

    print("\n===== 5-Day Readiness Simulation (service API) =====")
    for i, day in enumerate(plan):
        date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        # Yesterday's training for today's morning
        prev_training = '无' if i == 0 else plan[i-1]['train']
        drank = plan[i]['drank_last_night']
        payload = {
            'user_id': user_id,
            'date': date,
            'gender': gender,
            # training_load here is "yesterday's load" for computing today's prior
            'training_load': prev_training,
            'objective': derive_objective(prev_training, drank),
            'hooper': derive_hooper(prev_training, drank),
        }
        if prev_probs is not None:
            payload['previous_state_probs'] = prev_probs
        # 酒精影响今日先验（表示昨晚饮酒）：作为 journal_yesterday 传入
        if drank:
            payload['journal'] = {'alcohol_consumed': True}

        res = compute_readiness_from_payload(payload)

        # Print day summary
        print(f"\n-- Day {i+1} ({date}) | 昨日训练={prev_training} | 昨晚饮酒={'是' if drank else '否'} --")
        # Prior summary
        prior = res['prior_probs']
        prior_str = ' | '.join([f"{k}:{prior.get(k,0):.3f}" for k in ['Peak','Well-adapted','FOR','Acute Fatigue','NFOR','OTS']])
        print(f"Prior: {prior_str}")
        print(f"Obj: {payload['objective']} | Hooper: {payload['hooper']}")
        print(f"Final: score={res['final_readiness_score']}/100 | dx={res['final_diagnosis']}")

        # Chain for next day
        prev_probs = res['next_previous_state_probs']


if __name__ == '__main__':
    run_5_days()
