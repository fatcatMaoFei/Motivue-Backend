#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10天动态准备度模拟（使用 dynamic_model.DailyReadinessManager 原算法）

日程（第1–10天）：
- 第1天：高强度
- 第2天：高强度 + 昨晚饮酒（作为“昨天短期行为”进入先验）
- 第3天：高强度
- 第4天：休息（低强度）
- 第5天：高强度
- 第6天：当日生病（作为“今天持续状态”进入后验，并对次日先验有持续影响）
- 第7–10天：高强度（无额外日志）

说明：
- 严格 import 并调用 dynamic_model 中的算法；先验按乘法机制整合训练负荷与昨日日志因子。
- 每天把“昨天短期行为”写入昨日日志，影响今日先验；把“今天持续状态”（如生病）写入今日日志，影响今日后验。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from dynamic_model import DailyReadinessManager


def fmt_probs(probs: Dict[str, float]) -> str:
    states = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']
    return " | ".join(f"{s}: {probs.get(s, 0):.3f}" for s in states)


def run_day(
    user_id: str,
    date_str: str,
    prev_probs: Optional[Dict[str, float]],
    training_load_yesterday: str,
    yesterday_short_term: Optional[Dict[str, Any]] = None,
    yesterday_persistent: Optional[Dict[str, Any]] = None,
    today_sleep_data: Optional[Dict[str, Any]] = None,
    hooper_data: Optional[Dict[str, Any]] = None,
    today_journal: Optional[Dict[str, Any]] = None,
    additional_symptoms: Optional[Dict[str, Any]] = None,
    today_persistent: Optional[Dict[str, Any]] = None,
    gender: str = '男性',
) -> Dict[str, Any]:
    """Run one day with full inputs: yesterday logs (short-term/persistent), compute prior, then add today's evidence in steps."""
    manager = DailyReadinessManager(
        user_id=user_id,
        date=date_str,
        previous_state_probs=prev_probs,
        gender=gender,
    )

    # Populate yesterday journal (affects today's prior)
    if yesterday_short_term or yesterday_persistent:
        y_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        if yesterday_short_term:
            manager.journal_manager.add_journal_entry(user_id, y_date, "short_term_behaviors", yesterday_short_term)
        if yesterday_persistent:
            manager.journal_manager.add_journal_entry(user_id, y_date, "persistent_status", yesterday_persistent)

    # Optionally set today's persistent status (affects posterior today, and prior tomorrow via persistence)
    if today_persistent:
        manager.journal_manager.add_journal_entry(user_id, date_str, "persistent_status", today_persistent)

    # Compute prior using yesterday training load
    prior = manager.calculate_today_prior({
        'training_load': training_load_yesterday
    })

    # Prior score
    prior_score = manager._get_readiness_score(prior)

    # Defaults for evidence blocks if not provided
    if today_sleep_data is None:
        today_sleep_data = {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'}
    if hooper_data is None:
        hooper_data = {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 2, 'sleep_hooper': 3}
    if today_journal is None:
        today_journal = {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False}
    if additional_symptoms is None:
        additional_symptoms = {'subjective_fatigue': 'low', 'gi_symptoms': 'none', 'nutrition': 'adequate'}

    # Stepwise posterior updates (mirroring test_runner flow)
    manager.add_evidence_and_update(today_sleep_data)
    manager.add_evidence_and_update(hooper_data)
    manager.add_evidence_and_update(today_journal)
    update = manager.add_evidence_and_update(additional_symptoms)

    return {
        'date': date_str,
        'prior_probs': prior,
        'prior_score': prior_score,
        'posterior_probs': update['posterior_probs'],
        'posterior_score': update['readiness_score'],
        'diagnosis': update['diagnosis'],
        'evidence_pool_size': update['evidence_pool_size'],
        'next_prev_probs': update['posterior_probs'],
    }


def main():
    user_id = 'athlete_sim'
    start_date = datetime.strptime('2025-09-01', '%Y-%m-%d')
    gender = '男性'

    # Initial previous state distribution (can be tuned)
    prev_probs = {
        'Peak': 0.15, 'Well-adapted': 0.60, 'FOR': 0.20, 'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0
    }

    # 日程定义（昨日训练强度、昨日日志短期/持续、今日证据与持续状态）
    # 训练强度键需与 dynamic_model.TRAINING_LOAD_CPT 匹配：此处用 '高'（高强度）、'低'（休息）。
    schedule: List[Dict[str, Any]] = [
        # Day 1
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 2, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'low', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度'
        },
        # Day 2 (yesterday high + alcohol consumed)
        {
            'train_yesterday': '高',
            'y_short_term': {'alcohol_consumed': True, 'screen_before_bed': True, 'late_meal': True},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 2, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'low', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度 + 酒精(昨晚)'
        },
        # Day 3
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 2, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'low', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度'
        },
        # Day 4 (rest day -> use low as yesterday training load)
        {
            'train_yesterday': '低',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'good', 'restorative_sleep': 'high', 'hrv_trend': 'rising'},
            'hooper': {'fatigue_hooper': 2, 'soreness_hooper': 2, 'stress_hooper': 2, 'sleep_hooper': 2},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': True},
            'additional': {'subjective_fatigue': 'low', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '休息日(低)'
        },
        # Day 5
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 3, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'medium', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度'
        },
        # Day 6 (sick today)
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'poor', 'restorative_sleep': 'low', 'hrv_trend': 'slight_decline'},
            'hooper': {'fatigue_hooper': 5, 'soreness_hooper': 4, 'stress_hooper': 4, 'sleep_hooper': 5},
            'today_journal': {'is_sick': True, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'high', 'gi_symptoms': 'mild', 'nutrition': 'inadequate_mild'},
            'today_persistent': {'is_sick': True},
            'label': '生病(今日)'
        },
        # Day 7–10: 高强度（无额外日志）
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 3, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'medium', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度'
        },
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 3, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'medium', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度'
        },
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'good', 'restorative_sleep': 'high', 'hrv_trend': 'rising'},
            'hooper': {'fatigue_hooper': 2, 'soreness_hooper': 2, 'stress_hooper': 2, 'sleep_hooper': 2},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': True},
            'additional': {'subjective_fatigue': 'low', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '恢复(好睡眠)'
        },
        {
            'train_yesterday': '高',
            'y_short_term': {},
            'y_persistent': {},
            'today_sleep': {'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'},
            'hooper': {'fatigue_hooper': 3, 'soreness_hooper': 3, 'stress_hooper': 3, 'sleep_hooper': 3},
            'today_journal': {'is_sick': False, 'is_injured': False, 'high_stress_event_today': False, 'meditation_done_today': False},
            'additional': {'subjective_fatigue': 'medium', 'gi_symptoms': 'none', 'nutrition': 'adequate'},
            'today_persistent': {},
            'label': '高强度'
        },
    ]

    print("\n================ 10-Day Dynamic Readiness Simulation ================")
    print(f"User: {user_id} | Gender: {gender}")
    print("Schedule:")
    for i, d in enumerate(schedule, 1):
        print(f"  Day {i}: {d['label']} | 昨训: {d['train_yesterday']} | 昨短期: {list(d['y_short_term'].keys()) or '-'} | 今持续: {list(d['today_persistent'].keys()) or '-'}")

    day_results: List[Dict[str, Any]] = []

    for i, day in enumerate(schedule):
        date_str = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        result = run_day(
            user_id=user_id,
            date_str=date_str,
            prev_probs=prev_probs,
            training_load_yesterday=day['train_yesterday'],
            yesterday_short_term=day['y_short_term'],
            yesterday_persistent=day.get('y_persistent', {}),
            today_sleep_data=day.get('today_sleep'),
            hooper_data=day.get('hooper'),
            today_journal=day.get('today_journal'),
            additional_symptoms=day.get('additional'),
            today_persistent=day['today_persistent'],
            gender=gender,
        )
        prev_probs = result['next_prev_probs']
        day_results.append(result)

        # Print concise day summary
        print(f"\n-- Day {i+1} ({date_str}) | {day['label']} --")
        print(f"Prior Score: {result['prior_score']:>3d} | Prior: {fmt_probs(result['prior_probs'])}")
        print(f"Post  Score: {result['posterior_score']:>3d} | Post : {fmt_probs(result['posterior_probs'])} | Dx: {result['diagnosis']}")

    # Final aggregate summary
    print("\n=========================== Summary ===========================")
    priors = [r['prior_score'] for r in day_results]
    posts = [r['posterior_score'] for r in day_results]
    print("Prior scores:", priors)
    print("Post  scores:", posts)


if __name__ == '__main__':
    main()
