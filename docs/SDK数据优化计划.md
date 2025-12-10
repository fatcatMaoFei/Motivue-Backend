# Motivue SDK 数据优化计划

> 版本: 1.0  
> 日期: 2025-12-10  
> 目标: 最大化利用手环SDK数据，减少用户手动输入，提升准备度计算准确性

---

## 一、SDK数据获取确认 ✅

| 数据字段 | SDK属性/接口 | 数据类型 | 获取方式 | 确认状态 |
|---------|-------------|---------|---------|---------|
| **血氧** | `UTEModelMotionFrameItemContent.bloodOxygen` | 整数% | 每分钟采样 | ✅ 可获取 |
| **压力值** | `UTEModeStressOneData.stressValue` | 0-100 | `downloadStressDataFileModel` | ✅ 可获取 |
| **情绪** | `UTEModelMotionFrameItemContent.mood` | 1:消极 2:中性 3:积极 | 每分钟采样 | ✅ 可获取 |
| **PAI** | `LowPAI/midPAI/highPAI` | 整数 | 每分钟采样 | ✅ 可获取 |
| **PAI时长** | `LowPAIDuration/midPAIDuration/highPAIDuration` | 分钟 | 每分钟采样 | ✅ 可获取 |
| **训练负荷** | `UTEModeSportRecordSummary.loadPeak` | 整数AU | 运动记录 | ✅ 可获取 |
| **有氧训练效果** | `trainingEffect/aerobicEffect` | 0-5 | 运动记录 | ✅ 可获取 |
| **无氧训练效果** | `anaerobicSportsEffect/anaerobicEffect` | 0-5 | 运动记录 | ✅ 可获取 |
| **VO2max** | `oxygenConsumption` | ml/kg/min | 运动记录 | ✅ 可获取 |
| **MET** | `oxygenUptake` | 代谢当量 | 运动记录 | ✅ 可获取 |
| **恢复时间** | `recoveryTime` | 分钟 | 运动记录 | ✅ 可获取 |
| **设备体能年龄** | `fitnessAge` | 岁 | 运动记录 | ✅ 可获取 |
| **HRV** | `heartRateVariability` | 1-29低/30-60正常/61-101良好/102+优秀 | 每分钟采样 | ✅ 可获取 |
| **静息心率** | `restingHeartRate` | bpm | 日总计数据 | ✅ 可获取 |
| **心率区间** | `heartRateZone` | 1-5 | 实时运动 | ✅ 可获取 |

---

## 二、优化计划总览

### 阶段1: 准备度计算增强 (优先级 HIGH)

| 任务 | 当前状态 | 目标状态 | 涉及文件 |
|-----|---------|---------|---------|
| 设备压力值 (device_stress) | 未使用 | **仅展示** (暂不参与计算) | UI层 |
| 血氧数据 (blood_oxygen) | 未使用 | **仅展示** (暂不参与计算) | UI层 |
| 设备情绪 (device_mood) | 未使用 | **仅展示** (暂不参与计算) | UI层 |
| 训练负荷智能融合 | 50%手动+50%SDK | **保持**: 有啥用啥，都有就平分 | `engine.py` |
| 有氧/无氧训练效果 | 未使用 | 作为训练质量证据 | `constants.py`, `mapping.py` |
| 设备恢复状态 (device_recovery) | 刚加入 | **参与计算** | `constants.py`, `mapping.py` |

**重要原则**: 
- ⚠️ **Hooper主观评分逻辑不变**，保持原有权重
- `device_stress`、`device_mood`、`blood_oxygen` → **暂时只展示，不参与计算**
- `device_recovery`、`aerobic/anaerobic_training_effect` → **参与计算**

### 阶段2: 生理年龄计算增强 (优先级 HIGH)

| 任务 | 当前状态 | 目标状态 | 涉及文件 | 科学依据 |
|-----|---------|---------|---------|----------|
| **VO2max加入生理年龄计算** | 未使用 | 权重 -8.0 (最高) | `physio/core.py` | ACSM标准，与全因死亡率强相关 |
| **恢复时间加入生理年龄计算** | 未使用 | 权重 -3.0 | `physio/core.py` | 心血管恢复效率指标 |
| **周PAI加入生理年龄计算** | 未使用 | 权重 -2.0 | `physio/core.py` | HUNT研究 (N>55,000) |
| 对比设备fitnessAge | 未使用 | 交叉验证/展示 | `physio/core.py` | 设备算法对比 |
| 性别/年龄调整基准 | 固定基准 | 动态基准 | `physio/core.py` | 男女VO2max差异约15% |

