"""基线模块基本使用示例

演示如何使用 baseline 模块计算个人健康基线。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from baseline import compute_personal_baseline
from baseline.storage import FileBaselineStorage, MemoryBaselineStorage
from baseline.models import SleepRecord, HRVRecord

def generate_sample_data():
    """生成示例健康数据"""
    # 生成过去30天的睡眠数据
    sleep_data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        
        # 模拟个人睡眠模式：平均7.2小时，效率85%，有一些变化
        duration = 7.2 + (i % 7 - 3) * 0.2  # 6.6 - 7.8 小时
        efficiency = 0.85 + (i % 5 - 2) * 0.02  # 0.81 - 0.89
        
        sleep_data.append({
            'date': date.isoformat(),
            'sleep_duration_hours': duration,
            'sleep_efficiency': efficiency,
            'deep_sleep_ratio': 0.15 + (i % 3) * 0.02,
            'rem_sleep_ratio': 0.22 + (i % 4) * 0.01,
            'source_device': 'Apple Watch'
        })
    
    # 生成过去28天的HRV数据（不是每天都有）
    hrv_data = []
    for i in range(0, 28, 2):  # 每两天一个HRV测量
        timestamp = base_date + timedelta(days=i, hours=8)  # 早上8点测量
        
        # 模拟个人HRV模式：基线45ms，标准差8ms
        hrv_value = 45 + (i % 9 - 4) * 2  # 37-53 ms范围
        
        hrv_data.append({
            'timestamp': timestamp.isoformat(),
            'sdnn_value': hrv_value,
            'source_device': 'Apple Watch',
            'measurement_context': 'morning'
        })
    
    return sleep_data, hrv_data

def demo_basic_calculation():
    """演示基本的基线计算"""
    print("=== 基线计算基本示例 ===")
    
    # 1. 生成示例数据
    sleep_data, hrv_data = generate_sample_data()
    print(f"生成了 {len(sleep_data)} 条睡眠记录和 {len(hrv_data)} 条HRV记录")
    
    # 2. 使用内存存储进行计算
    result = compute_personal_baseline(
        user_id='demo_user',
        sleep_data=sleep_data,
        hrv_data=hrv_data,
        storage=MemoryBaselineStorage()
    )
    
    # 3. 显示结果
    print(f"\n计算状态: {result['status']}")
    print(f"数据质量评分: {result['data_quality']}")
    
    if result['status'] == 'success':
        baseline = result['baseline']
        print(f"\n个人睡眠基线:")
        print(f"  平均睡眠时长: {baseline['sleep_baseline_hours']:.1f} 小时")
        print(f"  平均睡眠效率: {baseline['sleep_baseline_eff']:.3f}")
        print(f"  恢复性睡眠比例: {baseline['rest_baseline_ratio']:.3f}")
        
        print(f"\n个人HRV基线:")
        print(f"  HRV均值: {baseline['hrv_baseline_mu']:.1f} ms")
        print(f"  HRV标准差: {baseline['hrv_baseline_sd']:.1f} ms")
        
        print(f"\n数据质量:")
        print(f"  睡眠数据天数: {baseline['sample_days_sleep']}")
        print(f"  HRV数据点数: {baseline['sample_days_hrv']}")
        
        # 显示用于 readiness 模块的负载格式
        readiness_payload = result['readiness_payload']
        print(f"\n用于 readiness 模块的基线数据:")
        for key, value in readiness_payload.items():
            print(f"  {key}: {value}")
    
    return result

def demo_file_storage():
    """演示文件存储的使用"""
    print("\n=== 文件存储示例 ===")
    
    # 1. 创建文件存储实例
    storage = FileBaselineStorage(storage_dir="demo_baseline_data")
    
    # 2. 生成数据并计算基线
    sleep_data, hrv_data = generate_sample_data()
    
    result = compute_personal_baseline(
        user_id='file_demo_user',
        sleep_data=sleep_data,
        hrv_data=hrv_data,
        storage=storage
    )
    
    if result['status'] == 'success':
        print("基线数据已保存到文件")
        
        # 3. 从存储中读取基线
        from baseline.service import get_user_baseline
        loaded_baseline = get_user_baseline('file_demo_user', storage)
        
        if loaded_baseline:
            print("成功从文件加载基线数据:")
            print(f"  用户ID: {loaded_baseline.user_id}")
            print(f"  睡眠基线: {loaded_baseline.sleep_baseline_hours:.1f}小时")
            print(f"  创建时间: {loaded_baseline.created_at}")
        
        # 4. 列出所有用户
        users = storage.list_users_with_baselines()
        print(f"存储中的用户: {users}")

def demo_quality_assessment():
    """演示数据质量评估"""
    print("\n=== 数据质量评估示例 ===")
    
    # 1. 高质量数据
    sleep_data, hrv_data = generate_sample_data()
    result_high = compute_personal_baseline('high_quality_user', sleep_data, hrv_data)
    print(f"高质量数据评分: {result_high['data_quality']:.3f}")
    
    # 2. 低质量数据（数据量少）
    sleep_data_low = sleep_data[:10]  # 只有10天数据
    hrv_data_low = hrv_data[:5]       # 只有5个HRV测量
    
    result_low = compute_personal_baseline('low_quality_user', sleep_data_low, hrv_data_low)
    print(f"低质量数据评分: {result_low['data_quality']:.3f}")
    print(f"计算状态: {result_low['status']}")
    if result_low.get('validation'):
        issues = result_low['validation'].get('issues', [])
        if issues:
            print(f"数据质量问题: {', '.join(issues)}")

def demo_direct_model_usage():
    """演示直接使用数据模型"""
    print("\n=== 直接使用数据模型示例 ===")
    
    from baseline.calculator import PersonalBaselineCalculator
    
    # 1. 创建数据记录
    sleep_records = []
    for i in range(20):
        date = datetime.now() - timedelta(days=i)
        record = SleepRecord(
            date=date,
            sleep_duration_hours=7.0 + i * 0.1,
            sleep_efficiency=0.85 + i * 0.002,
            deep_sleep_ratio=0.15,
            rem_sleep_ratio=0.22
        )
        sleep_records.append(record)
    
    hrv_records = []
    for i in range(15):
        timestamp = datetime.now() - timedelta(days=i * 2)
        record = HRVRecord(
            timestamp=timestamp,
            sdnn_value=45.0 + i * 1.5,
            measurement_context='morning'
        )
        hrv_records.append(record)
    
    # 2. 直接计算基线
    calculator = PersonalBaselineCalculator()
    baseline_result = calculator.calculate_baseline('direct_user', sleep_records, hrv_records)
    
    print(f"直接计算结果:")
    print(f"  用户ID: {baseline_result.user_id}")
    print(f"  基线有效性: {baseline_result.is_valid()}")
    print(f"  质量评分: {baseline_result.data_quality_score}")
    
    # 3. 获取调整因子
    adjustment_factors = calculator.get_baseline_adjustment_factors(baseline_result)
    print(f"  调整因子: {adjustment_factors}")

if __name__ == '__main__':
    # 运行所有示例
    demo_basic_calculation()
    demo_file_storage() 
    demo_quality_assessment()
    demo_direct_model_usage()
    
    print("\n=== 示例运行完成 ===")
    print("您可以查看生成的 demo_baseline_data/ 目录中的基线数据文件")