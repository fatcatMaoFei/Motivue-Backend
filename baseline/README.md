# Baseline（个人基线）模块

个人健康基线管理，为 Readiness 准备度评估提供“个体阈值”（睡眠/HRV 等）的长期个性化支持。

## 快速开始

```python
from baseline import (
    compute_baseline_from_healthkit_data,
    update_baseline_if_needed,
    SQLiteBaselineStorage,
)

storage = SQLiteBaselineStorage("baseline.db")

# 1) 计算个人基线（建议 >=30 天数据）
result = compute_baseline_from_healthkit_data(
    user_id="user123",
    healthkit_sleep_data=sleep_data,   # 近 30 天 HealthKit 睡眠
    healthkit_hrv_data=hrv_data,       # 近 30 天 HealthKit HRV
    storage=storage,
)

# 2) 集成到 Readiness（把个人阈值注入 payload）
baseline = storage.get_baseline("user123")
if baseline:
    readiness_payload.update(baseline.to_readiness_payload())

# 3) 智能更新（7 天增量 / 30 天完整）
update_baseline_if_needed(
    user_id="user123",
    new_sleep_data=recent_sleep_data,
    new_hrv_data=recent_hrv_data,
    storage=storage,
)
```

## 功能概览
- 个人基线计算：基于 HealthKit 近 30 天计算睡眠/HRV 个体阈值
- 默认基线（数据不足）：问卷分型 + 年龄段生成初始基线
- 智能更新：7 天增量 + 30 天完整重算；按数据质量/时间窗触发
- 无缝集成：Readiness 映射层自动使用基线阈值（有则用个人，无则用默认）

## 新用户默认基线（<30 天）
问卷两项得到初始分型：
- 睡眠类型：short_sleeper / normal_sleeper / long_sleeper
- HRV 类型：high_hrv / normal_hrv / low_hrv

当数据不足时，`compute_baseline_from_healthkit_data` 会返回 `success_with_defaults` 并给出默认阈值；数据充足后自动切换为 `success`（个人基线）。

## 输入数据格式（摘要）
睡眠（HealthKit）：日期、总时长（分钟）、效率（0..1/0..100）、深睡/REM、在床时长等；
HRV（HealthKit）：时间戳、SDNN（毫秒）及可选上下文。

你也可以只提供“日聚合”的睡眠时长/效率与 HRV 均值/标准差，模块会自动适配。

## Readiness 集成点
`readiness/mapping.py` 已内置对基线的支持，payload 存在以下字段时将启用“个体阈值”：
- `sleep_baseline_hours`（调整睡眠时长阈值）
- `sleep_baseline_eff`（调整睡眠效率阈值）
- `rest_baseline_ratio`（恢复性睡眠比例基线）
- `hrv_baseline_mu` / `hrv_baseline_sd`（按 Z 分数判定 HRV 趋势）

示例：
```python
good_dur_threshold = 7.0 if mu_dur is None else max(7.0, mu_dur - 0.5)
```

## 更新策略
触发：首次；距上次更新 >7 天；质量评分 <0.7；或定期完整重算（30 天）。
- 增量更新：最近 7 天滑动更新（平滑过渡）
- 完整重算：近 30 天重新估计全部参数
- 智能更新：`update_baseline_if_needed` 自动选择增量/完整

## 存储后端
支持内存/文件/SQLite（生产推荐）等：
```python
from baseline.storage import MemoryBaselineStorage, FileBaselineStorage, SQLiteBaselineStorage
```

## 服务化示例（FastAPI 摘要）
```python
from fastapi import FastAPI
from baseline import compute_baseline_from_healthkit_data
from baseline.storage import SQLiteBaselineStorage

app = FastAPI()
storage = SQLiteBaselineStorage("baseline.db")

@app.post("/api/v1/baseline/calculate")
async def calculate(req):
    return compute_baseline_from_healthkit_data(
        user_id=req.user_id,
        healthkit_sleep_data=req.sleep_data,
        healthkit_hrv_data=req.hrv_data,
        storage=storage,
    )
```

## 与个性化 CPT 的关系
Baseline 解决“阈值个体化”（长期特征），而个性化 CPT（个体化 P(evidence|state)）解决“证据响应个体化”。两者互补：
- 先用 Baseline 调整映射阈值（如睡眠 good/medium/poor 的判定）；
- 再用个性化 CPT 更新证据的状态似然（如苹果睡眠分、HRV 趋势对状态的差异权重）。

更多细节请参见 `baseline/API_REFERENCE.md` 与 `baseline/DEPLOYMENT_GUIDE.md`。
