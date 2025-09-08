#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整动态准备度模型测试脚本
所有参数预填在代码中，按步骤显示计算过程
"""

from numpy import true_divide
from dynamic_model import DailyReadinessManager, JournalManager
from datetime import datetime, timedelta

class ComprehensiveTestRunner:
    def __init__(self):
        self.user_id = "test_user"
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.manager = None
        
        # ===== 用户基本信息 =====
        self.gender = '男性'# 改为 '男性' 如果需要测试男性
        
        # ===== 前一天的最终状态 =====
        self.yesterday_final_state = {
            'Peak': 0.5,
            'Well-adapted': 0.2,
            'FOR': 0.20, 
            'Acute Fatigue': 0.1,
            'NFOR': 0.0, 
            'OTS': 0.0
        }
        
        # ===== 传统影响因素 (影响先验概率) =====
        self.yesterday_training_load = '低'  # 无/低/中/高/极高
        self.cumulative_fatigue_14day = 'medium'  # low/medium/high
        
        # ===== 女性月经周期 (仅当gender='女性'时生效) =====
        self.menstrual_phase = 'late_luteal'  # menstrual_early_follicular/late_follicular_ovulatory/early_luteal/late_luteal
        
        # ===== 昨天的Journal条目 (影响先验概率) =====
        self.yesterday_journal = {
            # 短期行为 (影响第二天)
            'alcohol_consumed': True,      # 昨晚是否饮酒
            'late_caffeine': False,         # 昨晚是否摄入咖啡因  
            'screen_before_bed': False,      # 昨晚睡前是否使用屏幕
            'late_meal': False,              # 昨晚是否有睡前进食 (影响会根据训练强度自动判断positive/negative)
            
            # 持续状态 (会持续影响)
            'is_sick': False,               # 昨天是否生病
            'is_injured': False,            # 昨天是否受伤
            'high_work_stress_period': False # 是否处于高工作压力期
        }
        
        # ===== 今天的客观数据 (第一次更新) =====
        self.today_sleep_data = {
            'sleep_performance_state': 'medium',    # good/medium/poor
            'restorative_sleep': 'medium',          # high/medium/low  
            'hrv_trend': 'stable'                   # rising/stable/slight_decline/significant_decline
        }
        
        # ===== Hooper指数 (第二次更新) =====
        self.hooper_data = {
            'fatigue_hooper': 3,    # 疲劳度 1-7
            'soreness_hooper': 2,   # 酸痛度 1-7
            'stress_hooper': 2,     # 压力度 1-7
            'sleep_hooper': 3       # 睡眠质量 1-7
        }
        
        # ===== 今天的Journal条目 (第三次更新) =====
        self.today_journal = {
            # 持续状态继承和新增
            'is_sick': False,                    # 今天是否仍然/新发生生病
            'is_injured': False,                 # 今天是否仍然/新发生受伤
            'high_stress_event_today': False,    # 今天是否发生重大压力事件
            
            # 当天行为
            'meditation_done_today': True       # 今天是否完成冥想
        }
        
        # ===== 额外症状证据 (最终更新) =====
        self.additional_symptoms = {
            'subjective_fatigue': 'low',         # low/medium/high
            'gi_symptoms': 'none',               # none/mild/severe
            'nutrition': 'adequate'              # adequate/inadequate_mild/inadequate_moderate/inadequate_severe
        }
    
    def print_header(self, title):
        """打印标题"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)
    
    def print_probability_distribution(self, probs, title):
        """打印概率分布"""
        print(f"\n{title}:")
        for state, prob in probs.items():
            print(f"   {state:15}: {prob:.4f} ({prob*100:.2f}%)")
    
    def print_score_and_diagnosis(self, probs, title):
        """打印分数和诊断"""
        score = self.manager._get_readiness_score(probs)
        diagnosis = max(probs, key=probs.get)
        confidence = probs[diagnosis]
        print(f"\n{title}: {score}/100")
        print(f"诊断: {diagnosis} (置信度: {confidence:.3f})")
        return score, diagnosis
    
    def run_comprehensive_test(self):
        """运行完整测试"""
        self.print_header("动态准备度模型完整测试")
        print(f"测试日期: {self.today}")
        print(f"用户: {self.user_id}")
        print(f"性别: {self.gender}")
        
        # ============== 显示所有预设参数 ==============
        self.print_header("所有预设参数")
        
        print("前一天最终状态:")
        for state, prob in self.yesterday_final_state.items():
            print(f"   {state}: {prob}")
            
        print(f"\n传统影响因素:")
        print(f"   昨天训练强度: {self.yesterday_training_load}")
        print(f"   14天累积疲劳: {self.cumulative_fatigue_14day}")
        if self.gender == '女性':
            print(f"   月经周期阶段: {self.menstrual_phase}")
        
        print(f"\n昨天Journal条目:")
        for key, value in self.yesterday_journal.items():
            if value:
                print(f"   {key}")
        
        print(f"\n今天客观数据:")
        for key, value in self.today_sleep_data.items():
            print(f"   {key}: {value}")
            
        print(f"\nHooper指数:")
        for key, value in self.hooper_data.items():
            print(f"   {key.replace('_hooper', '')}: {value}/7")
        
        print(f"\n今天Journal条目:")
        active_journal = [k for k, v in self.today_journal.items() if v]
        if active_journal:
            for item in active_journal:
                print(f"   {item}")
        else:
            print("   (无)")
            
        print(f"\n额外症状:")
        for key, value in self.additional_symptoms.items():
            print(f"   {key}: {value}")
        
        input("\n按回车键开始计算...")
        
        # ============== 第1步：计算先验概率 ==============
        self.print_header("第1步：计算先验概率 (Prior Probability)")
        
        # 创建管理器
        self.manager = DailyReadinessManager(
            user_id=self.user_id,
            date=self.today,
            previous_state_probs=self.yesterday_final_state,
            gender=self.gender
        )
        
        # 添加昨天的Journal数据
        journal_data = {
            'short_term_behaviors': {},
            'persistent_status': {},
            'training_context': {
                'training_load': self.yesterday_training_load,
                'cumulative_fatigue_14day': self.cumulative_fatigue_14day
            }
        }
        
        # 处理短期行为
        for key, value in self.yesterday_journal.items():
            if value and key in ['alcohol_consumed', 'late_caffeine', 'screen_before_bed', 'late_meal']:
                journal_data['short_term_behaviors'][key] = True
        
        # 处理持续状态
        for key in ['is_sick', 'is_injured', 'high_work_stress_period']:
            if self.yesterday_journal.get(key):
                journal_data['persistent_status'][key] = True
        
        # 添加月经周期（仅女性）
        if self.gender == '女性':
            journal_data['persistent_status']['menstrual_phase'] = self.menstrual_phase
        
        # 添加日志数据
        for entry_type, entry_data in journal_data.items():
            if entry_data:
                self.manager.journal_manager.add_journal_entry(
                    self.user_id, self.yesterday, entry_type, entry_data
                )
        
        # 计算先验概率 (subjective_sleep_state会由yesterday的sleep_hooper自动转换)
        causal_inputs = {
            'training_load': self.yesterday_training_load,
            'cumulative_fatigue_14day_state': self.cumulative_fatigue_14day
        }
        
        print("正在计算先验概率...")
        prior_probs = self.manager.calculate_today_prior(causal_inputs)
        
        self.print_probability_distribution(prior_probs, "先验概率分布")
        prior_score, prior_diagnosis = self.print_score_and_diagnosis(prior_probs, "先验准备度分数")
        
        input("\n按回车键继续第2步...")
        
        # ============== 第2步：添加客观睡眠HRV数据 ==============
        self.print_header("第2步：第一次更新 - 添加客观睡眠HRV数据")
        
        print("添加客观数据:")
        for key, value in self.today_sleep_data.items():
            print(f"   {key}: {value}")
        
        result1 = self.manager.add_evidence_and_update(self.today_sleep_data)
        
        self.print_probability_distribution(result1['posterior_probs'], "第一次更新后概率分布")
        score1, diagnosis1 = self.print_score_and_diagnosis(result1['posterior_probs'], "第一次更新后分数")
        
        print(f"\n分数变化: {prior_score} → {score1} ({score1-prior_score:+.0f})")
        print(f"诊断变化: {prior_diagnosis} → {diagnosis1}")
        
        input("\n按回车键继续第3步...")
        
        # ============== 第3步：添加Hooper指数 ==============
        self.print_header("第3步：第二次更新 - 添加Hooper指数")
        
        print("Hooper指数:")
        for key, value in self.hooper_data.items():
            print(f"   {key.replace('_hooper', '')}: {value}/7")
        
        result2 = self.manager.add_evidence_and_update(self.hooper_data)
        
        self.print_probability_distribution(result2['posterior_probs'], "第二次更新后概率分布")
        score2, diagnosis2 = self.print_score_and_diagnosis(result2['posterior_probs'], "第二次更新后分数")
        
        print(f"\n分数变化: {score1} → {score2} ({score2-score1:+.0f})")
        print(f"诊断变化: {diagnosis1} → {diagnosis2}")
        
        input("\n按回车键继续第4步...")
        
        # ============== 第4步：添加今天Journal ==============
        self.print_header("第4步：第三次更新 - 添加今天Journal数据")
        
        # 处理持续状态继承
        yesterday_journal_data = self.manager.journal_manager.get_yesterdays_journal(self.user_id, self.today)
        yesterday_persistent = yesterday_journal_data.get('persistent_status', {})
        
        print("持续状态处理:")
        if yesterday_persistent.get('is_sick'):
            if self.today_journal['is_sick']:
                print("   继续生病状态")
            else:
                print("   取消生病状态（已恢复）")
        elif self.today_journal['is_sick']:
            print("   新发生生病状态")
            
        if yesterday_persistent.get('is_injured'):
            if self.today_journal['is_injured']:
                print("   继续受伤状态")  
            else:
                print("   取消受伤状态（已恢复）")
        elif self.today_journal['is_injured']:
            print("   新发生受伤状态")
        
        print("\n当天Journal条目:")
        for key, value in self.today_journal.items():
            if value:
                print(f"   {key}")
        
        # 添加今天的Journal数据
        today_journal_data = {
            'short_term_behaviors': {},
            'persistent_status': {}
        }
        
        # 处理持续状态
        for key in ['is_sick', 'is_injured']:
            today_journal_data['persistent_status'][key] = self.today_journal[key]
            
        # 处理新的状态和行为
        if self.today_journal['high_stress_event_today']:
            today_journal_data['persistent_status']['high_stress_event_today'] = True
        if self.today_journal['meditation_done_today']:
            today_journal_data['short_term_behaviors']['meditation_done_today'] = True
        
        # 添加数据
        for entry_type, entry_data in today_journal_data.items():
            if entry_data:
                self.manager.journal_manager.add_journal_entry(
                    self.user_id, self.today, entry_type, entry_data
                )
        
        # 更新（Journal证据会自动被检测）
        result3 = self.manager.add_evidence_and_update({})
        
        self.print_probability_distribution(result3['posterior_probs'], "第三次更新后概率分布")
        score3, diagnosis3 = self.print_score_and_diagnosis(result3['posterior_probs'], "第三次更新后分数")
        
        print(f"\n分数变化: {score2} → {score3} ({score3-score2:+.0f})")
        print(f"诊断变化: {diagnosis2} → {diagnosis3}")
        
        input("\n按回车键继续最终步...")
        
        # ============== 第5步：添加额外症状 ==============
        self.print_header("第5步：最终更新 - 添加额外症状")
        
        print("额外症状证据:")
        for key, value in self.additional_symptoms.items():
            print(f"   {key}: {value}")
        
        result_final = self.manager.add_evidence_and_update(self.additional_symptoms)
        
        self.print_probability_distribution(result_final['posterior_probs'], "最终概率分布")
        final_score, final_diagnosis = self.print_score_and_diagnosis(result_final['posterior_probs'], "最终准备度分数")
        
        print(f"\n分数变化: {score3} → {final_score} ({final_score-score3:+.0f})")
        print(f"诊断变化: {diagnosis3} → {final_diagnosis}")
        
        # ============== 完整总结 ==============
        self.print_header("完整变化总结")
        
        print("分数变化轨迹:")
        print(f"   先验概率: {prior_score}/100 ({prior_diagnosis})")
        print(f"   +睡眠HRV: {score1}/100 ({diagnosis1}) [{score1-prior_score:+.0f}]")
        print(f"   +Hooper指数: {score2}/100 ({diagnosis2}) [{score2-score1:+.0f}]")
        print(f"   +Journal: {score3}/100 ({diagnosis3}) [{score3-score2:+.0f}]")
        print(f"   +额外症状: {final_score}/100 ({final_diagnosis}) [{final_score-score3:+.0f}]")
        
        print(f"\n总变化: {prior_score} → {final_score} ({final_score-prior_score:+.0f})")
        
        # 获取详细总结
        summary = self.manager.get_daily_summary()
        
        print(f"\n最终证据池 ({len(summary['evidence_pool'])}项):")
        for key, value in summary['evidence_pool'].items():
            print(f"   {key}: {value}")
        
        print(f"\n测试完成！")

if __name__ == "__main__":
    runner = ComprehensiveTestRunner()
    runner.run_comprehensive_test()