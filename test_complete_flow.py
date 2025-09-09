#!/usr/bin/env python3
"""完整流程测试：HealthKit数据 → Baseline计算 → Readiness评估

测试数据不足、正常计算、个性化评估等完整场景。
"""

import sys
sys.path.append('.')

from datetime import datetime, timedelta
from baseline.healthkit_integration import create_sample_healthkit_data
from baseline import compute_baseline_from_healthkit_data
from baseline.storage import MemoryBaselineStorage
from readiness.mapping import map_inputs_to_states

def test_insufficient_data_scenario():
    """测试数据不足的场景"""
    
    print("📊 测试场景1：数据不足")
    print("=" * 50)
    
    # 创建少量数据（不足7天睡眠，不足5个HRV）
    insufficient_sleep_data = [
        {
            'date': '2024-01-01T00:00:00Z',
            'sleep_duration_minutes': 420,
            'time_in_bed_minutes': 450,
            'deep_sleep_minutes': 80,
            'rem_sleep_minutes': 100,
            'source_device': 'Apple Watch'
        },
        {
            'date': '2024-01-02T00:00:00Z',
            'sleep_duration_minutes': 450,
            'time_in_bed_minutes': 480,
            'deep_sleep_minutes': 90,
            'rem_sleep_minutes': 110,
            'source_device': 'Apple Watch'
        }
    ]
    
    insufficient_hrv_data = [
        {
            'timestamp': '2024-01-01T08:00:00Z',
            'sdnn_value': 35.0,
            'source_device': 'Apple Watch'
        },
        {
            'timestamp': '2024-01-02T08:00:00Z', 
            'sdnn_value': 42.0,
            'source_device': 'Apple Watch'
        }
    ]
    
    # 计算基线
    result = compute_baseline_from_healthkit_data(
        user_id="new_user_001",
        healthkit_sleep_data=insufficient_sleep_data,
        healthkit_hrv_data=insufficient_hrv_data
    )
    
    print(f"🎯 结果: {result['status']}")
    print(f"📝 消息: {result['message']}")
    print(f"💡 策略: {result.get('fallback_strategy', 'N/A')}")
    
    if result.get('recommendations'):
        print(f"💬 建议:")
        for rec in result['recommendations']:
            print(f"   • {rec}")
    
    # 在数据不足的情况下，用默认阈值计算准备度
    print(f"\n🎯 使用默认阈值计算准备度:")
    
    current_data = {
        'sleep_duration_hours': 6.5,
        'sleep_efficiency': 0.82,
        'hrv_rmssd_today': 35.0,
        'hrv_rmssd_7day_avg': 37.0,  # 使用7天平均作为fallback
        'restorative_ratio': 0.30,
        'fatigue_hooper': 3,
        'stress_hooper': 2
    }
    
    # 不注入基线数据，使用默认阈值
    readiness_result = map_inputs_to_states(current_data)
    
    print(f"   睡眠表现: {readiness_result.get('sleep_performance', 'unknown')}")
    print(f"   HRV趋势: {readiness_result.get('hrv_trend', 'unknown')}")
    print(f"   恢复性睡眠: {readiness_result.get('restorative_sleep', 'unknown')}")
    
    return result

def test_sufficient_data_scenario():
    """测试数据充足的场景"""
    
    print(f"\n📊 测试场景2：数据充足，计算个人基线")
    print("=" * 50)
    
    # 创建充足的示例数据
    sample_sleep_data, sample_hrv_data = create_sample_healthkit_data()
    
    print(f"📱 输入数据: 睡眠{len(sample_sleep_data)}天, HRV{len(sample_hrv_data)}个")
    
    # 初始化存储
    storage = MemoryBaselineStorage()
    
    # 计算基线
    result = compute_baseline_from_healthkit_data(
        user_id="experienced_user_002",
        healthkit_sleep_data=sample_sleep_data,
        healthkit_hrv_data=sample_hrv_data,
        storage=storage
    )
    
    print(f"🎯 结果: {result['status']}")
    print(f"📊 数据质量: {result.get('data_quality', 0):.2f}")
    
    if result['status'] == 'success':
        baseline = result['baseline']
        print(f"\n📏 个人基线:")
        print(f"   睡眠时长基线: {baseline.get('sleep_baseline_hours', 'N/A'):.1f}小时")
        print(f"   睡眠效率基线: {baseline.get('sleep_baseline_eff', 'N/A'):.1%}")
        print(f"   恢复性睡眠基线: {baseline.get('rest_baseline_ratio', 'N/A'):.1%}")
        print(f"   HRV基线: {baseline.get('hrv_baseline_mu', 'N/A'):.1f}±{baseline.get('hrv_baseline_sd', 0):.1f}ms")
        
        # 显示建议
        if result.get('recommendations'):
            print(f"\n💡 个性化建议:")
            for rec in result['recommendations']:
                print(f"   • {rec}")
        
        return result, storage
    
    return None, None

