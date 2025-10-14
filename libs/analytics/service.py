"""基线计算服务接口

提供统一的基线计算服务接口，对接readiness模块。
负责数据预处理、基线计算和结果格式化。
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from .models import SleepRecord, HRVRecord, BaselineResult, validate_health_records
from .calculator import PersonalBaselineCalculator
from .storage import BaselineStorage, get_default_storage, SQLAlchemyBaselineStorage
from .healthkit_integration import parse_healthkit_api_data
from .default_baselines import get_default_baseline, create_default_baseline_result


def compute_personal_baseline(user_id: str, 
                            sleep_data: List[Dict[str, Any]], 
                            hrv_data: List[Dict[str, Any]],
                            storage: Optional[BaselineStorage] = None) -> Dict[str, Any]:
    """计算个人基线的主要接口
    
    Args:
        user_id: 用户ID
        sleep_data: 睡眠数据列表 (来自HealthKit)
        hrv_data: HRV数据列表 (来自HealthKit)
        storage: 可选的存储后端
    
    Returns:
        包含基线计算结果和状态信息的字典
    """
    
    try:
        # 1. 数据预处理和验证
        sleep_records = _parse_sleep_data(sleep_data)
        hrv_records = _parse_hrv_data(hrv_data)
        
        # 验证数据质量
        validation = validate_health_records(sleep_records, hrv_records)
        if validation['issues']:
            print(f"数据质量警告: {', '.join(validation['issues'])}")
        
        # 2. 计算基线
        calculator = PersonalBaselineCalculator()
        baseline_result = calculator.calculate_baseline(user_id, sleep_records, hrv_records)
        
        # 3. 检查结果有效性
        if not baseline_result.is_valid():
            return {
                'status': 'failed',
                'error': 'insufficient_data',
                'message': f'数据不足以计算可靠基线，质量评分: {baseline_result.data_quality_score}',
                'validation': validation,
                'baseline': None
            }
        
        # 4. 保存基线数据（如果提供了存储后端）
        if storage:
            try:
                storage.save_baseline(baseline_result)
            except Exception as e:
                print(f"保存基线数据失败: {e}")
        
        # 5. 返回结果
        return {
            'status': 'success',
            'user_id': user_id,
            'baseline': baseline_result.to_dict(),
            'readiness_payload': baseline_result.to_readiness_payload(),
            'data_quality': baseline_result.data_quality_score,
            'validation': validation,
            'adjustment_factors': calculator.get_baseline_adjustment_factors(baseline_result),
            'message': f'基线计算成功，质量评分: {baseline_result.data_quality_score}'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f'基线计算过程中发生错误: {str(e)}',
            'baseline': None
        }


def get_user_baseline(user_id: str, storage: BaselineStorage) -> Optional[BaselineResult]:
    """获取用户的现有基线数据"""
    try:
        return storage.get_baseline(user_id)
    except Exception as e:
        print(f"获取用户{user_id}基线数据失败: {e}")
        return None


# ====== 基线更新接口 ======

def update_baseline_smart(user_id: str,
                         sleep_data: List[Dict[str, Any]],
                         hrv_data: List[Dict[str, Any]], 
                         storage: BaselineStorage) -> Dict[str, Any]:
    """智能更新基线（推荐接口）
    
    自动判断需要增量更新（7天）还是完整更新（30天）
    
    Args:
        user_id: 用户ID
        sleep_data: 睡眠数据（7-30天）
        hrv_data: HRV数据
        storage: 存储后端
    
    Returns:
        更新结果信息
    """
    from .updater import BaselineUpdater
    
    updater = BaselineUpdater(storage)
    return updater.smart_update(user_id, sleep_data, hrv_data)


def update_baseline_incremental(user_id: str,
                               recent_sleep_data: List[Dict[str, Any]],
                               recent_hrv_data: List[Dict[str, Any]],
                               storage: BaselineStorage) -> Dict[str, Any]:
    """7天增量更新基线
    
    Args:
        user_id: 用户ID
        recent_sleep_data: 最近7天的睡眠数据
        recent_hrv_data: 最近7天的HRV数据
        storage: 存储后端
    
    Returns:
        增量更新结果
    """
    from .updater import BaselineUpdater
    
    updater = BaselineUpdater(storage)
    return updater.perform_incremental_update(user_id, recent_sleep_data, recent_hrv_data)


def update_baseline_full(user_id: str,
                        full_sleep_data: List[Dict[str, Any]],
                        full_hrv_data: List[Dict[str, Any]],
                        storage: BaselineStorage) -> Dict[str, Any]:
    """30天完整更新基线
    
    Args:
        user_id: 用户ID
        full_sleep_data: 最近30天的完整睡眠数据
        full_hrv_data: 最近30天的完整HRV数据
        storage: 存储后端
    
    Returns:
        完整更新结果
    """
    from .updater import BaselineUpdater
    
    updater = BaselineUpdater(storage)
    return updater.perform_full_update(user_id, full_sleep_data, full_hrv_data)


def check_baseline_update_needed(user_id: str, storage: BaselineStorage) -> Dict[str, Any]:
    """检查用户是否需要更新基线
    
    Args:
        user_id: 用户ID
        storage: 存储后端
    
    Returns:
        更新检查结果
    """
    from .updater import BaselineUpdater
    
    updater = BaselineUpdater(storage)
    return updater.check_update_needed(user_id)


def get_baseline_update_schedule(user_id: str, storage: BaselineStorage) -> Dict[str, Any]:
    """获取用户的基线更新计划
    
    Args:
        user_id: 用户ID
        storage: 存储后端
    
    Returns:
        更新计划信息
    """
    from .updater import BaselineUpdater
    
    updater = BaselineUpdater(storage)
    return updater.get_update_schedule(user_id)


# 向后兼容的接口
def update_baseline_if_needed(user_id: str,
                             new_sleep_data: List[Dict[str, Any]],
                             new_hrv_data: List[Dict[str, Any]], 
                             storage: BaselineStorage,
                             force_update: bool = False) -> Dict[str, Any]:
    """根据新数据智能更新基线（向后兼容接口）
    
    推荐使用 update_baseline_smart() 替代此方法
    """
    if force_update:
        return update_baseline_full(user_id, new_sleep_data, new_hrv_data, storage)
    else:
        return update_baseline_smart(user_id, new_sleep_data, new_hrv_data, storage)


def _parse_sleep_data(sleep_data: List[Dict[str, Any]]) -> List[SleepRecord]:
    """解析睡眠数据"""
    records = []
    
    for data in sleep_data:
        try:
            # 处理日期格式
            if 'date' in data and isinstance(data['date'], str):
                data['date'] = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
            elif 'date' not in data:
                continue  # 跳过没有日期的记录
            
            # 验证必需字段
            required_fields = ['sleep_duration_hours', 'sleep_efficiency']
            if not all(field in data for field in required_fields):
                continue
            
            # 创建记录
            record = SleepRecord.from_dict(data)
            records.append(record)
            
        except Exception as e:
            print(f"解析睡眠数据失败: {e}, 数据: {data}")
            continue
    
    return records


def _parse_hrv_data(hrv_data: List[Dict[str, Any]]) -> List[HRVRecord]:
    """解析HRV数据"""
    records = []
    
    for data in hrv_data:
        try:
            # 处理时间戳格式
            if 'timestamp' in data and isinstance(data['timestamp'], str):
                data['timestamp'] = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
            elif 'timestamp' not in data:
                continue
            
            # 验证必需字段
            if 'sdnn_value' not in data:
                continue
            
            # 处理不同的HRV字段名
            if 'hrv_value' in data and 'sdnn_value' not in data:
                data['sdnn_value'] = data['hrv_value']
            
            record = HRVRecord.from_dict(data)
            records.append(record)
            
        except Exception as e:
            print(f"解析HRV数据失败: {e}, 数据: {data}")
            continue
    
    return records


# ====== HealthKit专用接口 ======

def compute_baseline_from_healthkit_data(user_id: str, 
                                       healthkit_sleep_data: List[Dict[str, Any]], 
                                       healthkit_hrv_data: List[Dict[str, Any]],
                                       storage: Optional[BaselineStorage] = None,
                                       sleeper_type: str = "normal_sleeper",
                                       hrv_type: str = "normal_hrv") -> Dict[str, Any]:
    """从HealthKit API数据计算基线（推荐接口）
    
    这是专门为HealthKit数据设计的接口，会自动处理数据格式转换。
    
    Args:
        user_id: 用户ID
        healthkit_sleep_data: HealthKit睡眠数据（分钟格式）
        healthkit_hrv_data: HealthKit HRV数据（SDNN格式）
        storage: 可选的存储后端
    
    Returns:
        基线计算结果
    """
    
    try:
        # 使用HealthKit集成模块解析数据
        sleep_records, hrv_records = parse_healthkit_api_data(healthkit_sleep_data, healthkit_hrv_data)
        
        # 验证数据量 - 少于30天使用默认基线
        total_sleep_days = len(sleep_records)
        total_hrv_records = len(hrv_records)
        
        if total_sleep_days < 30 or total_hrv_records < 40:
            # 数据不足30天，使用默认基线
            default_baseline = create_default_baseline_result(user_id, sleeper_type, hrv_type)
            
            # 保存默认基线
            if storage:
                try:
                    storage.save_baseline(default_baseline)
                except Exception as e:
                    print(f"保存默认基线失败: {e}")
            
            return {
                'status': 'success_with_defaults',
                'baseline_source': 'default_profile',
                'sleeper_type': sleeper_type,
                'hrv_type': hrv_type,
                'user_id': user_id,
                'baseline': default_baseline.to_dict(),
                'readiness_payload': default_baseline.to_readiness_payload(),
                'data_quality': 0.8,  # 默认基线质量
                'data_summary': {
                    'sleep_records_available': total_sleep_days,
                    'hrv_records_available': total_hrv_records,
                    'baseline_strategy': 'default_profile'
                },
                'recommendations': [
                    f'当前使用{sleeper_type}和{hrv_type}默认基线',
                    f'继续记录数据，30天后可计算个性化基线',
                    f'已有{total_sleep_days}天睡眠数据，还需{30-total_sleep_days}天'
                ],
                'message': f'数据不足30天，使用{sleeper_type}默认基线，质量评分: 0.8'
            }
        
        # 执行基线计算
        calculator = PersonalBaselineCalculator()
        baseline_result = calculator.calculate_baseline(user_id, sleep_records, hrv_records)
        
        # 检查结果有效性
        if not baseline_result.is_valid():
            return {
                'status': 'failed', 
                'error': 'low_quality',
                'message': f'基线质量不足，评分: {baseline_result.data_quality_score:.2f}',
                'data_summary': {
                    'sleep_records': len(sleep_records),
                    'hrv_records': len(hrv_records),
                    'data_quality_score': baseline_result.data_quality_score
                },
                'baseline': None
            }
        
        # 保存基线数据
        if storage:
            try:
                storage.save_baseline(baseline_result)
            except Exception as e:
                print(f"保存基线数据失败: {e}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'baseline': baseline_result.to_dict(),
            'readiness_payload': baseline_result.to_readiness_payload(),
            'data_quality': baseline_result.data_quality_score,
            'data_summary': {
                'sleep_records_parsed': len(sleep_records),
                'hrv_records_parsed': len(hrv_records),
                'sleep_date_range': f"{sleep_records[0].date.date()} to {sleep_records[-1].date.date()}" if sleep_records else None,
                'hrv_date_range': f"{hrv_records[0].timestamp.date()} to {hrv_records[-1].timestamp.date()}" if hrv_records else None
            },
            'recommendations': _generate_baseline_recommendations(baseline_result),
            'message': f'HealthKit基线计算成功，质量评分: {baseline_result.data_quality_score:.2f}'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f'HealthKit基线计算失败: {str(e)}',
            'baseline': None
        }

def _generate_baseline_recommendations(baseline: BaselineResult) -> List[str]:
    """根据基线结果生成建议"""
    recommendations = []
    
    # 睡眠建议
    if baseline.sleep_baseline_hours:
        if baseline.sleep_baseline_hours < 6.5:
            recommendations.append(f"您的睡眠基线较短({baseline.sleep_baseline_hours:.1f}h)，建议逐步增加睡眠时间")
        elif baseline.sleep_baseline_hours > 9.0:
            recommendations.append(f"您的睡眠基线较长({baseline.sleep_baseline_hours:.1f}h)，注意睡眠质量")
    
    # HRV建议  
    if baseline.hrv_baseline_mu:
        if baseline.hrv_baseline_mu < 25:
            recommendations.append(f"您的HRV基线较低({baseline.hrv_baseline_mu:.1f}ms)，建议加强恢复管理")
        elif baseline.hrv_baseline_mu > 60:
            recommendations.append(f"您的HRV基线很好({baseline.hrv_baseline_mu:.1f}ms)，继续保持")
    
    # 数据质量建议
    if baseline.data_quality_score < 0.8:
        recommendations.append("建议继续记录更多数据，以提高基线准确性")
    
    if not recommendations:
        recommendations.append("您的个人基线已建立，系统将为您提供个性化的准备度评估")
    
    return recommendations

# 便捷函数：直接从HealthKit XML导出计算基线
def compute_baseline_from_healthkit_xml(user_id: str, xml_file_path: str, storage: Optional[BaselineStorage] = None) -> Dict[str, Any]:
    """从HealthKit XML导出文件计算基线
    
    Args:
        user_id: 用户ID
        xml_file_path: HealthKit导出的XML文件路径
        storage: 可选的存储后端
    
    Returns:
        基线计算结果
    """
    
    try:
        from .healthkit_integration import parse_healthkit_export_xml
        
        # 解析XML文件
        sleep_records, hrv_records = parse_healthkit_export_xml(xml_file_path)
        
        # 执行基线计算
        calculator = PersonalBaselineCalculator()
        baseline_result = calculator.calculate_baseline(user_id, sleep_records, hrv_records)
        
        # 处理结果
        if not baseline_result.is_valid():
            return {
                'status': 'failed',
                'error': 'insufficient_data_from_xml',
                'message': f'XML文件中的数据不足以计算基线',
                'baseline': None
            }
        
        # 保存基线
        if storage:
            storage.save_baseline(baseline_result)
        
        return {
            'status': 'success',
            'user_id': user_id,
            'baseline': baseline_result.to_dict(),
            'readiness_payload': baseline_result.to_readiness_payload(),
            'data_source': 'healthkit_xml_export',
            'message': f'从HealthKit导出计算基线成功'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f'XML文件解析失败: {str(e)}'
        }

# 便捷函数：直接从HealthKit格式计算基线（向后兼容）
def compute_baseline_from_healthkit(user_id: str, healthkit_export: Dict[str, Any]) -> Dict[str, Any]:
    """从HealthKit导出数据直接计算基线
    
    Args:
        user_id: 用户ID
        healthkit_export: HealthKit导出的数据字典
    
    Returns:
        基线计算结果
    """
    
    try:
        # 提取睡眠数据
        sleep_data = []
        if 'sleep_analysis' in healthkit_export:
            sleep_data = healthkit_export['sleep_analysis']
        elif 'Record' in healthkit_export:
            # 处理XML导出格式
            sleep_data = [r for r in healthkit_export['Record'] 
                         if r.get('type') == 'HKCategoryTypeIdentifierSleepAnalysis']
        
        # 提取HRV数据
        hrv_data = []
        if 'heart_rate_variability' in healthkit_export:
            hrv_data = healthkit_export['heart_rate_variability']
        elif 'Record' in healthkit_export:
            hrv_data = [r for r in healthkit_export['Record']
                       if r.get('type') == 'HKQuantityTypeIdentifierHeartRateVariabilitySDNN']
        
        return compute_personal_baseline(user_id, sleep_data, hrv_data)
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f'从HealthKit数据计算基线失败: {str(e)}'
        }