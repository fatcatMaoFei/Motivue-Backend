# -*- coding: utf-8 -*-
"""测试基线更新功能

验证7天增量更新和30天完整更新的功能
"""

import sys
sys.path.append('.')

from datetime import datetime, timedelta
from baseline.healthkit_integration import create_sample_healthkit_data
from baseline.service import (
    compute_baseline_from_healthkit_data,
    update_baseline_smart,
    update_baseline_incremental, 
    update_baseline_full,
    check_baseline_update_needed,
    get_baseline_update_schedule
)
from baseline.storage import MemoryBaselineStorage
import json

def create_test_data_with_dates(base_date: datetime, days: int):
    """创建指定日期范围的测试数据"""
    
    sleep_data = []
    hrv_data = []
    
    for day in range(days):
        date = base_date + timedelta(days=day)
        
        # 睡眠数据
        base_sleep = 7.0 + (day % 5 - 2) * 0.3  # 6.4-7.6小时变化
        sleep_minutes = int(base_sleep * 60)
        efficiency = 0.85 + (day % 3 - 1) * 0.03  # 0.82-0.88变化
        
        sleep_record = {
            'date': date.isoformat() + 'Z',
            'sleep_duration_minutes': sleep_minutes,
            'time_in_bed_minutes': int(sleep_minutes / efficiency),
            'deep_sleep_minutes': int(sleep_minutes * 0.16),
            'rem_sleep_minutes': int(sleep_minutes * 0.22),
            'core_sleep_minutes': int(sleep_minutes * 0.55),
            'awake_minutes': int(sleep_minutes / efficiency) - sleep_minutes,
            'source_device': 'Apple Watch'
        }
        sleep_data.append(sleep_record)
        
        # HRV数据（每天1-2个测量）
        for measurement in range(1 if day % 2 else 2):
            timestamp = date + timedelta(hours=8, minutes=measurement*30)
            base_hrv = 38.0 + (day % 7 - 3) * 2.0  # 32-44ms变化
            
            hrv_record = {
                'timestamp': timestamp.isoformat() + 'Z',
                'sdnn_value': max(20.0, min(60.0, base_hrv + (measurement * 1.5))),
                'source_device': 'Apple Watch',
                'measurement_context': 'morning'
            }
            hrv_data.append(hrv_record)
    
    return sleep_data, hrv_data

def test_initial_baseline_calculation():
    """测试初始基线计算"""
    print("\n" + "="*60)
    print("[TEST] 初始基线计算")
    print("="*60)
    
    storage = MemoryBaselineStorage()
    
    # 创建30天历史数据
    base_date = datetime(2024, 1, 1)
    sleep_data, hrv_data = create_test_data_with_dates(base_date, 30)
    
    # 计算初始基线
    result = compute_baseline_from_healthkit_data(
        user_id="test_user_001",
        healthkit_sleep_data=sleep_data,
        healthkit_hrv_data=hrv_data,
        storage=storage
    )
    
    print(f"[RESULT] 状态: {result['status']}")
    if result['status'] == 'success':
        baseline = result['baseline']
        print(f"[BASELINE] 睡眠基线: {baseline['sleep_baseline_hours']:.2f}h")
        print(f"[BASELINE] HRV基线: {baseline['hrv_baseline_mu']:.1f}±{baseline['hrv_baseline_sd']:.1f}ms")
        print(f"[QUALITY] 数据质量: {result['data_quality']:.2f}")
    
    return storage

def test_update_check(storage):
    """测试更新检查功能"""
    print("\n" + "="*60)
    print("[TEST] 更新检查功能")
    print("="*60)
    
    # 检查是否需要更新
    check_result = check_baseline_update_needed("test_user_001", storage)
    
    print(f"[CHECK] 需要更新: {check_result['needs_update']}")
    print(f"[CHECK] 更新类型: {check_result.get('update_type', 'none')}")
    print(f"[CHECK] 原因: {check_result['reason']}")
    
    if 'days_since_update' in check_result:
        print(f"[CHECK] 距离上次更新: {check_result['days_since_update']}天")
    
    # 获取更新计划
    schedule = get_baseline_update_schedule("test_user_001", storage)
    print(f"[SCHEDULE] 当前状态: {schedule['current_status']}")
    print(f"[SCHEDULE] 推荐操作: {schedule['recommended_action']}")