**新增指标科学依据**:
- **VO2max**: 每10年下降5-10%，是心肺功能最核心指标 (Cooper Institute)
- **恢复时间**: 恢复快(<6h)说明心血管效率高
- **PAI**: PAI≥100/周可降低心血管风险25% (HUNT研究)

### 阶段3: 展示层数据丰富 (优先级 MEDIUM)

| 任务 | 当前状态 | 目标状态 |
|-----|---------|---------|
| PAI仪表盘 | 未展示 | 周PAI累积图表 |
| 血氧趋势 | 未展示 | 日血氧波动图 |
| 训练效果可视化 | 未展示 | 有氧/无氧效果仪表盘 |
| 恢复时间展示 | 未展示 | 恢复状态进度条 |

---

## 三、详细实施方案

### 3.1 设备压力值 (device_stress) - 仅展示

**状态**: ⚠️ **暂不参与准备度计算，仅在仪表盘展示**

**数据来源**: SDK `UTEModeStressOneData.stressValue` (0-100)

**展示方式**:
- 日压力趋势图 (每小时平均值)
- 压力等级分布饼图
- 与Hooper主观压力评分对比展示

**后续考虑**: 如果用户反馈希望客观压力影响分数，可添加CPT：
```python
# 预留CPT (暂不启用)
'device_stress': {
    'relaxed': {...},  # 0-25
    'normal':  {...},  # 26-50  
    'medium':  {...},  # 51-75
    'high':    {...},  # 76-100
}
```

---

### 3.2 血氧数据 (blood_oxygen) - 仅展示

**状态**: ⚠️ **暂不参与准备度计算，仅在仪表盘展示**

**数据来源**: SDK `UTEModelMotionFrameItemContent.bloodOxygen` (%)

**展示方式**:
- 夜间睡眠血氧趋势图
- 日平均血氧值
- 血氧异常预警 (低于90%提示)

**后续考虑**: 如果需要参与计算，可添加CPT：
```python
# 预留CPT (暂不启用)
'blood_oxygen': {
    'excellent': {...},  # >=98%
    'normal':    {...},  # 95-97%
    'low':       {...},  # 90-94%
    'very_low':  {...},  # <90%
}
```

**注意**: 夜间睡眠血氧更有参考价值，建议取睡眠期间平均值

---

### 3.3 设备情绪 (device_mood) - 仅展示

**状态**: ⚠️ **暂不参与准备度计算，仅在仪表盘展示**

**数据来源**: SDK `UTEModelMotionFrameItemContent.mood` (1:消极 2:中性 3:积极)

**展示方式**:
- 日情绪状态分布图
- 情绪趋势变化图
- 与Hooper主观评分对比展示

**后续考虑**: 如果需要参与计算，可添加CPT：
```python
# 预留CPT (暂不启用)
'device_mood': {
    'positive': {...},  # mood=3
    'neutral':  {...},  # mood=2
    'negative': {...},  # mood=1
}
```

---

### 3.4 有氧/无氧训练效果 (training_effect)

**当前**: 未使用

**优化**: 作为训练质量证据，影响次日准备度

```python
# constants.py 新增
'aerobic_training_effect': {
    # 昨日训练效果 → 今日状态影响
    'none':       {'Peak': 0.40, 'Well-adapted': 0.50, 'FOR': 0.45, 'Acute Fatigue': 0.40, 'NFOR': 0.35, 'OTS': 0.30},  # 0-0.9 无效果
    'minor':      {'Peak': 0.55, 'Well-adapted': 0.60, 'FOR': 0.50, 'Acute Fatigue': 0.40, 'NFOR': 0.30, 'OTS': 0.25},  # 1.0-1.9 轻微
    'maintaining':{'Peak': 0.65, 'Well-adapted': 0.70, 'FOR': 0.55, 'Acute Fatigue': 0.45, 'NFOR': 0.30, 'OTS': 0.20},  # 2.0-2.9 维持
    'improving':  {'Peak': 0.50, 'Well-adapted': 0.55, 'FOR': 0.60, 'Acute Fatigue': 0.55, 'NFOR': 0.40, 'OTS': 0.30},  # 3.0-3.9 提高(需恢复)
    'highly_improving': {'Peak': 0.30, 'Well-adapted': 0.40, 'FOR': 0.65, 'Acute Fatigue': 0.60, 'NFOR': 0.50, 'OTS': 0.40},  # 4.0-5.0 大幅提高(需更多恢复)
}

'anaerobic_training_effect': {
    # 无氧训练对肌肉损伤更大
    'none':       {'Peak': 0.45, 'Well-adapted': 0.50, 'FOR': 0.45, 'Acute Fatigue': 0.40, 'NFOR': 0.30, 'OTS': 0.25},
    'minor':      {'Peak': 0.50, 'Well-adapted': 0.55, 'FOR': 0.50, 'Acute Fatigue': 0.45, 'NFOR': 0.35, 'OTS': 0.30},
    'moderate':   {'Peak': 0.40, 'Well-adapted': 0.50, 'FOR': 0.55, 'Acute Fatigue': 0.55, 'NFOR': 0.45, 'OTS': 0.35},
    'high':       {'Peak': 0.25, 'Well-adapted': 0.35, 'FOR': 0.60, 'Acute Fatigue': 0.65, 'NFOR': 0.55, 'OTS': 0.50},
    'extreme':    {'Peak': 0.10, 'Well-adapted': 0.20, 'FOR': 0.55, 'Acute Fatigue': 0.70, 'NFOR': 0.70, 'OTS': 0.65},
}
```

