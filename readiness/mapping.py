"""Input mapping helpers for the Readiness model (migrated).

Also supports mapping HealthKit-like numeric fields to model enums when enums
are not provided:
- sleep_performance_state from sleep_duration_hours/total_sleep_minutes and
  sleep_efficiency
- restorative_sleep from restorative_ratio or deep_sleep_ratio + rem_sleep_ratio
- hrv_trend from hrv_rmssd_3day_avg vs hrv_rmssd_7day_avg (or today vs 7-day)
"""

from __future__ import annotations
from typing import Any, Dict

def map_inputs_to_states(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw inputs to model variables used in EMISSION_CPT.

    - Hooper (1..7) → low/medium/high for subjective_* variables
    - Direct categorical passthrough for sleep/HRV/nutrition/GI/fatigue_3day_state
    - Direct booleans for journal keys (is_sick/is_injured/high_stress_event_today/meditation_done_today)
    """
    mapped: Dict[str, Any] = {}

    # ===== HealthKit 数值 → 枚举（若未传枚举时按数值和个体基线映射） =====
    # 1) 睡眠表现 sleep_performance_state（时长+效率：绝对阈值 ∧ 个体基线）
    if 'sleep_performance_state' not in raw_inputs:
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
            good_dur_threshold = 7.0 if mu_dur is None else max(7.0, mu_dur - 0.5)
            good_eff_threshold = 0.85 if mu_eff is None else max(0.85, mu_eff - 0.05)
            med_dur_threshold = 6.0 if mu_dur is None else max(6.0, mu_dur - 1.0)
            med_eff_threshold = 0.75 if mu_eff is None else max(0.75, mu_eff - 0.10)

            if duration_hours >= good_dur_threshold and eff >= good_eff_threshold:
                mapped['sleep_performance'] = 'good'
            elif duration_hours >= med_dur_threshold and eff >= med_eff_threshold:
                mapped['sleep_performance'] = 'medium'
            else:
                mapped['sleep_performance'] = 'poor'

    # 2) 恢复性睡眠 restorative_sleep（深睡+REM 占比：绝对阈值 ∧ 个体基线）
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
            high_thr = 0.45 if mu_rest is None else max(0.45, mu_rest + 0.05)
            if rest_ratio >= high_thr:
                mapped['restorative_sleep'] = 'high'
            elif (mu_rest is not None and abs(rest_ratio - mu_rest) <= 0.05) or rest_ratio >= 0.30:
                mapped['restorative_sleep'] = 'medium'
            else:
                mapped['restorative_sleep'] = 'low'

    # 3) HRV 趋势 hrv_trend（优先基线 z 分数；缺失基线时退回 3/7 天相对变化）
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

    # --- HealthKit numeric → enum mapping (only if enum not already present) ---
    # Sleep performance: duration (hours or minutes) + efficiency (0..1 or 0..100)
    if 'sleep_performance_state' not in raw_inputs:
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
            if duration_hours >= 7.0 and eff >= 0.85:
                mapped['sleep_performance'] = 'good'
            elif duration_hours >= 6.0 and eff >= 0.75:
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
            if rest_ratio >= 0.45:
                mapped['restorative_sleep'] = 'high'
            elif rest_ratio >= 0.30:
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
            mapped[key.replace('_state', '')] = raw_inputs[key]

    # Direct boolean journal evidence
    for key in ['is_sick', 'is_injured', 'high_stress_event_today', 'meditation_done_today']:
        if key in raw_inputs and raw_inputs[key] is not None:
            mapped[key] = raw_inputs[key]

    return mapped

__all__ = ['map_inputs_to_states']