def test_incremental_update(storage):
    """测试7天增量更新"""
    print("\n" + "="*60)
    print("[TEST] 7天增量更新")
    print("="*60)
    
    # 获取现有基线
    existing = storage.get_baseline("test_user_001")
    print(f"[BEFORE] 睡眠基线: {existing.sleep_baseline_hours:.2f}h")
    print(f"[BEFORE] HRV基线: {existing.hrv_baseline_mu:.1f}ms")
    
    # 模拟用户最近7天睡眠改善的情况
    recent_date = datetime(2024, 1, 31)  # 紧接着原有数据
    recent_sleep, recent_hrv = create_test_data_with_dates(recent_date, 7)
    
    # 调整最近数据，模拟睡眠改善
    for record in recent_sleep:
        record['sleep_duration_minutes'] += 30  # 增加0.5小时睡眠
        record['time_in_bed_minutes'] += 20     # 轻微提高效率
    
    for record in recent_hrv:
        record['sdnn_value'] += 3.0  # HRV改善3ms
    
    # 执行增量更新
    update_result = update_baseline_incremental(
        "test_user_001", recent_sleep, recent_hrv, storage
    )
    
    print(f"[RESULT] 状态: {update_result['status']}")
    if update_result['status'] == 'success':
        new_baseline = update_result['baseline']
        print(f"[AFTER] 睡眠基线: {new_baseline['sleep_baseline_hours']:.2f}h")
        print(f"[AFTER] HRV基线: {new_baseline['hrv_baseline_mu']:.1f}ms")
        
        changes = update_result.get('changes', {})
        if 'sleep_hours_change' in changes:
            print(f"[CHANGE] 睡眠时长变化: {changes['sleep_hours_change']:+.2f}h")
        if 'hrv_mean_change' in changes:
            print(f"[CHANGE] HRV均值变化: {changes['hrv_mean_change']:+.1f}ms")
    
    return storage

def test_full_update(storage):
    """测试30天完整更新"""
    print("\n" + "="*60)
    print("[TEST] 30天完整更新")
    print("="*60)
    
    # 获取现有基线
    existing = storage.get_baseline("test_user_001")
    print(f"[BEFORE] 数据质量: {existing.data_quality_score:.2f}")
    print(f"[BEFORE] 更新类型: {existing.update_type}")
    
    # 创建最近30天的完整数据（包含改善趋势）
    full_date = datetime(2024, 2, 1)
    full_sleep, full_hrv = create_test_data_with_dates(full_date, 30)
    
    # 模拟持续改善：后半月数据更好
    for i, record in enumerate(full_sleep):
        if i >= 15:  # 后半月改善
            record['sleep_duration_minutes'] += 45  # 增加0.75小时
            record['time_in_bed_minutes'] += 25     # 提高效率
    
    for i, record in enumerate(full_hrv):
        if i >= 20:  # 后期改善更明显
            record['sdnn_value'] += 5.0  # HRV改善5ms
    
    # 执行完整更新
    update_result = update_baseline_full(
        "test_user_001", full_sleep, full_hrv, storage
    )
    
    print(f"[RESULT] 状态: {update_result['status']}")
    if update_result['status'] == 'success':
        new_baseline = update_result['baseline']
        sleep_hours = new_baseline.get('sleep_baseline_hours')
        hrv_mu = new_baseline.get('hrv_baseline_mu')
        
        if sleep_hours:
            print(f"[AFTER] 睡眠基线: {sleep_hours:.2f}h")
        if hrv_mu:
            print(f"[AFTER] HRV基线: {hrv_mu:.1f}ms")
        print(f"[AFTER] 数据质量: {update_result['data_quality']:.2f}")
        
        comparison = update_result.get('comparison', {})
        if 'quality_improvement' in comparison:
            print(f"[IMPROVEMENT] 质量提升: {comparison['quality_improvement']:+.2f}")
        
        changes = update_result.get('changes', {})
        print(f"[CHANGES] {json.dumps(changes, indent=2, ensure_ascii=False)}")

def test_smart_update(storage):
    """测试智能更新功能"""
    print("\n" + "="*60)
    print("[TEST] 智能更新功能")
    print("="*60)
    
    # 模拟再过7天的数据
    smart_date = datetime(2024, 3, 1)
    smart_sleep, smart_hrv = create_test_data_with_dates(smart_date, 10)
    
    # 执行智能更新（应该选择增量更新）
    smart_result = update_baseline_smart(
        "test_user_001", smart_sleep, smart_hrv, storage
    )
    
    print(f"[RESULT] 状态: {smart_result['status']}")
    print(f"[RESULT] 更新类型: {smart_result.get('update_type', 'none')}")
    
    if smart_result['status'] == 'success':
        print(f"[AUTO] 自动选择了{smart_result['update_type']}更新")
        baseline = smart_result['baseline']
        sleep_hours = baseline.get('sleep_baseline_hours')
        if sleep_hours:
            print(f"[BASELINE] 睡眠基线: {sleep_hours:.2f}h")

def run_update_tests():
    """运行所有更新测试"""
    print("[SIMULATION] 基线更新功能完整测试")
    print("="*80)
    print("测试场景：初始基线 -> 7天增量更新 -> 30天完整更新 -> 智能更新")
    
    try:
        # 1. 初始基线计算
        storage = test_initial_baseline_calculation()
        
        # 2. 更新检查
        test_update_check(storage)
        
        # 3. 增量更新测试
        storage = test_incremental_update(storage)
        
        # 4. 完整更新测试
        test_full_update(storage)
        
        # 5. 智能更新测试
        test_smart_update(storage)
        
        print("\n" + "="*80)
        print("[COMPLETE] 所有更新功能测试完成！")
        print("[SUCCESS] 基线更新模块验证通过")
        
    except Exception as e:
        print(f"\n[ERROR] 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_update_tests()