#!/usr/bin/env python3
"""
Baseline模块数据格式示例

展示从HealthKit数据输入到Readiness模块输出的完整数据流转格式。
"""

from datetime import datetime, timedelta
import json

def get_healthkit_input_example():
    """HealthKit数据输入格式示例
    
    这是从iOS HealthKit获取的原始数据格式，需要发送给Baseline服务
    """
    
    # 模拟30天的睡眠数据
    sleep_records = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        sleep_records.append({
            "date": date.strftime("%Y-%m-%dT00:00:00Z"),
            "sleep_duration_hours": round(7.0 + (i % 3 - 1) * 0.5, 1),  # 6.5-7.5小时变化
            "sleep_efficiency": round(0.80 + (i % 5) * 0.02, 2),         # 0.80-0.88效率
            "deep_sleep_minutes": 80 + (i % 4) * 10,                     # 80-110分钟深睡眠
            "rem_sleep_minutes": 100 + (i % 3) * 15,                     # 100-130分钟REM
            "total_sleep_minutes": int((7.0 + (i % 3 - 1) * 0.5) * 60), # 总睡眠分钟数
            "restorative_ratio": round((80 + (i % 4) * 10 + 100 + (i % 3) * 15) / ((7.0 + (i % 3 - 1) * 0.5) * 60), 3)
        })
    
    # 模拟40个HRV数据点
    hrv_records = []
    for i in range(40):
        timestamp = base_date + timedelta(days=i//2, hours=8)  # 每两天一个测量
        hrv_records.append({
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sdnn_value": round(35.0 + (i % 7 - 3) * 3.5, 1)  # 24.5-45.5ms范围
        })
    
    return {
        "user_id": "user_123",
        "sleep_records": sleep_records,
        "hrv_records": hrv_records
    }

def get_baseline_output_example():
    """Baseline服务输出格式示例
    
    这是Baseline服务计算后返回的结果，需要存储到数据库
    """
    
    return {
        "user_id": "user_123",
        "baseline_data": {
            # 睡眠基线
            "sleep_baseline_hours": 7.2,      # 个人平均睡眠时长
            "sleep_baseline_eff": 0.85,       # 个人平均睡眠效率
            "rest_baseline_ratio": 0.32,      # 恢复性睡眠比例基线
            
            # HRV基线
            "hrv_baseline_mu": 38.5,          # HRV均值 (SDNN ms)
            "hrv_baseline_sd": 8.2,           # HRV标准差
            
            # 可选：更多基线参数
            "hrv_rmssd_28day_avg": 35.2,      # 28天RMSSD均值
            "hrv_rmssd_28day_sd": 7.8,        # 28天RMSSD标准差
            "hrv_rmssd_21day_avg": 36.1,      # 21天RMSSD均值  
            "hrv_rmssd_21day_sd": 7.5         # 21天RMSSD标准差
        },
        "quality_metrics": {
            "data_quality_score": 0.87,       # 数据质量评分 (0-1)
            "sample_days_sleep": 28,          # 有效睡眠记录天数
            "sample_days_hrv": 35,            # 有效HRV记录数量
            "completeness_sleep": 0.93,       # 睡眠数据完整度
            "completeness_hrv": 0.88          # HRV数据完整度
        },
        "adjustment_factors": {
            # 基于个人基线的调整因子
            "sleep_duration_factor": 1.0,     # 睡眠时长调整因子
            "hrv_sensitivity_factor": 1.1     # HRV变化敏感度因子
        },
        "metadata": {
            "calculated_at": "2024-01-15T10:30:00Z",
            "expires_at": "2024-01-22T10:30:00Z",    # 7天后需更新
            "algorithm_version": "1.0.0",
            "data_source": "healthkit"
        }
    }

def get_readiness_input_example():
    """Readiness模块输入格式示例
    
    这是mapping.py需要接收的完整数据格式，包含当天数据+个人基线
    """
    
    return {
        # 当天的健康数据
        "sleep_duration_hours": 6.8,
        "sleep_efficiency": 0.82,
        "hrv_rmssd_today": 35.0,
        "hrv_rmssd_3day_avg": 36.2,
        "hrv_rmssd_7day_avg": 37.1,
        
        # 恢复性睡眠数据
        "deep_sleep_ratio": 0.12,
        "rem_sleep_ratio": 0.22,
        "restorative_ratio": 0.34,
        
        # 个人基线数据 (从数据库获取)
        "sleep_baseline_hours": 7.2,
        "sleep_baseline_eff": 0.85,
        "rest_baseline_ratio": 0.32,
        "hrv_baseline_mu": 38.5,
        "hrv_baseline_sd": 8.2,
        
        # 可选的额外基线数据
        "hrv_rmssd_28day_avg": 35.2,
        "hrv_rmssd_28day_sd": 7.8,
        
        # Hooper量表数据
        "fatigue_hooper": 3,
        "soreness_hooper": 2,
        "stress_hooper": 4,
        "sleep_hooper": 3,
        
        # 布尔值日志数据
        "is_sick": False,
        "is_injured": False,
        "high_stress_event_today": False,
        "meditation_done_today": True
    }

def get_api_integration_example():
    """API集成示例
    
    展示如何在实际API中处理这些数据格式
    """
    
    # 1. 接收HealthKit数据的API
    healthkit_api_request = {
        "method": "POST",
        "url": "/api/v1/baseline/calculate",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer user_token"
        },
        "body": get_healthkit_input_example()
    }
    
    # 2. Baseline服务返回结果
    baseline_api_response = {
        "status": "success",
        "message": "Baseline calculated successfully", 
        "data": get_baseline_output_example()
    }
    
    # 3. Readiness计算API请求
    readiness_api_request = {
        "method": "POST", 
        "url": "/api/v1/readiness/calculate",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer user_token"
        },
        "body": get_readiness_input_example()
    }
    
    # 4. Readiness计算结果
    readiness_api_response = {
        "status": "success",
        "data": {
            "user_id": "user_123", 
            "readiness_score": 68,
            "readiness_level": "medium",
            "factors": {
                "sleep_performance": "medium",  # 基于个人基线: 6.8h < 7.2h基线
                "restorative_sleep": "high",    # 0.34 > 0.32基线+0.02
                "hrv_trend": "slight_decline",  # 35.0 vs 38.5±8.2基线
                "subjective_fatigue": "medium", # Hooper评分3
                "subjective_stress": "high"     # Hooper评分4
            },
            "recommendations": [
                "今晚试着早睡30分钟，达到你的个人基线7.2小时",
                "你的恢复性睡眠表现很好，继续保持",
                "HRV略有下降，注意压力管理"
            ]
        }
    }
    
    return {
        "healthkit_request": healthkit_api_request,
        "baseline_response": baseline_api_response, 
        "readiness_request": readiness_api_request,
        "readiness_response": readiness_api_response
    }