**使用逻辑**: 
- 昨日运动的训练效果 → 影响今日Prior
- 训练效果越高，短期内状态下降概率越大（需要恢复）
- 但长期来看，适度高训练效果促进适应

---

### 3.5 训练负荷智能融合 (training_load)

**原则**: ⚠️ **保持灵活性** - 有啥用啥，都有就平分权重

**当前**: 50%手动 + 50% SDK `loadPeak` (已实现)

**保持现有逻辑**:

```python
# engine.py - 保持现有融合逻辑

def _get_training_load(self, manual_input: Optional[str], sdk_load: Optional[int]) -> str:
    """训练负荷智能融合
    
    规则:
    1. 只有手动输入 → 100%使用手动
    2. 只有SDK数据 → 100%使用SDK
    3. 两个都有 → 50%+50%平分 (取平均后映射)
    """
    
    # 手动输入映射为AU
    manual_au_map = {'无': 0, '低': 200, '中': 350, '高': 500, '极高': 700}
    
    manual_au = None
    sdk_au = None
    
    if manual_input and manual_input in manual_au_map:
        manual_au = manual_au_map[manual_input]
    
    if sdk_load is not None and sdk_load > 0:
        sdk_au = sdk_load  # SDK loadPeak 直接作为AU
    
    # 融合逻辑
    if manual_au is not None and sdk_au is not None:
        # 两个都有 → 平分
        final_au = (manual_au + sdk_au) / 2
    elif manual_au is not None:
        # 只有手动
        final_au = manual_au
    elif sdk_au is not None:
        # 只有SDK
        final_au = sdk_au
    else:
        return '无'
    
    # AU → 等级映射
    if final_au < 100:
        return '无'
    elif final_au < 250:
        return '低'
    elif final_au < 400:
        return '中'
    elif final_au < 600:
        return '高'
    else:
        return '极高'
```

**ACWR计算** (同样支持混合数据源):
```python
def _calculate_acwr(self, recent_loads: List[float]) -> float:
    """计算ACWR
    
    recent_loads: 过去28天的训练负荷列表 (AU)
    - 可以来自手动输入
    - 可以来自SDK loadPeak
    - 可以是混合的
    """
    if len(recent_loads) < 7:
        return 1.0  # 数据不足，返回中性值
    
    acute_load = sum(recent_loads[-7:]) / 7  # 过去7天平均
    chronic_load = sum(recent_loads[-28:]) / min(28, len(recent_loads))  # 过去28天平均
    
    if chronic_load < 10:  # 避免除零
        return 1.0
    
    return acute_load / chronic_load
```

**UI展示**: 
- 显示手动输入框
- 同时显示SDK检测到的训练负荷
- 用户可选择使用哪个或让系统自动融合

---

### 3.6 生理年龄计算增强

**当前算法**: `physio/core.py`
```python
base_age = 35.0
age_adjust = -8.0 * sdnn_z + -5.0 * css_z + -6.0 * rhr_z
```

**优化方案**: 加入更多SDK指标

#### 可加入的指标分析

