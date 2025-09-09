# Baseline模块 API参考文档

这是为后端开发人员准备的完整API接口文档。

## 🚀 快速开始

### 核心API函数

```python
from baseline import compute_baseline_from_healthkit_data

# 从HealthKit数据计算基线（推荐使用）
result = compute_baseline_from_healthkit_data(
    user_id="user_123",
    healthkit_sleep_data=sleep_data,  # HealthKit格式的睡眠数据
    healthkit_hrv_data=hrv_data       # HealthKit格式的HRV数据
)
```

## 📊 数据格式说明

### HealthKit睡眠数据格式

```python
healthkit_sleep_data = [
    {
        'date': '2024-01-01T00:00:00Z',           # 睡眠日期
        'sleep_duration_minutes': 420,           # 总睡眠时长（分钟）
        'time_in_bed_minutes': 450,              # 在床时间（分钟）
        'deep_sleep_minutes': 80,                # 深度睡眠（分钟，可选）
        'rem_sleep_minutes': 100,                # REM睡眠（分钟，可选）
        'core_sleep_minutes': 240,               # 核心睡眠（分钟，可选）
        'awake_minutes': 10,                     # 清醒时间（分钟，可选）
        'source_device': 'Apple Watch Series 9' # 数据源设备（可选）
    }
    # ... 更多记录
]
```

### HealthKit HRV数据格式

```python
healthkit_hrv_data = [
    {
        'timestamp': '2024-01-01T08:00:00Z',     # 测量时间
        'sdnn_value': 42.5,                     # HRV SDNN值（毫秒）
        'source_device': 'Apple Watch Series 9', # 数据源设备（可选）
        'measurement_context': 'morning'         # 测量上下文（可选）
    }
    # ... 更多记录
]
```

## 🔧 主要API函数

### 1. compute_baseline_from_healthkit_data()

**主要接口，推荐使用**

```python
def compute_baseline_from_healthkit_data(
    user_id: str, 
    healthkit_sleep_data: List[Dict[str, Any]], 
    healthkit_hrv_data: List[Dict[str, Any]],
    storage: Optional[BaselineStorage] = None
) -> Dict[str, Any]
```

**参数:**
- `user_id`: 用户唯一标识符
- `healthkit_sleep_data`: HealthKit格式的睡眠数据列表
- `healthkit_hrv_data`: HealthKit格式的HRV数据列表  
- `storage`: 可选的存储后端实例

**返回值:**
```python
{
    'status': 'success',              # 状态: success/failed/error
    'user_id': 'user_123',           # 用户ID
    'baseline': {                     # 基线数据对象
        'sleep_baseline_hours': 7.2,
        'sleep_baseline_eff': 0.85,
        'rest_baseline_ratio': 0.32,
        'hrv_baseline_mu': 38.5,
        'hrv_baseline_sd': 8.2,
        # ... 更多字段
    },
    'readiness_payload': {            # 可直接用于readiness计算的格式
        'sleep_baseline_hours': 7.2,
        'sleep_baseline_eff': 0.85,
        'rest_baseline_ratio': 0.32,
        'hrv_baseline_mu': 38.5,
        'hrv_baseline_sd': 8.2
    },
    'data_quality': 0.87,            # 数据质量评分 (0-1)
    'data_summary': {                # 数据统计
        'sleep_records_parsed': 28,
        'hrv_records_parsed': 35,
        'sleep_date_range': '2024-01-01 to 2024-01-30'
    },
    'recommendations': [              # 个性化建议
        '您的个人基线已建立，系统将为您提供个性化的准备度评估'
    ],
    'message': 'HealthKit基线计算成功，质量评分: 0.87'
}
```

### 2. get_user_baseline()

**获取已存储的用户基线**

```python
def get_user_baseline(user_id: str, storage: BaselineStorage) -> Optional[BaselineResult]
```

**参数:**
- `user_id`: 用户ID
- `storage`: 存储后端实例

**返回值:**
- `BaselineResult`对象或`None`（如果不存在）

### 3. update_baseline_if_needed()

**智能基线更新**

```python
def update_baseline_if_needed(
    user_id: str,
    new_sleep_data: List[Dict[str, Any]],
    new_hrv_data: List[Dict[str, Any]], 
    storage: BaselineStorage,
    force_update: bool = False
) -> Dict[str, Any]
```

**更新策略:**
- 首次计算基线
- 基线数据超过7天未更新
- 数据质量评分低于0.7
- `force_update=True`强制更新

## 📁 存储后端

### 支持的存储类型

```python
from baseline.storage import MemoryBaselineStorage, FileBaselineStorage, SQLiteBaselineStorage

# 内存存储（开发测试）
storage = MemoryBaselineStorage()

# 文件存储（简单部署）
storage = FileBaselineStorage(storage_dir="/path/to/baseline_data")

# SQLite存储（生产推荐）
storage = SQLiteBaselineStorage(db_path="/path/to/baseline.db")
```

