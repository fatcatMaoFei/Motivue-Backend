# Motivue iOS SwiftUI SDK 交接文档

> 版本: 1.2  
> 日期: 2025-12-10  
> 用途: 将 Motivue-Backend 微服务计算逻辑迁移至 iOS 本地计算  
> 更新: 整合SDK数据优化计划，新增VO2max/恢复时间/PAI等指标

---

## 一、文档概述

### 1.1 迁移背景
原 Motivue-Backend 是一个 Python 微服务架构，包含以下核心模块：
- **Readiness Engine (准备度引擎)** - 贝叶斯状态推断
- **Personal Baseline (个人基线)** - 睡眠/HRV 基线计算
- **Physiological Age (生理年龄)** - CSS睡眠评分 + 生理年龄估算
- **Weekly Report (周报系统)** - 需要 LLM，保持联网
- **Journal (日志记录)** - 类似WHOOP，仅记录不参与计算

**迁移原则：**
- 除周报外，所有功能迁移至 iOS 本地计算
- 每分钟采集原始数据
- 使用 UTEBluetoothRYApi SDK 获取手环数据
- 同时支持 Apple HealthKit 数据源
- **个人基线本地存储**
- **个性化CPT表云端同步更新**
- **不使用苹果睡眠评分，只用原始睡眠数据**
- **Journal只做记录，不参与准备度计算**

### 1.2 文档结构
```
Motivue_iOS_SDK_交接文档.md        # 本文档 - 主索引
├── 01_SDK数据接口.md              # SDK接口与数据获取
├── 02_数据模型定义.md             # Swift 数据结构
├── 03_基线计算逻辑.md             # 个人基线算法
├── 04_准备度引擎.md               # 贝叶斯推断核心
├── 05_CSS与生理年龄.md            # 睡眠评分与生理年龄
├── 06_常量与CPT表.md              # 概率表与配置
└── 07_周报API对接.md              # 联网周报接口
```

---

## 二、系统架构总览

### 2.1 核心模块依赖关系

```
┌─────────────────────────────────────────────────────────────────┐
│                        iOS App (SwiftUI)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │ SDK数据层   │    │HealthKit层 │    │   本地存储 (Core    │  │
│  │UTEBluetooth │    │  Apple数据  │    │   Data / SQLite)    │  │
│  │   RYApi     │    │             │    │ - 个人基线          │  │
│  └──────┬──────┘    └──────┬──────┘    │ - 历史数据          │  │
│         │                  │           │ - Journal记录       │  │
│         └────────┬─────────┘           └──────────┬──────────┘  │
│                  ▼                                │              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    数据聚合层 (DataAggregator)               │ │
│  │   - 每分钟原始数据采集                                        │ │
│  │   - 数据归一化与验证                                          │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                             ▼                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ 基线计算模块  │  │ CSS睡眠评分  │  │    准备度引擎           │ │
│  │PersonalBase  │  │  模块        │  │ (ReadinessEngine)       │ │
│  │lineCalculator│  │              │  │ - Prior计算             │ │
│  │ (本地存储)   │──▶│              │──▶│ - Posterior更新        │ │
│  │              │  │              │  │ - 贝叶斯推断            │ │
│  └──────────────┘  └──────────────┘  └───────────┬─────────────┘ │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼─────────────┐ │
│  │           云端同步层 (CloudSync)              ▼             │ │
│  │  ┌──────────────────┐    ┌──────────────────────────────┐  │ │
│  │  │ 个性化CPT表同步   │    │      周报模块 (需联网)        │  │ │
│  │  │ - 定期拉取更新    │    │ - 数据打包上传                │  │ │
│  │  │ - 用户画像CPT     │    │ - LLM 生成报告                │  │ │
│  │  └──────────────────┘    └──────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           Journal 日志模块 (仅记录，不参与计算)               │ │
│  │   - 类似WHOOP日志                                            │ │
│  │   - 行为记录 (酒精/咖啡因/屏幕等)                             │ │
│  │   - 仅用于用户回顾，不影响准备度分数                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  UI展示层 (SwiftUI Views)                    │ │
│  │   - 实时准备度分数                                            │ │
│  │   - 趋势图表                                                  │ │
│  │   - 状态诊断                                                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 SDK完整数据采集能力

#### 实时采集数据 (每分钟)

| 数据类型 | SDK属性 | 数据类型 | 用途 |
|---------|---------|---------|------|
| 心率 | `heartRate` | bpm | 核心指标 |
| HRV (RMSSD) | `heartRateVariability` | **毫秒 (ms)** | 核心指标 |
| 血氧 | `bloodOxygen` | % | **仪表盘展示** |

> **⚠️ 重要说明：HRV数据**
> 
> SDK 的 `heartRateVariability` 就是 **RMSSD 毫秒值**，可直接用于HRV计算：
> - 1-29 ms = 低 (恢复不足/压力大)
> - 30-60 ms = 正常
> - 61-101 ms = 良好 
> - 102+ ms = 优秀 (运动员水平)
> 
> 在代码中直接使用：`let hrvRMSSD = sdkData.heartRateVariability // 单位：毫秒`
| 压力值 | `stressValue` | 0-100 | **仪表盘展示** |
| 情绪 | `mood` | 1消极/2中性/3积极 | **仪表盘展示** |
| PAI | `LowPAI/midPAI/highPAI` | 整数 | 活动量统计 |
| 步数 | `step` | 整数 | 活动量统计 |

#### 运动记录数据

| 数据类型 | SDK属性 | 数据类型 | 用途 |
|---------|---------|---------|------|
| 训练负荷 | `loadPeak` | AU | **参与计算** |
| 有氧训练效果 | `trainingEffect` | 0-5 | **参与计算** |
| 无氧训练效果 | `anaerobicSportsEffect` | 0-5 | **参与计算** |
| VO2max | `oxygenConsumption` | ml/kg/min | **生理年龄** |
| 恢复时间 | `recoveryTime` | 分钟 | **参与计算 + 生理年龄** |
| 设备体能年龄 | `fitnessAge` | 岁 | 对比展示 |

#### 日总计数据

| 数据类型 | SDK属性 | 数据类型 | 用途 |
|---------|---------|---------|------|
| 静息心率 | `restingHeartRate` | bpm | **生理年龄** |
| 睡眠数据 | 科学睡眠 | 分钟 | 核心指标 |

### 2.3 数据分类原则

⚠️ **重要**: 不同数据参与计算的方式不同

```
┌─────────────────────────────────────────────────────────────────┐
│                    SDK数据分类                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  【参与准备度计算】                【仅展示，暂不影响分数】       │
│  ├─ Hooper主观评分 (不变)         ├─ device_stress (客观压力)   │
│  │   ├─ fatigue: 0.75            ├─ device_mood (客观情绪)     │
│  │   ├─ stress: 0.70             └─ blood_oxygen (血氧)        │
│  │   ├─ soreness: 0.65                                         │
│  │   └─ sleep: 0.60                                            │
│  │                                                              │
│  ├─ HRV趋势: 1.00                                              │
│  ├─ device_recovery: 0.80 (新增)                               │
│  ├─ aerobic_training_effect: 0.55 (新增)                       │
│  ├─ anaerobic_training_effect: 0.50 (新增)                     │
│  └─ training_load (手动+SDK融合)                               │
│                                                                  │
│  【生理年龄计算】                  【周报/仪表盘】               │
│  ├─ RMSSD (SDK的heartRateVariability) ├─ weekly_pai           │
│  ├─ 静息心率                      ├─ 恢复时间趋势              │
│  ├─ CSS睡眠评分                   └─ 所有原始数据可视化        │
│  ├─ VO2max (新增)                                              │
│  ├─ 恢复时间 (新增)                                            │
│  └─ 周PAI (新增)                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 准备度状态定义

系统使用 6 种状态描述运动员/用户的恢复状态：

| 状态 | 英文名 | 分数权重 | 描述 |
|------|--------|---------|------|
| Peak | 巅峰 | 100 | 最佳状态，可进行高强度训练 |
| Well-adapted | 良好适应 | 85 | 恢复良好，可正常训练 |
| FOR | 功能性过度 | 60 | 短期疲劳累积，需注意负荷 |
| Acute Fatigue | 急性疲劳 | 50 | 明显疲劳，建议减量 |
| NFOR | 非功能性过度 | 30 | 严重疲劳，需要休息 |
| OTS | 过度训练综合症 | 10 | 危险状态，需医学干预 |

---

## 三、SDK 数据接口速查

### 3.1 UTEBluetoothRYApi SDK 核心接口

#### 3.1.1 初始化与连接

```swift
// 初始化 SDK
let bluetoothMgr = UTEBluetoothMgr.sharedInstance()
bluetoothMgr.initUTEMgr()

// 设置代理
bluetoothMgr.delegate = self

// 扫描设备
bluetoothMgr.startScanDevices()

// 连接设备
bluetoothMgr.connect(device)
```

#### 3.1.2 健康数据同步

```swift
// 获取当日运动总数据
UTEDeviceMgr.sharedInstance().getCurrentDayTotalWorkoutData { model, errorCode, dict in
    // model: UTEModelTodayStep - 包含步数、卡路里、距离等
}

// 获取采样点数据帧数 (心率/血氧/步数)
UTEDeviceMgr.sharedInstance().getSampleFrameListNew(startTime, endTime: endTime) { frameCount, errorCode, dict in
    // frameCount: 总帧数
}

// 获取采样点详细数据
UTEDeviceMgr.sharedInstance().getSampleDetailData(startTime, endTime: endTime, index: index) { model, errorCode, dict in
    // model: UTEModelMotionFrame - 包含心率、血氧、步数等时序数据
}
```

#### 3.1.3 睡眠数据

```swift
// 下载科学睡眠数据
UTEDeviceMgr.sharedInstance().getSciSleepModel(withStartTime: startTime, endTime: endTime) { debugArray, process, isSuccess, errorCode, filePath, dict in
    // dict[kSDKQuerySleepDayByDay]: 按天分组的睡眠数据
    // 包含：深睡、浅睡、REM、清醒等阶段
}
```

#### 3.1.4 压力数据

```swift
// 下载压力测量数据
UTEDeviceMgr.sharedInstance().downloadStressDataFileModel(startTime, endTime: endTime, filePath: nil) { process, isSuccess, errorCode, filePath, uuid, array in
    // array: [UTEModeStressOneData] - 压力值数组
}
```

#### 3.1.5 实时数据监听

```swift
// 监听实时健康数据帧
UTEDeviceMgr.sharedInstance().onNotifyCurrentData { currentModel in
    // currentModel: UTEModelMotionFrameItemContent - 当前分钟数据
}

// 监听运动数据通知
UTEDeviceMgr.sharedInstance().onNotifySportData { type, dict in
    // type & 0x01: 运动总计数据
    // type & 0x02: 运动实时数据
    // type & 0x04: 科学睡眠数据
    // type & 0x08: 单次运动数据
    // type & 0x10: 入睡通知数据
}
```

### 3.2 自动测量配置

```swift
// 设置心率自动测量
UTEDeviceMgr.sharedInstance().setContinueMeasureHeartRateSwitch(true) { errorCode, dict in }

// 设置心率测量间隔 (分钟)
UTEDeviceMgr.sharedInstance().setAutoHeartRateInterval(1) { errorCode in }

// 设置血氧周期测量
UTEDeviceMgr.sharedInstance().setPeriodSpo2Enable(true) { errorCode, dict in }

// 设置血氧测量间隔 (分钟)
UTEDeviceMgr.sharedInstance().setPeriodSpo2EnableInterval(5) { errorCode in }

// 设置压力自动检测
UTEDeviceMgr.sharedInstance().setAutoStress(true) { errorCode, dict in }

// 设置压力检测间隔 (分钟)
UTEDeviceMgr.sharedInstance().setAutoStressInterval(5) { errorCode in }
```

---

## 四、核心算法索引

### 4.1 个人基线计算 (PersonalBaselineCalculator)

**输入数据要求：**
- 睡眠记录: 至少 15 天
- HRV 记录: 至少 10 个样本

**输出基线：**
```swift
struct BaselineResult {
    var sleepBaselineHours: Double?     // 睡眠时长基线 (小时)
    var sleepBaselineEff: Double?       // 睡眠效率基线 (0-1)
    var restBaselineRatio: Double?      // 恢复性睡眠比例基线
    var hrvBaselineMu: Double?          // HRV均值基线 (ms)
    var hrvBaselineSd: Double?          // HRV标准差基线
    var dataQualityScore: Double        // 数据质量评分 (0-1)
}
```

**详细算法实现：**

```swift
class PersonalBaselineCalculator {
    
    // MARK: - 1. 异常值过滤 (百分位数法)
    
    /// 使用IQR方法过滤异常值
    /// - Parameter values: 原始数据数组
    /// - Returns: 过滤后的数据
    func filterOutliers(_ values: [Double]) -> [Double] {
        guard values.count >= 4 else { return values }
        
        let sorted = values.sorted()
        let q1Index = sorted.count / 4
        let q3Index = sorted.count * 3 / 4
        let q1 = sorted[q1Index]
        let q3 = sorted[q3Index]
        let iqr = q3 - q1
        
        let lowerBound = q1 - 1.5 * iqr
        let upperBound = q3 + 1.5 * iqr
        
        return values.filter { $0 >= lowerBound && $0 <= upperBound }
    }
    
    // MARK: - 2. 稳健均值计算 (20%修剪均值)
    
    /// 计算20%修剪均值 (去掉最高10%和最低10%)
    /// - Parameter values: 数据数组
    /// - Returns: 修剪均值
    func trimmedMean(_ values: [Double], trimPercent: Double = 0.2) -> Double {
        guard values.count >= 5 else {
            return values.isEmpty ? 0 : values.reduce(0, +) / Double(values.count)
        }
        
        let sorted = values.sorted()
        let trimCount = Int(Double(sorted.count) * trimPercent / 2)
        let trimmed = Array(sorted.dropFirst(trimCount).dropLast(trimCount))
        
        return trimmed.reduce(0, +) / Double(trimmed.count)
    }
    
    // MARK: - 3. 标准差计算
    
    func standardDeviation(_ values: [Double], mean: Double) -> Double {
        guard values.count > 1 else { return 0 }
        let variance = values.map { pow($0 - mean, 2) }.reduce(0, +) / Double(values.count - 1)
        return sqrt(variance)
    }
    
    // MARK: - 4. 完整基线计算
    
    func calculateBaseline(
        sleepRecords: [SleepRecord],  // 至少15天
        hrvRecords: [HRVRecord]        // 至少10个样本
    ) -> BaselineResult {
        
        var result = BaselineResult()
        
        // 睡眠时长基线
        let durations = sleepRecords.map { $0.durationHours }
        let filteredDurations = filterOutliers(durations)
        if filteredDurations.count >= 10 {
            result.sleepBaselineHours = trimmedMean(filteredDurations)
        }
        
        // 睡眠效率基线
        let efficiencies = sleepRecords.map { $0.efficiency }
        let filteredEfficiencies = filterOutliers(efficiencies)
        if filteredEfficiencies.count >= 10 {
            result.sleepBaselineEff = trimmedMean(filteredEfficiencies)
        }
        
        // 恢复性睡眠比例基线
        let restRatios = sleepRecords.map { $0.restorativeRatio }
        let filteredRestRatios = filterOutliers(restRatios)
        if filteredRestRatios.count >= 10 {
            result.restBaselineRatio = trimmedMean(filteredRestRatios)
        }
        
        // HRV基线 (均值和标准差)
        let hrvValues = hrvRecords.map { $0.rmssd }
        let filteredHRV = filterOutliers(hrvValues)
        if filteredHRV.count >= 7 {
            let mu = trimmedMean(filteredHRV)
            result.hrvBaselineMu = mu
            result.hrvBaselineSd = standardDeviation(filteredHRV, mean: mu)
        }
        
        // 数据质量评分
        let sleepQuality = min(1.0, Double(sleepRecords.count) / 30.0)
        let hrvQuality = min(1.0, Double(hrvRecords.count) / 21.0)
        result.dataQualityScore = (sleepQuality + hrvQuality) / 2.0
        
        return result
    }
}
```

### 4.2 CSS 睡眠评分 (Composite Sleep Score)

**公式：**
```
CSS = 0.40 × 时长评分 + 0.30 × 效率评分 + 0.30 × 恢复性评分
```

**详细评分算法实现：**

```swift
class CSSCalculator {
    
    // MARK: - 时长评分 (0-100)
    
    /// 睡眠时长评分
    /// - 4小时以下: 0分
    /// - 4-7小时: 线性增长 0→100
    /// - 7-9小时: 满分100
    /// - 9-11小时: 线性下降 100→50
    /// - 11小时以上: 50分
    func durationScore(hours: Double) -> Double {
        if hours < 4.0 {
            return 0.0
        } else if hours < 7.0 {
            return ((hours - 4.0) / 3.0) * 100.0
        } else if hours <= 9.0 {
            return 100.0
        } else if hours <= 11.0 {
            return 100.0 - ((hours - 9.0) / 2.0) * 50.0
        } else {
            return 50.0
        }
    }
    
    // MARK: - 效率评分 (0-100)
    
    /// 睡眠效率评分 (efficiency: 0.0-1.0)
    /// - <75%: 0分
    /// - 75%-85%: 线性增长 0→80
    /// - 85%-95%: 线性增长 80→100
    /// - ≥95%: 满分100
    func efficiencyScore(efficiency: Double) -> Double {
        let eff = efficiency > 1.0 ? efficiency / 100.0 : efficiency
        
        if eff < 0.75 {
            return 0.0
        } else if eff < 0.85 {
            return ((eff - 0.75) / 0.10) * 80.0
        } else if eff <= 0.95 {
            return 80.0 + ((eff - 0.85) / 0.10) * 20.0
        } else {
            return 100.0
        }
    }
    
    // MARK: - 恢复性睡眠评分 (0-100)
    
    /// 恢复性睡眠评分 (深睡+REM比例)
    /// - <20%: 0分
    /// - 20%-35%: 线性增长 0→100
    /// - 35%-55%: 满分100
    /// - >55%: 逐渐下降到80分 (过多REM可能不健康)
    func restorativeScore(ratio: Double) -> Double {
        if ratio < 0.20 {
            return 0.0
        } else if ratio < 0.35 {
            return ((ratio - 0.20) / 0.15) * 100.0
        } else if ratio <= 0.55 {
            return 100.0
        } else {
            // >55%时逐渐下降，最低80分
            let decrease = 100.0 - ((ratio - 0.55) / 0.10) * 20.0
            return max(80.0, decrease)
        }
    }
    
    // MARK: - 恢复性睡眠比例计算
    
    /// 计算恢复性睡眠比例
    func calculateRestorativeRatio(
        deepSleepMinutes: Double,
        remSleepMinutes: Double,
        totalSleepMinutes: Double
    ) -> Double? {
        guard totalSleepMinutes > 0 else { return nil }
        return (deepSleepMinutes + remSleepMinutes) / totalSleepMinutes
    }
    
    // MARK: - 综合CSS计算
    
    func computeCSS(
        durationHours: Double?,
        efficiency: Double?,
        restorativeRatio: Double?,
        weights: (duration: Double, efficiency: Double, restorative: Double) = (0.40, 0.30, 0.30)
    ) -> CSSResult {
        
        // 计算各分项
        let durScore = durationHours.map { durationScore(hours: $0) }
        let effScore = efficiency.map { efficiencyScore(efficiency: $0) }
        let restScore = restorativeRatio.map { restorativeScore(ratio: $0) }
        
        // 三项都需要才能计算CSS
        guard let d = durScore, let e = effScore, let r = restScore else {
            return CSSResult(
                status: .partial,
                css: nil,
                components: CSSComponents(
                    durationScore: durScore,
                    efficiencyScore: effScore,
                    restorativeScore: restScore
                )
            )
        }
        
        // 权重归一化
        let totalWeight = weights.duration + weights.efficiency + weights.restorative
        let wd = weights.duration / totalWeight
        let we = weights.efficiency / totalWeight
        let wr = weights.restorative / totalWeight
        
        let css = wd * d + we * e + wr * r
        
        return CSSResult(
            status: .ok,
            css: round(css * 10) / 10,  // 保留1位小数
            components: CSSComponents(
                durationScore: round(d * 10) / 10,
                efficiencyScore: round(e * 10) / 10,
                restorativeScore: round(r * 10) / 10
            )
        )
    }
}

struct CSSResult {
    enum Status { case ok, partial }
    let status: Status
    let css: Double?
    let components: CSSComponents
}

struct CSSComponents {
    let durationScore: Double?
    let efficiencyScore: Double?
    let restorativeScore: Double?
}
```

**示例计算：**
```
输入: 睡眠7.5小时, 效率88%, 恢复性32%
时长评分: 100 (7-9小时满分)
效率评分: 80 + (0.88-0.85)/0.10 × 20 = 86
恢复性评分: (0.32-0.20)/0.15 × 100 = 80

CSS = 0.40×100 + 0.30×86 + 0.30×80 = 40 + 25.8 + 24 = 89.8
```

### 4.3 准备度引擎 (ReadinessEngine)

**详细算法实现：**

```swift
class ReadinessEngine {
    
    // 6种状态
    let states = ["Peak", "Well-adapted", "FOR", "Acute Fatigue", "NFOR", "OTS"]
    
    // 状态权重 (用于计算分数)
    let stateWeights: [String: Double] = [
        "Peak": 100, "Well-adapted": 85, "FOR": 60,
        "Acute Fatigue": 50, "NFOR": 30, "OTS": 10
    ]
    
    var previousProbs: [String: Double]  // 昨日后验
    var todayPriorProbs: [String: Double]?
    var todayPosteriorProbs: [String: Double]?
    
    // MARK: - 1. Prior计算 (今日先验)
    
    func calculateTodayPrior(causalInputs: CausalInputs) -> [String: Double] {
        
        // 1.1 基线转移: P(Today|Yesterday) × P(Yesterday)
        var prior: [String: Double] = [:]
        for todayState in states {
            var sum = 0.0
            for yesterdayState in states {
                let transition = BASELINE_TRANSITION_CPT[yesterdayState]?[todayState] ?? 1e-6
                let yesterdayProb = previousProbs[yesterdayState] ?? 0
                sum += yesterdayProb * transition
            }
            prior[todayState] = sum
        }
        prior = normalize(prior)
        
        // 1.2 应用训练负荷CPT
        if let trainingLoad = causalInputs.trainingLoad,
           let loadCPT = TRAINING_LOAD_CPT[trainingLoad] {
            prior = combineMultiplicative(prior, loadCPT, weight: 1.0)
        }
        
        // 1.3 连续高负荷惩罚
        prior = applyTrainingStreakPenalty(prior, recentLoads: causalInputs.recentTrainingLoads)
        
        // 1.4 ACWR调整
        prior = applyACWRAdjustment(prior, causalInputs: causalInputs)
        
        todayPriorProbs = prior
        todayPosteriorProbs = prior  // 初始后验=先验
        return prior
    }
    
    // MARK: - 1.3 连续高负荷惩罚
    
    func applyTrainingStreakPenalty(_ probs: [String: Double], recentLoads: [String]) -> [String: Double] {
        var adjusted = probs
        let highSet: Set<String> = ["高", "极高"]
        
        // 4天内3天高负荷 → 向NFOR转移50%
        if recentLoads.count >= 4 {
            let last4 = Array(recentLoads.suffix(4))
            let highCount = last4.filter { highSet.contains($0) }.count
            if highCount >= 3 {
                adjusted = shiftProbability(adjusted,
                    from: ["Peak", "Well-adapted", "FOR", "Acute Fatigue"],
                    to: ["NFOR"],
                    ratio: 0.50)
            }
        }
        
        // 8天内6天高负荷 → 向NFOR转移60%
        if recentLoads.count >= 8 {
            let last8 = Array(recentLoads.suffix(8))
            let highCount = last8.filter { highSet.contains($0) }.count
            if highCount >= 6 {
                adjusted = shiftProbability(adjusted,
                    from: ["Peak", "Well-adapted", "FOR", "Acute Fatigue"],
                    to: ["NFOR"],
                    ratio: 0.60)
            }
        }
        
        return adjusted
    }
    
    // MARK: - 1.4 ACWR调整 (急慢性负荷比)
    
    func applyACWRAdjustment(_ probs: [String: Double], causalInputs: CausalInputs) -> [String: Double] {
        var adjusted = probs
        guard let recentAU = causalInputs.recentTrainingAU, recentAU.count >= 7 else {
            return adjusted
        }
        
        let last28 = Array(recentAU.suffix(28))
        let last7 = Array(recentAU.suffix(7))
        let last3 = Array(recentAU.suffix(3))
        
        let C28 = last28.reduce(0, +) / Double(last28.count)  // 慢性负荷
        let A7 = last7.reduce(0, +) / Double(last7.count)     // 急性负荷
        let A3 = last3.reduce(0, +) / Double(last3.count)     // 3日负荷
        
        guard C28 > 0 else { return adjusted }
        
        let R7_28 = A7 / C28  // ACWR
        let R3_28 = A3 / C28
        
        // 适应带判定
        let band: String
        if C28 < 1200 {
            band = "low"
        } else if C28 <= 2500 {
            band = "mid"
        } else {
            band = "high"
        }
        
        // 奖励: ACWR <= 0.9 (恢复充分)
        if R7_28 <= 0.9 {
            let base = R7_28 <= 0.8 ? 0.02 : 0.01
            let multiplier = band == "high" ? 1.2 : 1.0
            adjusted = shiftProbability(adjusted,
                from: ["NFOR", "Acute Fatigue"],
                to: ["Well-adapted", "Peak"],
                ratio: base * multiplier)
        }
        
        // 惩罚: ACWR >= 1.15 (急性负荷过高)
        if R7_28 >= 1.15 {
            var base: Double
            if R7_28 < 1.30 {
                base = 0.02
            } else if R7_28 < 1.50 {
                base = 0.04
            } else {
                base = 0.06
            }
            
            let multiplier = band == "low" ? 1.5 : (band == "mid" ? 1.0 : 0.5)
            var ratio = base * multiplier
            
            // 3日负荷过高额外惩罚
            if R3_28 >= 1.30 {
                ratio += 0.01
            }
            
            adjusted = shiftProbability(adjusted,
                from: ["Peak", "Well-adapted", "FOR"],
                to: ["Acute Fatigue", "NFOR"],
                ratio: ratio)
        }
        
        return normalize(adjusted)
    }
    
