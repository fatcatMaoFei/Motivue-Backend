#!/usr/bin/env python3
"""基线计算演示脚本

展示个人基线如何影响睡眠和HRV的判断标准，
以及相同数据在不同用户基线下的评估差异。
"""

from datetime import datetime, timedelta
import json

# 模拟基线计算逻辑（简化版）
class BaselineDemo:
    
    def __init__(self):
        # 默认阈值（无个人基线时）
        self.default_sleep_thresholds = {
            'good_duration': 7.0,
            'good_efficiency': 0.85,
            'medium_duration': 6.0,
            'medium_efficiency': 0.75
        }
        
        self.default_hrv_thresholds = {
            'rising_change': 0.03,      # 3%上升
            'slight_decline': -0.03,    # 3%下降
            'significant_decline': -0.08 # 8%下降
        }
        
        self.default_rest_thresholds = {
            'high': 0.45,
            'medium': 0.30
        }
    
    def calculate_sleep_performance(self, duration_hours, efficiency, baseline=None):
        """根据基线计算睡眠表现"""
        
        if baseline:
            # 使用个人基线调整阈值
            mu_dur = baseline.get('sleep_baseline_hours')
            mu_eff = baseline.get('sleep_baseline_eff')
            
            good_dur_threshold = 7.0 if mu_dur is None else max(7.0, mu_dur - 0.5)
            good_eff_threshold = 0.85 if mu_eff is None else max(0.85, mu_eff - 0.05)
            med_dur_threshold = 6.0 if mu_dur is None else max(6.0, mu_dur - 1.0)
            med_eff_threshold = 0.75 if mu_eff is None else max(0.75, mu_eff - 0.10)
        else:
            # 使用默认阈值
            good_dur_threshold = self.default_sleep_thresholds['good_duration']
            good_eff_threshold = self.default_sleep_thresholds['good_efficiency']
            med_dur_threshold = self.default_sleep_thresholds['medium_duration']
            med_eff_threshold = self.default_sleep_thresholds['medium_efficiency']
        
        # 判断等级
        if duration_hours >= good_dur_threshold and efficiency >= good_eff_threshold:
            return 'good', good_dur_threshold, good_eff_threshold
        elif duration_hours >= med_dur_threshold and efficiency >= med_eff_threshold:
            return 'medium', med_dur_threshold, med_eff_threshold
        else:
            return 'poor', med_dur_threshold, med_eff_threshold
    
    def calculate_hrv_trend(self, today_hrv, baseline=None, fallback_3day=None, fallback_7day=None):
        """根据基线计算HRV趋势"""
        
        if baseline and baseline.get('hrv_baseline_mu') and baseline.get('hrv_baseline_sd'):
            # 使用Z分数方法（个人基线）
            mu = baseline['hrv_baseline_mu']
            sd = baseline['hrv_baseline_sd']
            z = (today_hrv - mu) / sd
            
            if z >= 0.5:
                return 'rising', f'Z={z:.2f} (基线方法)'
            elif z <= -1.5:
                return 'significant_decline', f'Z={z:.2f} (基线方法)'
            elif z <= -0.5:
                return 'slight_decline', f'Z={z:.2f} (基线方法)'
            else:
                return 'stable', f'Z={z:.2f} (基线方法)'
        
        elif fallback_3day and fallback_7day and fallback_7day > 0:
            # 使用相对变化方法（无基线）
            delta = (fallback_3day - fallback_7day) / fallback_7day
            
            if delta >= 0.03:
                return 'rising', f'变化={delta*100:.1f}% (相对方法)'
            elif delta <= -0.08:
                return 'significant_decline', f'变化={delta*100:.1f}% (相对方法)'
            elif delta <= -0.03:
                return 'slight_decline', f'变化={delta*100:.1f}% (相对方法)'
            else:
                return 'stable', f'变化={delta*100:.1f}% (相对方法)'
        
        return 'unknown', '数据不足'
    
    def calculate_restorative_sleep(self, rest_ratio, baseline=None):
        """计算恢复性睡眠等级"""
        
        if baseline and baseline.get('rest_baseline_ratio'):
            mu_rest = baseline['rest_baseline_ratio']
            high_thr = max(0.45, mu_rest + 0.05)
            
            if rest_ratio >= high_thr:
                return 'high', high_thr
            elif abs(rest_ratio - mu_rest) <= 0.05 or rest_ratio >= 0.30:
                return 'medium', mu_rest
            else:
                return 'low', mu_rest
        else:
            # 默认阈值
            if rest_ratio >= 0.45:
                return 'high', 0.45
            elif rest_ratio >= 0.30:
                return 'medium', 0.30
            else:
                return 'low', 0.30

