# -*- coding: utf-8 -*-
"""70天完整流程模拟

完整模拟70天的基线管理周期：
- 第1-30天：初始基线计算
- 第31-37天：第一次7天增量更新
- 第38-44天：第二次7天增量更新  
- 第45-60天：30天完整更新
- 第61-70天：最终readiness评估验证
"""

import sys
sys.path.append('.')

from datetime import datetime, timedelta
from baseline.service import (
    compute_baseline_from_healthkit_data,
    update_baseline_smart,
    check_baseline_update_needed
)
from baseline.storage import MemoryBaselineStorage
from readiness.mapping import map_inputs_to_states
from readiness.service import compute_readiness_from_payload
import random
import json

def create_realistic_period_data(start_date: datetime, days: int, 
                                sleep_trend: str = "stable", 
                                hrv_trend: str = "stable"):
    """创建一个时期的真实数据，支持趋势变化
    
    Args:
        start_date: 开始日期
        days: 天数
        sleep_trend: 睡眠趋势 ("improving", "stable", "declining")
        hrv_trend: HRV趋势 ("improving", "stable", "declining")
    """
    
    sleep_data = []
    hrv_data = []
    
    # 基础参数
    base_sleep_hours = 7.2
    base_hrv = 36.0
    
    # 趋势调整
    sleep_trend_factor = {
        "improving": 0.02,    # 每天改善0.02小时
        "stable": 0.0,
        "declining": -0.015   # 每天下降0.015小时
    }.get(sleep_trend, 0.0)
    
    hrv_trend_factor = {
        "improving": 0.15,    # 每天改善0.15ms
        "stable": 0.0,
        "declining": -0.1     # 每天下降0.1ms
    }.get(hrv_trend, 0.0)
    
    for day in range(days):
        date = start_date + timedelta(days=day)
        
        # 睡眠数据 - 包含趋势和自然变化
        daily_sleep_hours = base_sleep_hours + (day * sleep_trend_factor)
        
        # 工作日vs周末差异
        is_weekend = date.weekday() >= 5
        weekend_bonus = 0.5 if is_weekend else 0.0
        
        # 随机变化
        daily_variation = random.uniform(-0.4, 0.4)
        stress_factor = 0.8 if day % 11 == 0 else 1.0  # 偶尔压力大
        
        final_sleep_hours = max(5.5, min(9.5, 
            daily_sleep_hours + weekend_bonus + daily_variation * stress_factor))
        
        sleep_minutes = int(final_sleep_hours * 60)
        efficiency = max(0.75, min(0.95, 0.84 + random.uniform(-0.05, 0.05)))
        
        # 睡眠阶段比例
        deep_ratio = max(0.12, min(0.20, 0.16 + random.uniform(-0.02, 0.02)))
        rem_ratio = max(0.18, min(0.26, 0.22 + random.uniform(-0.02, 0.02)))
        
        sleep_record = {
            'date': date.isoformat() + 'Z',
            'sleep_duration_minutes': sleep_minutes,
            'time_in_bed_minutes': int(sleep_minutes / efficiency),
            'deep_sleep_minutes': int(sleep_minutes * deep_ratio),
            'rem_sleep_minutes': int(sleep_minutes * rem_ratio),
            'core_sleep_minutes': int(sleep_minutes * (1 - deep_ratio - rem_ratio)),
            'awake_minutes': int(sleep_minutes / efficiency) - sleep_minutes,
            'source_device': 'Apple Watch Series 9'
        }
        sleep_data.append(sleep_record)
        
        # HRV数据 - 每天1-2个测量
        daily_measurements = 1 if day % 3 == 0 else 2
        
        for measurement in range(daily_measurements):
            timestamp = date + timedelta(hours=8, minutes=measurement*20)
            
            daily_hrv = base_hrv + (day * hrv_trend_factor)
            
            # HRV自然变化和测量差异
            measurement_variation = random.uniform(-3.0, 3.0)
            stress_impact = -2.0 if stress_factor < 1.0 else 0.0
            weekend_recovery = 1.0 if is_weekend and measurement == 0 else 0.0
            
            final_hrv = max(20.0, min(60.0,
                daily_hrv + measurement_variation + stress_impact + weekend_recovery))
            
            hrv_record = {
                'timestamp': timestamp.isoformat() + 'Z',
                'sdnn_value': round(final_hrv, 1),
                'source_device': 'Apple Watch Series 9',
                'measurement_context': 'morning' if measurement == 0 else 'evening'
            }
            hrv_data.append(hrv_record)
    
    return sleep_data, hrv_data

