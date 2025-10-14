"""Constants and CPT tables for the Readiness model (fully migrated).

All probabilities are encoded as floats; rows are normalized where appropriate
to ensure numerical stability.
"""

from __future__ import annotations

# Re-export from the legacy module to avoid duplication for now
from __future__ import annotations

# ------------------------- Emission CPTs (Posterior) -------------------------

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
    # iOS 26 苹果原生睡眠评分 (0-100分) - 严格基于现有sleep_performance概率
    'apple_sleep_score': {
        'excellent': {'Peak': 0.85, 'Well-adapted': 0.75, 'FOR': 0.20, 'Acute Fatigue': 0.30, 'NFOR': 0.15, 'OTS': 0.10},  # 80-100分，比good稍好
        'good': {'Peak': 0.80, 'Well-adapted': 0.70, 'FOR': 0.25, 'Acute Fatigue': 0.35, 'NFOR': 0.20, 'OTS': 0.15},      # 70-79分，对应sleep_performance good
        'fair': {'Peak': 0.20, 'Well-adapted': 0.30, 'FOR': 0.50, 'Acute Fatigue': 0.50, 'NFOR': 0.40, 'OTS': 0.35},      # 60-69分，对应sleep_performance medium
        'poor': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.25, 'Acute Fatigue': 0.15, 'NFOR': 0.40, 'OTS': 0.50},      # 40-59分，对应sleep_performance poor
        'very_poor': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.15, 'Acute Fatigue': 0.10, 'NFOR': 0.50, 'OTS': 0.65} # 0-39分，比poor稍差
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
    'is_sick': { True: {'Peak': 1e-9, 'Well-adapted': 1e-6, 'FOR': 0.05, 'Acute Fatigue': 0.40, 'NFOR': 0.80, 'OTS': 0.90}},
    'is_injured': { True: {'Peak': 1e-9, 'Well-adapted': 1e-6, 'FOR': 0.10, 'Acute Fatigue': 0.50, 'NFOR': 0.70, 'OTS': 0.60}},
    'high_stress_event_today': { True: {'Peak': 0.05, 'Well-adapted': 0.15, 'FOR': 0.25, 'Acute Fatigue': 0.30, 'NFOR': 0.50, 'OTS': 0.40}},
    'meditation_done_today': { True: {'Peak': 0.55, 'Well-adapted': 0.50, 'FOR': 0.45, 'Acute Fatigue': 0.40, 'NFOR': 0.35, 'OTS': 0.30}},
}


# ------------------------- Baseline/Weights -------------------------

