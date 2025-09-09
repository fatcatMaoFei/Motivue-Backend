"""个人基线计算核心逻辑

负责从用户健康数据中计算个性化基线，包括：
- 睡眠时长和效率基线
- 恢复性睡眠基线  
- HRV（心率变异性）基线
- 数据质量评估和异常值过滤
"""

from __future__ import annotations
from typing import List, Dict, Tuple, Optional
import statistics
import math
from datetime import datetime, timedelta

from .models import SleepRecord, HRVRecord, BaselineResult


class PersonalBaselineCalculator:
    """个人基线计算器
    
    使用稳健统计方法计算个人健康基线，具有异常值过滤功能。
    """
    
    def __init__(self):
        # 异常值过滤的百分位数范围
        self.sleep_percentile_range = (10, 90)  # 睡眠数据使用10-90百分位
        self.hrv_percentile_range = (5, 95)     # HRV数据使用5-95百分位（更宽松）
        
        # 数据质量要求
        self.min_sleep_records = 15
        self.min_hrv_records = 10
        
    def calculate_baseline(self, 
                         user_id: str,
                         sleep_records: List[SleepRecord], 
                         hrv_records: List[HRVRecord]) -> BaselineResult:
        """计算完整的个人基线"""
        
        result = BaselineResult(user_id=user_id)
        
        # 计算睡眠基线
        if len(sleep_records) >= self.min_sleep_records:
            sleep_baseline = self._calculate_sleep_baseline(sleep_records)
            result.sleep_baseline_hours = sleep_baseline.get('sleep_baseline_hours')
            result.sleep_baseline_eff = sleep_baseline.get('sleep_baseline_eff') 
            result.rest_baseline_ratio = sleep_baseline.get('rest_baseline_ratio')
            result.sample_days_sleep = len(sleep_records)
        
        # 计算HRV基线
        if len(hrv_records) >= self.min_hrv_records:
            hrv_baseline = self._calculate_hrv_baseline(hrv_records)
            result.hrv_baseline_mu = hrv_baseline.get('hrv_baseline_mu')
            result.hrv_baseline_sd = hrv_baseline.get('hrv_baseline_sd')
            result.sample_days_hrv = len(hrv_records)
        
        # 计算数据质量评分
        result.data_quality_score = self._calculate_quality_score(
            sleep_records, hrv_records, result
        )
        
        return result
    
    def _calculate_sleep_baseline(self, records: List[SleepRecord]) -> Dict[str, Optional[float]]:
        """计算睡眠基线"""
        if not records:
            return {'sleep_baseline_hours': None, 'sleep_baseline_eff': None, 'rest_baseline_ratio': None}
        
        # 提取数据
        durations = [r.sleep_duration_hours for r in records]
        efficiencies = [r.sleep_efficiency for r in records]
        restorative_ratios = [r.restorative_ratio for r in records if r.restorative_ratio is not None]
        
        # 过滤异常值并计算基线
        duration_filtered = self._filter_outliers(durations, self.sleep_percentile_range)
        efficiency_filtered = self._filter_outliers(efficiencies, self.sleep_percentile_range)
        
        sleep_baseline_hours = self._robust_mean(duration_filtered) if duration_filtered else None
        sleep_baseline_eff = self._robust_mean(efficiency_filtered) if efficiency_filtered else None
        
        # 恢复性睡眠基线
        rest_baseline_ratio = None
        if restorative_ratios:
            rest_filtered = self._filter_outliers(restorative_ratios, self.sleep_percentile_range)
            rest_baseline_ratio = self._robust_mean(rest_filtered) if rest_filtered else None
        
        return {
            'sleep_baseline_hours': round(sleep_baseline_hours, 2) if sleep_baseline_hours else None,
            'sleep_baseline_eff': round(sleep_baseline_eff, 3) if sleep_baseline_eff else None,
            'rest_baseline_ratio': round(rest_baseline_ratio, 3) if rest_baseline_ratio else None,
        }
    
    def _calculate_hrv_baseline(self, records: List[HRVRecord]) -> Dict[str, Optional[float]]:
        """计算HRV基线"""
        if not records:
            return {'hrv_baseline_mu': None, 'hrv_baseline_sd': None}
        
        # 提取HRV数值
        hrv_values = [r.sdnn_value for r in records]
        
        # 过滤异常值
        hrv_filtered = self._filter_outliers(hrv_values, self.hrv_percentile_range)
        
        if len(hrv_filtered) < 5:  # 至少需要5个有效值
            return {'hrv_baseline_mu': None, 'hrv_baseline_sd': None}
        
        # 计算均值和标准差
        hrv_mean = self._robust_mean(hrv_filtered)
        hrv_std = self._robust_std(hrv_filtered)
        
        return {
            'hrv_baseline_mu': round(hrv_mean, 2) if hrv_mean else None,
            'hrv_baseline_sd': round(hrv_std, 2) if hrv_std else None,
        }
    
    def _filter_outliers(self, data: List[float], percentile_range: Tuple[int, int]) -> List[float]:
        """使用百分位数方法过滤异常值"""
        if len(data) < 5:  # 数据太少时不过滤
            return data
        
        try:
            low_p, high_p = percentile_range
            
            # 计算百分位数阈值
            sorted_data = sorted(data)
            n = len(sorted_data)
            
            low_idx = max(0, int(n * low_p / 100))
            high_idx = min(n - 1, int(n * high_p / 100))
            
            low_threshold = sorted_data[low_idx]
            high_threshold = sorted_data[high_idx]
            
            # 过滤异常值
            filtered = [x for x in data if low_threshold <= x <= high_threshold]
            
            return filtered if filtered else data  # 如果过滤后为空，返回原数据
            
        except Exception:
            return data  # 出错时返回原数据
    
    def _robust_mean(self, data: List[float]) -> Optional[float]:
        """计算稳健均值（使用中位数或修剪均值）"""
        if not data:
            return None
        
        if len(data) < 3:
            return statistics.mean(data)
        
        try:
            # 对于小样本，使用普通均值
            if len(data) <= 10:
                return statistics.mean(data)
            
            # 对于大样本，使用20%修剪均值（去除最高和最低20%）
            sorted_data = sorted(data)
            trim_count = max(1, len(sorted_data) // 5)  # 20%修剪
            trimmed = sorted_data[trim_count:-trim_count]
            
            return statistics.mean(trimmed) if trimmed else statistics.mean(data)
            
        except Exception:
            return statistics.mean(data)
    
    def _robust_std(self, data: List[float]) -> Optional[float]:
        """计算稳健标准差"""
        if len(data) < 2:
            return None
            
        try:
            if len(data) <= 10:
                return statistics.stdev(data)
            
            # 使用修剪后的数据计算标准差
            sorted_data = sorted(data)
            trim_count = max(1, len(sorted_data) // 5)
            trimmed = sorted_data[trim_count:-trim_count]
            
            return statistics.stdev(trimmed) if len(trimmed) > 1 else statistics.stdev(data)
            
        except Exception:
            return statistics.stdev(data) if len(data) > 1 else None
    
    def _calculate_quality_score(self, 
                               sleep_records: List[SleepRecord], 
                               hrv_records: List[HRVRecord],
                               result: BaselineResult) -> float:
        """计算数据质量评分 (0-1)"""
        
        score_components = []
        
        # 1. 数据量评分 (40%)
        sleep_quantity_score = min(len(sleep_records) / 30, 1.0)  # 30天睡眠数据为满分
        hrv_quantity_score = min(len(hrv_records) / 50, 1.0)     # 50个HRV样本为满分
        
        if sleep_records and hrv_records:
            quantity_score = (sleep_quantity_score + hrv_quantity_score) / 2
        elif sleep_records:
            quantity_score = sleep_quantity_score
        elif hrv_records:
            quantity_score = hrv_quantity_score
        else:
            quantity_score = 0.0
            
        score_components.append(('quantity', quantity_score * 0.4))
        
        # 2. 数据完整性评分 (30%)
        completeness_score = 0.0
        if sleep_records:
            # 检查恢复性睡眠数据的完整性
            complete_sleep = sum(1 for r in sleep_records if r.restorative_ratio is not None)
            sleep_completeness = complete_sleep / len(sleep_records)
            completeness_score += sleep_completeness * 0.5
        
        if hrv_records:
            # HRV数据相对简单，主要看数量
            hrv_completeness = min(len(hrv_records) / 20, 1.0)
            completeness_score += hrv_completeness * 0.5
        
        score_components.append(('completeness', completeness_score * 0.3))
        
        # 3. 时间分布评分 (20%)
        distribution_score = 0.0
        if sleep_records:
            sleep_dates = [r.date.date() for r in sleep_records]
            if len(set(sleep_dates)) > 1:
                date_range_days = (max(sleep_dates) - min(sleep_dates)).days + 1
                coverage_ratio = len(set(sleep_dates)) / date_range_days
                distribution_score += coverage_ratio * 0.5
        
        if hrv_records:
            hrv_dates = [r.timestamp.date() for r in hrv_records]
            if len(set(hrv_dates)) > 1:
                date_range_days = (max(hrv_dates) - min(hrv_dates)).days + 1
                coverage_ratio = len(set(hrv_dates)) / date_range_days
                distribution_score += coverage_ratio * 0.5
        
        score_components.append(('distribution', distribution_score * 0.2))
        
        # 4. 基线计算成功率评分 (10%)
        success_score = 0.0
        if result.sleep_baseline_hours is not None:
            success_score += 0.3
        if result.sleep_baseline_eff is not None:
            success_score += 0.2
        if result.hrv_baseline_mu is not None:
            success_score += 0.3
        if result.rest_baseline_ratio is not None:
            success_score += 0.2
            
        score_components.append(('success', success_score * 0.1))
        
        # 计算总分
        total_score = sum(score for _, score in score_components)
        
        return round(min(total_score, 1.0), 3)
    
    def get_baseline_adjustment_factors(self, baseline: BaselineResult) -> Dict[str, float]:
        """获取基线调整因子，用于动态调整readiness阈值"""
        factors = {}
        
        # 睡眠调整因子
        if baseline.sleep_baseline_hours is not None:
            # 基于个人基线调整睡眠时长阈值
            if baseline.sleep_baseline_hours < 6.5:
                factors['sleep_duration_factor'] = 0.9  # 短睡眠者，降低阈值
            elif baseline.sleep_baseline_hours > 8.5:
                factors['sleep_duration_factor'] = 1.1  # 长睡眠者，提高阈值
            else:
                factors['sleep_duration_factor'] = 1.0
        
        # HRV调整因子
        if baseline.hrv_baseline_mu is not None:
            # 基于HRV基线调整变化敏感度
            if baseline.hrv_baseline_mu < 25:
                factors['hrv_sensitivity_factor'] = 1.2  # 低HRV者更敏感
            elif baseline.hrv_baseline_mu > 60:
                factors['hrv_sensitivity_factor'] = 0.8  # 高HRV者不敏感
            else:
                factors['hrv_sensitivity_factor'] = 1.0
        
        return factors