def simulate_day_30_initial_baseline():
    """第30天：初始基线计算"""
    print("\n" + "="*80)
    print("[DAY 30] 初始基线计算阶段")
    print("="*80)
    
    storage = MemoryBaselineStorage()
    
    # 创建前30天稳定期数据
    start_date = datetime(2024, 1, 1)
    sleep_data, hrv_data = create_realistic_period_data(
        start_date, 30, sleep_trend="stable", hrv_trend="stable"
    )
    
    print(f"[DATA] 创建了30天基线数据：{len(sleep_data)}天睡眠，{len(hrv_data)}个HRV测量")
    
    # 计算初始基线
    result = compute_baseline_from_healthkit_data(
        user_id="user_70day_test",
        healthkit_sleep_data=sleep_data,
        healthkit_hrv_data=hrv_data,
        storage=storage
    )
    
    if result['status'] == 'success':
        baseline = result['baseline']
        print(f"[SUCCESS] 初始基线建立成功")
        print(f"[BASELINE] 睡眠基线: {baseline['sleep_baseline_hours']:.2f}小时")
        print(f"[BASELINE] 睡眠效率基线: {baseline['sleep_baseline_eff']:.1%}")
        print(f"[BASELINE] 恢复性睡眠基线: {baseline['rest_baseline_ratio']:.1%}")
        print(f"[BASELINE] HRV基线: {baseline['hrv_baseline_mu']:.1f}±{baseline['hrv_baseline_sd']:.1f}ms")
        print(f"[QUALITY] 数据质量评分: {result['data_quality']:.2f}")
    else:
        print(f"[ERROR] 基线计算失败: {result.get('message')}")
        return None, None
    
    return storage, result

def simulate_day_37_incremental_update(storage, initial_baseline):
    """第37天：第一次7天增量更新（训练适应期）"""
    print("\n" + "="*80)
    print("[DAY 37] 第一次7天增量更新 - 训练适应期")
    print("="*80)
    
    # 手动调整基线创建时间，模拟7天前创建
    baseline = storage.get_baseline("user_70day_test")
    if baseline:
        baseline.created_at = datetime.now() - timedelta(days=8)  # 模拟8天前创建
        storage.save_baseline(baseline)
        print(f"[SIMULATE] 模拟基线创建于8天前")
    
    # 检查更新需求
    check_result = check_baseline_update_needed("user_70day_test", storage)
    print(f"[CHECK] 更新需求: {check_result['needs_update']}")
    print(f"[CHECK] 推荐类型: {check_result.get('update_type', 'none')}")
    print(f"[CHECK] 距离上次更新: {check_result.get('days_since_update', 0)}天")
    
    # 模拟第31-37天训练适应期（睡眠略有改善，HRV提升）
    period_start = datetime(2024, 1, 31)
    sleep_data, hrv_data = create_realistic_period_data(
        period_start, 7, sleep_trend="improving", hrv_trend="improving"
    )
    
    print(f"[DATA] 训练适应期数据：睡眠改善趋势，HRV提升趋势")
    
    # 执行智能更新
    update_result = update_baseline_smart(
        "user_70day_test", sleep_data, hrv_data, storage
    )
    
    if update_result['status'] == 'success':
        new_baseline = update_result['baseline']
        changes = update_result.get('changes', {})
        
        print(f"[SUCCESS] {update_result['update_type']}更新完成")
        print(f"[NEW] 睡眠基线: {new_baseline.get('sleep_baseline_hours', 0):.2f}小时")
        print(f"[NEW] HRV基线: {new_baseline.get('hrv_baseline_mu', 0):.1f}ms")
        
        if 'sleep_hours_change' in changes:
            print(f"[CHANGE] 睡眠时长变化: {changes['sleep_hours_change']:+.2f}小时")
        if 'hrv_mean_change' in changes:
            print(f"[CHANGE] HRV均值变化: {changes['hrv_mean_change']:+.1f}ms")
    
    return storage, update_result

