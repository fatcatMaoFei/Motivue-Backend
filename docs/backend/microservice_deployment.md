# 基线微服务部署指南

## 1. 服务架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端APP       │    │  基线微服务      │    │ 准备度微服务     │
│  (HealthKit)    │────│  (Baseline)     │────│ (Readiness)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   消息队列       │    │   用户数据库     │    │   CPT数据库     │
│  (RabbitMQ)     │    │ (User Baselines)│    │(Personal CPT)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 2. Docker部署配置

### 基线微服务 (baseline-service)

```dockerfile
# Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY baseline/ ./baseline/
EXPOSE 8001
CMD ["uvicorn", "baseline.api:app", "--host", "0.0.0.0", "--port", "8001"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  baseline-service:
    build: .
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/baseline_db
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://rabbitmq:5672
    depends_on:
      - postgres
      - redis
      - rabbitmq

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: baseline_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "15672:15672"
```

## 3. 单用户更新API

### 基线更新端点
```python
# baseline/api.py
from fastapi import FastAPI, HTTPException
from .service import update_baseline_smart, get_user_baseline

app = FastAPI()

@app.post("/api/baseline/user/{user_id}/update")
async def update_user_baseline(user_id: str):
    """更新单个用户基线"""
    result = await update_baseline_smart(user_id)
    
    if result['status'] == 'success':
        # 发送消息通知readiness服务更新CPT表
        await notify_readiness_service(user_id, result['baseline'])
        
    return result

@app.get("/api/baseline/user/{user_id}")
async def get_baseline(user_id: str):
    """获取用户基线"""
    baseline = get_user_baseline(user_id)
    if not baseline:
        raise HTTPException(404, "用户基线不存在")
    return baseline.to_dict()
```

## 4. 数据存储分离

### 用户基线表结构
```sql
CREATE TABLE user_baselines (
    user_id VARCHAR(50) PRIMARY KEY,
    sleep_baseline_hours FLOAT NOT NULL,
    hrv_baseline_sdnn FLOAT NOT NULL,
    baseline_source VARCHAR(20) DEFAULT 'default',
    data_quality_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_incremental_update TIMESTAMP,
    last_full_update TIMESTAMP
);

-- 索引优化查询
CREATE INDEX idx_user_baselines_updated ON user_baselines(updated_at);
CREATE INDEX idx_user_baselines_source ON user_baselines(baseline_source);
```

### CPT表结构 (在readiness服务中)
```sql
CREATE TABLE user_cpt_tables (
    user_id VARCHAR(50) PRIMARY KEY,
    sleep_good_threshold FLOAT,
    sleep_medium_threshold FLOAT,
    hrv_good_threshold FLOAT,
    hrv_medium_threshold FLOAT,
    cpt_probabilities JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 5. 消息队列通信

### 基线更新通知
```python
# 当基线更新时发送消息
async def notify_readiness_service(user_id: str, baseline: dict):
    message = {
        'event': 'baseline_updated',
        'user_id': user_id,
        'baseline': baseline,
        'timestamp': datetime.now().isoformat()
    }
    
    await message_queue.publish('readiness.baseline_updated', message)
```

### Readiness服务监听更新
```python
# readiness服务监听基线更新
async def handle_baseline_update(message: dict):
    user_id = message['user_id']
    new_baseline = message['baseline']
    
    # 重新计算个性化CPT表
    new_cpt = calculate_personalized_cpt(user_id, new_baseline)
    
    # 更新用户CPT表
    save_user_cpt_table(user_id, new_cpt)
```

## 6. 部署步骤

### 第1步：数据库准备
```bash
# 创建数据库
docker exec -it postgres createdb baseline_db

# 运行迁移
docker exec -it baseline-service python -m baseline.migrations
```

### 第2步：启动服务
```bash
# 启动所有服务
docker-compose up -d

# 检查服务状态
curl http://localhost:8001/health
```

### 第3步：初始化默认基线
```bash
# 为新用户创建默认基线
curl -X POST http://localhost:8001/api/baseline/defaults/initialize
```

## 7. 单用户更新流程

```mermaid
sequenceDiagram
    participant App as 移动APP
    participant BS as 基线微服务
    participant DB as 基线数据库
    participant MQ as 消息队列
    participant RS as 准备度微服务
    participant CPT as CPT数据库
    
    App->>BS: POST /user/123/update
    BS->>DB: 获取用户123历史数据
    BS->>BS: 计算新基线
    BS->>DB: 保存用户123基线
    BS->>MQ: 发送基线更新消息
    MQ->>RS: 通知用户123基线变更
    RS->>CPT: 更新用户123 CPT表
    BS->>App: 返回更新结果
```

## 8. 为什么能单独更新

1. **用户隔离**: 每个用户数据完全分离存储
2. **独立计算**: 基线计算只使用该用户的历史数据
3. **异步更新**: 通过消息队列异步更新相关服务
4. **缓存策略**: 用户基线独立缓存，互不影响

## 9. 扩展性

- **水平扩展**: 可部署多个基线微服务实例
- **负载均衡**: 根据用户ID分片处理
- **缓存优化**: Redis缓存热点用户基线
- **批量处理**: 支持批量用户基线更新

这样的架构确保了每个用户的基线和CPT表完全独立，更新时互不影响。