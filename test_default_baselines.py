#!/usr/bin/env python3
"""默认基线测试演示

展示数据不足和数据充足两种场景的处理结果。
"""

def demo_default_baselines():
    """演示默认基线配置"""
    
    print("🎯 默认基线配置演示")
    print("=" * 60)
    
    # 导入默认基线配置
    from baseline.default_baselines import DEFAULT_BASELINES, HRV_BASELINES, get_default_baseline
    
    print("💤 三种睡眠类型基线:")
    for sleep_type, config in DEFAULT_BASELINES.items():
        print(f"\n📊 {config['description']} ({sleep_type}):")
        print(f"   睡眠时长基线: {config['sleep_baseline_hours']}小时")
        print(f"   睡眠效率基线: {config['sleep_baseline_eff']:.1%}")
        print(f"   恢复性睡眠基线: {config['rest_baseline_ratio']:.1%}")
        
        # 计算对应的个性化阈值
        baseline_hours = config['sleep_baseline_hours']
        good_threshold = min(9.0, max(7.0, baseline_hours + 1.0))
        med_threshold = min(8.0, max(6.0, baseline_hours - 0.5))
        
        print(f"   → good阈值: ≥{good_threshold:.1f}h")
        print(f"   → medium阈值: ≥{med_threshold:.1f}h")
    
    print(f"\n💓 三种HRV类型基线:")
    for hrv_type, config in HRV_BASELINES.items():
        print(f"\n📈 {config['description']} ({hrv_type}):")
        print(f"   HRV基线: {config['hrv_baseline_mu']:.0f}±{config['hrv_baseline_sd']:.0f}ms")
        print(f"   适用人群: {config['age_range']}")

def demo_insufficient_data_scenario():
    """演示数据不足场景"""
    
    print(f"\n📊 场景1：数据不足（5天数据）")
    print("=" * 50)
    
    # 模拟5天的少量数据
    insufficient_sleep_data = [
        {'date': f'2024-01-0{i}T00:00:00Z', 'sleep_duration_minutes': 400 + i*10, 'time_in_bed_minutes': 430 + i*10}
        for i in range(1, 6)
    ]
    insufficient_hrv_data = [
        {'timestamp': f'2024-01-0{i}T08:00:00Z', 'sdnn_value': 35.0 + i}
        for i in range(1, 6)
    ]
    
    print(f"📱 输入: 睡眠{len(insufficient_sleep_data)}天, HRV{len(insufficient_hrv_data)}个")
    
    # 模拟三种用户类型的API调用结果
    user_types = [
        ("short_sleeper", "high_hrv", "年轻短睡眠型用户"),
        ("normal_sleeper", "normal_hrv", "标准用户"),
        ("long_sleeper", "low_hrv", "年长长睡眠型用户")
    ]
    
    for sleeper_type, hrv_type, desc in user_types:
        print(f"\n🎭 {desc}:")
        
        # 模拟API调用结果
        from baseline.default_baselines import get_default_baseline
        default_baseline = get_default_baseline(sleeper_type, hrv_type)
        
        result = {
            'status': 'success_with_defaults',
            'baseline_source': 'default_profile',
            'sleeper_type': sleeper_type,
            'hrv_type': hrv_type,
            'baseline': {
                'sleep_baseline_hours': default_baseline['sleep_baseline_hours'],
                'sleep_baseline_eff': default_baseline['sleep_baseline_eff'],
                'rest_baseline_ratio': default_baseline['rest_baseline_ratio'],
                'hrv_baseline_mu': default_baseline['hrv_baseline_mu'],
                'hrv_baseline_sd': default_baseline['hrv_baseline_sd']
            },
            'readiness_payload': default_baseline,
            'data_quality': 0.8,
            'recommendations': [
                f'当前使用{sleeper_type}和{hrv_type}默认基线',
                '继续记录数据，30天后可计算个性化基线',
                f'已有5天睡眠数据，还需25天'
            ]
        }
        
        print(f"   状态: {result['status']}")
        print(f"   基线来源: {result['baseline_source']}")
        baseline = result['baseline']
        print(f"   睡眠基线: {baseline['sleep_baseline_hours']}h, 效率{baseline['sleep_baseline_eff']:.1%}")
        print(f"   HRV基线: {baseline['hrv_baseline_mu']:.0f}±{baseline['hrv_baseline_sd']:.0f}ms")
        
        # 计算个性化阈值
        good_threshold = min(9.0, max(7.0, baseline['sleep_baseline_hours'] + 1.0))
        print(f"   → good睡眠阈值: ≥{good_threshold:.1f}h")