| 指标 | SDK属性 | 科学依据 | 建议权重 | 说明 |
|-----|--------|---------|---------|------|
| SDNN (HRV) | 已有 | ⭐⭐⭐ 自主神经功能 | -6.0 → -5.0 | 保留，略降权 |
| RHR | 已有 | ⭐⭐⭐ 心脏效率 | -6.0 → -5.0 | 保留 |
| CSS | 已有 | ⭐⭐ 睡眠质量 | -5.0 → -4.0 | 保留，略降权 |
| **VO2max** | `oxygenConsumption` | ⭐⭐⭐⭐ 心肺适能核心 | **-8.0** (最高) | **新增** |
| **恢复能力** | `recoveryTime` | ⭐⭐ 心肺恢复效率 | -3.0 | **新增** |
| **周活动量** | `weeklyPAI` | ⭐⭐ 长期活动水平 | -2.0 | **可选新增** |
| 设备体能年龄 | `fitnessAge` | - | (对比展示) | 不参与计算 |

#### 科学参考数据 (文献来源)

##### VO2max 参考值 (ACSM Guidelines / Cooper Institute)

**男性 VO2max (ml/kg/min):**
| 年龄 | 优秀 | 良好 | 中等 | 较差 |
|-----|------|------|------|------|
| 20-29 | ≥55 | 43-52 | 36-42 | ≤35 |
| 30-39 | ≥52 | 40-48 | 34-39 | ≤33 |
| 40-49 | ≥50 | 38-44 | 31-37 | ≤30 |
| 50-59 | ≥45 | 34-40 | 27-33 | ≤26 |
| 60+ | ≥42 | 30-36 | 23-29 | ≤22 |

**女性 VO2max (ml/kg/min):**
| 年龄 | 优秀 | 良好 | 中等 | 较差 |
|-----|------|------|------|------|
| 20-29 | ≥49 | 38-44 | 31-37 | ≤30 |
| 30-39 | ≥45 | 34-40 | 28-33 | ≤27 |
| 40-49 | ≥42 | 32-38 | 25-31 | ≤24 |
| 50-59 | ≥38 | 28-34 | 22-27 | ≤21 |
| 60+ | ≥35 | 24-30 | 18-23 | ≤17 |

**VO2max与年龄的关系:**
- 每10年下降约 5-10%
- 久坐人群下降更快 (~10%)
- 活跃人群下降较慢 (~5%)

##### 静息心率参考值

| 年龄 | 优秀 | 良好 | 中等 | 较差 |
|-----|------|------|------|------|
| 成人 | <60 | 60-69 | 70-79 | ≥80 |
| 运动员 | <50 | 50-55 | 56-65 | ≥66 |

**RHR与年龄关系:**
- RHR相对稳定，不随年龄显著变化
- 但低RHR反映更好的心脏效率和自主神经功能

##### HRV (SDNN) 参考值

| 年龄 | 正常范围 (ms) | 良好 | 优秀 |
|-----|-------------|------|------|
| 20-29 | 100-200 | >150 | >180 |
| 30-39 | 80-180 | >130 | >160 |
| 40-49 | 60-150 | >110 | >140 |
| 50-59 | 50-130 | >90 | >120 |
| 60+ | 40-110 | >70 | >100 |

**HRV与年龄关系:**
- SDNN每10年下降约 10-15 ms
- 反映自主神经功能老化

##### 运动恢复时间参考

| 恢复能力 | 完全恢复时间 | 说明 |
|---------|------------|------|
| 优秀 | <6小时 | 心肺效率极高 |
| 良好 | 6-12小时 | 正常健康水平 |
| 中等 | 12-24小时 | 需要关注 |
| 较差 | >24小时 | 恢复能力下降 |

##### PAI (Personal Activity Intelligence) 参考

基于 HUNT 研究 (挪威，N>55,000):
- **PAI ≥100/周**: 心血管疾病风险降低 25%
- **PAI ≥50/周**: 显著健康收益
- **PAI <25/周**: 活动不足

#### 优化后的代码

