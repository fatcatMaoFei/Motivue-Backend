#!/usr/bin/env python3
"""
mapping.py集成格式说明

详细说明readiness/mapping.py需要的基线数据格式和字段对应关系。
"""

def get_mapping_required_fields():
    """mapping.py需要的基线字段说明"""
    
    return {
        "required_baseline_fields": {
            # 睡眠基线字段 - 对应mapping.py中的mu_dur, mu_eff变量
            "sleep_baseline_hours": {
                "type": "float",
                "description": "个人睡眠时长基线，单位小时",
                "range": "5.0-10.0",
                "mapping_variable": "mu_dur",
                "usage": "计算睡眠时长good/medium阈值",
                "example": 7.2
            },
            "sleep_baseline_eff": {
                "type": "float", 
                "description": "个人睡眠效率基线，范围0-1",
                "range": "0.60-0.98",
                "mapping_variable": "mu_eff",
                "usage": "计算睡眠效率good/medium阈值",
                "example": 0.85
            },
            
            # 恢复性睡眠基线
            "rest_baseline_ratio": {
                "type": "float",
                "description": "恢复性睡眠比例基线，深睡+REM占比",
                "range": "0.20-0.50",
                "mapping_variable": "mu_rest", 
                "usage": "计算恢复性睡眠high/medium阈值",
                "example": 0.32
            },
            
            # HRV基线字段
            "hrv_baseline_mu": {
                "type": "float",
                "description": "个人HRV均值基线，SDNN单位ms",
                "range": "15.0-80.0",
                "mapping_variable": "mu",
                "usage": "HRV Z分数计算",
                "example": 38.5
            },
            "hrv_baseline_sd": {
                "type": "float",
                "description": "个人HRV标准差",
                "range": "3.0-20.0", 
                "mapping_variable": "sd",
                "usage": "HRV Z分数计算",
                "example": 8.2
            }
        },
        
        "optional_baseline_fields": {
            # 可选的额外HRV基线字段
            "hrv_rmssd_28day_avg": {
                "type": "float",
                "description": "28天RMSSD均值，备选HRV基线",
                "mapping_variable": "mu (fallback)",
                "usage": "当hrv_baseline_mu不存在时使用",
                "example": 35.2
            },
            "hrv_rmssd_28day_sd": {
                "type": "float", 
                "description": "28天RMSSD标准差，备选HRV基线",
                "mapping_variable": "sd (fallback)",
                "usage": "当hrv_baseline_sd不存在时使用",
                "example": 7.8
            },
            "hrv_rmssd_21day_avg": {
                "type": "float",
                "description": "21天RMSSD均值，备选HRV基线",
                "mapping_variable": "mu (fallback)",
                "usage": "当28天数据不足时使用",
                "example": 36.1
            },
            "hrv_rmssd_21day_sd": {
                "type": "float",
                "description": "21天RMSSD标准差，备选HRV基线", 
                "mapping_variable": "sd (fallback)",
                "usage": "当28天数据不足时使用",
                "example": 7.5
            }
        }
    }

def get_mapping_threshold_logic():
    """mapping.py中的阈值计算逻辑说明"""
    
    return {
        "sleep_duration_thresholds": {
            "algorithm": "科学化个性化阈值",
            "good_threshold": {
                "formula": "min(9.0, max(7.0, mu_dur + 1.0))",
                "description": "基线+1小时，7-9小时保护范围",
                "code_location": "mapping.py:61",
                "examples": [
                    {"baseline": 6.5, "threshold": 7.0, "note": "下限保护"},
                    {"baseline": 7.2, "threshold": 8.2, "note": "个性化"},
                    {"baseline": 8.8, "threshold": 9.0, "note": "上限保护"}
                ]
            },
            "medium_threshold": {
                "formula": "min(8.0, max(6.0, mu_dur - 0.5))", 
                "description": "基线-0.5小时，6-8小时保护范围",
                "code_location": "mapping.py:63",
                "examples": [
                    {"baseline": 5.5, "threshold": 6.0, "note": "下限保护"},
                    {"baseline": 7.2, "threshold": 6.7, "note": "个性化"},
                    {"baseline": 8.8, "threshold": 8.0, "note": "上限保护"}
                ]
            }
        },
        
        "sleep_efficiency_thresholds": {
            "good_threshold": {
                "formula": "max(0.85, mu_eff - 0.05)",
                "description": "基线-5%，最低85%",
                "code_location": "mapping.py:62"
            },
            "medium_threshold": {
                "formula": "max(0.75, mu_eff - 0.10)",
                "description": "基线-10%，最低75%", 
                "code_location": "mapping.py:64"
            }
        },
        
        "restorative_sleep_thresholds": {
            "high_threshold": {
                "formula": "min(0.55, max(0.35, mu_rest + 0.10))",
                "description": "基线+10%，35-55%保护范围",
                "code_location": "mapping.py:99"
            },
            "medium_threshold": {
                "formula": "max(0.25, mu_rest - 0.05)",
                "description": "基线-5%，最低25%",
                "code_location": "mapping.py:100"
            }
        },
        
        "hrv_trend_calculation": {
            "z_score_method": {
                "formula": "z = (today - mu) / sd",
                "description": "使用个人基线计算Z分数",
                "code_location": "mapping.py:134",
                "thresholds": {
                    "rising": "z >= 0.5", 
                    "stable": "-0.5 < z < 0.5",
                    "slight_decline": "-1.5 < z <= -0.5",
                    "significant_decline": "z <= -1.5"
                }
            },
            "fallback_method": {
                "formula": "delta = (rmssd3 - rmssd7) / rmssd7",
                "description": "当基线不存在时使用3天vs7天对比",
                "code_location": "mapping.py:158"
            }
        }
    }

