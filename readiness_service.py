#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Readiness Service: unified JSON interface to dynamic_model.

Usage (as a library):
  from readiness_service import compute_readiness_from_payload
  result = compute_readiness_from_payload(payload)

Payload JSON (example minimal):
{
  "user_id": "u001",
  "date": "2025-09-05",
  "gender": "男性",                 # 可选，默认男性
  "previous_state_probs": {...},     # 可选，不传则用模型默认
  "training_load": "高",            # 昨天训练强度
  "recent_training_loads": ["高","高","中","高","高","极高","中","高"],  # 可选（连续训练惩罚）
  "objective": {
    "sleep_performance_state": "medium",
    "restorative_sleep": "medium",
    "hrv_trend": "stable"
  },
  "hooper": {"fatigue": 3, "soreness": 3, "stress": 2, "sleep": 3},
  "journal_today": {"is_sick": false, "is_injured": false,
                     "high_stress_event_today": false, "meditation_done_today": false}
}

Notes
- 缺失字段会被忽略（例如没有 journal_today 就不加）。
- 若同日需要突发更新（如下午标记 is_sick=True），可再次调用本函数，
  传相同 user_id/date，并在 journal_today 中设置 is_sick=True；
  函数会基于同日先验重新整合证据给出新的后验（服务层可自行做幂等/缓存）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from dynamic_model import DailyReadinessManager


def _merge_evidence(target: Dict[str, Any], src: Optional[Dict[str, Any]]) -> None:
    if not src:
        return
    for k, v in src.items():
        if v is not None:
            target[k] = v


def compute_readiness_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = payload.get('user_id') or 'default_user'
    date = payload.get('date') or '1970-01-01'
    gender = payload.get('gender') or '男性'
    prev_probs = payload.get('previous_state_probs')

    manager = DailyReadinessManager(
        user_id=user_id,
        date=date,
        previous_state_probs=prev_probs,
        gender=gender,
    )

    # Prior causal inputs
    causal_inputs: Dict[str, Any] = {}
    if payload.get('training_load') is not None:
        causal_inputs['training_load'] = payload['training_load']
    if isinstance(payload.get('recent_training_loads'), list):
        causal_inputs['recent_training_loads'] = payload['recent_training_loads']

    prior = manager.calculate_today_prior(causal_inputs)

    # Build today's evidence in steps: objective -> hooper -> journal
    ev = {}
    objective = payload.get('objective') or {}
    hooper = payload.get('hooper') or {}
    journal_today = payload.get('journal_today') or {}

    # Map hooper keys to model keys
    hooper_mapped = {}
    if 'fatigue' in hooper: hooper_mapped['fatigue_hooper'] = hooper['fatigue']
    if 'soreness' in hooper: hooper_mapped['soreness_hooper'] = hooper['soreness']
    if 'stress' in hooper: hooper_mapped['stress_hooper'] = hooper['stress']
    if 'sleep' in hooper: hooper_mapped['sleep_hooper'] = hooper['sleep']

    # Stepwise updates
    result_updates = []
    if objective:
        r1 = manager.add_evidence_and_update(objective)
        result_updates.append(r1)
    if hooper_mapped:
        r2 = manager.add_evidence_and_update(hooper_mapped)
        result_updates.append(r2)
    if journal_today:
        r3 = manager.add_evidence_and_update(journal_today)
        result_updates.append(r3)

    # Final summary
    summary = manager.get_daily_summary()

    return {
        'user_id': user_id,
        'date': date,
        'gender': gender,
        'prior_probs': summary['prior_probs'],
        'final_posterior_probs': summary['final_posterior_probs'],
        'final_readiness_score': summary['final_readiness_score'],
        'final_diagnosis': summary['final_diagnosis'],
        'update_history': summary['update_history'],
        'evidence_pool': summary['evidence_pool'],
        # 为次日准备：可将今天的后验作为明日 previous_state_probs
        'next_previous_state_probs': summary['final_posterior_probs'],
    }


if __name__ == '__main__':
    # 简易演示：从标准输入读取JSON，输出结果（可用于本地测试或接入网关）
    import sys, json
    raw = sys.stdin.read()
    payload = json.loads(raw)
    res = compute_readiness_from_payload(payload)
    print(json.dumps(res, ensure_ascii=False, indent=2))

