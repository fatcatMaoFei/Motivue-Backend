#!/usr/bin/env python3
"""测试恢复性睡眠阈值调整逻辑

验证基于科学文献的恢复性睡眠新判断标准。
"""

def test_restorative_sleep_logic():
    """测试恢复性睡眠阈值逻辑"""
    
    print("🧪 恢复性睡眠阈值优化测试")
    print("基于科学文献：深睡10-20% + REM 20-25% = 恢复性睡眠30-45%")
    print("=" * 65)
    
    # 模拟新的恢复性睡眠阈值计算
    def calculate_restorative_thresholds(baseline_ratio):
        if baseline_ratio is None:
            return 0.35, 0.25  # 无基线时的固定阈值
        
        high_threshold = min(0.55, max(0.35, baseline_ratio + 0.10))  # 基线+10%，35-55%范围
        med_threshold = max(0.25, baseline_ratio - 0.05)              # 基线-5%，最低25%
        return high_threshold, med_threshold
    
    # 测试用例
    test_cases = [
        {'baseline': None, 'desc': '无基线用户'},
        {'baseline': 0.20, 'desc': '恢复性睡眠偏低用户'},
        {'baseline': 0.25, 'desc': '恢复性睡眠较低用户'},
        {'baseline': 0.30, 'desc': '恢复性睡眠标准用户'},
        {'baseline': 0.35, 'desc': '恢复性睡眠良好用户'},
        {'baseline': 0.40, 'desc': '恢复性睡眠优秀用户'},
        {'baseline': 0.45, 'desc': '恢复性睡眠很好用户'},
        {'baseline': 0.50, 'desc': '恢复性睡眠极好用户'},
        {'baseline': 0.60, 'desc': '恢复性睡眠异常高用户'},
    ]
    
    print(f"{'用户类型':<18} {'基线':<8} {'high阈值':<10} {'medium阈值':<12} {'保护机制'}")
    print("-" * 65)
    
    for case in test_cases:
        baseline = case['baseline']
        desc = case['desc']
        
        high_threshold, med_threshold = calculate_restorative_thresholds(baseline)
        
        # 分析保护机制
        protection = []
        if baseline is None:
            protection.append("默认标准")
        else:
            if high_threshold == 0.35 and baseline < 0.25:
                protection.append("下限保护")
            if high_threshold == 0.55 and baseline >= 0.45:
                protection.append("上限保护")
            if not protection:
                protection.append("个性化")
        
        baseline_str = f"{baseline*100:.0f}%" if baseline else "无"
        protection_str = ", ".join(protection)
        
        print(f"{desc:<18} {baseline_str:<8} {high_threshold*100:<10.0f}% {med_threshold*100:<12.0f}% {protection_str}")
    
    print(f"\n📊 恢复性睡眠判断范围分析:")
    
    # 分析几个典型用户的判断范围
    typical_users = [
        {'name': '低恢复性用户', 'baseline': 0.25},
        {'name': '标准用户', 'baseline': 0.35}, 
        {'name': '高恢复性用户', 'baseline': 0.45},
    ]
    
    for user in typical_users:
        baseline = user['baseline']
        high_threshold, med_threshold = calculate_restorative_thresholds(baseline)
        
        print(f"\n{user['name']} (基线{baseline*100:.0f}%):")
        print(f"  • high: ≥{high_threshold*100:.0f}% (基线+{(high_threshold-baseline)*100:.0f}%)")
        print(f"  • medium: {med_threshold*100:.0f}%-{high_threshold*100:.0f}% (基线-{(baseline-med_threshold)*100:.0f}%到基线+{(high_threshold-baseline)*100:.0f}%)")
        print(f"  • low: <{med_threshold*100:.0f}% (基线-{(baseline-med_threshold)*100:.0f}%以下)")

