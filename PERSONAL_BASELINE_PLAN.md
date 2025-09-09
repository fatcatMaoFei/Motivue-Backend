# 个人基线系统实施计划

## 项目概述
在现有 readiness 模块基础上，增加个人基线计算系统，实现用户个性化的准备度评估。通过获取用户 HealthKit 历史数据，计算个人睡眠和 HRV 基线，替换现有的硬编码阈值。

## 系统架构设计

### 整体架构图
```
iOS/Android 客户端
    ↓ HealthKit 历史数据 (30天睡眠 + 28天HRV)
┌──────────────────────┐
│  baseline-service    │ ← 新增独立微服务
│  (个人基线计算)       │   
└──────────────────────┘
    ↓ 计算结果存储
┌──────────────────────┐
│  user_baselines 表   │ ← 新增数据库表
└──────────────────────┘
    ↓ 基线数据查询
┌──────────────────────┐
│  readiness-service   │ ← 现有服务(需修改)
│  (集成个人基线)       │
└──────────────────────┘
```

## 详细实施计划

### 阶段一：数据库设计和基础设施

#### 1.1 新增数据库表
```sql
-- 用户基线数据表
CREATE TABLE user_baselines (
    user_id VARCHAR(255) PRIMARY KEY,
    
    -- 睡眠基线数据
    sleep_baseline_hours DECIMAL(4,2),        -- 平均睡眠时长(小时)
    sleep_baseline_eff DECIMAL(4,3),          -- 平均睡眠效率(0-1)
    rest_baseline_ratio DECIMAL(4,3),         -- 恢复性睡眠比例基线
    
    -- HRV基线数据  
    hrv_baseline_mu DECIMAL(6,2),             -- HRV均值(ms)
    hrv_baseline_sd DECIMAL(6,2),             -- HRV标准差(ms)
    
    -- 元数据
    baseline_version VARCHAR(50) DEFAULT 'v1.0',
    data_quality_score DECIMAL(3,2),          -- 基线数据质量评分(0-1)
    sample_days_sleep INT,                     -- 睡眠数据天数
    sample_days_hrv INT,                       -- HRV数据天数
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_recalculated_at TIMESTAMP,           -- 上次重新计算时间
    
    -- 索引
    INDEX idx_user_updated (user_id, updated_at)
);

-- 基线计算历史记录表 (可选，用于调试和监控)
CREATE TABLE baseline_calculation_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255),
    calculation_type ENUM('initial', 'periodic_update', 'manual_refresh'),
    input_data_summary JSON,                   -- 输入数据摘要
    calculated_baseline JSON,                  -- 计算结果
    execution_time_ms INT,                     -- 执行耗时
    error_message TEXT,                        -- 错误信息(如有)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_time (user_id, created_at)
);
```

#### 1.2 环境配置
```python
# config/baseline_config.py
class BaselineConfig:
    # 数据采集配置
    SLEEP_HISTORY_DAYS = 30      # 睡眠历史数据天数
    HRV_HISTORY_DAYS = 28        # HRV历史数据天数
    
    # 数据质量要求
    MIN_SLEEP_SAMPLES = 20       # 最少睡眠数据天数
    MIN_HRV_SAMPLES = 15         # 最少HRV数据天数
    
    # 基线更新策略
    UPDATE_FREQUENCY_DAYS = 7    # 每7天更新一次基线
    RECALCULATION_THRESHOLD = 30 # 30天后强制重新计算
    
    # 数据过滤
    SLEEP_DURATION_MIN = 3.0     # 最少睡眠时长(小时)
    SLEEP_DURATION_MAX = 12.0    # 最大睡眠时长(小时) 
    HRV_VALUE_MIN = 5.0          # HRV最小值(ms)
    HRV_VALUE_MAX = 200.0        # HRV最大值(ms)
```

### 阶段二：baseline-service 微服务开发

