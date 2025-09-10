# iOS 26 睡眠评分迁移指南

## 📱 新功能概述

iOS 26 引入了苹果原生睡眠评分功能，我们的系统现已完美支持！

**核心优势**：
- ✨ **智能评分**：苹果评分综合了睡眠时长、效率、一致性、觉醒频率等多维度数据
- 🔄 **二选一逻辑**：iOS 26用户优先使用苹果评分，老版本用户完全不受影响
- 🛡️ **优雅降级**：苹果评分不可用时自动fallback到传统方法
- ⚖️ **权重优化**：苹果评分权重1.0（满权重），因为它已包含完整睡眠质量信息

---

## 🔄 API变更说明

### 新增字段

```json
{
  "ios_version": 26,                    // 必填：iOS版本号
  "apple_sleep_score": 75.5,           // 可选：苹果睡眠评分 (0-100)
  
  // 原有字段保持不变，向下兼容
  "sleep_performance_state": "medium",  // iOS < 26 或无苹果评分时使用
  "sleep_duration_hours": 7.5,         // 传统方法backup
  "sleep_efficiency": 0.88,            // 传统方法backup
  "restorative_sleep": "medium"         // 恢复性睡眠仍需要（苹果未提供）
}
```

### 评分映射规则

| 苹果评分范围 | 映射级别 | 说明 |
|------------|---------|------|
| 80-100分 | excellent | 极好睡眠质量 |
| 70-79分  | good     | 良好睡眠质量（72分在此） |
| 60-69分  | fair     | 一般睡眠质量 |
| 40-59分  | poor     | 较差睡眠质量 |
| 0-39分   | very_poor| 极差睡眠质量 |

---

## 🎯 使用场景

### 场景1：iOS 26用户有苹果评分 ✨ 推荐
```json
{
  "user_id": "user_123",
  "date": "2024-09-10",
  "ios_version": 26,
  "apple_sleep_score": 72,        // 使用苹果评分
  "restorative_sleep": "medium",  // 仍需提供，苹果未包含此数据
  "hrv_trend": "stable"
}
```
**行为**：优先使用苹果评分(72→good)，跳过传统睡眠时长+效率计算

### 场景2：iOS 26用户无苹果评分 🔄 自动降级
```json
{
  "user_id": "user_123", 
  "date": "2024-09-10",
  "ios_version": 26,
  // 无apple_sleep_score字段
  "sleep_duration_hours": 7.5,
  "sleep_efficiency": 0.88,
  "restorative_sleep": "medium"
}
```
**行为**：自动fallback到传统睡眠时长+效率评估

### 场景3：老版本iOS用户 ✅ 完全兼容
```json
{
  "user_id": "user_123",
  "date": "2024-09-10", 
  "ios_version": 15,              // iOS < 26
  "sleep_performance_state": "good",
  "restorative_sleep": "medium"
}
```
**行为**：使用传统评估方法，行为完全不变

---

## 📊 权重调整

| 评分类型 | 之前权重 | 新权重 | 说明 |
|---------|---------|-------|------|
| 苹果评分 | - | **1.0** | 满权重，综合了多维数据 |
| 传统sleep_performance | 0.90 | 0.90 | 保持不变 |
| restorative_sleep | 0.95 | 0.95 | 保持不变，苹果未提供 |

**设计理念**：苹果评分 = 传统的 sleep_performance + sleep_efficiency + 睡眠一致性 + 觉醒频率

---

## 🔧 实施步骤

### 第1步：前端集成 📱
```swift
// iOS 26+ 获取苹果睡眠评分
if #available(iOS 26.0, *) {
    let sleepScore = getSleepScoreFromHealthKit() // 0-100分
    payload["ios_version"] = 26
    payload["apple_sleep_score"] = sleepScore
} else {
    payload["ios_version"] = UIDevice.current.systemVersion
    // 继续使用传统睡眠数据
}
```

### 第2步：API调用 🔗
```python
# Python后端示例
payload = {
    "user_id": "user_123",
    "date": "2024-09-10",
    "ios_version": 26,
    "apple_sleep_score": 75,
    "restorative_sleep": "medium",  # 仍需提供
    # ...其他字段
}

result = compute_readiness_from_payload(payload)
print(f"准备度: {result['final_readiness_score']}")
```

### 第3步：验证测试 ✅
```bash
# 运行兼容性测试
python test_ios26_sleep_score.py

# 预期结果：
# ✅ iOS 26 + 苹果评分 → 使用苹果评分
# ✅ iOS 26 + 无苹果评分 → fallback传统
# ✅ iOS < 26 → 完全兼容传统方法
```

---

## ⚠️ 注意事项

### 数据要求
1. **恢复性睡眠数据仍需提供** - 苹果评分不包含深睡眠/REM比例信息
2. **HRV数据独立** - 苹果评分不影响HRV趋势评估
3. **Hooper主观评分** - 保持独立，与苹果评分互补

### 边界情况
1. **同时提供两套数据** - 苹果评分优先，传统数据被忽略
2. **苹果评分解析失败** - 自动fallback到传统方法，无错误中断
3. **网络问题/权限不足** - 优雅降级，不影响整体计算

### 兼容性保证
- ✅ **向下兼容** - 老版本iOS用户体验完全不变
- ✅ **渐进升级** - 用户可以随时升级到iOS 26，无需特殊配置
- ✅ **数据安全** - 传统睡眠数据仍作为备份，确保服务连续性

---

## 📚 示例文件

我们提供了完整的iOS 26示例：

- `readiness/examples/ios26_male_request.json` - 男性用户示例
- `readiness/examples/ios26_female_request.json` - 女性用户示例 
- `readiness/examples/ios26_fallback_request.json` - fallback场景示例
- `readiness/examples/ios26_history_male_30days.csv` - 30天历史数据示例

---

## 🚀 升级建议

### 立即升级
- **移动端团队** - 集成iOS 26睡眠评分API获取
- **后端团队** - 更新API调用，添加新字段支持

### 分阶段部署  
1. **Phase 1** - 后端部署，支持新字段（向下兼容）
2. **Phase 2** - 移动端更新，iOS 26用户开始使用苹果评分
3. **Phase 3** - 数据分析，验证苹果评分vs传统评分效果

### 监控指标
- iOS 26用户占比和苹果评分使用率
- fallback到传统方法的频率
- 苹果评分vs传统评分的准确度对比

---

## 💡 FAQ

**Q: 升级后会影响现有用户吗？**
A: 完全不会。老版本iOS用户体验完全不变，只有iOS 26用户能享受新功能。

**Q: 如果苹果评分不可用怎么办？**  
A: 系统会自动fallback到传统的睡眠时长+效率评估，用户无感知。

**Q: 为什么还需要提供恢复性睡眠数据？**
A: 苹果的睡眠评分不包含深睡眠/REM的详细比例，这对运动恢复很重要。

**Q: 苹果评分的权重为什么是1.0？**
A: 因为苹果评分已经综合了睡眠时长、效率、一致性、觉醒频率等，相当于之前多个指标的组合。

**Q: 部署需要多长时间？**
A: 后端更新可立即部署（向下兼容），移动端按正常发版周期即可。

---

🎉 **恭喜！您的系统现已支持最先进的iOS 26睡眠评分功能！**