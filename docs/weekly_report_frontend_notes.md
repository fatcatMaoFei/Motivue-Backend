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
| 当日训练数据 | `daily_au`（必填，日粒度）、`rpe` / `duration_minutes` / `au`（可选） | 训练记录界面（与 AU、RPE、时长同一表单） | `user_daily.daily_au`；可选写入 `user_daily.objective.training_sessions[]`（JSON，含 `type_tags[]`） |
| Hooper 问卷 | `fatigue`, `soreness`, `stress`, `sleep` (1–7) | 客户端问卷 | `raw_inputs.hooper`，周报历史也会引用 |
| Lifestyle / Journal | `alcohol_consumed`, `late_caffeine`, `screen_before_bed`, `late_meal`, `is_sick`, `is_injured`, `lifestyle_tags[]`, `sliders{fatigue_slider, mood_slider,...}` | 客户端问卷 | `raw_inputs.journal`、`history.lifestyle_events` |
| 报告备注 | `report_notes`（自由文本，由教练/用户填写） | 客户端编辑 | `raw_inputs.report_notes`（周报 Finalizer 会引用） |

> 提交体例参见 `samples/original_payload_sample.json`：顶层可传今日快照（睡眠/HRV/Hooper/Journal），但**周报必需的数据是 `history[7]` + `recent_training_au`**。若未维护训练 session 明细，可忽略 `training_sessions` 字段。

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

入口：`uvicorn apps/weekly-report-api/main:app --reload`  
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

- `markdown_report` 为完整周报；从本版本起，正文会包含图表占位锚点（见下节）。
- `chart_ids` 指示图表的“全局推荐顺序”（用于图表面板或不解析占位的页面）。
- 图表数据在 `package.charts[]`（`ChartSpec{chart_id,title,chart_type,data}`）。
- 样例输出：`samples/original_workflow_state.json`（Phase 3）、`samples/original_package_sample.json`（Phase 4）、`samples/original_final_report.{json,md}`（Phase 5）。
- 当 `use_llm=false` 时，响应仍包含完整结构，只是 Analyst/Communicator/Finalizer 由规则组装。

### 3.1 Markdown 图表占位锚点（固定位置）

- 语法：`[[chart:<chart_id>]]`
- Finalizer 会在固定章节注入占位（仅当对应图表存在时才注入）：
  - 训练负荷与表现：`training_load`（表格后）；可选 `readiness_trend`
  - 恢复与生理（HRV 段）：`hrv_trend`、`readiness_vs_hrv`
  - 恢复与生理（睡眠段）：`sleep_duration`、`sleep_structure`
  - 主观反馈：`hooper_radar`
  - 生活方式事件：`lifestyle_timeline`

前端渲染步骤：
1. 扫描 `final_report.markdown_report` 中的 `[[chart:...]]` 占位；
2. 按 `chart_id` 从 `package.charts[]` 中取对应 `ChartSpec` 的 `title/chart_type/data` 渲染图表组件；
3. 找不到的占位跳过（不渲染）；
4. 若需图表面板或总览，按 `final_report.chart_ids` 顺序排列。

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

1. `weekly_report/trend_builder.py` 定义所有 `ChartSpec`。常用 `chart_id`：`readiness_trend`、`readiness_vs_hrv`、`hrv_trend`、`sleep_duration`、`sleep_structure`、`training_load`、`hooper_radar`、`lifestyle_timeline`。渲染时优先根据 Markdown 占位插入；不解析占位时，按 `final_report.chart_ids` 顺序渲染图表面板。
2. Markdown 不包含图表数据；前端需根据占位中的 `chart_id` 去 `package.charts[]` 取 `ChartSpec` 渲染。
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

---

## 6. iOS 图表（SwiftUI）数据规格与渲染规范

本节用于 iOS 端统一图表渲染的数据契约与规范。后端推荐提供“分析接口”返回简单时序，前端用 SwiftUI Charts 渲染；不强依赖 `ChartSpec`。

### 6.1 大类与图组
- Readiness：`readiness_score`（日分数）、`readiness_band`
- Training Load：`daily_au`（柱状）、`acute_load`、`chronic_load`、`acwr_value`、`acwr_band`（折线）
- HRV：`hrv_rmssd`（折线）、`hrv_z_score`（折线，辅轴）、`hrv_baseline_mu`（基线）
- Sleep：`sleep_duration_hours`（折线）、`sleep_efficiency`（0..1）、`restorative_ratio`（0..1）、`sleep_baseline_hours`（基线）
- Subjective（Hooper）：`fatigue/soreness/stress/sleep`（1..7，折线/雷达）
- Lifestyle：按日事件标注（垂直标记/标注）