#### 2.1 项目结构
```
baseline-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── models/
│   │   ├── __init__.py
│   │   ├── baseline.py      # 基线数据模型
│   │   └── health_data.py   # 健康数据模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── calculator.py    # 基线计算核心逻辑
│   │   ├── data_validator.py # 数据验证和清洗
│   │   └── database.py      # 数据库操作
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py     # API端点
│   └── utils/
│       ├── __init__.py
│       └── statistics.py    # 统计计算工具
├── requirements.txt
├── Dockerfile
└── README.md
```

#### 2.2 核心数据模型
```python
# app/models/health_data.py
from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime

class SleepRecord(BaseModel):
    date: datetime
    sleep_duration_hours: float
    sleep_efficiency: float
    deep_sleep_ratio: Optional[float] = None
    rem_sleep_ratio: Optional[float] = None
    restorative_ratio: Optional[float] = None
    
    @validator('sleep_duration_hours')
    def validate_duration(cls, v):
        if not 3.0 <= v <= 12.0:
            raise ValueError('睡眠时长必须在3-12小时之间')
        return v
    
    @validator('sleep_efficiency')  
    def validate_efficiency(cls, v):
        if not 0.3 <= v <= 1.0:
            raise ValueError('睡眠效率必须在0.3-1.0之间')
        return v

class HRVRecord(BaseModel):
    timestamp: datetime
    sdnn_value: float        # Apple HealthKit使用SDNN
    source_device: Optional[str] = None
    
    @validator('sdnn_value')
    def validate_hrv(cls, v):
        if not 5.0 <= v <= 200.0:
            raise ValueError('HRV值必须在5-200ms之间')
        return v

class BaselineCalculationRequest(BaseModel):
    user_id: str
    sleep_records: List[SleepRecord]
    hrv_records: List[HRVRecord]
    calculation_type: str = 'initial'  # initial, periodic_update, manual_refresh
    
    @validator('sleep_records')
    def validate_sleep_data(cls, v):
        if len(v) < 20:
            raise ValueError('睡眠数据至少需要20天')
        return v
    
    @validator('hrv_records')
    def validate_hrv_data(cls, v):
        if len(v) < 15:
            raise ValueError('HRV数据至少需要15个样本')
        return v
```

