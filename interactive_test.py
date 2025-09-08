
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式动态准备度模型测试脚本
按照真实使用流程进行3步测试：
1. 先验概率计算（昨天日志 + 睡眠HRV数据）
2. Hooper Index更新
3. 今日Journal更新
"""

from dynamic_model import DailyReadinessManager, JournalManager
from datetime import datetime, timedelta

class InteractiveTestRunner:
    def __init__(self):
        self.user_id = "test_user"
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.manager = None
        
        # 预设的传统影响因素 - 可以在这里修改
        self.preset_data = {
            'gender': '男性',  # 改为 '男性' 如果需要
            'yesterday_training_load': '高',  # 昨天训练强度：无/低/中/高/极高
            'yesterday_sleep_state': 'good',  # 昨晚睡眠状态：good/medium/poor
            'cumulative_fatigue_14day': 'medium',  # 14天累积疲劳：low/medium/high
            'menstrual_phase': 'late_luteal',  # 月经周期（仅女性）：menstrual_early_follicular/late_follicular_ovulatory/early_luteal/late_luteal
            'yesterday_final_state': {'Peak': 0.15, 'Well-adapted': 0.60, 'FOR': 0.20, 'Acute Fatigue': 0.05, 'NFOR': 0.0, 'OTS': 0.0},
            
            # 预设今天的客观数据
            'sleep_performance_state': 'medium',  # 睡眠表现：good/medium/poor
            'restorative_sleep': 'medium',        # 恢复性睡眠：high/medium/low
            'hrv_trend': 'stable',        # HRV趋势：rising/stable/slight_decline/significant_decline
            
            # 预设Hooper指数
            'fatigue_hooper': 3,    # 疲劳度 1-7
            'soreness_hooper': 5,   # 酸痛度 1-7
            'stress_hooper': 2,     # 压力度 1-7
            'sleep_hooper': 3,       # 睡眠质量 1-7
            
            # ===== Journal表 - 昨天的条目 (影响先验概率) =====
            'yesterday_journal': {
                # 短期行为 (影响第二天)
                'alcohol_consumed': False,         # 昨晚是否饮酒
                'late_caffeine': False,            # 昨晚是否摄入咖啡因
                'screen_before_bed': True,         # 昨晚睡前是否使用屏幕
                'late_meal_positive': False,       # 昨晚睡前营养良好的进食
                'late_meal_negative': True,        # 昨晚睡前不良影响的进食
                
                # 持续状态 (会持续影响)
                'is_sick': False,                  # 昨天是否生病
                'is_injured': False,               # 昨天是否受伤
                'high_work_stress_period': True,   # 是否处于高工作压力期
            },
            
            # ===== Journal表 - 今天的条目 (影响后验概率) =====
            'today_journal': {
                # 持续状态继承和新增
                'is_sick': False,                     # 今天是否仍然/新发生生病
                'is_injured': False,                  # 今天是否仍然/新发生受伤
                'high_stress_event_today': False,     # 今天是否发生重大压力事件
                
                # 当天行为
                'meditation_done_today': False,       # 今天是否完成冥想
            },
            
            # ===== 额外症状证据 =====
            'additional_symptoms': {
                'subjective_fatigue': 'low',         # low/medium/high
                'gi_symptoms': 'none',               # none/mild/severe
                'nutrition': 'adequate',             # adequate/inadequate_mild/inadequate_moderate/inadequate_severe
            }
        }
        
    def clear_screen(self):
        """清屏"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def print_header(self, title):
        """打印标题"""
        print("=" * 60)
        print(f"  {title}")
        print("=" * 60)
        
    def get_user_input(self, prompt, options=None, input_type=str):
        """获取用户输入"""
        while True:
            try:
                if options:
                    print(f"\n{prompt}")
                    for i, option in enumerate(options, 1):
                        print(f"{i}. {option}")
                    choice = int(input("请选择 (输入数字): ")) - 1
                    if 0 <= choice < len(options):
                        return options[choice]
                    else:
                        print("❌ 选择超出范围，请重新输入")
                else:
                    user_input = input(f"{prompt}: ")
                    return input_type(user_input)
            except (ValueError, IndexError):
                print("❌ 输入格式错误，请重新输入")
    
    def get_boolean_input(self, prompt):
        """获取True/False输入"""
        choice = self.get_user_input(f"{prompt}", ["是 (True)", "否 (False)"])
        return choice.startswith("是")
    
    def collect_journal_input(self, is_yesterday=True):
        """收集Journal输入 - 简化版本"""
        if is_yesterday:
            print("📝 昨天的Journal条目（用空格分隔，支持的条目如下）:")
            print("   短期行为: alcohol_consumed, late_caffeine, screen_before_bed")
            if self.preset_data['yesterday_training_load'] in ['高', '极高']:
                print("   睡前进食: late_meal_positive 或 late_meal_negative （基于高训练强度）")
            else:
                print("   睡前进食: late_meal_positive 或 late_meal_negative")
            print("   持续状态: is_sick, is_injured, high_work_stress_period")
            print("   示例: alcohol_consumed is_sick late_meal_negative")
            
            user_input = input("\n请输入昨天的Journal条目 (用空格分隔，无则直接回车): ").strip()
            
        else:
            print("📝 今天的Journal条目（用空格分隔，支持的条目如下）:")
            print("   持续状态: is_sick, is_injured, high_stress_event_today")
            print("   当天行为: meditation_done_today")
            print("   示例: is_sick meditation_done_today")
            
            # 检查昨天持续状态的继承
            yesterday_journal = self.manager.journal_manager.get_yesterdays_journal(self.user_id, self.today)
            yesterday_persistent = yesterday_journal.get('persistent_status', {})
            
            inherited_states = []
            if yesterday_persistent.get('is_sick'):
                inherited_states.append('is_sick')
            if yesterday_persistent.get('is_injured'):
                inherited_states.append('is_injured')
            
            if inherited_states:
                print(f"\n⚠️  昨天的持续状态: {' '.join(inherited_states)}")
                print("   如果今天仍然持续，请在输入中包含对应状态")
                print("   如果今天已恢复，请不要包含对应状态（将被自动取消）")
            
            user_input = input("\n请输入今天的Journal条目 (用空格分隔，无则直接回车): ").strip()
        
        return self.parse_journal_input(user_input, is_yesterday)
    
    def parse_journal_input(self, user_input, is_yesterday):
        """解析Journal输入"""
        if not user_input:
            return {
                'short_term_behaviors': {},
                'persistent_status': {},
                'training_context': {}
            }
        
        items = user_input.split()
        journal_data = {
            'short_term_behaviors': {},
            'persistent_status': {},
            'training_context': {}
        }
        
        if is_yesterday:
            # 处理昨天的条目
            for item in items:
                if item == 'alcohol_consumed':
                    journal_data['short_term_behaviors']['alcohol_consumed'] = True
                elif item == 'late_caffeine':
                    journal_data['short_term_behaviors']['late_caffeine'] = True
                elif item == 'screen_before_bed':
                    journal_data['short_term_behaviors']['screen_before_bed'] = True
                elif item == 'late_meal_positive':
                    journal_data['short_term_behaviors']['late_meal'] = 'positive'
                elif item == 'late_meal_negative':
                    journal_data['short_term_behaviors']['late_meal'] = 'negative'
                elif item == 'is_sick':
                    journal_data['persistent_status']['is_sick'] = True
                elif item == 'is_injured':
                    journal_data['persistent_status']['is_injured'] = True
                elif item == 'high_work_stress_period':
                    journal_data['persistent_status']['high_work_stress_period'] = True
                    
            # 添加预设数据
            if self.preset_data['gender'] == '女性':
                journal_data['persistent_status']['menstrual_phase'] = self.preset_data['menstrual_phase']
                
        else:
            # 处理今天的条目
            yesterday_journal = self.manager.journal_manager.get_yesterdays_journal(self.user_id, self.today)
            yesterday_persistent = yesterday_journal.get('persistent_status', {})
            
            # 默认继承昨天的持续状态
            if yesterday_persistent.get('is_sick'):
                journal_data['persistent_status']['is_sick'] = 'is_sick' in items
            if yesterday_persistent.get('is_injured'):
                journal_data['persistent_status']['is_injured'] = 'is_injured' in items
                
            # 处理新的条目
            for item in items:
                if item == 'is_sick' and not yesterday_persistent.get('is_sick'):
                    journal_data['persistent_status']['is_sick'] = True
                elif item == 'is_injured' and not yesterday_persistent.get('is_injured'):
                    journal_data['persistent_status']['is_injured'] = True
                elif item == 'high_stress_event_today':
                    journal_data['persistent_status']['high_stress_event_today'] = True
                elif item == 'meditation_done_today':
                    journal_data['short_term_behaviors']['meditation_done_today'] = True
        
        return journal_data
    
    def collect_sleep_hrv_data(self):
        """收集睡眠和HRV数据"""
        self.print_header("睡眠和HRV客观数据收集")
        print("📱 输入昨晚的睡眠传感器和HRV数据:")
        
        sleep_data = {
            'sleep_performance_state': self.get_user_input("睡眠表现状态", ['good', 'medium', 'poor']),
            'restorative_sleep': self.get_user_input("恢复性睡眠指标", ['high', 'medium', 'low']),
            'hrv_trend': self.get_user_input("HRV趋势", ['rising', 'stable', 'slight_decline', 'significant_decline'])
        }
        return sleep_data
    
    def collect_hooper_index(self):
        """收集Hooper指数"""
        self.print_header("Hooper指数量表填写")
        print("📝 请填写今早的主观感受量表 (1-7分，1=非常好，7=非常差):")
        
        hooper_data = {}
        hooper_items = [
            ('fatigue_hooper', '疲劳度'),
            ('soreness_hooper', '酸痛度'), 
            ('stress_hooper', '压力度'),
            ('sleep_hooper', '睡眠质量')
        ]
        
        for key, name in hooper_items:
            while True:
                try:
                    score = int(input(f"{name} (1-7): "))
                    if 1 <= score <= 7:
                        hooper_data[key] = score
                        break
                    else:
                        print("❌ 请输入1-7之间的数字")
                except ValueError:
                    print("❌ 请输入有效的数字")
                    
        return hooper_data
    
    def run_test(self):
        """运行完整测试"""
        self.clear_screen()
        print("🏃 动态准备度模型交互式测试")
        print(f"📅 测试日期: {self.today}")
        print(f"👤 测试用户: {self.user_id}")
        
        # 显示预设的传统影响因素
        self.print_header("预设的传统影响因素")
        print(f"性别: {self.preset_data['gender']}")
        print(f"昨天训练强度: {self.preset_data['yesterday_training_load']}")
        print(f"昨晚睡眠状态: {self.preset_data['yesterday_sleep_state']}")  
        print(f"14天累积疲劳: {self.preset_data['cumulative_fatigue_14day']}")
        if self.preset_data['gender'] == '女性':
            print(f"月经周期阶段: {self.preset_data['menstrual_phase']}")
        print(f"昨天最终状态: Well-adapted主导")
        
        input("\n如需修改预设值，请编辑代码中的preset_data。按回车键开始...")
        
        # ============== 第1步：收集昨天Journal + 计算先验概率 ==============
        self.clear_screen()
        yesterday_journal = self.collect_journal_input(is_yesterday=True)
        
        # 添加预设的传统数据
        yesterday_journal['training_context'] = {
            'training_load': self.preset_data['yesterday_training_load'],
            'cumulative_fatigue_14day': self.preset_data['cumulative_fatigue_14day']
        }
        
        # 创建管理器并添加日志数据
        self.manager = DailyReadinessManager(
            user_id=self.user_id,
            date=self.today,
            previous_state_probs=self.preset_data['yesterday_final_state'],
            gender=self.preset_data['gender']
        )
        
        # 添加昨天的日志数据
        for entry_type, entry_data in yesterday_journal.items():
            if entry_data:  # 只添加非空数据
                self.manager.journal_manager.add_journal_entry(
                    self.user_id, self.yesterday, entry_type, entry_data
                )
        
        # 计算先验概率
        causal_inputs = {
            'training_load': self.preset_data['yesterday_training_load'],
            'subjective_sleep_state': self.preset_data['yesterday_sleep_state'],
            'cumulative_fatigue_14day_state': self.preset_data['cumulative_fatigue_14day']
        }
        
        print("\n🧠 正在计算先验概率...")
        prior_probs = self.manager.calculate_today_prior(causal_inputs)
        prior_score = self.manager._get_readiness_score(prior_probs)
        
        print(f"\n✅ 先验概率计算完成！")
        print(f"📊 先验准备度分数: {prior_score}/100")
        diagnosis = max(prior_probs, key=prior_probs.get)
        print(f"🏥 先验诊断: {diagnosis}")
        
        input("\n按回车键继续到第2步...")
        
        # ============== 第2步：睡眠HRV数据 + Hooper指数 ==============
        self.clear_screen()
        
        # 收集睡眠HRV数据
        sleep_data = self.collect_sleep_hrv_data()
        result1 = self.manager.add_evidence_and_update(sleep_data)
        
        print(f"\n✅ 第一次更新完成（添加睡眠HRV数据）")
        print(f"📊 更新后准备度: {result1['readiness_score']}/100")
        print(f"🏥 当前诊断: {result1['diagnosis']}")
        
        input("\n按回车键填写Hooper指数...")
        
        # 收集Hooper指数
        hooper_data = self.collect_hooper_index()
        result2 = self.manager.add_evidence_and_update(hooper_data)
        
        print(f"\n✅ 第二次更新完成（添加Hooper指数）")
        print(f"📊 更新后准备度: {result2['readiness_score']}/100") 
        print(f"🏥 当前诊断: {result2['diagnosis']}")
        
        input("\n按回车键继续到第3步...")
        
        # ============== 第3步：今日Journal更新 ==============
        self.clear_screen()
        today_journal = self.collect_journal_input(is_yesterday=False)
        
        # 添加今天的日志数据
        for entry_type, entry_data in today_journal.items():
            if entry_data:  # 只添加非空数据
                self.manager.journal_manager.add_journal_entry(
                    self.user_id, self.today, entry_type, entry_data
                )
        
        # 添加其他可能的症状证据
        additional_evidence = {}
        if self.get_boolean_input("\n是否有其他症状需要记录？"):
            print("\n📝 其他症状记录:")
            additional_evidence = {
                'subjective_fatigue': self.get_user_input("当前主观疲劳感", ['low', 'medium', 'high']),
                'gi_symptoms': self.get_user_input("肠胃症状", ['none', 'mild', 'severe']),
                'nutrition': self.get_user_input("营养状况", ['adequate', 'inadequate_mild', 'inadequate_moderate', 'inadequate_severe'])
            }
        
        # 最终更新
        result3 = self.manager.add_evidence_and_update(additional_evidence)
        
        print(f"\n✅ 最终更新完成")
        print(f"📊 最终准备度分数: {result3['readiness_score']}/100")
        print(f"🏥 最终诊断: {result3['diagnosis']}")
        
        # ============== 总结报告 ==============
        self.show_summary_report()
    
    def show_summary_report(self):
        """显示总结报告"""
        input("\n按回车键查看详细报告...")
        self.clear_screen()
        
        self.print_header("完整准备度评估报告")
        summary = self.manager.get_daily_summary()
        
        print(f"📅 评估日期: {summary['date']}")
        print(f"👤 用户ID: {summary['user_id']}")
        print(f"🎯 最终准备度: {summary['final_readiness_score']}/100")
        print(f"🏥 最终诊断: {summary['final_diagnosis']}")
        print(f"🔄 总更新次数: {summary['total_updates']}")
        
        print(f"\n📊 准备度分数变化轨迹:")
        initial_score = self.manager._get_readiness_score(self.manager.today_prior_probs)
        print(f"初始先验分数: {initial_score}/100")
        
        update_labels = ["睡眠HRV数据", "Hooper指数", "Journal证据"]
        for i, update in enumerate(summary['update_history']): 
            score = update['readiness_score']
            label = update_labels[i] if i < len(update_labels) else f"更新{i+1}"
            print(f"第{i+1}次更新后: {score}/100 (添加{label})")
        
        print(f"\n🧠 概率分布变化:")
        print(f"{'状态':>15} {'先验':>8} {'最终':>8} {'变化':>8}")
        print("-" * 45)
        for state in self.manager.states:
            prior_prob = summary['prior_probs'].get(state, 0)
            final_prob = summary['final_posterior_probs'].get(state, 0)
            change = final_prob - prior_prob
            print(f"{state:>15} {prior_prob:>8.3f} {final_prob:>8.3f} {change:>+8.3f}")
        
        print(f"\n📋 最终证据池:")
        for key, value in summary['evidence_pool'].items():
            print(f"  • {key}: {value}")
            
        print(f"\n✅ 测试完成！")

if __name__ == "__main__":
    runner = InteractiveTestRunner()
    runner.run_test()