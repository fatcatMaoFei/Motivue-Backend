# Baseline（个人基线）模块

一个完整的个人健康基线管理系统，为 readiness 准备度评估提供个性化支持。

## ⚡ 快速开始

```python
from baseline import (
    compute_baseline_from_healthkit_data,
    update_baseline_smart,
    SQLiteBaselineStorage
)

# 1. 初始化存储
storage = SQLiteBaselineStorage("baseline.db")

# 2. 计算个人基线（新用户30天后）
result = compute_baseline_from_healthkit_data(
    user_id="user123",
    healthkit_sleep_data=sleep_data,   # 30天HealthKit睡眠数据
    healthkit_hrv_data=hrv_data,      # 30天HealthKit HRV数据
    storage=storage
)

# 3. 集成到readiness计算
baseline = storage.get_baseline("user123")
if baseline:
    readiness_payload.update(baseline.to_readiness_payload())

# 4. 自动更新（7天增量/30天完整）
update_result = update_baseline_smart(
    user_id="user123",
    sleep_data=recent_sleep_data,
    hrv_data=recent_hrv_data, 
    storage=storage
)
```

## 🎯 系统特性

### 核心功能
- ✅ **个人基线计算**: 基于30天HealthKit数据计算精准个人基线
- ✅ **新用户支持**: 问卷分类系统，数据不足时提供默认基线
- ✅ **智能更新**: 7天增量更新 + 30天完整更新自动调度
- ✅ **无缝集成**: 与现有readiness系统零代码侵入集成
- ✅ **数据质量**: 多维度数据质量评估和异常值过滤

### 生产特性  
- 🔄 **自动化**: 支持定时任务和后台更新
- 📊 **监控**: 完整的指标监控和健康检查
- 💾 **存储**: 支持SQLite/MySQL/PostgreSQL多种存储
- 🔒 **安全**: 数据隐私保护，仅存储统计结果
- 📈 **扩展**: 模块化设计，易于扩展新功能

## 📋 新用户默认基线

为数据不足30天的新用户提供个性化默认基线。

### 2个问题快速分类

**问题1：睡眠需求**
- 6-7小时 → `short_sleeper`
- 7-8小时 → `normal_sleeper` 
- 8-9小时+ → `long_sleeper`

**问题2：年龄段**  
- 25岁以下 → `high_hrv`
- 25-45岁 → `normal_hrv`
- 45岁以上 → `low_hrv`

详细问卷设计请参考 `QUESTIONNAIRE.md`

### API调用示例

```python
# 新用户：使用问卷结果
result = compute_baseline_from_healthkit_data(
    user_id="new_user",
    healthkit_sleep_data=sleep_data,  # <30天数据
    healthkit_hrv_data=hrv_data,
    sleeper_type="short_sleeper",     # 问卷结果
    hrv_type="high_hrv"              # 问卷结果
)
# 返回：success_with_defaults

# 老用户：自动个人基线
result = compute_baseline_from_healthkit_data(
    user_id="experienced_user", 
    healthkit_sleep_data=sleep_data,  # ≥30天数据
    healthkit_hrv_data=hrv_data
    # 不传sleeper_type，因为数据足够计算个人基线
)
# 返回：success (个人基线)
```

## ⚡ 后端集成说明

### 数据流转图

```
HealthKit数据 → Baseline服务 → 数据库存储 → Readiness计算
     ↓              ↓              ↓              ↓
[原始数据]    [个人基线]     [基线存储]    [个性化评估]
```

### 1. 输入格式：HealthKit → Baseline

**睡眠数据格式**：
```json
{
  "user_id": "user_123",
  "sleep_records": [
    {
      "date": "2024-01-01T00:00:00Z",
      "sleep_duration_hours": 7.5,
      "sleep_efficiency": 0.88,
      "deep_sleep_minutes": 90,
      "rem_sleep_minutes": 120,
      "total_sleep_minutes": 450,
      "restorative_ratio": 0.35
    }
  ],
  "hrv_records": [
    {
      "timestamp": "2024-01-01T08:00:00Z", 
      "sdnn_value": 42.3
    }
  ]
}
```

### 2. 输出格式：Baseline → 数据库

**基线计算结果**：
```json
{
  "user_id": "user_123",
  "baseline_data": {
    "sleep_baseline_hours": 7.2,
    "sleep_baseline_eff": 0.85,
    "rest_baseline_ratio": 0.32,
    "hrv_baseline_mu": 38.5,
    "hrv_baseline_sd": 8.2
  },
  "quality_metrics": {
    "data_quality_score": 0.87,
    "sample_days_sleep": 28,
    "sample_days_hrv": 35
  },
  "calculated_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-22T10:30:00Z"
}
```

### 3. 格式转换：数据库 → Readiness模块