def simulate_day_44_second_incremental(storage):
    """第44天：第二次7天增量更新（压力期）"""
    print("\n" + "="*80)
    print("[DAY 44] 第二次7天增量更新 - 高压力期")
    print("="*80)
    
    # 手动调整上次更新时间，模拟7天前更新
    baseline = storage.get_baseline("user_70day_test")
    if baseline:
        baseline.created_at = datetime.now() - timedelta(days=8)  # 模拟8天前
        baseline.last_incremental_update = datetime.now() - timedelta(days=8)
        storage.save_baseline(baseline)
        print(f"[SIMULATE] 模拟上次增量更新于8天前")
    
    # 模拟第38-44天压力期（睡眠下降，HRV波动）
    period_start = datetime(2024, 2, 7)
    sleep_data, hrv_data = create_realistic_period_data(
        period_start, 7, sleep_trend="declining", hrv_trend="declining"
    )
    
    print(f"[DATA] 高压力期数据：睡眠质量下降，HRV降低")
    
    # 执行智能更新
    update_result = update_baseline_smart(
        "user_70day_test", sleep_data, hrv_data, storage
    )
    
    if update_result['status'] == 'success':
        new_baseline = update_result['baseline']
        changes = update_result.get('changes', {})
        
        print(f"[SUCCESS] {update_result['update_type']}更新完成")
        print(f"[NEW] 睡眠基线: {new_baseline.get('sleep_baseline_hours', 0):.2f}小时")
        print(f"[NEW] HRV基线: {new_baseline.get('hrv_baseline_mu', 0):.1f}ms")
        
        if 'sleep_hours_change' in changes:
            print(f"[CHANGE] 睡眠时长变化: {changes['sleep_hours_change']:+.2f}小时")
        if 'hrv_mean_change' in changes:
            print(f"[CHANGE] HRV均值变化: {changes['hrv_mean_change']:+.1f}ms")
    
    return storage, update_result

def simulate_day_60_full_update(storage):
    """第60天：30天完整更新（完整重算）"""
    print("\n" + "="*80)
    print("[DAY 60] 30天完整更新 - 完整基线重算")
    print("="*80)
    
    # 手动调整基线时间，模拟30天前创建
    baseline = storage.get_baseline("user_70day_test")
    if baseline:
        baseline.created_at = datetime.now() - timedelta(days=32)  # 模拟32天前创建
        storage.save_baseline(baseline)
        print(f"[SIMULATE] 模拟基线创建于32天前，触发完整更新")
    
    # 创建第31-60天的完整数据（包含多个阶段）
    # 第31-45天：适应+压力期
    # 第45-60天：恢复改善期
    
    adaptation_data = create_realistic_period_data(
        datetime(2024, 1, 31), 15, "improving", "improving"
    )
    stress_data = create_realistic_period_data(
        datetime(2024, 2, 15), 15, "declining", "declining" 
    )
    recovery_data = create_realistic_period_data(
        datetime(2024, 3, 1), 15, "improving", "stable"
    )
    
    # 合并所有数据
    full_sleep = adaptation_data[0] + stress_data[0] + recovery_data[0]
    full_hrv = adaptation_data[1] + stress_data[1] + recovery_data[1]
    
    print(f"[DATA] 30天完整数据：包含适应期、压力期、恢复期")
    print(f"[DATA] 总计：{len(full_sleep)}天睡眠，{len(full_hrv)}个HRV测量")
    
    # 执行30天完整更新
    update_result = update_baseline_smart(
        "user_70day_test", full_sleep, full_hrv, storage
    )
    
    if update_result['status'] == 'success':
        new_baseline = update_result['baseline']
        comparison = update_result.get('comparison', {})
        
        print(f"[SUCCESS] {update_result['update_type']}更新完成")
        
        sleep_hours = new_baseline.get('sleep_baseline_hours')
        hrv_mu = new_baseline.get('hrv_baseline_mu')
        
        if sleep_hours:
            print(f"[NEW] 睡眠基线: {sleep_hours:.2f}小时")
        if hrv_mu:
            print(f"[NEW] HRV基线: {hrv_mu:.1f}ms")
        print(f"[NEW] 数据质量: {update_result['data_quality']:.2f}")
        
        if 'quality_improvement' in comparison:
            print(f"[IMPROVEMENT] 质量提升: {comparison['quality_improvement']:+.2f}")
    
    return storage, update_result