    // MARK: - 2. Posterior更新 (贝叶斯证据更新)
    
    func updateWithEvidence(_ evidence: [String: Any]) -> ReadinessResult {
        guard var posterior = todayPosteriorProbs else {
            fatalError("Must call calculateTodayPrior first")
        }
        
        // 2.1 遍历所有证据，乘以似然
        for (variable, value) in evidence {
            guard let cpt = EMISSION_CPT[variable],
                  let valueCPT = cpt[value as? String ?? ""] else {
                continue
            }
            
            let weight = EVIDENCE_WEIGHTS[variable] ?? 1.0
            
            // 贝叶斯更新: P(S|E) ∝ P(E|S)^w × P(S)
            for state in states {
                let likelihood = max(valueCPT[state] ?? 1e-6, 1e-6)
                posterior[state] = (posterior[state] ?? 0) * pow(likelihood, weight)
            }
        }
        
        // 2.2 交互CPT: 酸痛 + 压力
        if let soreness = evidence["muscle_soreness"] as? String,
           let stress = evidence["subjective_stress"] as? String,
           let interactionCPT = INTERACTION_CPT_SORENESS_STRESS[(soreness, stress)] {
            for state in states {
                let likelihood = max(interactionCPT[state] ?? 1e-6, 1e-6)
                posterior[state] = (posterior[state] ?? 0) * likelihood
            }
        }
        
        posterior = normalize(posterior)
        todayPosteriorProbs = posterior
        
        // 计算分数
        let score = calculateReadinessScore(posterior)
        let diagnosis = states.max { (posterior[$0] ?? 0) < (posterior[$1] ?? 0) } ?? "Well-adapted"
        
        return ReadinessResult(score: score, diagnosis: diagnosis, posteriorProbs: posterior)
    }
    
    // MARK: - 3. 分数计算
    
    func calculateReadinessScore(_ probs: [String: Double]) -> Int {
        var score = 0.0
        for state in states {
            score += (probs[state] ?? 0) * (stateWeights[state] ?? 0)
        }
        return Int(round(score))
    }
    
    // MARK: - 工具函数
    
    func normalize(_ probs: [String: Double]) -> [String: Double] {
        let total = probs.values.reduce(0, +)
        guard total > 0 else {
            return Dictionary(uniqueKeysWithValues: states.map { ($0, 1.0 / Double(states.count)) })
        }
        return probs.mapValues { $0 / total }
    }
    
    func combineMultiplicative(_ current: [String: Double], _ cpt: [String: Double], weight: Double) -> [String: Double] {
        var result: [String: Double] = [:]
        for state in states {
            let likelihood = max(cpt[state] ?? 1e-6, 1e-6)
            result[state] = (current[state] ?? 0) * pow(likelihood, weight)
        }
        return normalize(result)
    }
    
    func shiftProbability(_ probs: [String: Double], from: [String], to: [String], ratio: Double) -> [String: Double] {
        var adjusted = probs
        let totalFrom = from.reduce(0.0) { $0 + (adjusted[$1] ?? 0) }
        let amount = totalFrom * ratio
        
        // 从来源状态减少
        for state in from {
            if totalFrom > 0 {
                let reduction = ((adjusted[state] ?? 0) / totalFrom) * amount
                adjusted[state] = max(1e-6, (adjusted[state] ?? 0) - reduction)
            }
        }
        
        // 向目标状态增加
        let increment = amount / Double(to.count)
        for state in to {
            adjusted[state] = (adjusted[state] ?? 0) + increment
        }
        
        return normalize(adjusted)
    }
}

struct ReadinessResult {
    let score: Int          // 0-100
    let diagnosis: String   // 主导状态
    let posteriorProbs: [String: Double]
}
```

**计算示例：**
```
输入:
- 昨日后验: Well-adapted=0.6, FOR=0.3, Peak=0.1
- 今日训练负荷: "中"
- HRV趋势: "stable"
- 睡眠表现: "good"

Prior计算:
1. 基线转移后: Well-adapted=0.55, FOR=0.28, Peak=0.12, ...
2. 训练负荷CPT乘法后: 归一化

Posterior更新:
- HRV stable (w=1.0): 乘以似然
- 睡眠 good (w=0.9): 乘以似然
- 归一化

最终分数: Σ P(S) × Weight = 75分, 诊断: Well-adapted
```

### 4.4 生理年龄估算 (增强版)

> **⚠️ HRV指标说明**
> 
> SDK 的 `heartRateVariability` 是 **RMSSD 毫秒值**（不是SDNN）。
> RMSSD 和 SDNN 高度相关（r > 0.9），参考值范围类似（健康成年人30-100ms），
> 可以直接用 RMSSD 代替原公式中的 SDNN。

**原公式：**
```
PhysAge = 35 - 8×HRV_z - 5×CSS_z - 6×RHR_z
```

**增强版公式 (加入SDK数据)：**

```swift
// HRV使用SDK的heartRateVariability (RMSSD毫秒值)
let hrvRMSSD = sdkData.heartRateVariability  // 单位：毫秒

// 有VO2max时
age_adjust = -4.0 * hrv_z       // HRV (使用RMSSD)
           + -3.0 * css_z       // 睡眠
           + -4.0 * rhr_z       // 静息心率
           + -8.0 * vo2max_z    // VO2max (最高权重)
           + -3.0 * recovery_z  // 恢复能力
           + -2.0 * pai_z       // 活动量

// 无VO2max时
age_adjust = -8.0 * hrv_z       // HRV (使用RMSSD，权重提升)
           + -5.0 * css_z       // 睡眠
           + -6.0 * rhr_z       // 静息心率
           + -3.0 * recovery_z  // 恢复能力
           + -2.0 * pai_z       // 活动量

phys_age = max(18, min(80, 35 + age_adjust))
```

**z分数计算：**

| 指标 | 基准值 | 标准差 | 说明 |
|-----|--------|-------|------|
| HRV (RMSSD) | 50 ms | 20 ms | 高HRV更年轻，SDK的`heartRateVariability` |
| RHR | 60 bpm | 10 bpm | 低RHR更年轻 |
| CSS | 70 分 | 15 分 | 高CSS更年轻 |
| **VO2max** | 47-(age-20)×0.35 (男) / 41-(age-20)×0.35 (女) | 6 ml/kg/min | 高VO2更年轻 |
| **恢复时间** | 540 分钟 (9小时) | 360 分钟 | 短恢复更年轻 |
| **周PAI** | 75 | 35 | 高PAI更年轻 |

**VO2max科学参考 (ACSM Guidelines)：**

| 年龄 | 男性良好 | 女性良好 |
|-----|---------|---------|
| 20-29 | 43-52 | 38-44 |
| 30-39 | 40-48 | 34-40 |
| 40-49 | 38-44 | 32-38 |
| 50-59 | 34-40 | 28-34 |
| 60+ | 30-36 | 24-30 |

→ 详见 `SDK数据优化计划.md` 3.6节

---

## 五、关键常量表

### 5.1 Emission CPT (证据似然表) - 完整定义

```swift
/// 所有状态名
let STATES = ["Peak", "Well-adapted", "FOR", "Acute Fatigue", "NFOR", "OTS"]

// MARK: - Hooper主观评分CPT

let subjective_fatigue_cpt: [String: [String: Double]] = [
    "low":    ["Peak": 0.80, "Well-adapted": 0.70, "FOR": 0.25, "Acute Fatigue": 0.05, "NFOR": 0.05, "OTS": 1e-6],
    "medium": ["Peak": 0.15, "Well-adapted": 0.30, "FOR": 0.20, "Acute Fatigue": 0.15, "NFOR": 0.10, "OTS": 0.05],
    "high":   ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.70, "Acute Fatigue": 0.80, "NFOR": 0.80, "OTS": 0.90]
]

let muscle_soreness_cpt: [String: [String: Double]] = [
    "low":    ["Peak": 0.80, "Well-adapted": 0.75, "FOR": 0.35, "Acute Fatigue": 0.10, "NFOR": 0.10, "OTS": 0.20],
    "medium": ["Peak": 0.10, "Well-adapted": 0.25, "FOR": 0.50, "Acute Fatigue": 0.30, "NFOR": 0.40, "OTS": 0.50],
    "high":   ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.35, "Acute Fatigue": 0.60, "NFOR": 0.50, "OTS": 0.30]
]

let subjective_stress_cpt: [String: [String: Double]] = [
    "low":    ["Peak": 0.80, "Well-adapted": 0.70, "FOR": 0.40, "Acute Fatigue": 0.20, "NFOR": 0.10, "OTS": 1e-6],
    "medium": ["Peak": 0.10, "Well-adapted": 0.30, "FOR": 0.50, "Acute Fatigue": 0.50, "NFOR": 0.30, "OTS": 0.20],
    "high":   ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.10, "Acute Fatigue": 0.30, "NFOR": 0.60, "OTS": 0.80]
]

let subjective_sleep_cpt: [String: [String: Double]] = [
    "good":   ["Peak": 0.80, "Well-adapted": 0.75, "FOR": 0.30, "Acute Fatigue": 0.40, "NFOR": 0.15, "OTS": 0.10],
    "medium": ["Peak": 0.15, "Well-adapted": 0.25, "FOR": 0.40, "Acute Fatigue": 0.40, "NFOR": 0.35, "OTS": 0.20],
    "poor":   ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.15, "Acute Fatigue": 0.20, "NFOR": 0.65, "OTS": 0.70]
]

// MARK: - 客观睡眠CPT

let sleep_performance_cpt: [String: [String: Double]] = [
    "good":   ["Peak": 0.80, "Well-adapted": 0.70, "FOR": 0.25, "Acute Fatigue": 0.35, "NFOR": 0.20, "OTS": 0.15],
    "medium": ["Peak": 0.20, "Well-adapted": 0.30, "FOR": 0.50, "Acute Fatigue": 0.50, "NFOR": 0.40, "OTS": 0.35],
    "poor":   ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.25, "Acute Fatigue": 0.15, "NFOR": 0.40, "OTS": 0.50]
]

let restorative_sleep_cpt: [String: [String: Double]] = [
    "high":   ["Peak": 0.85, "Well-adapted": 0.75, "FOR": 0.30, "Acute Fatigue": 0.20, "NFOR": 0.05, "OTS": 1e-6],
    "medium": ["Peak": 0.40, "Well-adapted": 0.50, "FOR": 0.40, "Acute Fatigue": 0.35, "NFOR": 0.25, "OTS": 0.15],
    "low":    ["Peak": 1e-6, "Well-adapted": 0.10, "FOR": 0.20, "Acute Fatigue": 0.30, "NFOR": 0.70, "OTS": 0.80]
]

// MARK: - HRV趋势CPT

let hrv_trend_cpt: [String: [String: Double]] = [
    "rising":              ["Peak": 0.85, "Well-adapted": 0.20, "FOR": 0.10, "Acute Fatigue": 0.10, "NFOR": 0.05, "OTS": 0.01],
    "stable":              ["Peak": 0.40, "Well-adapted": 0.30, "FOR": 0.20, "Acute Fatigue": 0.20, "NFOR": 0.10, "OTS": 0.05],
    "slight_decline":      ["Peak": 0.05, "Well-adapted": 0.10, "FOR": 0.30, "Acute Fatigue": 0.30, "NFOR": 0.15, "OTS": 0.09],
    "significant_decline": ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.40, "Acute Fatigue": 0.40, "NFOR": 0.70, "OTS": 0.80]
]

// MARK: - 设备恢复状态CPT (新增)

let device_recovery_cpt: [String: [String: Double]] = [
    "good":   ["Peak": 0.70, "Well-adapted": 0.65, "FOR": 0.25, "Acute Fatigue": 0.15, "NFOR": 0.05, "OTS": 1e-6],  // <6小时
    "medium": ["Peak": 0.25, "Well-adapted": 0.40, "FOR": 0.40, "Acute Fatigue": 0.30, "NFOR": 0.15, "OTS": 0.05],  // 6-12小时
    "poor":   ["Peak": 1e-6, "Well-adapted": 0.05, "FOR": 0.20, "Acute Fatigue": 0.40, "NFOR": 0.60, "OTS": 0.70]   // >12小时
]

// MARK: - 其他CPT

let nutrition_cpt: [String: [String: Double]] = [
    "adequate":            ["Peak": 0.50, "Well-adapted": 0.60, "FOR": 0.50, "Acute Fatigue": 0.70, "NFOR": 0.40, "OTS": 0.30],
    "inadequate_mild":     ["Peak": 0.40, "Well-adapted": 0.40, "FOR": 0.45, "Acute Fatigue": 0.40, "NFOR": 0.50, "OTS": 0.45],
    "inadequate_moderate": ["Peak": 0.30, "Well-adapted": 0.35, "FOR": 0.42, "Acute Fatigue": 0.35, "NFOR": 0.55, "OTS": 0.60],
    "inadequate_severe":   ["Peak": 0.10, "Well-adapted": 0.15, "FOR": 0.40, "Acute Fatigue": 0.30, "NFOR": 0.60, "OTS": 0.70]
]

let gi_symptoms_cpt: [String: [String: Double]] = [
    "none":   ["Peak": 0.90, "Well-adapted": 0.85, "FOR": 0.80, "Acute Fatigue": 0.70, "NFOR": 0.50, "OTS": 0.40],
    "mild":   ["Peak": 0.05, "Well-adapted": 0.10, "FOR": 0.15, "Acute Fatigue": 0.25, "NFOR": 0.40, "OTS": 0.40],
    "severe": ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.05, "Acute Fatigue": 0.05, "NFOR": 0.10, "OTS": 0.20]
]

// MARK: - 布尔证据CPT

let is_sick_cpt: [String: Double] = ["Peak": 1e-9, "Well-adapted": 1e-6, "FOR": 0.05, "Acute Fatigue": 0.40, "NFOR": 0.80, "OTS": 0.90]
let is_injured_cpt: [String: Double] = ["Peak": 1e-9, "Well-adapted": 1e-6, "FOR": 0.10, "Acute Fatigue": 0.50, "NFOR": 0.70, "OTS": 0.60]

// MARK: - 基线转移CPT (Prior计算用)

let BASELINE_TRANSITION_CPT: [String: [String: Double]] = [
    "Peak":         ["Peak": 0.80, "Well-adapted": 0.10, "FOR": 0.05, "Acute Fatigue": 1e-6, "NFOR": 1e-6, "OTS": 1e-6],
    "Well-adapted": ["Peak": 0.60, "Well-adapted": 0.35, "FOR": 0.05, "Acute Fatigue": 1e-6, "NFOR": 1e-6, "OTS": 1e-6],
    "FOR":          ["Peak": 0.05, "Well-adapted": 0.40, "FOR": 0.30, "Acute Fatigue": 0.10, "NFOR": 0.10, "OTS": 0.05],
    "Acute Fatigue":["Peak": 0.20, "Well-adapted": 0.70, "FOR": 0.10, "Acute Fatigue": 1e-6, "NFOR": 1e-6, "OTS": 1e-6],
    "NFOR":         ["Peak": 0.01, "Well-adapted": 0.05, "FOR": 0.10, "Acute Fatigue": 0.05, "NFOR": 0.70, "OTS": 0.09],
    "OTS":          ["Peak": 0.01, "Well-adapted": 0.04, "FOR": 0.10, "Acute Fatigue": 0.05, "NFOR": 0.30, "OTS": 0.50]
]

// MARK: - 训练负荷CPT (Prior计算用)

let TRAINING_LOAD_CPT: [String: [String: Double]] = [
    "极高": ["Peak": 0.01, "Well-adapted": 0.05, "FOR": 0.40, "Acute Fatigue": 0.50, "NFOR": 0.04, "OTS": 0.0],
    "高":   ["Peak": 0.05, "Well-adapted": 0.15, "FOR": 0.50, "Acute Fatigue": 0.25, "NFOR": 0.05, "OTS": 0.0],
    "中":   ["Peak": 0.10, "Well-adapted": 0.60, "FOR": 0.20, "Acute Fatigue": 0.08, "NFOR": 0.02, "OTS": 0.0],
    "低":   ["Peak": 0.20, "Well-adapted": 0.70, "FOR": 0.05, "Acute Fatigue": 0.04, "NFOR": 0.01, "OTS": 0.0],
    "无":   ["Peak": 0.30, "Well-adapted": 0.60, "FOR": 0.05, "Acute Fatigue": 0.03, "NFOR": 0.02, "OTS": 0.0]
]

// MARK: - 交互CPT (酸痛×压力)

let INTERACTION_CPT_SORENESS_STRESS: [[String]: [String: Double]] = [
    ["low", "low"]:       ["Peak": 0.70, "Well-adapted": 0.60, "FOR": 0.20, "Acute Fatigue": 0.10, "NFOR": 0.05, "OTS": 1e-6],
    ["low", "medium"]:    ["Peak": 0.50, "Well-adapted": 0.45, "FOR": 0.30, "Acute Fatigue": 0.15, "NFOR": 0.10, "OTS": 0.05],
    ["low", "high"]:      ["Peak": 1e-6, "Well-adapted": 0.05, "FOR": 0.15, "Acute Fatigue": 0.20, "NFOR": 0.60, "OTS": 0.50],
    ["medium", "low"]:    ["Peak": 0.40, "Well-adapted": 0.50, "FOR": 0.35, "Acute Fatigue": 0.20, "NFOR": 0.10, "OTS": 0.05],
    ["medium", "medium"]: ["Peak": 0.25, "Well-adapted": 0.35, "FOR": 0.40, "Acute Fatigue": 0.30, "NFOR": 0.20, "OTS": 0.10],
    ["medium", "high"]:   ["Peak": 0.10, "Well-adapted": 0.15, "FOR": 0.25, "Acute Fatigue": 0.25, "NFOR": 0.45, "OTS": 0.30],
    ["high", "low"]:      ["Peak": 1e-6, "Well-adapted": 0.10, "FOR": 0.60, "Acute Fatigue": 0.50, "NFOR": 0.15, "OTS": 0.10],
    ["high", "medium"]:   ["Peak": 1e-6, "Well-adapted": 0.05, "FOR": 0.50, "Acute Fatigue": 0.60, "NFOR": 0.25, "OTS": 0.20],
    ["high", "high"]:     ["Peak": 1e-6, "Well-adapted": 1e-6, "FOR": 0.30, "Acute Fatigue": 0.40, "NFOR": 0.50, "OTS": 0.60]
]
```

### 5.2 训练负荷映射与融合

```swift
let trainingLoadAU = [
    "无":   0,
    "低":   200,
    "中":   350,
    "高":   500,
    "极高": 700
]
```

**训练负荷智能融合逻辑：**

```swift
/// 训练负荷智能融合
/// - 只有手动输入 → 100%使用手动
/// - 只有SDK数据 → 100%使用SDK
/// - 两个都有 → 50%+50%平分
func getTrainingLoad(manualInput: String?, sdkLoadPeak: Int?) -> String {
    var manualAU: Int? = nil
    var sdkAU: Int? = nil
    
    if let manual = manualInput, let au = trainingLoadAU[manual] {
        manualAU = au
    }
    
    if let sdk = sdkLoadPeak, sdk > 0 {
        sdkAU = sdk
    }
    
    let finalAU: Int
    if let m = manualAU, let s = sdkAU {
        finalAU = (m + s) / 2  // 两个都有 → 平分
    } else if let m = manualAU {
        finalAU = m            // 只有手动
    } else if let s = sdkAU {
        finalAU = s            // 只有SDK
    } else {
        return "无"
    }
    
    // AU → 等级映射
    switch finalAU {
    case ..<100: return "无"
    case 100..<250: return "低"
    case 250..<400: return "中"
    case 400..<600: return "高"
    default: return "极高"
    }
}
```

### 5.2.1 新增 CPT: device_recovery

```swift
// 设备恢复状态 (基于recoveryTime)
let deviceRecoveryCPT = [
    "good": [   // recoveryTime < 360分钟 (6小时)
        Peak: 0.70, WellAdapted: 0.65, FOR: 0.25, 
        AcuteFatigue: 0.15, NFOR: 0.05, OTS: 1e-6
    ],
    "medium": [ // 360-720分钟 (6-12小时)
        Peak: 0.25, WellAdapted: 0.40, FOR: 0.40, 
        AcuteFatigue: 0.30, NFOR: 0.15, OTS: 0.05
    ],
    "poor": [   // > 720分钟 (12小时)
        Peak: 1e-6, WellAdapted: 0.05, FOR: 0.20, 
        AcuteFatigue: 0.40, NFOR: 0.60, OTS: 0.70
    ]
]
```

### 5.2.2 新增 CPT: aerobic/anaerobic_training_effect

```swift
// 有氧训练效果 (昨日训练 → 今日状态)
let aerobicTrainingEffectCPT = [
    "none": [       // 0-0.9 无效果
        Peak: 0.40, WellAdapted: 0.50, FOR: 0.45, 
        AcuteFatigue: 0.40, NFOR: 0.35, OTS: 0.30
    ],
    "minor": [      // 1.0-1.9 轻微
        Peak: 0.55, WellAdapted: 0.60, FOR: 0.50, 
        AcuteFatigue: 0.40, NFOR: 0.30, OTS: 0.25
    ],
    "maintaining": [// 2.0-2.9 维持
        Peak: 0.65, WellAdapted: 0.70, FOR: 0.55, 
        AcuteFatigue: 0.45, NFOR: 0.30, OTS: 0.20
    ],
    "improving": [  // 3.0-3.9 提高 (需恢复)
        Peak: 0.50, WellAdapted: 0.55, FOR: 0.60, 
        AcuteFatigue: 0.55, NFOR: 0.40, OTS: 0.30
    ],
    "highly_improving": [ // 4.0-5.0 大幅提高 (需更多恢复)
        Peak: 0.30, WellAdapted: 0.40, FOR: 0.65, 
        AcuteFatigue: 0.60, NFOR: 0.50, OTS: 0.40
    ]
]

// 无氧训练效果 (对肌肉损伤更大)
let anaerobicTrainingEffectCPT = [
    "none": [     // 0-0.9
        Peak: 0.45, WellAdapted: 0.50, FOR: 0.45, 
        AcuteFatigue: 0.40, NFOR: 0.30, OTS: 0.25
    ],
    "minor": [    // 1.0-1.9
        Peak: 0.50, WellAdapted: 0.55, FOR: 0.50, 
        AcuteFatigue: 0.45, NFOR: 0.35, OTS: 0.30
    ],
    "moderate": [ // 2.0-2.9
        Peak: 0.40, WellAdapted: 0.50, FOR: 0.55, 
        AcuteFatigue: 0.55, NFOR: 0.45, OTS: 0.35
    ],
    "high": [     // 3.0-3.9
        Peak: 0.25, WellAdapted: 0.35, FOR: 0.60, 
        AcuteFatigue: 0.65, NFOR: 0.55, OTS: 0.50
    ],
    "extreme": [  // 4.0-5.0
        Peak: 0.10, WellAdapted: 0.20, FOR: 0.55, 
        AcuteFatigue: 0.70, NFOR: 0.70, OTS: 0.65
    ]
]
```

### 5.3 证据权重

⚠️ **重要**: Hooper主观评分权重保持不变

```swift
let evidenceWeights = [
    // ========== 核心客观数据 ==========
    "hrv_trend":           1.00,   // HRV趋势 - 核心指标
    "device_recovery":     0.80,   // 设备恢复状态 (新增)
    
    // ========== 睡眠相关 ==========
    "restorative_sleep":   0.95,   // 恢复性睡眠
    "sleep_performance":   0.90,   // 睡眠表现
    
    // ========== Hooper主观评分 (不变!) ==========
    "subjective_fatigue":  0.75,   // 主观疲劳 ← 保持
    "subjective_stress":   0.70,   // 主观压力 ← 保持
    "muscle_soreness":     0.65,   // 肌肉酸痛 ← 保持
    "subjective_sleep":    0.60,   // 主观睡眠 ← 保持
    
    // ========== 训练相关 (新增) ==========
    "aerobic_training_effect":   0.55,  // 有氧训练效果 (新增)
    "anaerobic_training_effect": 0.50,  // 无氧训练效果 (新增)
    
    // ========== 其他 ==========
    "menstrual_cycle":     0.80,
    "is_sick":             1.00,
    "is_injured":          0.80,
    "nutrition":           0.60,
    "gi_symptoms":         0.50,
]
```

### 5.4 暂时只展示、不参与计算的数据

| 数据 | SDK属性 | 展示方式 | 说明 |
|-----|--------|---------|------|
| device_stress | `stressValue` | 趋势图 | 供用户对比主观压力评分 |
| device_mood | `mood` | 趋势图 | 供用户对比主观评分 |
| blood_oxygen | `bloodOxygen` | 趋势图 | 健康监测展示 |

**后续如需加入计算，再添加对应CPT和权重。**

→ 完整 CPT 表详见 `06_常量与CPT表.md`

---

## 六、数据流与处理流程

### 6.1 每日数据处理流程

```
06:00-08:00 晨起时段
    │
    ├─▶ 同步昨夜睡眠数据
    │     └─▶ 计算睡眠表现 (sleep_performance)
    │     └─▶ 计算恢复性睡眠 (restorative_sleep)
    │     └─▶ 如有 iOS 26: 获取 apple_sleep_score
    │
    ├─▶ 获取晨起 HRV
    │     └─▶ 计算 HRV 趋势 (与基线比较)
    │
    └─▶ 执行 Prior 计算
          └─▶ 基线转移
          └─▶ 应用昨日因果因素
          └─▶ 生成今日先验概率