### 6.2 通用返回结构（建议）
```json
{
  "user_id": "u001",
  "dates": ["2025-09-09", "2025-09-10", ...],
  "series": {
    "<metric_key>": [number|null, ...],
    "<metric_key2>": [number|null, ...]
  },
  "baseline": {
    "<metric_key>": number|null
  },
  "thresholds": {
    "<metric_key>": {"low": number|null, "high": number|null}
  }
}
```
说明：
- `dates[]` 与 `series[*]` 一一对齐；缺失值用 null。
- `baseline` 可为标量（画水平线），或如需逐日基线可将其也放入 `series`。
- `thresholds` 用于绘制参考带（例如 ACWR 安全窗、readiness 正常区间）。

### 6.3 叠加规则（Overlay）
- 在任意图组内支持选择 1–N 条序列叠加渲染；采用颜色区分，必要时使用双 Y 轴（例如 HRV vs Hooper 疲劳）。
- X 轴对齐方式：按 `dates[]` 完整对齐；不对齐的数据由前端插值或跳空显示。
- 推荐组合：
  - HRV（RMSSD/Z）↔ Hooper 疲劳/压力（辅助轴）
  - Sleep duration ↔ ACWR/Readiness（辅助轴）
  - Daily AU（柱）↔ Readiness（线）

### 6.4 渲染细则（SwiftUI）
- 折线：平滑、缺失断点不连线；柱状：间距与对齐一致。
- 基线：以虚线/markLine 绘制，标注 `Baseline`；阈值/安全窗用浅色 `markArea`。
- 单位：AU（无单位）、HRV（ms）、sleep（h）、eff/restorative（0..1）；必要时百分比表示。
- 平滑与异常：不做前端平滑计算；异常值（如 `daily_au > 2000`）画图时可直接跳过（留空），并在图注提示“已过滤异常值”。
- 交互：多序列图例可见；支持手势查看某日所有序列的数值。

### 6.5 建议的分析接口（草案，仅文档约定）
- `GET /analytics/training-load/{user_id}?window_days=28`
  - 返回：`dates[]`, `series.daily_au`, `series.acute_load`, `series.chronic_load`, `series.acwr_value`, `thresholds.acwr_value={low:0.6, high:1.3}`
- `GET /analytics/hrv/{user_id}?window_days=28`
  - 返回：`series.hrv_rmssd`, `series.hrv_z_score`, `baseline.hrv_rmssd=hrv_mu`
- `GET /analytics/sleep/{user_id}?window_days=28`
  - 返回：`series.sleep_duration_hours`, `series.sleep_efficiency`, `series.restorative_ratio`, `baseline.sleep_duration_hours`
- `GET /analytics/subjective/{user_id}?window_days=28`
  - 返回：`series.hooper_fatigue/soreness/stress/sleep`

> 注意：接口实现可以统一由后端聚合，或由客户端拉取 `user_daily` 后按本结构组装；本规范仅约定前端需要的字段与渲染方式。

---

## 7. Journal 标签（lifestyle）规范与前缀（可扩展）

- 输入位：`raw_inputs.journal.lifestyle_tags[]`（字符串数组，可扩展）。聚合后写入 `history[i].lifestyle_events[]`。
- 标准标签（建议优先使用）：`travel`、`night_shift`、`alcohol`、`late_meal`、`screen_before_bed`、`sick`、`injured` 等。
- 训练类型推荐使用前缀，便于规则识别：
  - 运动类：`sport:tennis`、`sport:run`、`sport:swim` …
  - 力量部位：`strength:chest`、`strength:back`、`strength:legs` …
- 前端实现：在“选择标签”的控件中分组/前缀化，所选标签写入 `journal.lifestyle_tags[]`；后端不改表，仅透传。
- 规则消费：洞察/Planner 会优先匹配标准标签；前缀标签用于识别类型（例如“同日组合压力”“部位分布不均衡”等）。

规范建议：小写、蛇形，去重与非法字符过滤；未知标签按“自定义事件”渲染，不触发强阈值。
