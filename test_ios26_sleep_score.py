#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试iOS 26睡眠评分兼容性"""

from readiness.mapping import map_inputs_to_states

def test_ios26_apple_sleep_score():
    """测试iOS 26苹果睡眠评分优先逻辑"""
    
    print("=== iOS 26 睡眠评分测试 ===\n")
    
    # 测试场景1: 有苹果评分，应该使用苹果评分
    print("1. 有苹果评分（72分）")
    apple_input = {
        'apple_sleep_score': 72,
        # 同时也有传统数据，但应该被忽略
        'sleep_duration_hours': 8.0,
        'sleep_efficiency': 0.90
    }
    result1 = map_inputs_to_states(apple_input)
    print(f"输入: 苹果评分72分")
    print(f"输出: {result1}")
    print(f"使用苹果评分: {'apple_sleep_score' in result1}")
    print(f"跳过传统评分: {'sleep_performance' not in result1}")
    print()
    
    # 测试场景2: 有苹果评分（85分，excellent级别）  
    print("2. 有苹果评分（85分，excellent级别）")
    apple_excellent = {
        'apple_sleep_score': 85
    }
    result2 = map_inputs_to_states(apple_excellent)
    print(f"输入: 苹果评分85分")
    print(f"输出: {result2}")
    print(f"评分级别: {result2.get('apple_sleep_score', 'N/A')}")
    print()
    
    # 测试场景3: 无苹果评分，使用传统方法
    print("3. 无苹果评分，使用传统方法")
    traditional_input = {
        # 没有apple_sleep_score
        'sleep_duration_hours': 7.5,
        'sleep_efficiency': 0.88
    }
    result3 = map_inputs_to_states(traditional_input)
    print(f"输入: 无苹果评分，传统数据7.5h+88%效率")
    print(f"输出: {result3}")
    print(f"使用传统评分: {'sleep_performance' in result3}")
    print()
    
    # 测试场景4: 老版本iOS用户，使用传统方法
    print("4. 老版本iOS用户（iOS 15），使用传统方法")
    ios15_input = {
        'ios_version': 15,
        'sleep_duration_hours': 7.0,
        'sleep_efficiency': 0.85
    }
    result4 = map_inputs_to_states(ios15_input)
    print(f"输入: iOS 15, 传统数据7h+85%效率")
    print(f"输出: {result4}")
    print(f"使用传统评分: {'sleep_performance' in result4}")
    print(f"未使用苹果评分: {'apple_sleep_score' not in result4}")
    print()
    
    # 测试场景5: 苹果评分解析失败，自动fallback
    print("5. 苹果评分解析失败，自动fallback")
    invalid_score = {
        'ios_version': 26,
        'apple_sleep_score': 'invalid_data',  # 无法解析的数据
        'sleep_duration_hours': 8.0,
        'sleep_efficiency': 0.90
    }
    result5 = map_inputs_to_states(invalid_score)
    print(f"输入: iOS 26, 无效苹果评分，传统数据8h+90%效率")
    print(f"输出: {result5}")
    print(f"fallback到传统评分: {'sleep_performance' in result5}")
    print()
    
    # 测试场景6: 边界情况 - 同时有两套评分
    print("6. 边界情况：同时有苹果评分和传统数据")
    both_scores = {
        'apple_sleep_score': 75,  # good级别
        'sleep_duration_hours': 6.0,  # poor级别
        'sleep_efficiency': 0.70   # poor级别
    }
    result6 = map_inputs_to_states(both_scores)
    print(f"输入: 苹果75分(good) + 传统6h+70%(poor)")
    print(f"输出: {result6}")
    print(f"是否只使用苹果评分: {'apple_sleep_score' in result6 and 'sleep_performance' not in result6}")
    print(f"苹果评分胜出: {result6.get('apple_sleep_score', 'N/A')}")
    print()
    
    print("=== 测试完成 ===")

if __name__ == "__main__":
    test_ios26_apple_sleep_score()