全天实时
    │
    ├─▶ 每分钟采集心率数据
    ├─▶ 每5分钟采集血氧数据
    ├─▶ 每5分钟采集压力数据
    │
    └─▶ 用户输入主观评分时
          └─▶ Hooper量表 (1-7分)
          └─▶ 执行 Posterior 更新
          └─▶ 更新准备度分数

21:00-23:00 日终
    │
    ├─▶ 汇总今日数据
    ├─▶ 保存最终后验概率 (作为明日先验)
    └─▶ 更新个人基线 (增量/周期性)
```

### 6.2 数据映射规则 (详细算法)

#### 6.2.1 HRV 趋势判定

```swift
class HRVTrendMapper {
    
    /// HRV趋势判定 (优先z分数，退化到相对变化)
    func mapHRVTrend(
        todayRMSSD: Double?,
        baselineMu: Double?,
        baselineSd: Double?,
        rmssd3DayAvg: Double?,
        rmssd7DayAvg: Double?
    ) -> String? {
        
        // 方法1: Z分数法 (有基线时)
        if let today = todayRMSSD,
           let mu = baselineMu,
           let sd = baselineSd,
           sd > 0 {
            let z = (today - mu) / sd
            
            if z >= 0.5 {
                return "rising"           // HRV上升，恢复良好
            } else if z <= -1.5 {
                return "significant_decline"  // HRV显著下降，需警惕
            } else if z <= -0.5 {
                return "slight_decline"   // HRV轻微下降
            } else {
                return "stable"           // HRV稳定
            }
        }
        
        // 方法2: 相对变化法 (无基线退化)
        if let avg3 = rmssd3DayAvg,
           let avg7 = rmssd7DayAvg,
           avg7 > 0 {
            let delta = (avg3 - avg7) / avg7  // 相对变化率
            
            if delta >= 0.03 {
                return "rising"           // 3日>7日 3%以上
            } else if delta <= -0.08 {
                return "significant_decline"  // 3日<7日 8%以上
            } else if delta <= -0.03 {
                return "slight_decline"   // 3日<7日 3%-8%
            } else {
                return "stable"           // 变化<3%
            }
        }
        
        return nil
    }
}
```

**HRV趋势阈值说明：**
| 状态 | z分数 | 相对变化 | 含义 |
|-----|-------|---------|------|
| rising | z ≥ 0.5 | δ ≥ +3% | 副交感神经活跃，恢复良好 |
| stable | -0.5 < z < 0.5 | -3% < δ < +3% | 正常波动范围 |
| slight_decline | -1.5 < z ≤ -0.5 | -8% < δ ≤ -3% | 轻微疲劳信号 |
| significant_decline | z ≤ -1.5 | δ ≤ -8% | 明显疲劳/压力信号 |

#### 6.2.2 睡眠表现判定

```swift
class SleepPerformanceMapper {
    
    // 固定阈值
    let EFFICIENCY_GOOD = 0.85
    let EFFICIENCY_MED = 0.75
    
    /// 睡眠表现判定 (支持个性化基线)
    func mapSleepPerformance(
        durationHours: Double,
        efficiency: Double,  // 0-1 或 0-100
        baselineHours: Double? = nil,
        baselineEff: Double? = nil
    ) -> String {
        
        // 效率标准化
        let eff = efficiency > 1.0 ? efficiency / 100.0 : efficiency
        
        // 计算阈值 (有基线时个性化，无基线时固定)
        let goodDurThreshold: Double
        let goodEffThreshold: Double
        let medDurThreshold: Double
        let medEffThreshold: Double
        
        if let muDur = baselineHours {
            // 个性化: good = 基线+1小时(最低7,最高9)
            goodDurThreshold = min(9.0, max(7.0, muDur + 1.0))
            medDurThreshold = min(8.0, max(6.0, muDur - 0.5))
        } else {
            goodDurThreshold = 7.0
            medDurThreshold = 6.0
        }
        
        if let muEff = baselineEff {
            // 个性化: good = 基线-5%(最低85%)
            goodEffThreshold = max(EFFICIENCY_GOOD, muEff - 0.05)
            medEffThreshold = max(EFFICIENCY_MED, muEff - 0.10)
        } else {
            goodEffThreshold = EFFICIENCY_GOOD
            medEffThreshold = EFFICIENCY_MED
        }
        
        // 判定
        if durationHours >= goodDurThreshold && eff >= goodEffThreshold {
            return "good"
        } else if durationHours >= medDurThreshold && eff >= medEffThreshold {
            return "medium"
        } else {
            return "poor"
        }
    }
}
```

**睡眠表现阈值：**
| 等级 | 时长 (无基线) | 时长 (有基线) | 效率 |
|-----|-------------|--------------|------|
| good | ≥7小时 | ≥基线+1小时 | ≥85% |
| medium | ≥6小时 | ≥基线-0.5小时 | ≥75% |
| poor | <6小时 | <基线-0.5小时 | <75% |

#### 6.2.3 恢复性睡眠判定

```swift
class RestorativeSleepMapper {
    
    let RESTORATIVE_HIGH = 0.35  // 深睡+REM ≥35%
    let RESTORATIVE_MED = 0.25   // 深睡+REM ≥25%
    
    /// 恢复性睡眠判定
    func mapRestorativeSleep(
        restorativeRatio: Double?,  // 深睡+REM比例
        deepSleepRatio: Double? = nil,
        remSleepRatio: Double? = nil,
        baselineRatio: Double? = nil
    ) -> String? {
        
        // 计算恢复性比例
        var ratio: Double?
        if let r = restorativeRatio {
            ratio = r
        } else if let deep = deepSleepRatio, let rem = remSleepRatio {
            ratio = deep + rem
        }
        
        guard let r = ratio else { return nil }
        
        // 阈值 (可个性化)
        let highThreshold: Double
        let medThreshold: Double
        
        if let mu = baselineRatio {
            highThreshold = min(0.55, max(RESTORATIVE_HIGH, mu + 0.10))
            medThreshold = max(RESTORATIVE_MED, mu - 0.05)
        } else {
            highThreshold = RESTORATIVE_HIGH
            medThreshold = RESTORATIVE_MED
        }
        
        if r >= highThreshold {
            return "high"
        } else if r >= medThreshold {
            return "medium"
        } else {
            return "low"
        }
    }
}
```

#### 6.2.4 Hooper主观评分映射

```swift
class HooperMapper {
    
    /// Hooper量表映射 (1-7分 → low/medium/high)
    func mapHooperScore(_ score: Int) -> String {
        switch score {
        case 1...2: return "low"     // 1-2分: 状态好
        case 3...4: return "medium"  // 3-4分: 状态一般
        case 5...7: return "high"    // 5-7分: 状态差
        default: return "medium"
        }
    }
    
    /// Hooper到状态似然的连续映射 (用于贝叶斯更新)
    func hooperToStateLikelihood(variable: String, score: Int) -> [String: Double] {
        // score: 1-7, 越高越疲劳/压力/酸痛
        let t = Double(score - 1) / 6.0  // 归一化到0-1
        
        switch variable {
        case "subjective_fatigue":
            return [
                "Peak": 0.90 - 0.85 * t,
                "Well-adapted": 0.80 - 0.65 * t,
                "FOR": 0.20 + 0.50 * t,
                "Acute Fatigue": 0.05 + 0.75 * t,
                "NFOR": 0.02 + 0.78 * t,
                "OTS": 0.01 + 0.89 * t
            ]
        case "muscle_soreness":
            return [
                "Peak": 0.85 - 0.80 * t,
                "Well-adapted": 0.75 - 0.60 * t,
                "FOR": 0.25 + 0.45 * t,
                "Acute Fatigue": 0.10 + 0.70 * t,
                "NFOR": 0.05 + 0.75 * t,
                "OTS": 0.02 + 0.88 * t
            ]
        case "subjective_stress":
            return [
                "Peak": 0.80 - 0.75 * t,
                "Well-adapted": 0.70 - 0.55 * t,
                "FOR": 0.30 + 0.40 * t,
                "Acute Fatigue": 0.15 + 0.65 * t,
                "NFOR": 0.08 + 0.72 * t,
                "OTS": 0.05 + 0.85 * t
            ]
        case "subjective_sleep":
            return [
                "Peak": 0.85 - 0.80 * t,
                "Well-adapted": 0.70 - 0.55 * t,
                "FOR": 0.25 + 0.45 * t,
                "Acute Fatigue": 0.10 + 0.70 * t,
                "NFOR": 0.05 + 0.75 * t,
                "OTS": 0.02 + 0.88 * t
            ]
        default:
            return [:]
        }
    }
}
```

**Hooper量表说明：**
| 分数 | 含义 | 映射状态 |
|-----|------|---------|
| 1-2 | 非常好/好 | low (利好Peak/Well-adapted) |
| 3-4 | 一般 | medium (中性) |
| 5-7 | 差/很差/极差 | high (利好疲劳状态) |

#### ⚠️ Apple Sleep Score (已移除)

```swift
// 注意: 已决定不使用苹果睡眠评分
// 只使用原始睡眠数据计算CSS (Composite Sleep Score)
// Apple Sleep Score 相关代码已从 constants.py 和 mapping.py 中移除
```

#### device_recovery 映射 (新增)

```swift
/// 将SDK恢复时间映射为状态
func mapDeviceRecoveryState(_ recoveryTimeMinutes: Int) -> String {
    switch recoveryTimeMinutes {
    case ..<360: return "good"     // < 6小时
    case 360..<720: return "medium" // 6-12小时
    default: return "poor"          // > 12小时
    }
}
```

#### 训练效果映射 (新增)

```swift
/// 将SDK训练效果值映射为状态
func mapTrainingEffect(_ effect: Double) -> String {
    switch effect {
    case ..<1.0: return "none"           // 无效果
    case 1.0..<2.0: return "minor"       // 轻微
    case 2.0..<3.0: return "maintaining" // 维持
    case 3.0..<4.0: return "improving"   // 提高
    default: return "highly_improving"   // 大幅提高
    }
}

/// 无氧训练效果映射
func mapAnaerobicTrainingEffect(_ effect: Double) -> String {
    switch effect {
    case ..<1.0: return "none"
    case 1.0..<2.0: return "minor"
    case 2.0..<3.0: return "moderate"
    case 3.0..<4.0: return "high"
    default: return "extreme"
    }
}
```

#### 周PAI计算 (新增)

```swift
/// 计算周PAI总分
/// - Parameter dailyPAIData: 过去7天的PAI数据
/// - Returns: 周PAI信息
func calculateWeeklyPAI(dailyPAIData: [[String: Int]]) -> WeeklyPAIResult {
    var totalPAI: Double = 0
    
    for day in dailyPAIData {
        // PAI算法: 高强度贡献更多
        let daily = Double(day["LowPAI", default: 0]) * 1.0 +
                    Double(day["midPAI", default: 0]) * 2.0 +
                    Double(day["highPAI", default: 0]) * 3.0
        totalPAI += daily
    }
    
    // 状态判断 (基于HUNT研究)
    let status: String
    let message: String
    
    switch totalPAI {
    case 100...: 
        status = "optimal"
        message = "本周活动量达标，心血管健康受益"
    case 75..<100:
        status = "good"
        message = "本周活动量良好，继续保持"
    case 50..<75:
        status = "moderate"
        message = "本周活动量中等，建议增加高强度活动"
    default:
        status = "low"
        message = "本周活动量不足，建议增加运动"
    }
    
    return WeeklyPAIResult(
        weeklyPAI: totalPAI,
        target: 100,
        percentage: min(100, Int(totalPAI)),
        status: status,
        message: message
    )
}

struct WeeklyPAIResult {
    let weeklyPAI: Double
    let target: Int
    let percentage: Int
    let status: String
    let message: String
}
```

---

## 七、周报系统 (联网模块)

### 7.1 周报数据打包

周报是唯一需要联网的功能，需要将一周数据打包上传到服务端进行 LLM 分析。

**打包数据结构：**
```swift
struct WeeklyReportPayload: Codable {
    let userId: String
    let weekStartDate: String  // "YYYY-MM-DD"
    let weekEndDate: String
    
    // 每日准备度数据
    let dailyReadiness: [DailyReadinessRecord]
    
    // 睡眠汇总
    let sleepSummary: WeeklySleepSummary
    
    // HRV汇总
    let hrvSummary: WeeklyHRVSummary
    
    // 训练负荷汇总
    let trainingLoadSummary: WeeklyTrainingSummary
    
    // 用户基线
    let userBaseline: BaselineResult
    
    // 🆕 因果分析结果 (来自CausalEngine)
    let causalAnalysis: CausalAnalysisResult?
}
```

### 7.2 周报与因果引擎集成

> **重要**: 周报提交前，应调用 `CausalEngine` 获取因果分析结果，一并上传给服务端。

```swift
class WeeklyReportService {
    
    private let causalEngine: CausalEngine
    private let dataStore: LocalDataStore
    
    /// 准备周报数据 (包含因果分析)
    func prepareWeeklyPayload(weekStart: Date, weekEnd: Date) -> WeeklyReportPayload {
        
        // 1. 获取本周数据
        let weekData = dataStore.getDailyData(from: weekStart, to: weekEnd)
        
        // 2. 🆕 调用统一因果引擎分析
        let causalResult = causalEngine.analyze(data: weekData, period: .weekly)
        
        // 3. 打包上传
        return WeeklyReportPayload(
            userId: currentUserId,
            weekStartDate: weekStart.formatted(),
            weekEndDate: weekEnd.formatted(),
            dailyReadiness: weekData.map { $0.toReadinessRecord() },
            sleepSummary: buildSleepSummary(weekData),
            hrvSummary: buildHRVSummary(weekData),
            trainingLoadSummary: buildTrainingSummary(weekData),
            userBaseline: baselineManager.getCurrentBaseline(),
            causalAnalysis: causalResult  // 🆕 因果分析结果
        )
    }
}
```

**服务端处理流程：**
```
┌─────────────────────────────────────────────────────────────────┐
│                     周报生成流程                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  iOS端:                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ 本地数据    │───▶│ CausalEngine│───▶│ 打包上传    │         │
│  │ 7天DailyData│    │  .weekly    │    │ Payload     │         │
│  └─────────────┘    └─────────────┘    └──────┬──────┘         │
│                                               │                 │
│  ───────────────────────────────────────────────────────────── │
│                                               │ Network         │
│  服务端:                                      ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ 接收Payload │───▶│ LLM分析     │───▶│ 生成报告    │         │
│  │ + causal    │    │ 结合因果    │    │ Markdown    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 周报 API 端点

```
POST /api/v1/weekly-report/generate
Content-Type: application/json

Request Body: WeeklyReportPayload (JSON)

Response:
{
    "status": "ok",
    "report": {
        "summary": "...",
        "insights": [...],
        "recommendations": [...],
        "trends": {...}
    }
}
```

### 7.3 个性化CPT云端同步 API

```
GET /api/v1/user/{userId}/personalized-cpt
Authorization: Bearer {token}

Response:
{
    "status": "ok",
    "version": "2025-12-10",
    "cpt": {
        "subjective_fatigue": {...},
        "hrv_trend": {...},
        // ... 其他个性化CPT
    },
    "weights": {
        "hrv_trend": 1.0,
        "subjective_fatigue": 0.75,
        // ... 其他个性化权重
    },
    "updated_at": "2025-12-10T00:00:00Z"
}
```

**同步策略:**
- 启动时检查版本号
- 每周自动拉取一次
- 用户可手动刷新
- 本地缓存，离线可用

```swift
class CPTSyncService {
    
    func syncPersonalizedCPT(userId: String) async throws -> PersonalizedCPT {
        let url = URL(string: "https://api.motivue.com/api/v1/user/\(userId)/personalized-cpt")!
        let (data, _) = try await URLSession.shared.data(from: url)
        
        let response = try JSONDecoder().decode(CPTSyncResponse.self, from: data)
        
        // 保存到本地
        UserDefaults.standard.set(response.version, forKey: "cptVersion")
        try saveToLocal(response.cpt)
        
        return response.cpt
    }
    
    func shouldSync() -> Bool {
        let lastSync = UserDefaults.standard.object(forKey: "lastCPTSync") as? Date ?? .distantPast
        return Date().timeIntervalSince(lastSync) > 7 * 24 * 60 * 60  // 7天
    }
}
```

---

## 八、完整数据模型定义

### 8.1 核心数据模型 (Swift)

```swift
import Foundation

// MARK: - 睡眠记录
struct SleepRecord: Codable, Identifiable {
    let id: UUID
    let date: Date
    let bedTime: Date                    // 入睡时间
    let wakeTime: Date                   // 醒来时间
    let totalSleepMinutes: Int           // 总睡眠时长
    let inBedMinutes: Int                // 在床时长
    let deepSleepMinutes: Int            // 深睡时长
    let lightSleepMinutes: Int           // 浅睡时长
    let remSleepMinutes: Int             // REM时长
    let awakeMinutes: Int                // 清醒时长
    
    // 计算属性
    var durationHours: Double {
        Double(totalSleepMinutes) / 60.0
    }
    
    var efficiency: Double {
        guard inBedMinutes > 0 else { return 0 }
        return Double(totalSleepMinutes) / Double(inBedMinutes)
    }
    
    var restorativeRatio: Double {
        guard totalSleepMinutes > 0 else { return 0 }
        return Double(deepSleepMinutes + remSleepMinutes) / Double(totalSleepMinutes)
    }
    
    var deepSleepRatio: Double {
        guard totalSleepMinutes > 0 else { return 0 }
        return Double(deepSleepMinutes) / Double(totalSleepMinutes)
    }
    
    var remSleepRatio: Double {
        guard totalSleepMinutes > 0 else { return 0 }
        return Double(remSleepMinutes) / Double(totalSleepMinutes)
    }
}

// MARK: - HRV记录
struct HRVRecord: Codable, Identifiable {
    let id: UUID
    let timestamp: Date
    let rmssd: Double                    // RMSSD值 (ms)
    let sdnn: Double?                    // SDNN值 (ms)，可选
    let source: DataSource               // 数据来源
    
    enum DataSource: String, Codable {
        case sdk = "SDK"
        case healthKit = "HealthKit"
    }
}

// MARK: - 心率记录
struct HeartRateRecord: Codable, Identifiable {
    let id: UUID
    let timestamp: Date
    let bpm: Int                         // 心率值
    let isResting: Bool                  // 是否为静息心率
    let heartRateZone: Int?              // 心率区间 (1-5)
}

// MARK: - 运动记录
struct WorkoutRecord: Codable, Identifiable {
    let id: UUID
    let date: Date
    let startTime: Date
    let endTime: Date
    let durationMinutes: Int
    let workoutType: String              // 运动类型
    let loadPeak: Int                    // 训练负荷 (AU)
    let aerobicEffect: Double            // 有氧训练效果 (0-5)
    let anaerobicEffect: Double          // 无氧训练效果 (0-5)
    let vo2max: Double?                  // VO2max (ml/kg/min)
    let recoveryTimeMinutes: Int?        // 恢复时间 (分钟)
    let fitnessAge: Int?                 // 设备体能年龄
    let avgHeartRate: Int?
    let maxHeartRate: Int?
    let calories: Int?
}

// MARK: - 每日聚合数据
struct DailyAggregatedData: Codable, Identifiable {
    let id: UUID
    let date: Date
    
    // 睡眠
    var sleepRecord: SleepRecord?
    
    // HRV (当日晨起)
    var morningHRV: Double?
    var hrvRmssd3DayAvg: Double?
    var hrvRmssd7DayAvg: Double?
    
    // 静息心率
    var restingHeartRate: Int?
    
    // 训练
    var workouts: [WorkoutRecord]
    var totalTrainingLoadAU: Int {
        workouts.reduce(0) { $0 + $1.loadPeak }
    }
    
    // PAI
    var lowPAI: Int
    var midPAI: Int
    var highPAI: Int
    var weeklyPAI: Double?
    
    // 压力/情绪/血氧 (仅展示)
    var avgStress: Double?
    var avgMood: Double?
    var avgBloodOxygen: Double?
    var nightBloodOxygen: Double?        // 夜间平均血氧
    
    // Hooper主观评分 (1-7)
    var hooperFatigue: Int?
    var hooperSoreness: Int?
    var hooperStress: Int?
    var hooperSleep: Int?
    
    // 准备度结果
    var readinessScore: Int?
    var readinessDiagnosis: String?
    var posteriorProbs: [String: Double]?
}

// MARK: - 个人基线
struct PersonalBaseline: Codable {
    var userId: String
    var lastUpdated: Date
    
    // 睡眠基线
    var sleepBaselineHours: Double?
    var sleepBaselineEff: Double?
    var restBaselineRatio: Double?
    
    // HRV基线
    var hrvBaselineMu: Double?
    var hrvBaselineSd: Double?
    
    // 数据质量
    var dataQualityScore: Double
    var sleepRecordCount: Int
    var hrvRecordCount: Int
    
    // 是否有足够数据计算基线
    var isBaselineReady: Bool {
        sleepRecordCount >= 15 && hrvRecordCount >= 10
    }
}

// MARK: - 准备度状态
struct ReadinessState: Codable {
    let date: Date
    let priorProbs: [String: Double]
    let posteriorProbs: [String: Double]
    let score: Int                       // 0-100
    let diagnosis: String                // 主导状态名
    let evidenceUsed: [String]           // 使用的证据列表
    
    // 默认首日先验 (新用户)
    static let defaultFirstDayPrior: [String: Double] = [
        "Peak": 0.10,
        "Well-adapted": 0.50,
        "FOR": 0.30,
        "Acute Fatigue": 0.10,
        "NFOR": 0.0,
        "OTS": 0.0
    ]
}

// MARK: - 因果输入 (Prior计算用)
struct CausalInputs {
    var trainingLoad: String?            // "无"/"低"/"中"/"高"/"极高"
    var recentTrainingLoads: [String]    // 过去28天的训练负荷标签
    var recentTrainingAU: [Double]?      // 过去28天的训练负荷AU值
    var sdkLoadPeak: Int?                // SDK检测的训练负荷
}

// MARK: - 证据输入 (Posterior计算用)
struct EvidenceInputs {
    // 睡眠
    var sleepDurationHours: Double?
    var sleepEfficiency: Double?
    var restorativeRatio: Double?
    var sleepBaselineHours: Double?
    var sleepBaselineEff: Double?
    var restBaselineRatio: Double?
    
    // HRV
    var hrvRmssdToday: Double?
    var hrvBaselineMu: Double?
    var hrvBaselineSd: Double?
    var hrvRmssd3DayAvg: Double?
    var hrvRmssd7DayAvg: Double?
    
    // Hooper主观评分 (1-7)
    var fatigueHooper: Int?
    var sorenessHooper: Int?
    var stressHooper: Int?
    var sleepHooper: Int?
    
    // 设备恢复状态
    var deviceRecoveryTimeMinutes: Int?
    
    // 训练效果 (昨日)
    var yesterdayAerobicEffect: Double?
    var yesterdayAnaerobicEffect: Double?
    
    // 女性周期 (可选)
    var cycleDay: Int?
    var cycleLength: Int?
}

// MARK: - 用户档案
struct UserProfile: Codable {
    var userId: String
    var gender: Gender
    var birthDate: Date?
    var chronologicalAge: Int? {
        guard let birth = birthDate else { return nil }
        return Calendar.current.dateComponents([.year], from: birth, to: Date()).year
    }
    
    enum Gender: String, Codable {
        case male = "男性"
        case female = "女性"
    }
}
```

### 8.2 SDK睡眠数据解析

```swift
// MARK: - SDK睡眠数据解析

class SDKSleepParser {
    
    /// 从SDK科学睡眠数据解析睡眠记录
    /// - Parameter sdkSleepData: SDK返回的睡眠数据字典
    /// - Returns: SleepRecord
    func parseSciSleepData(_ sdkSleepData: [String: Any]) -> SleepRecord? {
        /*
         SDK科学睡眠数据结构 (UTEModelSciSleepInfo):
         - startTime: 入睡时间戳
         - endTime: 醒来时间戳
         - deepSleepData: [UTEModelSciSleepItem] 深睡片段
         - lightSleepData: [UTEModelSciSleepItem] 浅睡片段
         - remSleepData: [UTEModelSciSleepItem] REM片段
         - awakeSleepData: [UTEModelSciSleepItem] 清醒片段
         
         每个UTEModelSciSleepItem包含:
         - startTime: 开始时间
         - endTime: 结束时间
         - duration: 时长(分钟)
        */
        
        guard let startTimestamp = sdkSleepData["startTime"] as? TimeInterval,
              let endTimestamp = sdkSleepData["endTime"] as? TimeInterval else {
            return nil
        }
        
        let bedTime = Date(timeIntervalSince1970: startTimestamp)
        let wakeTime = Date(timeIntervalSince1970: endTimestamp)
        
        // 计算各阶段时长
        let deepMinutes = sumDuration(sdkSleepData["deepSleepData"])
        let lightMinutes = sumDuration(sdkSleepData["lightSleepData"])
        let remMinutes = sumDuration(sdkSleepData["remSleepData"])
        let awakeMinutes = sumDuration(sdkSleepData["awakeSleepData"])
        
        let totalSleep = deepMinutes + lightMinutes + remMinutes
        let inBedMinutes = Int(wakeTime.timeIntervalSince(bedTime) / 60)
        
        return SleepRecord(
            id: UUID(),
            date: Calendar.current.startOfDay(for: bedTime),
            bedTime: bedTime,
            wakeTime: wakeTime,
            totalSleepMinutes: totalSleep,
            inBedMinutes: inBedMinutes,
            deepSleepMinutes: deepMinutes,
            lightSleepMinutes: lightMinutes,
            remSleepMinutes: remMinutes,
            awakeMinutes: awakeMinutes
        )
    }
    
    private func sumDuration(_ sleepItems: Any?) -> Int {
        guard let items = sleepItems as? [[String: Any]] else { return 0 }
        return items.reduce(0) { sum, item in
            sum + (item["duration"] as? Int ?? 0)
        }
    }
}
```

