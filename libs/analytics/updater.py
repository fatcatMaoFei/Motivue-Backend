# -*- coding: utf-8 -*-
"""基线更新模块

负责基线的增量更新（7天小更新）和完整重算（30天大更新）
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import statistics

from .models import SleepRecord, HRVRecord, BaselineResult
from .calculator import PersonalBaselineCalculator
from .storage import BaselineStorage


@dataclass
class UpdateStrategy:
    """更新策略配置"""
    incremental_days: int = 7      # 增量更新周期（天）
    full_update_days: int = 30     # 完整更新周期（天）
    incremental_weight: float = 0.3  # 新数据在增量更新中的权重
    min_data_quality: float = 0.7   # 触发更新的最低质量阈值
    

class BaselineUpdater:
    """基线更新器"""
    
    def __init__(self, storage: BaselineStorage, strategy: UpdateStrategy = None):
        self.storage = storage
        self.strategy = strategy or UpdateStrategy()
        self.calculator = PersonalBaselineCalculator()
    
    def check_update_needed(self, user_id: str) -> Dict[str, Any]:
        """检查是否需要更新基线
        
        Returns:
            更新检查结果，包含更新类型和原因
        """
        try:
            existing_baseline = self.storage.get_baseline(user_id)
            
            if not existing_baseline:
                return {
                    'needs_update': True,
                    'update_type': 'initial',
                    'reason': '用户首次计算基线',
                    'days_since_update': None
                }
            
            # 计算距离上次更新的天数
            days_since_update = (datetime.now() - existing_baseline.created_at).days
            
            # 检查数据质量
            quality_issue = existing_baseline.data_quality_score < self.strategy.min_data_quality
            
            # 决定更新类型
            if days_since_update >= self.strategy.full_update_days:
                return {
                    'needs_update': True,
                    'update_type': 'full',
                    'reason': f'超过{self.strategy.full_update_days}天未完整更新',
                    'days_since_update': days_since_update,
                    'quality_issue': quality_issue
                }
            
            elif days_since_update >= self.strategy.incremental_days or quality_issue:
                reasons = []
                if days_since_update >= self.strategy.incremental_days:
                    reasons.append(f'超过{self.strategy.incremental_days}天未增量更新')
                if quality_issue:
                    reasons.append(f'数据质量偏低({existing_baseline.data_quality_score:.2f})')
                
                return {
                    'needs_update': True,
                    'update_type': 'incremental',
                    'reason': ', '.join(reasons),
                    'days_since_update': days_since_update,
                    'quality_issue': quality_issue
                }
            
            else:
                return {
                    'needs_update': False,
                    'update_type': None,
                    'reason': '基线数据仍然有效',
                    'days_since_update': days_since_update,
                    'next_incremental_in': self.strategy.incremental_days - days_since_update,
                    'next_full_in': self.strategy.full_update_days - days_since_update
                }
                
        except Exception as e:
            return {
                'needs_update': True,
                'update_type': 'error_recovery',
                'reason': f'检查更新状态时发生错误: {str(e)}',
                'error': str(e)
            }
    
    def perform_incremental_update(self, user_id: str, 
                                 new_sleep_data: List[Dict[str, Any]], 
                                 new_hrv_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行7天增量更新
        
        Args:
            user_id: 用户ID
            new_sleep_data: 最近7天的新睡眠数据
            new_hrv_data: 最近7天的新HRV数据
        
        Returns:
            增量更新结果
        """
        try:
            # 获取现有基线
            existing_baseline = self.storage.get_baseline(user_id)
            if not existing_baseline:
                return {
                    'status': 'error',
                    'message': '找不到现有基线，请先执行完整计算',
                    'suggestion': 'perform_full_update'
                }
            
            # 解析新数据
            from .service import _parse_sleep_data, _parse_hrv_data
            new_sleep_records = _parse_sleep_data(new_sleep_data)
            new_hrv_records = _parse_hrv_data(new_hrv_data)
            
            if not new_sleep_records and not new_hrv_records:
                return {
                    'status': 'skipped',
                    'message': '没有新数据可用于增量更新',
                    'existing_baseline': existing_baseline.to_dict()
                }
            
            # 计算新数据的统计指标
            new_stats = self._calculate_incremental_stats(new_sleep_records, new_hrv_records)
            
            # 使用加权平均更新基线
            updated_baseline = self._blend_baseline_with_new_data(
                existing_baseline, new_stats, self.strategy.incremental_weight
            )
            
            # 更新元数据
            updated_baseline.created_at = datetime.now()
            updated_baseline.update_type = 'incremental'
            updated_baseline.last_incremental_update = datetime.now()
            
            # 保存更新后的基线
            self.storage.save_baseline(updated_baseline)
            
            return {
                'status': 'success',
                'update_type': 'incremental',
                'user_id': user_id,
                'baseline': updated_baseline.to_dict(),
                'readiness_payload': updated_baseline.to_readiness_payload(),
                'data_quality': updated_baseline.data_quality_score,
                'update_summary': {
                    'new_sleep_records': len(new_sleep_records),
                    'new_hrv_records': len(new_hrv_records),
                    'blend_weight': self.strategy.incremental_weight,
                    'previous_baseline': existing_baseline.to_dict()
                },
                'changes': self._calculate_baseline_changes(existing_baseline, updated_baseline),
                'message': f'增量更新成功，使用{len(new_sleep_records)}天睡眠数据和{len(new_hrv_records)}个HRV记录'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'update_type': 'incremental',
                'error': str(e),
                'message': f'增量更新失败: {str(e)}'
            }
    
    def perform_full_update(self, user_id: str,
                          sleep_data: List[Dict[str, Any]], 
                          hrv_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行30天完整更新
        
        Args:
            user_id: 用户ID
            sleep_data: 最近30天的完整睡眠数据
            hrv_data: 最近30天的完整HRV数据
        
        Returns:
            完整更新结果
        """
        try:
            # 获取现有基线（用于对比）
            existing_baseline = self.storage.get_baseline(user_id)
            
            # 重新计算完整基线
            from .service import compute_personal_baseline
            full_result = compute_personal_baseline(user_id, sleep_data, hrv_data, self.storage)
            
            if full_result['status'] != 'success':
                return {
                    'status': 'error',
                    'update_type': 'full',
                    'message': f"完整更新失败: {full_result.get('message', 'unknown error')}",
                    'error': full_result.get('error', 'calculation_failed'),
                    'fallback_baseline': existing_baseline.to_dict() if existing_baseline else None
                }
            
            # 更新元数据
            new_baseline = self.storage.get_baseline(user_id)  # 获取刚保存的新基线
            if new_baseline:
                new_baseline.update_type = 'full'
                new_baseline.last_full_update = datetime.now()
                self.storage.save_baseline(new_baseline)
            
            # 计算变化
            changes = {}
            if existing_baseline:
                changes = self._calculate_baseline_changes(existing_baseline, new_baseline)
            
            result = full_result.copy()
            result.update({
                'update_type': 'full',
                'changes': changes,
                'comparison': {
                    'previous_baseline': existing_baseline.to_dict() if existing_baseline else None,
                    'quality_improvement': (
                        new_baseline.data_quality_score - existing_baseline.data_quality_score 
                        if existing_baseline else 0
                    )
                },
                'message': f'30天完整更新成功，质量评分: {full_result["data_quality"]:.2f}'
            })
            
            return result
            
        except Exception as e:
            return {
                'status': 'error',
                'update_type': 'full',
                'error': str(e),
                'message': f'完整更新失败: {str(e)}'
            }
    
    def smart_update(self, user_id: str,
                    sleep_data: List[Dict[str, Any]],
                    hrv_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """智能更新：自动选择增量或完整更新
        
        Args:
            user_id: 用户ID
            sleep_data: 睡眠数据（自动判断是7天还是30天）
            hrv_data: HRV数据
        
        Returns:
            更新结果
        """
        
        # 检查更新需求
        check_result = self.check_update_needed(user_id)
        
        if not check_result['needs_update']:
            return {
                'status': 'skipped',
                'message': check_result['reason'],
                'next_update': {
                    'incremental_in_days': check_result.get('next_incremental_in'),
                    'full_in_days': check_result.get('next_full_in')
                }
            }
        
        update_type = check_result['update_type']
        
        if update_type in ['full', 'initial', 'error_recovery']:
            return self.perform_full_update(user_id, sleep_data, hrv_data)
        elif update_type == 'incremental':
            # 对于增量更新，只使用最近7天的数据
            recent_sleep = self._filter_recent_data(sleep_data, days=7)
            recent_hrv = self._filter_recent_data(hrv_data, days=7)
            return self.perform_incremental_update(user_id, recent_sleep, recent_hrv)
        else:
            return {
                'status': 'error',
                'message': f'未知的更新类型: {update_type}'
            }
    
    def _calculate_incremental_stats(self, sleep_records: List[SleepRecord], 
                                   hrv_records: List[HRVRecord]) -> Dict[str, float]:
        """计算新数据的统计指标"""
        stats = {}
        
        if sleep_records:
            sleep_hours = [r.sleep_duration_hours for r in sleep_records if r.sleep_duration_hours]
            sleep_eff = [r.sleep_efficiency for r in sleep_records if r.sleep_efficiency]
            restorative = [r.restorative_ratio for r in sleep_records if r.restorative_ratio]
            
            if sleep_hours:
                stats['sleep_duration_mean'] = statistics.mean(sleep_hours)
            if sleep_eff:
                stats['sleep_efficiency_mean'] = statistics.mean(sleep_eff)
            if restorative:
                stats['restorative_ratio_mean'] = statistics.mean(restorative)
        
        if hrv_records:
            hrv_values = [r.sdnn_value for r in hrv_records if r.sdnn_value]
            if hrv_values:
                stats['hrv_mean'] = statistics.mean(hrv_values)
                stats['hrv_stdev'] = statistics.stdev(hrv_values) if len(hrv_values) > 1 else 0
        
        return stats
    
    def _blend_baseline_with_new_data(self, existing: BaselineResult, 
                                    new_stats: Dict[str, float], 
                                    new_weight: float) -> BaselineResult:
        """使用加权平均混合现有基线和新数据"""
        old_weight = 1.0 - new_weight
        
        # 创建更新后的基线
        updated = BaselineResult(
            user_id=existing.user_id,
            created_at=datetime.now(),
            
            # 睡眠基线混合
            sleep_baseline_hours=(
                existing.sleep_baseline_hours * old_weight +
                new_stats.get('sleep_duration_mean', existing.sleep_baseline_hours) * new_weight
                if existing.sleep_baseline_hours else new_stats.get('sleep_duration_mean')
            ),
            
            sleep_baseline_eff=(
                existing.sleep_baseline_eff * old_weight +
                new_stats.get('sleep_efficiency_mean', existing.sleep_baseline_eff) * new_weight
                if existing.sleep_baseline_eff else new_stats.get('sleep_efficiency_mean')
            ),
            
            rest_baseline_ratio=(
                existing.rest_baseline_ratio * old_weight +
                new_stats.get('restorative_ratio_mean', existing.rest_baseline_ratio) * new_weight
                if existing.rest_baseline_ratio else new_stats.get('restorative_ratio_mean')
            ),
            
            # HRV基线混合
            hrv_baseline_mu=(
                existing.hrv_baseline_mu * old_weight +
                new_stats.get('hrv_mean', existing.hrv_baseline_mu) * new_weight
                if existing.hrv_baseline_mu else new_stats.get('hrv_mean')
            ),
            
            hrv_baseline_sd=(
                existing.hrv_baseline_sd * old_weight +
                new_stats.get('hrv_stdev', existing.hrv_baseline_sd) * new_weight
                if existing.hrv_baseline_sd else new_stats.get('hrv_stdev')
            ),
            
            # 保持其他属性
            data_quality_score=min(existing.data_quality_score + 0.05, 1.0),  # 略微提升质量分
            sample_days_sleep=existing.sample_days_sleep,
            sample_days_hrv=existing.sample_days_hrv
        )
        
        return updated
    
    def _calculate_baseline_changes(self, old: BaselineResult, 
                                  new: BaselineResult) -> Dict[str, float]:
        """计算基线变化"""
        changes = {}
        
        if old.sleep_baseline_hours and new.sleep_baseline_hours:
            changes['sleep_hours_change'] = new.sleep_baseline_hours - old.sleep_baseline_hours
        
        if old.sleep_baseline_eff and new.sleep_baseline_eff:
            changes['sleep_efficiency_change'] = new.sleep_baseline_eff - old.sleep_baseline_eff
        
        if old.hrv_baseline_mu and new.hrv_baseline_mu:
            changes['hrv_mean_change'] = new.hrv_baseline_mu - old.hrv_baseline_mu
        
        if old.data_quality_score and new.data_quality_score:
            changes['quality_change'] = new.data_quality_score - old.data_quality_score
        
        return changes
    
    def _filter_recent_data(self, data: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
        """过滤出最近N天的数据"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_data = []
        for record in data:
            record_date = None
            
            # 尝试不同的日期字段
            for date_field in ['date', 'timestamp', 'startDate', 'endDate']:
                if date_field in record:
                    try:
                        if isinstance(record[date_field], str):
                            record_date = datetime.fromisoformat(record[date_field].replace('Z', '+00:00'))
                            # 转换为naive datetime进行比较
                            if record_date.tzinfo is not None:
                                record_date = record_date.replace(tzinfo=None)
                        elif isinstance(record[date_field], datetime):
                            record_date = record[date_field]
                            # 确保是naive datetime
                            if record_date.tzinfo is not None:
                                record_date = record_date.replace(tzinfo=None)
                        break
                    except:
                        continue
            
            if record_date and record_date >= cutoff_date:
                recent_data.append(record)
        
        return recent_data
    
    def get_update_schedule(self, user_id: str) -> Dict[str, Any]:
        """获取用户的更新计划"""
        check_result = self.check_update_needed(user_id)
        
        schedule = {
            'user_id': user_id,
            'current_status': 'needs_update' if check_result['needs_update'] else 'up_to_date',
            'recommended_action': check_result.get('update_type', 'none'),
            'reason': check_result['reason']
        }
        
        if not check_result['needs_update']:
            schedule.update({
                'next_incremental_update': {
                    'in_days': check_result.get('next_incremental_in'),
                    'date': (datetime.now() + timedelta(days=check_result.get('next_incremental_in', 0))).isoformat()
                },
                'next_full_update': {
                    'in_days': check_result.get('next_full_in'), 
                    'date': (datetime.now() + timedelta(days=check_result.get('next_full_in', 0))).isoformat()
                }
            })
        
        return schedule