```python
# physio/core.py 修改

def compute_physiological_age(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    生理年龄计算 - 增强版
    
    输入:
    - sdnn_series: SDNN序列 (≥30天)
    - rhr_series: 静息心率序列 (≥30天)
    - chronological_age: 实际年龄 (用于性别调整VO2max基准)
    - gender: 性别 ('male'/'female')
    - vo2max: 最大摄氧量 ml/kg/min (来自SDK运动记录)
    - avg_recovery_time: 平均恢复时间 分钟 (来自SDK)
    - weekly_pai: 周PAI值 (来自SDK，可选)
    - device_fitness_age: 设备计算的体能年龄 (用于对比展示)
    - 睡眠相关参数 (用于CSS计算)
    """
    
    # ... 原有 SDNN/RHR/CSS 逻辑保持不变 ...
    
    gender = payload.get('gender', 'male')
    chrono_age = payload.get('chronological_age', 35)
    
    # ========== 新增: VO2max ==========
    # 科学依据: ACSM Guidelines, Cooper Institute
    # VO2max每10年下降约5-10%，是心肺功能最重要指标
    vo2max = payload.get('vo2max')
    vo2max_z = 0.0
    if vo2max is not None:
        try:
            vo2max = float(vo2max)
            
            # 性别和年龄调整的基准值 (基于ACSM "良好"水平中值)
            if gender == 'female':
                # 女性基准: 20岁41, 30岁37, 40岁35, 50岁31, 60岁27
                vo2max_anchor = 41.0 - (chrono_age - 20) * 0.35
            else:
                # 男性基准: 20岁47, 30岁44, 40岁41, 50岁37, 60岁33
                vo2max_anchor = 47.0 - (chrono_age - 20) * 0.35
            
            vo2max_anchor = max(25.0, min(50.0, vo2max_anchor))  # 限制范围
            
            # 每6 ml/kg/min ≈ 10岁生理差异 (基于文献)
            vo2max_scale = 6.0
            vo2max_z = (vo2max - vo2max_anchor) / vo2max_scale
        except Exception:
            vo2max = None
    
    # ========== 新增: 恢复能力 ==========
    # 科学依据: 恢复时间反映心血管恢复效率
    # 完全恢复时间: <6h优秀, 6-12h良好, 12-24h中等, >24h较差
    avg_recovery = payload.get('avg_recovery_time')  # 分钟
    recovery_z = 0.0
    if avg_recovery is not None:
        try:
            avg_recovery = float(avg_recovery)
            # 基准: 540分钟(9小时) 为"良好"中值
            # 每180分钟(3小时)偏离 ≈ 0.5个z单位
            recovery_anchor = 540.0  # 9小时
            recovery_scale = 360.0   # 6小时 (半个标准差)
            recovery_z = (recovery_anchor - avg_recovery) / recovery_scale  # 短→正z
            recovery_z = max(-2.0, min(2.0, recovery_z))  # 限制极值
        except Exception:
            avg_recovery = None
    
    # ========== 新增: 周活动量 PAI (可选) ==========
    # 科学依据: HUNT研究 (N>55,000)
    # PAI≥100/周: 心血管风险降低25%
    weekly_pai = payload.get('weekly_pai')
    pai_z = 0.0
    if weekly_pai is not None:
        try:
            weekly_pai = float(weekly_pai)
            # 基准: 75 PAI为"良好"活动水平
            # 100为目标，50为最低有效
            pai_anchor = 75.0
            pai_scale = 35.0  # 标准差约35
            pai_z = (weekly_pai - pai_anchor) / pai_scale
            pai_z = max(-2.0, min(2.0, pai_z))  # 限制极值
        except Exception:
            weekly_pai = None
    
    # ========== 综合计算 ==========
    # 权重设计原则:
    # - VO2max是最重要的心肺指标，给予最高权重
    # - 权重绝对值总和控制在25-30，确保年龄范围18-80
    
    if vo2max is not None:
        # 有VO2max时的权重分配
        age_adjust = (
            -4.0 * sdnn_z +        # HRV (自主神经)
            -3.0 * css_z +         # 睡眠质量
            -4.0 * rhr_z +         # 静息心率 (心脏效率)
            -8.0 * vo2max_z +      # VO2max (心肺适能，最高权重)
            -3.0 * recovery_z +    # 恢复能力
            -2.0 * pai_z           # 活动量
        )
        # 总权重: 24
    else:
        # 无VO2max时，其他指标权重提升
        age_adjust = (
            -8.0 * sdnn_z +        # HRV (权重提升，代替VO2max)
            -5.0 * css_z +         # 睡眠
            -6.0 * rhr_z +         # 静息心率
            -3.0 * recovery_z +    # 恢复能力
            -2.0 * pai_z           # 活动量
        )
        # 总权重: 24
    
    phys_age = max(18.0, min(80.0, base_age + age_adjust))
    
    # 软权重: 70%计算值 + 30%基准值 (平滑极端情况)
    phys_age_weighted = max(18.0, min(80.0, 0.7 * phys_age + 0.3 * base_age))
    
    # ========== 设备体能年龄对比 ==========
    device_fitness_age = payload.get('device_fitness_age')
    comparison = None
    if device_fitness_age is not None:
        try:
            device_age = float(device_fitness_age)
            diff = phys_age - device_age
            comparison = {
                'device_age': int(device_age),
                'calculated_age': round(phys_age),
                'difference': round(diff, 1),
                'agreement': 'good' if abs(diff) < 3 else 'moderate' if abs(diff) < 7 else 'low'
            }
        except Exception:
            pass
    
    return {
        "status": "ok",
        "physiological_age": round(phys_age),
        "physiological_age_weighted": round(phys_age_weighted, 1),
        "css_details": css_res,
        "device_comparison": comparison,
        "inputs_used": {
            "sdnn": sdnn_mean is not None,
            "rhr": rhr_mean is not None,
            "css": css_value is not None,
            "vo2max": vo2max is not None,
            "recovery": avg_recovery is not None,
            "pai": weekly_pai is not None,
        },
        "z_scores": {
            "sdnn_z": round(sdnn_z, 2),
            "rhr_z": round(rhr_z, 2),
            "css_z": round(css_z, 2),
            "vo2max_z": round(vo2max_z, 2) if vo2max else None,
            "recovery_z": round(recovery_z, 2) if avg_recovery else None,
            "pai_z": round(pai_z, 2) if weekly_pai else None,
        },
        "reference_values": {
            "vo2max_anchor": round(vo2max_anchor, 1) if vo2max else None,
            "recovery_anchor_min": 540,
            "pai_anchor": 75,
        },
        "data_days_count": {"sdnn": len(sdnn), "rhr": len(rhr)},
    }
```