### 8.3 本地存储Schema (Core Data)

```swift
// MARK: - Core Data Entity Definitions

/*
 Entity: DailySleepEntity
 Attributes:
   - id: UUID
   - date: Date (indexed)
   - bedTime: Date
   - wakeTime: Date
   - totalSleepMinutes: Int16
   - inBedMinutes: Int16
   - deepSleepMinutes: Int16
   - lightSleepMinutes: Int16
   - remSleepMinutes: Int16
   - awakeMinutes: Int16
 
 Entity: HRVRecordEntity
 Attributes:
   - id: UUID
   - timestamp: Date (indexed)
   - rmssd: Double
   - sdnn: Double (optional)
   - source: String
 
 Entity: WorkoutEntity
 Attributes:
   - id: UUID
   - date: Date (indexed)
   - startTime: Date
   - endTime: Date
   - durationMinutes: Int16
   - workoutType: String
   - loadPeak: Int16
   - aerobicEffect: Double
   - anaerobicEffect: Double
   - vo2max: Double (optional)
   - recoveryTimeMinutes: Int16 (optional)
   - fitnessAge: Int16 (optional)
 
 Entity: ReadinessStateEntity
 Attributes:
   - id: UUID
   - date: Date (indexed, unique)
   - score: Int16
   - diagnosis: String
   - priorProbsJSON: String (JSON encoded)
   - posteriorProbsJSON: String (JSON encoded)
 
 Entity: PersonalBaselineEntity
 Attributes:
   - userId: String (primary key)
   - lastUpdated: Date
   - sleepBaselineHours: Double (optional)
   - sleepBaselineEff: Double (optional)
   - restBaselineRatio: Double (optional)
   - hrvBaselineMu: Double (optional)
   - hrvBaselineSd: Double (optional)
   - dataQualityScore: Double
   - sleepRecordCount: Int16
   - hrvRecordCount: Int16
 
 Entity: DailyHooperEntity
 Attributes:
   - id: UUID
   - date: Date (indexed, unique)
   - fatigue: Int16 (optional, 1-7)
   - soreness: Int16 (optional, 1-7)
   - stress: Int16 (optional, 1-7)
   - sleep: Int16 (optional, 1-7)
   - timestamp: Date
*/
```

### 8.4 生理年龄完整实现

```swift
class PhysiologicalAgeCalculator {
    
    struct PhysioAgeResult {
        let status: String                // "ok" / "partial" / "error"
        let physiologicalAge: Int?
        let physiologicalAgeWeighted: Double?
        let cssDetails: CSSResult?
        let deviceComparison: DeviceComparison?
        let inputsUsed: [String: Bool]
        let zScores: [String: Double?]
        let message: String?
    }
    
    struct DeviceComparison {
        let deviceAge: Int
        let calculatedAge: Int
        let difference: Double
        let agreement: String  // "good" / "moderate" / "low"
    }
    
    func compute(
        sdnnSeries: [Double],             // ≥30天SDNN数据
        rhrSeries: [Double],              // ≥30天静息心率数据
        sleepPayload: [String: Any],      // CSS计算用
        vo2max: Double? = nil,
        avgRecoveryTimeMinutes: Double? = nil,
        weeklyPAI: Double? = nil,
        deviceFitnessAge: Int? = nil,
        chronologicalAge: Int = 35,
        gender: String = "male"
    ) -> PhysioAgeResult {
        
        // 数据校验
        guard sdnnSeries.count >= 30, rhrSeries.count >= 30 else {
            return PhysioAgeResult(
                status: "error",
                physiologicalAge: nil,
                physiologicalAgeWeighted: nil,
                cssDetails: nil,
                deviceComparison: nil,
                inputsUsed: [:],
                zScores: [:],
                message: "需要至少30天的SDNN和静息心率数据"
            )
        }
        
        // 计算均值
        let sdnnMean = sdnnSeries.reduce(0, +) / Double(sdnnSeries.count)
        let rhrMean = rhrSeries.reduce(0, +) / Double(rhrSeries.count)
        
        // 计算CSS
        let cssCalculator = CSSCalculator()
        let cssResult = cssCalculator.computeCSS(
            durationHours: sleepPayload["sleep_duration_hours"] as? Double,
            efficiency: sleepPayload["sleep_efficiency"] as? Double,
            restorativeRatio: sleepPayload["restorative_ratio"] as? Double
        )
        let cssValue = cssResult.css ?? 70.0
        
        // 基础z分数
        let sdnnAnchor = 50.0, sdnnScale = 20.0
        let rhrAnchor = 60.0, rhrScale = 10.0
        let cssAnchor = 70.0, cssScale = 15.0
        
        let sdnnZ = (sdnnMean - sdnnAnchor) / sdnnScale
        let rhrZ = (rhrAnchor - rhrMean) / rhrScale  // 低RHR更好
        let cssZ = (cssValue - cssAnchor) / cssScale
        
        // VO2max z分数
        var vo2maxZ: Double? = nil
        if let vo2 = vo2max {
            let vo2maxAnchor: Double
            if gender == "female" {
                vo2maxAnchor = 41.0 - Double(chronologicalAge - 20) * 0.35
            } else {
                vo2maxAnchor = 47.0 - Double(chronologicalAge - 20) * 0.35
            }
            let clampedAnchor = max(25.0, min(50.0, vo2maxAnchor))
            vo2maxZ = (vo2 - clampedAnchor) / 6.0
        }
        
        // 恢复时间z分数
        var recoveryZ: Double? = nil
        if let recovery = avgRecoveryTimeMinutes {
            let recoveryAnchor = 540.0  // 9小时
            let recoveryScale = 360.0   // 6小时
            recoveryZ = max(-2.0, min(2.0, (recoveryAnchor - recovery) / recoveryScale))
        }
        
        // PAI z分数
        var paiZ: Double? = nil
        if let pai = weeklyPAI {
            paiZ = max(-2.0, min(2.0, (pai - 75.0) / 35.0))
        }
        
        // 计算年龄调整
        let baseAge = 35.0
        let ageAdjust: Double
        
        if vo2maxZ != nil {
            // 有VO2max时
            ageAdjust = -4.0 * sdnnZ
                      + -3.0 * cssZ
                      + -4.0 * rhrZ
                      + -8.0 * (vo2maxZ ?? 0)
                      + -3.0 * (recoveryZ ?? 0)
                      + -2.0 * (paiZ ?? 0)
        } else {
            // 无VO2max时
            ageAdjust = -8.0 * sdnnZ
                      + -5.0 * cssZ
                      + -6.0 * rhrZ
                      + -3.0 * (recoveryZ ?? 0)
                      + -2.0 * (paiZ ?? 0)
        }
        
        let physAge = max(18.0, min(80.0, baseAge + ageAdjust))
        let physAgeWeighted = max(18.0, min(80.0, 0.7 * physAge + 0.3 * baseAge))
        
        // 设备对比
        var comparison: DeviceComparison? = nil
        if let deviceAge = deviceFitnessAge {
            let diff = physAge - Double(deviceAge)
            let agreement: String
            if abs(diff) < 3 {
                agreement = "good"
            } else if abs(diff) < 7 {
                agreement = "moderate"
            } else {
                agreement = "low"
            }
            comparison = DeviceComparison(
                deviceAge: deviceAge,
                calculatedAge: Int(round(physAge)),
                difference: round(diff * 10) / 10,
                agreement: agreement
            )
        }
        
        return PhysioAgeResult(
            status: "ok",
            physiologicalAge: Int(round(physAge)),
            physiologicalAgeWeighted: round(physAgeWeighted * 10) / 10,
            cssDetails: cssResult,
            deviceComparison: comparison,
            inputsUsed: [
                "sdnn": true,
                "rhr": true,
                "css": cssResult.status == .ok,
                "vo2max": vo2max != nil,
                "recovery": avgRecoveryTimeMinutes != nil,
                "pai": weeklyPAI != nil
            ],
            zScores: [
                "sdnn_z": round(sdnnZ * 100) / 100,
                "rhr_z": round(rhrZ * 100) / 100,
                "css_z": round(cssZ * 100) / 100,
                "vo2max_z": vo2maxZ.map { round($0 * 100) / 100 },
                "recovery_z": recoveryZ.map { round($0 * 100) / 100 },
                "pai_z": paiZ.map { round($0 * 100) / 100 }
            ],
            message: nil
        )
    }
}
```

### 8.5 女性月经周期算法

```swift
class MenstrualCycleCalculator {
    
    /// 根据周期日和周期长度计算状态似然
    func cycleLikelihoodByDay(day: Int, cycleLength: Int = 28) -> [String: Double] {
        // 周期阶段划分
        // 1. 经期+早期卵泡期 (1-7天): 能量低
        // 2. 晚期卵泡期+排卵期 (8-14天): 能量高峰
        // 3. 早期黄体期 (15-21天): 能量中等
        // 4. 晚期黄体期 (22-28天): PMS，能量低
        
        // 根据周期长度调整阶段
        let ovulationDay = cycleLength / 2  // 排卵日约为周期中点
        let lutealLength = cycleLength - ovulationDay  // 黄体期长度 (通常14天)
        
        let phase: String
        
        if day <= 5 {
            // 经期 (1-5天)
            phase = "menstrual"
        } else if day <= ovulationDay - 3 {
            // 早期卵泡期
            phase = "early_follicular"
        } else if day <= ovulationDay + 2 {
            // 晚期卵泡期 + 排卵期 (能量高峰)
            phase = "late_follicular_ovulatory"
        } else if day <= ovulationDay + lutealLength / 2 {
            // 早期黄体期
            phase = "early_luteal"
        } else {
            // 晚期黄体期 (PMS)
            phase = "late_luteal"
        }
        
        // 根据阶段返回似然
        switch phase {
        case "menstrual":
            return [
                "Peak": 0.10, "Well-adapted": 0.35, "FOR": 0.25,
                "Acute Fatigue": 0.20, "NFOR": 0.10, "OTS": 0.0
            ]
        case "early_follicular":
            return [
                "Peak": 0.15, "Well-adapted": 0.40, "FOR": 0.20,
                "Acute Fatigue": 0.15, "NFOR": 0.10, "OTS": 0.0
            ]
        case "late_follicular_ovulatory":
            // 能量高峰期
            return [
                "Peak": 0.45, "Well-adapted": 0.45, "FOR": 0.05,
                "Acute Fatigue": 0.03, "NFOR": 0.02, "OTS": 0.0
            ]
        case "early_luteal":
            return [
                "Peak": 0.10, "Well-adapted": 0.30, "FOR": 0.25,
                "Acute Fatigue": 0.20, "NFOR": 0.15, "OTS": 0.0
            ]
        case "late_luteal":
            // PMS期，能量最低
            return [
                "Peak": 0.044, "Well-adapted": 0.177, "FOR": 0.177,
                "Acute Fatigue": 0.248, "NFOR": 0.354, "OTS": 0.0
            ]
        default:
            // 默认中性
            return [
                "Peak": 0.20, "Well-adapted": 0.40, "FOR": 0.20,
                "Acute Fatigue": 0.15, "NFOR": 0.05, "OTS": 0.0
            ]
        }
    }
}
```

### 8.6 iOS后台数据采集配置

```swift
import BackgroundTasks

class BackgroundDataCollector {
    
    static let shared = BackgroundDataCollector()
    
    // 后台任务标识符 (需在Info.plist中注册)
    static let healthSyncTaskId = "com.motivue.healthSync"
    static let baselineUpdateTaskId = "com.motivue.baselineUpdate"
    
    // MARK: - 注册后台任务
    
    func registerBackgroundTasks() {
        // 健康数据同步任务 (每小时)
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.healthSyncTaskId,
            using: nil
        ) { task in
            self.handleHealthSyncTask(task as! BGAppRefreshTask)
        }
        
        // 基线更新任务 (每天凌晨)
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.baselineUpdateTaskId,
            using: nil
        ) { task in
            self.handleBaselineUpdateTask(task as! BGProcessingTask)
        }
    }
    
    // MARK: - 调度后台任务
    
    func scheduleHealthSync() {
        let request = BGAppRefreshTaskRequest(identifier: Self.healthSyncTaskId)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)  // 1小时后
        
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            print("无法调度健康同步任务: \(error)")
        }
    }
    
    func scheduleBaselineUpdate() {
        let request = BGProcessingTaskRequest(identifier: Self.baselineUpdateTaskId)
        request.requiresNetworkConnectivity = false
        request.requiresExternalPower = false
        
        // 设置为每天凌晨3点执行
        var components = Calendar.current.dateComponents([.hour, .minute], from: Date())
        components.hour = 3
        components.minute = 0
        if let nextRun = Calendar.current.nextDate(after: Date(), matching: components, matchingPolicy: .nextTime) {
            request.earliestBeginDate = nextRun
        }
        
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch {
            print("无法调度基线更新任务: \(error)")
        }
    }
    
    // MARK: - 任务处理
    
    private func handleHealthSyncTask(_ task: BGAppRefreshTask) {
        scheduleHealthSync()  // 调度下一次
        
        let operation = HealthSyncOperation()
        
        task.expirationHandler = {
            operation.cancel()
        }
        
        operation.completionBlock = {
            task.setTaskCompleted(success: !operation.isCancelled)
        }
        
        OperationQueue().addOperation(operation)
    }
    
    private func handleBaselineUpdateTask(_ task: BGProcessingTask) {
        scheduleBaselineUpdate()  // 调度下一次
        
        Task {
            do {
                let calculator = PersonalBaselineCalculator()
                // 获取过去30天数据
                let sleepRecords = try await fetchRecentSleepRecords(days: 30)
                let hrvRecords = try await fetchRecentHRVRecords(days: 30)
                
                // 计算新基线
                let newBaseline = calculator.calculateBaseline(
                    sleepRecords: sleepRecords,
                    hrvRecords: hrvRecords
                )
                
                // 保存到本地
                try await saveBaseline(newBaseline)
                
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }
    }
}

/*
 Info.plist 需要添加:
 
 <key>BGTaskSchedulerPermittedIdentifiers</key>
 <array>
     <string>com.motivue.healthSync</string>
     <string>com.motivue.baselineUpdate</string>
 </array>
 
 <key>UIBackgroundModes</key>
 <array>
     <string>fetch</string>
     <string>processing</string>
     <string>bluetooth-central</string>
 </array>
*/
```

---

## 九、SwiftUI 实现建议

### 9.1 项目结构

```
Motivue/
├── App/
│   └── MotivueApp.swift
├── Core/
│   ├── Models/
│   │   ├── SleepRecord.swift
│   │   ├── HRVRecord.swift
│   │   ├── BaselineResult.swift
│   │   └── ReadinessState.swift
│   ├── Services/
│   │   ├── BluetoothService.swift      # SDK封装
│   │   ├── HealthKitService.swift      # HealthKit封装
│   │   ├── DataAggregatorService.swift # 数据聚合
│   │   └── PersistenceService.swift    # 本地存储
│   └── Engines/
│       ├── BaselineCalculator.swift    # 基线计算
│       ├── CSSCalculator.swift         # 睡眠评分
│       ├── ReadinessEngine.swift       # 准备度引擎
│       └── PhysioAgeCalculator.swift   # 生理年龄
├── Features/
│   ├── Dashboard/
│   ├── Readiness/
│   ├── Sleep/
│   ├── HRV/
│   └── WeeklyReport/
├── Constants/
│   ├── CPTTables.swift                 # 概率表
│   └── ThresholdConfig.swift           # 阈值配置
└── Resources/
```

### 8.2 核心 Protocol 定义

```swift
protocol DataSourceProtocol {
    func fetchSleepData(from: Date, to: Date) async throws -> [SleepRecord]
    func fetchHRVData(from: Date, to: Date) async throws -> [HRVRecord]
    func fetchHeartRateData(from: Date, to: Date) async throws -> [HeartRateRecord]
}

protocol ReadinessEngineProtocol {
    var currentState: ReadinessState { get }
    func calculatePrior(causalInputs: CausalInputs) -> StateProbabilities
    func updateWithEvidence(_ evidence: Evidence) -> ReadinessResult
}

protocol BaselineCalculatorProtocol {
    func calculateBaseline(sleepRecords: [SleepRecord], hrvRecords: [HRVRecord]) -> BaselineResult
}
```

---

## 十、测试与验证

### 10.1 验证用例 (给定输入 → 预期输出)

#### CSS睡眠评分验证

| 用例 | 时长(h) | 效率 | 恢复性 | 预期CSS | 说明 |
|-----|--------|------|--------|---------|------|
| 优秀睡眠 | 8.0 | 0.92 | 0.40 | 96.0 | 100×0.4 + 94×0.3 + 100×0.3 |
| 良好睡眠 | 7.5 | 0.88 | 0.32 | 89.8 | 100×0.4 + 86×0.3 + 80×0.3 |
| 中等睡眠 | 6.5 | 0.80 | 0.28 | 66.0 | 83×0.4 + 40×0.3 + 53×0.3 |
| 较差睡眠 | 5.0 | 0.72 | 0.18 | 11.1 | 33×0.4 + 0×0.3 + 0×0.3 |

```swift
// CSS验证测试
func testCSSCalculation() {
    let calculator = CSSCalculator()
    
    // 用例1: 优秀睡眠
    let result1 = calculator.computeCSS(durationHours: 8.0, efficiency: 0.92, restorativeRatio: 0.40)
    XCTAssertEqual(result1.css!, 96.0, accuracy: 1.0)
    
    // 用例2: 良好睡眠
    let result2 = calculator.computeCSS(durationHours: 7.5, efficiency: 0.88, restorativeRatio: 0.32)
    XCTAssertEqual(result2.css!, 89.8, accuracy: 1.0)
}
```

#### HRV趋势判定验证

| 用例 | 今日HRV | 基线μ | 基线σ | z分数 | 预期趋势 |
|-----|--------|-------|-------|-------|---------|
| 上升 | 65 | 50 | 20 | +0.75 | rising |
| 稳定 | 52 | 50 | 20 | +0.10 | stable |
| 轻微下降 | 38 | 50 | 20 | -0.60 | slight_decline |
| 显著下降 | 15 | 50 | 20 | -1.75 | significant_decline |

#### 准备度引擎验证

**用例: 良好恢复日**
```
输入:
- 昨日后验: {Peak: 0.1, Well-adapted: 0.6, FOR: 0.2, Acute Fatigue: 0.1, NFOR: 0, OTS: 0}
- 训练负荷: "中"
- HRV趋势: "stable"
- 睡眠表现: "good"
- 恢复性睡眠: "high"
- Hooper疲劳: 2 (low)

预期输出:
- 准备度分数: 78-82
- 诊断: Well-adapted
```

**用例: 高负荷后疲劳日**
```
输入:
- 昨日后验: {Peak: 0.05, Well-adapted: 0.3, FOR: 0.4, Acute Fatigue: 0.2, NFOR: 0.05, OTS: 0}
- 训练负荷: "高"
- HRV趋势: "slight_decline"
- 睡眠表现: "medium"
- Hooper疲劳: 5 (high)
- Hooper酸痛: 5 (high)

预期输出:
- 准备度分数: 45-55
- 诊断: FOR 或 Acute Fatigue
```

#### 生理年龄验证

| 用例 | SDNN均值 | RHR均值 | CSS | VO2max | 实际年龄 | 预期生理年龄 |
|-----|---------|--------|-----|--------|---------|------------|
| 年轻运动员 | 70 | 52 | 85 | 55 | 30 | 22-26 |
| 健康中年 | 50 | 60 | 70 | 40 | 40 | 33-38 |
| 久坐不动 | 30 | 75 | 55 | 30 | 40 | 50-58 |

### 10.2 单元测试代码

```swift
import XCTest
@testable import Motivue

class ReadinessEngineTests: XCTestCase {
    
    var engine: ReadinessEngine!
    
    override func setUp() {
        super.setUp()
        // 使用默认首日先验
        engine = ReadinessEngine(previousProbs: ReadinessState.defaultFirstDayPrior)
    }
    
    // MARK: - Prior计算测试
    
    func testPriorNormalization() {
        let causalInputs = CausalInputs(trainingLoad: "中", recentTrainingLoads: [])
        let prior = engine.calculateTodayPrior(causalInputs: causalInputs)
        
        // 验证归一化: 所有概率和为1
        let sum = prior.values.reduce(0, +)
        XCTAssertEqual(sum, 1.0, accuracy: 0.0001)
    }
    
    func testTrainingLoadImpact() {
        // 高训练负荷应该增加FOR/Acute Fatigue概率
        let highLoadInputs = CausalInputs(trainingLoad: "极高", recentTrainingLoads: [])
        let highPrior = engine.calculateTodayPrior(causalInputs: highLoadInputs)
        
        engine = ReadinessEngine(previousProbs: ReadinessState.defaultFirstDayPrior)
        let lowLoadInputs = CausalInputs(trainingLoad: "低", recentTrainingLoads: [])
        let lowPrior = engine.calculateTodayPrior(causalInputs: lowLoadInputs)
        
        // 高负荷的FOR概率应该更高
        XCTAssertGreaterThan(highPrior["FOR"]!, lowPrior["FOR"]!)
        // 高负荷的Peak概率应该更低
        XCTAssertLessThan(highPrior["Peak"]!, lowPrior["Peak"]!)
    }
    
    func testConsecutiveHighLoadPenalty() {
        // 连续4天高负荷应该触发惩罚
        let recentLoads = ["高", "高", "高", "高"]
        let inputs = CausalInputs(trainingLoad: "高", recentTrainingLoads: recentLoads)
        let prior = engine.calculateTodayPrior(causalInputs: inputs)
        
        // NFOR概率应该显著增加
        XCTAssertGreaterThan(prior["NFOR"]!, 0.1)
    }
    
    // MARK: - Posterior更新测试
    
    func testPosteriorConvergence() {
        let causalInputs = CausalInputs(trainingLoad: "中", recentTrainingLoads: [])
        _ = engine.calculateTodayPrior(causalInputs: causalInputs)
        
        // 累加多个正面证据
        var evidence: [String: Any] = ["hrv_trend": "rising"]
        var result = engine.updateWithEvidence(evidence)
        let score1 = result.score
        
        evidence["sleep_performance"] = "good"
        result = engine.updateWithEvidence(evidence)
        let score2 = result.score
        
        evidence["subjective_fatigue"] = "low"
        result = engine.updateWithEvidence(evidence)
        let score3 = result.score
        
        // 分数应该逐步提高
        XCTAssertGreaterThanOrEqual(score2, score1)
        XCTAssertGreaterThanOrEqual(score3, score2)
    }
    
    // MARK: - 数据映射测试
    
    func testHRVTrendMapping() {
        let mapper = HRVTrendMapper()
        
        // z分数测试
        XCTAssertEqual(mapper.mapHRVTrend(todayRMSSD: 65, baselineMu: 50, baselineSd: 20, rmssd3DayAvg: nil, rmssd7DayAvg: nil), "rising")
        XCTAssertEqual(mapper.mapHRVTrend(todayRMSSD: 52, baselineMu: 50, baselineSd: 20, rmssd3DayAvg: nil, rmssd7DayAvg: nil), "stable")
        XCTAssertEqual(mapper.mapHRVTrend(todayRMSSD: 38, baselineMu: 50, baselineSd: 20, rmssd3DayAvg: nil, rmssd7DayAvg: nil), "slight_decline")
        XCTAssertEqual(mapper.mapHRVTrend(todayRMSSD: 15, baselineMu: 50, baselineSd: 20, rmssd3DayAvg: nil, rmssd7DayAvg: nil), "significant_decline")
    }
    
    func testSleepPerformanceMapping() {
        let mapper = SleepPerformanceMapper()
        
        XCTAssertEqual(mapper.mapSleepPerformance(durationHours: 8.0, efficiency: 0.90), "good")
        XCTAssertEqual(mapper.mapSleepPerformance(durationHours: 6.5, efficiency: 0.78), "medium")
        XCTAssertEqual(mapper.mapSleepPerformance(durationHours: 5.0, efficiency: 0.70), "poor")
    }
    
    func testHooperMapping() {
        let mapper = HooperMapper()
        
        XCTAssertEqual(mapper.mapHooperScore(1), "low")
        XCTAssertEqual(mapper.mapHooperScore(2), "low")
        XCTAssertEqual(mapper.mapHooperScore(3), "medium")
        XCTAssertEqual(mapper.mapHooperScore(4), "medium")
        XCTAssertEqual(mapper.mapHooperScore(5), "high")
        XCTAssertEqual(mapper.mapHooperScore(7), "high")
    }
}
```

### 10.3 集成测试要点

1. **SDK数据同步完整性**
   - 蓝牙连接稳定性
   - 数据帧丢失检测
   - 断线重连后数据补全

2. **后台数据采集稳定性**
   - BGTask调度可靠性
   - 内存使用监控
   - 电池消耗优化

3. **多数据源融合**
   - SDK与HealthKit数据冲突处理
   - 数据去重
   - 时间戳对齐

---

## 十一、洞察与因果分析系统 (Unified Insights Engine)

> **核心设计原则**: 统一因果引擎 (CausalEngine) 作为单一入口，供日报洞察、周报分析、仪表盘图表共同调用。避免重复实现因果分析逻辑。