def create_user_profiles():
    """创建不同类型用户的基线配置"""
    
    profiles = {
        'short_sleeper': {
            'name': '短睡眠高效型 (小明)',
            'description': '需要睡眠少但质量高的用户',
            'baseline': {
                'sleep_baseline_hours': 6.2,
                'sleep_baseline_eff': 0.92,
                'rest_baseline_ratio': 0.38,
                'hrv_baseline_mu': 38.0,
                'hrv_baseline_sd': 6.5
            }
        },
        
        'long_sleeper': {
            'name': '长睡眠需求型 (小红)',  
            'description': '需要长时间睡眠才能恢复的用户',
            'baseline': {
                'sleep_baseline_hours': 8.5,
                'sleep_baseline_eff': 0.76,
                'rest_baseline_ratio': 0.42,
                'hrv_baseline_mu': 52.0,
                'hrv_baseline_sd': 9.2
            }
        },
        
        'athlete': {
            'name': '运动员型 (小强)',
            'description': '高HRV，中等睡眠需求的运动员',
            'baseline': {
                'sleep_baseline_hours': 7.8,
                'sleep_baseline_eff': 0.88,
                'rest_baseline_ratio': 0.46,
                'hrv_baseline_mu': 65.0,
                'hrv_baseline_sd': 8.8
            }
        }
    }
    
    return profiles

def demo_sleep_performance_differences():
    """演示相同睡眠数据在不同基线下的评估差异"""
    
    print("=" * 60)
    print("🛏️  睡眠表现个性化评估对比")
    print("=" * 60)
    
    demo = BaselineDemo()
    profiles = create_user_profiles()
    
    # 测试用例：相同的睡眠数据
    test_cases = [
        {'duration': 6.5, 'efficiency': 0.88, 'desc': '6.5小时/88%效率'},
        {'duration': 7.0, 'efficiency': 0.82, 'desc': '7.0小时/82%效率'},
        {'duration': 7.5, 'efficiency': 0.85, 'desc': '7.5小时/85%效率'},
        {'duration': 8.0, 'efficiency': 0.79, 'desc': '8.0小时/79%效率'}
    ]
    
    print(f"{'睡眠数据':<18} {'无基线':<12} {'短睡眠型':<12} {'长睡眠型':<12} {'运动员型':<12}")
    print("-" * 78)
    
    for case in test_cases:
        results = []
        
        # 无基线评估
        no_baseline_result, _, _ = demo.calculate_sleep_performance(
            case['duration'], case['efficiency'], None
        )
        results.append(no_baseline_result)
        
        # 各类用户基线评估
        for profile_key in ['short_sleeper', 'long_sleeper', 'athlete']:
            baseline = profiles[profile_key]['baseline']
            result, _, _ = demo.calculate_sleep_performance(
                case['duration'], case['efficiency'], baseline
            )
            results.append(result)
        
        print(f"{case['desc']:<18} {results[0]:<12} {results[1]:<12} {results[2]:<12} {results[3]:<12}")
    
    # 显示基线详情
    print(f"\n基线对比:")
    print(f"{'用户类型':<15} {'睡眠基线(小时)':<12} {'效率基线':<10} {'阈值调整'}")
    print("-" * 50)
    
    for profile_key, profile in profiles.items():
        baseline = profile['baseline']
        sleep_hours = baseline['sleep_baseline_hours']
        sleep_eff = baseline['sleep_baseline_eff']
        
        good_dur_threshold = max(7.0, sleep_hours - 0.5)
        good_eff_threshold = max(0.85, sleep_eff - 0.05)
        
        print(f"{profile['name'][:14]:<15} {sleep_hours:<12.1f} {sleep_eff:<10.2f} ≥{good_dur_threshold:.1f}h且≥{good_eff_threshold:.2f}")

