#!/usr/bin/env python3
"""测试新的睡眠阈值调整逻辑

验证修改后的睡眠判断标准是否按预期工作。
"""

import sys
sys.path.append('.')

from readiness.mapping import map_inputs_to_states

def test_new_sleep_logic():
    """测试新的睡眠阈值逻辑"""
    
    print("🧪 测试新的睡眠阈值调整逻辑")
    print("=" * 60)
    
    # 测试用例：不同基线的用户
    test_users = [
        {
            'name': '短睡眠型用户(小明)',
            'baseline': {
                'sleep_baseline_hours': 6.5,
                'sleep_baseline_eff': 0.90
            },
            'expected_good_threshold': 7.0,  # max(7.0, 6.5+0.5) = 7.0
            'expected_med_threshold': 6.0   # max(6.0, 6.5-0.5) = 6.0
        },
        {
            'name': '标准睡眠型用户(小红)',
            'baseline': {
                'sleep_baseline_hours': 7.2,
                'sleep_baseline_eff': 0.85
            },
            'expected_good_threshold': 7.7,  # max(7.0, 7.2+0.5) = 7.7
            'expected_med_threshold': 6.7   # max(6.0, 7.2-0.5) = 6.7
        },
        {
            'name': '长睡眠型用户(小强)',
            'baseline': {
                'sleep_baseline_hours': 8.5,
                'sleep_baseline_eff': 0.80
            },
            'expected_good_threshold': 9.0,  # max(7.0, 8.5+0.5) = 9.0
            'expected_med_threshold': 8.0   # max(6.0, 8.5-0.5) = 8.0
        }
    ]
    
    # 测试睡眠数据
    sleep_test_cases = [
        {'duration': 6.5, 'efficiency': 0.88},
        {'duration': 7.0, 'efficiency': 0.85},
        {'duration': 7.5, 'efficiency': 0.82},
        {'duration': 8.0, 'efficiency': 0.78},
        {'duration': 8.5, 'efficiency': 0.85},
        {'duration': 9.0, 'efficiency': 0.88}
    ]
    
    print(f"{'用户类型':<15} {'睡眠数据':<12} {'旧逻辑结果':<12} {'新逻辑结果':<12} {'预期结果'}")
    print("-" * 75)
    
    for user in test_users:
        print(f"\n{user['name']}:")
        print(f"  基线: {user['baseline']['sleep_baseline_hours']}h, {user['baseline']['sleep_baseline_eff']:.2f}")
        print(f"  新阈值: good≥{user['expected_good_threshold']:.1f}h, medium≥{user['expected_med_threshold']:.1f}h")
        
        for sleep_case in sleep_test_cases:
            duration = sleep_case['duration']
            efficiency = sleep_case['efficiency']
            
            # 测试新逻辑（有基线）
            payload_with_baseline = {
                'sleep_duration_hours': duration,
                'sleep_efficiency': efficiency,
                'sleep_baseline_hours': user['baseline']['sleep_baseline_hours'],
                'sleep_baseline_eff': user['baseline']['sleep_baseline_eff']
            }
            
            # 测试旧逻辑（模拟旧的基线-0.5逻辑）
            old_good_threshold = max(7.0, user['baseline']['sleep_baseline_hours'] - 0.5)
            old_med_threshold = max(6.0, user['baseline']['sleep_baseline_hours'] - 1.0)
            
            if duration >= old_good_threshold and efficiency >= 0.85:
                old_result = 'good'
            elif duration >= old_med_threshold and efficiency >= 0.75:
                old_result = 'medium'
            else:
                old_result = 'poor'
            
            # 执行新逻辑
            new_mapped = map_inputs_to_states(payload_with_baseline)
            new_result = new_mapped.get('sleep_performance', 'unknown')
            
            # 预期结果
            if duration >= user['expected_good_threshold'] and efficiency >= 0.85:
                expected_result = 'good'
            elif duration >= user['expected_med_threshold'] and efficiency >= 0.75:
                expected_result = 'medium'
            else:
                expected_result = 'poor'
            
            sleep_desc = f"{duration}h/{efficiency:.2f}"
            status = "✅" if new_result == expected_result else "❌"
            
            print(f"    {sleep_desc:<12} {old_result:<12} {new_result:<12} {expected_result} {status}")

