# 个人基线分类问卷

为数据不足30天的新用户提供合适的默认基线。

## 📋 问卷设计

### **问题1：睡眠需求 (决定sleeper_type)**
**"你通常需要多少小时睡眠才感觉精神充沛？"**

- A. **6-7小时** → `short_sleeper`
- B. **7-8小时** → `normal_sleeper`  
- C. **8-9小时以上** → `long_sleeper`

### **问题2：年龄段 (决定hrv_type)**
**"你的年龄段是？"**

- A. **25岁以下** → `high_hrv`
- B. **25-45岁** → `normal_hrv`
- C. **45岁以上** → `low_hrv`

### **可选问题3：运动习惯 (微调hrv_type)**
**"你的运动习惯是？"**

- A. **经常运动(每周4次以上)** → HRV等级+1
- B. **偶尔运动(每周1-3次)** → 保持当前等级
- C. **很少运动(每月几次)** → HRV等级-1

## 🧮 分类逻辑

### **Sleep Type分类：**
```python
def classify_sleep_type(sleep_hours_needed):
    if sleep_hours_needed <= 7:
        return "short_sleeper"
    elif sleep_hours_needed <= 8:
        return "normal_sleeper"
    else:
        return "long_sleeper"
```

### **HRV Type分类：**
```python
def classify_hrv_type(age, exercise_frequency="normal"):
    # 基础分类
    if age < 25:
        base_hrv = "high_hrv"
    elif age <= 45:
        base_hrv = "normal_hrv" 
    else:
        base_hrv = "low_hrv"
    
    # 运动习惯调整
    if exercise_frequency == "high" and base_hrv == "normal_hrv":
        return "high_hrv"
    elif exercise_frequency == "high" and base_hrv == "low_hrv":
        return "normal_hrv"
    elif exercise_frequency == "low" and base_hrv == "high_hrv":
        return "normal_hrv"
    elif exercise_frequency == "low" and base_hrv == "normal_hrv":
        return "low_hrv"
    
    return base_hrv
```

## 📱 前端实现示例

### **简化版（2个问题）：**
```html
<div class="baseline-questionnaire">
    <h3>个性化睡眠基线设置</h3>
    <p>为了给您提供更准确的准备度评估，请回答以下问题：</p>
    
    <div class="question">
        <label>1. 您通常需要多少小时睡眠才感觉精神充沛？</label>
        <select id="sleep-hours">
            <option value="short">6-7小时</option>
            <option value="normal" selected>7-8小时</option>
            <option value="long">8-9小时以上</option>
        </select>
    </div>
    
    <div class="question">
        <label>2. 您的年龄段是？</label>
        <select id="age-range">
            <option value="young">25岁以下</option>
            <option value="middle" selected>25-45岁</option>
            <option value="senior">45岁以上</option>
        </select>
    </div>
    
    <button onclick="setUserProfile()">设置个人档案</button>
</div>

<script>
function setUserProfile() {
    const sleepMap = {
        'short': 'short_sleeper',
        'normal': 'normal_sleeper', 
        'long': 'long_sleeper'
    };
    
    const hrvMap = {
        'young': 'high_hrv',
        'middle': 'normal_hrv',
        'senior': 'low_hrv'
    };
    
    const sleepType = sleepMap[document.getElementById('sleep-hours').value];
    const hrvType = hrvMap[document.getElementById('age-range').value];
    
    // 保存用户档案
    localStorage.setItem('sleeper_type', sleepType);
    localStorage.setItem('hrv_type', hrvType);
    
    // 调用后端API
    calculateBaseline(sleepType, hrvType);
}
</script>
```

## 🎯 基线对应关系

### **睡眠基线对照表：**
| 用户回答 | sleeper_type | 基线睡眠时长 | good阈值 | medium阈值 |
|----------|-------------|-------------|----------|------------|
| 6-7小时 | short_sleeper | 6.5h | ≥7.5h | ≥6.0h |
| 7-8小时 | normal_sleeper | 7.5h | ≥8.5h | ≥7.0h |
| 8-9小时+ | long_sleeper | 8.5h | ≥9.0h | ≥8.0h |

### **HRV基线对照表：**
| 年龄段 | hrv_type | HRV基线 | 说明 |
|--------|----------|---------|------|
| <25岁 | high_hrv | 55±10ms | 年轻人HRV较高 |
| 25-45岁 | normal_hrv | 40±8ms | 中年人标准HRV |
| 45岁+ | low_hrv | 28±6ms | 年长者HRV较低 |

## 💡 实际效果示例

### **场景：用户睡了7.0小时**

| 用户类型 | 基线 | good阈值 | 判断结果 | 合理性 |
|----------|------|----------|----------|--------|
| 短睡眠型(6.5h基线) | 6.5h | 7.5h | medium | ✅ 略超基线，中等评价 |
| 标准型(7.5h基线) | 7.5h | 8.5h | poor | ✅ 低于基线，需改善 |
| 长睡眠型(8.5h基线) | 8.5h | 9.0h | poor | ✅ 明显不足，急需改善 |

## 🔧 后端集成

### **API调用方式：**
```python
# 获取问卷结果
sleeper_type = request.json.get('sleeper_type', 'normal_sleeper')
hrv_type = request.json.get('hrv_type', 'normal_hrv')

# 计算基线
result = compute_baseline_from_healthkit_data(
    user_id=user_id,
    healthkit_sleep_data=sleep_data,
    healthkit_hrv_data=hrv_data,
    sleeper_type=sleeper_type,
    hrv_type=hrv_type
)
```

### **数据库存储建议：**
```sql
-- 用户档案表
CREATE TABLE user_profiles (
    user_id VARCHAR(255) PRIMARY KEY,
    sleeper_type ENUM('short_sleeper', 'normal_sleeper', 'long_sleeper') DEFAULT 'normal_sleeper',
    hrv_type ENUM('low_hrv', 'normal_hrv', 'high_hrv') DEFAULT 'normal_hrv',
    questionnaire_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## ⚠️ 注意事项

1. **问卷是可选的**：不填问卷直接使用`normal_sleeper`+`normal_hrv`
2. **30天后自动升级**：有足够数据后自动切换到个人基线
3. **可以修改**：用户随时可以重新填写问卷调整类型
4. **不影响个人基线**：问卷只影响默认基线，不影响30天后的个人计算

## 🎉 用户体验

- **新用户**：2个问题，30秒完成，立即获得个性化体验
- **老用户**：自动升级到精准个人基线
- **灵活调整**：发现分类不准确可随时调整