def demo_hrv_trend_differences():
    """演示HRV趋势判断的差异"""
    
    print("\n" + "=" * 60)
    print("❤️  HRV趋势个性化评估对比") 
    print("=" * 60)
    
    demo = BaselineDemo()
    profiles = create_user_profiles()
    
    # 测试HRV值
    test_hrv_values = [25, 35, 45, 55, 65]
    
    print(f"{'HRV值(ms)':<10} {'无基线判断':<15} {'短睡眠型':<15} {'长睡眠型':<15} {'运动员型':<15}")
    print("-" * 75)
    
    for hrv_value in test_hrv_values:
        results = []
        
        # 无基线（使用相对变化方法）
        fallback_result, detail = demo.calculate_hrv_trend(
            hrv_value, None, hrv_value, hrv_value * 1.05  # 模拟5%下降
        )
        results.append(fallback_result)
        
        # 各用户基线判断
        for profile_key in ['short_sleeper', 'long_sleeper', 'athlete']:
            baseline = profiles[profile_key]['baseline']
            result, detail = demo.calculate_hrv_trend(hrv_value, baseline)
            results.append(result)
        
        print(f"{hrv_value:<10} {results[0]:<15} {results[1]:<15} {results[2]:<15} {results[3]:<15}")
    
    # 显示HRV基线详情
    print(f"\nHRV基线对比:")
    print(f"{'用户类型':<15} {'HRV均值(ms)':<12} {'标准差(ms)':<12} {'Z分数区间'}")
    print("-" * 55)
    
    for profile_key, profile in profiles.items():
        baseline = profile['baseline'] 
        mu = baseline['hrv_baseline_mu']
        sd = baseline['hrv_baseline_sd']
        
        # 计算各等级对应的HRV值范围
        stable_low = mu - 0.5 * sd
        stable_high = mu + 0.5 * sd
        
        print(f"{profile['name'][:14]:<15} {mu:<12.1f} {sd:<12.1f} 稳定:{stable_low:.1f}-{stable_high:.1f}")

def demo_threshold_adjustment_mechanism():
    """演示阈值调整机制的详细过程"""
    
    print("\n" + "=" * 60)
    print("🎯  阈值调整机制详细演示")
    print("=" * 60)
    
    demo = BaselineDemo()
    profiles = create_user_profiles()
    
    # 选择一个具体案例详细展示
    test_duration = 6.8
    test_efficiency = 0.86
    
    print(f"测试睡眠数据: {test_duration}小时, {test_efficiency:.2f}效率\n")
    
    # 默认阈值判断
    result_default, threshold_dur, threshold_eff = demo.calculate_sleep_performance(
        test_duration, test_efficiency, None
    )
    
    print(f"默认阈值判断:")
    print(f"  good阈值: ≥7.0小时 且 ≥0.85效率")
    print(f"  medium阈值: ≥6.0小时 且 ≥0.75效率") 
    print(f"  判断结果: {result_default}")
    print()
    
    # 各用户的个性化阈值判断
    for profile_key, profile in profiles.items():
        baseline = profile['baseline']
        result, threshold_dur, threshold_eff = demo.calculate_sleep_performance(
            test_duration, test_efficiency, baseline
        )
        
        # 计算调整后的阈值
        mu_dur = baseline['sleep_baseline_hours']
        mu_eff = baseline['sleep_baseline_eff']
        good_dur_adj = max(7.0, mu_dur - 0.5)
        good_eff_adj = max(0.85, mu_eff - 0.05)
        med_dur_adj = max(6.0, mu_dur - 1.0)
        med_eff_adj = max(0.75, mu_eff - 0.10)
        
        print(f"{profile['name']}:")
        print(f"  个人基线: {mu_dur:.1f}小时, {mu_eff:.2f}效率")
        print(f"  调整后good阈值: ≥{good_dur_adj:.1f}小时 且 ≥{good_eff_adj:.2f}效率")
        print(f"  调整后medium阈值: ≥{med_dur_adj:.1f}小时 且 ≥{med_eff_adj:.2f}效率")
        print(f"  判断结果: {result}")
        print(f"  阈值调整逻辑: max(默认值, 基线-调整量)")
        print()

