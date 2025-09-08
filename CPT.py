import numpy as np
import pandas as pd

# --- 核心概率表 ---

# Emission CPT (P(Evidence | State)) - 最终版症状指纹库
# ** 已根据您的图片和要求进行完整填充，并将HRV趋势细化为4个状态 **
EMISSION_CPT = {
    'subjective_fatigue': {
        'low': {'Peak': 0.80, 'Well-adapted': 0.70, 'FOR': 0.25, 'Acute Fatigue': 0.05, 'NFOR': 0.05, 'OTS': 1e-6},
        'medium': {'Peak': 0.15, 'Well-adapted': 0.30, 'FOR': 0.20, 'Acute Fatigue': 0.15, 'NFOR': 0.10, 'OTS': 0.05},
        'high': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.70, 'Acute Fatigue': 0.80, 'NFOR': 0.80, 'OTS': 0.90}
    },
    'muscle_soreness': {
        'low': {'Peak': 0.80, 'Well-adapted': 0.75, 'FOR': 0.35, 'Acute Fatigue': 0.10, 'NFOR': 0.10, 'OTS': 0.20},
        'medium': {'Peak': 0.10, 'Well-adapted': 0.25, 'FOR': 0.50, 'Acute Fatigue': 0.30, 'NFOR': 0.40, 'OTS': 0.50},
        'high': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.35, 'Acute Fatigue': 0.60, 'NFOR': 0.50, 'OTS': 0.30}
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
        'slight_decline': {'Peak': 0.05, 'Well-adapted': 0.10, 'FOR': 0.30, 'Acute Fatigue': 0.30, 'NFOR': 0.15,
                           'OTS': 0.09},
        'significant_decline': {'Peak': 1e-6, 'Well-adapted': 1e-6, 'FOR': 0.40, 'Acute Fatigue': 0.40, 'NFOR': 0.70,
                                'OTS': 0.80}
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
    }
}