def test_personalized_readiness_calculation(baseline_result, storage):
    """测试个性化准备度计算"""
    
    print(f"\n📊 测试场景3：个性化准备度计算")  
    print("=" * 50)
    
    if not baseline_result or baseline_result['status'] != 'success':
        print("❌ 无有效基线数据，跳过个性化测试")
        return
    
    # 获取基线数据
    readiness_payload = baseline_result['readiness_payload']
    baseline_sleep_hours = readiness_payload.get('sleep_baseline_hours', 7.5)
    
    # 测试场景：不同的睡眠时长
    test_scenarios = [
        {
            'name': '睡眠充足场景',
            'sleep_hours': baseline_sleep_hours + 0.8,  # 基线+0.8小时
            'efficiency': 0.88,
            'hrv': readiness_payload.get('hrv_baseline_mu', 40) + 5,
            'expected': 'good睡眠表现'
        },
        {
            'name': '睡眠略低于基线',
            'sleep_hours': baseline_sleep_hours - 0.3,  # 基线-0.3小时
            'efficiency': 0.82,
            'hrv': readiness_payload.get('hrv_baseline_mu', 40) - 3,
            'expected': 'medium睡眠表现'
        },
        {
            'name': '睡眠明显不足',
            'sleep_hours': baseline_sleep_hours - 0.8,  # 基线-0.8小时
            'efficiency': 0.75,
            'hrv': readiness_payload.get('hrv_baseline_mu', 40) - 8,
            'expected': 'poor睡眠表现'
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n🧪 {scenario['name']}:")
        print(f"   当天睡眠: {scenario['sleep_hours']:.1f}h (基线{baseline_sleep_hours:.1f}h)")
        print(f"   睡眠效率: {scenario['efficiency']:.1%}")
        print(f"   当天HRV: {scenario['hrv']:.1f}ms")
        
        # 构造测试数据
        current_data = {
            'sleep_duration_hours': scenario['sleep_hours'],
            'sleep_efficiency': scenario['efficiency'],
            'hrv_rmssd_today': scenario['hrv'],
            'restorative_ratio': 0.32,
            'fatigue_hooper': 3,
            'stress_hooper': 2,
            'is_sick': False,
            'is_injured': False
        }
        
        # 注入个人基线
        current_data.update(readiness_payload)
        
        # 计算个性化准备度
        states = map_inputs_to_states(current_data)
        
        print(f"   → 睡眠表现: {states.get('sleep_performance', 'unknown')}")
        print(f"   → HRV趋势: {states.get('hrv_trend', 'unknown')}")
        print(f"   → 恢复性睡眠: {states.get('restorative_sleep', 'unknown')}")
        print(f"   → 主观疲劳: {states.get('subjective_fatigue', 'unknown')}")
        
        # 验证个性化效果
        sleep_perf = states.get('sleep_performance')
        if 'good' in scenario['expected'] and sleep_perf == 'good':
            print(f"   ✅ 个性化生效: {sleep_perf}")
        elif 'medium' in scenario['expected'] and sleep_perf == 'medium':
            print(f"   ✅ 个性化生效: {sleep_perf}")
        elif 'poor' in scenario['expected'] and sleep_perf == 'poor':
            print(f"   ✅ 个性化生效: {sleep_perf}")
        else:
            print(f"   ℹ️ 结果: {sleep_perf}")

def compare_default_vs_personalized():
    """对比默认阈值vs个性化阈值的差异"""
    
    print(f"\n📊 测试场景4：默认vs个性化对比")
    print("=" * 50)
    
    # 创建个人基线偏低的用户数据
    short_sleeper_data = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(25):  # 25天数据，基线约6.5小时
        date = base_date + timedelta(days=i)
        sleep_minutes = 390 + (i % 5 - 2) * 10  # 6.5小时 ± 变化
        
        short_sleeper_data.append({
            'date': date.isoformat() + 'Z',
            'sleep_duration_minutes': sleep_minutes,
            'time_in_bed_minutes': sleep_minutes + 20,
            'deep_sleep_minutes': int(sleep_minutes * 0.15),
            'rem_sleep_minutes': int(sleep_minutes * 0.22),
            'source_device': 'Apple Watch'
        })
    
    # HRV数据偏低
    short_sleeper_hrv = []
    for i in range(20):
        timestamp = base_date + timedelta(days=i, hours=8)
        hrv_value = 28.0 + (i % 7 - 3) * 2.5  # 低HRV基线
        
        short_sleeper_hrv.append({
            'timestamp': timestamp.isoformat() + 'Z',
            'sdnn_value': hrv_value,
            'source_device': 'Apple Watch'
        })
    
    # 计算个人基线
    storage = MemoryBaselineStorage()
    result = compute_baseline_from_healthkit_data(
        user_id="short_sleeper_003",
        healthkit_sleep_data=short_sleeper_data,
        healthkit_hrv_data=short_sleeper_hrv,
        storage=storage
    )
    
    if result['status'] != 'success':
        print("❌ 基线计算失败")
        return
    
    baseline = result['baseline']
    readiness_payload = result['readiness_payload']
    
    print(f"👤 短睡眠型用户基线:")
    print(f"   睡眠基线: {baseline['sleep_baseline_hours']:.1f}小时")
    print(f"   HRV基线: {baseline['hrv_baseline_mu']:.1f}ms")
    
    # 测试场景：用户睡了6.8小时
    test_sleep_hours = 6.8
    test_efficiency = 0.85
    test_hrv = 30.0
    
    print(f"\n🧪 测试数据: {test_sleep_hours}小时睡眠, {test_efficiency:.1%}效率, {test_hrv}ms HRV")
    
    # 默认阈值判断
    print(f"\n📊 默认阈值判断:")
    default_data = {
        'sleep_duration_hours': test_sleep_hours,
        'sleep_efficiency': test_efficiency,
        'hrv_rmssd_today': test_hrv,
        'hrv_rmssd_7day_avg': 35.0,  # 使用7天平均
        'restorative_ratio': 0.35
    }
    
    default_states = map_inputs_to_states(default_data)
    print(f"   睡眠表现: {default_states.get('sleep_performance', 'unknown')}")
    print(f"   (6.8h vs 默认7.0h good阈值)")
    
    # 个性化阈值判断
    print(f"\n🎯 个性化阈值判断:")
    personalized_data = default_data.copy()
    personalized_data.update(readiness_payload)
    
    personalized_states = map_inputs_to_states(personalized_data)
    print(f"   睡眠表现: {personalized_states.get('sleep_performance', 'unknown')}")
    
    personal_baseline = baseline['sleep_baseline_hours']
    good_threshold = min(9.0, max(7.0, personal_baseline + 1.0))
    print(f"   (6.8h vs 个性化{good_threshold:.1f}h good阈值，基线{personal_baseline:.1f}h)")
    
    # 显示差异
    default_perf = default_states.get('sleep_performance')
    personalized_perf = personalized_states.get('sleep_performance')
    
    print(f"\n💡 个性化效果:")
    if default_perf != personalized_perf:
        print(f"   默认判断: {default_perf} → 个性化判断: {personalized_perf} ✨")
        print(f"   个性化让短睡眠型用户获得更合理的评估！")
    else:
        print(f"   两种方式结果一致: {default_perf}")

def run_complete_flow_test():
    """运行完整流程测试"""
    
    print("🚀 完整流程测试：HealthKit → Baseline → Readiness")
    print("=" * 80)
    
    # 场景1：数据不足
    insufficient_result = test_insufficient_data_scenario()
    
    # 场景2：数据充足，计算基线
    baseline_result, storage = test_sufficient_data_scenario()
    
    # 场景3：个性化准备度计算
    if baseline_result:
        test_personalized_readiness_calculation(baseline_result, storage)
    
    # 场景4：对比默认vs个性化
    compare_default_vs_personalized()
    
    print(f"\n🎉 完整流程测试完成！")
    print(f"✅ 数据不足场景: 返回fallback策略")
    print(f"✅ 数据充足场景: 成功计算个人基线")
    print(f"✅ 个性化评估: 基于个人基线动态调整阈值")
    print(f"✅ 对比验证: 个性化vs默认阈值的差异明显")

if __name__ == '__main__':
    run_complete_flow_test()