def demo_complete_readiness_impact():
    """演示完整准备度计算中基线的影响"""
    
    print("\n" + "=" * 60) 
    print("🏃‍♂️  完整准备度评估影响演示")
    print("=" * 60)
    
    # 准备度状态概率权重（来自constants.py）
    readiness_weights = {'Peak': 100, 'Well-adapted': 85, 'FOR': 60, 'Acute Fatigue': 50, 'NFOR': 30, 'OTS': 10}
    
    # 睡眠表现对各状态的发射概率（来自constants.py）
    sleep_emission_probs = {
        'good': {'Peak': 0.80, 'Well-adapted': 0.70, 'FOR': 0.25, 'Acute Fatigue': 0.35, 'NFOR': 0.20, 'OTS': 0.15},
        'medium': {'Peak': 0.20, 'Well-adapted': 0.30, 'FOR': 0.50, 'Acute Fatigue': 0.50, 'NFOR': 0.40, 'OTS': 0.35},
        'poor': {'Peak': 0.000001, 'Well-adapted': 0.000001, 'FOR': 0.25, 'Acute Fatigue': 0.15, 'NFOR': 0.40, 'OTS': 0.50}
    }
    
    # HRV趋势对各状态的发射概率
    hrv_emission_probs = {
        'rising': {'Peak': 0.85, 'Well-adapted': 0.20, 'FOR': 0.10, 'Acute Fatigue': 0.10, 'NFOR': 0.05, 'OTS': 0.01},
        'stable': {'Peak': 0.4, 'Well-adapted': 0.3, 'FOR': 0.20, 'Acute Fatigue': 0.20, 'NFOR': 0.10, 'OTS': 0.05},
        'slight_decline': {'Peak': 0.05, 'Well-adapted': 0.10, 'FOR': 0.30, 'Acute Fatigue': 0.30, 'NFOR': 0.15, 'OTS': 0.09},
        'significant_decline': {'Peak': 0.000001, 'Well-adapted': 0.000001, 'FOR': 0.40, 'Acute Fatigue': 0.40, 'NFOR': 0.70, 'OTS': 0.80}
    }
    
    def calculate_readiness_score(sleep_perf, hrv_trend):
        """简化的准备度评分计算"""
        combined_probs = {}
        
        # 简化：假设均匀先验，只考虑睡眠和HRV证据
        for state in readiness_weights:
            sleep_prob = sleep_emission_probs[sleep_perf][state]
            hrv_prob = hrv_emission_probs[hrv_trend][state]
            combined_probs[state] = sleep_prob * hrv_prob
        
        # 归一化
        total = sum(combined_probs.values())
        if total > 0:
            for state in combined_probs:
                combined_probs[state] /= total
        
        # 计算加权评分
        score = sum(prob * readiness_weights[state] for state, prob in combined_probs.items())
        
        # 找最可能的状态
        max_state = max(combined_probs, key=combined_probs.get)
        
        return score, max_state, combined_probs
    
    demo = BaselineDemo()
    profiles = create_user_profiles()
    
    # 测试数据
    test_sleep_duration = 7.0
    test_sleep_efficiency = 0.83
    test_hrv_today = 42.0
    
    print(f"测试数据: {test_sleep_duration}小时睡眠, {test_sleep_efficiency:.2f}效率, HRV {test_hrv_today}ms\n")
    
    results = []
    
    # 无基线评估
    sleep_perf_default, _, _ = demo.calculate_sleep_performance(
        test_sleep_duration, test_sleep_efficiency, None
    )
    hrv_trend_default, _ = demo.calculate_hrv_trend(
        test_hrv_today, None, test_hrv_today, test_hrv_today * 1.02
    )
    score_default, state_default, _ = calculate_readiness_score(sleep_perf_default, hrv_trend_default)
    results.append(('无基线', sleep_perf_default, hrv_trend_default, score_default, state_default))
    
    # 各用户基线评估
    for profile_key, profile in profiles.items():
        baseline = profile['baseline']
        
        sleep_perf, _, _ = demo.calculate_sleep_performance(
            test_sleep_duration, test_sleep_efficiency, baseline
        )
        hrv_trend, _ = demo.calculate_hrv_trend(test_hrv_today, baseline)
        score, state, _ = calculate_readiness_score(sleep_perf, hrv_trend)
        
        results.append((profile['name'], sleep_perf, hrv_trend, score, state))
    
    # 显示结果对比
    print(f"{'评估方式':<18} {'睡眠表现':<12} {'HRV趋势':<18} {'准备度评分':<12} {'最可能状态'}")
    print("-" * 85)
    
    for name, sleep_perf, hrv_trend, score, state in results:
        print(f"{name:<18} {sleep_perf:<12} {hrv_trend:<18} {score:<12.1f} {state}")
    
    print(f"\n💡 关键发现:")
    print(f"   • 相同的原始数据在不同个人基线下产生了不同的sleep_performance和hrv_trend判断")
    print(f"   • 这些差异直接影响了最终的准备度评分和状态诊断") 
    print(f"   • 个性化基线让评估更加精准，避免了'一刀切'的问题")