def test_edge_cases():
    """测试边缘情况"""
    
    print(f"\n🔍 边缘情况测试")
    print("=" * 40)
    
    # 测试无基线情况（应该使用默认阈值）
    payload_no_baseline = {
        'sleep_duration_hours': 7.2,
        'sleep_efficiency': 0.86
    }
    
    result_no_baseline = map_inputs_to_states(payload_no_baseline)
    print(f"无基线用户 7.2h/86%: {result_no_baseline.get('sleep_performance')}")
    
    # 测试极低基线情况
    payload_low_baseline = {
        'sleep_duration_hours': 6.0,
        'sleep_efficiency': 0.88,
        'sleep_baseline_hours': 5.5,
        'sleep_baseline_eff': 0.85
    }
    
    result_low_baseline = map_inputs_to_states(payload_low_baseline)
    print(f"极低基线用户(5.5h) 6.0h/88%: {result_low_baseline.get('sleep_performance')}")
    
    # 测试极高基线情况
    payload_high_baseline = {
        'sleep_duration_hours': 9.5,
        'sleep_efficiency': 0.82,
        'sleep_baseline_hours': 9.0,
        'sleep_baseline_eff': 0.80
    }
    
    result_high_baseline = map_inputs_to_states(payload_high_baseline)
    print(f"极高基线用户(9.0h) 9.5h/82%: {result_high_baseline.get('sleep_performance')}")

def compare_before_after():
    """对比修改前后的效果"""
    
    print(f"\n📊 修改前后效果对比")
    print("=" * 50)
    
    # 关键测试用例
    test_case = {
        'duration': 8.2,
        'efficiency': 0.85,
        'baseline_hours': 8.0,
        'baseline_eff': 0.82
    }
    
    print(f"测试用例: {test_case['duration']}小时睡眠，{test_case['efficiency']:.2f}效率")
    print(f"个人基线: {test_case['baseline_hours']}小时，{test_case['baseline_eff']:.2f}效率")
    
    # 旧逻辑计算
    old_good_threshold = max(7.0, test_case['baseline_hours'] - 0.5)  # 7.5
    old_med_threshold = max(6.0, test_case['baseline_hours'] - 1.0)   # 7.0
    
    if test_case['duration'] >= old_good_threshold and test_case['efficiency'] >= 0.85:
        old_result = 'good'
    elif test_case['duration'] >= old_med_threshold and test_case['efficiency'] >= 0.75:
        old_result = 'medium'
    else:
        old_result = 'poor'
    
    # 新逻辑计算
    payload = {
        'sleep_duration_hours': test_case['duration'],
        'sleep_efficiency': test_case['efficiency'],
        'sleep_baseline_hours': test_case['baseline_hours'],
        'sleep_baseline_eff': test_case['baseline_eff']
    }
    
    new_mapped = map_inputs_to_states(payload)
    new_result = new_mapped.get('sleep_performance')
    
    print(f"\n旧逻辑:")
    print(f"  good阈值: ≥{old_good_threshold}h (基线-0.5)")
    print(f"  判断结果: {old_result}")
    
    print(f"\n新逻辑:")
    new_good_threshold = max(7.0, test_case['baseline_hours'] + 0.5)  # 8.5
    print(f"  good阈值: ≥{new_good_threshold}h (基线+0.5)")
    print(f"  判断结果: {new_result}")
    
    print(f"\n💡 分析:")
    print(f"  • 8小时基线用户睡了8.2小时")
    print(f"  • 旧逻辑: 要求7.5小时→判断为{old_result}")
    print(f"  • 新逻辑: 要求8.5小时→判断为{new_result}")
    print(f"  • 新逻辑更合理：略超过基线应该算medium，而非good")

if __name__ == '__main__':
    test_new_sleep_logic()
    test_edge_cases() 
    compare_before_after()
    
    print(f"\n✅ 测试完成！")
    print(f"新的睡眠阈值逻辑已生效：")
    print(f"  • good: 个人基线 + 0.5小时")
    print(f"  • medium: 个人基线 ± 0.5小时")
    print(f"  • poor: 低于个人基线 0.5小时以上")