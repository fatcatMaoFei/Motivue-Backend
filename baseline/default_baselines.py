#!/usr/bin/env python3
"""默认基线配置

为数据不足(<30天)的用户提供三种类型的默认基线。
基于问卷或用户特征分类后使用。
"""

from typing import Dict, Any, Optional
from .models import BaselineResult

# 三种睡眠类型的默认基线配置
DEFAULT_BASELINES = {
    "short_sleeper": {
        # 短睡眠型用户（通常6-7小时就够，效率高）
        "sleep_baseline_hours": 6.5,
        "sleep_baseline_eff": 0.90,
        "rest_baseline_ratio": 0.30,
        "hrv_baseline_mu": 35.0,
        "hrv_baseline_sd": 7.0,
        "description": "短睡眠高效型",
        "characteristics": ["睡眠需求6-7小时", "入睡快", "睡眠效率高", "早起不困难"]
    },
    
    "normal_sleeper": {  
        # 标准睡眠型用户（需要7-8小时）
        "sleep_baseline_hours": 7.5,
        "sleep_baseline_eff": 0.85,
        "rest_baseline_ratio": 0.32,
        "hrv_baseline_mu": 40.0,
        "hrv_baseline_sd": 8.0,
        "description": "标准睡眠型",
        "characteristics": ["睡眠需求7-8小时", "标准入睡时间", "中等睡眠效率", "正常起床"]
    },
    
    "long_sleeper": {
        # 长睡眠型用户（需要8-9小时才够）
        "sleep_baseline_hours": 8.5,
        "sleep_baseline_eff": 0.82,
        "rest_baseline_ratio": 0.28,
        "hrv_baseline_mu": 42.0,
        "hrv_baseline_sd": 9.0,
        "description": "长睡眠型",
        "characteristics": ["睡眠需求8-9小时", "入睡较慢", "需要更多恢复时间", "早起困难"]
    }
}

# HRV的三种基线类型（按年龄/体能水平）
HRV_BASELINES = {
    "low_hrv": {
        # 低HRV基线（年龄较大、体能一般）
        "hrv_baseline_mu": 28.0,
        "hrv_baseline_sd": 6.0,
        "description": "低HRV型",
        "age_range": "45+岁或体能一般"
    },
    
    "normal_hrv": {
        # 标准HRV基线（中等年龄、中等体能）
        "hrv_baseline_mu": 40.0, 
        "hrv_baseline_sd": 8.0,
        "description": "标准HRV型",
        "age_range": "25-45岁，正常体能"
    },
    
    "high_hrv": {
        # 高HRV基线（年轻、体能好）
        "hrv_baseline_mu": 55.0,
        "hrv_baseline_sd": 10.0,
        "description": "高HRV型", 
        "age_range": "25岁以下或体能很好"
    }
}

def get_default_baseline(sleeper_type: str, hrv_type: str = "normal_hrv") -> Dict[str, Any]:
    """获取指定类型的默认基线
    
    Args:
        sleeper_type: 睡眠类型 ("short_sleeper", "normal_sleeper", "long_sleeper")
        hrv_type: HRV类型 ("low_hrv", "normal_hrv", "high_hrv")
    
    Returns:
        默认基线数据字典
    """
    
    if sleeper_type not in DEFAULT_BASELINES:
        sleeper_type = "normal_sleeper"  # 默认使用标准型
    
    if hrv_type not in HRV_BASELINES:
        hrv_type = "normal_hrv"  # 默认使用标准HRV
    
    sleep_config = DEFAULT_BASELINES[sleeper_type]
    hrv_config = HRV_BASELINES[hrv_type]
    
    # 合并睡眠和HRV基线
    baseline = {
        "sleep_baseline_hours": sleep_config["sleep_baseline_hours"],
        "sleep_baseline_eff": sleep_config["sleep_baseline_eff"],
        "rest_baseline_ratio": sleep_config["rest_baseline_ratio"],
        "hrv_baseline_mu": hrv_config["hrv_baseline_mu"],
        "hrv_baseline_sd": hrv_config["hrv_baseline_sd"],
    }
    
    return baseline