def main():
    """主演示函数"""
    
    print("🎯 个人基线系统效果演示")
    print("展示基线如何影响睡眠和HRV的判断标准\n")
    
    # 1. 睡眠表现差异演示
    demo_sleep_performance_differences()
    
    # 2. HRV趋势差异演示  
    demo_hrv_trend_differences()
    
    # 3. 阈值调整机制演示
    demo_threshold_adjustment_mechanism()
    
    # 4. 完整准备度影响演示
    demo_complete_readiness_impact()
    
    print("\n" + "=" * 60)
    print("✅ 演示完成！")
    print("=" * 60)
    
    print(f"\n📋 总结 - 基线对睡眠和HRV判断的影响:")
    
    print(f"\n🛏️  睡眠表现判断标准:")
    print(f"   • good: 时长 ≥ max(7.0h, 个人基线-0.5h) 且 效率 ≥ max(85%, 个人基线-5%)")
    print(f"   • medium: 时长 ≥ max(6.0h, 个人基线-1.0h) 且 效率 ≥ max(75%, 个人基线-10%)")
    print(f"   • poor: 其他情况")
    
    print(f"\n❤️  HRV趋势判断标准:")
    print(f"   有基线时(Z分数方法):")
    print(f"     • rising: Z ≥ 0.5 (今天HRV比个人基线高0.5个标准差)")
    print(f"     • stable: -0.5 < Z < 0.5 (在个人正常范围内)")
    print(f"     • slight_decline: -1.5 < Z ≤ -0.5 (轻微低于个人基线)")
    print(f"     • significant_decline: Z ≤ -1.5 (显著低于个人基线)")
    print(f"   无基线时(相对变化方法):")
    print(f"     • rising: 3天均值比7天均值高≥3%")
    print(f"     • stable: 变化在±3%内")
    print(f"     • slight_decline: 下降3%-8%")
    print(f"     • significant_decline: 下降≥8%")
    
    print(f"\n🎯  恢复性睡眠判断标准:")
    print(f"   • high: ≥ max(45%, 个人基线+5%)")
    print(f"   • medium: 在个人基线±5%范围内 或 ≥30%")
    print(f"   • low: 其他情况")
    
    print(f"\n🔄  个性化带来的价值:")
    print(f"   • 避免对短睡眠高效用户的误判")
    print(f"   • 识别长睡眠需求用户的真实状态") 
    print(f"   • 基于个人HRV模式的精准变化检测")
    print(f"   • 最终准备度评分更贴合个人实际恢复状态")

if __name__ == '__main__':
    main()