BASELINE_TRANSITION_CPT = {
    'Peak': {'Peak': 0.80, 'Well-adapted': 0.10, 'FOR': 0.05, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'Well-adapted': {'Peak': 0.60, 'Well-adapted': 0.35, 'FOR': 0.05, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'FOR': {'Peak': 0.05, 'Well-adapted': 0.40, 'FOR': 0.30, 'Acute Fatigue': 0.10, 'NFOR': 0.10, 'OTS': 0.05},
    'Acute Fatigue': {'Peak': 0.20, 'Well-adapted': 0.70, 'FOR': 0.10, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'NFOR': {'Peak': 0.01, 'Well-adapted': 0.05, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.70, 'OTS': 0.09},
    'OTS': {'Peak': 0.01, 'Well-adapted': 0.04, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.30, 'OTS': 0.50}
}
for st in BASELINE_TRANSITION_CPT:
    tot = sum(BASELINE_TRANSITION_CPT[st].values())
    if tot > 0:
        BASELINE_TRANSITION_CPT[st] = {s: p / tot for s, p in BASELINE_TRANSITION_CPT[st].items()}

READINESS_WEIGHTS = {'Peak': 100, 'Well-adapted': 85, 'FOR': 60, 'Acute Fatigue': 50, 'NFOR': 30, 'OTS': 10}

EVIDENCE_WEIGHTS_FITNESS = {
    "hrv_trend": 1.0,
    "restorative_sleep": 0.95,
    "sleep_performance": 0.90,
    "apple_sleep_score": 1.0,   # iOS 26苹果原生评分，满权重（综合了时长+效率+一致性+觉醒频率）
    "subjective_fatigue": 0.75,
    "subjective_stress": 0.70,
    "muscle_soreness": 0.65,
    "subjective_sleep": 0.60,
    "nutrition": 0.60,
    "gi_symptoms": 0.50,
    "fatigue_3day_state": 0.85,
    "is_sick": 1.0,
    "is_injured": 0.8,
    "high_stress_event_today": 0.6,
    "meditation_done_today": 0.5,
    # Menstrual cycle effect as posterior evidence (continuous likelihood)
    "menstrual_cycle": 0.8,
}


# ------------------------- Interactions -------------------------

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


# ------------------------- Causal CPTs (Prior) -------------------------

HEALTHY_NEUTRAL_BASELINE = {'Peak': 1, 'Well-adapted': 1, 'FOR': 1, 'Acute Fatigue': 1, 'NFOR': 1, 'OTS': 1}

ALCOHOL_CONSUMPTION_CPT = {
    True:  {'Peak': 1e-6, 'Well-adapted': 0.10, 'FOR': 0.20, 'Acute Fatigue': 0.40, 'NFOR': 0.30, 'OTS': 1e-6},
    False: HEALTHY_NEUTRAL_BASELINE
}

LATE_CAFFEINE_CPT = {
    True:  {'Peak': 0.10, 'Well-adapted': 0.20, 'FOR': 0.20, 'Acute Fatigue': 0.15, 'NFOR': 0.30, 'OTS': 1e-6},
    False: HEALTHY_NEUTRAL_BASELINE
}

SCREEN_BEFORE_BED_CPT = {
    True:  {'Peak': 0.10, 'Well-adapted': 0.20, 'FOR': 0.30, 'Acute Fatigue': 0.25, 'NFOR': 0.25, 'OTS': 1e-6},
    False: HEALTHY_NEUTRAL_BASELINE
}

MENSTRUAL_PHASE_CPT = {
    'menstrual_early_follicular': {'Peak': 0.15, 'Well-adapted': 0.40, 'FOR': 0.20, 'Acute Fatigue': 0.15, 'NFOR': 0.10, 'OTS': 0.0},
    'late_follicular_ovulatory':  {'Peak': 0.45, 'Well-adapted': 0.45, 'FOR': 0.05, 'Acute Fatigue': 0.03, 'NFOR': 0.02, 'OTS': 0.0},
    'early_luteal':               {'Peak': 0.10, 'Well-adapted': 0.30, 'FOR': 0.25, 'Acute Fatigue': 0.20, 'NFOR': 0.15, 'OTS': 0.0},
    'late_luteal':                {'Peak': 0.044, 'Well-adapted': 0.177, 'FOR': 0.177, 'Acute Fatigue': 0.248, 'NFOR': 0.354, 'OTS': 0.0},
}

TRAINING_LOAD_CPT = {
    '极高': {'Peak': 0.01, 'Well-adapted': 0.05, 'FOR': 0.40, 'Acute Fatigue': 0.50, 'NFOR': 0.04, 'OTS': 0.0},
    '高':   {'Peak': 0.05, 'Well-adapted': 0.15, 'FOR': 0.50, 'Acute Fatigue': 0.25, 'NFOR': 0.05, 'OTS': 0.0},
    '中':   {'Peak': 0.10, 'Well-adapted': 0.60, 'FOR': 0.20, 'Acute Fatigue': 0.08, 'NFOR': 0.02, 'OTS': 0.0},
    '低':   {'Peak': 0.20, 'Well-adapted': 0.70, 'FOR': 0.05, 'Acute Fatigue': 0.04, 'NFOR': 0.01, 'OTS': 0.0},
    '无':   {'Peak': 0.30, 'Well-adapted': 0.60, 'FOR': 0.05, 'Acute Fatigue': 0.03, 'NFOR': 0.02, 'OTS': 0.0},
}

# Discrete training-load label to AU (Arbitrary Units) mapping for ACWR.
# Used only to derive recent AU from labels when explicit AU is not provided.
# Values are cold-start defaults and can be personalized per user later.
TRAINING_LOAD_AU = {
    '无': 0,
    '低': 200,
    '中': 350,
    '高': 500,
    '极高': 700,
}

LATE_MEAL_CPT = {
    'positive': {'Peak': 0.50, 'Well-adapted': 0.50, 'FOR': 0.45, 'Acute Fatigue': 0.30, 'NFOR': 0.25, 'OTS': 1e-6},
    'negative': {'Peak': 0.20, 'Well-adapted': 0.20, 'FOR': 0.30, 'Acute Fatigue': 0.30, 'NFOR': 0.10, 'OTS': 1e-6},
    'neutral':  {'Peak': 0.30, 'Well-adapted': 0.50, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.05, 'OTS': 1e-6},
}

CAUSAL_FACTOR_WEIGHTS = {
    'baseline_transition': 1.0,
    'training_load': 1.0,
    'alcohol': 1.0,
    'menstrual_phase': 0.8,
    'late_meal': 0.5,
    'late_caffeine': 0.5,
    'screen_before_bed': 0.3,
}

__all__ = [
    'EMISSION_CPT',
    'INTERACTION_CPT_SORENESS_STRESS',
    'BASELINE_TRANSITION_CPT',
    'TRAINING_LOAD_CPT',
    'TRAINING_LOAD_AU',
    'ALCOHOL_CONSUMPTION_CPT',
    'LATE_CAFFEINE_CPT',
    'SCREEN_BEFORE_BED_CPT',
    'LATE_MEAL_CPT',
    'MENSTRUAL_PHASE_CPT',
    'CAUSAL_FACTOR_WEIGHTS',
    'READINESS_WEIGHTS',
    'EVIDENCE_WEIGHTS_FITNESS',
]