#### 2.3 基线计算核心逻辑
```python
# app/services/calculator.py
import numpy as np
from typing import Dict, List, Tuple
from ..models.health_data import SleepRecord, HRVRecord
from ..utils.statistics import robust_mean, robust_std

class PersonalBaselineCalculator:
    """个人基线计算器"""
    
    def __init__(self):
        self.sleep_percentile_range = (10, 90)  # 使用10-90百分位数过滤异常值
        self.hrv_percentile_range = (5, 95)     # HRV使用5-95百分位数
    
    def calculate_sleep_baseline(self, sleep_records: List[SleepRecord]) -> Dict[str, float]:
        """计算睡眠基线"""
        durations = [r.sleep_duration_hours for r in sleep_records]
        efficiencies = [r.sleep_efficiency for r in sleep_records]
        
        # 过滤异常值
        duration_filtered = self._filter_outliers(durations, self.sleep_percentile_range)
        efficiency_filtered = self._filter_outliers(efficiencies, self.sleep_percentile_range)
        
        # 计算基线
        sleep_baseline_hours = robust_mean(duration_filtered)
        sleep_baseline_eff = robust_mean(efficiency_filtered)
        
        # 计算恢复性睡眠基线
        restorative_ratios = []
        for record in sleep_records:
            if record.restorative_ratio is not None:
                restorative_ratios.append(record.restorative_ratio)
            elif record.deep_sleep_ratio and record.rem_sleep_ratio:
                restorative_ratios.append(record.deep_sleep_ratio + record.rem_sleep_ratio)
        
        rest_baseline_ratio = robust_mean(restorative_ratios) if restorative_ratios else None
        
        return {
            'sleep_baseline_hours': round(sleep_baseline_hours, 2),
            'sleep_baseline_eff': round(sleep_baseline_eff, 3),
            'rest_baseline_ratio': round(rest_baseline_ratio, 3) if rest_baseline_ratio else None,
        }
    
    def calculate_hrv_baseline(self, hrv_records: List[HRVRecord]) -> Dict[str, float]:
        """计算HRV基线"""
        hrv_values = [r.sdnn_value for r in hrv_records]
        
        # 过滤异常值  
        hrv_filtered = self._filter_outliers(hrv_values, self.hrv_percentile_range)
        
        # 计算均值和标准差
        hrv_mean = robust_mean(hrv_filtered)
        hrv_std = robust_std(hrv_filtered)
        
        return {
            'hrv_baseline_mu': round(hrv_mean, 2),
            'hrv_baseline_sd': round(hrv_std, 2),
        }
    
    def _filter_outliers(self, data: List[float], percentile_range: Tuple[int, int]) -> List[float]:
        """过滤异常值"""
        if len(data) < 5:
            return data
            
        low_p, high_p = percentile_range
        low_threshold = np.percentile(data, low_p)
        high_threshold = np.percentile(data, high_p)
        
        return [x for x in data if low_threshold <= x <= high_threshold]
    
    def calculate_data_quality_score(self, 
                                   sleep_records: List[SleepRecord], 
                                   hrv_records: List[HRVRecord]) -> float:
        """计算数据质量评分"""
        score = 0.0
        
        # 数据量评分 (40%)
        sleep_days = len(sleep_records)
        hrv_samples = len(hrv_records)
        
        sleep_score = min(sleep_days / 30, 1.0)  # 30天满分
        hrv_score = min(hrv_samples / 50, 1.0)   # 50个样本满分
        data_quantity_score = (sleep_score + hrv_score) / 2 * 0.4
        
        # 数据完整性评分 (30%)
        complete_sleep_fields = sum(1 for r in sleep_records 
                                  if r.restorative_ratio is not None or 
                                     (r.deep_sleep_ratio and r.rem_sleep_ratio))
        completeness_score = (complete_sleep_fields / len(sleep_records)) * 0.3
        
        # 数据时间分布评分 (30%)
        # 检查数据是否均匀分布在时间轴上
        sleep_dates = [r.date.date() for r in sleep_records]
        date_range = (max(sleep_dates) - min(sleep_dates)).days + 1
        coverage_ratio = len(set(sleep_dates)) / date_range if date_range > 0 else 0
        distribution_score = coverage_ratio * 0.3
        
        total_score = data_quantity_score + completeness_score + distribution_score
        return round(min(total_score, 1.0), 2)
```

#### 2.4 API端点实现
```python
# app/api/endpoints.py
from fastapi import APIRouter, HTTPException, Depends
from ..models.health_data import BaselineCalculationRequest
from ..services.calculator import PersonalBaselineCalculator
from ..services.database import BaselineDatabase
from ..services.data_validator import DataValidator

router = APIRouter()

@router.post("/api/v1/calculate-baseline")
async def calculate_baseline(
    request: BaselineCalculationRequest,
    db: BaselineDatabase = Depends()
):
    """计算用户个人基线"""
    try:
        # 1. 数据验证和清洗
        validator = DataValidator()
        cleaned_sleep_data = validator.validate_and_clean_sleep_data(request.sleep_records)
        cleaned_hrv_data = validator.validate_and_clean_hrv_data(request.hrv_records)
        
        # 2. 基线计算
        calculator = PersonalBaselineCalculator()
        sleep_baseline = calculator.calculate_sleep_baseline(cleaned_sleep_data)
        hrv_baseline = calculator.calculate_hrv_baseline(cleaned_hrv_data)
        data_quality = calculator.calculate_data_quality_score(
            cleaned_sleep_data, cleaned_hrv_data
        )
        
        # 3. 合并结果
        baseline_result = {
            **sleep_baseline,
            **hrv_baseline,
            'data_quality_score': data_quality,
            'sample_days_sleep': len(cleaned_sleep_data),
            'sample_days_hrv': len(cleaned_hrv_data),
        }
        
        # 4. 保存到数据库
        await db.save_user_baseline(request.user_id, baseline_result)
        
        # 5. 记录计算日志
        await db.log_baseline_calculation(
            user_id=request.user_id,
            calculation_type=request.calculation_type,
            input_summary={
                'sleep_records_count': len(request.sleep_records),
                'hrv_records_count': len(request.hrv_records),
                'date_range': {
                    'start': min(r.date for r in request.sleep_records).isoformat(),
                    'end': max(r.date for r in request.sleep_records).isoformat()
                }
            },
            result=baseline_result
        )
        
        return {
            'status': 'success',
            'user_id': request.user_id,
            'baseline': baseline_result,
            'message': f'基线计算完成，数据质量评分: {data_quality}'
        }
        
    except Exception as e:
        await db.log_baseline_calculation(
            user_id=request.user_id,
            calculation_type=request.calculation_type,
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=f"基线计算失败: {str(e)}")

@router.get("/api/v1/baseline/{user_id}")
async def get_user_baseline(user_id: str, db: BaselineDatabase = Depends()):
    """获取用户基线数据"""
    baseline = await db.get_user_baseline(user_id)
    if not baseline:
        raise HTTPException(status_code=404, detail="用户基线数据不存在")
    return baseline

@router.post("/api/v1/baseline/{user_id}/refresh")
async def refresh_baseline(user_id: str, db: BaselineDatabase = Depends()):
    """标记基线需要刷新（由定时任务处理）"""
    await db.mark_baseline_for_refresh(user_id)
    return {'status': 'marked_for_refresh', 'user_id': user_id}
```