**mapping.py需要的格式**：
```json
{
  "sleep_duration_hours": 6.8,
  "sleep_efficiency": 0.82,
  "sleep_baseline_hours": 7.2,
  "sleep_baseline_eff": 0.85,
  "rest_baseline_ratio": 0.32,
  "hrv_rmssd_today": 35.0,
  "hrv_baseline_mu": 38.5,
  "hrv_baseline_sd": 8.2
}
```

## 功能特性

- 🏃‍♂️ **个性化基线计算**：基于用户 HealthKit 历史数据计算睡眠和 HRV 个人基线
- 📊 **稳健统计算法**：使用异常值过滤和稳健统计方法，确保基线准确性
- 🔄 **智能更新机制**：支持增量更新和定期重新计算
- 💾 **多种存储后端**：支持内存、文件、SQLite 等存储方式
- ✅ **数据质量评估**：自动评估输入数据质量，确保基线可靠性

## 快速开始

### 基本用法

```python
from baseline import compute_personal_baseline
from baseline.storage import FileBaselineStorage

# 准备用户健康数据（通常来自HealthKit）
sleep_data = [
    {
        'date': '2024-01-01T00:00:00',
        'sleep_duration_hours': 7.5,
        'sleep_efficiency': 0.88,
        'deep_sleep_ratio': 0.15,
        'rem_sleep_ratio': 0.25
    },
    # ... 更多睡眠记录
]

hrv_data = [
    {
        'timestamp': '2024-01-01T08:00:00',
        'sdnn_value': 42.3  # Apple HealthKit 使用 SDNN (ms)
    },
    # ... 更多HRV记录  
]

# 计算个人基线
storage = FileBaselineStorage()
result = compute_personal_baseline(
    user_id='user_123', 
    sleep_data=sleep_data,
    hrv_data=hrv_data,
    storage=storage
)

print(f"基线计算状态: {result['status']}")
print(f"数据质量评分: {result['data_quality']}")
print(f"个人基线: {result['baseline']}")
```

### 与 readiness 模块集成

```python
from baseline import get_user_baseline
from baseline.storage import get_default_storage
from readiness.service import compute_readiness_from_payload

# 获取用户基线数据
storage = get_default_storage()
baseline = get_user_baseline('user_123', storage)

# 构造 readiness 计算请求，自动包含个人基线
payload = {
    'user_id': 'user_123',
    'sleep_duration_hours': 6.8,
    'sleep_efficiency': 0.82,
    'hrv_rmssd_today': 38.5,
    # ... 其他当天数据
}

# 注入个人基线数据
if baseline:
    payload.update(baseline.to_readiness_payload())

# 使用个性化基线计算准备度
readiness_result = compute_readiness_from_payload(payload)
```

## 📁 文件结构和作用

```
baseline/
├── __init__.py                 # 模块导出和版本信息  
├── models.py                   # 数据模型定义（SleepRecord, HRVRecord, BaselineResult）
├── calculator.py               # 基线计算核心算法
├── service.py                  # 业务逻辑和API接口（主要函数）
├── updater.py                  # 7天/30天更新逻辑（新增）
├── storage.py                  # 数据存储抽象层（SQLite/MySQL支持）
├── healthkit_integration.py    # HealthKit数据解析
├── default_baselines.py        # 新用户默认基线配置
├── examples/                   # 使用示例和测试
│   ├── basic_usage.py         
│   ├── healthkit_integration.py
│   └── readiness_integration.py
├── README.md                   # 本文档
├── QUESTIONNAIRE.md           # 新用户问卷设计
└── DEPLOYMENT_GUIDE.md        # 完整部署指南（重要！）
```

### 🔑 关键文件说明

#### 1. `service.py` - 核心业务接口
```python
# 主要API函数
compute_baseline_from_healthkit_data()  # 从HealthKit计算基线
update_baseline_smart()                # 智能更新（推荐）
update_baseline_incremental()          # 7天增量更新
update_baseline_full()                # 30天完整更新
check_baseline_update_needed()         # 检查更新需求
get_baseline_update_schedule()         # 获取更新计划
```

#### 2. `updater.py` - 更新调度逻辑
```python
class BaselineUpdater:
    # 7天增量更新：新数据权重30%，旧基线权重70%
    perform_incremental_update()
    
    # 30天完整更新：重新计算全部基线参数
    perform_full_update()
    
    # 智能选择：自动判断增量还是完整更新
    smart_update()
```

#### 3. `models.py` - 数据模型
```python
@dataclass
class BaselineResult:
    sleep_baseline_hours: float      # 个人睡眠时长基线
    sleep_baseline_eff: float       # 个人睡眠效率基线
    hrv_baseline_mu: float          # 个人HRV均值基线
    hrv_baseline_sd: float          # 个人HRV标准差
    data_quality_score: float       # 数据质量评分
    # 更新跟踪字段
    update_type: str                # 'initial', 'incremental', 'full'
    last_incremental_update: datetime
    last_full_update: datetime
```