#### 权重设计说明

| 指标 | 有VO2max时 | 无VO2max时 | 科学依据 |
|-----|-----------|-----------|----------|
| **VO2max** | **-8.0** | - | 心肺适能核心指标，与全因死亡率强相关 |
| SDNN (HRV) | -4.0 | -8.0 | 自主神经功能，无VO2时成为核心指标 |
| RHR | -4.0 | -6.0 | 心脏效率，低RHR反映更好的心脏适应性 |
| CSS (睡眠) | -3.0 | -5.0 | 恢复性睡眠对健康至关重要 |
| Recovery | -3.0 | -3.0 | 心血管恢复效率 |
| PAI | -2.0 | -2.0 | 长期活动水平 (HUNT研究支持) |
| **总权重** | **-24** | **-24** | 控制年龄范围在18-80 |

#### 参数校准说明

**VO2max 基准值公式:**
```
男性: anchor = 47.0 - (age - 20) × 0.35
女性: anchor = 41.0 - (age - 20) × 0.35

示例 (男性):
- 20岁: 47.0 ml/kg/min
- 30岁: 43.5 ml/kg/min
- 40岁: 40.0 ml/kg/min
- 50岁: 36.5 ml/kg/min
- 60岁: 33.0 ml/kg/min

scale = 6.0 (每6 ml/kg/min ≈ 10岁生理差异)
```

**恢复时间 基准值:**
```
anchor = 540分钟 (9小时)
scale = 360分钟 (6小时)

示例:
- 3小时恢复: z = (540-180)/360 = 1.0 → 年龄 -3岁
- 9小时恢复: z = 0 → 年龄 ±0岁
- 15小时恢复: z = -1.0 → 年龄 +3岁
```

**PAI 基准值:**
```
anchor = 75 PAI/周
scale = 35

示例:
- PAI 150: z = 2.14 → 年龄 -4岁
- PAI 100: z = 0.71 → 年龄 -1.4岁
- PAI 75: z = 0 → 年龄 ±0岁
- PAI 40: z = -1.0 → 年龄 +2岁
```

#### 极端情况验证

**最年轻场景** (优秀运动员):
```
SDNN_z = +2.0, RHR_z = +2.0, CSS_z = +1.5
VO2max_z = +2.5, Recovery_z = +1.5, PAI_z = +2.0

age_adjust = -4×2 + -3×1.5 + -4×2 + -8×2.5 + -3×1.5 + -2×2
           = -8 - 4.5 - 8 - 20 - 4.5 - 4 = -49
phys_age = max(18, 35 - 49) = 18岁 ✓
```

**最年老场景** (健康问题):
```
SDNN_z = -2.0, RHR_z = -2.0, CSS_z = -1.5
VO2max_z = -2.5, Recovery_z = -1.5, PAI_z = -2.0

age_adjust = -4×(-2) + -3×(-1.5) + -4×(-2) + -8×(-2.5) + -3×(-1.5) + -2×(-2)
           = 8 + 4.5 + 8 + 20 + 4.5 + 4 = +49
phys_age = min(80, 35 + 49) = 80岁 ✓
```

**典型场景** (40岁良好水平):
```
所有z ≈ 0
phys_age ≈ 35岁 (基准值)
weighted_age = 0.7×35 + 0.3×35 = 35岁
```

---

