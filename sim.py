import numpy as np
import random
from CPT_test import DBN_Engine, map_inputs_to_states

engine = DBN_Engine()
results_a = []
results_b = []

print("30天训练策略对比模拟")
print("策略A: 练3休1，第13天后连续训练")

# 策略A
previous_probs_a = {'Peak': 0.3, 'Well-adapted': 0.5, 'FOR': 0.15, 'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0}

for day in range(1, 31):
    if day <= 12:
        cycle_day = (day - 1) % 4 + 1
        training_load = random.choice(['中', '高']) if cycle_day <= 3 else '无'
    else:
        training_load = random.choice(['高', '极高'])
        
    symptoms = {
        'fatigue_hooper': 3 + (2 if training_load in ['高', '极高'] else 0),
        'soreness_hooper': 3 + (2 if training_load in ['高', '极高'] else 0),
        'stress_hooper': 2 + (1 if day > 15 else 0),
        'sleep_hooper': 2,
        'sleep_performance_state': 'medium',
        'restorative_sleep': 'medium',
        'hrv_trend': 'slight_decline' if day > 20 else 'stable',
        'nutrition': 'adequate',
        'gi_symptoms': 'none',
        'fatigue_3day_state': 'high' if day > 18 else 'low'
    }
    
    causal_inputs = {
        'training_load': training_load,
        'subjective_sleep_state': 'good',
        'cumulative_fatigue_14day_state': 'high' if day > 15 else 'low',
        'pss10_context': {'initial_factor': 1, 'days_since_test': 1}
    }
    
    prior = engine.calculate_transition_probabilities(previous_probs_a, causal_inputs)
    posterior = engine.run_bayesian_update(prior, map_inputs_to_states(symptoms))
    readiness_score = engine.get_readiness_score(posterior)
    
    diagnosis = max(posterior, key=posterior.get)
    results_a.append(readiness_score)
    
    print(f"第{day}天: 训练[{training_load:^4}] 准备度[{readiness_score:2d}/100] 诊断[{diagnosis}]")
    previous_probs_a = posterior

print("\n策略B: 智能休息策略")

# 策略B
previous_probs_b = {'Peak': 0.3, 'Well-adapted': 0.5, 'FOR': 0.15, 'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0}

for day in range(1, 31):
    if day <= 12:
        cycle_day = (day - 1) % 4 + 1
        training_load = random.choice(['中', '高']) if cycle_day <= 3 else '无'
    else:
        if day in [16, 23]:
            training_load = '无'
            print(f"第{day}天: 智能休息")
        else:
            cycle_day = (day - 1) % 4 + 1
            training_load = random.choice(['中', '高']) if cycle_day <= 3 else '无'
            
    symptoms = {
        'fatigue_hooper': 3 + (1 if training_load in ['高'] else 0),
        'soreness_hooper': 3 + (1 if training_load in ['高'] else 0), 
        'stress_hooper': 2,
        'sleep_hooper': 2,
        'sleep_performance_state': 'good',
        'restorative_sleep': 'high' if training_load == '无' else 'medium',
        'hrv_trend': 'stable',
        'nutrition': 'adequate',
        'gi_symptoms': 'none',
        'fatigue_3day_state': 'low'
    }
    
    causal_inputs = {
        'training_load': training_load,
        'subjective_sleep_state': 'good',
        'cumulative_fatigue_14day_state': 'low',
        'pss10_context': {'initial_factor': 1, 'days_since_test': 1}
    }
    
    prior = engine.calculate_transition_probabilities(previous_probs_b, causal_inputs)
    posterior = engine.run_bayesian_update(prior, map_inputs_to_states(symptoms))
    readiness_score = engine.get_readiness_score(posterior)
    
    diagnosis = max(posterior, key=posterior.get)
    results_b.append(readiness_score)
    
    print(f"第{day}天: 训练[{training_load:^4}] 准备度[{readiness_score:2d}/100] 诊断[{diagnosis}]")
    previous_probs_b = posterior

print("\n结果分析:")
avg_a = np.mean(results_a)
avg_b = np.mean(results_b)
last_week_a = np.mean(results_a[-7:])
last_week_b = np.mean(results_b[-7:])

print(f"策略A平均准备度: {avg_a:.1f}/100")
print(f"策略B平均准备度: {avg_b:.1f}/100")
print(f"策略A最后一周: {last_week_a:.1f}/100")
print(f"策略B最后一周: {last_week_b:.1f}/100")
print(f"智能休息策略比连续训练策略平均高 {avg_b - avg_a:+.1f} 分")
print(f"最后一周差异: {last_week_b - last_week_a:+.1f} 分")

# 更多策略测试
print("\n" + "="*60)
print("更多训练策略测试")
print("="*60)

def test_strategy(name, pattern):
    print(f"\n{name}:")
    results = []
    previous_probs = {'Peak': 0.3, 'Well-adapted': 0.5, 'FOR': 0.15, 'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0}
    
    for day in range(1, 31):
        if name == "练2休1":
            cycle = (day-1) % 3
            load = random.choice(['中', '高']) if cycle < 2 else '无'
        elif name == "练5休1":
            cycle = (day-1) % 6
            load = random.choice(['中', '高']) if cycle < 5 else '无'
        elif name == "练6休1":
            cycle = (day-1) % 7
            load = random.choice(['中', '高']) if cycle < 6 else '无'
        elif name == "练3休1练3":
            week = (day-1) % 7 + 1
            load = random.choice(['中', '高']) if week in [1,2,3,5,6,7] else '无'
        
        # 根据策略调整症状强度
        fatigue_base = 3
        soreness_base = 3
        if name == "练6休1" and day > 15:
            fatigue_base += 2
            soreness_base += 2
        elif name == "练5休1" and day > 20:
            fatigue_base += 1
            soreness_base += 1
        elif load in ['高']:
            fatigue_base += 1
            soreness_base += 1
            
        symptoms = {
            'fatigue_hooper': min(7, fatigue_base + (1 if load == '高' else 0)),
            'soreness_hooper': min(7, soreness_base + (1 if load == '高' else 0)),
            'stress_hooper': 2,
            'sleep_hooper': 2,
            'sleep_performance_state': 'good',
            'restorative_sleep': 'high' if load == '无' else 'medium',
            'hrv_trend': 'stable',
            'nutrition': 'adequate',
            'gi_symptoms': 'none',
            'fatigue_3day_state': 'low'
        }
        
        causal = {
            'training_load': load,
            'subjective_sleep_state': 'good',
            'cumulative_fatigue_14day_state': 'low',
            'pss10_context': {'initial_factor': 1, 'days_since_test': 1}
        }
        
        prior = engine.calculate_transition_probabilities(previous_probs, causal)
        posterior = engine.run_bayesian_update(prior, map_inputs_to_states(symptoms))
        score = engine.get_readiness_score(posterior)
        
        diagnosis = max(posterior, key=posterior.get)
        results.append(score)
        print(f"第{day:2d}天: [{load:^4}] {score:2d}/100 {diagnosis}")
        previous_probs = posterior
    
    return results

# 测试所有策略
strategies = ["练2休1", "练5休1", "练6休1", "练3休1练3"]
all_results = {"策略A(原始)": results_a, "策略B(智能)": results_b}

for strategy in strategies:
    all_results[strategy] = test_strategy(strategy, None)

print("\n" + "="*80)
print("所有策略对比分析")
print("="*80)
print(f"{'策略':^15} {'平均准备度':^12} {'最后7天':^10} {'前7天':^10}")
print("-"*80)

for name, scores in all_results.items():
    avg = np.mean(scores)
    last7 = np.mean(scores[-7:])
    first7 = np.mean(scores[:7])
    print(f"{name:^15} {avg:^12.1f} {last7:^10.1f} {first7:^10.1f}")

best = max(all_results.items(), key=lambda x: np.mean(x[1]))
worst = min(all_results.items(), key=lambda x: np.mean(x[1]))

print(f"\n🏆 最优策略: {best[0]} (平均{np.mean(best[1]):.1f}分)")
print(f"❌ 最差策略: {worst[0]} (平均{np.mean(worst[1]):.1f}分)")
print(f"📊 策略差异: {np.mean(best[1]) - np.mean(worst[1]):.1f}分")
