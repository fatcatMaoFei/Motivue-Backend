"""Baseline（个人基线）模块

用于计算和管理用户个人健康基线的独立模块。
为 readiness 准备度评估提供个性化支持。

支持7天增量更新和30天完整更新策略。

主要功能：
- 从HealthKit历史数据计算个人睡眠基线
- 从HealthKit历史数据计算个人HRV基线  
- 数据质量评估和异常值过滤
- 基线数据存储和更新管理
- 7天增量更新和30天完整更新
- 智能更新调度
"""

from .calculator import PersonalBaselineCalculator
from .models import SleepRecord, HRVRecord, BaselineResult
from .service import (
    compute_personal_baseline,
    compute_baseline_from_healthkit_data,
    compute_baseline_from_healthkit,
    get_user_baseline,
    update_baseline_if_needed,
    # 新的更新接口
    update_baseline_smart,
    update_baseline_incremental,
    update_baseline_full,
    check_baseline_update_needed,
    get_baseline_update_schedule
)
from .storage import BaselineStorage, MemoryBaselineStorage, FileBaselineStorage
from .updater import BaselineUpdater, UpdateStrategy
from .auto_upgrade import BaselineAutoUpgrade, check_user_upgrade_eligibility, auto_upgrade_user

__version__ = "1.1.0"
__author__ = "Readiness Team"

__all__ = [
    # 计算器
    'PersonalBaselineCalculator',
    
    # 数据模型
    'SleepRecord', 
    'HRVRecord',
    'BaselineResult',
    
    # 主要服务接口
    'compute_personal_baseline',
    'compute_baseline_from_healthkit_data', 
    'compute_baseline_from_healthkit',
    'get_user_baseline',
    'update_baseline_if_needed',
    
    # 更新接口
    'update_baseline_smart',        # 推荐：智能选择更新类型
    'update_baseline_incremental',  # 7天增量更新
    'update_baseline_full',        # 30天完整更新
    'check_baseline_update_needed', # 检查更新需求
    'get_baseline_update_schedule', # 获取更新计划
    
    # 自动升级接口
    'BaselineAutoUpgrade',         # 自动升级管理器
    'check_user_upgrade_eligibility', # 检查升级资格
    'auto_upgrade_user',           # 自动升级用户
    
    # 更新器类
    'BaselineUpdater',
    'UpdateStrategy',
    
    # 存储管理
    'BaselineStorage',
    'MemoryBaselineStorage',
    'FileBaselineStorage'
]