def demonstrate_data_flow():
    """演示完整的数据流转过程"""
    
    print("🔄 Baseline模块数据格式完整示例")
    print("=" * 60)
    
    # 1. HealthKit输入数据
    print("\n1️⃣ HealthKit数据 → Baseline服务")
    print("-" * 40)
    healthkit_data = get_healthkit_input_example()
    print(f"📱 用户ID: {healthkit_data['user_id']}")
    print(f"📊 睡眠记录: {len(healthkit_data['sleep_records'])}天")
    print(f"💓 HRV记录: {len(healthkit_data['hrv_records'])}个")
    print("\n📋 数据样本:")
    print(f"  睡眠: {healthkit_data['sleep_records'][0]['sleep_duration_hours']}h, 效率{healthkit_data['sleep_records'][0]['sleep_efficiency']}")
    print(f"  HRV: {healthkit_data['hrv_records'][0]['sdnn_value']}ms")
    
    # 2. Baseline计算结果
    print("\n2️⃣ Baseline服务 → 数据库存储")
    print("-" * 40)
    baseline_result = get_baseline_output_example()
    baseline_data = baseline_result['baseline_data']
    quality = baseline_result['quality_metrics']
    
    print(f"✅ 基线计算完成，质量评分: {quality['data_quality_score']}")
    print(f"📏 睡眠基线: {baseline_data['sleep_baseline_hours']}h, 效率{baseline_data['sleep_baseline_eff']}")
    print(f"💓 HRV基线: {baseline_data['hrv_baseline_mu']}±{baseline_data['hrv_baseline_sd']}ms")
    print(f"😴 恢复性睡眠基线: {baseline_data['rest_baseline_ratio']*100:.0f}%")
    
    # 3. Readiness输入格式
    print("\n3️⃣ 数据库 → Readiness模块")
    print("-" * 40)
    readiness_data = get_readiness_input_example()
    print(f"🌙 当天睡眠: {readiness_data['sleep_duration_hours']}h (基线{readiness_data['sleep_baseline_hours']}h)")
    print(f"💓 当天HRV: {readiness_data['hrv_rmssd_today']}ms (基线{readiness_data['hrv_baseline_mu']}ms)")
    print(f"😴 恢复性睡眠: {readiness_data['restorative_ratio']*100:.0f}% (基线{readiness_data['rest_baseline_ratio']*100:.0f}%)")
    
    # 4. 个性化判断示例
    print("\n4️⃣ 个性化阈值判断")
    print("-" * 40)
    
    # 睡眠判断
    sleep_actual = readiness_data['sleep_duration_hours']
    sleep_baseline = readiness_data['sleep_baseline_hours']
    sleep_good_threshold = min(9.0, max(7.0, sleep_baseline + 1.0))  # 基线+1小时
    sleep_med_threshold = min(8.0, max(6.0, sleep_baseline - 0.5))   # 基线-0.5小时
    
    if sleep_actual >= sleep_good_threshold:
        sleep_rating = "good"
    elif sleep_actual >= sleep_med_threshold:
        sleep_rating = "medium"
    else:
        sleep_rating = "poor"
    
    print(f"🌙 睡眠评估: {sleep_actual}h → {sleep_rating}")
    print(f"   good阈值: ≥{sleep_good_threshold:.1f}h (基线+1h)")
    print(f"   medium阈值: ≥{sleep_med_threshold:.1f}h (基线-0.5h)")
    
    # HRV判断
    hrv_today = readiness_data['hrv_rmssd_today']
    hrv_mu = readiness_data['hrv_baseline_mu']
    hrv_sd = readiness_data['hrv_baseline_sd']
    hrv_z_score = (hrv_today - hrv_mu) / hrv_sd
    
    if hrv_z_score >= 0.5:
        hrv_trend = "rising"
    elif hrv_z_score <= -1.5:
        hrv_trend = "significant_decline"
    elif hrv_z_score <= -0.5:
        hrv_trend = "slight_decline"
    else:
        hrv_trend = "stable"
    
    print(f"💓 HRV趋势: {hrv_today}ms → {hrv_trend}")
    print(f"   Z分数: {hrv_z_score:.2f} (基于{hrv_mu}±{hrv_sd}ms)")
    
    print(f"\n🎯 个性化优势:")
    print(f"   • 同样6.8小时睡眠，不同基线用户评级不同")
    print(f"   • 基线7.2h用户: 6.8h=medium (略低于基线)")
    print(f"   • 基线6.5h用户: 6.8h=good (超过基线)")

if __name__ == '__main__':
    # 演示完整数据流
    demonstrate_data_flow()
    
    # 输出完整JSON格式供参考
    print(f"\n📄 完整JSON格式参考")
    print("=" * 60)
    
    print(f"\n📱 HealthKit输入格式:")
    print(json.dumps(get_healthkit_input_example(), indent=2, ensure_ascii=False))
    
    print(f"\n💾 Baseline输出格式:")  
    print(json.dumps(get_baseline_output_example(), indent=2, ensure_ascii=False))
    
    print(f"\n🎯 Readiness输入格式:")
    print(json.dumps(get_readiness_input_example(), indent=2, ensure_ascii=False))