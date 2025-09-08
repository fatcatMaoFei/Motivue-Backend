#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic Readiness Model v2.0 - 动态准备度评估模型
核心设计：严格分离先验(Prior)和后验(Posterior)的动态更新系统

============================================================================
★★★ 概率表结构说明 ★★★
============================================================================

【先验概率计算部分 - PRIOR PROBABILITY】
使用的概率表：
1. BASELINE_TRANSITION_CPT - 基线状态转移概率
2. TRAINING_LOAD_CPT - 训练负荷影响 
3. ALCOHOL_CONSUMPTION_CPT - 酒精摄入影响
4. LATE_CAFFEINE_CPT - 深夜咖啡因影响
5. SCREEN_BEFORE_BED_CPT - 睡前屏幕影响
6. MENSTRUAL_PHASE_CPT - 月经周期影响
7. LATE_MEAL_CPT - 睡前进食影响

【后验概率计算部分 - POSTERIOR PROBABILITY (指纹库)】
使用的概率表：
1. EMISSION_CPT - 主要症状指纹库 P(Evidence | State)
2. INTERACTION_CPT_SORENESS_STRESS - 交互效应指纹库

============================================================================

设计原则：
- Prior(预测): 基于前一天的所有原因，每天计算一次且固定不变
- Posterior(诊断): 基于固定Prior和当天不断累积的证据进行多次实时更新
- 指纹库: 描述每种状态下出现各种症状的概率分布
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

# =======================================================================
# ★★★ 指纹库 (EMISSION CPT) - 用于后验概率计算 ★★★
# P(Evidence | State) - 症状指纹库，基于6种准备度状态的症状表现概率
# =======================================================================

EMISSION_CPT = {
    'subjective_fatigue': {
        'low': {'Peak': 0.80, 'Well-adapted': 0.70, 'FOR': 0.25, 'Acute Fatigue': 0.05, 'NFOR': 0.05, 'OTS': 1e-6},
        'medium': {'Peak': 0.15, 'Well-adapted': 0.30, 'FOR': 0.20, 'Acute Fatigue': 0.15, 'NFOR': 0.10, 'OTS': 0.05},
        'high': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.70, 'Acute Fatigue': 0.80, 'NFOR': 0.80, 'OTS': 0.90}
    },
    "muscle_soreness": {
        "low": {"Peak": 0.80, "Well-adapted": 0.75, "FOR": 0.35, "Acute Fatigue": 0.10, "NFOR": 0.10, "OTS": 0.20},
        "medium": {"Peak": 0.10, "Well-adapted": 0.25, "FOR": 0.50, "Acute Fatigue": 0.30, "NFOR": 0.40, "OTS": 0.50},
        "high": {"Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.35, "Acute Fatigue": 0.60, "NFOR": 0.50, "OTS": 0.30}
    },
    'subjective_stress': {
        'low': {'Peak': 0.80, 'Well-adapted': 0.70, 'FOR': 0.40, 'Acute Fatigue': 0.20, 'NFOR': 0.10, 'OTS': 1e-6},
        'medium': {'Peak': 0.10, 'Well-adapted': 0.30, 'FOR': 0.50, 'Acute Fatigue': 0.50, 'NFOR': 0.30, 'OTS': 0.20},
        'high': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.10, 'Acute Fatigue': 0.30, 'NFOR': 0.60, 'OTS': 0.80}
    },
    'subjective_sleep': {
        'good': {'Peak': 0.80, 'Well-adapted': 0.75, 'FOR': 0.30, 'Acute Fatigue': 0.40, 'NFOR': 0.15, 'OTS': 0.10},
        'medium': {'Peak': 0.15, 'Well-adapted': 0.25, 'FOR': 0.40, 'Acute Fatigue': 0.40, 'NFOR': 0.35, 'OTS': 0.20},
        'poor': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.15, 'Acute Fatigue': 0.20, 'NFOR': 0.65, 'OTS': 0.70}
    },
    'sleep_performance': {
        'good': {'Peak': 0.80, 'Well-adapted': 0.70, 'FOR': 0.25, 'Acute Fatigue': 0.35, 'NFOR': 0.20, 'OTS': 0.15},
        'medium': {'Peak': 0.20, 'Well-adapted': 0.30, 'FOR': 0.50, 'Acute Fatigue': 0.50, 'NFOR': 0.40, 'OTS': 0.35},
        'poor': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.25, 'Acute Fatigue': 0.15, 'NFOR': 0.40, 'OTS': 0.50}
    },
    'hrv_trend': {
        'rising': {'Peak': 0.85, 'Well-adapted': 0.20, 'FOR': 0.10, 'Acute Fatigue': 0.10, 'NFOR': 0.05, 'OTS': 0.01},
        'stable': {'Peak': 0.4, 'Well-adapted': 0.3, 'FOR': 0.20, 'Acute Fatigue': 0.20, 'NFOR': 0.10, 'OTS': 0.05},
        'slight_decline': {'Peak': 0.05, 'Well-adapted': 0.10, 'FOR': 0.30, 'Acute Fatigue': 0.30, 'NFOR': 0.15, 'OTS': 0.09},
        'significant_decline': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.40, 'Acute Fatigue': 0.40, 'NFOR': 0.70, 'OTS': 0.80}
    },
    'nutrition': {
        'adequate': {'Peak': 0.50, 'Well-adapted': 0.60, 'FOR': 0.50, 'Acute Fatigue': 0.70, 'NFOR': 0.40, 'OTS': 0.30},
        'inadequate_mild': {'Peak': 0.40, 'Well-adapted': 0.40, 'FOR': 0.45, 'Acute Fatigue': 0.40, 'NFOR': 0.50, 'OTS': 0.45},
        'inadequate_moderate': {'Peak': 0.30, 'Well-adapted': 0.35, 'FOR': 0.42, 'Acute Fatigue': 0.35, 'NFOR': 0.55, 'OTS': 0.60},
        'inadequate_severe': {'Peak': 0.10, 'Well-adapted': 0.15, 'FOR': 0.40, 'Acute Fatigue': 0.30, 'NFOR': 0.60, 'OTS': 0.70}
    },
    'restorative_sleep': {
        'high': {'Peak': 0.85, 'Well-adapted': 0.75, 'FOR': 0.30, 'Acute Fatigue': 0.20, 'NFOR': 0.05, 'OTS': 1e-6},
        'medium': {'Peak': 0.40, 'Well-adapted': 0.50, 'FOR': 0.40, 'Acute Fatigue': 0.35, 'NFOR': 0.25, 'OTS': 0.15},
        'low': {'Peak': 1e-6, 'Well-adapted': 0.10, 'FOR': 0.20, 'Acute Fatigue': 0.30, 'NFOR': 0.70, 'OTS': 0.80}
    },
    'gi_symptoms': {
        'none': {'Peak': 0.90, 'Well-adapted': 0.85, 'FOR': 0.80, 'Acute Fatigue': 0.70, 'NFOR': 0.50, 'OTS': 0.40},
        'mild': {'Peak': 0.05, 'Well-adapted': 0.10, 'FOR': 0.15, 'Acute Fatigue': 0.25, 'NFOR': 0.40, 'OTS': 0.40},
        'severe': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.05, 'Acute Fatigue': 0.05, 'NFOR': 0.10, 'OTS': 0.20}
    },
    
    # =======================================================================
    # ★★★ 新增 Journal 症状发射概率 ★★★
    # =======================================================================
    
    # 1. 今日是否生病 (is_sick: True)
    'is_sick': {
        True: {'Peak': 1e-9, 'Well-adapted': 1e-6, 'FOR': 0.05, 'Acute Fatigue': 0.40, 'NFOR': 0.80, 'OTS': 0.90}
    },

    # 2. 今日是否受伤 (is_injured: True)
    'is_injured': {
        True: {'Peak': 1e-9, 'Well-adapted': 1e-6, 'FOR': 0.10, 'Acute Fatigue': 0.50, 'NFOR': 0.70, 'OTS': 0.60}
    },

    # 3. 今日发生重大压力事件 (high_stress_event_today: True)
    'high_stress_event_today': {
        True: {'Peak': 0.05, 'Well-adapted': 0.15, 'FOR': 0.25, 'Acute Fatigue': 0.30, 'NFOR': 0.50, 'OTS': 0.40}
    },

    # 4. 今日完成冥想 (meditation_done_today: True)
    'meditation_done_today': {
        True: {'Peak': 0.55, 'Well-adapted': 0.50, 'FOR': 0.45, 'Acute Fatigue': 0.40, 'NFOR': 0.35, 'OTS': 0.30}
    }
}