### 11.1 统一因果引擎架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CausalEngine (统一因果引擎)                          │
│                           ═══════════════════════                           │
│                            单一入口，多场景复用                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   输入: [DailyData] + PersonalBaseline + AnalysisPeriod                     │
│                                                                              │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │  Step 1: collectCauses()                                           │    │
│   │    • 运动记录 (任意类型，不写死)                                    │    │
│   │    • Journal字段 (通用扫描，新字段自动参与)                         │    │
│   │    • SDK额外数据 (device_stress, mood等)                           │    │
│   ├────────────────────────────────────────────────────────────────────┤    │
│   │  Step 2: collectEffects()                                          │    │
│   │    • HRV变化 (相对基线%)                                           │    │
│   │    • 睡眠效率变化                                                   │    │
│   │    • 睡眠时长变化                                                   │    │
│   │    • 准备度分数                                                     │    │
│   ├────────────────────────────────────────────────────────────────────┤    │
│   │  Step 3: discoverCorrelations()                                    │    │
│   │    • 分组: 有cause时的effect vs 无cause时的effect                  │    │
│   │    • Cohen's d 显著性检验                                          │    │
│   │    • 只输出 significance ≥ 0.5 的关联                              │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│   输出: CausalAnalysisResult                                                │
│     • correlations: [DiscoveredCorrelation]                                 │
│     • patterns: [DetectedPattern]                                           │
│     • summary: StatsSummary                                                 │
│                                                                              │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  📱 日报洞察     │       │  📊 周报系统     │       │  📈 仪表盘图表  │
│                 │       │                 │       │                 │
│ engine.analyze( │       │ engine.analyze( │       │ 直接使用        │
│   period: .daily│       │   period: .week │       │ correlations +  │
│   data: 1-3天   │       │   data: 7天     │       │ trends 渲染     │
│ )               │       │ )               │       │                 │
│ + 小模型文案    │       │ → 云端LLM报告   │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

#### 设计优势

| 特性 | 说明 |
|------|------|
| **单一入口** | 所有因果分析通过 `CausalEngine.analyze()` 调用 |
| **零重复** | 日报/周报/图表共用同一套分析逻辑 |
| **通用性** | 不写死字段，任何有值记录都参与分析 |
| **可扩展** | Journal新增字段自动参与因果发现 |
| **多周期** | 支持 daily(1-3天) / weekly(7天) / monthly(28天) |

### 11.2 统一数据模型 (CausalEngine)

```swift
// MARK: - 因果引擎核心数据模型

/// 分析周期
enum AnalysisPeriod: String, Codable {
    case daily = "daily"      // 1-3天，用于日报一句话洞察
    case weekly = "weekly"    // 7天，用于周报
    case monthly = "monthly"  // 28天，用于月度趋势
}

// MARK: - 输入模型

/// 因记录 (Cause)
struct CauseRecord: Codable {
    let category: String          // "activity", "journal", "sdk_extra"
    let key: String               // 字段key (如 "running", "alcohol_consumed")
    let label: String             // 显示名称 (如 "跑步", "饮酒")
    let value: Double             // 量化值
    let date: Date                // 发生日期
    let daysAgo: Int              // 距今天数
    let metadata: [String: Any]?  // 额外信息
}

/// 果记录 (Effect)
struct EffectRecord: Codable {
    let key: String               // "hrv_change", "sleep_efficiency_change" 等
    let value: Double             // 变化值 (百分比或绝对值)
    let date: Date                // 发生日期
}

/// 发现的相关性 (核心输出)
struct DiscoveredCorrelation: Codable {
    let causeKey: String          // 因的key
    let causeLabel: String        // 因的显示名称
    let effectKey: String         // 果的key
    let avgEffectWithCause: Double    // 有该因时的平均果值
    let avgEffectWithoutCause: Double // 无该因时的平均果值
    let difference: Double        // 差异
    let significance: Double      // 显著性 (0-1, Cohen's d 归一化)
    let sampleSize: Int           // 样本量
    let isSignificant: Bool       // 是否显著 (>= 0.5)
}

/// 检测到的模式
struct DetectedPattern: Codable {
    let patternType: String       // "consecutive_high_load", "sleep_debt", "weekend_effect"
    let description: String       // 模式描述
    let occurrences: Int          // 发生次数
    let avgImpact: Double         // 平均影响
}

// MARK: - 输出模型

/// 因果分析结果 (CausalEngine的统一输出)
struct CausalAnalysisResult: Codable {
    let period: AnalysisPeriod
    let correlations: [DiscoveredCorrelation]  // 发现的相关性
    let patterns: [DetectedPattern]            // 发现的模式
    let summary: StatsSummary                  // 统计摘要
    let generatedAt: Date
}

/// 统计摘要
struct StatsSummary: Codable {
    let totalCauses: Int          // 分析的因数量
    let totalEffects: Int         // 分析的果数量
    let significantCorrelations: Int // 显著相关性数量
    let topCauseKey: String?      // 影响最大的因
    let topEffectKey: String?     // 变化最明显的果
}

// MARK: - 洞察展示模型

/// 洞察项 (用于UI展示)
struct InsightItem: Codable, Identifiable {
    let id: String
    let period: AnalysisPeriod
    let correlation: DiscoveredCorrelation
    let narrative: String         // 自然语言文案 (小模型生成)
    let generatedAt: Date
}

/// 一句话洞察 (日报专用)
struct OneLinerInsight: Codable {
    let headline: String          // "📉 HRV下降提醒"
    let body: String              // "昨天打篮球后，今天HRV下降了8%..."
    let recommendation: String?   // "建议今天安排轻度恢复"
    let priority: Int             // 1=高, 2=中, 3=低
}

/// 日报洞察汇总
struct DailyInsightSummary: Codable {
    let date: Date
    let overallStatus: String         // "optimal", "good", "attention", "warning"
    let statusEmoji: String           // "🟢", "🟡", "🟠", "🔴"
    let oneLiner: OneLinerInsight?    // 主洞察
    let insights: [InsightItem]       // 其他洞察
}
```

### 11.3 CausalEngine 核心实现

> **⚠️ 重要**: 以下是统一因果引擎的核心实现，取代了之前分散的规则引擎。所有因果分析都应通过 `CausalEngine.analyze()` 调用。

```swift
// MARK: - CausalEngine (统一因果分析引擎)

class CausalEngine {
    
    private let baselineManager: PersonalBaselineManager
    private let fieldLabelConfig: FieldLabelConfig
    
    init(baselineManager: PersonalBaselineManager) {
        self.baselineManager = baselineManager
        self.fieldLabelConfig = FieldLabelConfig.shared
    }
    
    // MARK: - 公开接口 (唯一入口)
    
    /// 执行因果分析 - 日报/周报/仪表盘统一调用此方法
    func analyze(data: [DailyData], period: AnalysisPeriod) -> CausalAnalysisResult {
        
        guard let baseline = baselineManager.getCurrentBaseline() else {
            return CausalAnalysisResult.empty(period: period)
        }
        
        // Step 1: 收集所有"因"
        let causes = collectAllCauses(data: data)
        
        // Step 2: 收集所有"果"
        let effects = collectAllEffects(data: data, baseline: baseline)
        
        // Step 3: 发现相关性
        let correlations = discoverCorrelations(causes: causes, effects: effects)
        
        // Step 4: 检测模式
        let patterns = detectPatterns(data: data, correlations: correlations)
        
        // Step 5: 构建摘要
        let summary = buildSummary(
            causes: causes,
            effects: effects,
            correlations: correlations
        )
        
        return CausalAnalysisResult(
            period: period,
            correlations: correlations,
            patterns: patterns,
            summary: summary,
            generatedAt: Date()
        )
    }
    
    // MARK: - Step 1: 收集所有因 (通用，不写死字段)
    
    private func collectAllCauses(data: [DailyData]) -> [CauseRecord] {
        
        var causes: [CauseRecord] = []
        
        for (dayIndex, day) in data.enumerated() {
            let daysAgo = dayIndex + 1
            
            // === 运动记录 (任意类型) ===
            for activity in day.activities {
                causes.append(CauseRecord(
                    category: "activity",
                    key: activity.type,
                    label: activity.type,
                    value: activity.trainingLoad,
                    date: day.date,
                    daysAgo: daysAgo,
                    metadata: [
                        "duration": activity.duration,
                        "intensity": activity.intensity
                    ]
                ))
            }
            
            // === Journal记录 (通用扫描) ===
            if let journal = day.journal {
                causes.append(contentsOf: extractJournalCauses(journal: journal, daysAgo: daysAgo))
            }
            
            // === SDK额外数据 ===
            if let sdkExtras = day.sdkExtras {
                causes.append(contentsOf: extractSDKCauses(extras: sdkExtras, date: day.date, daysAgo: daysAgo))
            }
        }
        
        return causes
    }
    
    /// 通用Journal字段提取 - 自动扫描所有非空字段
    private func extractJournalCauses(journal: JournalEntry, daysAgo: Int) -> [CauseRecord] {
        
        var causes: [CauseRecord] = []
        let journalDict = journal.toDictionary()
        
        for (key, value) in journalDict {
            // 跳过空值和元数据
            guard !isEmptyValue(value), !isMetadataField(key) else { continue }
            
            causes.append(CauseRecord(
                category: "journal",
                key: key,
                label: fieldLabelConfig.getLabel(for: key),
                value: normalizeValue(value),
                date: journal.date,
                daysAgo: daysAgo,
                metadata: ["raw_value": "\(value)"]
            ))
        }
        
        return causes
    }
    
    // MARK: - Step 2: 收集所有果
    
    private func collectAllEffects(data: [DailyData], baseline: PersonalBaseline) -> [EffectRecord] {
        
        var effects: [EffectRecord] = []
        
        for day in data {
            guard let metrics = day.metrics else { continue }
            
            // HRV变化 (相对基线%)
            if let hrv = metrics.hrvRMSSD {
                let change = ((hrv - baseline.hrvRMSSDMean) / baseline.hrvRMSSDMean) * 100
                effects.append(EffectRecord(key: "hrv_change", value: change, date: day.date))
            }
            
            // 睡眠效率变化
            let sleepEffChange = ((metrics.sleep.efficiency - baseline.sleepEfficiencyMean) 
                                  / baseline.sleepEfficiencyMean) * 100
            effects.append(EffectRecord(key: "sleep_efficiency_change", value: sleepEffChange, date: day.date))
            
            // 睡眠时长变化
            let durationChange = ((Double(metrics.sleep.totalMinutes) - baseline.sleepDurationMean) 
                                  / baseline.sleepDurationMean) * 100
            effects.append(EffectRecord(key: "sleep_duration_change", value: durationChange, date: day.date))
            
            // 准备度分数
            if let readiness = metrics.readinessScore {
                effects.append(EffectRecord(key: "readiness_score", value: readiness, date: day.date))
            }
        }
        
        return effects
    }
    
    // MARK: - Step 3: 发现相关性 (Cohen's d 显著性检验)
    
    private func discoverCorrelations(
        causes: [CauseRecord],
        effects: [EffectRecord]
    ) -> [DiscoveredCorrelation] {
        
        var correlations: [DiscoveredCorrelation] = []
        
        let causesByKey = Dictionary(grouping: causes) { $0.key }
        let effectsByKey = Dictionary(grouping: effects) { $0.key }
        
        for (causeKey, causeRecords) in causesByKey {
            let causeDates = Set(causeRecords.map { $0.date })
            
            for (effectKey, effectRecords) in effectsByKey {
                
                // 分组: 有cause时 vs 无cause时
                var effectsWithCause: [Double] = []
                var effectsWithoutCause: [Double] = []
                
                for effect in effectRecords {
                    let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: effect.date)!
                    let dayBefore = Calendar.current.date(byAdding: .day, value: -2, to: effect.date)!
                    
                    if causeDates.contains(yesterday) || causeDates.contains(dayBefore) {
                        effectsWithCause.append(effect.value)
                    } else {
                        effectsWithoutCause.append(effect.value)
                    }
                }
                
                // 样本量检查
                guard effectsWithCause.count >= 3, effectsWithoutCause.count >= 3 else { continue }
                
                // 计算差异
                let avgWith = effectsWithCause.reduce(0, +) / Double(effectsWithCause.count)
                let avgWithout = effectsWithoutCause.reduce(0, +) / Double(effectsWithoutCause.count)
                let difference = avgWith - avgWithout
                
                // Cohen's d 显著性
                let pooledStd = calculatePooledStd(effectsWithCause, effectsWithoutCause)
                let effectSize = pooledStd > 0 ? abs(difference) / pooledStd : 0
                let significance = min(effectSize / 0.8, 1.0)
                
                guard significance >= 0.3 else { continue }
                
                correlations.append(DiscoveredCorrelation(
                    causeKey: causeKey,
                    causeLabel: causeRecords.first?.label ?? causeKey,
                    effectKey: effectKey,
                    avgEffectWithCause: avgWith,
                    avgEffectWithoutCause: avgWithout,
                    difference: difference,
                    significance: significance,
                    sampleSize: effectsWithCause.count,
                    isSignificant: significance >= 0.5
                ))
            }
        }
        
        return correlations.sorted { $0.significance > $1.significance }
    }
    
    // MARK: - Step 4: 模式检测
    
    private func detectPatterns(data: [DailyData], correlations: [DiscoveredCorrelation]) -> [DetectedPattern] {
        
        var patterns: [DetectedPattern] = []
        
        // 检测连续高负荷模式
        if let highLoadPattern = detectConsecutiveHighLoad(data: data) {
            patterns.append(highLoadPattern)
        }
        
        // 检测睡眠债务模式
        if let sleepDebtPattern = detectSleepDebt(data: data) {
            patterns.append(sleepDebtPattern)
        }
        
        // 检测周末效应
        if let weekendPattern = detectWeekendEffect(data: data) {
            patterns.append(weekendPattern)
        }
        
        return patterns
    }
    
    // MARK: - 辅助方法
    
    private func calculatePooledStd(_ a: [Double], _ b: [Double]) -> Double {
        let n1 = Double(a.count)
        let n2 = Double(b.count)
        let mean1 = a.reduce(0, +) / n1
        let mean2 = b.reduce(0, +) / n2
        let var1 = a.map { pow($0 - mean1, 2) }.reduce(0, +) / n1
        let var2 = b.map { pow($0 - mean2, 2) }.reduce(0, +) / n2
        return sqrt((var1 + var2) / 2)
    }
    
    private func isEmptyValue(_ value: Any) -> Bool {
        if let b = value as? Bool { return !b }
        if let s = value as? String { return s.isEmpty }
        if let a = value as? [Any] { return a.isEmpty }
        return false
    }
    
    private func isMetadataField(_ key: String) -> Bool {
        ["id", "date", "created_at", "updated_at", "user_id"].contains(key)
    }
    
    private func normalizeValue(_ value: Any) -> Double {
        if let d = value as? Double { return d }
        if let i = value as? Int { return Double(i) }
        if let b = value as? Bool { return b ? 1.0 : 0.0 }
        return 1.0
    }
}
```

---

> **📝 以下是旧版规则引擎代码 (已废弃，仅作参考)**
> 
> 新代码应使用上面的 `CausalEngine`，以下代码保留是为了帮助理解旧系统逻辑。

<details>
<summary>点击展开旧版规则引擎代码 (已废弃)</summary>

```swift
// MARK: - [已废弃] 旧版因果关联分析器

class CausalAnalyzer_Legacy {
    
    private let dataStore: LocalDataStore
    private let baselineManager: PersonalBaselineManager
    
    // MARK: - 活动影响分析
    
    /// 分析昨日活动对今日指标的影响
    func analyzeActivityImpact(
        todayMetrics: DailyMetrics,
        yesterdayActivities: [ActivityRecord]
    ) -> [InsightItem] {
        
        var insights: [InsightItem] = []
        
        // 获取基线
        guard let baseline = baselineManager.getCurrentBaseline() else { return insights }
        
        // 计算今日HRV相对基线的变化
        let hrvChange = calculateHRVChange(today: todayMetrics.hrvRMSSD, baseline: baseline)
        
        // 遍历昨日活动，寻找关联
        for activity in yesterdayActivities {
            if let insight = analyzeActivityHRVCorrelation(
                activity: activity,
                hrvChange: hrvChange,
                todayMetrics: todayMetrics,
                baseline: baseline
            ) {
                insights.append(insight)
            }
        }
        
        return insights
    }
    
    /// 分析单个活动与HRV变化的关联
    private func analyzeActivityHRVCorrelation(
        activity: ActivityRecord,
        hrvChange: MetricChange,
        todayMetrics: DailyMetrics,
        baseline: PersonalBaseline
    ) -> InsightItem? {
        
        // 高强度活动 + HRV下降 = 强关联
        let isHighIntensity = activity.intensity >= 0.7 || activity.trainingLoad >= 300
        let isHRVDeclined = hrvChange.changeDirection == "down" && 
                            abs(hrvChange.changePercent) >= 5
        
        guard isHighIntensity && isHRVDeclined else { return nil }
        
        // 构建因果证据
        let cause = CausalEvidence(
            factor: activity.type,
            factorLabel: activityTypeLabel(activity.type),
            timestamp: activity.endTime,
            value: activity.duration,
            source: activity.source
        )
        
        // 生成自然语言文案
        let narrative = generateActivityImpactNarrative(
            activity: activity,
            hrvChange: hrvChange,
            baseline: baseline
        )
        
        return InsightItem(
            id: UUID().uuidString,
            type: .activityImpact,
            priority: abs(hrvChange.changePercent) >= 15 ? .high : .medium,
            timestamp: Date(),
            causes: [cause],
            effects: [hrvChange],
            correlationStrength: calculateCorrelationStrength(activity, hrvChange),
            headline: "训练影响提醒",
            narrative: narrative,
            recommendation: generateActivityRecommendation(hrvChange),
            tags: ["activity", "hrv", activity.type],
            expiresAt: Calendar.current.date(byAdding: .hour, value: 24, to: Date()),
            isRead: false,
            userFeedback: nil
        )
    }
    
    // MARK: - 生活方式影响分析
    
    /// 分析生活方式因素对恢复的影响
    func analyzeLifestyleImpact(
        todayMetrics: DailyMetrics,
        yesterdayJournal: JournalEntry?
    ) -> [InsightItem] {
        
        var insights: [InsightItem] = []
        guard let journal = yesterdayJournal else { return insights }
        guard let baseline = baselineManager.getCurrentBaseline() else { return insights }
        
        // 检测各种生活方式因素
        let lifestyleFactors: [(factor: String, label: String, value: Bool)] = [
            ("alcohol", "饮酒", journal.alcoholConsumed),
            ("late_caffeine", "晚间咖啡因", journal.lateCaffeine),
            ("screen_before_bed", "睡前屏幕", journal.screenBeforeBed),
            ("late_meal", "晚餐过晚", journal.lateMeal)
        ]
        
        for (factor, label, occurred) in lifestyleFactors {
            guard occurred else { continue }
            
            // 检查睡眠质量下降
            let sleepChange = calculateSleepChange(today: todayMetrics.sleep, baseline: baseline)
            
            if sleepChange.changeDirection == "down" && abs(sleepChange.changePercent) >= 10 {
                let cause = CausalEvidence(
                    factor: factor,
                    factorLabel: label,
                    timestamp: journal.date,
                    value: nil,
                    source: "journal"
                )
                
                let narrative = generateLifestyleImpactNarrative(
                    factor: factor,
                    factorLabel: label,
                    sleepChange: sleepChange
                )
                
                insights.append(InsightItem(
                    id: UUID().uuidString,
                    type: .lifestyleImpact,
                    priority: .medium,
                    timestamp: Date(),
                    causes: [cause],
                    effects: [sleepChange],
                    correlationStrength: 0.6,
                    headline: "生活习惯影响",
                    narrative: narrative,
                    recommendation: getLifestyleRecommendation(factor),
                    tags: ["lifestyle", factor, "sleep"],
                    expiresAt: nil,
                    isRead: false,
                    userFeedback: nil
                ))
            }
        }
        
        return insights
    }
    
    // MARK: - 趋势分析
    
    /// 分析多日趋势，预测风险
    func analyzeTrend(last7DaysMetrics: [DailyMetrics]) -> [InsightItem] {
        var insights: [InsightItem] = []
        
        // 检测连续下降趋势
        let hrvTrend = detectTrend(values: last7DaysMetrics.compactMap { $0.hrvRMSSD })
        let sleepTrend = detectTrend(values: last7DaysMetrics.map { $0.sleep.efficiency })
        
        // 连续3天HRV下降
        if hrvTrend.consecutiveDeclines >= 3 {
            insights.append(createTrendWarningInsight(
                metric: "HRV",
                trend: hrvTrend,
                headline: "HRV连续下降",
                narrative: "过去\(hrvTrend.consecutiveDeclines)天HRV持续走低，累计下降\(String(format: "%.1f", hrvTrend.totalChange))%。这可能预示着累积疲劳，建议安排恢复日。"
            ))
        }
        
        // 睡眠效率连续下降
        if sleepTrend.consecutiveDeclines >= 3 {
            insights.append(createTrendWarningInsight(
                metric: "睡眠效率",
                trend: sleepTrend,
                headline: "睡眠质量下滑",
                narrative: "睡眠效率已连续\(sleepTrend.consecutiveDeclines)天下降。检查最近的睡眠习惯是否有变化？"
            ))
        }
        
        return insights
    }
}
```

### 11.4 自然语言生成器

```swift
// MARK: - 洞察文案生成器

class InsightNarrativeGenerator {
    
    // MARK: - 活动影响文案模板
    
    /// 生成活动影响的自然语言描述
    func generateActivityImpactNarrative(
        activity: ActivityRecord,
        hrvChange: MetricChange,
        baseline: PersonalBaseline
    ) -> String {
        
        let activityName = activityTypeLabel(activity.type)
        let timeAgo = formatTimeAgo(activity.endTime)
        let durationText = formatDuration(activity.duration)
        
        // 根据变化幅度选择不同模板
        let changeText: String
        let hrvCurrent = Int(hrvChange.currentValue)
        let hrvBaseline = Int(baseline.hrvRMSSDMean)
        let changePercent = abs(hrvChange.changePercent)
        
        if changePercent >= 20 {
            changeText = "明显下降"
        } else if changePercent >= 10 {
            changeText = "有所下降"
        } else {
            changeText = "略有波动"
        }
        
        // 组合自然语言
        var narrative = "\(timeAgo)你进行了\(durationText)的\(activityName)，"
        narrative += "今天的HRV（\(hrvCurrent)ms）较你的基线（\(hrvBaseline)ms）\(changeText)"
        
        if changePercent >= 10 {
            narrative += "（-\(String(format: "%.0f", changePercent))%）"
        }
        narrative += "。"
        
        // 添加解读
        if changePercent >= 15 {
            narrative += "这表明身体正在恢复中，建议今天以轻度活动为主。"
        } else if changePercent >= 10 {
            narrative += "属于正常的训练反应，注意补充营养和睡眠。"
        }
        
        return narrative
    }
    
    // MARK: - 生活方式影响文案
    
    func generateLifestyleImpactNarrative(
        factor: String,
        factorLabel: String,
        sleepChange: MetricChange
    ) -> String {
        
        let templates: [String: String] = [
            "alcohol": "昨晚的饮酒可能影响了你的睡眠质量，睡眠效率下降了\(String(format: "%.0f", abs(sleepChange.changePercent)))%。酒精会干扰深度睡眠，建议控制饮酒频率。",
            
            "late_caffeine": "晚间摄入的咖啡因似乎影响了入睡，睡眠效率较基线低\(String(format: "%.0f", abs(sleepChange.changePercent)))%。建议下午2点后避免咖啡因。",
            
            "screen_before_bed": "睡前使用屏幕可能延迟了你的入睡时间，今天睡眠效率下降\(String(format: "%.0f", abs(sleepChange.changePercent)))%。尝试睡前1小时放下手机。",
            
            "late_meal": "晚餐时间偏晚可能影响了睡眠质量，效率下降\(String(format: "%.0f", abs(sleepChange.changePercent)))%。建议睡前3小时完成进食。"
        ]
        
        return templates[factor] ?? "检测到\(factorLabel)与睡眠质量下降存在关联。"
    }
    
    // MARK: - HRV趋势文案
    
    func generateHRVTrendNarrative(
        currentHRV: Double,
        baselineHRV: Double,
        zScore: Double,
        trend3Day: Double?,
        trend7Day: Double?
    ) -> String {
        
        var narrative = "今日HRV \(Int(currentHRV))ms，"
        
        // 与基线对比
        let vsBaseline = ((currentHRV - baselineHRV) / baselineHRV) * 100
        if abs(vsBaseline) < 5 {
            narrative += "与你的基线（\(Int(baselineHRV))ms）基本持平。"
        } else if vsBaseline > 0 {
            narrative += "高于基线\(String(format: "%.0f", vsBaseline))%，恢复状态良好！"
        } else {
            narrative += "低于基线\(String(format: "%.0f", abs(vsBaseline)))%。"
        }
        
        // Z分数解读
        if zScore <= -1.5 {
            narrative += "这是一个明显的低值，身体可能需要更多恢复时间。"
        } else if zScore <= -0.5 {
            narrative += "略低于正常范围，注意监测后续变化。"
        } else if zScore >= 1.0 {
            narrative += "状态极佳，是进行高强度训练的好时机！"
        }
        
        // 趋势
        if let d3 = trend3Day, d3 < -5 {
            narrative += "近3天呈下降趋势，建议安排恢复。"
        } else if let d7 = trend7Day, d7 > 5 {
            narrative += "本周整体恢复良好，继续保持！"
        }
        
        return narrative
    }
    
    // MARK: - 睡眠洞察文案
    
    func generateSleepInsightNarrative(
        sleep: SleepMetrics,
        baseline: PersonalBaseline
    ) -> String {
        
        let durationHours = sleep.totalMinutes / 60.0
        let baselineDuration = baseline.sleepDurationMean / 60.0
        
        var narrative = "昨晚睡眠\(String(format: "%.1f", durationHours))小时，"
        
        // 时长对比
        let durationDiff = durationHours - baselineDuration
        if abs(durationDiff) < 0.3 {
            narrative += "与平时相当。"
        } else if durationDiff > 0 {
            narrative += "比平时多睡了\(String(format: "%.1f", durationDiff))小时。"
        } else {
            narrative += "比平时少睡\(String(format: "%.1f", abs(durationDiff)))小时。"
        }
        
        // 睡眠效率
        let effPercent = Int(sleep.efficiency * 100)
        if effPercent >= 90 {
            narrative += "睡眠效率\(effPercent)%，非常高效！"
        } else if effPercent >= 85 {
            narrative += "效率\(effPercent)%，质量不错。"
        } else if effPercent >= 75 {
            narrative += "效率\(effPercent)%，还有提升空间。"
        } else {
            narrative += "效率仅\(effPercent)%，建议检查睡眠环境。"
        }
        
        // 睡眠结构
        let deepRatio = Double(sleep.deepSleepMinutes) / Double(sleep.totalMinutes)
        let remRatio = Double(sleep.remSleepMinutes) / Double(sleep.totalMinutes)
        
        if deepRatio >= 0.20 {
            narrative += "深度睡眠充足（\(Int(deepRatio * 100))%）。"
        } else if deepRatio < 0.13 {
            narrative += "深度睡眠偏少（\(Int(deepRatio * 100))%），可能影响身体恢复。"
        }
        
        return narrative
    }
    
    // MARK: - 综合日报一句话
    
    func generateDailyOneLiner(
        readinessScore: Double,
        hrvStatus: String,
        sleepQuality: String,
        topConcern: String?
    ) -> String {
        
        let templates: [(range: ClosedRange<Double>, texts: [String])] = [
            (80...100, [
                "状态极佳！今天适合挑战高强度训练。",
                "恢复充分，是突破个人记录的好时机！",
                "身体状态在线，尽情享受运动吧！"
            ]),
            (60...79, [
                "状态良好，可以进行正常训练计划。",
                "恢复不错，保持节奏继续前进。",
                "今天状态稳定，适合中等强度训练。"
            ]),
            (40...59, [
                "恢复中等，建议适度降低训练强度。",
                "身体需要更多恢复，今天轻松一点。",
                "注意倾听身体信号，别勉强自己。"
            ]),
            (0...39, [
                "身体发出休息信号，建议安排恢复日。",
                "恢复不足，今天以放松为主。",
                "累积疲劳明显，优先保证睡眠和营养。"
            ])
        ]
        
        for (range, texts) in templates {
            if range.contains(readinessScore) {
                var oneLiner = texts.randomElement()!
                
                // 如果有特别关注点，追加
                if let concern = topConcern {
                    oneLiner += "（\(concern)）"
                }
                
                return oneLiner
            }
        }
        
        return "数据不足，继续佩戴设备获取更多信息。"
    }
    
    // MARK: - 辅助函数
    
    private func activityTypeLabel(_ type: String) -> String {
        let mapping: [String: String] = [
            "basketball": "篮球",
            "running": "跑步",
            "cycling": "骑行",
            "swimming": "游泳",
            "strength": "力量训练",
            "yoga": "瑜伽",
            "hiit": "HIIT",
            "walking": "步行",
            "football": "足球",
            "tennis": "网球"
        ]
        return mapping[type] ?? type
    }
    
    private func formatTimeAgo(_ date: Date) -> String {
        let hours = Int(-date.timeIntervalSinceNow / 3600)
        if hours < 24 {
            return "昨天"
        } else if hours < 48 {
            return "前天"
        } else {
            return "\(hours / 24)天前"
        }
    }
    
    private func formatDuration(_ minutes: Double) -> String {
        let hours = Int(minutes / 60)
        let mins = Int(minutes.truncatingRemainder(dividingBy: 60))
        if hours > 0 {
            return "\(hours)小时\(mins)分钟"
        } else {
            return "\(mins)分钟"
        }
    }
}
```