def create_default_baseline_result(user_id: str, sleeper_type: str, hrv_type: str = "normal_hrv") -> BaselineResult:
    """创建默认基线的BaselineResult对象
    
    Args:
        user_id: 用户ID
        sleeper_type: 睡眠类型
        hrv_type: HRV类型
    
    Returns:
        BaselineResult对象
    """
    
    baseline_data = get_default_baseline(sleeper_type, hrv_type)
    
    # 创建BaselineResult对象
    result = BaselineResult(
        user_id=user_id,
        sleep_baseline_hours=baseline_data["sleep_baseline_hours"],
        sleep_baseline_eff=baseline_data["sleep_baseline_eff"], 
        rest_baseline_ratio=baseline_data["rest_baseline_ratio"],
        hrv_baseline_mu=baseline_data["hrv_baseline_mu"],
        hrv_baseline_sd=baseline_data["hrv_baseline_sd"],
        data_quality_score=0.8,  # 默认基线质量设为0.8
        sample_days_sleep=0,     # 标记为默认基线
        sample_days_hrv=0,
        calculation_version="default_v1.0"
    )
    
    return result

def get_all_baseline_types():
    """获取所有可用的基线类型，用于问卷选项"""
    
    return {
        "sleep_types": {
            "short_sleeper": {
                "name": "短睡眠型",
                "description": "通常6-7小时睡眠就够，入睡快，效率高",
                "sleep_hours": "6-7小时"
            },
            "normal_sleeper": {
                "name": "标准睡眠型", 
                "description": "需要7-8小时睡眠，中等睡眠效率",
                "sleep_hours": "7-8小时"
            },
            "long_sleeper": {
                "name": "长睡眠型",
                "description": "需要8-9小时睡眠，需要更多恢复时间",
                "sleep_hours": "8-9小时"
            }
        },
        
        "hrv_types": {
            "low_hrv": {
                "name": "低HRV型",
                "description": "适合45岁以上或体能一般的用户",
                "baseline_range": "22-34ms"
            },
            "normal_hrv": {
                "name": "标准HRV型",
                "description": "适合25-45岁，正常体能用户", 
                "baseline_range": "32-48ms"
            },
            "high_hrv": {
                "name": "高HRV型",
                "description": "适合25岁以下或体能很好的用户",
                "baseline_range": "45-65ms"
            }
        }
    }

def demo_default_baselines():
    """演示所有默认基线配置"""
    
    print("🎯 默认基线配置演示")
    print("=" * 60)
    
    print("💤 睡眠类型基线:")
    for sleep_type, config in DEFAULT_BASELINES.items():
        print(f"\n📊 {config['description']} ({sleep_type}):")
        print(f"   睡眠时长基线: {config['sleep_baseline_hours']}小时")
        print(f"   睡眠效率基线: {config['sleep_baseline_eff']:.1%}")
        print(f"   恢复性睡眠基线: {config['rest_baseline_ratio']:.1%}")
        print(f"   特征: {', '.join(config['characteristics'])}")
    
    print(f"\n💓 HRV类型基线:")
    for hrv_type, config in HRV_BASELINES.items():
        print(f"\n📈 {config['description']} ({hrv_type}):")
        print(f"   HRV基线: {config['hrv_baseline_mu']:.0f}±{config['hrv_baseline_sd']:.0f}ms")
        print(f"   适用人群: {config['age_range']}")
    
    print(f"\n🔄 组合示例:")
    combinations = [
        ("short_sleeper", "high_hrv", "年轻短睡眠型"),
        ("normal_sleeper", "normal_hrv", "标准用户"),
        ("long_sleeper", "low_hrv", "年长长睡眠型")
    ]
    
    for sleep_type, hrv_type, desc in combinations:
        baseline = get_default_baseline(sleep_type, hrv_type)
        print(f"\n🎭 {desc}:")
        print(f"   睡眠: {baseline['sleep_baseline_hours']}h, 效率{baseline['sleep_baseline_eff']:.1%}")
        print(f"   HRV: {baseline['hrv_baseline_mu']:.0f}±{baseline['hrv_baseline_sd']:.0f}ms")
    
    # 展示阈值计算效果
    print(f"\n🧮 阈值计算效果演示:")
    for sleep_type in ["short_sleeper", "normal_sleeper", "long_sleeper"]:
        config = DEFAULT_BASELINES[sleep_type]
        baseline_hours = config['sleep_baseline_hours']
        
        good_threshold = min(9.0, max(7.0, baseline_hours + 1.0))
        med_threshold = min(8.0, max(6.0, baseline_hours - 0.5))
        
        print(f"\n   {config['description']} (基线{baseline_hours}h):")
        print(f"   → good阈值: ≥{good_threshold:.1f}h")
        print(f"   → medium阈值: ≥{med_threshold:.1f}h")

if __name__ == '__main__':
    demo_default_baselines()