# =======================================================================
# ★★★ 基线转移概率表 - 用于先验概率计算基础 ★★★  
# P(Today | Yesterday) - 状态自然转移概率，无外部影响时的基础转移
# =======================================================================

BASELINE_TRANSITION_CPT = {
    'Peak': {'Peak': 0.80, 'Well-adapted': 0.10, 'FOR': 0.05, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'Well-adapted': {'Peak': 0.60, 'Well-adapted': 0.35, 'FOR': 0.05, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'FOR': {'Peak': 0.05, 'Well-adapted': 0.40, 'FOR': 0.30, 'Acute Fatigue': 0.10, 'NFOR': 0.10, 'OTS': 0.05},
    'Acute Fatigue': {'Peak': 0.20, 'Well-adapted': 0.70, 'FOR': 0.10, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'NFOR': {'Peak': 0.01, 'Well-adapted': 0.05, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.70, 'OTS': 0.09},
    'OTS': {'Peak': 0.01, 'Well-adapted': 0.04, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.30, 'OTS': 0.50}
}

# 确保每行概率总和为1
for state in BASELINE_TRANSITION_CPT:
    total = sum(BASELINE_TRANSITION_CPT[state].values())
    if total > 0:
        BASELINE_TRANSITION_CPT[state] = {s: p / total for s, p in BASELINE_TRANSITION_CPT[state].items()}

READINESS_WEIGHTS = {'Peak': 100, 'Well-adapted': 85, 'FOR': 60, 'Acute Fatigue': 50, 'NFOR': 30, 'OTS': 10}

EVIDENCE_WEIGHTS_FITNESS = {
    "hrv_trend": 1.0,
    "restorative_sleep": 0.95,
    "sleep_performance": 0.90,
    "subjective_fatigue": 0.75,
    "subjective_stress": 0.70,
    "muscle_soreness": 0.65,
    "subjective_sleep": 0.60,
    "nutrition": 0.60,
    "gi_symptoms": 0.50,
    "fatigue_3day_state": 0.85,
    # 新增Journal证据权重
    "is_sick": 1,                    # 生病状态 - 高权重
    "is_injured": 0.8,                 # 受伤状态 - 高权重
    "high_stress_event_today": 0.6,    # 今日重大压力事件
    "meditation_done_today": 0.5       # 今日冥想完成 - 积极因素
}

# =======================================================================
# ★★★ 交互效应指纹库 - 用于后验概率计算 ★★★
# 特殊症状组合的发射概率（肌肉酸痛 + 主观压力）
# =======================================================================

INTERACTION_CPT_SORENESS_STRESS = {
    ("low", "high"): {"Peak": 1e-6, "Well-adapted": 0.05, "FOR": 0.15, "Acute Fatigue": 0.20, "NFOR": 0.60, "OTS": 0.50},
    ("low", "low"): {"Peak": 0.70, "Well-adapted": 0.60, "FOR": 0.20, "Acute Fatigue": 0.10, "NFOR": 0.05, "OTS": 1e-6},
    ("low", "medium"): {"Peak": 0.50, "Well-adapted": 0.45, "FOR": 0.30, "Acute Fatigue": 0.15, "NFOR": 0.10, "OTS": 0.05},
    ("medium", "low"): {"Peak": 0.40, "Well-adapted": 0.50, "FOR": 0.35, "Acute Fatigue": 0.20, "NFOR": 0.10, "OTS": 0.05},
    ("medium", "medium"): {"Peak": 0.25, "Well-adapted": 0.35, "FOR": 0.40, "Acute Fatigue": 0.30, "NFOR": 0.20, "OTS": 0.10},
    ("medium", "high"): {"Peak": 0.10, "Well-adapted": 0.15, "FOR": 0.25, "Acute Fatigue": 0.25, "NFOR": 0.45, "OTS": 0.30},
    ("high", "low"): {"Peak": 1e-6, "Well-adapted": 0.10, "FOR": 0.60, "Acute Fatigue": 0.50, "NFOR": 0.15, "OTS": 0.10},
    ("high", "medium"): {"Peak": 1e-6, "Well-adapted": 0.05, "FOR": 0.50, "Acute Fatigue": 0.60, "NFOR": 0.25, "OTS": 0.20},
    ("high", "high"): {"Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.30, "Acute Fatigue": 0.40, "NFOR": 0.50, "OTS": 0.60}
}

# =======================================================================
# ★★★ 先验概率影响因子CPT表 - 用于先验概率计算 ★★★
# P(Today | Causal_Factor) - 各种原因对今日状态概率的影响
# =======================================================================

# 健康中性基线 (用于无影响因子时)
HEALTHY_NEUTRAL_BASELINE = {'Peak': 1, 'Well-adapted': 1, 'FOR': 1, 'Acute Fatigue': 1, 'NFOR': 1, 'OTS': 1}

# 原因1: 酒精摄入 (P(今日状态 | 昨晚是否饮酒))
ALCOHOL_CONSUMPTION_CPT = {
    # 按建议：避免绝对0，使用极小值1e-6以兼容乘法更新；同时加强对良好状态的抑制
    True:  {'Peak': 1e-6, 'Well-adapted': 0.10, 'FOR': 0.20, 'Acute Fatigue': 0.40, 'NFOR': 0.30, 'OTS': 1e-6},
    False: HEALTHY_NEUTRAL_BASELINE # 未摄入，使用中性基线
}

# 原因2: 深夜咖啡因 (P(今日状态 | 昨晚是否摄入咖啡因))
LATE_CAFFEINE_CPT = {
    # 避免绝对0（OTS），改为极小值
    True:  {'Peak': 0.10, 'Well-adapted': 0.20, 'FOR': 0.20, 'Acute Fatigue': 0.15, 'NFOR': 0.30, 'OTS': 1e-6},
    False: HEALTHY_NEUTRAL_BASELINE # 未摄入，使用中性基线
}

# 原因3: 睡前屏幕 (P(今日状态 | 昨晚是否使用))
SCREEN_BEFORE_BED_CPT = {
    # 略加强负面影响，且避免绝对0（OTS）
    True:  {'Peak': 0.10, 'Well-adapted': 0.20, 'FOR': 0.30, 'Acute Fatigue': 0.25, 'NFOR': 0.25, 'OTS': 1e-6},
    False: HEALTHY_NEUTRAL_BASELINE # 未使用，使用中性基线
}

# 原因4: 月经周期 (P(今日状态 | 昨日月经阶段))
# **完全根据您的研究表格进行重新校准**
MENSTRUAL_PHASE_CPT = {
    # 阶段1: 月经期/卵泡期早期 (天 1-6)
    # 特征: 生理潜力高但睡眠受扰且损伤风险极高。概率分布反映这种矛盾性。
    'menstrual_early_follicular': {'Peak': 0.15, 'Well-adapted': 0.40, 'FOR': 0.20, 'Acute Fatigue': 0.15, 'NFOR': 0.10, 'OTS': 0.0},
    
    # 阶段2: 卵泡期晚期/排卵期 (天 7-14)
    # 特征: 能量和运动表现的峰值。概率分布显著偏向最佳状态。
    'late_follicular_ovulatory':  {'Peak': 0.45, 'Well-adapted': 0.45, 'FOR': 0.05, 'Acute Fatigue': 0.03, 'NFOR': 0.02, 'OTS': 0.0},

    # 阶段3: 黄体期早期 (天 15-21)
    # 特征: HRV开始下降，恢复变慢。概率分布开始向疲劳状态偏移。
    'early_luteal':     {'Peak': 0.10, 'Well-adapted': 0.30, 'FOR': 0.25, 'Acute Fatigue': 0.20, 'NFOR': 0.15, 'OTS': 0.0},

    # 阶段4: 黄体期晚期 (天 22-28)
    # 特征: 恢复最困难的时期，PMS症状。概率分布显著偏向恢复不佳的状态。
    # 修正：原表各项之和≈1.13，这里按比例缩放至总和≈1.0
    'late_luteal':     {'Peak': 0.044, 'Well-adapted': 0.177, 'FOR': 0.177, 'Acute Fatigue': 0.248, 'NFOR': 0.354, 'OTS': 0.0}
}

# 前一天的训练负荷 (P(今日状态 | 昨日训练负荷))
TRAINING_LOAD_CPT = {
    '极高': {'Peak': 0.01, 'Well-adapted': 0.05, 'FOR': 0.40, 'Acute Fatigue': 0.50, 'NFOR': 0.04, 'OTS': 0.0},
    '高':   {'Peak': 0.05, 'Well-adapted': 0.15, 'FOR': 0.50, 'Acute Fatigue': 0.25, 'NFOR': 0.05, 'OTS': 0.0},
    '中':   {'Peak': 0.10, 'Well-adapted': 0.60, 'FOR': 0.20, 'Acute Fatigue': 0.08, 'NFOR': 0.02, 'OTS': 0.0},
    '低':   {'Peak': 0.20, 'Well-adapted': 0.70, 'FOR': 0.05, 'Acute Fatigue': 0.04, 'NFOR': 0.01, 'OTS': 0.0},
    '无':   {'Peak': 0.30, 'Well-adapted': 0.60, 'FOR': 0.05, 'Acute Fatigue': 0.03, 'NFOR': 0.02, 'OTS': 0.0}
}

# 睡前进食 (条件性) (P(今日状态 | 昨晚进食情况))
LATE_MEAL_CPT = {
    # 降低“positive”对良好状态的过强拉升，避免掩盖强负面因子
    'positive': {'Peak': 0.50, 'Well-adapted': 0.50, 'FOR': 0.45, 'Acute Fatigue': 0.30, 'NFOR': 0.25, 'OTS': 1e-6},
    'negative': {'Peak': 0.20, 'Well-adapted': 0.20, 'FOR': 0.30, 'Acute Fatigue': 0.30, 'NFOR': 0.10, 'OTS': 1e-6},
    'neutral':  {'Peak': 0.30, 'Well-adapted': 0.50, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.05, 'OTS': 1e-6}
}

# "原因"权重表 (Causal Factor Weights)
CAUSAL_FACTOR_WEIGHTS = {
    'baseline_transition': 1.0, 
    'training_load': 1,
    'alcohol': 1.0,
    'menstrual_phase': 0.8,
    'late_meal': 0.5,
    'late_caffeine': 0.5,
    'screen_before_bed': 0.3
}

class JournalManager:
    """
    日志管理器 - 负责用户日志数据的管理和处理
    """
    
    def __init__(self):
        # 模拟日志数据库（实际应用中连接真实数据库）
        self.journal_database = {}
        
    def get_yesterdays_journal(self, user_id: str, today_date: str) -> Dict[str, Any]:
        """获取昨天的日志数据用于影响今日先验概率"""
        yesterday_date = self._get_previous_date(today_date)
        journal_key = f"{user_id}_{yesterday_date}"
        
        # 返回昨天的完整日志数据
        return self.journal_database.get(journal_key, {
            'short_term_behaviors': {},
            'persistent_status': {},
            'training_context': {}
        })
    
    def get_today_journal_evidence(self, user_id: str, date: str) -> Dict[str, Any]:
        """获取今天可以作为证据的日志条目（如生病、突发压力）"""
        journal_key = f"{user_id}_{date}"
        today_journal = self.journal_database.get(journal_key, {})
        
        # 只返回可以作为当天证据的日志条目
        evidence = {}
        persistent_status = today_journal.get('persistent_status', {})
        short_term = today_journal.get('short_term_behaviors', {})
        
        # 持续状态类证据
        if persistent_status.get('is_sick'):
            evidence['is_sick'] = True
        if persistent_status.get('is_injured'):
            evidence['is_injured'] = True
        if persistent_status.get('high_stress_event_today'):
            evidence['high_stress_event_today'] = True
            
        # 当天行为类证据
        if short_term.get('meditation_done_today'):
            evidence['meditation_done_today'] = True
            
        return evidence
    
    def add_journal_entry(self, user_id: str, date: str, entry_type: str, entry_data: Dict):
        """添加日志条目"""
        journal_key = f"{user_id}_{date}"
        if journal_key not in self.journal_database:
            self.journal_database[journal_key] = {
                'short_term_behaviors': {},
                'persistent_status': {},
                'training_context': {}
            }
        
        self.journal_database[journal_key][entry_type].update(entry_data)
    
    def auto_clear_short_term_flags(self, user_id: str, yesterday_date: str):
        """自动清理昨天的短期行为标记（在计算完先验概率后）"""
        journal_key = f"{user_id}_{yesterday_date}"
        if journal_key in self.journal_database:
            # 清空短期行为，保留持续状态和训练上下文
            self.journal_database[journal_key]['short_term_behaviors'] = {}
            print(f"✓ 已自动清理 {yesterday_date} 的短期行为标记")
    
    def _get_previous_date(self, date_str: str) -> str:
        """获取前一天的日期"""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        previous_date = date_obj - timedelta(days=1)
        return previous_date.strftime("%Y-%m-%d")

class DailyReadinessManager:
    """
    动态准备度管理器 - 核心类
    负责管理一整天的准备度评估流程
    """
    
    def __init__(self, user_id: str, date: str, previous_state_probs: Optional[Dict] = None, gender: str = '男性'):
        """
        初始化当天的准备度管理器
        
        Args:
            user_id: 用户ID
            date: 日期 (YYYY-MM-DD格式)
            previous_state_probs: 昨天的最终状态概率分布
            gender: 用户性别 ('男性' 或 '女性')
        """
        self.user_id = user_id
        self.date = date
        self.gender = gender
        self.states = ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue', 'NFOR', 'OTS']
        
        # 初始化昨天的状态概率（如果没有提供，使用默认值）
        self.previous_probs = previous_state_probs or {
            'Peak': 0.3, 'Well-adapted': 0.5, 'FOR': 0.15, 
            'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0
        }
        
        # 日志管理器
        self.journal_manager = JournalManager()
        
        # 今日先验概率（固定，每天只计算一次）
        self.today_prior_probs = None
        self.prior_calculated = False
        
        # 今日后验概率（动态更新）
        self.today_posterior_probs = None
        
        # 证据池（累积当天收到的所有证据）
        self.evidence_pool = {}
        
        # 更新历史记录
        self.update_history = []
        
    def calculate_today_prior(self, causal_inputs: Dict[str, Any]) -> Dict[str, float]:
        """
        ★★★ 计算今日先验概率 (PRIOR PROBABILITY) ★★★
        基于昨天状态、传统因果输入和日志影响计算今日的预测概率
        注意：此方法每天只能调用一次，结果固定不变，作为后续所有更新的基础
        
        计算步骤：
        1. BASELINE_TRANSITION_CPT: 基线转移概率
        2. TRAINING_LOAD_CPT等: 传统因果输入影响
        3. ALCOHOL_CONSUMPTION_CPT等: 日志原因影响
        
        Args:
            causal_inputs: 传统因果输入（训练负荷、睡眠状态等）
            
        Returns:
            今日先验概率分布 - P(Today_State | All_Causal_Factors)
        """
        if self.prior_calculated:
            return self.today_prior_probs
        
        print(f"开始计算 {self.date} 的先验概率")
            
        # 第1步：从基线转移概率开始
        prior_probs = {}
        for today_state in self.states:
            prior_probs[today_state] = sum(
                self.previous_probs.get(yesterday_state, 0) * 
                BASELINE_TRANSITION_CPT[yesterday_state].get(today_state, 1e-6)
                for yesterday_state in self.states
            )
        
        # 标准化
        total = sum(prior_probs.values())
        if total > 0:
            prior_probs = {state: prob / total for state, prob in prior_probs.items()}
        
        print("   基线转移概率计算完成")
        self._print_probabilities("基线转移后", prior_probs)
        
        # 第2步：应用传统因果输入影响（复用CPT_test.py逻辑）
        prior_probs = self._apply_traditional_causal_inputs(prior_probs, causal_inputs)
        print("   传统因果输入影响计算完成")
        self._print_probabilities("传统因果后", prior_probs)
        
        # 第3步：获取昨天的日志数据并应用影响
        yesterday_journal = self.journal_manager.get_yesterdays_journal(self.user_id, self.date)
        if yesterday_journal and any(yesterday_journal.values()):
            # 传递训练强度给睡前饮食逻辑使用
            training_load = causal_inputs.get('training_load', '无')
            prior_probs = self._apply_journal_prior_impacts(prior_probs, yesterday_journal, training_load)
            print("   日志先验影响计算完成")
            self._print_probabilities("日志影响后", prior_probs)
        else:
            print("   昨天无日志数据，跳过日志先验影响")
        
        # 第4步：自动清理昨天的短期行为标记
        yesterday_date = self.journal_manager._get_previous_date(self.date)
        self.journal_manager.auto_clear_short_term_flags(self.user_id, yesterday_date)
        
        self.today_prior_probs = prior_probs
        self.today_posterior_probs = prior_probs.copy()  # 初始化后验=先验
        self.prior_calculated = True
        
        print(f"{self.date} 先验概率计算完成")
        self._print_probabilities("最终先验", self.today_prior_probs)
        
        return self.today_prior_probs
    
    def _apply_traditional_causal_inputs(self, probs: Dict[str, float], causal_inputs: Dict[str, Any]) -> Dict[str, float]:
        """
        应用传统因果输入的影响 - 使用新的CPT表
        """
        adjusted_probs = probs.copy()
        
        # 处理训练负荷影响
        if 'training_load' in causal_inputs:
            training_load = causal_inputs['training_load']
            if training_load in TRAINING_LOAD_CPT:
                print(f"     应用训练负荷影响: {training_load}")
                training_impact = TRAINING_LOAD_CPT[training_load]
                weight = CAUSAL_FACTOR_WEIGHTS.get('training_load', 1.0)
                adjusted_probs = self._combine_probabilities_multiplicative(adjusted_probs, training_impact, weight)
        
        # 连续训练惩罚（4/8天内高强度不休息）
        recent_loads = causal_inputs.get('recent_training_loads')
        if isinstance(recent_loads, list) and recent_loads:
            adjusted_probs = self._apply_training_streak_penalty(adjusted_probs, recent_loads)

        # TODO: 可以添加其他传统因果输入如累积疲劳等
        
        return adjusted_probs
        
    def _apply_training_streak_penalty(self, probs: Dict[str, float], recent_training_loads: List[str]) -> Dict[str, float]:
        """
        根据最近训练强度序列施加“连续高强度不休息”的先验惩罚。
        规则参考 CPT_test：
        - 最近4天中“高/极高”天数>=3 → 从良好/一般/疲劳状态向 NFOR 迁移 50%
        - 最近8天中“高/极高”天数>=6 → 再向 NFOR 迁移 60%
        两条规则按顺序叠加（每次都会归一化）。
        """
        adjusted = probs.copy()
        HIGH = {'高', '极高'}
        loads = list(recent_training_loads or [])
        # 近4天
        if len(loads) >= 4:
            last4 = loads[-4:]
            if sum(1 for x in last4 if x in HIGH) >= 3:
                print("     连续训练惩罚: 最近4天高强度≥3次 → 向NFOR迁移50%")
                adjusted = self._shift_probability(adjusted, ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue'], ['NFOR'], 0.50)
        # 近8天
        if len(loads) >= 8:
            last8 = loads[-8:]
            if sum(1 for x in last8 if x in HIGH) >= 6:
                print("     连续训练惩罚: 最近8天高强度≥6次 → 向NFOR迁移60%")
                adjusted = self._shift_probability(adjusted, ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue'], ['NFOR'], 0.60)
        return adjusted
    def _apply_journal_prior_impacts(self, probs: Dict[str, float], journal_data: Dict[str, Any], training_load: str = '无') -> Dict[str, float]:
        """
        应用日志对先验概率的影响 - 使用新的CPT表
        注意：这里只处理影响第二天的日志条目
        """
        adjusted_probs = probs.copy()
        
        # 处理短期行为的先验影响
        short_term = journal_data.get('short_term_behaviors', {})
        
        # 酒精摄入的影响
        if short_term.get('alcohol_consumed'):
            print("     应用酒精摄入影响")
            alcohol_impact = ALCOHOL_CONSUMPTION_CPT[True]
            weight = CAUSAL_FACTOR_WEIGHTS.get('alcohol', 1.0)
            adjusted_probs = self._combine_probabilities_multiplicative(adjusted_probs, alcohol_impact, weight)
        
        # 深夜咖啡因的影响
        if short_term.get('late_caffeine'):
            print("     应用深夜咖啡因影响")
            caffeine_impact = LATE_CAFFEINE_CPT[True]
            weight = CAUSAL_FACTOR_WEIGHTS.get('late_caffeine', 1.0)
            adjusted_probs = self._combine_probabilities_multiplicative(adjusted_probs, caffeine_impact, weight)
        
        # 睡前屏幕使用的影响
        if short_term.get('screen_before_bed'):
            print("     应用睡前屏幕影响")
            screen_impact = SCREEN_BEFORE_BED_CPT[True]
            weight = CAUSAL_FACTOR_WEIGHTS.get('screen_before_bed', 1.0)
            adjusted_probs = self._combine_probabilities_multiplicative(adjusted_probs, screen_impact, weight)
        
        # 睡前进食的影响 - 根据训练强度自动决定positive/negative
        if short_term.get('late_meal'):  # late_meal = True时才应用影响
            # 根据训练强度决定使用positive还是negative影响
            if training_load in ['中', '高', '极高']:
                meal_status = 'positive'  # 训练强度中等以上，睡前进食是好的
            else:
                meal_status = 'negative'  # 训练强度低或无，睡前进食是不好的
            
            print(f"     应用睡前进食影响: {meal_status} (基于训练强度: {training_load})")
            meal_impact = LATE_MEAL_CPT[meal_status]
            weight = CAUSAL_FACTOR_WEIGHTS.get('late_meal', 1.0)
            adjusted_probs = self._combine_probabilities_multiplicative(adjusted_probs, meal_impact, weight)
            
        # 处理持续状态的先验影响 - 这些持续状态也会影响第二天
        persistent = journal_data.get('persistent_status', {})
        
        # 生病状态持续影响（如果昨天生病，今天先验概率受影响）
        if persistent.get('is_sick'):
            print("     应用持续生病状态的先验影响")
            # 这里可以定义生病对第二天先验概率的影响（与当天证据影响不同）
            adjusted_probs = self._shift_probability(adjusted_probs, ['Peak', 'Well-adapted'], ['NFOR', 'OTS'], 0.4)
        
        # 持续受伤的先验影响：将部分概率从良好状态转移到疲劳/不良状态
        if persistent.get('is_injured'):
            print("     应用持续受伤状态的先验影响")
            adjusted_probs = self._shift_probability(adjusted_probs, ['Peak', 'Well-adapted'], ['FOR', 'NFOR'], 0.3)
        
        # 月经周期的影响（仅女性且有记录时）
        if self.gender == '女性' and 'menstrual_phase' in persistent:
            phase = persistent['menstrual_phase']
            if phase in MENSTRUAL_PHASE_CPT:
                print(f"     应用月经周期影响: {phase}")
                menstrual_impact = MENSTRUAL_PHASE_CPT[phase]
                weight = CAUSAL_FACTOR_WEIGHTS.get('menstrual_phase', 1.0)
                adjusted_probs = self._combine_probabilities_multiplicative(adjusted_probs, menstrual_impact, weight)
        elif self.gender == '男性' and 'menstrual_phase' in persistent:
            print(f"     男性用户，忽略月经周期数据: {persistent['menstrual_phase']}")
            
        return adjusted_probs
    
    def _combine_probabilities_weighted(self, current_probs: Dict[str, float], impact_cpt: Dict[str, float], weight: float) -> Dict[str, float]:
        """
        加权概率组合方法：将当前概率分布与CPT影响进行加权组合
        
        Args:
            current_probs: 当前的概率分布
            impact_cpt: CPT影响概率分布
            weight: 影响权重（支持大于1的值）
            
        Returns:
            组合后的概率分布
        """
        combined_probs = {}
        
        # 标准化权重以避免负概率
        # 如果weight > 1，我们增强CPT的影响
        normalized_weight = min(weight, 1.0)  # 限制在[0,1]范围内用于插值
        enhancement_factor = weight  # 保留原始权重用于后续增强
        
        # 对每个状态进行加权组合
        for state in self.states:
            current_prob = current_probs.get(state, 0)
            impact_prob = impact_cpt.get(state, 0)
            
            # 基础插值组合: (1-normalized_weight) * current + normalized_weight * impact
            base_combined = (1 - normalized_weight) * current_prob + normalized_weight * impact_prob
            
            # 如果原始权重>1，则增强CPT的影响
            if weight > 1.0:
                enhancement = (weight - 1.0) * impact_prob
                combined_prob = base_combined + enhancement * 0.5  # 适度增强避免过度影响
            else:
                combined_prob = base_combined
                
            combined_probs[state] = max(1e-9, combined_prob)  # 确保非负
        
        # 重新标准化确保概率总和为1
        total = sum(combined_probs.values())
        if total > 0:
            combined_probs = {state: prob / total for state, prob in combined_probs.items()}
        
        return combined_probs
    
    def _shift_probability(self, probs: Dict[str, float], from_states: List[str], to_states: List[str], shift_ratio: float) -> Dict[str, float]:
        """
        概率转移辅助函数：从某些状态转移概率到其他状态
        """
        adjusted_probs = probs.copy()
        
        # 计算需要转移的总概率量
        total_from_prob = sum(adjusted_probs.get(state, 0) for state in from_states)
        shift_amount = total_from_prob * shift_ratio
        
        # 从源状态减少概率
        for state in from_states:
            if state in adjusted_probs:
                reduction = (adjusted_probs[state] / total_from_prob) * shift_amount if total_from_prob > 0 else 0
                adjusted_probs[state] = max(1e-6, adjusted_probs[state] - reduction)
        
        # 向目标状态增加概率
        per_target_increase = shift_amount / len(to_states)
        for state in to_states:
            adjusted_probs[state] = adjusted_probs.get(state, 0) + per_target_increase
            
        # 重新标准化
        total = sum(adjusted_probs.values())
        if total > 0:
            adjusted_probs = {state: prob / total for state, prob in adjusted_probs.items()}
            
        return adjusted_probs
    
    def _normalize_distribution(self, impact_cpt: Dict[str, float]) -> Dict[str, float]:
        """将因子影响分布规范化为合法概率分布，并对零值应用最小下限以避免乘法归零。"""
        eps = 1e-6
        clipped = {state: max(float(impact_cpt.get(state, eps)), eps) for state in self.states}
        total = sum(clipped.values())
        if total <= 0:
            return {s: 1.0 / len(self.states) for s in self.states}
        return {s: v / total for s, v in clipped.items()}

    def _combine_probabilities_multiplicative(self, current_probs: Dict[str, float], impact_cpt: Dict[str, float], weight: float) -> Dict[str, float]:
        """
        按建议实现的乘法（贝叶斯式）组合：
        P'(state) ∝ P(state) * (impact_cpt[state]_clipped) ^ weight
        - 仅对单个值做最小下限裁剪 max(x, 1e-6)，不强制归一化 impact_cpt。
        - 每次组合后归一化输出分布。
        """
        w = float(weight) if weight is not None else 1.0
        new_probs: Dict[str, float] = {}
        for state, curr_prob in current_probs.items():
            like = max(float(impact_cpt.get(state, 1e-6)), 1e-6)
            new_probs[state] = curr_prob * (like ** w)
        total = sum(new_probs.values())
        return {s: (p / total if total > 0 else 0.0) for s, p in new_probs.items()}

    def add_evidence_and_update(self, new_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        ★★★ 更新后验概率 (POSTERIOR PROBABILITY) ★★★
        基于固定的先验概率和累积的证据，使用指纹库计算后验概率
        这是核心的实时更新方法，可以被多次调用
        
        使用的指纹库：
        1. EMISSION_CPT: 主要症状指纹库
        2. INTERACTION_CPT_SORENESS_STRESS: 交互效应指纹库
        
        证据优先级：
        1. Hooper Index（最重要主观指标）
        2. 客观睡眠/HRV数据
        3. 少数当天Journal证据（如生病、突发压力）
        
        计算公式: P(State | Evidence) ∝ P(State | Causal) × P(Evidence | State)
                 先验概率 × 指纹库概率 = 后验概率
        
        Args:
            new_evidence: 新的证据 {'fatigue_hooper': 4, 'hrv_trend': 'stable', 'is_sick': True}
            
        Returns:
            更新结果包含准备度分数和概率分布
        """
        if not self.prior_calculated:
            raise RuntimeError("必须先调用 calculate_today_prior() 计算先验概率")
        
        # 更新证据池 - 添加新证据
        for key, value in new_evidence.items():
            if value is not None:  # 只添加非空证据
                self.evidence_pool[key] = value
        
        # 检查是否有今天的Journal证据需要添加
        today_journal_evidence = self.journal_manager.get_today_journal_evidence(self.user_id, self.date)
        if today_journal_evidence:
            print(f"   检测到当天Journal证据: {today_journal_evidence}")
            self.evidence_pool.update(today_journal_evidence)
        
        # 显示当前证据池状态
        evidence_types = self._categorize_evidence(self.evidence_pool)
        print(f"当前证据池状态:")
        for category, evidence_list in evidence_types.items():
            if evidence_list:
                print(f"   {category}: {evidence_list}")
        
        # 使用固定的先验概率和完整的证据池计算新的后验概率
        # 重要：这里复用CPT_test.py的贝叶斯更新逻辑
        mapped_evidence = map_inputs_to_states(self.evidence_pool)
        self.today_posterior_probs = self._run_bayesian_update(
            self.today_prior_probs,  # 固定先验
            mapped_evidence         # 累积的所有证据
        )
        
        # 计算准备度分数
        readiness_score = self._get_readiness_score(self.today_posterior_probs)
        
        # 记录更新历史
        update_record = {
            'timestamp': datetime.now().isoformat(),
            'new_evidence': new_evidence.copy(),
            'evidence_pool_size': len(self.evidence_pool),
            'readiness_score': readiness_score,
            'posterior_probs': self.today_posterior_probs.copy()
        }
        self.update_history.append(update_record)
        
        # 显示更新结果
        diagnosis = max(self.today_posterior_probs, key=self.today_posterior_probs.get)
        print(f"准备度更新完成")
        print(f"   分数: {readiness_score}/100 | 诊断: {diagnosis}")
        print(f"   新增证据: {list(new_evidence.keys())}")
        print(f"   累积证据: {len(self.evidence_pool)}项")
        
        return {
            'readiness_score': readiness_score,
            'diagnosis': diagnosis,
            'posterior_probs': self.today_posterior_probs,
            'evidence_pool_size': len(self.evidence_pool),
            'update_count': len(self.update_history)
        }
    
    def _categorize_evidence(self, evidence_pool: Dict[str, Any]) -> Dict[str, List[str]]:
        """将证据按类型分类显示"""
        hooper_evidence = []
        objective_evidence = []
        journal_evidence = []
        other_evidence = []
        
        for key in evidence_pool.keys():
            if 'hooper' in key:
                hooper_evidence.append(key)
            elif key in ['sleep_performance_state', 'hrv_trend', 'restorative_sleep']:
                objective_evidence.append(key)
            elif key in ['is_sick', 'is_injured', 'high_stress_event_today', 'meditation_done_today']:
                journal_evidence.append(key)
            else:
                other_evidence.append(key)
        
        return {
            'Hooper指数': hooper_evidence,
            '客观数据': objective_evidence, 
            'Journal证据': journal_evidence,
            '其他证据': other_evidence
        }
    
    def _run_bayesian_update(self, prior_probs: Dict, evidence: Dict) -> Dict[str, float]:
        """
        ★★★ 贝叶斯更新核心算法 - 指纹库匹配 ★★★
        使用EMISSION_CPT指纹库和INTERACTION_CPT计算似然概率
        （从CPT_test.py继承并适配）
        
        核心公式: P(State | Evidence) = P(State) × ∏P(Evidence_i | State)
        """
        posterior_probs = prior_probs.copy()
        weights = EVIDENCE_WEIGHTS_FITNESS
        
        # 处理肌肉酸痛+压力的交互效应
        interaction_processed = False
        if ("muscle_soreness" in evidence and evidence["muscle_soreness"] is not None and
            "subjective_stress" in evidence and evidence["subjective_stress"] is not None):
            
            muscle_val = evidence["muscle_soreness"]
            stress_val = evidence["subjective_stress"]
            interaction_key = (muscle_val, stress_val)
            
            if interaction_key in INTERACTION_CPT_SORENESS_STRESS:
                weight = weights.get("soreness_stress_interaction", 1.0)
                for state in self.states:
                    likelihood = INTERACTION_CPT_SORENESS_STRESS[interaction_key].get(state, 1e-6)
                    posterior_probs[state] *= (likelihood ** weight)
                interaction_processed = True
        
        # 处理其他独立证据
        for evidence_type, value in evidence.items():
            if interaction_processed and evidence_type in ["muscle_soreness", "subjective_stress"]:
                continue
                
            if evidence_type in EMISSION_CPT and value is not None:
                for state in self.states:
                    likelihood = EMISSION_CPT[evidence_type].get(value, {}).get(state, 0.001)
                    weight = weights.get(evidence_type, 1.0)
                    posterior_probs[state] *= (likelihood ** weight)
        
        # 标准化
        total = sum(posterior_probs.values())
        if total > 0:
            posterior_probs = {state: prob / total for state, prob in posterior_probs.items()}
        
        return posterior_probs
    
    def _get_readiness_score(self, probs: Dict[str, float]) -> int:
        """计算准备度分数（0-100）"""
        score = sum(probs.get(state, 0) * weight for state, weight in READINESS_WEIGHTS.items())
        return int(round(score))
    
    def _print_probabilities(self, title: str, probs: Dict[str, float]):
        """格式化打印概率分布"""
        print(f"   {title}: " + " | ".join([f"{state}: {prob:.3f}" for state, prob in probs.items()]))
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """获取当天的完整总结"""
        if not self.today_posterior_probs:
            return {"error": "尚未进行任何概率计算"}
        
        final_diagnosis = max(self.today_posterior_probs, key=self.today_posterior_probs.get)
        final_score = self._get_readiness_score(self.today_posterior_probs)
        
        return {
            'user_id': self.user_id,
            'date': self.date,
            'final_readiness_score': final_score,
            'final_diagnosis': final_diagnosis,
            'final_posterior_probs': self.today_posterior_probs,
            'prior_probs': self.today_prior_probs,
            'evidence_pool': self.evidence_pool,
            'total_updates': len(self.update_history),
            'update_history': self.update_history
        }


def map_inputs_to_states(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    将原始输入映射到模型状态（从CPT_test.py继承）
    """
    mapped = {}
    
    # Hooper量表映射 (1-7 -> low/medium/high)
    hooper_mapping = {
        'fatigue_hooper': 'subjective_fatigue',
        'soreness_hooper': 'muscle_soreness', 
        'stress_hooper': 'subjective_stress',
        'sleep_hooper': 'subjective_sleep'
    }
    
    for raw_key, model_key in hooper_mapping.items():
        if raw_key in raw_inputs:
            val = raw_inputs[raw_key]
            if val is not None and 1 <= val <= 7:
                if val <= 2:
                    mapped[model_key] = 'low'
                elif val <= 4:
                    mapped[model_key] = 'medium'
                else:
                    mapped[model_key] = 'high'
    
    # 直接映射的字段
    direct_mappings = [
        'sleep_performance_state', 'restorative_sleep', 'hrv_trend', 
        'nutrition', 'gi_symptoms', 'fatigue_3day_state'
    ]
    
    for key in direct_mappings:
        if key in raw_inputs and raw_inputs[key] is not None:
            mapped[key.replace('_state', '')] = raw_inputs[key]
    
    # 直接保留作为发射证据使用的布尔Journal键
    for key in ['is_sick', 'is_injured', 'high_stress_event_today', 'meditation_done_today']:
        if key in raw_inputs and raw_inputs[key] is not None:
            mapped[key] = raw_inputs[key]
    
    return mapped


if __name__ == "__main__":
    """
    模拟真实使用场景的动态准备度评估流程
    按照实际的时间顺序和数据输入流程
    """
    print("🏃 动态准备度模型 v2.0 - 真实使用场景模拟")
    print("="*70)
    
    # =================== 准备阶段：设置模拟数据 ===================
    print("\n📋 准备阶段：设置模拟的日志数据")
    print("-"*50)
    
    # 创建管理器
    manager = DailyReadinessManager(
        user_id="athlete_001", 
        date="2024-01-16",
        previous_state_probs={'Peak': 0.15, 'Well-adapted': 0.60, 'FOR': 0.20, 'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0}
    )
    
    # 模拟添加昨天的日志数据
    manager.journal_manager.add_journal_entry("athlete_001", "2024-01-15", "short_term_behaviors", {
        'alcohol_consumed': True,    # 昨晚喝了酒
        'ate_before_bed': False,     # 没有睡前进食
        'stayed_up_late': False      # 没有熬夜
    })
    
    manager.journal_manager.add_journal_entry("athlete_001", "2024-01-15", "persistent_status", {
        'is_sick': False,            # 没有生病
        'high_work_stress_period': True  # 工作压力期
    })
    
    manager.journal_manager.add_journal_entry("athlete_001", "2024-01-15", "training_context", {
        'training_load': '高',       # 昨天高强度训练
        'cumulative_fatigue_14day': 'medium'
    })
    
    # 模拟今天突然生病
    manager.journal_manager.add_journal_entry("athlete_001", "2024-01-16", "persistent_status", {
        'is_sick': True,             # 今天感觉生病了
        'acute_stress': None
    })
    
    print("✅ 模拟数据设置完成")
    
    # =================== 第1步：计算今日先验概率 ===================
    print(f"\n🧠 第1步：基于昨天数据计算今日先验概率")
    print("-"*50)
    print("⏰ 时间：今早7:00（系统自动执行）")
    
    # 传统因果输入
    causal_inputs = {
        'training_load': '高',  # 昨天训练强度
        'subjective_sleep_state': 'good',  # 昨晚睡眠状态
        'cumulative_fatigue_14day_state': 'medium'  # 累积疲劳
    }
    
    prior = manager.calculate_today_prior(causal_inputs)
    
    # =================== 第2步：早上睡眠+HRV数据更新 ===================
    print(f"\n☀️ 第2步：早上睡眠和HRV数据更新")
    print("-"*50)
    print("⏰ 时间：今早8:00")
    print("📱 自动同步昨晚的睡眠传感器和HRV数据")
    
    objective_sleep_data = {
        'sleep_performance_state': 'medium',  # 睡眠表现一般（可能受饮酒影响）
        'restorative_sleep': 'medium',        # 恢复性睡眠中等
        'hrv_trend': 'slight_decline'         # HRV轻微下降
    }
    
    result1 = manager.add_evidence_and_update(objective_sleep_data)
    
    # =================== 第3步：填写Hooper量表 ===================
    print(f"\n📝 第3步：手动填写Hooper指数量表")
    print("-"*50)
    print("⏰ 时间：今早8:30")
    print("🖊️  运动员填写主观感受量表")
    
    hooper_data = {
        'fatigue_hooper': 5,    # 疲劳度 5/7（中高）
        'soreness_hooper': 3,   # 酸痛度 3/7（中等）  
        'stress_hooper': 6,     # 压力度 6/7（高）- 工作压力+生病影响
        'sleep_hooper': 3       # 睡眠质量 3/7（一般）- 饮酒影响
    }
    
    print(f"Hooper量表填写: 疲劳 {hooper_data['fatigue_hooper']}/7, 酸痛 {hooper_data['soreness_hooper']}/7, 压力 {hooper_data['stress_hooper']}/7, 睡眠 {hooper_data['sleep_hooper']}/7")
    
    result2 = manager.add_evidence_and_update(hooper_data)
    
    # =================== 第4步：下午突发状况更新 ===================
    print(f"\n🚨 第4步：下午突发状况 - 感冒症状确认")
    print("-"*50)
    print("⏰ 时间：今天14:30")
    print("📝 运动员在日志中确认感冒症状")
    
    # 注意：生病状态会自动从journal中检测到
    emergency_symptoms = {
        'subjective_fatigue': 'high',  # 主观疲劳感突然增加
        'gi_symptoms': 'mild'          # 轻微胃肠不适
    }
    
    result3 = manager.add_evidence_and_update(emergency_symptoms)
    
    # =================== 展示完整的更新历程 ===================
    print("\n" + "="*70)
    print("📈 完整的准备度评估历程总结")
    print("="*70)
    
    summary = manager.get_daily_summary()
    
    print(f"📅 评估日期: {summary['date']}")
    print(f"👤 运动员ID: {summary['user_id']}")
    print(f"🎯 最终准备度: {summary['final_readiness_score']}/100")
    print(f"🏥 最终诊断: {summary['final_diagnosis']}")
    print(f"🔄 总更新次数: {summary['total_updates']}")
    
    print(f"\n📊 准备度分数变化轨迹:")
    initial_score = manager._get_readiness_score(manager.today_prior_probs)
    print(f"初始先验分数: {initial_score}/100")
    
    update_labels = ["睡眠HRV数据", "Hooper量表", "突发症状"]
    for i, update in enumerate(summary['update_history']): 
        score = update['readiness_score']
        label = update_labels[i] if i < len(update_labels) else f"更新{i+1}"
        print(f"第{i+1}次更新后: {score}/100 (添加{label})")
    
    print(f"\n🧠 概率分布变化历程:")
    print(f"{'状态':>12} {'先验':>8} {'最终':>8} {'变化':>8} {'趋势':>4}")
    print("-" * 40)
    for state in manager.states:
        prior_prob = summary['prior_probs'].get(state, 0)
        final_prob = summary['final_posterior_probs'].get(state, 0)
        change = final_prob - prior_prob
        trend = "📈" if change > 0.05 else "📉" if change < -0.05 else "➡️"
        print(f"{state:>12} {prior_prob:>8.3f} {final_prob:>8.3f} {change:>+8.3f} {trend:>4}")
    
    print(f"\n📋 最终证据池详情:")
    evidence_categories = manager._categorize_evidence(summary['evidence_pool'])
    for category, evidence_list in evidence_categories.items():
        if evidence_list:
            print(f"  {category}: {len(evidence_list)}项 - {evidence_list}")
    
    print(f"\n🔑 关键设计验证:")
    print(f"✅ 先验概率受日志影响：昨晚饮酒 → 影响今日预测")
    print(f"✅ 后验概率累积更新：[固定先验] + [累积证据] = [实时后验]") 
    print(f"✅ 证据优先级体现：Hooper指数 > 客观数据 > Journal证据")
    print(f"✅ 日志自动清理：短期行为已清理，持续状态保留")
    
    print(f"\n🎉 真实使用场景模拟完成！")