### 11.5 日报洞察生成器

```swift
// MARK: - 日报洞察生成器

class DailyInsightGenerator {
    
    private let causalAnalyzer: CausalAnalyzer
    private let narrativeGenerator: InsightNarrativeGenerator
    private let dataStore: LocalDataStore
    
    /// 生成今日洞察摘要
    func generateDailyInsights() -> DailyInsightSummary {
        
        // 1. 获取今日和昨日数据
        let today = Date()
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: today)!
        
        guard let todayMetrics = dataStore.getDailyMetrics(for: today),
              let yesterdayData = dataStore.getDailyData(for: yesterday) else {
            return createEmptyDaySummary()
        }
        
        var allInsights: [InsightItem] = []
        
        // 2. 活动影响分析
        let activityInsights = causalAnalyzer.analyzeActivityImpact(
            todayMetrics: todayMetrics,
            yesterdayActivities: yesterdayData.activities
        )
        allInsights.append(contentsOf: activityInsights)
        
        // 3. 生活方式影响分析
        let lifestyleInsights = causalAnalyzer.analyzeLifestyleImpact(
            todayMetrics: todayMetrics,
            yesterdayJournal: yesterdayData.journal
        )
        allInsights.append(contentsOf: lifestyleInsights)
        
        // 4. 趋势分析
        let last7Days = dataStore.getMetricsForLastDays(7)
        let trendInsights = causalAnalyzer.analyzeTrend(last7DaysMetrics: last7Days)
        allInsights.append(contentsOf: trendInsights)
        
        // 5. HRV状态洞察
        if let hrvInsight = generateHRVInsight(todayMetrics: todayMetrics) {
            allInsights.append(hrvInsight)
        }
        
        // 6. 睡眠洞察
        if let sleepInsight = generateSleepInsight(sleep: todayMetrics.sleep) {
            allInsights.append(sleepInsight)
        }
        
        // 7. 排序和筛选
        allInsights.sort { $0.priority.rawValue < $1.priority.rawValue }
        let topInsights = Array(allInsights.prefix(5)) // 最多显示5条
        
        // 8. 生成总体状态
        let (status, emoji) = determineOverallStatus(
            readinessScore: todayMetrics.readinessScore,
            insights: topInsights
        )
        
        // 9. 生成一句话总结
        let oneLiner = narrativeGenerator.generateDailyOneLiner(
            readinessScore: todayMetrics.readinessScore ?? 50,
            hrvStatus: todayMetrics.hrvStatus,
            sleepQuality: todayMetrics.sleepQuality,
            topConcern: topInsights.first?.headline
        )
        
        return DailyInsightSummary(
            date: today,
            overallStatus: status,
            statusEmoji: emoji,
            oneLiner: oneLiner,
            insights: topInsights,
            topRecommendation: topInsights.first?.recommendation
        )
    }
    
    // MARK: - 各类洞察生成
    
    private func generateHRVInsight(todayMetrics: DailyMetrics) -> InsightItem? {
        guard let hrv = todayMetrics.hrvRMSSD,
              let baseline = dataStore.getBaseline() else { return nil }
        
        let zScore = (hrv - baseline.hrvRMSSDMean) / baseline.hrvRMSSDStd
        
        // 只有显著变化才生成洞察
        guard abs(zScore) >= 0.5 else { return nil }
        
        let narrative = narrativeGenerator.generateHRVTrendNarrative(
            currentHRV: hrv,
            baselineHRV: baseline.hrvRMSSDMean,
            zScore: zScore,
            trend3Day: todayMetrics.hrvTrend3Day,
            trend7Day: todayMetrics.hrvTrend7Day
        )
        
        let type: InsightType = zScore > 0 ? .hrvImproved : .hrvDecline
        let priority: InsightPriority = abs(zScore) >= 1.5 ? .high : .medium
        
        return InsightItem(
            id: UUID().uuidString,
            type: type,
            priority: priority,
            timestamp: Date(),
            causes: [],
            effects: [MetricChange(
                metric: "hrv_rmssd",
                metricLabel: "HRV",
                previousValue: baseline.hrvRMSSDMean,
                currentValue: hrv,
                baselineValue: baseline.hrvRMSSDMean,
                changePercent: ((hrv - baseline.hrvRMSSDMean) / baseline.hrvRMSSDMean) * 100,
                changeDirection: zScore > 0 ? "up" : "down",
                significance: abs(zScore) >= 1.5 ? "significant" : "moderate"
            )],
            correlationStrength: 1.0,
            headline: zScore > 0 ? "HRV状态良好" : "HRV下降提醒",
            narrative: narrative,
            recommendation: zScore < -1.0 ? "建议今天以恢复性活动为主，保证充足睡眠。" : nil,
            tags: ["hrv", "recovery"],
            expiresAt: nil,
            isRead: false,
            userFeedback: nil
        )
    }
    
    private func generateSleepInsight(sleep: SleepMetrics) -> InsightItem? {
        guard let baseline = dataStore.getBaseline() else { return nil }
        
        let narrative = narrativeGenerator.generateSleepInsightNarrative(
            sleep: sleep,
            baseline: baseline
        )
        
        // 判断是否需要生成洞察
        let efficiencyDrop = (baseline.sleepEfficiencyMean - sleep.efficiency) / baseline.sleepEfficiencyMean
        let durationDrop = (baseline.sleepDurationMean - Double(sleep.totalMinutes)) / baseline.sleepDurationMean
        
        guard efficiencyDrop >= 0.05 || durationDrop >= 0.1 else {
            // 如果睡眠很好，也生成正面洞察
            if sleep.efficiency >= 0.90 && Double(sleep.totalMinutes) >= baseline.sleepDurationMean {
                return InsightItem(
                    id: UUID().uuidString,
                    type: .sleepQualityImproved,
                    priority: .low,
                    timestamp: Date(),
                    causes: [],
                    effects: [],
                    correlationStrength: 1.0,
                    headline: "睡眠质量优秀",
                    narrative: narrative,
                    recommendation: nil,
                    tags: ["sleep", "positive"],
                    expiresAt: nil,
                    isRead: false,
                    userFeedback: nil
                )
            }
            return nil
        }
        
        return InsightItem(
            id: UUID().uuidString,
            type: .sleepQualityDrop,
            priority: efficiencyDrop >= 0.1 ? .high : .medium,
            timestamp: Date(),
            causes: [],
            effects: [],
            correlationStrength: 1.0,
            headline: "睡眠质量下降",
            narrative: narrative,
            recommendation: "建议检查睡眠环境，保持固定作息时间。",
            tags: ["sleep", "recovery"],
            expiresAt: nil,
            isRead: false,
            userFeedback: nil
        )
    }
    
    private func determineOverallStatus(
        readinessScore: Double?,
        insights: [InsightItem]
    ) -> (status: String, emoji: String) {
        
        let score = readinessScore ?? 50
        let hasCritical = insights.contains { $0.priority == .critical }
        let hasHigh = insights.contains { $0.priority == .high }
        
        if hasCritical || score < 30 {
            return ("warning", "🔴")
        } else if hasHigh || score < 50 {
            return ("attention", "🟠")
        } else if score < 70 {
            return ("good", "🟡")
        } else {
            return ("optimal", "🟢")
        }
    }
}
```

### 11.6 洞察UI展示示例

```swift
// MARK: - SwiftUI 洞察卡片

struct InsightCardView: View {
    let insight: InsightItem
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 标题行
            HStack {
                priorityBadge
                Text(insight.headline)
                    .font(.headline)
                    .fontWeight(.semibold)
                Spacer()
                Text(timeAgo)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // 主文案 (自然语言)
            Text(insight.narrative)
                .font(.body)
                .foregroundColor(.primary)
                .lineSpacing(4)
            
            // 因果关联 (如果有)
            if !insight.causes.isEmpty {
                HStack(spacing: 8) {
                    ForEach(insight.causes, id: \.factor) { cause in
                        CauseBadge(cause: cause)
                    }
                    Image(systemName: "arrow.right")
                        .foregroundColor(.secondary)
                    ForEach(insight.effects, id: \.metric) { effect in
                        EffectBadge(effect: effect)
                    }
                }
                .font(.caption)
            }
            
            // 建议 (如果有)
            if let recommendation = insight.recommendation {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "lightbulb.fill")
                        .foregroundColor(.yellow)
                    Text(recommendation)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(cardBackground)
        .cornerRadius(16)
    }
    
    private var priorityBadge: some View {
        let (color, icon) = priorityStyle
        return Image(systemName: icon)
            .foregroundColor(color)
    }
    
    private var priorityStyle: (Color, String) {
        switch insight.priority {
        case .critical: return (.red, "exclamationmark.triangle.fill")
        case .high: return (.orange, "exclamationmark.circle.fill")
        case .medium: return (.yellow, "info.circle.fill")
        case .low: return (.green, "checkmark.circle.fill")
        }
    }
    
    private var cardBackground: Color {
        switch insight.priority {
        case .critical: return Color.red.opacity(0.1)
        case .high: return Color.orange.opacity(0.1)
        default: return Color(.systemBackground)
        }
    }
    
    private var timeAgo: String {
        // 简化时间显示
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter.localizedString(for: insight.timestamp, relativeTo: Date())
    }
}

struct CauseBadge: View {
    let cause: CausalEvidence
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: iconForFactor(cause.factor))
            Text(cause.factorLabel)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color.blue.opacity(0.15))
        .cornerRadius(8)
    }
    
    private func iconForFactor(_ factor: String) -> String {
        switch factor {
        case "basketball": return "basketball"
        case "running": return "figure.run"
        case "alcohol": return "wineglass"
        case "late_caffeine": return "cup.and.saucer"
        case "screen_before_bed": return "iphone"
        default: return "circle.fill"
        }
    }
}

struct EffectBadge: View {
    let effect: MetricChange
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: effect.changeDirection == "down" ? "arrow.down" : "arrow.up")
            Text("\(effect.metricLabel) \(String(format: "%.0f", abs(effect.changePercent)))%")
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(effect.changeDirection == "down" ? Color.red.opacity(0.15) : Color.green.opacity(0.15))
        .cornerRadius(8)
    }
}

// MARK: - 日报洞察页面

struct DailyInsightsView: View {
    @StateObject private var viewModel = DailyInsightsViewModel()
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // 顶部状态卡片
                StatusHeaderCard(summary: viewModel.summary)
                
                // 一句话总结
                Text(viewModel.summary.oneLiner)
                    .font(.title3)
                    .fontWeight(.medium)
                    .padding(.horizontal)
                
                // 洞察列表
                ForEach(viewModel.summary.insights) { insight in
                    InsightCardView(insight: insight)
                        .padding(.horizontal)
                }
                
                // 如果没有洞察
                if viewModel.summary.insights.isEmpty {
                    EmptyInsightsView()
                }
            }
            .padding(.vertical)
        }
        .navigationTitle("今日洞察")
        .onAppear {
            viewModel.loadInsights()
        }
    }
}

struct StatusHeaderCard: View {
    let summary: DailyInsightSummary
    
    var body: some View {
        HStack {
            Text(summary.statusEmoji)
                .font(.system(size: 48))
            
            VStack(alignment: .leading) {
                Text(statusText)
                    .font(.headline)
                Text(Date(), style: .date)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding()
        .background(statusBackgroundColor.opacity(0.2))
        .cornerRadius(16)
        .padding(.horizontal)
    }
    
    private var statusText: String {
        switch summary.overallStatus {
        case "optimal": return "状态极佳"
        case "good": return "状态良好"
        case "attention": return "需要关注"
        case "warning": return "注意休息"
        default: return "数据收集中"
        }
    }
    
    private var statusBackgroundColor: Color {
        switch summary.overallStatus {
        case "optimal": return .green
        case "good": return .yellow
        case "attention": return .orange
        case "warning": return .red
        default: return .gray
        }
    }
}
```

### 11.7 洞察触发规则汇总

| 规则ID | 触发条件 | 洞察类型 | 优先级 | 文案示例 |
|--------|---------|---------|--------|---------|
| `ACT_HRV_01` | 昨日高强度活动 + 今日HRV下降≥10% | `activity_impact` | High | "昨天的篮球训练后，今天HRV较基线下降15%..." |
| `ACT_HRV_02` | 昨日运动 + 今日HRV上升 | `recovery_optimal` | Low | "昨天的轻度跑步后恢复良好，HRV已回升至基线..." |
| `LIFE_SLP_01` | 昨日饮酒 + 睡眠效率下降≥10% | `lifestyle_impact` | Medium | "昨晚的饮酒可能影响了睡眠质量..." |
| `LIFE_SLP_02` | 睡前屏幕 + 入睡时间延迟 | `sleep_habit_impact` | Medium | "睡前使用屏幕可能延迟了入睡时间..." |
| `TRD_HRV_01` | HRV连续3天下降 | `trend_warning` | High | "过去3天HRV持续走低，建议安排恢复日..." |
| `TRD_SLP_01` | 睡眠效率连续下滑 | `trend_warning` | Medium | "睡眠效率已连续4天下降..." |
| `LOAD_HIGH` | ACWR ≥ 1.3 | `training_load_high` | High | "训练负荷偏高，ACWR达到1.4..." |
| `LOAD_LOW` | ACWR ≤ 0.6 持续3天 | `detraining` | Medium | "训练负荷过低，可能影响适应效果..." |
| `CONF_01` | 主观疲劳高 + 客观指标正常 | `subjective_objective_conflict` | Medium | "虽然HRV正常，但主观感觉疲劳..." |
| `REC_OPT` | Readiness ≥ 80 | `recovery_optimal` | Low | "恢复充分，今天适合挑战高强度！" |

</details>

---

### 11.4 洞察生成与展示

> 基于 `CausalEngine` 的输出生成自然语言洞察。

```swift
// MARK: - 洞察生成器

class InsightGenerator {
    
    private let causalEngine: CausalEngine
    private let narrativeGen: NarrativeGenerator
    
    init(causalEngine: CausalEngine) {
        self.causalEngine = causalEngine
        self.narrativeGen = NarrativeGenerator()
    }
    
    // MARK: - 日报一句话洞察 (最常用场景)
    
    /// 生成日报洞察 - 用于首页展示一句话
    func generateDailyOneLiner(recentData: [DailyData]) -> OneLinerInsight? {
        
        // 调用统一因果引擎
        let result = causalEngine.analyze(data: recentData, period: .daily)
        
        // 取最显著的相关性
        guard let top = result.correlations.first(where: { $0.isSignificant }) else {
            return nil
        }
        
        // 生成文案
        return narrativeGen.generateOneLiner(correlation: top)
    }
    
    // MARK: - 周报洞察列表
    
    /// 生成周报洞察 - 返回多条供周报使用
    func generateWeeklyInsights(weekData: [DailyData]) -> [InsightItem] {
        
        let result = causalEngine.analyze(data: weekData, period: .weekly)
        
        return result.correlations
            .filter { $0.isSignificant }
            .prefix(5)  // 最多5条
            .map { correlation in
                InsightItem(
                    id: UUID().uuidString,
                    period: .weekly,
                    correlation: correlation,
                    narrative: narrativeGen.generateNarrative(correlation: correlation),
                    generatedAt: Date()
                )
            }
    }
}

// MARK: - 自然语言生成器

class NarrativeGenerator {
    
    private let localLLM: LocalLLMEngine?
    
    init() {
        self.localLLM = try? LocalLLMEngine()
    }
    
    /// 生成一句话洞察
    func generateOneLiner(correlation: DiscoveredCorrelation) -> OneLinerInsight {
        
        // 确定方向
        let direction = correlation.difference > 0 ? "上升" : "下降"
        let absChange = abs(correlation.difference)
        
        // 优先使用小模型
        if let llm = localLLM {
            let prompt = buildPrompt(correlation: correlation)
            let response = llm.generate(prompt: prompt, maxTokens: 100)
            return parseOneLinerResponse(response, correlation: correlation)
        }
        
        // 回退到模板
        return OneLinerInsight(
            headline: "📊 发现关联",
            body: "你\(correlation.causeLabel)后，\(effectLabel(correlation.effectKey))平均\(direction)\(String(format: "%.1f", absChange))%。",
            recommendation: generateRecommendation(correlation: correlation),
            priority: correlation.significance >= 0.7 ? 1 : 2
        )
    }
    
    /// 生成完整文案 (周报用)
    func generateNarrative(correlation: DiscoveredCorrelation) -> String {
        
        let direction = correlation.difference > 0 ? "上升" : "下降"
        let absChange = abs(correlation.difference)
        
        return """
        分析发现，当你\(correlation.causeLabel)时，次日\(effectLabel(correlation.effectKey))平均\(direction)\(String(format: "%.1f", absChange))%。\
        这一关联基于\(correlation.sampleSize)次观察，统计显著性为\(String(format: "%.0f", correlation.significance * 100))%。
        """
    }
    
    private func effectLabel(_ key: String) -> String {
        switch key {
        case "hrv_change": return "HRV"
        case "sleep_efficiency_change": return "睡眠效率"
        case "sleep_duration_change": return "睡眠时长"
        case "readiness_score": return "准备度"
        default: return key
        }
    }
    
    private func generateRecommendation(correlation: DiscoveredCorrelation) -> String? {
        if correlation.effectKey == "hrv_change" && correlation.difference < -5 {
            return "建议今天安排轻度恢复活动"
        }
        if correlation.effectKey == "sleep_efficiency_change" && correlation.difference < -10 {
            return "注意调整睡前习惯"
        }
        return nil
    }
}
```

#### 使用示例

```swift
// 任何需要洞察的地方
class HomeViewController {
    
    let insightGenerator: InsightGenerator
    
    func loadDailyInsight() {
        let recentData = dataStore.getRecentDays(count: 3)
        
        if let oneLiner = insightGenerator.generateDailyOneLiner(recentData: recentData) {
            // 显示一句话洞察
            insightLabel.text = oneLiner.body
            recommendationLabel.text = oneLiner.recommendation
        }
    }
}

// 周报提交时
class WeeklyReportService {
    
    let insightGenerator: InsightGenerator
    
    func prepareWeeklyReport(weekData: [DailyData]) -> WeeklyReportPayload {
        
        let insights = insightGenerator.generateWeeklyInsights(weekData: weekData)
        
        return WeeklyReportPayload(
            // ... 其他数据 ...
            causalInsights: insights
        )
    }
}
```

---

### 11.5 趋势图表展示规范

> 适用于仪表盘和周报的趋势图表渲染。

#### 图表类型枚举

```swift
enum ChartType: String, Codable {
    case line = "line"                    // 折线图 (HRV, 睡眠时长, 准备度)
    case bar = "bar"                      // 柱状图 (训练负荷AU)
    case stackedBar = "stacked_bar"       // 堆叠柱状图 (睡眠结构)
    case multiAxisLine = "multi_axis_line" // 双轴折线图 (准备度vs HRV)
    case radar = "radar"                  // 雷达图 (Hooper主观评分)
    case timeline = "timeline"            // 时间线 (生活方式事件)
}
```

#### 图表数据规范

```swift
/// 通用图表数据结构
struct ChartData: Codable {
    let chartId: String               // 图表标识
    let chartType: ChartType          // 图表类型
    let title: String                 // 标题
    let dates: [String]               // X轴日期 ["2025-12-01", ...]
    let series: [ChartSeries]         // 数据系列
    let baseline: [String: Double]?   // 基线值 (可选)
    let thresholds: [String: ChartThreshold]? // 阈值/安全区间 (可选)
    let notes: String?                // 图表说明
}

struct ChartSeries: Codable {
    let name: String                  // 系列名称
    let key: String                   // 数据key
    let type: String                  // "line", "bar"
    let data: [Double?]               // 数据点 (null表示缺失)
    let yAxisIndex: Int?              // 双轴时指定Y轴
    let smooth: Bool?                 // 是否平滑
    let stack: String?                // 堆叠组名
}

struct ChartThreshold: Codable {
    let low: Double?                  // 下限
    let high: Double?                 // 上限
}
```

#### 标准图表清单

| 图表ID | 类型 | 数据来源 | 用途 | 渲染建议 |
|--------|------|---------|------|---------|
| `readiness_trend` | line | readiness_score | 准备度7天趋势 | 平滑曲线，参考区间70-100 |
| `readiness_vs_hrv` | multiAxisLine | readiness + hrv_rmssd | 准备度与HRV对比 | 双Y轴，颜色区分 |
| `hrv_trend` | line | hrv_rmssd | HRV 28天趋势 | 显示基线虚线 |
| `sleep_duration` | line | sleep_duration_hours | 睡眠时长趋势 | 显示基线虚线 |
| `sleep_structure` | stackedBar | deep/rem/light | 睡眠结构 | 堆叠显示三种睡眠阶段 |
| `training_load` | bar | daily_au | 训练负荷 | 柱状图，过滤>2000异常值 |
| `hooper_radar` | radar | hooper scores | 主观疲劳雷达 | 四维雷达图 |
| `lifestyle_timeline` | timeline | lifestyle_events | 生活事件标注 | 时间线+标签 |

#### SwiftUI 图表渲染示例

```swift
import Charts

struct ReadinessTrendChart: View {
    let chartData: ChartData
    
    var body: some View {
        Chart {
            ForEach(Array(chartData.dates.enumerated()), id: \.offset) { index, date in
                if let value = chartData.series.first?.data[index] {
                    LineMark(
                        x: .value("日期", date),
                        y: .value("准备度", value)
                    )
                    .interpolationMethod(.catmullRom) // 平滑曲线
                    .foregroundStyle(.blue)
                }
            }
            
            // 参考区间
            if let threshold = chartData.thresholds?["readiness_score"] {
                RectangleMark(
                    yStart: .value("", threshold.low ?? 70),
                    yEnd: .value("", threshold.high ?? 100)
                )
                .foregroundStyle(.green.opacity(0.1))
            }
            
            // 基线
            if let baseline = chartData.baseline?["readiness_score"] {
                RuleMark(y: .value("基线", baseline))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 5]))
                    .foregroundStyle(.gray)
            }
        }
        .chartYScale(domain: 0...100)
        .frame(height: 200)
    }
}

// 双轴图表
struct ReadinessHRVComboChart: View {
    let chartData: ChartData
    
    var body: some View {
        Chart {
            // 准备度 (左Y轴)
            ForEach(Array(chartData.dates.enumerated()), id: \.offset) { index, date in
                if let series = chartData.series.first(where: { $0.key == "readiness_score" }),
                   let value = series.data[index] {
                    LineMark(
                        x: .value("日期", date),
                        y: .value("准备度", value)
                    )
                    .foregroundStyle(.blue)
                }
            }
            
            // HRV (右Y轴 - 需要归一化或使用双轴库)
            ForEach(Array(chartData.dates.enumerated()), id: \.offset) { index, date in
                if let series = chartData.series.first(where: { $0.key == "hrv_rmssd" }),
                   let value = series.data[index] {
                    LineMark(
                        x: .value("日期", date),
                        y: .value("HRV", value)
                    )
                    .foregroundStyle(.orange)
                }
            }
        }
        .chartLegend(position: .bottom)
    }
}
```

