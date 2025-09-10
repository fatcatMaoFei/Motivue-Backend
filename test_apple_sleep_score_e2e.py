#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""端到端测试：苹果睡眠评分完整准备度计算"""

from readiness.service import compute_readiness_from_payload

def test_apple_sleep_score_e2e():
    """测试苹果睡眠评分的端到端准备度计算"""
    
    print("=== 苹果睡眠评分端到端测试 ===\n")
    
    # 测试场景1: 使用苹果评分计算准备度
    print("1. 使用苹果评分计算准备度")
    apple_payload = {
        "user_id": "test_user_apple",
        "date": "2024-09-10",
        "gender": "男性",
        "apple_sleep_score": 75,  # good级别
        "previous_state_probs": {
            "Peak": 0.2,
            "Well-adapted": 0.5,
            "FOR": 0.2,
            "Acute Fatigue": 0.05,
            "NFOR": 0.04,
            "OTS": 0.01
        },
        "training_load": "中",
        "recent_training_loads": ["低", "中", "中", "高", "中", "低", "无"],
        "journal": {
            "alcohol_consumed": False,
            "late_caffeine": False,
            "screen_before_bed": True,
            "late_meal": False,
            "is_sick": False,
            "is_injured": False
        },
        "objective": {
            "hrv_trend": "stable",
            "restorative_sleep": "medium"
        },
        "hooper": {
            "fatigue": 3,
            "soreness": 2,
            "stress": 3,
            "sleep": 3
        }
    }
    
    result1 = compute_readiness_from_payload(apple_payload)
    print(f"输入: 苹果评分75分")
    print(f"准备度分数: {result1['final_readiness_score']}")
    print(f"诊断: {result1['final_diagnosis']}")
    print(f"使用的evidence: {list(result1['evidence_pool'].keys())}")
    print(f"苹果评分在evidence中: {'apple_sleep_score' in result1['evidence_pool']}")
    print(f"传统睡眠评分在evidence中: {'sleep_performance' in result1['evidence_pool']}")
    print()
    
    # 测试场景2: 对比传统睡眠评分计算准备度
    print("2. 使用传统睡眠评分计算准备度（对比）")
    traditional_payload = apple_payload.copy()
    del traditional_payload["apple_sleep_score"]  # 移除苹果评分
    traditional_payload["objective"] = {
        "sleep_performance_state": "good",  # 对应75分的good级别
        "restorative_sleep": "medium",
        "hrv_trend": "stable"
    }
    
    result2 = compute_readiness_from_payload(traditional_payload)
    print(f"输入: 传统睡眠评分good")
    print(f"准备度分数: {result2['final_readiness_score']}")
    print(f"诊断: {result2['final_diagnosis']}")
    print(f"使用的evidence: {list(result2['evidence_pool'].keys())}")
    print(f"苹果评分在evidence中: {'apple_sleep_score' in result2['evidence_pool']}")
    print(f"传统睡眠评分在evidence中: {'sleep_performance' in result2['evidence_pool']}")
    print()
    
    # 测试场景3: 苹果评分excellent vs good的对比
    print("3. 苹果评分excellent vs good对比")
    excellent_payload = apple_payload.copy()
    excellent_payload["apple_sleep_score"] = 85  # excellent级别
    
    result3 = compute_readiness_from_payload(excellent_payload)
    print(f"苹果评分85分(excellent)")
    print(f"准备度分数: {result3['final_readiness_score']}")
    print(f"诊断: {result3['final_diagnosis']}")
    print()
    
    print(f"苹果评分75分(good)")
    print(f"准备度分数: {result1['final_readiness_score']}")
    print(f"诊断: {result1['final_diagnosis']}")
    print()
    
    score_diff = result3['final_readiness_score'] - result1['final_readiness_score']
    print(f"评分差异: excellent比good高 {score_diff:.2f} 分")
    print()
    
    # 测试场景4: 同时有两套数据，验证优先级
    print("4. 同时有苹果评分和传统数据，验证苹果评分优先")
    mixed_payload = apple_payload.copy()
    mixed_payload["apple_sleep_score"] = 78  # good级别
    mixed_payload["objective"] = {
        "sleep_performance_state": "poor",  # 故意设置冲突的评分
        "restorative_sleep": "medium",
        "hrv_trend": "stable"
    }
    
    result4 = compute_readiness_from_payload(mixed_payload)
    print(f"输入: 苹果78分(good) + 传统评分(poor)")
    print(f"准备度分数: {result4['final_readiness_score']}")
    print(f"诊断: {result4['final_diagnosis']}")
    print(f"evidence池: {result4['evidence_pool']}")
    print(f"苹果评分胜出: {'apple_sleep_score' in result4['evidence_pool'] and 'sleep_performance' not in result4['evidence_pool']}")
    print()
    
    # 测试场景5: 苹果评分解析失败的fallback
    print("5. 苹果评分解析失败，fallback到传统方法")
    fallback_payload = apple_payload.copy()
    fallback_payload["apple_sleep_score"] = "invalid_data"  # 无效数据
    fallback_payload["objective"] = {
        "sleep_performance_state": "medium",
        "restorative_sleep": "medium", 
        "hrv_trend": "stable"
    }
    
    result5 = compute_readiness_from_payload(fallback_payload)
    print(f"输入: 无效苹果评分 + 传统medium")
    print(f"准备度分数: {result5['final_readiness_score']}")
    print(f"诊断: {result5['final_diagnosis']}")
    print(f"成功fallback: {'sleep_performance' in result5['evidence_pool'] and 'apple_sleep_score' not in result5['evidence_pool']}")
    print()
    
    print("=== 权重验证 ===")
    print(f"苹果评分权重设计: 1.0 (满权重)")
    print(f"传统sleep_performance权重: 0.90")
    print(f"设计理念: 苹果评分 = 传统多维数据综合")
    print()
    
    print("=== 测试完成 ===")

if __name__ == "__main__":
    test_apple_sleep_score_e2e()