### 3.7 PAI (Personal Activity Intelligence)

**当前**: 未使用

**优化**: 作为长期健康趋势指标展示 + 参与周报评估

```python
# 新增 pai_calculator.py

def calculate_weekly_pai(daily_pai_data: List[Dict]) -> Dict[str, Any]:
    """计算周PAI总分
    
    daily_pai_data: 过去7天的PAI数据
    [
        {'LowPAI': 10, 'midPAI': 15, 'highPAI': 8, ...},
        ...
    ]
    
    目标: 周PAI >= 100 分可降低心血管疾病风险
    """
    total_pai = 0
    for day in daily_pai_data:
        # PAI算法: 高强度贡献更多
        daily = (day.get('LowPAI', 0) * 1.0 + 
                 day.get('midPAI', 0) * 2.0 + 
                 day.get('highPAI', 0) * 3.0)
        total_pai += daily
    
    # 状态判断
    if total_pai >= 100:
        status = 'optimal'
        message = '本周活动量达标，心血管健康受益'
    elif total_pai >= 75:
        status = 'good'
        message = '本周活动量良好，继续保持'
    elif total_pai >= 50:
        status = 'moderate'
        message = '本周活动量中等，建议增加高强度活动'
    else:
        status = 'low'
        message = '本周活动量不足，建议增加运动'
    
    return {
        'weekly_pai': round(total_pai, 1),
        'target': 100,
        'percentage': min(100, round(total_pai)),
        'status': status,
        'message': message,
    }
```

---

## 四、数据流优化架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SDK 数据采集层                                │
│  每分钟: 心率、血氧、压力、情绪、HRV、PAI                             │
│  运动结束: loadPeak、trainingEffect、VO2max、recoveryTime、fitnessAge │
│  每日同步: 睡眠数据、日活总计                                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      数据预处理层 (DataProcessor)                    │
│  - 血氧: 取睡眠期间平均值                                             │
│  - 压力: 取日间平均值                                                 │
│  - 情绪: 取最频繁状态                                                 │
│  - HRV: 计算3日/7日/28日平均                                         │
│  - 训练负荷: 累加当日所有运动loadPeak                                 │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
     ┌──────────────────────┼──────────────────────┐
     │                      │                      │
     ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│ 参与计算的数据   │  │ 仅展示的数据    │  │      其他模块           │