#### 图表构建器 (复用CausalEngine数据)

```swift
class ChartBuilder {
    
    /// 从CausalAnalysisResult构建相关性图表
    static func buildCorrelationChart(
        result: CausalAnalysisResult,
        topN: Int = 5
    ) -> ChartData {
        
        let topCorrelations = Array(result.correlations.prefix(topN))
        
        return ChartData(
            chartId: "causal_correlations",
            chartType: .bar,
            title: "发现的因果关联",
            dates: topCorrelations.map { $0.causeLabel },
            series: [
                ChartSeries(
                    name: "影响强度",
                    key: "significance",
                    type: "bar",
                    data: topCorrelations.map { $0.significance * 100 },
                    yAxisIndex: nil,
                    smooth: nil,
                    stack: nil
                )
            ],
            baseline: nil,
            thresholds: ["significance": ChartThreshold(low: 50, high: nil)],
            notes: "显著性≥50%的关联"
        )
    }
}
```

---

### 11.6 通用因果发现原则 (已整合到11.3)

> ⚠️ **注意**: 以下内容已整合到 **11.3 CausalEngine 核心实现** 中，此处保留原设计文档供参考。

#### 设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│                      通用因果发现原则                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ❌ 错误做法 (写死)                                              │
│  if journal.alcoholConsumed { ... }  // 只能识别预设字段        │
│                                                                  │
│  ✅ 正确做法 (通用)                                              │
│  for field in journal.allFields {    // 任何有值字段都参与      │
│      if field.hasValue { analyzeCorrelation(field) }            │
│  }                                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        通用因果发现系统                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Step 1: 收集所有"因" (通用扫描)                                       │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│   │ 运动记录       │  │ Journal记录    │  │ SDK数据        │           │
│   │ (任意类型)     │  │ (任意字段)     │  │ (任意指标)     │           │
│   └───────┬────────┘  └───────┬────────┘  └───────┬────────┘           │
│           └───────────────────┴───────────────────┘                     │
│                               │                                          │
│   Step 2: 收集所有"果" (指标变化)                                       │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│   │ HRV变化        │  │ 睡眠变化       │  │ 准备度变化     │           │
│   └───────┬────────┘  └───────┬────────┘  └───────┬────────┘           │
│           └───────────────────┴───────────────────┘                     │
│                               │                                          │
│   Step 3: 统计相关性分析                                                │
│   计算每个"因"出现后，各个"果"的平均变化                               │
│   与无该"因"时对比，发现显著关联                                        │
│                               │                                          │
│   Step 4: 小模型生成文案                                                │
│   将发现的相关性用自然语言描述                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 核心代码实现

```swift
// MARK: - 通用因果发现系统

class UniversalCausalDiscovery {
    
    private let dataStore: LocalDataStore
    private let localLLM: LocalLLMEngine
    
    // MARK: - 主入口 (支持多周期)
    
    /// 日报洞察 (1-3天因果)
    func discoverDailyInsights() async -> [Insight] {
        return await discoverInsights(period: .daily, lookbackDays: 3)
    }
    
    /// 周报洞察 (7天模式)
    func discoverWeeklyInsights() async -> [Insight] {
        return await discoverInsights(period: .weekly, lookbackDays: 7)
    }
    
    /// 月报洞察 (28天趋势)
    func discoverMonthlyInsights() async -> [Insight] {
        return await discoverInsights(period: .monthly, lookbackDays: 28)
    }
    
    private func discoverInsights(period: AnalysisPeriod, lookbackDays: Int) async -> [Insight] {
        
        let data = dataStore.getDataForLastDays(lookbackDays)
        guard let baseline = dataStore.getBaseline() else { return [] }
        
        // Step 1: 收集所有"因"
        let allCauses = collectAllCauses(data: data)
        
        // Step 2: 收集所有"果"
        let allEffects = collectAllEffects(data: data, baseline: baseline)
        
        // Step 3: 发现相关性
        let correlations = discoverCorrelations(causes: allCauses, effects: allEffects)
        
        // Step 4: 生成洞察 (用小模型)
        var insights: [Insight] = []
        for correlation in correlations.filter({ $0.isSignificant }) {
            let narrative = await generateNarrativeWithLLM(correlation: correlation, period: period)
            insights.append(Insight(
                id: UUID().uuidString,
                period: period,
                correlation: correlation,
                narrative: narrative,
                generatedAt: Date()
            ))
        }
        
        return insights
    }
    
    // MARK: - Step 1: 通用收集"因"
    
    private func collectAllCauses(data: [DailyData]) -> [CauseRecord] {
        
        var causes: [CauseRecord] = []
        
        for (dayIndex, day) in data.enumerated() {
            let daysAgo = dayIndex + 1
            
            // === 运动记录 (任意类型，不写死) ===
            for activity in day.activities {
                causes.append(CauseRecord(
                    category: "activity",
                    key: activity.type,              // 运动类型作为key
                    label: activity.type,            // 显示名称
                    value: activity.trainingLoad,    // 数值
                    date: day.date,
                    daysAgo: daysAgo,
                    metadata: [
                        "duration": activity.duration,
                        "intensity": activity.intensity
                    ]
                ))
            }
            
            // === Journal记录 (通用扫描，任意字段) ===
            if let journal = day.journal {
                let journalCauses = extractAllJournalFields(journal: journal, daysAgo: daysAgo)
                causes.append(contentsOf: journalCauses)
            }
        }
        
        return causes
    }
    
    /// 通用Journal字段提取 - 不写死具体字段名
    private func extractAllJournalFields(journal: JournalEntry, daysAgo: Int) -> [CauseRecord] {
        
        var causes: [CauseRecord] = []
        
        // Journal转为字典，遍历所有字段
        let journalDict = journal.toDictionary()
        
        for (key, value) in journalDict {
            
            // 跳过空值和元数据字段
            guard !isEmptyValue(value),
                  !isMetadataField(key) else { continue }
            
            causes.append(CauseRecord(
                category: "journal",
                key: key,                             // 字段名作为key
                label: FieldLabelConfig.shared.getLabel(for: key),
                value: normalizeValue(value),
                date: journal.date,
                daysAgo: daysAgo,
                metadata: ["raw_value": "\(value)"]
            ))
        }
        
        return causes
    }
    
    /// 判断是否为空值
    private func isEmptyValue(_ value: Any) -> Bool {
        if let boolValue = value as? Bool { return !boolValue }
        if let stringValue = value as? String { return stringValue.isEmpty }
        if let arrayValue = value as? [Any] { return arrayValue.isEmpty }
        return false
    }
    
    /// 元数据字段 (不参与因果分析)
    private func isMetadataField(_ key: String) -> Bool {
        return ["id", "date", "created_at", "updated_at", "user_id"].contains(key)
    }
    
    /// 统一值为数值
    private func normalizeValue(_ value: Any) -> Double {
        if let d = value as? Double { return d }
        if let i = value as? Int { return Double(i) }
        if let b = value as? Bool { return b ? 1.0 : 0.0 }
        return 1.0  // 其他类型表示"存在"
    }
    
    // MARK: - Step 2: 收集"果"
    
    private func collectAllEffects(data: [DailyData], baseline: PersonalBaseline) -> [EffectRecord] {
        
        var effects: [EffectRecord] = []
        
        for day in data {
            guard let metrics = day.metrics else { continue }
            
            // HRV变化
            if let hrv = metrics.hrvRMSSD {
                let change = ((hrv - baseline.hrvRMSSDMean) / baseline.hrvRMSSDMean) * 100
                effects.append(EffectRecord(
                    key: "hrv_change",
                    value: change,
                    date: day.date
                ))
            }
            
            // 睡眠效率变化
            let sleepEffChange = ((metrics.sleep.efficiency - baseline.sleepEfficiencyMean) 
                                  / baseline.sleepEfficiencyMean) * 100
            effects.append(EffectRecord(key: "sleep_efficiency_change", value: sleepEffChange, date: day.date))
            
            // 睡眠时长变化
            let durationChange = ((Double(metrics.sleep.totalMinutes) - baseline.sleepDurationMean) 
                                  / baseline.sleepDurationMean) * 100
            effects.append(EffectRecord(key: "sleep_duration_change", value: durationChange, date: day.date))
            
            // 准备度
            if let readiness = metrics.readinessScore {
                effects.append(EffectRecord(key: "readiness_score", value: readiness, date: day.date))
            }
        }
        
        return effects
    }
    
    // MARK: - Step 3: 发现相关性 (核心算法)
    
    private func discoverCorrelations(
        causes: [CauseRecord],
        effects: [EffectRecord]
    ) -> [DiscoveredCorrelation] {
        
        var correlations: [DiscoveredCorrelation] = []
        
        // 按cause的key分组
        let causesByKey = Dictionary(grouping: causes) { $0.key }
        let effectsByKey = Dictionary(grouping: effects) { $0.key }
        
        // 对每种cause，分析与各种effect的关系
        for (causeKey, causeRecords) in causesByKey {
            let causeDates = Set(causeRecords.map { $0.date })
            
            for (effectKey, effectRecords) in effectsByKey {
                
                // 分组: 有cause时的effect vs 无cause时的effect
                var effectsWithCause: [Double] = []
                var effectsWithoutCause: [Double] = []
                
                for effect in effectRecords {
                    // 检查前1-2天是否有该cause
                    let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: effect.date)!
                    let dayBefore = Calendar.current.date(byAdding: .day, value: -2, to: effect.date)!
                    
                    if causeDates.contains(yesterday) || causeDates.contains(dayBefore) {
                        effectsWithCause.append(effect.value)
                    } else {
                        effectsWithoutCause.append(effect.value)
                    }
                }
                
                // 样本量检查
                guard effectsWithCause.count >= 3, effectsWithoutCause.count >= 3 else { continue }
                
                // 计算差异
                let avgWith = effectsWithCause.reduce(0, +) / Double(effectsWithCause.count)
                let avgWithout = effectsWithoutCause.reduce(0, +) / Double(effectsWithoutCause.count)
                let difference = avgWith - avgWithout
                
                // 计算显著性 (Cohen's d)
                let pooledStd = calculatePooledStd(effectsWithCause, effectsWithoutCause)
                let effectSize = pooledStd > 0 ? abs(difference) / pooledStd : 0
                let significance = min(effectSize / 0.8, 1.0)
                
                guard significance >= 0.3 else { continue }
                
                correlations.append(DiscoveredCorrelation(
                    causeKey: causeKey,
                    causeLabel: causeRecords.first?.label ?? causeKey,
                    effectKey: effectKey,
                    avgEffectWithCause: avgWith,
                    avgEffectWithoutCause: avgWithout,
                    difference: difference,
                    significance: significance,
                    sampleSize: effectsWithCause.count,
                    isSignificant: significance >= 0.5
                ))
            }
        }
        
        return correlations.sorted { $0.significance > $1.significance }
    }
    
    // MARK: - Step 4: 小模型生成文案
    
    private func generateNarrativeWithLLM(
        correlation: DiscoveredCorrelation,
        period: AnalysisPeriod
    ) async -> String {
        
        let periodText = switch period {
            case .daily: "近几天"
            case .weekly: "本周"
            case .monthly: "本月"
        }
        
        let directionText = correlation.difference > 0 ? "上升" : "下降"
        
        let prompt = """
        你是健康数据分析师，请根据发现的数据相关性生成一段简洁的洞察文案。
        
        发现的相关性:
        - 因素: \(correlation.causeLabel)
        - 影响: \(correlation.effectKey) \(directionText)
        - 有该因素时平均值: \(String(format: "%.1f", correlation.avgEffectWithCause))
        - 无该因素时平均值: \(String(format: "%.1f", correlation.avgEffectWithoutCause))
        - 差异: \(String(format: "%.1f", abs(correlation.difference)))
        - 相关强度: \(String(format: "%.0f", correlation.significance * 100))%
        - 时间范围: \(periodText)
        
        要求:
        1. 用"你"称呼用户
        2. 说明发现了什么规律
        3. 给出1条具体建议
        4. 控制在80字以内
        5. 语气友好
        
        洞察文案:
        """
        
        do {
            return try await localLLM.generate(prompt: prompt)
        } catch {
            // 降级到模板
            let dir = correlation.difference > 0 ? "提高" : "降低"
            return "发现规律：当有\"\(correlation.causeLabel)\"时，\(correlation.effectKey)会\(dir)约\(String(format: "%.0f", abs(correlation.difference)))%。"
        }
    }
}
```

#### 数据模型

```swift
// MARK: - 因果发现数据模型

enum AnalysisPeriod {
    case daily    // 1-3天
    case weekly   // 7天
    case monthly  // 28天
}

struct CauseRecord {
    let category: String         // "activity", "journal", "sdk"
    let key: String              // 唯一标识 (字段名/运动类型)
    let label: String            // 显示名称
    let value: Double            // 数值化的值
    let date: Date
    let daysAgo: Int
    let metadata: [String: Any]
}

struct EffectRecord {
    let key: String              // "hrv_change", "sleep_efficiency_change"
    let value: Double            // 变化百分比
    let date: Date
}

struct DiscoveredCorrelation {
    let causeKey: String
    let causeLabel: String
    let effectKey: String
    let avgEffectWithCause: Double
    let avgEffectWithoutCause: Double
    let difference: Double
    let significance: Double     // 0-1, ≥0.5为显著
    let sampleSize: Int
    let isSignificant: Bool
}

struct Insight: Identifiable {
    let id: String
    let period: AnalysisPeriod
    let correlation: DiscoveredCorrelation
    let narrative: String        // 小模型生成的文案
    let generatedAt: Date
}
```

#### 字段显示名称配置 (可扩展)

```swift
// MARK: - 字段名称配置 (支持动态扩展)

class FieldLabelConfig {
    
    static let shared = FieldLabelConfig()
    
    /// 字段名 → 显示名称 (可从云端更新)
    private var labelMap: [String: String] = [
        // 预设常见字段
        "alcohol_consumed": "饮酒",
        "late_caffeine": "晚间咖啡因",
        "screen_before_bed": "睡前屏幕",
        "late_meal": "晚餐过晚",
        "hooper_fatigue": "疲劳感",
        "hooper_stress": "压力感",
        "hooper_soreness": "肌肉酸痛",
        "hooper_sleep": "主观睡眠",
        "is_sick": "身体不适",
        "is_traveling": "出差旅行",
        // ... 新字段会自动使用key作为显示名
    ]
    
    func getLabel(for key: String) -> String {
        return labelMap[key] ?? formatKeyAsLabel(key)
    }
    
    /// 从云端更新配置
    func updateFromCloud(_ newLabels: [String: String]) {
        labelMap.merge(newLabels) { _, new in new }
    }
    
    /// snake_case → 可读文本
    private func formatKeyAsLabel(_ key: String) -> String {
        return key.replacingOccurrences(of: "_", with: " ").capitalized
    }
}
```

#### 相关性发现示例

| 周期 | 发现的因 | 发现的果 | 强度 | 小模型生成文案 |
|------|---------|---------|------|---------------|
| 日报 | `running` | HRV -8% | 65% | "发现你跑步后，第二天HRV通常下降约8%。这是正常的训练反应，跑步后注意补充休息。" |
| 日报 | `alcohol_consumed` | 睡眠效率 -12% | 78% | "你喝酒后睡眠效率平均下降12%。如果明天有重要事，今晚可以少喝点。" |
| 周报 | `meditation` (新增字段) | HRV +5% | 52% | "有意思：你冥想后HRV会略微提升。坚持下去应该会有帮助。" |
| 周报 | `work_overtime` (自定义) | 准备度 -15 | 71% | "加班和准备度下降有关联，加班后准备度平均低15分。注意工作平衡哦。" |
| 月报 | 连续高强度训练模式 | HRV周趋势↓ | 82% | "本月有几次连续3天高强度训练后HRV下降。身体需要恢复周期。" |
| 月报 | 周末效应 | 周一HRV↓ | 68% | "发现规律：周六有饮酒的周末，周一HRV通常偏低。" |

#### 核心特性

| 特性 | 说明 |
|------|------|
| **通用性** | 不写死字段，任何有值记录都参与 |
| **自动发现** | 统计分析自动发现因果关联 |
| **多周期** | 日报(1-3天) / 周报(7天) / 月报(28天) |
| **可扩展** | Journal新增字段自动参与分析 |
| **小模型文案** | 用本地LLM生成自然语言 |
| **显著性过滤** | Cohen's d ≥ 0.5 才输出 |

---

## 十二、AI Coach 系统 (本地LLM + RAG)

> 参考WHOOP Coach，实现本地AI教练功能。支持离线问答，结合用户数据+知识库进行个性化推理。

### 12.1 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Coach 系统架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         iOS 本地层                                   │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                      │    │
│  │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │    │
│  │   │  用户数据层   │    │   RAG引擎    │    │  本地LLM     │          │    │
│  │   │              │    │              │    │              │          │    │
│  │   │ • HRV历史    │    │ • 向量检索   │    │ • Phi-3-mini │          │    │
│  │   │ • 睡眠记录   │───▶│ • 知识匹配   │───▶│ • Gemma 2B   │          │    │
│  │   │ • 训练记录   │    │ • 上下文构建 │    │ • Llama 3.2  │          │    │
│  │   │ • 洞察历史   │    │              │    │   (1B/3B)    │          │    │
│  │   └──────────────┘    └──────────────┘    └──────────────┘          │    │
│  │                              │                   │                  │    │
│  │   ┌──────────────────────────┴───────────────────┴───────────┐      │    │
│  │   │                    Prompt 组装器                          │      │    │
│  │   │  [系统提示] + [用户数据摘要] + [RAG知识] + [用户问题]     │      │    │
│  │   └──────────────────────────────────────────────────────────┘      │    │
│  │                              │                                      │    │
│  │                              ▼                                      │    │
│  │                       响应生成 & 后处理                             │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                      │
│                                      │ (复杂问题/云端增强)                  │
│                                      ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         云端服务 (可选)                              │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  • GPT-4o / Claude 备选 (复杂问题)                                  │    │
│  │  • 知识库更新推送 (论文/规则)                                       │    │
│  │  • 调用次数限制管理                                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 与WHOOP Coach对比

| 维度 | WHOOP Coach | 我们的方案 | 优势 |
|------|------------|-----------|------|
| **模型** | 云端 GPT-4 | 本地小模型 + 云端备选 | 离线可用，成本低 |
| **知识库** | OpenAI训练数据 | 本地RAG (论文/书籍) | 知识可控，可持续更新 |
| **用户数据** | 云端处理 | 本地处理 | 隐私保护 |
| **更新方式** | 依赖OpenAI | 我们主动推送 | 自主可控 |
| **离线能力** | ❌ 需联网 | ✅ 支持离线 | 用户体验好 |
| **成本** | 高 (API调用) | 低 (本地推理) | 可规模化 |

### 12.3 核心推理流程

用户问题 + 用户数据 + RAG知识 = 个性化回答

```
用户问: "今天适合高强度训练吗?"
                ↓
┌─────────────────────────────────────────────────────────────────┐
│                        Prompt 组装                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [系统提示] 你是AI健康教练...                                    │
│                                                                  │
│  [用户数据] ← 从本地数据库实时读取                               │
│  • 今日HRV: 48ms (基线62ms, 下降22%)                            │
│  • 昨晚睡眠: 5.5小时，效率72%                                   │
│  • 准备度: 45分                                                 │
│  • 昨日训练: 篮球1.5小时                                        │
│  • ACWR: 1.4 (偏高)                                             │
│                                                                  │
│  [RAG知识] ← 向量检索相关论文/书籍片段                           │
│  • "HRV下降超过15%时,建议避免高强度训练" (ACSM 2023)            │
│  • "ACWR>1.3时过度训练风险增加" (Gabbett 2016)                  │
│  • "睡眠不足会降低运动表现和恢复能力" (睡眠科学)                │
│                                                                  │
│  [用户问题] 今天适合高强度训练吗?                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                ↓
┌─────────────────────────────────────────────────────────────────┐
│  LLM推理输出 (结合数据+知识)                                     │
│                                                                  │
│  "根据你今天的状态，不建议进行高强度训练。                       │
│                                                                  │
│   原因：                                                         │
│   1. HRV较基线下降22%，身体还在恢复中                           │
│   2. 昨晚只睡了5.5小时，低于你平时的7小时                       │
│   3. ACWR达到1.4，训练负荷已经偏高                              │
│                                                                  │
│   建议：今天以轻度恢复性活动为主，比如30分钟散步或瑜伽。         │
│   好好休息一晚，明天状态应该会好转。"                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 12.4 本地LLM选型与集成

#### 推荐模型

| 模型 | 大小 | 特点 | iOS适配 |
|------|------|------|---------|
| **Phi-3-mini** | 3.8B | 微软出品，推理快，质量高 | ⭐ 首选 |
| **Gemma 2B** | 2B | Google出品，轻量 | 低端设备备选 |
| **Llama 3.2 1B/3B** | 1-3B | Meta最新，边缘设备优化 | 备选 |
| **Qwen2 1.5B** | 1.5B | 阿里，中文友好 | 中文场景 |

#### iOS运行方式

```swift
// MARK: - 本地LLM引擎 (基于llama.cpp)

class LocalLLMEngine {
    
    private var llamaContext: OpaquePointer?  // llama.cpp上下文
    private let modelPath: String
    private let maxTokens: Int
    private var isLoaded = false
    
    init(modelPath: String, maxTokens: Int = 512) {
        self.modelPath = modelPath
        self.maxTokens = maxTokens
    }
    
    /// 加载模型 (App启动时异步调用)
    func loadModel() async throws {
        // 模型参数配置
        var params = llama_model_default_params()
        params.n_gpu_layers = 0  // iOS不使用GPU层
        
        // 加载GGUF格式模型
        guard let model = llama_load_model_from_file(modelPath, params) else {
            throw LLMError.modelLoadFailed
        }
        
        // 创建上下文
        var ctxParams = llama_context_default_params()
        ctxParams.n_ctx = 4096       // 上下文长度
        ctxParams.n_batch = 512      // 批处理大小
        ctxParams.n_threads = 4      // CPU线程数
        
        llamaContext = llama_new_context_with_model(model, ctxParams)
        isLoaded = true
        
        print("✅ 本地LLM加载完成，模型大小: \(getModelSize())MB")
    }
    
    /// 生成回答
    func generate(prompt: String) async throws -> String {
        guard isLoaded, let ctx = llamaContext else {
            throw LLMError.modelNotLoaded
        }
        
        // 分词
        let tokens = tokenize(prompt)
        
        // 推理生成
        var output = ""
        var generatedTokens = 0
        
        while generatedTokens < maxTokens {
            // 获取下一个token
            let nextToken = llama_sample_token(ctx, /* sampling params */)
            
            // 检查结束标记
            if nextToken == llama_token_eos(ctx) {
                break
            }
            
            // 解码token为文本
            let tokenText = decodeToken(nextToken)
            output += tokenText
            generatedTokens += 1
        }
        
        return output.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    /// 流式生成 (UI实时显示)
    func generateStream(prompt: String) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                guard isLoaded else {
                    continuation.finish(throwing: LLMError.modelNotLoaded)
                    return
                }
                
                let tokens = tokenize(prompt)
                var generatedTokens = 0
                
                while generatedTokens < maxTokens {
                    let nextToken = sampleNextToken()
                    
                    if isEndOfSequence(nextToken) {
                        break
                    }
                    
                    let tokenText = decodeToken(nextToken)
                    continuation.yield(tokenText)
                    generatedTokens += 1
                }
                
                continuation.finish()
            }
        }
    }
    
    // MARK: - 辅助方法
    
    private func tokenize(_ text: String) -> [Int32] {
        // 使用llama.cpp的分词器
        // ...
        return []
    }
    
    private func decodeToken(_ token: Int32) -> String {
        // 将token解码为文本
        // ...
        return ""
    }
    
    private func getModelSize() -> Int {
        // 获取模型文件大小
        let fileManager = FileManager.default
        if let attrs = try? fileManager.attributesOfItem(atPath: modelPath),
           let size = attrs[.size] as? Int {
            return size / 1024 / 1024
        }
        return 0
    }
}

enum LLMError: Error {
    case modelLoadFailed
    case modelNotLoaded
    case generationFailed
}
```

### 12.5 RAG知识库系统

#### 知识库架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      RAG 知识库架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   知识来源                          本地存储                     │
│   ─────────                         ─────────                    │
│                                                                  │
│   ┌─────────────┐                  ┌─────────────────────────┐  │
│   │ 科学论文     │   chunk+embed   │                         │  │
│   │ • HRV研究   │────────────────▶│   SQLite + sqlite-vss   │  │
│   │ • 睡眠科学  │                  │   (向量搜索扩展)        │  │
│   │ • 训练理论  │                  │                         │  │
│   │ • ACSM指南  │                  │   knowledge.db (~50MB)  │  │
│   └─────────────┘                  │   • chunks表 (文本)     │  │
│                                    │   • vectors表 (向量)    │  │
│   ┌─────────────┐                  │                         │  │
│   │ 专业书籍    │   chunk+embed   │                         │  │
│   │ • 运动生理  │────────────────▶│                         │  │
│   │ • 营养学    │                  └─────────────────────────┘  │
│   │ • 睡眠科学  │                             │                 │
│   └─────────────┘                             │                 │
│                                               ▼                 │
│   ┌─────────────┐                  ┌─────────────────────────┐  │
│   │ 规则知识    │                  │     向量相似度检索       │  │
│   │ • 训练原则  │───直接存储─────▶│     Top-K匹配           │  │
│   │ • 恢复建议  │                  │     阈值过滤            │  │
│   └─────────────┘                  └─────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 知识分类

| 类别 | 内容示例 | 条目数 | 更新频率 |
|------|---------|--------|---------|
| **核心论文** | HRV与恢复关系、ACWR理论、睡眠阶段研究 | ~500条 | 季度 |
| **指南标准** | ACSM运动指南、WHO睡眠建议 | ~100条 | 年度 |
| **训练原则** | 周期化训练、超量恢复、减量策略 | ~150条 | 稳定 |
| **营养知识** | 运动前后营养、睡眠营养、补剂建议 | ~200条 | 季度 |
| **规则知识** | 阈值判断、状态映射、建议模板 | ~150条 | 按需 |
| **最新研究** | 新发表论文摘要 | ~100条 | 月度 |

#### RAG引擎实现

```swift
// MARK: - RAG检索引擎

