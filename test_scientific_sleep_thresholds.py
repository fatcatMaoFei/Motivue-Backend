#!/usr/bin/env python3
"""测试科学化的睡眠阈值调整逻辑

验证基线±1小时和7-9小时安全范围的新逻辑。
"""

def test_scientific_sleep_logic():
    """测试科学化的睡眠阈值逻辑"""
    
    print("🔬 科学化睡眠阈值逻辑测试")
    print("基于最新研究：1小时睡眠债务需4天恢复，个体差异约2小时")
    print("=" * 70)
    
    # 模拟新的阈值计算逻辑
    def calculate_new_thresholds(baseline_hours):
        if baseline_hours is None:
            return 7.0, 6.0  # 默认阈值
        
        good_threshold = min(9.0, max(7.0, baseline_hours + 1.0))
        med_threshold = max(6.0, baseline_hours - 0.5)
        return good_threshold, med_threshold
    
    # 测试用例
    test_cases = [
        {'baseline': None, 'desc': '无基线用户'},
        {'baseline': 5.5, 'desc': '极短睡眠用户'},
        {'baseline': 6.0, 'desc': '短睡眠用户'},
        {'baseline': 6.5, 'desc': '偏短睡眠用户'},
        {'baseline': 7.0, 'desc': '标准睡眠用户'},
        {'baseline': 7.5, 'desc': '偏长睡眠用户'},
        {'baseline': 8.0, 'desc': '长睡眠用户'},
        {'baseline': 8.5, 'desc': '很长睡眠用户'},
        {'baseline': 9.0, 'desc': '极长睡眠用户'},
        {'baseline': 10.0, 'desc': '异常长睡眠用户'},
    ]
    
    print(f"{'用户类型':<15} {'基线':<8} {'good阈值':<10} {'medium阈值':<12} {'保护机制'}")
    print("-" * 70)
    
    for case in test_cases:
        baseline = case['baseline']
        desc = case['desc']
        
        good_threshold, med_threshold = calculate_new_thresholds(baseline)
        
        # 分析保护机制
        protection = []
        if baseline is None:
            protection.append("默认标准")
        else:
            if good_threshold == 7.0 and baseline < 6.0:
                protection.append("下限保护")
            if good_threshold == 9.0 and baseline >= 8.0:
                protection.append("上限保护")
            if not protection:
                protection.append("个性化")
        
        baseline_str = f"{baseline:.1f}h" if baseline else "无"
        protection_str = ", ".join(protection)
        
        print(f"{desc:<15} {baseline_str:<8} {good_threshold:<10.1f} {med_threshold:<12.1f} {protection_str}")
    
    print(f"\n📊 睡眠判断范围分析:")
    
    # 分析几个典型用户的睡眠判断范围
    typical_users = [
        {'name': '短睡眠用户', 'baseline': 6.5},
        {'name': '标准用户', 'baseline': 7.5}, 
        {'name': '长睡眠用户', 'baseline': 8.5},
    ]
    
    for user in typical_users:
        baseline = user['baseline']
        good_threshold, med_threshold = calculate_new_thresholds(baseline)
        
        print(f"\n{user['name']} (基线{baseline}h):")
        print(f"  • good: ≥{good_threshold:.1f}h (基线+{good_threshold-baseline:.1f}h)")
        print(f"  • medium: {med_threshold:.1f}h-{good_threshold:.1f}h (基线±0.5-1h)")
        print(f"  • poor: <{med_threshold:.1f}h (基线-{baseline-med_threshold:.1f}h)")

def test_real_world_scenarios():
    """测试真实场景下的评估效果"""
    
    print(f"\n🌍 真实场景测试")
    print("=" * 40)
    
    # 真实测试数据
    scenarios = [
        {
            'desc': '短睡眠高效用户睡了7小时',
            'baseline': 6.5,
            'actual_sleep': 7.0,
            'expected': 'good',
            'reasoning': '超过基线0.5小时，但未达到+1小时标准'
        },
        {
            'desc': '标准用户睡了8.2小时', 
            'baseline': 7.5,
            'actual_sleep': 8.2,
            'expected': 'medium',
            'reasoning': '略低于基线+1小时(8.5h)的good标准'
        },
        {
            'desc': '长睡眠用户睡了9.2小时',
            'baseline': 8.5, 
            'actual_sleep': 9.2,
            'expected': 'medium',
            'reasoning': '略低于上限保护的9小时good标准'
        },
        {
            'desc': '标准用户严重睡眠不足',
            'baseline': 7.5,
            'actual_sleep': 6.8,
            'expected': 'poor',
            'reasoning': '低于基线-0.5小时(7.0h)的medium阈值'
        }
    ]
    
    def evaluate_sleep(baseline, actual_sleep, efficiency=0.85):
        good_threshold, med_threshold = calculate_new_thresholds(baseline) if baseline else (7.0, 6.0)
        
        if actual_sleep >= good_threshold and efficiency >= 0.85:
            return 'good'
        elif actual_sleep >= med_threshold and efficiency >= 0.75:
            return 'medium'  
        else:
            return 'poor'
    
    print(f"{'场景':<25} {'基线':<8} {'实际':<8} {'预期':<8} {'结果':<8} {'状态'}")
    print("-" * 75)
    
    for scenario in scenarios:
        baseline = scenario['baseline']
        actual = scenario['actual_sleep']
        expected = scenario['expected']
        
        result = evaluate_sleep(baseline, actual)
        status = "✅" if result == expected else "❌"
        
        print(f"{scenario['desc']:<25} {baseline:<8.1f} {actual:<8.1f} {expected:<8} {result:<8} {status}")
        if result != expected:
            print(f"  ⚠️  期望{expected}，实际{result}")
        print(f"  💭 {scenario['reasoning']}")
        print()

def analyze_scientific_backing():
    """分析科学依据支撑"""
    
    print(f"\n🧬 科学依据分析")
    print("=" * 30)
    
    print("📚 基于2024年最新睡眠研究:")
    print("  • 个体最优睡眠时长差异约2小时 (Nature Scientific Reports)")
    print("  • 仅1小时睡眠债务需要4天完全恢复")
    print("  • 睡眠一致性比时长对健康更重要")
    print("  • 慢性睡眠限制效应会累积")
    
    print(f"\n🎯 我们的±1小时标准的科学合理性:")
    print("  ✅ 基线+1小时算good:")
    print("     - 确保充足恢复时间，避免睡眠债务")
    print("     - 符合2小时个体差异范围")
    print("     - 预防慢性睡眠限制累积")
    
    print("  ✅ 基线-1小时影响严重:")
    print("     - 1小时不足已有显著生理影响") 
    print("     - 影响糖代谢、皮质醇、认知表现")
    print("     - medium阈值设在-0.5小时作为缓冲")
    
    print("  ✅ 7-9小时安全边界:")
    print("     - 保护极端基线用户")
    print("     - 符合国际睡眠健康指南")
    print("     - 平衡个性化与安全性")

if __name__ == '__main__':
    test_scientific_sleep_logic()
    test_real_world_scenarios()
    analyze_scientific_backing()
    
    print(f"\n🏆 科学化睡眠阈值优化完成！")
    print("新标准更符合个体生理需求和最新科学研究")