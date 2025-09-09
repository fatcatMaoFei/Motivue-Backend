#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整流程仿真测试

完整模拟：历史数据 → Baseline计算 → 当天数据 → Readiness评估
"""

import sys
sys.path.append('.')

from datetime import datetime, timedelta
from baseline.healthkit_integration import create_sample_healthkit_data
from baseline.service import compute_baseline_from_healthkit_data
from baseline.storage import MemoryBaselineStorage
from readiness.mapping import map_inputs_to_states
from readiness.service import compute_readiness_from_payload
import json

def create_realistic_30day_data():
    """创建真实的30天历史数据"""
    
    print("[DATA] 创建30天历史数据...")
    
    # 模拟一个标准用户的30天数据
    sleep_data = []
    hrv_data = []
    
    base_date = datetime(2024, 1, 1)
    
    # 睡眠数据：模拟真实变化
    for day in range(30):
        date = base_date + timedelta(days=day)
        
        # 工作日vs周末的睡眠差异
        is_weekend = date.weekday() >= 5  # 周六日
        
        if is_weekend:
            # 周末多睡1小时
            base_sleep_minutes = 480  # 8小时
            base_efficiency = 0.82
        else:
            # 工作日
            base_sleep_minutes = 420  # 7小时
            base_efficiency = 0.85
        
        # 添加个人变化（压力、疲劳等）
        stress_factor = 0.9 if day % 7 == 0 else 1.0  # 每周一压力大
        sleep_minutes = int(base_sleep_minutes * stress_factor + (day % 5 - 2) * 15)
        efficiency = base_efficiency + (day % 6 - 2.5) * 0.02
        
        # 计算睡眠阶段
        deep_minutes = int(sleep_minutes * (0.15 + (day % 4) * 0.01))  # 15-18%
        rem_minutes = int(sleep_minutes * (0.22 + (day % 3) * 0.01))   # 22-24%
        core_minutes = sleep_minutes - deep_minutes - rem_minutes
        
        sleep_record = {
            'date': date.isoformat() + 'Z',
            'sleep_duration_minutes': sleep_minutes,
            'time_in_bed_minutes': int(sleep_minutes / efficiency),
            'deep_sleep_minutes': deep_minutes,
            'rem_sleep_minutes': rem_minutes, 
            'core_sleep_minutes': core_minutes,
            'awake_minutes': int((sleep_minutes / efficiency) - sleep_minutes),
            'source_device': 'Apple Watch Series 9'
        }
        
        sleep_data.append(sleep_record)
    
    # HRV数据：45个测量点
    for i in range(45):
        timestamp = base_date + timedelta(days=i*30//45, hours=8, minutes=i*10)
        
        # 基础HRV: 38ms，随个人状态变化
        base_hrv = 38.0
        daily_variation = (i % 7 - 3) * 2.0  # 每周变化
        recovery_status = 1.0 if i % 10 < 7 else 0.85  # 偶尔恢复不好
        
        hrv_value = base_hrv * recovery_status + daily_variation + (i % 5 - 2) * 1.5
        hrv_value = max(20.0, min(60.0, hrv_value))  # 限制在合理范围
        
        hrv_record = {
            'timestamp': timestamp.isoformat() + 'Z',
            'sdnn_value': round(hrv_value, 1),
            'source_device': 'Apple Watch Series 9',
            'measurement_context': 'morning'
        }
        
        hrv_data.append(hrv_record)
    
    print(f"[SUCCESS] 创建完成: {len(sleep_data)}天睡眠数据, {len(hrv_data)}个HRV记录")
    
    return sleep_data, hrv_data

def calculate_personal_baseline(sleep_data, hrv_data):
    """计算个人基线"""
    
    print("\n[BASELINE] 计算个人基线...")
    
    # 初始化存储
    storage = MemoryBaselineStorage()
    
    # 调用baseline计算API
    result = compute_baseline_from_healthkit_data(
        user_id="simulation_user_001",
        healthkit_sleep_data=sleep_data,
        healthkit_hrv_data=hrv_data,
        storage=storage
    )
    
    print(f"[RESULT] 基线计算结果: {result['status']}")
    
    if result['status'] == 'success':
        baseline = result['baseline']
        print(f"[SUCCESS] 个人基线计算成功:")
        print(f"   睡眠时长基线: {baseline['sleep_baseline_hours']:.1f}小时")
        print(f"   睡眠效率基线: {baseline['sleep_baseline_eff']:.1%}")
        print(f"   恢复性睡眠基线: {baseline['rest_baseline_ratio']:.1%}")
        print(f"   HRV基线: {baseline['hrv_baseline_mu']:.1f}±{baseline['hrv_baseline_sd']:.1f}ms")
        print(f"   数据质量评分: {result['data_quality']:.2f}")
        
        return result, storage
    
    else:
        print(f"[ERROR] 基线计算失败: {result.get('message', 'unknown error')}")
        return None, None

def simulate_today_data(personal_baseline):
    """模拟当天的健康数据"""
    
    print(f"\n[TODAY] 模拟当天数据...")
    
    baseline_sleep = personal_baseline['baseline']['sleep_baseline_hours']  
    baseline_hrv = personal_baseline['baseline']['hrv_baseline_mu']
    
    # 场景：用户昨晚睡得还可以，但略低于个人基线
    today_sleep_hours = baseline_sleep - 0.3  # 比基线少0.3小时
    today_efficiency = 0.82  # 效率还不错
    today_hrv = baseline_hrv - 2.0  # HRV略低于基线
    
    # 恢复性睡眠数据
    today_deep_ratio = 0.16  # 16%深睡眠
    today_rem_ratio = 0.21   # 21%REM
    today_restorative_ratio = today_deep_ratio + today_rem_ratio  # 37%
    
    today_data = {
        # 客观数据
        'sleep_duration_hours': today_sleep_hours,
        'sleep_efficiency': today_efficiency,
        'hrv_rmssd_today': today_hrv,
        'restorative_ratio': today_restorative_ratio,
        'deep_sleep_ratio': today_deep_ratio,
        'rem_sleep_ratio': today_rem_ratio,
        
        # Hooper量表 - 默认3分（中等）
        'fatigue_hooper': 3,
        'soreness_hooper': 3,  
        'stress_hooper': 3,
        'sleep_hooper': 3,
        
        # 布尔值
        'is_sick': False,
        'is_injured': False,
        'high_stress_event_today': False,
        'meditation_done_today': False,
        
        # 训练强度 - 中等
        'training_intensity': 'medium'  # 这个字段mapping.py可能没用，但记录一下
    }
    
    print(f"[INFO] 当天数据:")
    print(f"   睡眠: {today_sleep_hours:.1f}h, 效率{today_efficiency:.1%}")
    print(f"   HRV: {today_hrv:.1f}ms") 
    print(f"   恢复性睡眠: {today_restorative_ratio:.1%}")
    print(f"   Hooper评分: 疲劳{today_data['fatigue_hooper']}, 压力{today_data['stress_hooper']}")
    
    return today_data

def calculate_readiness_with_baseline(today_data, personal_baseline):
    """使用个人基线和你的readiness引擎计算准备度"""
    
    print(f"\n[READINESS] 使用readiness引擎计算个性化准备度...")
    
    # 先通过mapping将原始数据转换为状态
    mapping_payload = today_data.copy()
    baseline_data = personal_baseline['readiness_payload']
    mapping_payload.update(baseline_data)
    
    print(f"[INJECT] 基线数据注入:")
    print(f"   sleep_baseline_hours: {baseline_data['sleep_baseline_hours']:.1f}")
    print(f"   hrv_baseline_mu: {baseline_data['hrv_baseline_mu']:.1f}")
    print(f"   hrv_baseline_sd: {baseline_data['hrv_baseline_sd']:.1f}")
    
    # 调用mapping获取状态
    states = map_inputs_to_states(mapping_payload)
    
    print(f"\n[MAPPING] 状态结果:")
    for key, value in states.items():
        if key.endswith('_score'):
            continue
        print(f"   {key}: {value}")
    
    # 构造readiness service需要的完整payload格式
    readiness_payload = {
        'user_id': 'simulation_user_001',
        'date': '2024-01-31',  # 假设今天日期
        'gender': '男性',
        
        # objective数据部分 - 使用mapping后的状态
        'objective': states,
        
        # hooper量表数据
        'hooper': {
            'fatigue': today_data['fatigue_hooper'],
            'soreness': today_data['soreness_hooper'], 
            'stress': today_data['stress_hooper'],
            'sleep': today_data['sleep_hooper']
        },
        
        # journal数据
        'journal': {
            'is_sick': today_data['is_sick'],
            'is_injured': today_data['is_injured'],
            'high_stress_event_today': today_data['high_stress_event_today'],
            'meditation_done_today': today_data['meditation_done_today']
        }
    }
    
    print(f"\n[ENGINE] 调用readiness引擎...")
    
    # 调用你的readiness服务
    readiness_result = compute_readiness_from_payload(readiness_payload)
    
    print(f"[RESULT] Readiness引擎结果:")
    print(f"   最终评分: {readiness_result['final_readiness_score']:.1f}/100")
    print(f"   最终诊断: {readiness_result['final_diagnosis']}")
    print(f"   先验概率: {readiness_result['prior_probs']}")
    print(f"   后验概率: {readiness_result['final_posterior_probs']}")
    
    return states, mapping_payload, readiness_result


def calculate_readiness_without_baseline(today_data):
    """不使用个人基线计算准备度（对比）"""
    
    print(f"\n[COMPARE] 对比：无基线的准备度计算...")
    
    # 不注入基线数据，使用默认阈值
    default_payload = today_data.copy()
    
    # 添加7天HRV平均作为fallback（模拟）
    default_payload['hrv_rmssd_7day_avg'] = 39.0  # 假设的7天平均
    
    states = map_inputs_to_states(default_payload)
    
    print(f"[DEFAULT] 默认阈值结果:")
    for key, value in states.items():
        if key.endswith('_score'):
            continue
        print(f"   {key}: {value}")
    
    return states

def analyze_personalization_effect(personalized_states, default_states, baseline_info, today_data, readiness_result):
    """分析个性化效果"""
    
    print(f"\n[ANALYSIS] 个性化效果分析:")
    print("=" * 50)
    
    # 首先显示最终的准备度评分
    print(f"[SCORE] 最终准备度评分: {readiness_result['final_readiness_score']:.1f}/100")
    print(f"[DIAGNOSIS] 诊断结果: {readiness_result['final_diagnosis']}")
    print()
    
    baseline_sleep = baseline_info['baseline']['sleep_baseline_hours']
    today_sleep = today_data['sleep_duration_hours']
    
    # 分析睡眠表现差异
    personal_sleep = personalized_states.get('sleep_performance', 'unknown')
    default_sleep = default_states.get('sleep_performance', 'unknown')
    
    print(f"[SLEEP] 睡眠表现对比:")
    print(f"   个人基线: {baseline_sleep:.1f}h")
    print(f"   当天睡眠: {today_sleep:.1f}h (比基线{today_sleep-baseline_sleep:+.1f}h)")
    
    # 计算个性化阈值
    good_threshold = min(9.0, max(7.0, baseline_sleep + 1.0))
    med_threshold = min(8.0, max(6.0, baseline_sleep - 0.5))
    
    print(f"   个性化阈值: good≥{good_threshold:.1f}h, medium≥{med_threshold:.1f}h")
    print(f"   个性化判断: {personal_sleep}")
    print(f"   默认阈值判断: {default_sleep}")
    
    if personal_sleep != default_sleep:
        print(f"   [PERSONALIZED] 个性化生效: {default_sleep} -> {personal_sleep}")
        
        if today_sleep < baseline_sleep:
            print(f"      用户睡眠低于个人基线，个性化给出更合理的评估")
        else:
            print(f"      用户睡眠符合个人模式，个性化给出更准确的评估")
    else:
        print(f"   [SAME] 两种方式结果一致: {personal_sleep}")
    
    # HRV趋势分析
    personal_hrv = personalized_states.get('hrv_trend', 'unknown')
    default_hrv = default_states.get('hrv_trend', 'unknown')
    
    print(f"\n[HRV] HRV趋势对比:")
    baseline_hrv_mu = baseline_info['baseline']['hrv_baseline_mu']
    baseline_hrv_sd = baseline_info['baseline']['hrv_baseline_sd']
    today_hrv = today_data['hrv_rmssd_today']
    
    hrv_z_score = (today_hrv - baseline_hrv_mu) / baseline_hrv_sd
    
    print(f"   个人HRV基线: {baseline_hrv_mu:.1f}±{baseline_hrv_sd:.1f}ms")
    print(f"   当天HRV: {today_hrv:.1f}ms (Z分数: {hrv_z_score:.2f})")
    print(f"   个性化判断: {personal_hrv}")
    print(f"   默认方法判断: {default_hrv}")
    
    if personal_hrv != default_hrv:
        print(f"   [PERSONALIZED] 个性化HRV分析更精准")

def run_complete_simulation():
    """运行完整仿真流程"""
    
    print("[SIMULATION] 完整流程仿真测试")
    print("=" * 80)
    print("目标：模拟真实用户从数据收集到准备度评估的完整流程")
    
    # 1. 创建历史数据
    sleep_data, hrv_data = create_realistic_30day_data()
    
    # 2. 计算个人基线
    baseline_result, storage = calculate_personal_baseline(sleep_data, hrv_data)
    
    if not baseline_result:
        print("[ERROR] 基线计算失败，无法继续")
        return
    
    # 3. 模拟当天数据
    today_data = simulate_today_data(baseline_result)
    
    # 4. 个性化准备度计算
    personalized_states, full_payload, readiness_result = calculate_readiness_with_baseline(
        today_data, baseline_result
    )
    
    # 5. 对比默认阈值
    default_states = calculate_readiness_without_baseline(today_data)
    
    # 6. 分析个性化效果
    analyze_personalization_effect(
        personalized_states, default_states, baseline_result, today_data, readiness_result
    )
    
    print(f"\n[COMPLETE] 完整流程仿真完成！")
    print(f"[SUCCESS] 历史数据 -> 个人基线 -> 个性化评估 全流程打通")
    print(f"[SUCCESS] 验证了个性化基线的实际效果")
    
    # 输出最终的完整payload供参考
    print(f"\n[PAYLOAD] 完整的readiness计算payload:")
    print("=" * 50)
    
    key_fields = [
        'sleep_duration_hours', 'sleep_efficiency', 'sleep_baseline_hours', 'sleep_baseline_eff',
        'hrv_rmssd_today', 'hrv_baseline_mu', 'hrv_baseline_sd',
        'restorative_ratio', 'rest_baseline_ratio',
        'fatigue_hooper', 'stress_hooper'
    ]
    
    for field in key_fields:
        if field in full_payload:
            value = full_payload[field]
            if isinstance(value, float):
                print(f"   {field}: {value:.2f}")
            else:
                print(f"   {field}: {value}")

if __name__ == '__main__':
    run_complete_simulation()