def get_payload_examples():
    """payload数据格式示例"""
    
    return {
        "complete_payload": {
            "description": "包含基线数据的完整payload",
            "data": {
                # 当天实际数据
                "sleep_duration_hours": 6.8,
                "sleep_efficiency": 0.82,
                "hrv_rmssd_today": 35.0,
                "restorative_ratio": 0.34,
                
                # 个人基线数据 (从baseline服务获取)
                "sleep_baseline_hours": 7.2,
                "sleep_baseline_eff": 0.85, 
                "rest_baseline_ratio": 0.32,
                "hrv_baseline_mu": 38.5,
                "hrv_baseline_sd": 8.2,
                
                # 其他readiness数据
                "fatigue_hooper": 3,
                "stress_hooper": 4,
                "is_sick": False,
                "is_injured": False
            }
        },
        
        "no_baseline_payload": {
            "description": "无基线数据时的payload（使用默认阈值）",
            "data": {
                "sleep_duration_hours": 6.8,
                "sleep_efficiency": 0.82,
                "hrv_rmssd_today": 35.0,
                "hrv_rmssd_7day_avg": 37.1,  # 用于HRV趋势计算
                "restorative_ratio": 0.34,
                "fatigue_hooper": 3,
                "stress_hooper": 4
            }
        },
        
        "partial_baseline_payload": {
            "description": "部分基线数据的payload",
            "data": {
                "sleep_duration_hours": 6.8,
                "sleep_efficiency": 0.82,
                "sleep_baseline_hours": 7.2,  # 只有睡眠基线
                "hrv_rmssd_today": 35.0,
                "hrv_rmssd_7day_avg": 37.1,   # HRV用fallback方法
                "restorative_ratio": 0.34
            }
        }
    }