# Baseline Transition CPT (P(Today | Yesterday))
BASELINE_TRANSITION_CPT = {
    'Peak': {'Peak': 0.80, 'Well-adapted': 0.10, 'FOR': 0.05, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'Well-adapted': {'Peak': 0.60, 'Well-adapted': 0.35, 'FOR': 0.05, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6, 'OTS': 1e-6},
    'FOR': {'Peak': 0.05, 'Well-adapted': 0.40, 'FOR': 0.30, 'Acute Fatigue': 0.10, 'NFOR': 0.10, 'OTS': 0.05},
    'Acute Fatigue': {'Peak': 0.20, 'Well-adapted': 0.70, 'FOR': 0.10, 'Acute Fatigue': 1e-6, 'NFOR': 1e-6,
                      'OTS': 1e-6},
    'NFOR': {'Peak': 0.01, 'Well-adapted': 0.05, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.70, 'OTS': 0.09},
    'OTS': {'Peak': 0.01, 'Well-adapted': 0.04, 'FOR': 0.10, 'Acute Fatigue': 0.05, 'NFOR': 0.30, 'OTS': 0.50}
}
# 确保每行概率总和为1
for state in BASELINE_TRANSITION_CPT:
    total = sum(BASELINE_TRANSITION_CPT[state].values())
    if total > 0:
        BASELINE_TRANSITION_CPT[state] = {s: p / total for s, p in BASELINE_TRANSITION_CPT[state].items()}

READINESS_WEIGHTS = {'Peak': 100, 'Well-adapted': 85, 'FOR': 60, 'Acute Fatigue': 50, 'NFOR': 30, 'OTS': 10}


class DBN_Engine:
    def __init__(self):
        self.states = list(BASELINE_TRANSITION_CPT.keys())
        self.training_history = []  # 新增：训练历史记录
        
    def add_training_day(self, training_load, day_number=None):
        """添加训练日记录用于NFOR累积规则"""
        self.training_history.append({
            'day': day_number or len(self.training_history) + 1,
            'training_load': training_load
        })
    
    def clear_training_history(self):
        """清空训练历史"""
        self.training_history = []
    
    def check_nfor_persistence_rule(self, prior_probs):
        """检查NFOR持久规则：前验NFOR>30%时，限制快速恢复"""
        if prior_probs.get('NFOR', 0) > 0.3:
            return 0.3  # 转移30%回NFOR/FOR
        return 0
    
    def check_nfor_accumulation_rules(self):
        """检查NFOR累积规则并分别返回4天和8天规则的转移量"""
        four_day_transfer = 0
        eight_day_transfer = 0
        applied_rules = []
        
        # 检查4天滚动窗口规则
        if len(self.training_history) >= 4:
            recent_4_days = self.training_history[-4:]
            high_intensity_count = sum(1 for day in recent_4_days if day['training_load'] in ['高', '极高'])
            medium_intensity_count = sum(1 for day in recent_4_days if day['training_load'] == '中')
            
            if high_intensity_count >= 3 and medium_intensity_count >= 1:
                four_day_transfer = 0.50  # 4天规则转移50%
                applied_rules.append("连续4天规则(3高+1中)")
        
        # 检查8天滚动窗口规则 - 可以在4天规则基础上再次触发
        if len(self.training_history) >= 8:
            recent_8_days = self.training_history[-8:]
            high_intensity_count = sum(1 for day in recent_8_days if day['training_load'] in ['高', '极高'])
            
            if high_intensity_count >= 6:
                eight_day_transfer = 0.60  # 8天规则转移60%
                applied_rules.append("分散8天规则(6次高强度)")
        
        return four_day_transfer, eight_day_transfer, applied_rules

    def _shift_probability(self, probs, from_states, to_states, amount):
        from_states = [s for s in from_states if s in probs]
        to_states = [s for s in to_states if s in probs]
        if not from_states or not to_states: return probs
        total_from_prob = sum(probs.get(s, 0) for s in from_states)
        if total_from_prob == 0: return probs
        amount_to_shift = total_from_prob * amount
        for s in from_states:
            if total_from_prob > 0: probs[s] -= amount_to_shift * (probs.get(s, 0) / total_from_prob)
        for s in to_states: probs[s] += amount_to_shift / len(to_states)
        return probs

    def _get_pss10_decay_factor(self, pss10_context):
        if not pss10_context: return 1.0
        initial_factor = pss10_context.get('initial_factor', 1.0)
        days_since = pss10_context.get('days_since_test', 0)
        decay_rate = 0.8
        return 1.0 + (initial_factor - 1.0) * (decay_rate ** days_since)

    def calculate_transition_probabilities(self, yesterday_probs, causal_inputs):
        today_probs = {s: 0 for s in self.states}
        for prev_state, prev_prob in yesterday_probs.items():
            if prev_prob > 0:
                for today_state, transition_prob in BASELINE_TRANSITION_CPT[prev_state].items():
                    today_probs[today_state] += prev_prob * transition_prob

        load = causal_inputs.get('training_load', '无')
        sleep = causal_inputs.get('subjective_sleep_state', 'good')

        if load == '极高':
            today_probs = self._shift_probability(today_probs, ['Peak', 'Well-adapted'], ['FOR', 'Acute Fatigue'], 0.85)
        elif load == '高':
            today_probs = self._shift_probability(today_probs, ['Peak', 'Well-adapted'], ['FOR', 'Acute Fatigue'], 0.60)

        if causal_inputs.get('cumulative_fatigue_14day_state') == 'high':
            today_probs = self._shift_probability(today_probs, ['Peak', 'Well-adapted', 'FOR'], ['NFOR', 'OTS'], 0.1)

        if sleep == 'poor':
            pss10_factor = self._get_pss10_decay_factor(causal_inputs.get('pss10_context'))
            today_probs = self._shift_probability(today_probs, ['Peak', 'Well-adapted'], ['NFOR'], 0.4 * pss10_factor)

        total = sum(today_probs.values())
        return {s: p / total for s, p in today_probs.items()}

    def run_bayesian_update(self, prior_probs, symptom_evidence):
        posterior_probs = prior_probs.copy()

        for evidence_type, value in symptom_evidence.items():
            if evidence_type in EMISSION_CPT and value is not None:
                for state in self.states:
                    likelihood = EMISSION_CPT[evidence_type].get(value, {}).get(state, 0.001)
                    posterior_probs[state] *= likelihood

        if symptom_evidence.get('fatigue_3day_state') == 'high':
            posterior_probs['Peak'] *= 0.01

        if symptom_evidence.get('muscle_soreness') == 'low' and symptom_evidence.get('subjective_stress') == 'high':
            posterior_probs['NFOR'] *= 2.0
            posterior_probs['FOR'] *= 0.5

        # 营养不良分级特殊逻辑：只有当nutrition实际提供时才执行
        if 'nutrition' in symptom_evidence and symptom_evidence.get('nutrition') is not None:
            peak_well_adapted_prob = posterior_probs.get('Peak', 0) + posterior_probs.get('Well-adapted', 0)
            current_total = sum(posterior_probs.values())
            
            if current_total > 0:
                peak_well_adapted_ratio = peak_well_adapted_prob / current_total
                
                if peak_well_adapted_ratio >= 0.80:
                    nutrition_status = symptom_evidence.get('nutrition')
                    shift_amount = 0
                    
                    if nutrition_status == 'inadequate_mild':
                        shift_amount = 0.15  # 轻度营养不良：15%转移
                    elif nutrition_status == 'inadequate_moderate': 
                        shift_amount = 0.25  # 中度营养不良：25%转移
                    elif nutrition_status == 'inadequate_severe':
                        shift_amount = 0.35  # 重度营养不良：35%转移
                    
                    if shift_amount > 0:
                        # 从Peak和Well-adapted向NFOR转移指定概率
                        posterior_probs = self._shift_probability(posterior_probs, ['Peak', 'Well-adapted'], ['NFOR'], shift_amount)

        # 新增：NFOR累积规则 - 基于训练历史的概率转移（进阶触发）
        four_day_transfer, eight_day_transfer, nfor_rules_applied = self.check_nfor_accumulation_rules()
        
        # 先执行4天规则转移（如果触发）
        if four_day_transfer > 0:
            posterior_probs = self._shift_probability(posterior_probs, 
                ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue'], ['NFOR'], four_day_transfer)
        
        # 再在新状态基础上执行8天规则转移（如果触发）
        if eight_day_transfer > 0:
            posterior_probs = self._shift_probability(posterior_probs, 
                ['Peak', 'Well-adapted', 'FOR', 'Acute Fatigue'], ['NFOR'], eight_day_transfer)

        # 新增：NFOR持久规则 - 防止NFOR快速恢复
        persistence_transfer = self.check_nfor_persistence_rule(prior_probs)
        if persistence_transfer > 0:
            posterior_probs = self._shift_probability(posterior_probs, 
                ['Peak', 'Well-adapted'], ['NFOR', 'FOR'], persistence_transfer)

        total = sum(posterior_probs.values())
        if total == 0: return {s: 1 / len(self.states) for s in self.states}
        return {s: p / total for s, p in posterior_probs.items()}

    def get_readiness_score(self, probs):
        score = sum(probs.get(state, 0) * READINESS_WEIGHTS.get(state, 0) for state in self.states)
        return round(score)

    def display_results(self, day, prior, posterior):
        df = pd.DataFrame([prior, posterior], index=['先验概率 (预测)', '后验概率 (诊断)']).T
        df.index.name = f"--- Day {day}: 诊断流程 ---"
        df['后验概率 (诊断)'] = df['后验概率 (诊断)'].apply(lambda x: f"{x:.1%}")
        df['先验概率 (预测)'] = df['先验概率 (预测)'].apply(lambda x: f"{x:.1%}")
        print(df.to_string())
        diagnosis = max(posterior, key=posterior.get)
        readiness_score = self.get_readiness_score(posterior)
        print(f"\n[+] 最终诊断: {diagnosis} (置信度: {posterior[diagnosis]:.1%})")
        print(f"[+] 综合准备度分数: {readiness_score} / 100\n" + "=" * 40)


def map_inputs_to_states(inputs):
    evidence = {}
    
    # 只处理实际提供的Hooper量表数据
    if 'fatigue_hooper' in inputs and inputs['fatigue_hooper'] is not None:
        evidence['subjective_fatigue'] = 'high' if inputs['fatigue_hooper'] >= 6 else 'medium' if inputs['fatigue_hooper'] >= 3 else 'low'
    
    if 'soreness_hooper' in inputs and inputs['soreness_hooper'] is not None:
        evidence['muscle_soreness'] = 'high' if inputs['soreness_hooper'] >= 6 else 'medium' if inputs['soreness_hooper'] >= 3 else 'low'
    
    if 'stress_hooper' in inputs and inputs['stress_hooper'] is not None:
        evidence['subjective_stress'] = 'high' if inputs['stress_hooper'] >= 6 else 'medium' if inputs['stress_hooper'] >= 3 else 'low'
    
    if 'sleep_hooper' in inputs and inputs['sleep_hooper'] is not None:
        evidence['subjective_sleep'] = 'poor' if inputs['sleep_hooper'] >= 6 else 'medium' if inputs['sleep_hooper'] >= 3 else 'good'
    
    # 只处理实际提供的其他症状数据
    optional_symptoms = ['sleep_performance_state', 'restorative_sleep', 'hrv_trend', 'nutrition', 'gi_symptoms', 'fatigue_3day_state']
    for symptom in optional_symptoms:
        if symptom in inputs and inputs[symptom] is not None:
            evidence[symptom] = inputs[symptom]
    
    return evidence


# --- 用户输入模板与说明 ---
if __name__ == '__main__':
    engine = DBN_Engine()

    # --- Day 0: 设定初始状态 ---
    previous_day_probabilities = {
        'Peak': 0, 'Well-adapted': 0, 'FOR': 0.3,
        'Acute Fatigue': 0.1, 'NFOR': 0.6, 'OTS': 0.0
    }

    # --- PSS-10 背景压力设定 ---
    pss10_context = {'initial_factor': 1, 'days_since_test': 1}

    # --- 当天的因果性输入 ---
    causal_inputs = {
        # 当日训练负荷: '无', '低', '中', '高', '极高'
        'training_load': '高',
        # 主观睡眠状态: 'good', 'medium', 'poor' (由 sleep_hooper 分数自动转换)
        'subjective_sleep_state': 'poor',
        # PSS-10 背景压力
        'pss10_context': pss10_context,
        # 14天累积疲劳状态: 'high', 'low'
        'cumulative_fatigue_14day_state': 'high'
    }

    # --- 当天的症状证据输入 ---
    # ** 如果某项数据缺失，直接从字典中删除那一行即可 **
    symptom_inputs = {
        # Hooper Index (1-7分, 分数越高感觉越差)
        'fatigue_hooper': 6,
        'soreness_hooper': 6,
        'stress_hooper': 3,
        # Hooper Sleep (1-7分, 分数越高感觉越差)
        'sleep_hooper': 5,

        # 客观睡眠量化表现: 'good', 'medium', 'poor'
        'sleep_performance_state': 'medium',
        
        # 恢复性睡眠质量: 'high', 'medium', 'low'
        'restorative_sleep': 'medium',

        # HRV 趋势: 'rising', 'stable', 'slight_decline', 'significant_decline'
        'hrv_trend': 'slight_decline',  # 使用新的'stable'状态

        # 营养状况: 'adequate', 'inadequate_mild', 'inadequate_moderate', 'inadequate_severe'
        'nutrition': 'adequate',

        # 肠胃症状: 'none', 'mild', 'severe'
        'gi_symptoms': 'none',

        # 3天即时疲劳状态: 'high', 'low'
        'fatigue_3day_state': 'low'
    }

    # --- 运行并展示结果 ---
    print("=" * 15 + " 开始模拟 " + "=" * 15)
    # 阶段一
    prior = engine.calculate_transition_probabilities(previous_day_probabilities, causal_inputs)
    # 阶段二
    posterior = engine.run_bayesian_update(prior, map_inputs_to_states(symptom_inputs))
    # 展示
    engine.display_results(1, prior, posterior)