│                 │  │ (暂不影响分数)   │  │                         │
├─────────────────┤  ├─────────────────┤  │  生理年龄:              │
│ Hooper主观评分: │  │ device_stress   │  │    - vo2max             │
│  fatigue  0.75  │  │   → 趋势图展示  │  │    - device_fitness_age │
│  stress   0.70  │  │ device_mood     │  │                         │
│  soreness 0.65  │  │   → 趋势图展示  │  │  周报:                  │
│  sleep    0.60  │  │ blood_oxygen    │  │    - weekly_pai         │
│                 │  │   → 趋势图展示  │  │    - recovery_time_avg  │
│ SDK计算数据:    │  │ PAI             │  │                         │
│  device_recovery│  │   → 周累积展示  │  │  仪表盘展示:            │
│           0.80  │  │                 │  │    - 所有原始数据       │
│  aerobic_eff.   │  │                 │  │    - 客观压力趋势图     │
│           0.55  │  │                 │  │    - 客观情绪趋势图     │
│  anaerobic_eff. │  │                 │  │    - 血氧趋势图         │
│           0.50  │  │                 │  │                         │
│                 │  │                 │  │                         │
│ training_load   │  │                 │  │                         │
│  (手动/SDK融合) │  │                 │  │                         │
└────────┬────────┘  └─────────────────┘  └─────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│        准备度引擎 (ReadinessEngine)      │
│                                          │
│  参与计算:                               │
│  - Hooper主观评分 (不变)                 │
│  - device_recovery                       │
│  - aerobic/anaerobic_training_effect     │
│  - training_load (手动/SDK融合)          │
│  - hrv_trend, sleep_performance 等       │
│                                          │
│  暂不参与:                               │
│  - device_stress (仅展示)                │
│  - device_mood (仅展示)                  │
│  - blood_oxygen (仅展示)                 │
└─────────────────────────────────────────┘
```

**关键原则**:
1. **Hooper主观评分不变** - 权重保持原样
2. **device_stress/mood/blood_oxygen** - 暂时只展示，不影响分数
3. **device_recovery/training_effect** - 参与计算
4. **训练负荷融合** - 可手动、可SDK、可混合

---

## 五、实施优先级排序

### P0 - 立即实施 (本周)

1. **训练负荷融合逻辑确认** - 保持: 有啥用啥，都有就平分
2. **aerobic/anaerobic_training_effect** - 训练质量证据，参与计算
3. **device_recovery** - 你已加入，确认CPT和权重

### P1 - 短期实施 (下周)

4. **VO2max加入生理年龄** - 权重 -8.0，心肺核心指标
   - 数据源: `UTEModeSportRecordSummary.oxygenConsumption`
   - 基准: 男性 47-(age-20)×0.35, 女性 41-(age-20)×0.35
   - scale = 6.0 ml/kg/min

5. **恢复时间加入生理年龄** - 权重 -3.0，心血管恢复效率
   - 数据源: `UTEModeSportRecordSummary.recoveryTime`
   - 基准: 540分钟(9小时)
   - scale = 360分钟

6. **周PAI加入生理年龄** - 权重 -2.0，长期活动水平
   - 数据源: `weeklyPAI` (累积计算)
   - 基准: 75 PAI
   - scale = 35

7. **device_fitness_age对比** - 生理年龄页面展示设备计算值

### P2 - 中期实施 (2周内) - 仪表盘展示

6. **device_stress展示** - 客观压力趋势图 (⚠️ 仅展示，不影响分数)
7. **device_mood展示** - 客观情绪趋势图 (⚠️ 仅展示，不影响分数)
8. **blood_oxygen展示** - 血氧趋势图 (⚠️ 仅展示，不影响分数)
9. **PAI展示** - 周PAI累积图表
10. **恢复时间趋势** - 恢复状态可视化

### P3 - 长期优化

11. **个性化CPT云端同步** - 基于用户数据调整
12. **异常检测预警** - 血氧/心率异常
13. **训练建议生成** - 基于当前状态
14. **评估是否让展示数据参与计算** - 根据用户反馈决定

---

## 六、证据权重表

**原则**: ⚠️ **Hooper主观评分权重保持不变**

```python
EVIDENCE_WEIGHTS_FITNESS = {
    # ========== 核心客观数据 ==========
    "hrv_trend": 1.0,              # HRV趋势 - 核心指标
    "device_recovery": 0.80,       # 设备恢复状态 - 直接关联
    
    # ========== 睡眠相关 (权重不变) ==========
    "restorative_sleep": 0.95,     # 恢复性睡眠
    "sleep_performance": 0.90,     # 睡眠表现
    
    # ========== Hooper主观评分 (保持不变!) ==========
    "subjective_fatigue": 0.75,    # 主观疲劳 ← 不变
    "subjective_stress": 0.70,     # 主观压力 ← 不变
    "muscle_soreness": 0.65,       # 肌肉酸痛 ← 不变
    "subjective_sleep": 0.60,      # 主观睡眠 ← 不变
    
    # ========== 训练相关 (新增) ==========
    "aerobic_training_effect": 0.55,   # 有氧训练效果
    "anaerobic_training_effect": 0.50, # 无氧训练效果
    
    # ========== 其他 (保持不变) ==========
    "nutrition": 0.60,
    "gi_symptoms": 0.50,
}
```

### ⚠️ 暂时只做展示、不参与准备度计算的数据

以下三个SDK数据**暂时只在仪表盘展示**，不加入EMISSION_CPT：

| 数据 | 用途 | 说明 |
|-----|------|-----|
| `device_stress` | 仪表盘展示客观压力趋势 | 供用户参考对比，不影响分数 |
| `device_mood` | 仪表盘展示客观情绪趋势 | 供用户参考对比，不影响分数 |
| `blood_oxygen` | 仪表盘展示血氧趋势 | 健康监测展示，不影响分数 |

**后续如果需要加入计算，再添加对应的CPT和权重。**

---

## 七、待确认事项

1. **SDK数据采集频率**: 确认每分钟采样是否稳定
2. **客观压力展示方式**: UI如何展示device_stress供用户参考对比
3. **VO2max准确性**: 设备端VO2max计算算法可靠性
4. **PAI算法**: 确认SDK PAI与官方PAI算法一致性
5. **个性化CPT云端同步**: 频率和数据格式
6. **训练负荷融合UI**: 如何让用户选择手动/SDK/混合模式

---

## 八、测试计划

1. **单元测试**: 每个新增mapping函数
2. **集成测试**: 完整数据流从SDK到准备度分数
3. **回归测试**: 确保原有功能不受影响
4. **用户验收**: 对比新旧版本准备度分数差异

---

*文档作者: AI Assistant*  
*最后更新: 2025-12-10*

