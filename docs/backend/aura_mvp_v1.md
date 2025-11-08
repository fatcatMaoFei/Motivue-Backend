## Aura MVP V1 说明（后端 + 计算逻辑）

直白版，开箱即用。包含接口、入参/出参、表结构与启动方式。

### 一、服务与端口
- Readiness 服务（就绪度计算）: http://localhost:8000
  - 文档: /docs
- Baseline 服务（个人基线）: http://localhost:8001
  - 文档: /docs
- RabbitMQ 管理端: http://localhost:15672（guest/guest）

### 二、核心能力
- HealthKit 原始数据 → 枚举（睡眠表现/恢复性睡眠/HRV 趋势）→ 计算就绪度（分数/诊断/分布）
- iOS≥26 时支持苹果原生睡眠评分（有评分则优先使用）
- 自动注入 Baseline：未显式传基线字段时，Readiness 会自动读取/拉取并缓存
- 个性化 CPT（P(Evidence|State)）：通过 MQ 事件写入 `user_models`，计算时自动覆盖全局权重

### 三、数据表结构（Supabase/Postgres）

1) `user_daily`（Readiness 按日存档）
- user_id: varchar（PK part）
- date: date（PK part）
- previous_state_probs: json（昨天后验，供次日作为先验）
- training_load: varchar（可空）
- journal: json
- objective: json（sleep_performance_state/restorative_sleep/hrv_trend）
- hooper: json（fatigue/soreness/stress/sleep）
- cycle: json
- final_readiness_score: int4
- final_diagnosis: varchar
- final_posterior_probs: json
- next_previous_state_probs: json
- daily_au: int4（可空，RPE×时长）

2) `user_models`（Readiness 个性化模型仓库）
- user_id: varchar（PK part）
- model_type: varchar（PK part，当前固定 'EMISSION_CPT'）
- payload_json: json（例如 {"emission_cpt": {...}}）
- version: varchar（可选）
- created_at: timestamp（可选）

3) `user_baselines`（Baseline 个人基线参数）
- user_id: varchar（PK）
- sleep_baseline_hours: int4/float8
- sleep_baseline_eff: int4/float8（0..1）
- rest_baseline_ratio: int4/float8（0..1）
- hrv_baseline_mu: int4/float8（SDNN，ms）
- hrv_baseline_sd: int4/float8（>0）

### 四、Readiness 接口

1) 健康检查
- GET /health → {"status":"ok"}

2) 模板（示例字段）
- GET /healthkit/template → 返回一份可参考的字段模板（JSON），便于组装请求（MVP 不会去拉真实 HK 数据）

3) 计算就绪度（核心）
- POST /readiness/from-healthkit
- 必填：
  - user_id: string
  - date: YYYY-MM-DD
  - previous_state_probs: {Peak, Well-adapted, FOR, Acute Fatigue, NFOR, OTS}（服务端会归一化；首日可用 {0.1,0.5,0.3,0.1,0,0}）
- 可选：
  - ios_version（int）/ apple_sleep_score（0..100）：iOS≥26 且有评分则优先使用评分
  - HK 数值：sleep_duration_hours / total_sleep_minutes，sleep_efficiency（0..1/0..100），restorative_ratio（0..1），hrv_rmssd_today / 3day/7day_avg / baseline_mu/sd 等
  - journal：{alcohol_consumed, late_caffeine, screen_before_bed, late_meal, is_sick, is_injured, ...}
  - hooper：{fatigue, soreness, stress, sleep} ∈ 1..7
  - cycle：{day（≥1）, cycle_length（20..40）}
  - daily_au：int≥0（落库用，不影响当天计算）
- 自动注入 Baseline：
  - 若未显式传入基线字段，服务会先读本地缓存 `UserBaseline`；若没有会请求 Baseline 服务并写回缓存
  - 若远端/缓存 hrv_baseline_sd≤0，会兜底为 5.0，保证 HRV z 分数可用（不影响已有有效 sd 的用户）
- 响应：
  - prior_probs / final_posterior_probs / final_readiness_score / final_diagnosis
  - update_history / evidence_pool
  - next_previous_state_probs（供次日作为 previous_state_probs）

请求最小示例：
```json
{
  "user_id": "u001",
  "date": "2025-09-13",
  "journal": {"is_sick": false},
  "hooper": {"fatigue": 3, "soreness": 3, "stress": 3, "sleep": 3},
  "hrv_rmssd_today": 42,
  "previous_state_probs": {"Peak":0.1,"Well-adapted":0.5,"FOR":0.3,"Acute Fatigue":0.1,"NFOR":0,"OTS":0}
}
```

4) 查看基线（便于可视化/刷新缓存）
- GET /baseline/{user_id}?refresh=0|1
  - refresh=0（默认）：读本地缓存
  - refresh=1：忽略缓存，强制请求 Baseline 服务获取最新，并写回缓存

### 五、Baseline 服务接口

1) 计算/更新基线（≥30 天效果最好）
- POST /api/baseline/user/{user_id}/update
- 请求（简化示例）：
```json
{
  "sleep_data": [
    { "date":"2025-08-01T00:00:00Z", "sleep_duration_hours":7.5, "sleep_efficiency":0.88, "total_sleep_minutes":450, "restorative_ratio":0.35 }
    // ...补足到 30~31 天
  ],
  "hrv_data": [
    { "timestamp":"2025-08-01T08:00:00Z", "sdnn_value":42.3 }
    // ...补足到 30~31 天
  ]
}
```
- 响应：`{ status: 'success' | 'success_with_defaults' | 'failed', baseline: {...} }`

2) 获取基线
- GET /api/baseline/user/{user_id} → 返回该用户当前基线参数（sleep_baseline_* / hrv_baseline_* 等）

### 六、个性化 CPT（可选）
- 队列：`readiness.baseline_updated`
- 事件（MVP 可直接携带 CPT）
```json
{
  "event": "baseline_updated",
  "user_id": "u002",
  "emission_cpt": { "hrv_trend": { "rising": { "Peak":0.90, "Well-adapted":0.09, "FOR":0.01, "Acute Fatigue":0, "NFOR":0, "OTS":0 } } }
}
```
- Readiness 后台消费者会把 `emission_cpt` 写入 `user_models`，后续计算自动覆盖全局权重。

### 七、启动与验证
1) 启动
```
docker compose down -v
docker compose up -d rabbitmq
docker compose up -d --build readiness baseline
```
2) 打开文档
- Readiness: http://localhost:8000/docs
- Baseline: http://localhost:8001/docs
3) 基线 → 计算链路
- 先 `POST /api/baseline/user/{id}/update` 写基线
- `GET /baseline/{id}?refresh=1` 查看/刷新缓存
- `POST /readiness/from-healthkit` 计算（可不传基线字段，自动注入）

### 八、注意事项
- 404 访问 `/` 正常；请用本文列出的实际路由
- 睡眠维度想对比基线阈值效应时，不要传 `apple_sleep_score`（或 `ios_version<26`），否则会走苹果评分
- HRV 显示基线效应最明显：today 与（mu, sd）差异越大，`hrv_trend` 越明显