### 阶段三：现有 readiness-service 集成修改

#### 3.1 修改 service.py
```python
# readiness/service.py (修改现有文件)
from typing import Optional, Dict
import asyncio

# 新增基线数据获取函数
async def get_user_baseline(user_id: str) -> Optional[Dict]:
    """获取用户个人基线数据"""
    try:
        # 这里可以是数据库查询或调用baseline-service API
        # 示例：数据库查询
        baseline = await BaselineDatabase.get_user_baseline(user_id)
        return baseline
    except Exception as e:
        print(f"获取用户{user_id}基线数据失败: {e}")
        return None

def compute_readiness_from_payload(payload: dict) -> dict:
    """
    计算就绪度（现有函数，需要修改以集成个人基线）
    """
    user_id = payload.get('user_id')
    
    # === 新增：尝试获取个人基线数据 ===
    if user_id:
        try:
            # 同步获取基线数据（或使用缓存）
            baseline = get_user_baseline_sync(user_id)  # 需要实现同步版本
            if baseline:
                # 注入基线数据到payload
                baseline_keys = [
                    'sleep_baseline_hours', 'sleep_baseline_eff', 
                    'rest_baseline_ratio', 'hrv_baseline_mu', 'hrv_baseline_sd'
                ]
                for key in baseline_keys:
                    if key in baseline and baseline[key] is not None:
                        payload[key] = baseline[key]
                
                # 可选：添加基线数据质量到上下文
                payload['_baseline_quality'] = baseline.get('data_quality_score', 0.0)
        except Exception as e:
            print(f"集成个人基线数据时出错: {e}")
            # 继续使用默认逻辑，不影响核心功能
    
    # === 原有逻辑保持不变 ===
    user_id = payload.get('user_id', 'anonymous')
    date = payload.get('date', get_today_date())
    gender = payload.get('gender', '男')
    previous_state_probs = payload.get('previous_state_probs')
    
    eng = ReadinessEngine(user_id, date, previous_state_probs, gender)
    
    # ... 其余逻辑完全不变
    
    return eng.get_daily_summary()

def get_user_baseline_sync(user_id: str) -> Optional[Dict]:
    """同步版本的基线获取（避免在同步函数中使用async）"""
    try:
        # 可以使用缓存、数据库连接池等同步方式
        # 或者预加载基线数据到内存缓存
        return BaselineCache.get(user_id)
    except Exception as e:
        print(f"同步获取基线数据失败: {e}")
        return None
```