#### 4. `DEPLOYMENT_GUIDE.md` - 部署指南⭐
**完整的生产部署文档，包含**：
- 详细的API接口规范
- 与Readiness模块集成代码
- 定时任务配置
- 监控和维护指南
- 常见问题解决方案

## 核心组件

### 1. 数据模型 (`models.py`)

定义了结构化的健康数据模型：

- **`SleepRecord`**: 睡眠记录，包含时长、效率、恢复性睡眠等
- **`HRVRecord`**: HRV记录，支持SDNN值和测量上下文  
- **`BaselineResult`**: 基线计算结果，包含所有个人基线参数

### 2. 基线计算器 (`calculator.py`)

核心算法组件：

- **异常值过滤**: 使用百分位数方法过滤不正常的数据点
- **稳健统计**: 采用修剪均值和稳健标准差，减少极值影响
- **数据质量评估**: 从数据量、完整性、时间分布等多维度评估
- **调整因子**: 为不同基线水平的用户提供个性化调整建议

### 3. 存储管理 (`storage.py`)

支持多种存储后端：

- **`MemoryBaselineStorage`**: 内存存储（开发测试用）
- **`FileBaselineStorage`**: 文件存储（简单部署）  
- **`SQLiteBaselineStorage`**: SQLite数据库（生产推荐）

### 4. 服务接口 (`service.py`)

业务逻辑封装：

- **`compute_personal_baseline()`**: 主要计算接口
- **`update_baseline_if_needed()`**: 智能更新判断
- **`compute_baseline_from_healthkit()`**: HealthKit数据直接处理

## 个人基线参数

计算得到的个人基线包括：

### 睡眠基线
- **`sleep_baseline_hours`**: 个人平均睡眠时长
- **`sleep_baseline_eff`**: 个人平均睡眠效率  
- **`rest_baseline_ratio`**: 个人恢复性睡眠比例基线

### HRV基线
- **`hrv_baseline_mu`**: 个人HRV均值（SDNN，单位ms）
- **`hrv_baseline_sd`**: 个人HRV标准差

### 质量指标
- **`data_quality_score`**: 数据质量评分 (0-1)
- **`sample_days_sleep/hrv`**: 有效数据天数

## 基线更新策略

### 更新触发条件

1. **首次计算**: 用户首次使用时从历史数据计算
2. **定期更新**: 每7天自动检查是否需要更新
3. **质量驱动**: 当数据质量评分<0.7时主动更新
4. **完整重算**: 每30天完整重新计算基线

### 更新方式

- **增量更新**: 使用最近7天数据进行滑动平均更新
- **完整重算**: 重新分析过去30天完整数据
- **自适应更新**: 检测到生活模式显著变化时触发

## 与 readiness 模块的集成

### 自动基线注入

现有的 `readiness/mapping.py` 已经包含基线支持逻辑：

```python
# mapping.py 中的现有代码会自动使用基线调整阈值
good_dur_threshold = 7.0 if mu_dur is None else max(7.0, mu_dur - 0.5)
```

当 payload 包含个人基线时：
- `sleep_baseline_hours` → `mu_dur` → 动态调整睡眠时长阈值
- `sleep_baseline_eff` → `mu_eff` → 动态调整睡眠效率阈值  
- `hrv_baseline_mu/sd` → 使用Z分数进行HRV趋势判断

### 阈值个性化示例

```python
# 用户A: 短睡眠高效型
baseline_A = {
    'sleep_baseline_hours': 6.5,  # 平均只需6.5小时
    'sleep_baseline_eff': 0.92    # 但效率很高
}
# 对于用户A，6.5小时睡眠被判定为 "good"

# 用户B: 长睡眠需求型  
baseline_B = {
    'sleep_baseline_hours': 8.2,  # 需要8.2小时才恢复
    'sleep_baseline_eff': 0.78    # 效率相对较低
}
# 对于用户B，7.5小时睡眠仅被判定为 "poor"
```

## 数据质量要求

### 最低数据要求

- **睡眠数据**: 至少15天的有效记录
- **HRV数据**: 至少10个有效测量值
- **时间跨度**: 建议涵盖至少2周的数据

### 数据质量评分构成

- **数据量 (40%)**: 基于样本数量，30天睡眠+50个HRV为满分
- **完整性 (30%)**: 恢复性睡眠数据的完整程度
- **时间分布 (20%)**: 数据在时间轴上的分布均匀性
- **计算成功率 (10%)**: 基线参数计算的成功情况

## 使用注意事项

### 1. 数据隐私
- 本模块仅存储计算后的基线统计结果
- 不保存用户原始健康数据
- 支持用户随时删除个人基线数据