class RAGEngine {
    
    private let db: Connection           // SQLite连接
    private let embedder: TextEmbedder   // 文本嵌入 (MiniLM)
    
    init(databasePath: String) throws {
        db = try Connection(databasePath)
        embedder = try TextEmbedder()
        
        // 加载sqlite-vss向量搜索扩展
        try db.execute("SELECT load_extension('vss0')")
    }
    
    /// 检索相关知识
    func retrieve(query: String, topK: Int = 3, threshold: Float = 0.7) -> [KnowledgeChunk] {
        
        // 1. 将查询文本向量化
        let queryVector = embedder.embed(query)
        
        // 2. 向量相似度搜索
        let sql = """
            SELECT c.id, c.content, c.source, c.category, v.distance
            FROM knowledge_chunks c
            JOIN knowledge_vectors v ON c.id = v.chunk_id
            WHERE vss_search(v.embedding, ?)
            ORDER BY v.distance ASC
            LIMIT ?
        """
        
        var results: [KnowledgeChunk] = []
        
        for row in try! db.prepare(sql, queryVector.data, topK) {
            let distance = row[4] as! Float
            
            // 相似度阈值过滤
            let similarity = 1.0 - distance
            guard similarity >= threshold else { continue }
            
            results.append(KnowledgeChunk(
                id: row[0] as! String,
                content: row[1] as! String,
                source: row[2] as! String,
                category: row[3] as! String,
                similarity: similarity
            ))
        }
        
        return results
    }
    
    /// 格式化检索结果为Prompt上下文
    func formatAsContext(_ chunks: [KnowledgeChunk]) -> String {
        guard !chunks.isEmpty else {
            return "暂无相关参考资料"
        }
        
        var context = ""
        for (index, chunk) in chunks.enumerated() {
            context += """
            
            【参考\(index + 1)】\(chunk.source)
            \(chunk.content)
            
            """
        }
        return context
    }
    
    /// 添加新知识片段
    func addChunk(_ chunk: KnowledgeChunk) throws {
        // 1. 存储文本
        try db.run("""
            INSERT INTO knowledge_chunks (id, content, source, category)
            VALUES (?, ?, ?, ?)
        """, chunk.id, chunk.content, chunk.source, chunk.category)
        
        // 2. 生成并存储向量
        let vector = embedder.embed(chunk.content)
        try db.run("""
            INSERT INTO knowledge_vectors (chunk_id, embedding)
            VALUES (?, ?)
        """, chunk.id, vector.data)
    }
}

// MARK: - 知识片段模型

struct KnowledgeChunk: Codable {
    let id: String
    let content: String          // 文本内容 (通常200-500字)
    let source: String           // 来源 (论文标题/书名/章节)
    let category: String         // 分类 (hrv/sleep/training/nutrition/rules)
    var similarity: Float = 0    // 检索相似度
}

// MARK: - 文本嵌入模型 (MiniLM)

class TextEmbedder {
    
    private let model: MLModel  // CoreML模型
    
    init() throws {
        // 加载MiniLM CoreML模型 (384维向量)
        let config = MLModelConfiguration()
        config.computeUnits = .cpuOnly
        model = try MiniLMEmbedder(configuration: config).model
    }
    
    func embed(_ text: String) -> EmbeddingVector {
        // 1. 分词
        let tokens = tokenize(text)
        
        // 2. 模型推理
        let input = try! MLMultiArray(shape: [1, 128], dataType: .int32)
        for (i, token) in tokens.prefix(128).enumerated() {
            input[i] = NSNumber(value: token)
        }
        
        let output = try! model.prediction(from: MiniLMInput(input_ids: input))
        
        // 3. 提取向量 (384维)
        return EmbeddingVector(data: output.embeddings)
    }
    
    private func tokenize(_ text: String) -> [Int32] {
        // 使用预训练的分词器
        // ...
        return []
    }
}

struct EmbeddingVector {
    let data: [Float]  // 384维向量
}
```

### 12.6 用户数据上下文构建

```swift
// MARK: - 用户数据上下文生成器

class UserContextBuilder {
    
    private let dataStore: LocalDataStore
    
    /// 构建用户数据摘要，注入到Prompt中
    func buildUserContext() -> String {
        
        let today = Date()
        let baseline = dataStore.getBaseline()
        let todayMetrics = dataStore.getDailyMetrics(for: today)
        let last7Days = dataStore.getMetricsForLastDays(7)
        let recentInsights = dataStore.getRecentInsights(days: 3)
        
        var context = """
        ## 用户当前状态
        
        ### 今日数据
        - 准备度分数: \(formatOptional(todayMetrics?.readinessScore, format: "%.0f"))/100
        - HRV (RMSSD): \(formatOptional(todayMetrics?.hrvRMSSD, format: "%.0f")) ms
        - 静息心率: \(formatOptional(todayMetrics?.restingHR, format: "%.0f")) bpm
        - 昨晚睡眠: \(formatSleep(todayMetrics?.sleep))
        - 训练负荷(ACWR): \(formatOptional(todayMetrics?.acwr, format: "%.2f"))
        
        ### 个人基线 (过去30天平均)
        - HRV基线: \(formatOptional(baseline?.hrvRMSSDMean, format: "%.0f")) ms
        - 睡眠时长基线: \(formatOptional(baseline?.sleepDurationMean.map { $0 / 60 }, format: "%.1f")) 小时
        - 睡眠效率基线: \(formatOptional(baseline?.sleepEfficiencyMean.map { $0 * 100 }, format: "%.0f"))%
        
        ### 近7天变化趋势
        \(format7DayTrend(last7Days))
        
        ### 近期洞察记录
        \(formatRecentInsights(recentInsights))
        """
        
        // 添加用户档案信息
        if let profile = dataStore.getUserProfile() {
            context += """
            
            ### 用户档案
            - 年龄: \(profile.age)岁
            - 生理年龄: \(formatOptional(profile.physiologicalAge, format: "%.1f"))岁
            - 运动目标: \(profile.fitnessGoal)
            - 运动水平: \(profile.activityLevel)
            """
            
            if profile.isFemale, let cycleDay = profile.menstrualCycleDay {
                context += "\n- 月经周期: 第\(cycleDay)天"
            }
        }
        
        return context
    }
    
    // MARK: - 格式化辅助
    
    private func formatOptional<T>(_ value: T?, format: String) -> String {
        guard let v = value else { return "未知" }
        if let d = v as? Double {
            return String(format: format, d)
        }
        return "\(v)"
    }
    
    private func formatSleep(_ sleep: SleepMetrics?) -> String {
        guard let s = sleep else { return "无数据" }
        let hours = String(format: "%.1f", Double(s.totalMinutes) / 60)
        let efficiency = Int(s.efficiency * 100)
        return "\(hours)小时，效率\(efficiency)%"
    }
    
    private func format7DayTrend(_ metrics: [DailyMetrics]) -> String {
        guard metrics.count >= 3 else { return "数据不足，无法分析趋势" }
        
        // 计算HRV趋势
        let hrvValues = metrics.compactMap { $0.hrvRMSSD }
        let hrvTrend = calculateTrendDirection(hrvValues)
        
        // 计算睡眠趋势
        let sleepValues = metrics.map { Double($0.sleep.totalMinutes) }
        let sleepTrend = calculateTrendDirection(sleepValues)
        
        return """
        - HRV趋势: \(hrvTrend)
        - 睡眠趋势: \(sleepTrend)
        - 本周平均准备度: \(calculateAverage(metrics.compactMap { $0.readinessScore }))分
        """
    }
    
    private func calculateTrendDirection(_ values: [Double]) -> String {
        guard values.count >= 3 else { return "数据不足" }
        
        let recent3 = Array(values.suffix(3))
        let earlier3 = Array(values.prefix(3))
        
        let recentAvg = recent3.reduce(0, +) / Double(recent3.count)
        let earlierAvg = earlier3.reduce(0, +) / Double(earlier3.count)
        
        let change = (recentAvg - earlierAvg) / earlierAvg * 100
        
        if change > 5 {
            return "上升 (+\(String(format: "%.0f", change))%)"
        } else if change < -5 {
            return "下降 (\(String(format: "%.0f", change))%)"
        } else {
            return "稳定"
        }
    }
}
```

### 12.7 Prompt模板设计

```swift
// MARK: - AI Coach Prompt模板

struct AICoachPromptTemplate {
    
    /// 系统提示词
    static let systemPrompt = """
    你是Motivue AI健康教练，专注于运动恢复、睡眠优化和训练指导。

    ## 你的能力
    1. 基于用户的生理数据（HRV、睡眠、训练负荷）提供个性化建议
    2. 解释数据背后的科学原理
    3. 提供具体可行的行动建议
    4. 回答运动科学、恢复、营养相关问题

    ## 回答原则
    1. 简洁明了，控制在200字以内
    2. 必须结合用户当前数据给出针对性建议
    3. 引用知识库内容时要准确
    4. 承认不确定性，不做过度承诺
    5. 涉及医疗问题建议咨询专业人士

    ## 回答格式
    - 先直接回答问题
    - 再简要解释原因
    - 最后给出1-2条具体建议
    """
    
    /// 构建完整Prompt
    static func buildPrompt(
        userQuestion: String,
        userContext: String,
        ragContext: String
    ) -> String {
        
        return """
        \(systemPrompt)
        
        ---
        
        \(userContext)
        
        ---
        
        ## 相关知识参考
        \(ragContext)
        
        ---
        
        ## 用户问题
        \(userQuestion)
        
        请基于用户当前状态和相关知识，给出个性化的回答:
        """
    }
}
```

### 12.8 知识库更新机制

#### 本地与云端知识库关系

```
┌─────────────────────────────────────────────────────────────────┐
│              本地 vs 云端 知识库设计                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   云端 (完整版)                    本地 (精简版)                 │
│   ═══════════════                  ═══════════════               │
│                                                                  │
│   • 全部论文原文                   • 论文摘要+关键结论           │
│   • 完整书籍内容                   • 书籍核心片段                │
│   • 历史所有版本                   • 仅最新版本                  │
│   • 多语言支持                     • 中文为主                    │
│   • ~5GB                           • ~50-100MB                   │
│                                                                  │
│   用途:                            用途:                         │
│   • 云端LLM复杂问题检索            • 本地LLM日常问答检索          │
│   • 知识审核和管理                 • 离线使用                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 更新流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    知识库更新流程                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   云端知识管理后台                                               │
│   ─────────────────                                              │
│   1. 添加新论文/书籍                                             │
│   2. 分块 (chunk) + 向量化 (embed)                               │
│   3. 人工审核确认                                                │
│   4. 打包生成增量更新包                                          │
│   5. 发布新版本号                                                │
│                                                                  │
│                              │                                   │
│                              ▼ API推送                           │
│                                                                  │
│   iOS客户端                                                      │
│   ─────────                                                      │
│   1. App启动时检查版本: GET /api/knowledge/version               │
│   2. 版本不一致则下载增量包: GET /api/knowledge/updates?from=v1  │
│   3. 后台解压并合并到本地SQLite                                  │
│   4. 更新本地版本号                                              │
│   5. 下次问答使用新知识                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 更新服务实现

```swift
// MARK: - 知识库更新服务

class KnowledgeUpdateService {
    
    private let ragEngine: RAGEngine
    private let apiClient: APIClient
    private let currentVersionKey = "knowledge_version"
    
    /// 检查并更新知识库 (App启动/后台刷新时调用)
    func checkAndUpdate() async {
        do {
            // 1. 获取当前本地版本
            let currentVersion = UserDefaults.standard.string(forKey: currentVersionKey) ?? "0"
            
            // 2. 查询云端最新版本
            let latestInfo = try await apiClient.request(
                endpoint: "/api/knowledge/version",
                method: .GET
            ) as KnowledgeVersionResponse
            
            guard latestInfo.version != currentVersion else {
                print("✅ 知识库已是最新版本: v\(currentVersion)")
                return
            }
            
            print("📦 发现新版本: v\(currentVersion) → v\(latestInfo.version)")
            
            // 3. 下载增量更新包
            let updates = try await apiClient.request(
                endpoint: "/api/knowledge/updates",
                method: .GET,
                params: ["from_version": currentVersion]
            ) as KnowledgeUpdatesResponse
            
            // 4. 应用更新
            var addedCount = 0
            var updatedCount = 0
            var deletedCount = 0
            
            for update in updates.updates {
                switch update.action {
                case "add":
                    try ragEngine.addChunk(update.chunk)
                    addedCount += 1
                case "update":
                    try ragEngine.updateChunk(update.chunk)
                    updatedCount += 1
                case "delete":
                    try ragEngine.deleteChunk(id: update.chunkId)
                    deletedCount += 1
                default:
                    break
                }
            }
            
            // 5. 保存新版本号
            UserDefaults.standard.set(latestInfo.version, forKey: currentVersionKey)
            
            print("✅ 知识库更新完成: 新增\(addedCount)条, 更新\(updatedCount)条, 删除\(deletedCount)条")
            
        } catch {
            print("⚠️ 知识库更新失败: \(error)")
        }
    }
}

// MARK: - API响应模型

struct KnowledgeVersionResponse: Codable {
    let version: String        // "2025.12.1"
    let chunksCount: Int       // 1500
    let lastUpdated: String    // "2025-12-10T10:00:00Z"
}

struct KnowledgeUpdatesResponse: Codable {
    let fromVersion: String
    let toVersion: String
    let updates: [KnowledgeUpdate]
}

struct KnowledgeUpdate: Codable {
    let action: String         // "add", "update", "delete"
    let chunkId: String
    let chunk: KnowledgeChunk?
}
```

### 12.9 本地/云端路由策略

```swift
// MARK: - AI Coach 主服务

class AICoachService {
    
    private let localLLM: LocalLLMEngine
    private let ragEngine: RAGEngine
    private let contextBuilder: UserContextBuilder
    private let cloudService: CloudLLMService?
    
    private var isLocalReady = false
    
    // 云端调用次数限制
    private let maxCloudCallsPerDay = 10
    private var todayCloudCalls = 0
    
    // MARK: - 主问答接口
    
    func ask(_ question: String) async throws -> AICoachResponse {
        
        // 1. 构建用户上下文 (从本地数据库)
        let userContext = contextBuilder.buildUserContext()
        
        // 2. RAG检索相关知识 (从本地知识库)
        let relevantChunks = ragEngine.retrieve(query: question, topK: 3)
        let ragContext = ragEngine.formatAsContext(relevantChunks)
        
        // 3. 组装完整Prompt
        let prompt = AICoachPromptTemplate.buildPrompt(
            userQuestion: question,
            userContext: userContext,
            ragContext: ragContext
        )
        
        // 4. 决定使用本地还是云端
        let routeDecision = decideRoute(question: question)
        
        let answer: String
        let source: String
        
        switch routeDecision {
        case .local:
            answer = try await localLLM.generate(prompt: prompt)
            source = "local"
            
        case .cloud:
            guard let cloud = cloudService else {
                throw AICoachError.cloudNotAvailable
            }
            guard todayCloudCalls < maxCloudCallsPerDay else {
                throw AICoachError.cloudQuotaExceeded
            }
            
            answer = try await cloud.generate(prompt: prompt)
            source = "cloud"
            todayCloudCalls += 1
            
        case .localWithCloudFallback:
            do {
                answer = try await localLLM.generate(prompt: prompt)
                source = "local"
            } catch {
                // 本地失败，尝试云端
                if let cloud = cloudService, todayCloudCalls < maxCloudCallsPerDay {
                    answer = try await cloud.generate(prompt: prompt)
                    source = "cloud"
                    todayCloudCalls += 1
                } else {
                    throw error
                }
            }
        }
        
        return AICoachResponse(
            answer: postProcess(answer),
            sources: relevantChunks.map { $0.source },
            generatedBy: source,
            remainingCloudCalls: maxCloudCallsPerDay - todayCloudCalls
        )
    }
    
    // MARK: - 路由决策
    
    enum RouteDecision {
        case local                    // 本地处理
        case cloud                    // 云端处理
        case localWithCloudFallback   // 本地优先，失败走云端
    }
    
    private func decideRoute(question: String) -> RouteDecision {
        
        // 1. 本地模型未就绪 → 云端
        if !isLocalReady {
            return .cloud
        }
        
        // 2. 复杂问题标识 → 云端
        let complexKeywords = ["为什么会这样", "详细解释", "深入分析", "对比", "长期", "原理是什么"]
        let isComplex = complexKeywords.contains { question.contains($0) }
        
        // 3. 问题过长 → 云端 (可能需要更强推理)
        let isTooLong = question.count > 150
        
        // 4. 用户主动要求 → 云端
        let userWantsCloud = question.contains("用AI") || question.contains("详细")
        
        if isComplex || isTooLong || userWantsCloud {
            // 检查配额
            if todayCloudCalls < maxCloudCallsPerDay {
                return .cloud
            } else {
                return .localWithCloudFallback
            }
        }
        
        // 5. 简单问题 → 本地
        return .local
    }
    
    private func postProcess(_ answer: String) -> String {
        var result = answer
        
        // 移除特殊标记
        result = result.replacingOccurrences(of: "<|endoftext|>", with: "")
        result = result.replacingOccurrences(of: "</s>", with: "")
        
        // 截断过长回答
        if result.count > 800 {
            result = String(result.prefix(800)) + "..."
        }
        
        return result.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

// MARK: - 响应模型

struct AICoachResponse {
    let answer: String              // 回答内容
    let sources: [String]           // 引用的知识来源
    let generatedBy: String         // "local" 或 "cloud"
    let remainingCloudCalls: Int    // 剩余云端调用次数
}
```

### 12.10 云端API定义

```swift
// MARK: - 云端LLM服务

class CloudLLMService {
    
    private let apiClient: APIClient
    private let model: String
    
    init(model: String = "gpt-4o-mini") {
        self.apiClient = APIClient()
        self.model = model
    }
    
    func generate(prompt: String) async throws -> String {
        
        let response = try await apiClient.request(
            endpoint: "/api/ai/chat",
            method: .POST,
            body: CloudChatRequest(
                model: model,
                prompt: prompt,
                maxTokens: 512,
                temperature: 0.7
            )
        ) as CloudChatResponse
        
        return response.answer
    }
}

// MARK: - 云端API模型

struct CloudChatRequest: Codable {
    let model: String
    let prompt: String
    let maxTokens: Int
    let temperature: Double
}

struct CloudChatResponse: Codable {
    let answer: String
    let tokensUsed: Int
    let model: String
}
```

**云端API端点**:
```
POST /api/ai/chat
Authorization: Bearer {user_token}

Request:
{
    "model": "gpt-4o-mini",
    "prompt": "...",
    "max_tokens": 512,
    "temperature": 0.7
}

Response:
{
    "answer": "根据你的数据...",
    "tokens_used": 245,
    "model": "gpt-4o-mini"
}
```

### 12.11 UI集成

```swift
// MARK: - AI Coach 聊天界面

struct AICoachChatView: View {
    
    @StateObject private var viewModel = AICoachViewModel()
    @State private var inputText = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // 消息列表
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 16) {
                        // 欢迎消息
                        WelcomeMessage()
                        
                        // 对话历史
                        ForEach(viewModel.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                        
                        // 正在生成
                        if viewModel.isGenerating {
                            TypingIndicator()
                                .id("typing")
                        }
                    }
                    .padding()
                }
                .onChange(of: viewModel.messages.count) { _ in
                    withAnimation {
                        proxy.scrollTo(viewModel.messages.last?.id ?? "typing", anchor: .bottom)
                    }
                }
            }
            
            Divider()
            
            // 快捷问题
            QuickQuestionsBar(
                questions: [
                    "今天适合怎么练？",
                    "我的HRV怎么样？",
                    "如何改善睡眠？",
                    "为什么我这么累？"
                ],
                onSelect: { viewModel.send($0) }
            )
            
            // 剩余云端次数提示
            if viewModel.remainingCloudCalls <= 3 {
                HStack {
                    Image(systemName: "cloud")
                    Text("今日剩余\(viewModel.remainingCloudCalls)次深度分析")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.vertical, 4)
            }
            
            // 输入区域
            HStack(spacing: 12) {
                TextField("问问AI教练...", text: $inputText)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { sendMessage() }
                
                Button(action: sendMessage) {
                    Image(systemName: "paperplane.fill")
                        .foregroundColor(inputText.isEmpty ? .gray : .accentColor)
                }
                .disabled(inputText.isEmpty || viewModel.isGenerating)
            }
            .padding()
        }
        .navigationTitle("AI教练")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    private func sendMessage() {
        guard !inputText.isEmpty else { return }
        viewModel.send(inputText)
        inputText = ""
    }
}

// MARK: - 消息气泡

struct MessageBubble: View {
    let message: ChatMessage
    
    var body: some View {
        HStack {
            if message.isUser { Spacer() }
            
            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                Text(message.content)
                    .padding(12)
                    .background(message.isUser ? Color.accentColor : Color(.systemGray6))
                    .foregroundColor(message.isUser ? .white : .primary)
                    .cornerRadius(16)
                
                // 来源标识
                if !message.isUser {
                    HStack(spacing: 4) {
                        Image(systemName: message.source == "cloud" ? "cloud" : "iphone")
                            .font(.caption2)
                        if !message.references.isEmpty {
                            Text("参考: \(message.references.joined(separator: ", "))")
                                .font(.caption2)
                        }
                    }
                    .foregroundColor(.secondary)
                }
            }
            
            if !message.isUser { Spacer() }
        }
    }
}

// MARK: - ViewModel

class AICoachViewModel: ObservableObject {
    
    @Published var messages: [ChatMessage] = []
    @Published var isGenerating = false
    @Published var remainingCloudCalls = 10
    
    private let aiCoach = AICoachService()
    
    func send(_ question: String) {
        // 添加用户消息
        messages.append(ChatMessage(
            content: question,
            isUser: true,
            source: "user",
            references: []
        ))
        
        isGenerating = true
        
        Task {
            do {
                let response = try await aiCoach.ask(question)
                
                await MainActor.run {
                    messages.append(ChatMessage(
                        content: response.answer,
                        isUser: false,
                        source: response.generatedBy,
                        references: response.sources
                    ))
                    remainingCloudCalls = response.remainingCloudCalls
                    isGenerating = false
                }
            } catch {
                await MainActor.run {
                    messages.append(ChatMessage(
                        content: "抱歉，遇到了一些问题: \(error.localizedDescription)",
                        isUser: false,
                        source: "error",
                        references: []
                    ))
                    isGenerating = false
                }
            }
        }
    }
}

struct ChatMessage: Identifiable {
    let id = UUID()
    let content: String
    let isUser: Bool
    let source: String        // "local", "cloud", "user", "error"
    let references: [String]  // 引用的知识来源
}
```

### 12.12 实现路线图

| 阶段 | 任务 | 优先级 | 预估时间 |
|------|------|--------|---------|
| **P0** | 规则引擎洞察系统 | ✅ 已完成 | - |
| **P1** | 本地LLM集成 (llama.cpp) | 高 | 2周 |
| **P1** | RAG知识库搭建 (SQLite+向量) | 高 | 1周 |
| **P1** | 用户数据上下文构建 | 高 | 3天 |
| **P2** | 云端LLM备选接入 | 中 | 1周 |
| **P2** | 知识库更新机制 | 中 | 1周 |
| **P2** | 调用次数限制管理 | 中 | 2天 |
| **P3** | UI优化 & 流式输出 | 低 | 1周 |
| **P3** | 知识库内容填充 | 持续 | 持续 |

---

## 十三、附录

### 13.1 参考文档
- 原 Python 代码: `Motivue-Backend/libs/`
- SDK 头文件: `iOS-SDK1.0.45/phone/UTEBluetoothRYApi.framework/Headers/`
- SDK数据优化计划: `docs/SDK数据优化计划.md`
- Apple HealthKit 文档

### 13.2 版本历史

| 版本 | 日期 | 变更 |
|-----|------|------|
| 1.0 | 2025-12-10 | 初始版本 |
| 1.1 | 2025-12-10 | 移除Apple Sleep Score，Journal不参与计算 |
| 1.2 | 2025-12-10 | 整合SDK优化计划: 新增VO2max/恢复时间/PAI生理年龄指标; 新增device_recovery/training_effect CPT |
| 1.3 | 2025-12-10 | 完整实现版: 新增Swift完整数据模型定义; SDK睡眠解析逻辑; Core Data Schema; 生理年龄完整实现; 女性月经周期算法; iOS后台采集配置; 验证用例和单元测试; 个性化CPT云端同步API |
| 1.4 | 2025-12-10 | 新增洞察系统: WHOOP风格因果关联洞察; 自然语言生成器; 日报洞察生成器; SwiftUI展示组件; 完整触发规则表 |
| 1.5 | 2025-12-10 | 新增AI Coach系统: 本地LLM(Phi-3/Llama)+RAG架构; 用户数据+知识库联合推理; 云端备选+调用限制; 知识库更新机制; 完整SwiftUI聊天界面 |
| **1.6** | **2025-12-10** | **通用因果发现系统**: 不写死字段，任何运动/Journal记录自动参与; 统计相关性分析; 多周期(日/周/月)洞察; 小模型生成文案; 可扩展字段配置 |

### 13.3 联系方式
- 技术负责人: [填写]
- 文档维护: [填写]