def demonstrate_mapping_integration():
    """演示mapping.py集成过程"""
    
    print("🔗 mapping.py基线集成说明")
    print("=" * 50)
    
    # 1. 必需字段说明
    print("\n1️⃣ 必需的基线字段")
    print("-" * 30)
    
    required_fields = get_mapping_required_fields()["required_baseline_fields"]
    
    for field_name, field_info in required_fields.items():
        print(f"📊 {field_name}:")
        print(f"   类型: {field_info['type']}")
        print(f"   描述: {field_info['description']}")
        print(f"   范围: {field_info['range']}")
        print(f"   变量: {field_info['mapping_variable']}")
        print(f"   示例: {field_info['example']}")
        print()
    
    # 2. 阈值计算逻辑
    print("2️⃣ 阈值计算逻辑")
    print("-" * 30)
    
    threshold_logic = get_mapping_threshold_logic()
    
    print("🌙 睡眠时长阈值:")
    good_info = threshold_logic["sleep_duration_thresholds"]["good_threshold"]
    med_info = threshold_logic["sleep_duration_thresholds"]["medium_threshold"]
    
    print(f"   good: {good_info['formula']}")
    print(f"   medium: {med_info['formula']}")
    
    print("\n📊 示例计算:")
    for example in good_info["examples"]:
        baseline = example["baseline"]
        good_threshold = min(9.0, max(7.0, baseline + 1.0))
        med_threshold = min(8.0, max(6.0, baseline - 0.5))
        print(f"   基线{baseline}h → good≥{good_threshold}h, medium≥{med_threshold}h ({example['note']})")
    
    # 3. 实际使用示例
    print(f"\n3️⃣ 实际使用示例")
    print("-" * 30)
    
    examples = get_payload_examples()
    
    # 模拟mapping.py的处理过程
    payload = examples["complete_payload"]["data"]
    
    print(f"📥 输入数据:")
    print(f"   当天睡眠: {payload['sleep_duration_hours']}h, 效率{payload['sleep_efficiency']}")
    print(f"   个人基线: {payload['sleep_baseline_hours']}h, 效率{payload['sleep_baseline_eff']}")
    
    # 计算阈值
    mu_dur = payload.get('sleep_baseline_hours')
    mu_eff = payload.get('sleep_baseline_eff')
    
    if mu_dur and mu_eff:
        good_dur_threshold = min(9.0, max(7.0, mu_dur + 1.0))
        good_eff_threshold = max(0.85, mu_eff - 0.05)
        med_dur_threshold = min(8.0, max(6.0, mu_dur - 0.5))
        med_eff_threshold = max(0.75, mu_eff - 0.10)
        
        print(f"\n🧮 阈值计算:")
        print(f"   good阈值: ≥{good_dur_threshold:.1f}h + ≥{good_eff_threshold:.2f}效率")
        print(f"   medium阈值: ≥{med_dur_threshold:.1f}h + ≥{med_eff_threshold:.2f}效率")
        
        # 判断结果
        actual_dur = payload['sleep_duration_hours']
        actual_eff = payload['sleep_efficiency']
        
        if actual_dur >= good_dur_threshold and actual_eff >= good_eff_threshold:
            result = "good"
        elif actual_dur >= med_dur_threshold and actual_eff >= med_eff_threshold:
            result = "medium"
        else:
            result = "poor"
        
        print(f"\n🎯 判断结果:")
        print(f"   {actual_dur}h + {actual_eff}效率 → {result}")
        
        # 解释个性化优势
        print(f"\n💡 个性化优势:")
        default_good = 7.0
        if good_dur_threshold != default_good:
            diff = good_dur_threshold - default_good
            print(f"   基于个人基线，good标准调整了{diff:+.1f}h")
            print(f"   标准用户需要{default_good}h，你需要{good_dur_threshold:.1f}h")

def get_integration_checklist():
    """集成检查清单"""
    
    return {
        "数据库设计": [
            "✅ user_baselines表包含所有必需字段",
            "✅ 基线数据有过期时间控制",
            "✅ 支持基线版本管理",
            "✅ 数据质量评分存储"
        ],
        "API设计": [
            "✅ POST /baseline/calculate 接收HealthKit数据",
            "✅ GET /baseline/{user_id} 获取用户基线",
            "✅ POST /readiness/calculate 自动注入基线数据",
            "✅ 基线过期自动提示重新计算"
        ],
        "数据流转": [
            "✅ HealthKit → Baseline服务 数据格式转换",
            "✅ Baseline → 数据库 结果存储",
            "✅ 数据库 → Readiness 基线注入",
            "✅ mapping.py 正确解析基线字段"
        ],
        "错误处理": [
            "✅ 基线数据不足时的fallback逻辑",
            "✅ 基线过期时的默认阈值",
            "✅ 异常基线值的安全边界保护",
            "✅ 数据质量评分的使用决策"
        ],
        "性能优化": [
            "✅ 基线数据缓存机制",
            "✅ 增量更新vs完整重算",
            "✅ 批量用户基线计算",
            "✅ 数据库查询优化"
        ]
    }

if __name__ == '__main__':
    # 运行演示
    demonstrate_mapping_integration()
    
    # 输出检查清单
    print(f"\n📋 集成检查清单")
    print("=" * 50)
    
    checklist = get_integration_checklist()
    
    for category, items in checklist.items():
        print(f"\n📌 {category}:")
        for item in items:
            print(f"   {item}")
    
    # 输出JSON格式参考
    print(f"\n📄 payload格式参考")
    print("=" * 50)
    
    import json
    examples = get_payload_examples()
    
    for example_name, example_info in examples.items():
        print(f"\n{example_info['description']}:")
        print(json.dumps(example_info['data'], indent=2, ensure_ascii=False))