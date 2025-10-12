# Weekly Report – Front-end Integration

本文档面向客户端团队，梳理：
- 前端需要采集/提交的原始字段
- 后端自动补齐的派生数据
- 各微服务的接口与请求/响应结构（周报 API 与 readiness/consumption 风格保持一致）
- 周报渲染注意事项

所有服务遵循统一流程：**客户端提交原始打卡 → 后端写库/计算 → 对外返回结构化 JSON 或 Markdown**。前端只需保证原始数据完整、按需调用接口即可。

---

## 1. 数据责任分工

### 1.1 客户端必须每日提交的原始字段

| 类别 | 字段 | 说明 / 采集方式 | 后端映射 |
| --- | --- | --- | --- |
| 基础信息 | `user_id`, `date` (YYYY-MM-DD), `gender` (`男性`/`女性`) | 登录态/用户档案 | 所有服务必填 |
| 睡眠原始值 | `total_sleep_minutes`, `in_bed_minutes`, `deep_sleep_minutes`, `rem_sleep_minutes`, *可选* `core_sleep_minutes` | HealthKit / 可穿戴直传原始分钟数；**不用**自行算效率 | `raw_inputs.sleep.*` |
| HRV 原始值 | `hrv_rmssd_today`; *可选* `hrv_rmssd_3day_avg/7day_avg/28day_avg/28day_sd` | HealthKit RMSSD。只有日值也可，后端会滚动缓存 | `raw_inputs.hrv.*` |
| 当日训练 Session | `training_sessions[{label, rpe, duration_minutes, au, notes}]` | 客户端训练记录 | `raw_inputs.training_sessions`（供 readiness/周报使用） |
| Hooper 问卷 | `fatigue`, `soreness`, `stress`, `sleep` (1–7) | 客户端问卷 | `raw_inputs.hooper`，周报历史也会引用 |
| Lifestyle / Journal | `alcohol_consumed`, `late_caffeine`, `screen_before_bed`, `late_meal`, `is_sick`, `is_injured`, `lifestyle_tags[]`, `sliders{fatigue_slider, mood_slider,...}` | 客户端问卷 | `raw_inputs.journal`、`history.lifestyle_events` |
| 报告备注 | `report_notes`（自由文本，由教练/用户填写） | 客户端编辑 | `raw_inputs.report_notes`（周报 Finalizer 会引用） |

> 提交体例参见 `samples/original_payload_sample.json` 中的 `raw_inputs` 部分。

### 1.2 推荐同步的历史/辅助数据

- `recent_training_au`（近 7–28 天 AU 序列）或 `recent_training_loads`（低/中/高标签序列）  
  用于 readiness/周报计算 ACWR；如前端难以拼装，可由后端根据历史 Session 自动生成。
- `daily_au`（当日 AU 数值）若已有则一并提交，便于展示。
- 训练量标签默认映射见 `readiness/constants.py::TRAINING_LOAD_AU`。

### 1.3 后端自动注入的数据（前端无需直接提供）

| 数据 | 来源/说明 |
| --- | --- |
| 睡眠/HRV 基线 (`sleep_baseline_hours`, `hrv_baseline_mu`, …) | 由 `/baseline/{user_id}` 或离线任务写入。缺省时周报 API 会通过可选参数覆盖。 |
| `history` (近 7 天 `WeeklyHistoryEntry[]`) | 后端根据 `user_daily`、训练/Hooper/生活方式表聚合，作为周报 `payload.history`。前端无需手动拼装。 |
| 洞察/复杂度/LLM 回溯 | 在 `run_workflow` 内部生成，包含于响应的 `phase3_state.insights`、`package` 等字段。 |

---

## 2. Readiness / Training 消耗微服务

入口：`uvicorn api.main:app --reload`  
接口风格与周报服务一致，基于 FastAPI 返回 JSON。

### 2.1 `POST /readiness/from-healthkit`
- **作用**：写入当日原始 payload，计算准备度并保存 `user_daily`。
- **关键字段**：

| 字段 | 描述 |
| --- | --- |
| `user_id`, `date`, `gender` | 基础信息 |
| 睡眠输入 | 见 §1.1，全部分钟数 |
| HRV 输入 | `hrv_rmssd_today` + 可选滚动统计 |
| 基线覆盖 (可选) | `sleep_baseline_hours`, `hrv_baseline_mu`, … |
| 训练历史 | `recent_training_au` 或 `recent_training_loads` |
| `training_sessions[]` | 当日训练明细 |
| Journal / Hooper | 见 §1.1 |

- **响应**：`{ final_readiness_score, final_diagnosis, final_posterior_probs, next_previous_state_probs, ... }`

