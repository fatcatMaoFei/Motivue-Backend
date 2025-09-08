#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示 Hooper 连续映射（贝塞尔） vs 旧离散三档映射的差异。
对比 subjective_fatigue 在分数=3 与 5 时：
- 旧方案：直接用分类锚点（3=medium, 5=high）
- 新方案：1..7 平滑映射为连续似然（贝塞尔权重混合 low/med/high 锚点）

其他证据固定为“中等”，先验用“昨天训练=中”，初始分布=[0.1,0.5,0.3,0.1,0,0]
"""

from __future__ import annotations

from typing import Dict

from readiness.engine import ReadinessEngine
from readiness.hooper import hooper_to_state_likelihood


STATES = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']


def build_engine() -> ReadinessEngine:
    eng = ReadinessEngine(
        user_id="demo_user",
        date="2025-09-10",
        previous_state_probs={'Peak': 0.10, 'Well-adapted': 0.50, 'FOR': 0.30, 'Acute Fatigue': 0.10, 'NFOR': 0.0, 'OTS': 0.0},
        gender='男性',
    )
    eng.calculate_today_prior({'training_load': '中'})
    # 固定“今天早晨”客观为中等
    eng.add_evidence_and_update({'sleep_performance_state': 'medium', 'restorative_sleep': 'medium', 'hrv_trend': 'stable'})
    return eng


def run_discrete(score: int) -> Dict:
    eng = build_engine()
    # 旧离散：1..2=low, 3..4=medium, 5..7=high
    if score <= 2:
        cat = 'low'
    elif score <= 4:
        cat = 'medium'
    else:
        cat = 'high'
    r = eng.add_evidence_and_update({'subjective_fatigue': cat})
    return {
        'score': r['readiness_score'],
        'posterior': r['posterior_probs']
    }


def run_continuous(score: int) -> Dict:
    eng = build_engine()
    # 新连续：传 1..7 数值，内部做贝塞尔连续混合
    r = eng.add_evidence_and_update({'fatigue_hooper': score})
    return {
        'score': r['readiness_score'],
        'posterior': r['posterior_probs']
    }


def fmt_probs(p: Dict[str, float]) -> str:
    return ' | '.join(f"{s}:{p.get(s,0):.3f}" for s in STATES)


def main():
    for s in [1, 7]:
        like = hooper_to_state_likelihood('subjective_fatigue', s)
        old = run_discrete(s)
        new = run_continuous(s)
        print("\n==========================")
        print(f"subjective_fatigue Hooper={s}")
        print("- 连续似然(贝塞尔)向量:")
        print("  ", fmt_probs(like))
        print("- 旧离散后验: ")
        print(f"  分数={old['score']}/100 | 后验= {fmt_probs(old['posterior'])}")
        print("- 新连续后验: ")
        print(f"  分数={new['score']}/100 | 后验= {fmt_probs(new['posterior'])}")


if __name__ == '__main__':
    main()

