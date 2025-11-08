"""Readiness input mapping helpers.

Maps numeric inputs to model enums when explicit enums are missing:
- sleep_performance from duration + efficiency
- restorative_sleep from restorative_ratio or deep+REM ratios
- hrv_trend from RMSSD deltas/baselines (today/3-day vs 7-day, or z-score)

Notes:
- Duration uses personalized thresholds when baseline is provided.
- Efficiency and restorative use fixed thresholds by default; personalization can be toggled via module flags.
"""

from __future__ import annotations
from typing import Any, Dict

# ---------------------------- Mapping Config ----------------------------
# Fixed thresholds (product rules)
# 默认启用个性化阈值（效率/恢复性）
PERSONALIZE_SLEEP_EFFICIENCY = True
PERSONALIZE_RESTORATIVE = True

# Fixed threshold values
EFFICIENCY_GOOD = 0.85
EFFICIENCY_MED = 0.75
RESTORATIVE_HIGH = 0.35
RESTORATIVE_MED = 0.25
def map_inputs_to_states(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw inputs to EMISSION_CPT variables.

    - Hooper (1..7) -> low/medium/high for subjective_* variables
    - Direct categorical passthrough for sleep/HRV/nutrition/GI/fatigue_3day_state
    - Direct booleans for journal keys (is_sick/is_injured/high_stress_event_today/meditation_done_today)
    """
    mapped: Dict[str, Any] = {}

    # ===== 苹果睡眠评分优先处理（仅当 iOS 版本 >= 26 时启用）=====
    apple_sleep_score = raw_inputs.get('apple_sleep_score')
    ios_version = raw_inputs.get('ios_version')
    try:
        ios_ver_int = int(ios_version) if ios_version is not None else None
    except Exception:
        ios_ver_int = None

    if apple_sleep_score is not None and ios_ver_int is not None and ios_ver_int >= 26:
        # 使用苹果原生睡眠评分，跳过传统的时长+效率计算
        try:
            score = float(apple_sleep_score)
            if score >= 80:
                mapped['apple_sleep_score'] = 'excellent'
            elif score >= 70:
                mapped['apple_sleep_score'] = 'good'
            elif score >= 60:
                mapped['apple_sleep_score'] = 'fair'
            elif score >= 40:
                mapped['apple_sleep_score'] = 'poor'
            else:
                mapped['apple_sleep_score'] = 'very_poor'
            # 鏍囪浣跨敤浜嗚嫻鏋滆瘎鍒嗭紝璺宠繃浼犵粺鐫＄湢璁＄畻
            mapped['_using_apple_sleep_score'] = True
        except Exception:
            pass
            # Parsing failed; fallback to traditional mapping
            pass
    # 1) Sleep performance: duration + efficiency (duration personalized; efficiency fixed by default)
    if 'sleep_performance_state' not in raw_inputs and not mapped.get('_using_apple_sleep_score', False):
        if raw_inputs.get('sleep_duration_hours') is not None:
            try:
                duration_hours = float(raw_inputs['sleep_duration_hours'])
            except Exception:
                duration_hours = None
        elif raw_inputs.get('total_sleep_minutes') is not None:
            try:
                duration_hours = float(raw_inputs['total_sleep_minutes']) / 60.0
            except Exception:
                duration_hours = None

        eff = None
        if raw_inputs.get('sleep_efficiency') is not None:
            try:
                eff = float(raw_inputs['sleep_efficiency'])
                if eff > 1.0:
                    eff = eff / 100.0
            except Exception:
                eff = None

        mu_dur = None
        mu_eff = None
        try:
            if raw_inputs.get('sleep_baseline_hours') is not None:
                mu_dur = float(raw_inputs['sleep_baseline_hours'])
            if raw_inputs.get('sleep_baseline_eff') is not None:
                mu_eff = float(raw_inputs['sleep_baseline_eff'])
                if mu_eff > 1.0:
                    mu_eff = mu_eff / 100.0
        except Exception:
            mu_dur = mu_eff = None

        if duration_hours is not None and eff is not None:
            # Duration thresholds (personalized): good=min(9, max(7, mu_dur + 1)); medium=min(8, max(6, mu_dur - 0.5))
            good_dur_threshold = 7.0 if mu_dur is None else min(9.0, max(7.0, mu_dur + 1.0))
            good_eff_threshold = EFFICIENCY_GOOD if mu_eff is None else max(EFFICIENCY_GOOD, mu_eff - 0.05)
            med_dur_threshold = 6.0 if mu_dur is None else min(8.0, max(6.0, mu_dur - 0.5))
            med_eff_threshold = EFFICIENCY_MED if mu_eff is None else max(EFFICIENCY_MED, mu_eff - 0.10)
            # Default: disable efficiency personalization; use fixed thresholds unless flag is on
            if not PERSONALIZE_SLEEP_EFFICIENCY:
                good_eff_threshold = EFFICIENCY_GOOD
                med_eff_threshold = EFFICIENCY_MED

            if duration_hours >= good_dur_threshold and eff >= good_eff_threshold:
                mapped['sleep_performance'] = 'good'
            elif duration_hours >= med_dur_threshold and eff >= med_eff_threshold:
                mapped['sleep_performance'] = 'medium'
            else:
                mapped['sleep_performance'] = 'poor'

    # 2) Restorative sleep (deep + REM ratio; baseline optional)
    if 'restorative_sleep' not in raw_inputs and 'restorative_sleep' not in mapped:
        rest_ratio = None
        if raw_inputs.get('restorative_ratio') is not None:
            try:
                rest_ratio = float(raw_inputs['restorative_ratio'])
            except Exception:
                rest_ratio = None
        else:
            try:
                deep = raw_inputs.get('deep_sleep_ratio')
                rem = raw_inputs.get('rem_sleep_ratio')
                if deep is not None and rem is not None:
                    rest_ratio = float(deep) + float(rem)
            except Exception:
                rest_ratio = None

        mu_rest = None
        try:
            if raw_inputs.get('rest_baseline_ratio') is not None:
                mu_rest = float(raw_inputs['rest_baseline_ratio'])
        except Exception:
            mu_rest = None

        if rest_ratio is not None:
            # Restorative thresholds (fixed by default): high>=0.35, medium>=0.25
            high_thr = RESTORATIVE_HIGH if mu_rest is None else min(0.55, max(RESTORATIVE_HIGH, mu_rest + 0.10))
            med_thr = RESTORATIVE_MED if mu_rest is None else max(RESTORATIVE_MED, mu_rest - 0.05)
            # 默认关闭恢复性个性化：使用固定阈值；若开启，则保留上面的个性化结果
            if not PERSONALIZE_RESTORATIVE:
                high_thr = RESTORATIVE_HIGH
                med_thr = RESTORATIVE_MED
            
            if rest_ratio >= high_thr:
                mapped['restorative_sleep'] = 'high'
            elif rest_ratio >= med_thr:
                mapped['restorative_sleep'] = 'medium'
            else:
                mapped['restorative_sleep'] = 'low'

    # 3) HRV 瓒嬪娍 hrv_trend锛堜紭鍏堝熀绾?z 鍒嗘暟锛涚己澶卞熀绾挎椂閫€鍥?3/7 澶╃浉瀵瑰彉鍖栵級
    if 'hrv_trend' not in raw_inputs and 'hrv_trend' not in mapped:
        today = None
        mu = None
        sd = None
        try:
            if raw_inputs.get('hrv_rmssd_today') is not None:
                today = float(raw_inputs['hrv_rmssd_today'])
            if raw_inputs.get('hrv_baseline_mu') is not None:
                mu = float(raw_inputs['hrv_baseline_mu'])
            if raw_inputs.get('hrv_baseline_sd') is not None:
                sd = float(raw_inputs['hrv_baseline_sd'])
            if mu is None and raw_inputs.get('hrv_rmssd_28day_avg') is not None:
                mu = float(raw_inputs['hrv_rmssd_28day_avg'])
            if sd is None and raw_inputs.get('hrv_rmssd_28day_sd') is not None:
                sd = float(raw_inputs['hrv_rmssd_28day_sd'])
            if mu is None and raw_inputs.get('hrv_rmssd_21day_avg') is not None:
                mu = float(raw_inputs['hrv_rmssd_21day_avg'])
            if sd is None and raw_inputs.get('hrv_rmssd_21day_sd') is not None:
                sd = float(raw_inputs['hrv_rmssd_21day_sd'])
        except Exception:
            today = mu = sd = None

        categorized = False
        if today is not None and mu is not None and sd is not None and sd > 0:
            z = (today - mu) / sd
            if z >= 0.5:
                mapped['hrv_trend'] = 'rising'
            elif z <= -1.5:
                mapped['hrv_trend'] = 'significant_decline'
            elif z <= -0.5:
                mapped['hrv_trend'] = 'slight_decline'
            else:
                mapped['hrv_trend'] = 'stable'
            categorized = True

        if not categorized:
            rmssd3 = None
            rmssd7 = None
            try:
                if raw_inputs.get('hrv_rmssd_3day_avg') is not None:
                    rmssd3 = float(raw_inputs['hrv_rmssd_3day_avg'])
                if raw_inputs.get('hrv_rmssd_7day_avg') is not None:
                    rmssd7 = float(raw_inputs['hrv_rmssd_7day_avg'])
                if rmssd3 is None and raw_inputs.get('hrv_rmssd_today') is not None:
                    rmssd3 = float(raw_inputs['hrv_rmssd_today'])
            except Exception:
                rmssd3 = rmssd7 = None
            if rmssd3 is not None and rmssd7 is not None and rmssd7 > 0:
                delta = (rmssd3 - rmssd7) / rmssd7
                if delta >= 0.03:
                    mapped['hrv_trend'] = 'rising'
                elif delta <= -0.08:
                    mapped['hrv_trend'] = 'significant_decline'
                elif delta <= -0.03:
                    mapped['hrv_trend'] = 'slight_decline'
                else:
                    mapped['hrv_trend'] = 'stable'

    # --- HealthKit numeric 鈫?enum mapping (only if enum not already present) ---
    # Sleep performance: duration (hours or minutes) + efficiency (0..1 or 0..100)
    if 'sleep_performance_state' not in raw_inputs and not mapped.get('_using_apple_sleep_score', False) and 'sleep_performance' not in mapped:
        duration_hours = None
        if raw_inputs.get('sleep_duration_hours') is not None:
            try:
                duration_hours = float(raw_inputs['sleep_duration_hours'])
            except Exception:
                duration_hours = None
        elif raw_inputs.get('total_sleep_minutes') is not None:
            try:
                duration_hours = float(raw_inputs['total_sleep_minutes']) / 60.0
            except Exception:
                duration_hours = None

        eff = None
        if raw_inputs.get('sleep_efficiency') is not None:
            try:
                eff = float(raw_inputs['sleep_efficiency'])
                if eff > 1.0:
                    eff = eff / 100.0
            except Exception:
                eff = None

        if duration_hours is not None and eff is not None:
            if duration_hours >= 7.0 and eff >= EFFICIENCY_GOOD:
                mapped['sleep_performance'] = 'good'
            elif duration_hours >= 6.0 and eff >= EFFICIENCY_MED:
                mapped['sleep_performance'] = 'medium'
            else:
                mapped['sleep_performance'] = 'poor'

    # Restorative sleep: deep+REM ratio (or directly given restorative_ratio)
    if 'restorative_sleep' not in raw_inputs and 'restorative_sleep' not in mapped:
        rest_ratio = None
        if raw_inputs.get('restorative_ratio') is not None:
            try:
                rest_ratio = float(raw_inputs['restorative_ratio'])
            except Exception:
                rest_ratio = None
        else:
            try:
                deep = raw_inputs.get('deep_sleep_ratio')
                rem = raw_inputs.get('rem_sleep_ratio')
                if deep is not None and rem is not None:
                    rest_ratio = float(deep) + float(rem)
            except Exception:
                rest_ratio = None
        if rest_ratio is not None:
            # 绉戝鍖栫殑鎭㈠鎬х潯鐪犺瘎鍒ゆ爣鍑嗭紙鏃犲熀绾挎椂浣跨敤鍥哄畾闃堝€硷級
            if rest_ratio >= RESTORATIVE_HIGH:  # 鎻愰珮high鏍囧噯浠?5%鍒?5%
                mapped['restorative_sleep'] = 'high'
            elif rest_ratio >= RESTORATIVE_MED:  # 鎻愰珮medium鏍囧噯浠?0%鍒?5%
                mapped['restorative_sleep'] = 'medium'
            else:
                mapped['restorative_sleep'] = 'low'

    # HRV trend from RMSSD averages
    if 'hrv_trend' not in raw_inputs and 'hrv_trend' not in mapped:
        rmssd3 = None
        rmssd7 = None
        try:
            if raw_inputs.get('hrv_rmssd_3day_avg') is not None:
                rmssd3 = float(raw_inputs['hrv_rmssd_3day_avg'])
            if raw_inputs.get('hrv_rmssd_7day_avg') is not None:
                rmssd7 = float(raw_inputs['hrv_rmssd_7day_avg'])
            if rmssd3 is None and raw_inputs.get('hrv_rmssd_today') is not None:
                rmssd3 = float(raw_inputs['hrv_rmssd_today'])
        except Exception:
            rmssd3 = rmssd7 = None
        if rmssd3 is not None and rmssd7 is not None and rmssd7 > 0:
            delta = (rmssd3 - rmssd7) / rmssd7
            if delta >= 0.03:
                mapped['hrv_trend'] = 'rising'
            elif delta <= -0.08:
                mapped['hrv_trend'] = 'significant_decline'
            elif delta <= -0.03:
                mapped['hrv_trend'] = 'slight_decline'
            else:
                mapped['hrv_trend'] = 'stable'

    # Hooper mappings (categorical + keep numeric score for continuous mapping)
    hooper_mapping = {
        'fatigue_hooper': 'subjective_fatigue',
        'soreness_hooper': 'muscle_soreness',
        'stress_hooper': 'subjective_stress',
        'sleep_hooper': 'subjective_sleep',
    }
    for raw_key, model_key in hooper_mapping.items():
        if raw_key in raw_inputs:
            val = raw_inputs[raw_key]
            if val is not None and isinstance(val, (int, float)) and 1 <= val <= 7:
                # Keep numeric score for continuous mapping in engine
                mapped[f"{raw_key}_score"] = int(val)
                if val <= 2:
                    mapped[model_key] = 'low'
                elif val <= 4:
                    mapped[model_key] = 'medium'
                else:
                    mapped[model_key] = 'high'

    # Direct categorical passthrough
    for key in ['sleep_performance_state', 'restorative_sleep', 'hrv_trend', 'nutrition', 'gi_symptoms', 'fatigue_3day_state']:
        if key in raw_inputs and raw_inputs[key] is not None:
            # If Apple sleep score is present, enforce either-or: drop traditional sleep_performance
            if key == 'sleep_performance_state' and mapped.get('_using_apple_sleep_score', False):
                continue
            mapped[key.replace('_state', '')] = raw_inputs[key]

    # Enforce either-or at the end defensively: if Apple score is used, drop any sleep_performance that may have slipped in
    if mapped.get('_using_apple_sleep_score', False):
        mapped.pop('sleep_performance', None)

    # Direct boolean journal evidence
    for key in ['is_sick', 'is_injured', 'high_stress_event_today', 'meditation_done_today']:
        if key in raw_inputs and raw_inputs[key] is not None:
            mapped[key] = raw_inputs[key]

    return mapped

__all__ = ['map_inputs_to_states']