## 🔌 FastAPI集成示例

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from baseline import compute_baseline_from_healthkit_data
from baseline.storage import SQLiteBaselineStorage

app = FastAPI()

# 初始化存储
storage = SQLiteBaselineStorage("baseline.db")

class HealthKitDataRequest(BaseModel):
    user_id: str
    sleep_data: List[Dict[str, Any]]
    hrv_data: List[Dict[str, Any]]

@app.post("/api/v1/baseline/calculate")
async def calculate_baseline(request: HealthKitDataRequest):
    """计算用户个人基线"""
    
    result = compute_baseline_from_healthkit_data(
        user_id=request.user_id,
        healthkit_sleep_data=request.sleep_data,
        healthkit_hrv_data=request.hrv_data,
        storage=storage
    )
    
    if result['status'] == 'success':
        return {
            "success": True,
            "data": result
        }
    else:
        raise HTTPException(
            status_code=400, 
            detail=result.get('message', 'Baseline calculation failed')
        )

@app.get("/api/v1/baseline/{user_id}")
async def get_baseline(user_id: str):
    """获取用户基线数据"""
    
    from baseline import get_user_baseline
    
    baseline = get_user_baseline(user_id, storage)
    
    if baseline:
        return {
            "success": True,
            "data": baseline.to_dict()
        }
    else:
        raise HTTPException(status_code=404, detail="Baseline not found")
```

## 🎯 与Readiness模块集成

### 自动基线注入

```python
from baseline import get_user_baseline
from readiness.mapping import map_inputs_to_states

def calculate_readiness_with_baseline(user_id: str, current_health_data: Dict[str, Any]):
    # 1. 获取用户基线
    baseline = get_user_baseline(user_id, storage)
    
    # 2. 构造payload
    payload = current_health_data.copy()
    
    # 3. 注入基线数据
    if baseline:
        payload.update(baseline.to_readiness_payload())
    
    # 4. 计算个性化准备度
    states = map_inputs_to_states(payload)
    
    return states
```

### Readiness Payload格式

基线数据转换为readiness模块需要的格式：

```python
readiness_payload = {
    'sleep_baseline_hours': 7.2,     # mapping.py中的mu_dur
    'sleep_baseline_eff': 0.85,      # mapping.py中的mu_eff  
    'rest_baseline_ratio': 0.32,     # mapping.py中的mu_rest
    'hrv_baseline_mu': 38.5,         # mapping.py中的mu (HRV Z分数计算)
    'hrv_baseline_sd': 8.2           # mapping.py中的sd (HRV Z分数计算)
}
```

## ⚠️ 错误处理

### 常见错误状态

| Status | Error | 含义 | 处理建议 |
|--------|-------|------|----------|
| `failed` | `insufficient_data` | 数据不足 | 请用户提供更多历史数据 |
| `failed` | `low_quality` | 数据质量低 | 建议继续记录数据 |
| `error` | `Exception message` | 系统错误 | 检查输入格式和系统状态 |

### 最低数据要求

- **睡眠数据**: 至少10天有效记录
- **HRV数据**: 至少8个有效测量
- **数据质量**: 评分≥0.3才认为基线有效

## 📈 性能和优化

### 缓存策略

- 基线数据默认7天有效期
- 使用存储后端避免重复计算
- 支持增量数据更新

### 批量处理

```python
# 批量用户基线计算
for user_data in users_data:
    result = compute_baseline_from_healthkit_data(
        user_id=user_data['user_id'],
        healthkit_sleep_data=user_data['sleep_data'], 
        healthkit_hrv_data=user_data['hrv_data'],
        storage=storage
    )
    # 处理结果...
```

## 🔒 隐私和安全

- 只存储计算后的基线统计结果，不保存原始健康数据
- 支持用户删除个人基线数据
- 所有计算在本地完成，不上传原始数据

## 🧪 测试数据

使用内置的测试数据生成器：

```python
from baseline.healthkit_integration import create_sample_healthkit_data

# 生成30天睡眠 + 40个HRV样本
sample_sleep_data, sample_hrv_data = create_sample_healthkit_data()

# 测试基线计算
result = compute_baseline_from_healthkit_data(
    user_id="test_user",
    healthkit_sleep_data=sample_sleep_data,
    healthkit_hrv_data=sample_hrv_data
)
```

## 📞 技术支持

如有任何技术问题或集成困难，请参考：

1. `baseline/examples/` - 完整示例代码
2. `baseline/README.md` - 详细说明文档  
3. `baseline/models.py` - 数据模型定义
4. `baseline/healthkit_integration.py` - HealthKit数据处理

推荐的集成流程：**HealthKit数据 → baseline计算 → 存储基线 → readiness计算**