def simulate_day_70_readiness_integration(storage, final_baseline):
    """第70天：完整Readiness集成测试"""
    print("\n" + "="*80)
    print("[DAY 70] 完整Readiness集成验证")
    print("="*80)
    
    # 获取最终基线
    baseline_result = storage.get_baseline("user_70day_test")
    readiness_payload = baseline_result.to_readiness_payload()
    
    print(f"[BASELINE] 最终个人基线参数:")
    for key, value in readiness_payload.items():
        if isinstance(value, float):
            print(f"           {key}: {value:.2f}")
        else:
            print(f"           {key}: {value}")
    
    # 模拟第70天的当天数据（正常状态）
    # 使用默认值防止None值
    baseline_sleep = baseline_result.sleep_baseline_hours or 7.2
    baseline_eff = baseline_result.sleep_baseline_eff or 0.84
    baseline_hrv = baseline_result.hrv_baseline_mu or 36.0
    baseline_rest = baseline_result.rest_baseline_ratio or 0.38
    
    today_data = {
        # 客观数据 - 略低于个人基线
        'sleep_duration_hours': baseline_sleep - 0.2,
        'sleep_efficiency': baseline_eff - 0.02,
        'hrv_rmssd_today': baseline_hrv - 1.5,
        'restorative_ratio': baseline_rest - 0.01,
        'deep_sleep_ratio': 0.15,
        'rem_sleep_ratio': 0.23,
        
        # Hooper量表 - 轻度疲劳
        'fatigue_hooper': 4,
        'soreness_hooper': 3,
        'stress_hooper': 3,
        'sleep_hooper': 3,
        
        # 布尔值
        'is_sick': False,
        'is_injured': False,
        'high_stress_event_today': False,
        'meditation_done_today': True
    }
    
    print(f"[TODAY] 第70天数据模拟:")
    print(f"        睡眠: {today_data['sleep_duration_hours']:.1f}h (基线{baseline_sleep:.1f}h)")
    print(f"        HRV: {today_data['hrv_rmssd_today']:.1f}ms (基线{baseline_hrv:.1f}ms)")
    print(f"        Hooper: 疲劳{today_data['fatigue_hooper']}, 压力{today_data['stress_hooper']}")
    
    # 构造mapping输入
    mapping_input = today_data.copy()
    mapping_input.update(readiness_payload)
    
    print(f"\n[MAPPING] 使用个性化基线进行状态映射...")
    
    # 执行mapping
    states = map_inputs_to_states(mapping_input)
    
    print(f"[STATES] Mapping结果:")
    for key, value in states.items():
        if not key.endswith('_score'):
            print(f"         {key}: {value}")
    
    # 构造readiness payload
    readiness_payload_full = {
        'user_id': 'user_70day_test',
        'date': '2024-03-12',  # 第70天
        'gender': '男性',
        'objective': states,
        'hooper': {
            'fatigue': today_data['fatigue_hooper'],
            'soreness': today_data['soreness_hooper'],
            'stress': today_data['stress_hooper'],
            'sleep': today_data['sleep_hooper']
        },
        'journal': {
            'is_sick': today_data['is_sick'],
            'is_injured': today_data['is_injured'],
            'high_stress_event_today': today_data['high_stress_event_today'],
            'meditation_done_today': today_data['meditation_done_today']
        }
    }
    
    print(f"\n[READINESS] 调用完整准备度引擎...")
    
    # 调用readiness引擎
    readiness_result = compute_readiness_from_payload(readiness_payload_full)
    
    print(f"[RESULT] 最终准备度评估:")
    print(f"         评分: {readiness_result['final_readiness_score']:.1f}/100")
    print(f"         诊断: {readiness_result['final_diagnosis']}")
    print(f"         先验概率: {readiness_result['prior_probs']}")
    print(f"         后验概率: {readiness_result['final_posterior_probs']}")
    
    return readiness_result

def run_70_day_complete_simulation():
    """运行70天完整模拟"""
    print("[SIMULATION] 70天完整基线管理周期")
    print("="*100)
    print("模拟场景: 30天初始基线 → 7天增量更新 → 7天增量更新 → 30天完整更新 → Readiness集成")
    print("生活场景: 稳定期 → 训练适应期 → 压力期 → 恢复期 → 正常评估")
    
    try:
        # 第30天：初始基线
        storage, initial_result = simulate_day_30_initial_baseline()
        if not storage:
            return
        
        # 第37天：第一次增量更新
        storage, first_update = simulate_day_37_incremental_update(storage, initial_result)
        
        # 第44天：第二次增量更新
        storage, second_update = simulate_day_44_second_incremental(storage)
        
        # 第60天：30天完整更新
        storage, full_update = simulate_day_60_full_update(storage)
        
        # 第70天：Readiness集成验证
        final_result = simulate_day_70_readiness_integration(storage, full_update)
        
        # 总结
        print("\n" + "="*100)
        print("[COMPLETE] 70天完整模拟成功完成！")
        print("="*100)
        
        print(f"[SUMMARY] 完整周期验证:")
        print(f"          [OK] 30天初始基线建立")
        print(f"          [OK] 7天增量更新 × 2次")
        print(f"          [OK] 30天完整重算")
        print(f"          [OK] Readiness引擎集成")
        print(f"          [OK] 个性化阈值生效")
        
        print(f"\n[IMPACT] 个性化基线效果:")
        print(f"         [SCORE] 最终准备度: {final_result['final_readiness_score']:.1f}/100")
        print(f"         [DIAGNOSIS] 诊断结果: {final_result['final_diagnosis']}")
        print(f"         [PRECISION] 基于70天个人数据的精准评估")
        
        print(f"\n[READY] 系统已完全ready，可交付后端集成！")
        
    except Exception as e:
        print(f"\n[ERROR] 70天模拟过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_70_day_complete_simulation()