def demo_sufficient_data_scenario():
    """演示数据充足场景"""
    
    print(f"\n📊 场景2：数据充足（35天数据）")
    print("=" * 50)
    
    print(f"📱 输入: 睡眠35天, HRV50个（模拟数据）")
    
    # 模拟个人基线计算结果
    personal_baseline_result = {
        'status': 'success',
        'baseline_source': 'personal_calculation',
        'user_id': 'user_with_data',
        'baseline': {
            'sleep_baseline_hours': 7.2,    # 实际个人数据计算出的基线
            'sleep_baseline_eff': 0.87,
            'rest_baseline_ratio': 0.31,
            'hrv_baseline_mu': 36.8,
            'hrv_baseline_sd': 7.5,
            'data_quality_score': 0.89
        },
        'data_quality': 0.89,
        'data_summary': {
            'sleep_records_parsed': 35,
            'hrv_records_parsed': 50,
            'baseline_strategy': 'personal_calculation'
        },
        'message': '个人基线计算成功，质量评分: 0.89'
    }
    
    print(f"🎯 结果: {personal_baseline_result['status']}")
    print(f"📊 数据质量: {personal_baseline_result['data_quality']}")
    
    baseline = personal_baseline_result['baseline']
    print(f"\n📏 个人基线:")
    print(f"   睡眠时长基线: {baseline['sleep_baseline_hours']:.1f}小时")
    print(f"   睡眠效率基线: {baseline['sleep_baseline_eff']:.1%}")
    print(f"   HRV基线: {baseline['hrv_baseline_mu']:.1f}±{baseline['hrv_baseline_sd']:.1f}ms")
    
    # 计算个性化阈值
    good_threshold = min(9.0, max(7.0, baseline['sleep_baseline_hours'] + 1.0))
    med_threshold = min(8.0, max(6.0, baseline['sleep_baseline_hours'] - 0.5))
    print(f"   → good阈值: ≥{good_threshold:.1f}h")
    print(f"   → medium阈值: ≥{med_threshold:.1f}h")

def demo_readiness_with_different_baselines():
    """演示不同基线类型的准备度计算效果"""
    
    print(f"\n📊 场景3：准备度计算效果对比")
    print("=" * 50)
    
    # 统一测试数据：用户睡了7.0小时
    current_sleep_hours = 7.0
    current_efficiency = 0.83
    current_hrv = 38.0
    
    print(f"🧪 统一测试数据: {current_sleep_hours}小时睡眠，{current_efficiency:.1%}效率，{current_hrv}ms HRV")
    print("-" * 70)
    
    # 不同基线类型的判断结果
    from baseline.default_baselines import get_default_baseline
    
    test_cases = [
        ("short_sleeper", "high_hrv", "短睡眠高HRV型"),
        ("normal_sleeper", "normal_hrv", "标准型"),
        ("long_sleeper", "low_hrv", "长睡眠低HRV型")
    ]
    
    for sleeper_type, hrv_type, desc in test_cases:
        baseline = get_default_baseline(sleeper_type, hrv_type)
        
        # 计算睡眠表现
        good_threshold = min(9.0, max(7.0, baseline['sleep_baseline_hours'] + 1.0))
        med_threshold = min(8.0, max(6.0, baseline['sleep_baseline_hours'] - 0.5))
        
        if current_sleep_hours >= good_threshold and current_efficiency >= 0.85:
            sleep_perf = 'good'
        elif current_sleep_hours >= med_threshold and current_efficiency >= 0.75:
            sleep_perf = 'medium'
        else:
            sleep_perf = 'poor'
        
        # HRV趋势计算
        hrv_z = (current_hrv - baseline['hrv_baseline_mu']) / baseline['hrv_baseline_sd']
        
        if hrv_z >= 0.5:
            hrv_trend = 'rising'
        elif hrv_z <= -0.5:
            hrv_trend = 'declining'
        else:
            hrv_trend = 'stable'
        
        print(f"👤 {desc}:")
        print(f"   基线: {baseline['sleep_baseline_hours']}h睡眠，{baseline['hrv_baseline_mu']:.0f}ms HRV")
        print(f"   good阈值: ≥{good_threshold:.1f}h")
        print(f"   判断: 睡眠={sleep_perf}, HRV={hrv_trend} (Z={hrv_z:.1f})")
        print(f"   效果: {current_sleep_hours}h对{desc}来说是{sleep_perf}")
        print()

def run_demo():
    """运行完整演示"""
    
    print("🚀 默认基线系统演示")
    print("=" * 80)
    
    # 展示配置
    demo_default_baselines()
    
    # 数据不足场景
    demo_insufficient_data_scenario()
    
    # 数据充足场景
    demo_sufficient_data_scenario()
    
    # 准备度计算对比
    demo_readiness_with_different_baselines()
    
    print(f"\n🎉 演示完成！关键特点：")
    print(f"✅ 三种睡眠类型 × 三种HRV类型 = 灵活组合")
    print(f"✅ <30天数据：自动使用默认基线，立即可用")
    print(f"✅ ≥30天数据：计算个性化基线，精准评估")
    print(f"✅ 不同类型用户获得差异化的合理评估")
    
    print(f"\n🔧 集成方式：")
    print(f"📱 前端：问卷确定sleeper_type和hrv_type")
    print(f"🔙 后端：调用API时传入用户分类参数")
    print(f"🎯 效果：新用户立即获得个性化体验")

if __name__ == '__main__':
    run_demo()