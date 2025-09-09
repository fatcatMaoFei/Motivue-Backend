# Baseline模块部署清单

快速部署个人基线管理系统到生产环境。

## 📋 部署前检查

- [ ] Python 3.8+ 环境已准备
- [ ] 数据库已创建（SQLite/MySQL/PostgreSQL）
- [ ] Redis/RabbitMQ已安装（用于定时任务）
- [ ] 监控系统已准备（Prometheus/Grafana可选）

## 🚀 快速部署（5步完成）

### 第1步：安装基线模块
```bash
# 复制baseline文件夹到项目中
cp -r baseline/ /path/to/your/project/

# 安装依赖
pip install -r requirements.txt
```

### 第2步：初始化数据库
```python
# 创建基线数据表
from baseline.storage import SQLiteBaselineStorage
storage = SQLiteBaselineStorage("baseline.db")
storage.init_db()
```

### 第3步：集成到现有Readiness计算
```python
# 只需在readiness计算入口添加3行代码
from baseline import get_user_baseline, MemoryBaselineStorage

def calculate_readiness(user_id, today_data):
    # 新增：注入个人基线
    storage = MemoryBaselineStorage()  # 或你的存储实现
    baseline = get_user_baseline(user_id, storage)
    if baseline:
        today_data.update(baseline.to_readiness_payload())
    
    # 原有代码不变
    states = map_inputs_to_states(today_data)
    return compute_readiness_from_payload(payload)
```

### 第4步：添加基线计算API
```python
# 在你的API服务中添加
@app.post("/api/baseline/calculate")
def calculate_user_baseline(request):
    from baseline import compute_baseline_from_healthkit_data
    
    result = compute_baseline_from_healthkit_data(
        user_id=request.user_id,
        healthkit_sleep_data=request.sleep_data,
        healthkit_hrv_data=request.hrv_data,
        storage=storage
    )
    return result

@app.post("/api/baseline/update")  
def update_user_baseline(request):
    from baseline import update_baseline_smart
    
    result = update_baseline_smart(
        user_id=request.user_id,
        sleep_data=request.sleep_data,
        hrv_data=request.hrv_data,
        storage=storage
    )
    return result
```

### 第5步：设置定时更新任务
```python
# 使用Celery设置每日更新检查
from celery import Celery
from baseline import check_baseline_update_needed, update_baseline_smart

@celery_app.task
def daily_baseline_check():
    for user_id in get_all_user_ids():
        check = check_baseline_update_needed(user_id, storage)
        if check['needs_update']:
            data = get_user_recent_data(user_id)
            update_baseline_smart(user_id, data['sleep'], data['hrv'], storage)

# 定时配置：每天凌晨2点运行
celery_app.conf.beat_schedule = {
    'baseline-check': {
        'task': 'your_app.daily_baseline_check',
        'schedule': crontab(hour=2, minute=0)
    }
}
```

## ✅ 部署后验证

### 测试基线计算
```bash
# 运行测试脚本验证功能
python test_70_day_complete_flow.py

# 预期输出：70天完整流程成功，最终评分显示
```

### 测试API接口
```bash
# 测试基线计算API
curl -X POST http://localhost:8000/api/baseline/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "sleep_data": [...],
    "hrv_data": [...]
  }'

# 预期响应：{"status": "success", "baseline": {...}}
```

### 验证Readiness集成
```python
# 测试个性化准备度计算
result = calculate_readiness("test_user", today_data)
print(f"个性化评分: {result['final_readiness_score']}")
print(f"使用个人基线: {result.get('personalized', False)}")
```

## 📊 生产监控

### 关键指标监控
- [ ] 基线计算成功率 >95%
- [ ] 平均数据质量分 >0.8
- [ ] 每日更新任务成功执行
- [ ] API响应时间 <2s

### 健康检查
```bash
# 检查基线服务状态
curl http://localhost:8000/health/baseline

# 预期响应：{"status": "healthy", "recent_updates": 150}
```

## 🔧 常见问题解决

### Q1：新用户没有30天数据怎么办？
**A**：自动使用默认基线系统
```python
# 系统会自动判断数据量
# <30天：使用问卷分类的默认基线
# ≥30天：计算个人精准基线
```

### Q2：基线更新失败怎么办？
**A**：检查数据质量和存储
```python
# 检查更新日志
tail -f /logs/baseline.log

# 检查数据质量
from baseline import check_baseline_update_needed
result = check_baseline_update_needed("problematic_user", storage)
print(result)
```

### Q3：如何回滚错误的更新？
**A**：使用版本管理
```python
# 基线更新会自动保存版本历史
# 可以回滚到上一个稳定版本
```

## 📈 扩展配置

### 自定义更新策略
```python
from baseline.updater import UpdateStrategy

# 自定义更新频率
custom_strategy = UpdateStrategy(
    incremental_days=5,     # 5天增量更新
    full_update_days=21,    # 21天完整更新
    incremental_weight=0.4, # 新数据权重40%
    min_data_quality=0.8    # 更高质量要求
)
```

### 多数据库支持
```python
# SQLite（开发/小规模）
storage = SQLiteBaselineStorage("baseline.db")

# MySQL（生产推荐）
storage = MySQLBaselineStorage(
    host="localhost",
    database="baseline_db", 
    user="baseline_user",
    password="secure_password"
)
```

## 🎉 部署完成

部署完成后，你的系统将获得：

- ✅ **新用户**：问卷分类 → 个性化默认基线 → 立即享受个性化评分
- ✅ **老用户**：30天历史数据 → 精准个人基线 → 基于个人模式的准确评估  
- ✅ **自动更新**：7天增量调整 + 30天完整重算 → 基线始终跟上生活变化
- ✅ **零侵入集成**：现有Readiness代码几乎不用改 → 平滑升级

**系统已完全production-ready！** 🚀

---

💡 **需要帮助？**
- 查看 `baseline/DEPLOYMENT_GUIDE.md` 获取详细技术文档
- 查看 `baseline/README.md` 了解功能特性
- 运行 `test_70_day_complete_flow.py` 验证完整流程