#### 3.2 mapping.py 无需修改
```python
# readiness/mapping.py 
# 现有代码已经完美支持个人基线！
# 只要payload中包含基线数据，mapping逻辑会自动使用：

# 示例：当payload包含基线时
payload = {
    'user_id': 'user123',
    'sleep_duration_hours': 7.5,
    'sleep_efficiency': 0.88,
    'sleep_baseline_hours': 7.2,    # ← 来自baseline-service
    'sleep_baseline_eff': 0.85,     # ← 来自baseline-service
    # ...
}

# mapping.py中的逻辑会自动使用基线调整阈值：
# good_dur_threshold = max(7.0, 7.2 - 0.5) = 7.0
# good_eff_threshold = max(0.85, 0.85 - 0.05) = 0.85
# 然后进行个性化判断
```

### 阶段四：基线更新策略

#### 4.1 定时更新任务
```python
# baseline-service/app/tasks/periodic_update.py
from celery import Celery
from datetime import datetime, timedelta
from ..services.database import BaselineDatabase

app = Celery('baseline_updater')

@app.task
def update_outdated_baselines():
    """定时任务：更新过期的基线数据"""
    db = BaselineDatabase()
    
    # 查找需要更新的用户（7天未更新）
    threshold_date = datetime.now() - timedelta(days=7)
    users_to_update = db.get_users_with_outdated_baselines(threshold_date)
    
    for user_id in users_to_update:
        try:
            # 触发客户端获取新的历史数据
            notify_client_for_baseline_update.delay(user_id)
        except Exception as e:
            print(f"用户{user_id}基线更新失败: {e}")

@app.task  
def notify_client_for_baseline_update(user_id: str):
    """通知客户端需要更新基线数据"""
    # 发送推送通知或在用户下次打开应用时提示
    # 可以通过消息队列、推送服务等实现
    pass
```

#### 4.2 基线更新频率策略
```python
# 更新策略配置
BASELINE_UPDATE_RULES = {
    'initial_calculation': {
        'trigger': '首次使用',
        'data_range': '过去30天',
        'required': True
    },
    'weekly_update': {
        'trigger': '每7天',
        'data_range': '最近7天增量数据', 
        'condition': '数据质量>0.7',
        'method': 'rolling_average'  # 滑动平均
    },
    'monthly_recalculation': {
        'trigger': '每30天',
        'data_range': '过去30天完整数据',
        'method': 'full_recalculation'  # 完全重新计算
    },
    'significant_change': {
        'trigger': '数据模式显著变化',
        'condition': '新数据与基线偏差>2个标准差',
        'method': 'adaptive_update'  # 自适应更新
    }
}
```

## 实施风险和注意事项

### 代码修改风险控制

#### 1. 现有代码影响最小化
- ✅ **mapping.py**: 无需修改，现有基线逻辑直接可用
- ✅ **engine.py**: 无需修改，基线数据通过payload自然传递
- ✅ **constants.py**: 无需修改，所有概率表保持不变
- ⚠️ **service.py**: 仅需添加基线数据获取，原逻辑不变

#### 2. 向后兼容保证
```python
# 在service.py修改中确保向后兼容
def compute_readiness_from_payload(payload: dict) -> dict:
    # 新增基线逻辑使用try-catch包装
    try:
        baseline = get_user_baseline_sync(payload.get('user_id'))
        if baseline:
            payload.update(baseline)  # 有基线就用，没有就用默认
    except Exception:
        pass  # 静默失败，确保原功能不受影响
    
    # 原有逻辑完全不变
    return original_compute_logic(payload)
```

#### 3. 渐进式部署策略
```
Phase 1: 基线服务独立开发和测试
Phase 2: 基线数据库创建和API测试  
Phase 3: readiness-service小范围集成测试
Phase 4: 客户端HealthKit集成
Phase 5: 全量用户灰度发布
```

### 数据隐私和安全

#### 1. HealthKit 数据处理
- 客户端数据预处理，只发送必要的统计信息
- 原始健康数据不存储，仅保存计算结果
- 用户可以随时删除个人基线数据