### 2. 计算准确性
- 建议至少30天历史数据以获得稳定基线
- 异常值过滤可能会排除极端但真实的数据点
- 基线会随时间和生活方式变化而需要更新

### 3. 性能考虑
- 基线计算为CPU密集型操作，建议在后台执行
- 支持缓存计算结果，避免重复计算
- 大批量用户建议使用队列处理

## 环境配置

```bash
# 设置存储类型
export BASELINE_STORAGE_TYPE=sqlite  # memory, file, sqlite

# SQLite存储配置
export BASELINE_DB_PATH=/path/to/baseline.db

# 文件存储配置  
export BASELINE_STORAGE_DIR=/path/to/baseline_data
```

## 🔄 自动化和更新机制

### 数据不足时的处理策略

```python
# 永不报错，智能降级
result = compute_baseline_from_healthkit_data(user_id, sleep_data, hrv_data)

# 结果状态
if result['status'] == 'success':
    # 30天+数据，个人基线
    pass
elif result['status'] == 'success_with_defaults': 
    # <30天数据，默认基线
    pass  
elif result['status'] == 'success_with_fallback':
    # 异常情况，兜底基线
    pass
```

### 30天自动升级机制

```python
# 定时任务自动检测和升级
from baseline.auto_upgrade import BaselineAutoUpgrade

upgrader = BaselineAutoUpgrade(storage, data_service)

# 检查升级资格
eligibility = await upgrader.check_upgrade_eligibility(user_id)
if eligibility['eligible']:
    # 自动升级到个人基线
    result = await upgrader.auto_upgrade_to_personal(user_id)
```

### 微服务单用户更新

```python
# API接口：更新指定用户基线
POST /api/baseline/user/{user_id}/update

# 智能选择：7天增量 or 30天完整
update_result = update_baseline_smart(
    user_id=user_id,
    sleep_data=recent_data,
    hrv_data=recent_hrv_data,
    storage=storage
)
```

## 🧠 与Readiness个性化CPT集成

### CPT表自动更新机制

当用户基线更新时，自动触发Readiness服务的CPT表个性化：

```python
# 基线更新 → 消息队列 → CPT表更新
await message_queue.publish('readiness.user_baseline_updated', {
    'user_id': user_id,
    'baseline': baseline,
    'timestamp': datetime.now().isoformat()
})

# Readiness服务接收消息并更新CPT
@message_queue.subscribe('readiness.user_baseline_updated')
async def update_user_cpt(message):
    cpt_manager = PersonalizedCPTManager()
    await cpt_manager.update_user_cpt(message['user_id'], message['baseline'])
```

### 个性化CPT调整逻辑

```python
# 基于个人基线调整CPT概率
if baseline_hours < 7.0:  # 短睡眠型用户
    cpt['good']['sleep_6h'] *= 1.3  # 6小时睡眠给予更高good概率
elif baseline_hours > 8.0:  # 长睡眠型用户
    cpt['poor']['sleep_6h'] *= 1.4  # 6小时睡眠给予更高poor概率

# HRV基线调整
if hrv_baseline < 30:  # 低HRV基线用户
    cpt['stable']['slight_decline'] *= 0.8  # 相同HRV下降给予更宽松评价
```

详细的微服务集成方案请参考项目根目录的 `MICROSERVICES_INTEGRATION.md`

## 📈 生产部署

### 完整部署文档
- 📋 **快速部署清单**: `/BASELINE_DEPLOYMENT_CHECKLIST.md` 
- 📖 **详细技术文档**: `baseline/DEPLOYMENT_GUIDE.md`
- 🏗️ **微服务架构**: `/MICROSERVICES_INTEGRATION.md`

### 关键特性
- ✅ **零错误保证**: 数据不足时自动降级，永不失败
- 🔄 **自动化管理**: 30天升级、7天更新、质量监控
- 🎯 **个性化CPT**: 基线更新自动触发readiness个性化
- 🚀 **生产就绪**: Docker、监控、告警、容错全套方案

## 扩展开发

### 添加新的基线类型

1. 在 `models.py` 中扩展 `BaselineResult` 模型
2. 在 `calculator.py` 中添加对应的计算方法
3. 更新 `service.py` 中的处理逻辑
4. 修改 `readiness/mapping.py` 支持新的基线参数

### 自定义存储后端

```python
from baseline.storage import BaselineStorage

class CustomStorage(BaselineStorage):
    def save_baseline(self, baseline: BaselineResult) -> bool:
        # 实现自定义保存逻辑
        pass
    
    def get_baseline(self, user_id: str) -> Optional[BaselineResult]:
        # 实现自定义读取逻辑  
        pass
```

## 版本历史

- **v1.1.0**: 完整的微服务架构，自动升级机制，CPT个性化
- **v1.0.0**: 初始版本，支持睡眠和HRV基线计算