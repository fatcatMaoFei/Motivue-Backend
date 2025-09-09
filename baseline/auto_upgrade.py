# -*- coding: utf-8 -*-
"""基线自动升级模块

负责检测用户数据量达到30天时，自动从默认基线升级到个人基线
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import logging

from .models import BaselineResult
from .service import compute_baseline_from_healthkit_data
from .storage import BaselineStorage

logger = logging.getLogger(__name__)

@dataclass
class DataSummary:
    """用户数据摘要"""
    user_id: str
    total_sleep_days: int
    total_hrv_records: int
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    data_quality_estimate: float = 0.0
    
    @property
    def is_sufficient_for_personal_baseline(self) -> bool:
        """检查数据是否足够计算个人基线"""
        return self.total_sleep_days >= 30 and self.total_hrv_records >= 40


class BaselineAutoUpgrade:
    """个人基线自动升级管理器"""
    
    def __init__(self, storage: BaselineStorage, data_service=None, message_queue=None):
        self.storage = storage
        self.data_service = data_service
        self.message_queue = message_queue
        self.logger = logging.getLogger(__name__)
    
    async def check_upgrade_eligibility(self, user_id: str) -> Dict[str, Any]:
        """检查用户是否可以升级到个人基线
        
        Args:
            user_id: 用户ID
            
        Returns:
            升级资格检查结果
        """
        try:
            # 获取当前基线
            current_baseline = self.storage.get_baseline(user_id)
            
            if not current_baseline:
                return {
                    'eligible': False,
                    'reason': 'no_baseline',
                    'message': '用户没有基线数据'
                }
            
            # 检查是否已经是个人基线
            if hasattr(current_baseline, 'baseline_source'):
                if current_baseline.baseline_source == 'personal':
                    return {
                        'eligible': False,
                        'reason': 'already_personal',
                        'message': '已经使用个人基线'
                    }
            
            # 如果没有baseline_source属性，通过数据质量判断
            if current_baseline.data_quality_score >= 0.9:
                return {
                    'eligible': False, 
                    'reason': 'already_personal',
                    'message': '已经使用个人基线（基于质量评分判断）'
                }
            
            # 检查历史数据量
            if self.data_service:
                data_summary = await self._get_data_summary(user_id)
            else:
                # 如果没有数据服务，使用模拟数据进行测试
                data_summary = await self._simulate_data_summary(user_id)
            
            if data_summary.is_sufficient_for_personal_baseline:
                return {
                    'eligible': True,
                    'sleep_days': data_summary.total_sleep_days,
                    'hrv_count': data_summary.total_hrv_records,
                    'estimated_quality': data_summary.data_quality_estimate,
                    'upgrade_type': 'personal_baseline',
                    'message': f'数据充足，可升级到个人基线（{data_summary.total_sleep_days}天睡眠数据）'
                }
            
            return {
                'eligible': False,
                'reason': 'insufficient_data',
                'sleep_days': data_summary.total_sleep_days,
                'hrv_count': data_summary.total_hrv_records,
                'needed': {
                    'sleep_days': max(0, 30 - data_summary.total_sleep_days),
                    'hrv_count': max(0, 40 - data_summary.total_hrv_records)
                },
                'message': f'数据不足，还需{max(0, 30 - data_summary.total_sleep_days)}天睡眠数据'
            }
            
        except Exception as e:
            self.logger.error(f"检查用户{user_id}升级资格失败: {e}")
            return {
                'eligible': False,
                'reason': 'error',
                'error': str(e),
                'message': f'检查失败: {str(e)}'
            }
    
    async def auto_upgrade_to_personal(self, user_id: str) -> Dict[str, Any]:
        """自动升级到个人基线
        
        Args:
            user_id: 用户ID
            
        Returns:
            升级结果
        """
        try:
            # 检查升级资格
            eligibility = await self.check_upgrade_eligibility(user_id)
            if not eligibility['eligible']:
                return {
                    'status': 'skipped',
                    'reason': eligibility['reason'],
                    'message': eligibility['message']
                }
            
            # 获取完整历史数据
            if self.data_service:
                full_data = await self._get_full_history_data(user_id)
            else:
                # 测试模式：使用模拟数据
                full_data = await self._simulate_full_data(user_id)
            
            # 计算个人基线
            result = compute_baseline_from_healthkit_data(
                user_id=user_id,
                healthkit_sleep_data=full_data['sleep'],
                healthkit_hrv_data=full_data['hrv'],
                storage=self.storage
            )
            
            if result['status'] == 'success':
                # 标记为个人基线
                baseline = self.storage.get_baseline(user_id)
                if baseline:
                    baseline.baseline_source = 'personal'
                    baseline.update_type = 'auto_upgrade'
                    baseline.last_full_update = datetime.now()
                    self.storage.save_baseline(baseline)
                
                # 触发CPT表更新
                if self.message_queue:
                    await self._trigger_cpt_update(user_id, result['baseline'])
                
                # 记录升级日志
                await self._log_upgrade_event(user_id, 'default_to_personal', result)
                
                return {
                    'status': 'upgraded',
                    'from': 'default',
                    'to': 'personal',
                    'data_quality': result['data_quality'],
                    'sleep_days': eligibility['sleep_days'],
                    'hrv_count': eligibility['hrv_count'],
                    'message': f'成功升级到个人基线，质量评分: {result["data_quality"]:.2f}'
                }
            
            return {
                'status': 'failed',
                'error': result.get('error', 'calculation_failed'),
                'message': result.get('message', '个人基线计算失败')
            }
            
        except Exception as e:
            self.logger.error(f"用户{user_id}自动升级失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'message': f'升级过程发生错误: {str(e)}'
            }
    
    async def batch_check_upgrades(self, user_ids: List[str]) -> Dict[str, Any]:
        """批量检查用户升级资格
        
        Args:
            user_ids: 用户ID列表
            
        Returns:
            批量检查结果
        """
        results = {
            'eligible_users': [],
            'already_personal': [],
            'insufficient_data': [],
            'errors': []
        }
        
        # 并发检查（限制并发数避免过载）
        semaphore = asyncio.Semaphore(10)
        
        async def check_single_user(user_id):
            async with semaphore:
                try:
                    result = await self.check_upgrade_eligibility(user_id)
                    
                    if result['eligible']:
                        results['eligible_users'].append({
                            'user_id': user_id,
                            'sleep_days': result['sleep_days'],
                            'hrv_count': result['hrv_count']
                        })
                    elif result['reason'] == 'already_personal':
                        results['already_personal'].append(user_id)
                    elif result['reason'] == 'insufficient_data':
                        results['insufficient_data'].append({
                            'user_id': user_id,
                            'sleep_days': result['sleep_days'],
                            'needed': result['needed']
                        })
                    else:
                        results['errors'].append({
                            'user_id': user_id,
                            'reason': result['reason'],
                            'error': result.get('error')
                        })
                        
                except Exception as e:
                    results['errors'].append({
                        'user_id': user_id,
                        'error': str(e)
                    })
        
        # 执行并发检查
        await asyncio.gather(*[check_single_user(uid) for uid in user_ids])
        
        results['summary'] = {
            'total_checked': len(user_ids),
            'eligible_count': len(results['eligible_users']),
            'already_personal_count': len(results['already_personal']),
            'insufficient_data_count': len(results['insufficient_data']),
            'error_count': len(results['errors'])
        }
        
        return results
    
    async def batch_auto_upgrade(self, user_ids: List[str]) -> Dict[str, Any]:
        """批量自动升级用户
        
        Args:
            user_ids: 用户ID列表
            
        Returns:
            批量升级结果
        """
        results = {
            'upgraded': [],
            'skipped': [],
            'failed': [],
            'errors': []
        }
        
        # 限制并发数
        semaphore = asyncio.Semaphore(5)
        
        async def upgrade_single_user(user_id):
            async with semaphore:
                try:
                    result = await self.auto_upgrade_to_personal(user_id)
                    
                    if result['status'] == 'upgraded':
                        results['upgraded'].append({
                            'user_id': user_id,
                            'data_quality': result['data_quality'],
                            'sleep_days': result['sleep_days']
                        })
                    elif result['status'] == 'skipped':
                        results['skipped'].append({
                            'user_id': user_id,
                            'reason': result['reason']
                        })
                    elif result['status'] == 'failed':
                        results['failed'].append({
                            'user_id': user_id,
                            'error': result['error']
                        })
                    else:
                        results['errors'].append({
                            'user_id': user_id,
                            'error': result.get('error', 'unknown_error')
                        })
                        
                except Exception as e:
                    results['errors'].append({
                        'user_id': user_id,
                        'error': str(e)
                    })
        
        # 执行批量升级
        await asyncio.gather(*[upgrade_single_user(uid) for uid in user_ids])
        
        results['summary'] = {
            'total_processed': len(user_ids),
            'upgraded_count': len(results['upgraded']),
            'skipped_count': len(results['skipped']),
            'failed_count': len(results['failed']),
            'error_count': len(results['errors'])
        }
        
        return results
    
    async def _get_data_summary(self, user_id: str) -> DataSummary:
        """获取用户数据摘要（通过数据服务）"""
        if not self.data_service:
            return await self._simulate_data_summary(user_id)
        
        # 调用数据服务API
        summary_data = await self.data_service.get_user_data_summary(user_id)
        
        return DataSummary(
            user_id=user_id,
            total_sleep_days=summary_data.get('total_sleep_days', 0),
            total_hrv_records=summary_data.get('total_hrv_records', 0),
            date_range_start=summary_data.get('date_range_start'),
            date_range_end=summary_data.get('date_range_end'),
            data_quality_estimate=summary_data.get('data_quality_estimate', 0.0)
        )
    
    async def _get_full_history_data(self, user_id: str) -> Dict[str, List]:
        """获取用户完整历史数据"""
        if not self.data_service:
            return await self._simulate_full_data(user_id)
        
        # 获取最近30天数据
        return await self.data_service.get_user_history(user_id, days=30)
    
    async def _simulate_data_summary(self, user_id: str) -> DataSummary:
        """模拟数据摘要（测试用）"""
        # 模拟用户已有35天数据，符合升级条件
        return DataSummary(
            user_id=user_id,
            total_sleep_days=35,
            total_hrv_records=50,
            data_quality_estimate=0.85
        )
    
    async def _simulate_full_data(self, user_id: str) -> Dict[str, List]:
        """模拟完整数据（测试用）"""
        from .healthkit_integration import create_sample_healthkit_data
        
        # 创建30天测试数据
        sleep_data, hrv_data = create_sample_healthkit_data(
            start_date=datetime.now() - timedelta(days=30),
            days=30,
            user_id=user_id
        )
        
        return {
            'sleep': sleep_data,
            'hrv': hrv_data
        }
    
    async def _trigger_cpt_update(self, user_id: str, baseline: Dict[str, Any]):
        """触发readiness服务的CPT表更新"""
        if not self.message_queue:
            self.logger.warning(f"用户{user_id}基线升级完成，但无消息队列配置，跳过CPT更新通知")
            return
        
        # 发送消息到readiness服务
        message = {
            'event': 'baseline_upgraded',
            'user_id': user_id,
            'baseline': baseline,
            'upgrade_type': 'default_to_personal',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            await self.message_queue.publish('readiness.baseline_upgraded', message)
            self.logger.info(f"已发送用户{user_id}基线升级通知到readiness服务")
        except Exception as e:
            self.logger.error(f"发送用户{user_id}基线升级通知失败: {e}")
    
    async def _log_upgrade_event(self, user_id: str, upgrade_type: str, result: Dict[str, Any]):
        """记录升级事件日志"""
        log_entry = {
            'user_id': user_id,
            'event': 'baseline_upgrade',
            'upgrade_type': upgrade_type,
            'timestamp': datetime.now().isoformat(),
            'data_quality': result.get('data_quality'),
            'baseline_data': result.get('baseline'),
            'status': 'success'
        }
        
        # 记录到日志系统
        self.logger.info(f"用户基线升级: {log_entry}")
        
        # 可选：保存到数据库的升级历史表
        if hasattr(self.storage, 'save_upgrade_log'):
            try:
                await self.storage.save_upgrade_log(log_entry)
            except Exception as e:
                self.logger.warning(f"保存升级日志失败: {e}")


# 便捷函数
async def check_user_upgrade_eligibility(user_id: str, storage: BaselineStorage) -> Dict[str, Any]:
    """检查单个用户升级资格的便捷函数"""
    upgrader = BaselineAutoUpgrade(storage)
    return await upgrader.check_upgrade_eligibility(user_id)

async def auto_upgrade_user(user_id: str, storage: BaselineStorage, 
                           data_service=None, message_queue=None) -> Dict[str, Any]:
    """自动升级单个用户的便捷函数"""
    upgrader = BaselineAutoUpgrade(storage, data_service, message_queue)
    return await upgrader.auto_upgrade_to_personal(user_id)