def test_comparison_old_vs_new():
    """对比旧逻辑vs新逻辑"""
    
    print(f"\n📈 新旧逻辑对比分析")
    print("=" * 40)
    
    # 模拟旧逻辑
    def old_restorative_logic(baseline_ratio, actual_ratio):
        if baseline_ratio is None:
            if actual_ratio >= 0.45:
                return 'high'
            elif actual_ratio >= 0.30:
                return 'medium'
            else:
                return 'low'
        else:
            high_thr = max(0.45, baseline_ratio + 0.05)
            if actual_ratio >= high_thr:
                return 'high'
            elif abs(actual_ratio - baseline_ratio) <= 0.05 or actual_ratio >= 0.30:
                return 'medium'
            else:
                return 'low'
    
    # 模拟新逻辑
    def new_restorative_logic(baseline_ratio, actual_ratio):
        if baseline_ratio is None:
            high_thr, med_thr = 0.35, 0.25
        else:
            high_thr = min(0.55, max(0.35, baseline_ratio + 0.10))
            med_thr = max(0.25, baseline_ratio - 0.05)
        
        if actual_ratio >= high_thr:
            return 'high'
        elif actual_ratio >= med_thr:
            return 'medium'
        else:
            return 'low'
    
    # 测试案例
    test_scenarios = [
        {'baseline': None, 'actual': 0.35, 'desc': '无基线用户35%恢复性睡眠'},
        {'baseline': 0.30, 'actual': 0.35, 'desc': '基线30%用户实际35%'},
        {'baseline': 0.40, 'actual': 0.45, 'desc': '基线40%用户实际45%'},
        {'baseline': 0.45, 'actual': 0.48, 'desc': '高基线用户略微超过'},
        {'baseline': 0.35, 'actual': 0.32, 'desc': '标准用户略低于基线'},
    ]
    
    print(f"{'测试场景':<25} {'基线':<8} {'实际':<8} {'旧逻辑':<8} {'新逻辑':<8} {'变化'}")
    print("-" * 70)
    
    for scenario in test_scenarios:
        baseline = scenario['baseline']
        actual = scenario['actual']
        desc = scenario['desc']
        
        old_result = old_restorative_logic(baseline, actual)
        new_result = new_restorative_logic(baseline, actual)
        
        change = "→" if old_result == new_result else f"→{new_result}✨"
        baseline_str = f"{baseline*100:.0f}%" if baseline else "无"
        
        print(f"{desc:<25} {baseline_str:<8} {actual*100:<8.0f}% {old_result:<8} {new_result:<8} {change}")

def analyze_scientific_improvements():
    """分析科学改进"""
    
    print(f"\n🔬 科学改进分析")
    print("=" * 30)
    
    print("📚 基于2024年睡眠科学研究:")
    print("  • 深睡眠：占总睡眠10-20% (优质13-23%)")
    print("  • REM睡眠：占总睡眠20-25%") 
    print("  • 恢复性睡眠总和：30-45% (深睡+REM)")
    print("  • 个体差异：约10-15%变异")
    print("  • 年龄影响：深睡眠每十年减少约2%")
    
    print(f"\n🎯 我们的新标准改进:")
    
    print("  ✅ 调整幅度更科学:")
    print("     - 旧：基线+5%算high → 新：基线+10%算high")
    print("     - 符合个体差异10-15%的科学发现")
    
    print("  ✅ 安全范围保护:")
    print("     - 35-55%安全边界，覆盖正常生理范围")
    print("     - 防止极端基线用户的异常标准")
    
    print("  ✅ 更合理的默认标准:")
    print("     - 旧：45%才算high → 新：35%算high") 
    print("     - 基于科学文献30-45%正常范围")
    
    print("  ✅ Medium标准优化:")
    print("     - 更清晰的分层：基线-5%作为medium下限")
    print("     - 避免旧逻辑中复杂的±5%判断")

if __name__ == '__main__':
    test_restorative_sleep_logic()
    test_comparison_old_vs_new()
    analyze_scientific_improvements()
    
    print(f"\n🏆 恢复性睡眠阈值优化完成！")
    print("新标准更符合睡眠科学和个体生理差异")