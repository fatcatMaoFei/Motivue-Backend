#!/usr/bin/env python3
"""
HealthKit数据集成模块

提供从苹果健康app数据格式转换为baseline模块数据格式的功能。
支持XML导出解析和HealthKit API数据转换。
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from .models import SleepRecord, HRVRecord

class HealthKitDataParser:
    """苹果健康数据解析器"""
    
    def __init__(self):
        self.sleep_stage_mapping = {
            # 苹果健康睡眠阶段值映射
            'HKCategoryValueSleepAnalysisAsleepDeep': 'deep',
            'HKCategoryValueSleepAnalysisAsleepREM': 'rem', 
            'HKCategoryValueSleepAnalysisAsleepCore': 'core',
            'HKCategoryValueSleepAnalysisAwake': 'awake',
            'HKCategoryValueSleepAnalysisInBed': 'in_bed',
            'HKCategoryValueSleepAnalysisAsleepUnspecified': 'unspecified'
        }
    
    def parse_healthkit_xml(self, xml_file_path: str) -> Tuple[List[SleepRecord], List[HRVRecord]]:
        """解析HealthKit导出的XML文件
        
        Args:
            xml_file_path: XML文件路径
            
        Returns:
            (睡眠记录列表, HRV记录列表)
        """
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        sleep_records = self._parse_sleep_data_from_xml(root)
        hrv_records = self._parse_hrv_data_from_xml(root)
        
        return sleep_records, hrv_records
    
    def _parse_sleep_data_from_xml(self, root: ET.Element) -> List[SleepRecord]:
        """从XML解析睡眠数据"""
        sleep_samples = []
        
        # 查找所有睡眠记录
        for record in root.findall(".//Record[@type='HKCategoryTypeIdentifierSleepAnalysis']"):
            start_date = datetime.fromisoformat(record.get('startDate').replace(' ', 'T'))
            end_date = datetime.fromisoformat(record.get('endDate').replace(' ', 'T'))
            value = record.get('value', '')
            source = record.get('sourceName', 'Unknown')
            
            duration_minutes = int((end_date - start_date).total_seconds() / 60)
            
            sleep_samples.append({
                'start_date': start_date,
                'end_date': end_date,
                'stage': self.sleep_stage_mapping.get(value, 'unknown'),
                'duration_minutes': duration_minutes,
                'source': source
            })
        
        # 按日期聚合睡眠数据
        return self._aggregate_sleep_samples_by_date(sleep_samples)
    
    def _aggregate_sleep_samples_by_date(self, samples: List[Dict]) -> List[SleepRecord]:
        """按日期聚合睡眠样本"""
        daily_sleep = {}
        
        for sample in samples:
            sleep_date = sample['start_date'].date()
            
            if sleep_date not in daily_sleep:
                daily_sleep[sleep_date] = {
                    'deep_minutes': 0,
                    'rem_minutes': 0,
                    'core_minutes': 0,
                    'awake_minutes': 0,
                    'in_bed_minutes': 0,
                    'total_sleep_minutes': 0,
                    'source': sample['source'],
                    'samples': []
                }
            
            day_data = daily_sleep[sleep_date]
            stage = sample['stage']
            duration = sample['duration_minutes']
            
            day_data['samples'].append(sample)
            
            if stage == 'deep':
                day_data['deep_minutes'] += duration
                day_data['total_sleep_minutes'] += duration
            elif stage == 'rem':
                day_data['rem_minutes'] += duration
                day_data['total_sleep_minutes'] += duration
            elif stage == 'core':
                day_data['core_minutes'] += duration
                day_data['total_sleep_minutes'] += duration
            elif stage == 'awake':
                day_data['awake_minutes'] += duration
            elif stage == 'in_bed':
                day_data['in_bed_minutes'] += duration
        
        # 转换为SleepRecord对象
        sleep_records = []
        
        for date, data in daily_sleep.items():
            # 计算在床总时间（如果没有in_bed记录，则使用睡眠总时间+清醒时间）
            time_in_bed = data['in_bed_minutes']
            if time_in_bed == 0:
                time_in_bed = data['total_sleep_minutes'] + data['awake_minutes']
            
            # 只有有效睡眠数据才创建记录
            if data['total_sleep_minutes'] > 60:  # 至少1小时睡眠
                sleep_record = SleepRecord(
                    date=datetime.combine(date, datetime.min.time()),
                    sleep_duration_minutes=data['total_sleep_minutes'],
                    time_in_bed_minutes=time_in_bed,
                    deep_sleep_minutes=data['deep_minutes'] if data['deep_minutes'] > 0 else None,
                    rem_sleep_minutes=data['rem_minutes'] if data['rem_minutes'] > 0 else None,
                    core_sleep_minutes=data['core_minutes'] if data['core_minutes'] > 0 else None,
                    awake_minutes=data['awake_minutes'],
                    source_device=data['source']
                )
                sleep_records.append(sleep_record)
        
        return sorted(sleep_records, key=lambda x: x.date)
    
    def _parse_hrv_data_from_xml(self, root: ET.Element) -> List[HRVRecord]:
        """从XML解析HRV数据"""
        hrv_records = []
        
        # 查找所有HRV记录（SDNN）
        for record in root.findall(".//Record[@type='HKQuantityTypeIdentifierHeartRateVariabilitySDNN']"):
            start_date = datetime.fromisoformat(record.get('startDate').replace(' ', 'T'))
            value = float(record.get('value'))
            unit = record.get('unit', 'ms')
            source = record.get('sourceName', 'Unknown')
            
            # 确保单位是毫秒
            if unit != 'ms':
                continue  # 跳过非毫秒单位的数据
            
            # 基本数据验证
            if 5.0 <= value <= 300.0:
                hrv_record = HRVRecord(
                    timestamp=start_date,
                    sdnn_value=value,
                    source_device=source,
                    measurement_context=self._infer_measurement_context(start_date)
                )
                hrv_records.append(hrv_record)
        
        return sorted(hrv_records, key=lambda x: x.timestamp)
    
    def _infer_measurement_context(self, timestamp: datetime) -> str:
        """推断HRV测量上下文"""
        hour = timestamp.hour
        
        if 6 <= hour <= 10:
            return 'morning'
        elif 22 <= hour or hour <= 2:
            return 'evening'
        else:
            return 'random'
    
    def parse_healthkit_api_data(self, sleep_data: List[Dict], hrv_data: List[Dict]) -> Tuple[List[SleepRecord], List[HRVRecord]]:
        """解析从HealthKit API获取的数据
        
        Args:
            sleep_data: HealthKit API睡眠数据
            hrv_data: HealthKit API HRV数据
            
        Returns:
            (睡眠记录列表, HRV记录列表)
        """
        sleep_records = []
        hrv_records = []
        
        # 解析睡眠数据
        for data in sleep_data:
            try:
                sleep_record = SleepRecord(
                    date=datetime.fromisoformat(data['date']),
                    sleep_duration_minutes=data['sleep_duration_minutes'],
                    time_in_bed_minutes=data.get('time_in_bed_minutes', data['sleep_duration_minutes']),
                    deep_sleep_minutes=data.get('deep_sleep_minutes'),
                    rem_sleep_minutes=data.get('rem_sleep_minutes'), 
                    core_sleep_minutes=data.get('core_sleep_minutes'),
                    awake_minutes=data.get('awake_minutes', 0),
                    source_device=data.get('source_device', 'HealthKit')
                )
                sleep_records.append(sleep_record)
            except (ValueError, KeyError) as e:
                print(f"跳过无效睡眠记录: {e}")
                continue
        
        # 解析HRV数据
        for data in hrv_data:
            try:
                hrv_record = HRVRecord(
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    sdnn_value=float(data['sdnn_value']),
                    source_device=data.get('source_device', 'HealthKit'),
                    measurement_context=data.get('measurement_context', 'unknown')
                )
                hrv_records.append(hrv_record)
            except (ValueError, KeyError) as e:
                print(f"跳过无效HRV记录: {e}")
                continue
        
        return sleep_records, hrv_records

def create_sample_healthkit_data() -> Tuple[List[Dict], List[Dict]]:
    """创建示例HealthKit数据格式
    
    Returns:
        (示例睡眠数据, 示例HRV数据)
    """
    
    # 示例睡眠数据（30天）
    sample_sleep_data = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        
        # 模拟真实的睡眠变化
        base_sleep = 420 + (i % 7 - 3) * 15  # 7小时基础 ± 45分钟
        deep_sleep = int(base_sleep * (0.12 + (i % 5) * 0.02))  # 12-20%深睡眠
        rem_sleep = int(base_sleep * (0.20 + (i % 3) * 0.03))   # 20-26%REM
        core_sleep = base_sleep - deep_sleep - rem_sleep
        
        sample_sleep_data.append({
            'date': date.isoformat(),
            'sleep_duration_minutes': base_sleep,
            'time_in_bed_minutes': base_sleep + 20 + (i % 4) * 10,  # 在床时间稍长
            'deep_sleep_minutes': deep_sleep,
            'rem_sleep_minutes': rem_sleep,
            'core_sleep_minutes': core_sleep,
            'awake_minutes': 5 + (i % 3) * 5,
            'source_device': 'Apple Watch Series 9'
        })
    
    # 示例HRV数据（40个样本）
    sample_hrv_data = []
    
    for i in range(40):
        timestamp = base_date + timedelta(days=i//2, hours=8, minutes=i*5)
        # 模拟HRV变化：基础值35ms ± 变化
        hrv_value = 35.0 + (i % 9 - 4) * 3.5 + (i % 3 - 1) * 2.0
        
        sample_hrv_data.append({
            'timestamp': timestamp.isoformat(),
            'sdnn_value': round(hrv_value, 1),
            'source_device': 'Apple Watch Series 9',
            'measurement_context': 'morning' if timestamp.hour == 8 else 'random'
        })
    
    return sample_sleep_data, sample_hrv_data

# 快捷函数
def parse_healthkit_export_xml(xml_file_path: str) -> Tuple[List[SleepRecord], List[HRVRecord]]:
    """解析HealthKit导出XML文件的快捷函数"""
    parser = HealthKitDataParser()
    return parser.parse_healthkit_xml(xml_file_path)

def parse_healthkit_api_data(sleep_data: List[Dict], hrv_data: List[Dict]) -> Tuple[List[SleepRecord], List[HRVRecord]]:
    """解析HealthKit API数据的快捷函数"""
    parser = HealthKitDataParser()
    return parser.parse_healthkit_api_data(sleep_data, hrv_data)

if __name__ == '__main__':
    # 演示数据解析
    print("🍎 HealthKit数据解析演示")
    print("=" * 50)
    
    # 创建示例数据
    sample_sleep_data, sample_hrv_data = create_sample_healthkit_data()
    
    print(f"📊 示例数据:")
    print(f"   睡眠记录: {len(sample_sleep_data)}天")
    print(f"   HRV记录: {len(sample_hrv_data)}个")
    
    # 解析数据
    parser = HealthKitDataParser()
    sleep_records, hrv_records = parser.parse_healthkit_api_data(sample_sleep_data, sample_hrv_data)
    
    print(f"\n✅ 解析结果:")
    print(f"   有效睡眠记录: {len(sleep_records)}")
    print(f"   有效HRV记录: {len(hrv_records)}")
    
    # 显示示例记录
    if sleep_records:
        record = sleep_records[0]
        print(f"\n🌙 睡眠记录示例:")
        print(f"   日期: {record.date.date()}")
        print(f"   总睡眠: {record.sleep_duration_hours:.1f}小时")
        print(f"   睡眠效率: {record.sleep_efficiency:.1%}")
        print(f"   恢复性睡眠: {record.restorative_ratio:.1%}" if record.restorative_ratio else "   恢复性睡眠: 无数据")
    
    if hrv_records:
        record = hrv_records[0]
        print(f"\n💓 HRV记录示例:")
        print(f"   时间: {record.timestamp}")
        print(f"   SDNN: {record.sdnn_value}ms")
        print(f"   上下文: {record.measurement_context}")