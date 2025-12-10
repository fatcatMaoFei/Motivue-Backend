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
| HRV | `heartRateVariability` | 1-29低/30-60正常/61-101良好/102+优秀 | 核心指标 |
| 血氧 | `bloodOxygen` | % | **仪表盘展示** |
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
│  ├─ SDNN (HRV)                    ├─ weekly_pai                │
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

**原公式：**
```
PhysAge = 35 - 8×SDNN_z - 5×CSS_z - 6×RHR_z
```

**增强版公式 (加入SDK数据)：**

```swift
// 有VO2max时
age_adjust = -4.0 * sdnn_z      // HRV
           + -3.0 * css_z       // 睡眠
           + -4.0 * rhr_z       // 静息心率
           + -8.0 * vo2max_z    // VO2max (最高权重)
           + -3.0 * recovery_z  // 恢复能力
           + -2.0 * pai_z       // 活动量

// 无VO2max时
age_adjust = -8.0 * sdnn_z      // HRV (权重提升)
           + -5.0 * css_z       // 睡眠
           + -6.0 * rhr_z       // 静息心率
           + -3.0 * recovery_z  // 恢复能力
           + -2.0 * pai_z       // 活动量

phys_age = max(18, min(80, 35 + age_adjust))
```

**z分数计算：**

| 指标 | 基准值 | 标准差 | 说明 |
|-----|--------|-------|------|
| SDNN | 50 ms | 20 ms | 高SDNN更年轻 |
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
}
```

### 7.2 周报 API 端点

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

## 十一、附录

### 11.1 参考文档
- 原 Python 代码: `Motivue-Backend/libs/`
- SDK 头文件: `iOS-SDK1.0.45/phone/UTEBluetoothRYApi.framework/Headers/`
- SDK数据优化计划: `iossdk/docs/SDK数据优化计划.md`
- Apple HealthKit 文档

### 11.2 版本历史

| 版本 | 日期 | 变更 |
|-----|------|------|
| 1.0 | 2025-12-10 | 初始版本 |
| 1.1 | 2025-12-10 | 移除Apple Sleep Score，Journal不参与计算 |
| 1.2 | 2025-12-10 | 整合SDK优化计划: 新增VO2max/恢复时间/PAI生理年龄指标; 新增device_recovery/training_effect CPT |
| **1.3** | **2025-12-10** | **完整实现版**: 新增Swift完整数据模型定义; SDK睡眠解析逻辑; Core Data Schema; 生理年龄完整实现; 女性月经周期算法; iOS后台采集配置; 验证用例和单元测试; 个性化CPT云端同步API |

### 11.3 联系方式
- 技术负责人: [填写]
- 文档维护: [填写]

