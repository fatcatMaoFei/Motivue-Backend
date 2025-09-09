"""展示 baseline 模块与 readiness 模块集成的示例

演示如何将个人基线数据集成到 readiness 准备度计算中，
实现个性化的准备度评估。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from baseline import compute_personal_baseline
from baseline.service import get_user_baseline  
from baseline.storage import MemoryBaselineStorage

# 导入 readiness 模块
from readiness.service import compute_readiness_from_payload
from readiness.mapping import map_inputs_to_states

def create_user_baseline(user_id: str, sleep_hours_avg: float, sleep_eff_avg: float, hrv_avg: float):
    """为指定用户创建个人基线"""
    
    # 生成符合指定基线的历史数据
    sleep_data = []
    hrv_data = []
    
    base_date = datetime.now() - timedelta(days=30)
    
    # 生成睡眠数据（围绕指定的平均值变化）
    for i in range(25):  # 25天睡眠数据
        date = base_date + timedelta(days=i)
        
        # 在平均值基础上添加随机变化
        duration = sleep_hours_avg + (i % 7 - 3) * 0.15
        efficiency = sleep_eff_avg + (i % 5 - 2) * 0.02
        
        sleep_data.append({
            'date': date.isoformat(),
            'sleep_duration_hours': max(4.0, min(12.0, duration)),
            'sleep_efficiency': max(0.5, min(1.0, efficiency)),
            'deep_sleep_ratio': 0.15 + (i % 3) * 0.01,
            'rem_sleep_ratio': 0.22 + (i % 4) * 0.005
        })
    
    # 生成HRV数据
    for i in range(0, 20, 2):  # 10个HRV测量
        timestamp = base_date + timedelta(days=i, hours=8)
        hrv_value = hrv_avg + (i % 8 - 4) * 3  # 在平均值周围变化
        
        hrv_data.append({
            'timestamp': timestamp.isoformat(),
            'sdnn_value': max(10.0, min(100.0, hrv_value))
        })
    
    # 计算并返回基线
    storage = MemoryBaselineStorage()
    result = compute_personal_baseline(user_id, sleep_data, hrv_data, storage)
    
    return result, storage

def demo_personalized_readiness():
    """演示个性化准备度评估"""
    print("=== 个性化准备度评估示例 ===")
    
    # 创建三种不同类型的用户基线
    
    # 1. 短睡眠高效型用户
    print("\n1. 短睡眠高效型用户 (小明)")
    user_a_result, storage_a = create_user_baseline(
        user_id='xiaoming',
        sleep_hours_avg=6.2,    # 平均只需6.2小时
        sleep_eff_avg=0.92,     # 但睡眠效率很高
        hrv_avg=38.0           # HRV中等
    )
    
    if user_a_result['status'] == 'success':
        baseline_a = user_a_result['baseline']
        print(f"  基线: {baseline_a['sleep_baseline_hours']:.1f}小时, 效率{baseline_a['sleep_baseline_eff']:.2f}")
    
    # 2. 长睡眠需求型用户  
    print("\n2. 长睡眠需求型用户 (小红)")
    user_b_result, storage_b = create_user_baseline(
        user_id='xiaohong', 
        sleep_hours_avg=8.5,    # 需要8.5小时才恢复
        sleep_eff_avg=0.76,     # 睡眠效率较低
        hrv_avg=52.0           # HRV较高
    )
    
    if user_b_result['status'] == 'success':
        baseline_b = user_b_result['baseline']
        print(f"  基线: {baseline_b['sleep_baseline_hours']:.1f}小时, 效率{baseline_b['sleep_baseline_eff']:.2f}")
    
    # 3. 运动员型用户
    print("\n3. 运动员型用户 (小强)")
    user_c_result, storage_c = create_user_baseline(
        user_id='xiaoqiang',
        sleep_hours_avg=7.8,    # 中等睡眠时长
        sleep_eff_avg=0.88,     # 高效率
        hrv_avg=65.0           # 很高的HRV
    )
    
    if user_c_result['status'] == 'success':
        baseline_c = user_c_result['baseline']
        print(f"  基线: {baseline_c['sleep_baseline_hours']:.1f}小时, 效率{baseline_c['sleep_baseline_eff']:.2f}")
    
    # 现在测试相同睡眠数据在不同基线下的评估结果
    print("\n=== 相同睡眠表现的个性化评估对比 ===")
    
    # 测试数据：7小时睡眠，85%效率
    test_sleep_data = {
        'sleep_duration_hours': 7.0,
        'sleep_efficiency': 0.85,
        'hrv_rmssd_today': 45.0,
        'training_load': '中',
        'date': datetime.now().strftime('%Y-%m-%d')
    }
    
    print(f"测试睡眠: {test_sleep_data['sleep_duration_hours']}小时, 效率{test_sleep_data['sleep_efficiency']}")
    
    # 分别为三个用户计算准备度
    users_data = [
        ('小明(短睡眠)', 'xiaoming', storage_a),
        ('小红(长睡眠)', 'xiaohong', storage_b), 
        ('小强(运动员)', 'xiaoqiang', storage_c)
    ]
    
    for name, user_id, storage in users_data:
        # 构造payload
        payload = test_sleep_data.copy()
        payload['user_id'] = user_id
        
        # 获取个人基线并注入
        baseline = get_user_baseline(user_id, storage)
        if baseline:
            payload.update(baseline.to_readiness_payload())
            print(f"\n{name}:")
            print(f"  个人基线已注入: sleep_baseline_hours={payload.get('sleep_baseline_hours'):.1f}")
            
            # 查看mapping结果
            mapped = map_inputs_to_states(payload)
            sleep_perf = mapped.get('sleep_performance', '未知')
            print(f"  映射结果: sleep_performance = '{sleep_perf}'")
            
            # 计算完整准备度  
            try:
                readiness_result = compute_readiness_from_payload(payload)
                score = readiness_result.get('final_readiness_score', 0)
                diagnosis = readiness_result.get('final_diagnosis', '未知')
                print(f"  准备度评分: {score}/100")
                print(f"  诊断结果: {diagnosis}")
            except Exception as e:
                print(f"  准备度计算错误: {e}")

def demo_baseline_threshold_adjustment():
    """演示基线如何调整判定阈值"""
    print("\n\n=== 基线阈值调整机制演示 ===")
    
    # 创建一个有特定基线的用户
    user_result, storage = create_user_baseline(
        user_id='demo_user',
        sleep_hours_avg=6.8,    # 个人基线6.8小时
        sleep_eff_avg=0.90,     # 个人基线90%效率
        hrv_avg=42.0
    )
    
    if user_result['status'] != 'success':
        print("基线创建失败")
        return
        
    baseline = get_user_baseline('demo_user', storage)
    baseline_payload = baseline.to_readiness_payload()
    
    print(f"用户个人基线:")
    print(f"  sleep_baseline_hours: {baseline_payload['sleep_baseline_hours']:.1f}")
    print(f"  sleep_baseline_eff: {baseline_payload['sleep_baseline_eff']:.3f}")
    
    # 测试不同睡眠数据的映射结果
    test_cases = [
        {'duration': 6.5, 'efficiency': 0.88, 'desc': '个人基线以下'},
        {'duration': 7.0, 'efficiency': 0.85, 'desc': '标准阈值边界'},
        {'duration': 7.5, 'efficiency': 0.92, 'desc': '高于个人基线'},
    ]
    
    print(f"\n阈值调整效果对比:")
    print(f"{'睡眠数据':<15} {'无基线映射':<12} {'有基线映射':<12} {'阈值调整'}")
    print("-" * 55)
    
    for case in test_cases:
        # 无基线映射（使用默认阈值）
        payload_no_baseline = {
            'sleep_duration_hours': case['duration'],
            'sleep_efficiency': case['efficiency']
        }
        mapped_no_baseline = map_inputs_to_states(payload_no_baseline)
        result_no_baseline = mapped_no_baseline.get('sleep_performance', '未知')
        
        # 有基线映射（使用个人基线调整阈值）
        payload_with_baseline = payload_no_baseline.copy()
        payload_with_baseline.update(baseline_payload)
        mapped_with_baseline = map_inputs_to_states(payload_with_baseline)
        result_with_baseline = mapped_with_baseline.get('sleep_performance', '未知')
        
        # 计算实际使用的阈值
        mu_dur = baseline_payload['sleep_baseline_hours']
        mu_eff = baseline_payload['sleep_baseline_eff']
        good_dur_threshold = max(7.0, mu_dur - 0.5)  # 来自mapping.py逻辑
        good_eff_threshold = max(0.85, mu_eff - 0.05)
        
        adjustment_desc = f"时长≥{good_dur_threshold:.1f}h且效率≥{good_eff_threshold:.2f}"
        
        data_desc = f"{case['duration']}h/{case['efficiency']:.2f}"
        print(f"{data_desc:<15} {result_no_baseline:<12} {result_with_baseline:<12} {adjustment_desc}")

def demo_hrv_baseline_usage():
    """演示HRV基线的使用"""
    print("\n\n=== HRV基线使用示例 ===")
    
    # 创建HRV基线差异较大的两个用户
    low_hrv_result, storage_low = create_user_baseline(
        user_id='low_hrv_user',
        sleep_hours_avg=7.0,
        sleep_eff_avg=0.85,
        hrv_avg=25.0    # 低HRV基线
    )
    
    high_hrv_result, storage_high = create_user_baseline(
        user_id='high_hrv_user', 
        sleep_hours_avg=7.0,
        sleep_eff_avg=0.85,
        hrv_avg=60.0    # 高HRV基线
    )
    
    if low_hrv_result['status'] == 'success' and high_hrv_result['status'] == 'success':
        low_baseline = get_user_baseline('low_hrv_user', storage_low).to_readiness_payload()
        high_baseline = get_user_baseline('high_hrv_user', storage_high).to_readiness_payload()
        
        print(f"低HRV用户基线: μ={low_baseline['hrv_baseline_mu']:.1f}, σ={low_baseline['hrv_baseline_sd']:.1f}")
        print(f"高HRV用户基线: μ={high_baseline['hrv_baseline_mu']:.1f}, σ={high_baseline['hrv_baseline_sd']:.1f}")
        
        # 测试相同HRV数值在不同基线下的评估
        test_hrv_value = 35.0  # 测试HRV值
        
        print(f"\n当前HRV值: {test_hrv_value} ms")
        
        for user_name, baseline in [('低HRV用户', low_baseline), ('高HRV用户', high_baseline)]:
            payload = {
                'hrv_rmssd_today': test_hrv_value,
                'hrv_baseline_mu': baseline['hrv_baseline_mu'],
                'hrv_baseline_sd': baseline['hrv_baseline_sd']
            }
            
            mapped = map_inputs_to_states(payload)
            hrv_trend = mapped.get('hrv_trend', '未知')
            
            # 计算Z分数
            mu = baseline['hrv_baseline_mu'] 
            sd = baseline['hrv_baseline_sd']
            z_score = (test_hrv_value - mu) / sd if sd > 0 else 0
            
            print(f"  {user_name}: Z分数={z_score:.2f}, HRV趋势='{hrv_trend}'")

if __name__ == '__main__':
    demo_personalized_readiness()
    demo_baseline_threshold_adjustment() 
    demo_hrv_baseline_usage()
    
    print("\n=== 集成示例完成 ===")
    print("可以看到，个人基线显著影响了准备度评估的个性化程度！")