#### 2. 数据传输安全
```python
# 客户端数据脱敏处理
class PrivacyProtection:
    @staticmethod
    def sanitize_sleep_data(records: List[SleepRecord]) -> List[dict]:
        """脱敏处理睡眠数据"""
        return [{
            'duration_hours': round(r.sleep_duration_hours, 1),  # 精度降低
            'efficiency': round(r.sleep_efficiency, 2),
            'date_hash': hash(r.date.date())  # 日期哈希化
        } for r in records]
```

## 测试策略

### 单元测试
```python
# tests/test_baseline_calculator.py
class TestBaselineCalculator:
    def test_sleep_baseline_calculation(self):
        # 测试正常情况
        records = [SleepRecord(...) for _ in range(30)]
        calculator = PersonalBaselineCalculator()
        result = calculator.calculate_sleep_baseline(records)
        assert 'sleep_baseline_hours' in result
        assert 4.0 <= result['sleep_baseline_hours'] <= 10.0
    
    def test_outlier_filtering(self):
        # 测试异常值过滤
        data = [7.0] * 20 + [2.0, 15.0]  # 添加异常值
        filtered = calculator._filter_outliers(data, (10, 90))
        assert 2.0 not in filtered
        assert 15.0 not in filtered
    
    def test_insufficient_data(self):
        # 测试数据不足情况
        records = [SleepRecord(...) for _ in range(5)]
        with pytest.raises(ValueError):
            calculator.calculate_sleep_baseline(records)
```

### 集成测试
```python
# tests/test_service_integration.py
class TestReadinessServiceIntegration:
    def test_with_personal_baseline(self):
        # 测试有个人基线的情况
        payload = {
            'user_id': 'test_user',
            'sleep_duration_hours': 6.5,
            'sleep_efficiency': 0.82,
            # 模拟个人基线会被自动注入
        }
        
        # 模拟基线数据
        mock_baseline = {
            'sleep_baseline_hours': 6.8,
            'sleep_baseline_eff': 0.88
        }
        
        with patch('readiness.service.get_user_baseline_sync', return_value=mock_baseline):
            result = compute_readiness_from_payload(payload)
            # 验证个人基线生效（阈值应该被调整）
            assert result['final_readiness_score'] != compute_without_baseline(payload)
    
    def test_fallback_to_default(self):
        # 测试基线获取失败时的回退逻辑
        payload = {'user_id': 'test_user', 'sleep_duration_hours': 7.0}
        
        with patch('readiness.service.get_user_baseline_sync', side_effect=Exception):
            result = compute_readiness_from_payload(payload)
            # 应该能正常工作，使用默认阈值
            assert 'final_readiness_score' in result
```

## 监控和运维

### 关键指标监控
```python
# 基线计算成功率
baseline_calculation_success_rate = (
    successful_calculations / total_calculation_requests
)

# 数据质量分布
data_quality_distribution = {
    'high_quality': users_with_quality_score_above_0_8,
    'medium_quality': users_with_quality_score_0_5_to_0_8, 
    'low_quality': users_with_quality_score_below_0_5
}

# 基线更新及时性
baseline_freshness = {
    'up_to_date': users_with_baseline_updated_within_7_days,
    'outdated': users_with_baseline_older_than_7_days,
    'never_calculated': users_without_baseline
}
```

### 告警规则
```yaml
alerts:
  - name: BaselineCalculationFailureRate
    condition: baseline_calculation_success_rate < 0.95
    severity: warning
    
  - name: BaselineServiceDown  
    condition: baseline_service_health_check_failed
    severity: critical
    
  - name: HighDataQualityDrop
    condition: avg_data_quality_score < 0.6
    severity: warning
```

## 总结

这个计划确保了：
1. **最小侵入性**：现有代码基本不需要修改，mapping.py的基线逻辑直接可用
2. **渐进式实施**：可以分阶段开发和部署，降低风险  
3. **向后兼容**：没有基线数据时自动回退到原有逻辑
4. **可扩展性**：基线更新策略可以不断优化
5. **用户体验**：一次授权后自动提供个性化评估

需要我详细展开哪个部分？