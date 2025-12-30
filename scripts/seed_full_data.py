#!/usr/bin/env python3
"""
数据填充脚本 - 为本地开发填充真实结构的测试数据

运行方式:
    cd Motivue-Backend
    source venv/bin/activate
    PYTHONPATH=. python scripts/seed_full_data.py
"""

import os
import sys
import json
from datetime import date, timedelta, datetime
import random

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from libs.core_domain.db import Base, User, UserBaseline, UserDaily

# 使用本地 SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")
engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)

def seed_data():
    """填充测试数据"""
    
    # 创建表
    Base.metadata.create_all(engine)
    
    session = Session()
    
    try:
        user_id = "u001"
        today = date.today()
        
        # 1. 创建用户
        existing_user = session.query(User).filter_by(user_id=user_id).first()
        if not existing_user:
            user = User(
                user_id=user_id,
                email="test@motivue.com",
                password_hash="not_used",
                display_name="测试用户",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(user)
            print(f"✅ 创建用户: {user_id}")
        else:
            print(f"⏭️ 用户已存在: {user_id}")
        
        # 2. 创建基线数据
        existing_baseline = session.query(UserBaseline).filter_by(user_id=user_id).first()
        if existing_baseline:
            session.delete(existing_baseline)
        
        baseline = UserBaseline(
            user_id=user_id,
            sleep_baseline_hours=7.5,
            sleep_baseline_eff=88.0,
            rest_baseline_ratio=0.35,
            hrv_baseline_mu=55.0,
            hrv_baseline_sd=12.0
        )
        session.add(baseline)
        print(f"✅ 创建基线数据")
        
        # 3. 创建过去7天的每日数据
        for days_ago in range(7, -1, -1):  # 7天前到今天
            record_date = today - timedelta(days=days_ago)
            
            # 删除已存在的记录
            existing_daily = session.query(UserDaily).filter_by(
                user_id=user_id, 
                date=record_date
            ).first()
            if existing_daily:
                session.delete(existing_daily)
            
            # 生成合理的随机数据
            sleep_hours = random.uniform(6.5, 8.5)
            deep_ratio = random.uniform(0.15, 0.25)
            rem_ratio = random.uniform(0.20, 0.28)
            light_ratio = 1.0 - deep_ratio - rem_ratio - 0.05  # 5% 清醒时间
            
            hrv_rmssd = random.uniform(45, 75)
            resting_hr = random.uniform(52, 68)
            
            # Hooper 主观感受 (1-7 分)
            hooper = {
                "fatigue": random.randint(2, 5),
                "stress": random.randint(2, 4),
                "soreness": random.randint(1, 4),
                "sleep": random.randint(4, 7)
            }
            
            # 设备指标
            device_metrics = {
                "sleep_duration_hours": sleep_hours,
                "sleep_efficiency": random.uniform(82, 95),
                "deep_sleep_ratio": deep_ratio,
                "rem_sleep_ratio": rem_ratio,
                "light_sleep_ratio": light_ratio,
                "hrv_rmssd_today": hrv_rmssd,
                "resting_hr": resting_hr,
                "spo2_percent": random.uniform(96, 99),
                "skin_temp_celsius": random.uniform(34.5, 36.5)
            }
            
            # Evidence Pool (用于 Readiness Factors 显示)
            evidence_pool = {
                "sleep_performance": {
                    "state": random.choice(["Optimal", "Good", "Suboptimal"]),
                    "value": sleep_hours,
                    "description": f"昨晚睡眠 {sleep_hours:.1f} 小时"
                },
                "restorative_sleep": {
                    "state": random.choice(["Optimal", "Good", "Suboptimal"]),
                    "value": (deep_ratio + rem_ratio) * 100,
                    "description": f"恢复性睡眠占比 {(deep_ratio + rem_ratio) * 100:.0f}%"
                },
                "hrv_trend": {
                    "state": random.choice(["Optimal", "Good", "Suboptimal"]),
                    "value": hrv_rmssd,
                    "description": f"HRV RMSSD {hrv_rmssd:.0f} ms"
                },
                "recovery_index": {
                    "state": random.choice(["Optimal", "Good", "Suboptimal"]),
                    "value": random.uniform(0.6, 0.95),
                    "description": "基于多维度指标的恢复评估"
                }
            }
            
            # 计算 Readiness Score (模拟后端计算逻辑)
            # 简化版: 基于睡眠时长、HRV、Hooper 计算
            sleep_score = min(100, (sleep_hours / 8.0) * 100)
            hrv_score = min(100, (hrv_rmssd / 60.0) * 100)
            hooper_score = ((7 - hooper["fatigue"]) + (7 - hooper["stress"]) + 
                           (7 - hooper["soreness"]) + hooper["sleep"]) / 28 * 100
            
            final_readiness_score = int(sleep_score * 0.35 + hrv_score * 0.35 + hooper_score * 0.30)
            
            # 诊断
            if final_readiness_score >= 80:
                diagnosis = "Ready to Perform"
            elif final_readiness_score >= 60:
                diagnosis = "Moderate Readiness"
            else:
                diagnosis = "Need Recovery"
            
            daily = UserDaily(
                user_id=user_id,
                date=record_date,
                hooper=hooper,
                device_metrics=device_metrics,
                final_readiness_score=final_readiness_score,
                current_readiness_score=final_readiness_score,
                final_diagnosis=diagnosis,
                objective=evidence_pool,  # 存储 evidence_pool 到 objective 字段
                previous_state_probs={
                    "Peak": 0.1,
                    "Well-adapted": 0.5,
                    "FOR": 0.3,
                    "Acute Fatigue": 0.1,
                    "NFOR": 0.0,
                    "OTS": 0.0
                }
            )
            session.add(daily)
            print(f"✅ 创建每日数据: {record_date} | Readiness: {final_readiness_score} | {diagnosis}")
        
        session.commit()
        print("\n🎉 数据填充完成！")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 错误: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    seed_data()