### 2.2 `POST /readiness/consumption`
- **作用**：传入当日训练 Session，返回消耗分数并扣减 `current_readiness_score`。
- **示例请求**：
```json
{
  "user_id": "athlete_001",
  "date": "2025-09-15",
  "sessions": [
    {"label": "高", "rpe": 8, "duration_minutes": 70},
    {"label": "中", "au": 300}
  ]
}
```
- **响应**：`{consumption_score, display_readiness, breakdown, ...}`

### 2.3 `GET /baseline/{user_id}`
- 返回用户睡眠/HRV 基线；用于客户端对齐或在 readiness/周报缺失时补值。

---

## 3. Weekly Report 微服务

入口：`uvicorn weekly_report.api:app --reload`  
接口签名沿用 readiness 微服务风格。

### `POST /weekly-report/run`

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `payload` | object | 今日 raw_inputs + 后端聚合的 `history`。结构见 `samples/original_payload_sample.json`。 |
| `use_llm` | boolean，默认 `false` | `true` 时调用 Gemini（Analyst / Communicator / Critique / Finalizer）；`false` 走规则 fallback。 |
| `persist` | boolean，默认 `false` | `true` 时把 Phase 5 结果写入 `weekly_reports`。需要配置数据库。 |
| `sleep_baseline_hours`, `hrv_baseline_mu` | number，可选 | 当 payload 中缺失或需要重写基线时使用。 |

**响应结构**
```json
{
  "phase3_state": {...},   // ReadinessState (raw_inputs/metrics/insights/insight_reviews)
  "package": {...},        // WeeklyReportPackage (charts + analyst + communicator + critique)
  "final_report": {...},   // WeeklyFinalReport (markdown_report/html_report/chart_ids/call_to_action)
  "persisted": false
}
```

- `markdown_report` 为完整周报，可直接渲染。`chart_ids` 指示图表展示顺序。  
- 样例输出：`samples/original_workflow_state.json`（Phase 3）、`samples/original_package_sample.json`（Phase 4）、`samples/original_final_report.{json,md}`（Phase 5）。
- 当 `use_llm=false` 时，响应仍包含完整结构，只是 Analyst/Communicator/Finalizer 由规则组装。

### `weekly_reports` 表结构（当 `persist=true`）

| 列 | 说明 |
| --- | --- |
| `user_id` | 用户 ID |
| `week_start`, `week_end` | `history` 中最早/最晚日期 |
| `report_payload` | `WeeklyFinalReport` JSON（便于后续渲染/重播） |
| `markdown_report` | Markdown 文本（直接给教练/下载用） |
| `report_version`, `created_at` | 版本信息与生成时间 |

> 当前服务未暴露读取接口，若前端需要查询历史周报可额外实现 `GET /weekly-reports/{user_id}`。

---

## 4. 生理年龄服务（Physio Age）

入口：`uvicorn physio_age.api:app --reload`

### `POST /physio-age`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | string | 必填 |
| `date` | string，可选 | 默认当日 |
| `user_gender` | string (`male`/`female`) | 用于选择参考表 |
| `sdnn_series` | array[float]（≥30） | SDNN 序列 |
| `rhr_series` | array[float]（≥30） | 静息心率序列 |

返回示例：`{status, physiological_age, physiological_age_weighted, css_details, best_age_zscores, ...}`。CSS 计算依赖 `user_daily.device_metrics` 中的睡眠记录。

---

## 5. 周报渲染与其他注意事项

1. `weekly_report/trend_builder.py` 定义所有 `ChartSpec`。常用 `chart_id`：`readiness_trend`、`readiness_vs_hrv`、`hrv_trend`、`sleep_duration`、`sleep_structure`、`training_load`、`hooper_radar`、`lifestyle_timeline`。渲染时按 `final_report.chart_ids` 顺序取对应图表配置。
2. Markdown 不包含图表数据；前端需根据 `chart_id` 查 `package.charts[]` 并渲染。
3. LLM 相关环境变量：
   - `GOOGLE_API_KEY`
   - `READINESS_LLM_MODEL`（默认 `gemini-2.5-flash`）
   - `READINESS_LLM_FALLBACK_MODELS`（逗号分隔）  
   调试可将 `use_llm=false`，走完整规则回退路径。
4. 若 `persisted=false` 且期望写库，请检查数据库配置（`api/db.py`）是否指向正确实例。
5. Phase 3 的规则洞察位于 `phase3_state["insights"]`，结构与 readiness 原有洞察一致，可用于可视化或 debug。
6. 周报运行时间与 LLM 调用次数相关：`use_llm=true` 会依次调用 ToT、Critique、Analyst、Communicator、Finalizer 共 5 次。  
   若只需结构，可保持 `use_llm=false`，或在 `run_workflow` 阶段仅用于预览洞察。

如有接口/字段调整，请同步更新本文档并通知后端团队。
