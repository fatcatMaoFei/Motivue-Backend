"""基线计算相关的数据模型

定义了睡眠记录、HRV记录和基线计算结果的数据结构。
支持数据验证和类型安全。
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
import json


@dataclass
class SleepRecord:
    """睡眠记录数据模型 - 匹配苹果健康app数据格式"""
    date: datetime
    sleep_duration_minutes: int  # 苹果健康app以分钟为单位
    time_in_bed_minutes: int     # 在床时间，用于计算睡眠效率
    deep_sleep_minutes: Optional[int] = None    # 深度睡眠分钟数
    rem_sleep_minutes: Optional[int] = None     # REM睡眠分钟数
    core_sleep_minutes: Optional[int] = None    # 核心睡眠分钟数
    awake_minutes: Optional[int] = 0            # 清醒分钟数
    source_device: Optional[str] = None
    # iOS 26 新增字段
    apple_sleep_score: Optional[float] = None   # 苹果原生睡眠评分 (0-100)
    
    # 计算属性
    @property
    def sleep_duration_hours(self) -> float:
        """睡眠时长（小时）"""
        return self.sleep_duration_minutes / 60.0
    
    @property 
    def sleep_efficiency(self) -> float:
        """睡眠效率 = 实际睡眠时间 / 在床时间"""
        if self.time_in_bed_minutes <= 0:
            return 0.0
        return self.sleep_duration_minutes / self.time_in_bed_minutes
    
    @property
    def deep_sleep_ratio(self) -> Optional[float]:
        """深度睡眠比例"""
        if self.deep_sleep_minutes is None or self.sleep_duration_minutes <= 0:
            return None
        return self.deep_sleep_minutes / self.sleep_duration_minutes
    
    @property
    def rem_sleep_ratio(self) -> Optional[float]:
        """REM睡眠比例"""
        if self.rem_sleep_minutes is None or self.sleep_duration_minutes <= 0:
            return None
        return self.rem_sleep_minutes / self.sleep_duration_minutes
    
    @property
    def restorative_ratio(self) -> Optional[float]:
        """恢复性睡眠比例 = (深度睡眠 + REM睡眠) / 总睡眠"""
        if (self.deep_sleep_minutes is None or self.rem_sleep_minutes is None 
            or self.sleep_duration_minutes <= 0):
            return None
        return (self.deep_sleep_minutes + self.rem_sleep_minutes) / self.sleep_duration_minutes
    
    def __post_init__(self):
        """数据验证"""
        if not 120 <= self.sleep_duration_minutes <= 900:  # 2-15小时的分钟数
            raise ValueError(f"睡眠时长异常: {self.sleep_duration_minutes}分钟")
        
        if not 120 <= self.time_in_bed_minutes <= 1200:  # 2-20小时的分钟数
            raise ValueError(f"在床时间异常: {self.time_in_bed_minutes}分钟")
            
        if self.sleep_efficiency > 1.0:
            raise ValueError(f"睡眠效率不能超过100%: {self.sleep_efficiency:.2%}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（包含计算属性）"""
        return {
            'date': self.date.isoformat(),
            'sleep_duration_minutes': self.sleep_duration_minutes,
            'time_in_bed_minutes': self.time_in_bed_minutes,
            'deep_sleep_minutes': self.deep_sleep_minutes,
            'rem_sleep_minutes': self.rem_sleep_minutes,
            'core_sleep_minutes': self.core_sleep_minutes,
            'awake_minutes': self.awake_minutes,
            'source_device': self.source_device,
            'apple_sleep_score': self.apple_sleep_score,
            # 计算属性
            'sleep_duration_hours': self.sleep_duration_hours,
            'sleep_efficiency': self.sleep_efficiency,
            'deep_sleep_ratio': self.deep_sleep_ratio,
            'rem_sleep_ratio': self.rem_sleep_ratio,
            'restorative_ratio': self.restorative_ratio
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SleepRecord':
        """从字典创建对象"""
        data = data.copy()
        if 'date' in data and isinstance(data['date'], str):
            data['date'] = datetime.fromisoformat(data['date'])
        return cls(**data)


@dataclass  
class HRVRecord:
    """HRV记录数据模型"""
    timestamp: datetime
    sdnn_value: float  # Apple HealthKit使用SDNN (ms)
    source_device: Optional[str] = None
    measurement_context: Optional[str] = None  # 'morning', 'post_workout', 'random'
    
    def __post_init__(self):
        """数据验证"""
        if not 5.0 <= self.sdnn_value <= 300.0:
            raise ValueError(f"HRV值异常: {self.sdnn_value}ms")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'sdnn_value': self.sdnn_value,
            'source_device': self.source_device,
            'measurement_context': self.measurement_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HRVRecord':
        """从字典创建对象"""
        data = data.copy()
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class BaselineResult:
    """基线计算结果"""
    user_id: str
    
    # 睡眠基线
    sleep_baseline_hours: Optional[float] = None
    sleep_baseline_eff: Optional[float] = None
    rest_baseline_ratio: Optional[float] = None
    # iOS 26 新增基线
    apple_sleep_score_baseline: Optional[float] = None  # 苹果评分基线 (0-100)
    
    # HRV基线
    hrv_baseline_mu: Optional[float] = None
    hrv_baseline_sd: Optional[float] = None
    
    # 元数据
    data_quality_score: float = 0.0
    sample_days_sleep: int = 0
    sample_days_hrv: int = 0
    calculation_version: str = "1.0"
    created_at: Optional[datetime] = None
    
    # 更新跟踪字段
    update_type: Optional[str] = None  # 'initial', 'incremental', 'full'
    last_incremental_update: Optional[datetime] = None
    last_full_update: Optional[datetime] = None
    
    def __post_init__(self):
        """设置默认值"""
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def is_valid(self) -> bool:
        """检查基线数据是否有效"""
        has_sleep = (self.sleep_baseline_hours is not None and 
                    self.sleep_baseline_eff is not None)
        has_hrv = (self.hrv_baseline_mu is not None and 
                  self.hrv_baseline_sd is not None)
        
        return (has_sleep or has_hrv) and self.data_quality_score >= 0.3
    
    def to_readiness_payload(self) -> Dict[str, Any]:
        """转换为readiness模块需要的格式"""
        payload = {}
        
        if self.sleep_baseline_hours is not None:
            payload['sleep_baseline_hours'] = self.sleep_baseline_hours
        if self.sleep_baseline_eff is not None:
            payload['sleep_baseline_eff'] = self.sleep_baseline_eff
        if self.rest_baseline_ratio is not None:
            payload['rest_baseline_ratio'] = self.rest_baseline_ratio
        if self.hrv_baseline_mu is not None:
            payload['hrv_baseline_mu'] = self.hrv_baseline_mu
        if self.hrv_baseline_sd is not None:
            payload['hrv_baseline_sd'] = self.hrv_baseline_sd
            
        return payload
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'user_id': self.user_id,
            'sleep_baseline_hours': self.sleep_baseline_hours,
            'sleep_baseline_eff': self.sleep_baseline_eff,
            'rest_baseline_ratio': self.rest_baseline_ratio,
            'apple_sleep_score_baseline': self.apple_sleep_score_baseline,
            'hrv_baseline_mu': self.hrv_baseline_mu,
            'hrv_baseline_sd': self.hrv_baseline_sd,
            'data_quality_score': self.data_quality_score,
            'sample_days_sleep': self.sample_days_sleep,
            'sample_days_hrv': self.sample_days_hrv,
            'calculation_version': self.calculation_version,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaselineResult':
        """从字典创建对象"""
        data = data.copy()
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


# 辅助函数
def validate_health_records(sleep_records: List[SleepRecord], 
                          hrv_records: List[HRVRecord]) -> Dict[str, Any]:
    """验证健康数据记录的质量"""
    validation_result = {
        'sleep_records_valid': 0,
        'hrv_records_valid': 0,
        'sleep_date_range_days': 0,
        'hrv_date_range_days': 0,
        'issues': []
    }
    
    # 验证睡眠记录
    if sleep_records:
        sleep_dates = [r.date.date() for r in sleep_records]
        validation_result['sleep_date_range_days'] = (max(sleep_dates) - min(sleep_dates)).days + 1
        validation_result['sleep_records_valid'] = len(sleep_records)
        
        if len(sleep_records) < 15:
            validation_result['issues'].append(f"睡眠记录太少: {len(sleep_records)}, 建议至少15天")
    
    # 验证HRV记录  
    if hrv_records:
        hrv_dates = [r.timestamp.date() for r in hrv_records]
        validation_result['hrv_date_range_days'] = (max(hrv_dates) - min(hrv_dates)).days + 1
        validation_result['hrv_records_valid'] = len(hrv_records)
        
        if len(hrv_records) < 10:
            validation_result['issues'].append(f"HRV记录太少: {len(hrv_records)}, 建议至少10个样本")
    
    return validation_result